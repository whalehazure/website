import hashlib
import json
import logging
import re

import scrapy
from scrapy.http import FormRequest

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class TaiwanreportsSpider(scrapy.Spider):
    name = "taiwanreports"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = name

    def start_requests(self):
        homepage = ''
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://taiwanreports.com/archives/category/nationwide/political'
            # inputdata = {}
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
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.taiwan-reports.com/archives/category/bothsides',
            'https://www.taiwan-reports.com/archives/category/youth',
            'https://taiwanreports.com/archives/category/nationwide/%E8%A6%81%E8%81%9E',
            'https://taiwanreports.com/archives/category/nationwide/political',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        page = response.meta.get('page', 1)

        # 处理AJAX响应
        if response.meta.get('is_ajax'):
            try:
                data = json.loads(response.text)
                if data.get('success') and data.get('data', {}).get('content'):
                    content_html = ''.join(data['data']['content'])
                    # 创建一个临时的HtmlResponse来解析内容
                    from scrapy.http import HtmlResponse
                    temp_response = HtmlResponse(url=response.url, body=content_html.encode())
                    links = temp_response.xpath("//article//h2[@class='entry-title entry-title-big']/a/@href").getall()
                else:
                    links = []
            except (json.JSONDecodeError, KeyError) as e:
                logging.error(f"解析AJAX响应失败: {e}")
                links = []
        else:
            # 处理普通页面响应
            links = response.xpath("//div[@class='post-description']/div/a/@href|//article/div/header["
                                   "@class='entry-header']/h2/a/@href|//article//h2[@class='entry-title "
                                   "entry-title-big']/a/@href").getall()

        for link in links:
            if not link:
                continue
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        # 处理分页
        if if_new and not response.meta.get('is_ajax'):
            # 检查是否需要使用动态加载
            ajax_patterns = ['nationwide/%E8%A6%81%E8%81%9E', 'nationwide/political']
            if any(pattern in ch_url for pattern in ajax_patterns):
                # 提取AvenewsVars参数
                avenews_vars = self._extract_avenews_vars(response)
                if avenews_vars:
                    yield self._create_ajax_request(ch_url, avenews_vars, page + 1)
            else:
                # 使用传统分页
                next_url = response.xpath("//div[@class='nav-links']/a[@class='next page-numbers']/@href|"
                                          "//div[@class='nav-links']/div[@class='nav-previous']/a/@href").get('')
                if next_url:
                    yield scrapy.Request(next_url, callback=self.parse_sec, meta={'ch_url': ch_url})
        elif if_new and response.meta.get('is_ajax') and links:
            # 继续AJAX分页
            avenews_vars = response.meta.get('avenews_vars')
            if avenews_vars:
                yield self._create_ajax_request(ch_url, avenews_vars, page + 1)

    @staticmethod
    def _extract_avenews_vars(response):
        """从页面中提取AvenewsVars参数"""
        try:
            # 查找包含AvenewsVars的script标签
            script_content = response.xpath("//script[@id='avenews-load-posts-js-extra']/text()").get()
            if not script_content:
                return None

            # 提取nonce
            nonce_match = re.search(r'"nonce":"([^"]+)"', script_content)
            nonce = nonce_match.group(1) if nonce_match else ''

            # 提取ajaxurl
            ajaxurl_match = re.search(r'"ajaxurl":"([^"]+)"', script_content)
            ajaxurl = ajaxurl_match.group(1) if ajaxurl_match else ''
            ajaxurl = ajaxurl.replace('\\/', '/')  # 处理转义的斜杠

            query_vars_match = re.search(r'"query_vars":"(.*?)"(?=\s*};)', script_content)
            if not query_vars_match:
                # 备用匹配方式
                query_vars_match = re.search(r'"query_vars":"([^"]*(?:\\"[^"]*)*)"', script_content)

            query_vars = query_vars_match.group(1) if query_vars_match else ''
            # 处理转义字符：保留JSON结构，只处理必要的转义
            query_vars = query_vars.replace('\\"', '"').replace('\\/', '/')

            return {
                'nonce': nonce,
                'ajaxurl': ajaxurl,
                'query_vars': query_vars
            }
        except Exception as e:
            logging.error(f"提取AvenewsVars失败: {e}")
            return None

    def _create_ajax_request(self, ch_url, avenews_vars, page):
        """创建AJAX分页请求"""
        try:
            ajax_url = avenews_vars['ajaxurl']
            nonce = avenews_vars['nonce']
            query_vars = avenews_vars['query_vars']

            # 构建POST数据
            form_data = {
                'action': 'avenews_load_posts',
                'nonce': nonce,
                'query_vars': query_vars,
                'page': str(page)
            }

            return FormRequest(
                url=ajax_url,
                formdata=form_data,
                callback=self.parse_sec,
                meta={
                    'ch_url': ch_url,
                    'page': page,
                    'is_ajax': True,
                    'avenews_vars': avenews_vars
                }
            )
        except Exception as e:
            logging.error(f"创建AJAX请求失败: {e}")
            return None

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        lang = 'zh'
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = lang
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
