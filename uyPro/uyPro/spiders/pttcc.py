import hashlib
import json
import logging
import re

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls, parse_date
from .webmod import convert_traditional_to_simplified


class PttccSpider(scrapy.Spider):
    name = "pttcc"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = self.name

    def start_requests(self):
        homepage = ''
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'inc', '', '1_1_1_1', '')
            # churl = 'https://www.ptt.cc/bbs/Gossiping/index.html'
            # inputdata = {}
            # tweeturl = 'https://www.ptv.com.pk/ptvNews/urduNewsDetail/79254'
            self.taskid = taskid
            self.bid = inputfilename.split('_')[3]
            self.crawler.stats.set_value('inputdata', inputdata)
            self.crawler.stats.set_value('inputfilename', inputfilename)
            self.crawler.stats.set_value('recent_files_append', recent_files_append)
            self.inc = False if dltype == 'full' else True
            if homepage:
                yield scrapy.Request(url=homepage, callback=self.parse)
            elif method == 'getchannel':
                yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl})
            else:
                # gettweet
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.ptt.cc/bbs/Gossiping/index.html',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='r-ent']/div[@class='title']/a/@href").getall()
        for link in links:
            if not link:
                continue
            link = response.urljoin(link)
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            if self.redis_conn.hexists(f'{self.proname}_hash_done_urls', link_hash) and self.inc:
                ch_urls_json = self.redis_conn.hget(f'{self.proname}_hash_done_urls', link_hash)
                ch_urls = json.loads(ch_urls_json) if ch_urls_json else []
                if ch_url in ch_urls:
                    logging.info(f'{link} : repetition')
                else:
                    item = UyproItem()
                    item['ch_url'] = ch_url
                    item['tweet_id'] = link
                    item['taskid'] = self.taskid
                    item['bid'] = self.bid
                    ch_urls.append(ch_url)
                    self.redis_conn.hset(f'{self.proname}_hash_done_urls', link_hash, json.dumps(ch_urls))
                    if_new = True
                    yield item
            else:
                if_new = True
                # print(link)
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        next_url = response.xpath("//a[@class='btn wide'][contains(text(),'‹')]/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

    def article(self, response):
        """
        解析文章详情页面

        提取文章内容、作者、时间、IP地址等信息，
        并提取评论数据保存到BCP文件
        """
        item = UyproItem()
        link = response.meta['link']
        ch_url = response.meta['ch_url']

        # 设置基础字段
        item['ch_url'] = ch_url
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['tweet_lang'] = 'zh'
        item['taskid'] = self.taskid
        item['bid'] = self.bid

        try:
            # ==================== 提取文章内容 ====================

            # 提取标题
            article_title = response.xpath(
                "//div[@class='article-metaline']/span[@class='article-meta-tag'][text()='標題']"
                "/following-sibling::span[@class='article-meta-value']/text()"
            ).get('').strip()

            # 提取作者
            tweet_author = response.xpath(
                "//div[@class='article-metaline']/span[@class='article-meta-tag'][text()='作者']"
                "/following-sibling::span[@class='article-meta-value']/text()"
            ).get('').strip()

            # 提取发布时间
            tweet_createtime_str = response.xpath(
                "//div[@class='article-metaline']/span[@class='article-meta-tag'][text()='時間']"
                "/following-sibling::span[@class='article-meta-value']/text()"
            ).get('').strip()

            # 解析时间 (格式: Sun Nov 16 11:57:31 2025)
            tweet_createtime = parse_date(tweet_createtime_str, default_timezone="Asia/Taipei")

            # 提取文章内容 (去除元数据行和推文)
            main_content = response.xpath("//div[@id='main-content']").get('')

            # 移除元数据行
            content_without_meta = re.sub(
                r'<div class="article-metaline.*?</div>',
                '',
                main_content,
                flags=re.DOTALL
            )
            content_without_meta = re.sub(
                r'<div class="article-metaline-right.*?</div>',
                '',
                content_without_meta,
                flags=re.DOTALL
            )

            # 移除推文区域
            content_without_push = re.sub(
                r'<div class="push">.*?</div>',
                '',
                content_without_meta,
                flags=re.DOTALL
            )

            # 提取纯文本内容
            from scrapy.http import HtmlResponse
            temp_response = HtmlResponse(
                url=response.url,
                body=content_without_push.encode('utf-8'),
                encoding='utf-8'
            )
            article_content = temp_response.xpath("string(//div[@id='main-content'])").get('').strip()

            # 清理内容 (移除发信站信息)
            article_content = re.sub(r'※ 發信站:.*?(?=\n|$)', '', article_content, flags=re.DOTALL)
            article_content = re.sub(r'※ 文章網址:.*?(?=\n|$)', '', article_content)
            article_content = article_content.strip()

            # 提取 IPv4 地址
            tweet_ipv4 = ''
            ipv4_match = response.xpath(
                "//span[@class='f2'][contains(text(), '來自:')]/text()"
            ).get('')
            if ipv4_match:
                # 提取 IP 地址 (格式: 來自: 42.70.2.61 (臺灣))
                ip_pattern = r'來自:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                match = re.search(ip_pattern, ipv4_match)
                if match:
                    tweet_ipv4 = match.group(1)

            # 设置 item 字段
            item['tweet_title'] = article_title
            title_simplified = convert_traditional_to_simplified(article_title)
            item['tweet_title_tslt'] = title_simplified  # 繁体转简体

            item['tweet_content'] = article_content
            content_simplified = convert_traditional_to_simplified(article_content)
            item['tweet_content_tslt'] = content_simplified  # 繁体转简体

            item['tweet_author'] = tweet_author
            item['tweet_createtime'] = tweet_createtime
            item['tweet_ipv4'] = tweet_ipv4

            # 提取图片URL (如果有)
            img_urls = response.xpath("//div[@id='main-content']//img/@src").getall()
            if img_urls:
                item['tweet_img_url'] = img_urls

            # ==================== 提取评论数据 ====================

            comments = []
            comment_nodes = response.xpath("//div[@class='push']")

            for comment_node in comment_nodes:
                # 提取评论类型 (推/噓/→)
                push_tag = comment_node.xpath(".//span[@class='hl push-tag']/text()").get('').strip()

                # 提取评论者ID
                push_userid = comment_node.xpath(".//span[@class='f3 hl push-userid']/text()").get('').strip()

                # 提取评论内容（使用 string() 获取所有文本，包括 <a> 标签内的网址）
                push_content = comment_node.xpath("string(.//span[@class='f3 push-content'])").get('').strip()
                # 移除开头的冒号和空格
                if push_content.startswith(':'):
                    push_content = push_content[1:].strip()

                # 提取评论时间和IP
                push_ipdatetime = comment_node.xpath(".//span[@class='push-ipdatetime']/text()").get('').strip()

                # 解析时间和IP (格式: "118.168.160.228 11/16 11:58")
                comment_ip = ''
                comment_time = ''
                if push_ipdatetime:
                    parts = push_ipdatetime.strip().split()
                    if len(parts) >= 3:
                        comment_ip = parts[0]
                        comment_date = parts[1]  # 11/16
                        comment_hour = parts[2]  # 11:58

                        # 构建完整时间字符串 (使用文章发布年份)
                        if tweet_createtime:
                            year = tweet_createtime.split('-')[0] if '-' in tweet_createtime else '2025'
                            comment_time_str = f"{year}-{comment_date.replace('/', '-')} {comment_hour}:00"
                        else:
                            comment_time_str = f"2025-{comment_date.replace('/', '-')} {comment_hour}:00"

                        # 使用 parse_date() 函数标准化时间格式（与 tweet_createtime 一致）
                        comment_time = parse_date(comment_time_str, default_timezone="Asia/Taipei")

                # 构建评论数据
                comment_simplified = convert_traditional_to_simplified(push_content)
                comment_data = {
                    'ch_url': ch_url,
                    'tweet_id': link,
                    'tweet_url': response.url,
                    'comment_create_time': comment_time,
                    'comment_ch_ids': push_userid,  # 只保存用户ID
                    'comment_topic': push_content,  # 评论内容
                    'comment_topic_tslt': comment_simplified,  # 繁体转简体
                    'comment_ipv4': comment_ip  # IPv4 地址
                }
                comments.append(comment_data)

            # 将评论数据存储到 item 中，由 pipeline 处理
            if comments:
                item['tweet_comments'] = comments

            # ==================== 更新 Redis 并返回 ====================

            link_hash = hashlib.sha1(link.encode()).hexdigest()
            update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
            yield item

        except Exception as e:
            logging.error(f"解析文章失败 {response.url}: {e}")
            import traceback
            logging.error(traceback.format_exc())
