import hashlib
import json
import logging
import re

import scrapy
from scrapy.http import HtmlResponse

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls, sort_and_replace_p_tags
from .webmod import get_map


class ZaobaoSpider(scrapy.Spider):
    name = "zaobao"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        # 'AUTOTHROTTLE_DEBUG': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "zaobao"

    def start_requests(self):
        homepage = ''
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://www.zaobao.com/realtime/world'
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
            'https://www.zaobao.com/realtime/china',
            'https://www.zaobao.com/realtime/world',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath(
            "//a[@class='article-type-link']/@href|//div[@class='row reset-row-margin']/a/@href|//div[contains("
            "@class,'content-header')]/a[contains(@class,'cursor-pointer touch-auto')]/@href").getall()
        for link in links:
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
        if 'zaobao.com.sg' in response.url:
            pageNo = 1
            next_url = f'https://www.zaobao.com.sg/_plat/api/v2/page-content/realtime/world?page={str(pageNo)}'
            if next_url and if_new:
                yield response.follow(url=next_url, callback=self.parse_fou, meta={'ch_url': ch_url, 'pageNo': pageNo + 1})
        else:
            script_content = response.xpath('//script[contains(text(), "sitemapId")]/text()').get()
            if script_content:
                match = re.search(r'sitemapId\s*=\s*"(\d+)"', script_content)
                if match:
                    sitemap_id = match.group(1)
                    pageNo = 3
                    next_url = f'https://www.zaobao.com/more/sitemap/{sitemap_id}?pageNo={str(pageNo)}&pageSize=9'
                    if next_url and if_new:
                        yield response.follow(url=next_url, callback=self.parse_trd,
                                              meta={'ch_url': ch_url, 'sitemap_id': sitemap_id, 'pageNo': pageNo + 1})

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        sitemap_id = response.meta['sitemap_id']
        pageNo = response.meta['pageNo']
        try:
            datas = response.json().get('result', {}).get('data', {})
        except Exception as e:
            logging.info(f'{e}: {response.url}')
            datas = []
        for data in datas:
            link = data.get('url', '')
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        next_url = f'https://www.zaobao.com/more/sitemap/{sitemap_id}?pageNo={str(pageNo)}&pageSize=9'
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_trd, headers={'Referer': ch_url},
                                  meta={'ch_url': ch_url, 'sitemap_id': sitemap_id, 'pageNo': pageNo + 1})

    def parse_fou(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        pageNo = response.meta['pageNo']
        try:
            datas = response.json().get('response', {}).get('articles', {})
        except Exception as e:
            logging.info(f'{e}: {response.url}')
            datas = []
        for data in datas:
            link = data.get('href', '')
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        next_url = f'https://www.zaobao.com.sg/_plat/api/v2/page-content/realtime/world?page={str(pageNo)}'
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_fou, meta={'ch_url': ch_url, 'pageNo': pageNo + 1})

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
            if 'zaobao.com/' in response.url:
                response = HtmlResponse(
                    url=response.url,
                    status=response.status,
                    headers=response.headers,
                    body=sort_and_replace_p_tags(response.text).encode('utf-8'),
                    encoding='utf-8'
                )
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
