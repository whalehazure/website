import hashlib
import json
import logging
import re

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls, translate_text_googleapi, parse_date
from .webmod import get_map


class LynasrareearthsSpider(scrapy.Spider):
    name = "lynasrareearths"
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
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://lynasrareearths.com/investors-media/briefings/'
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
                if 'ynasrareearths.com/investors-media/news-and-media' in churl:
                    yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl})
                elif 'lynasrareearths.com/investors-media/briefings' in churl:
                    yield scrapy.Request(url=churl, callback=self.parse_trd, meta={'ch_url': churl})
                else:
                    yield scrapy.Request(url=churl, callback=self.parse_fou_one, meta={'ch_url': churl})
            else:
                # gettweet
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://lynasrareearths.com/investors-media/news-and-media/',
            'https://lynasrareearths.com/investors-media/asx-announcements/',
            'https://lynasrareearths.com/investors-media/reporting-centre/annual-reports/',
            'https://lynasrareearths.com/investors-media/reporting-centre/esg-reports/',
            'https://lynasrareearths.com/investors-media/reporting-centre/presentations/',
            'https://lynasrareearths.com/investors-media/reporting-centre/financial-reports/',
            'https://lynasrareearths.com/investors-media/briefings/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@id='content']//div[@class='CommunitiesContent']/a/@href").getall()
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

        next_url = response.xpath("//div[@id='content']//a[@class='next page-numbers']/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

    def parse_trd(self, response):
        ch_url = response.meta['ch_url']
        # 获取标签页内容中的所有p标签
        ps = response.xpath("//div[contains(@id,'elementor-tab-content')]/p")

        current_title = ""
        current_content = []
        current_links = []

        for p in ps:
            text = p.xpath('.//text()').getall()
            text = ' '.join([t.strip() for t in text if t.strip()])

            # 检查是否为日期标题
            if p.xpath('.//span[@style="font-weight: bolder;"]|.//strong').get():
                # 如果已收集数据，生成前一个item
                if current_title and (current_content or current_links):
                    yield self.create_item(ch_url, current_title, current_content, current_links)

                # 开始新的分组
                current_title = text
                current_content = []
                current_links = []
            else:
                # 获取当前p标签中的链接
                links = p.xpath('.//a/@href').getall()
                if links:
                    current_links.extend(links)
                # 如果文本不为空，添加到内容中
                if text:
                    current_content.append(text)

        # 不要忘记生成最后一个item
        if current_title and (current_content or current_links):
            yield self.create_item(ch_url, current_title, current_content, current_links)

    def create_item(self, ch_url, title, content, links):
        """创建格式统一的item的辅助方法"""
        link = links[-1] if links else ""  # 如果有多个链接，使用最后一个
        if not link:
            return None

        link_hash = hashlib.sha1(link.encode()).hexdigest()

        # 检查是否存在重复URL
        if self.redis_conn.hexists(f'{self.proname}_hash_done_urls', link_hash) and self.inc:
            ch_urls_json = self.redis_conn.hget(f'{self.proname}_hash_done_urls', link_hash)
            ch_urls = json.loads(ch_urls_json) if ch_urls_json else []
            if ch_url in ch_urls:
                logging.info(f'{link} : repetition')
                return None

        # 创建并填充item
        item = UyproItem()
        item['ch_url'] = ch_url
        item['tweet_url'] = link
        item['tweet_id'] = link
        item['tweet_lang'] = 'en'
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_title'] = title
        item['tweet_content'] = '\n'.join(content)
        item['tweet_title_tslt'] = translate_text_googleapi(title)
        item['tweet_content_tslt'] = translate_text_googleapi(item['tweet_content'])

        # 从标题中提取日期并解析
        date_match = re.search(r'\d+\s+(?:[A-Z]+|[A-Z][a-z]+)\s+\d{4}', title)
        if date_match:
            tweet_createtime = date_match.group()
            item['tweet_createtime'] = parse_date(tweet_createtime)
        else:
            logging.info(f"Date not found in title: {title}")

        # 如果不是增量更新，更新URL缓存
        if not self.inc:
            update_ch_urls(self.redis_conn, self.proname, link_hash, ch_url)

        return item

    def parse_fou_one(self, response):
        ch_url = response.meta['ch_url']
        ch_url_dict = {
            'lynasrareearths.com/investors-media/asx-announcements': 'https://wcsecure.weblink.com.au/Clients/lynascorp/HeadlineJsonP.aspx?numberHdPerPage=200&pageNumber=1&year=0&search=',
            'lynasrareearths.com/investors-media/reporting-centre/annual-reports': 'https://wcsecure.weblink.com.au/Clients/lynascorp/HeadlineJsonP.aspx?hdGroup=1&numberHdPerPage=200&pageNumber=1&year=0&search=',
            'lynasrareearths.com/investors-media/reporting-centre/esg-reports': 'https://wcsecure.weblink.com.au/Clients/lynascorp/HeadlineJsonP.aspx?hdGroup=6&numberHdPerPage=200&pageNumber=1&year=0&search=',
            'lynasrareearths.com/investors-media/reporting-centre/presentations': 'https://wcsecure.weblink.com.au/Clients/lynascorp/HeadlineJsonP.aspx?hdGroup=4&numberHdPerPage=200&pageNumber=1&year=0&search=',
            'lynasrareearths.com/investors-media/reporting-centre/financial-reports': 'https://wcsecure.weblink.com.au/Clients/lynascorp/HeadlineJsonP.aspx?hdGroup=5&numberHdPerPage=200&pageNumber=1&year=0&search=',
        }
        # 获取对应链接
        target_url = next((value for key, value in ch_url_dict.items() if key in ch_url), None)
        yield response.follow(url=target_url, callback=self.parse_fou,
                              meta={'ch_url': ch_url, 'target_url': target_url})

    def parse_fou(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        target_url = response.meta['target_url']
        max_year = response.meta.get('max_year', 0)
        json_str = re.search(r'wl_headlinesFunction\((.*)\)', response.text).group(1)
        data = json.loads(f"[{json_str}]")
        headlines = data[0]['headlines']
        # total_headlines = data[1]['totalHeadlines']
        max_year = max_year if max_year else data[2]['maxYear']
        min_year = data[3]['minYear']

        for headline in headlines:
            link = headline['pdfLink']
            if not link:
                continue
            # link = response.urljoin(link)
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
                item = UyproItem()
                item['ch_url'] = ch_url
                item['tweet_url'] = link
                item['tweet_id'] = link
                lang = 'en'
                item['tweet_lang'] = lang
                item['taskid'] = self.taskid
                item['bid'] = self.bid
                tweet_title = headline['HeadlineText']
                item['tweet_title'] = tweet_title
                item['tweet_title_tslt'] = translate_text_googleapi(tweet_title)
                tweet_createtime = re.search(r'\((\d+)\)', headline['datetime']).group(1)[:10]
                item['tweet_createtime'] = parse_date(tweet_createtime)
                item['tweet_pdf_url'] = [link]
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item

        if max_year > min_year and if_new:
            max_year -= 1
            next_url = re.sub(r'year=\d+', f'year={max_year}', target_url)
            yield response.follow(
                url=next_url, callback=self.parse_fou, meta={
                    'ch_url': ch_url, 'target_url': target_url, 'max_year': max_year})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        lang = 'en'
        item['tweet_lang'] = lang
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
