import hashlib
import json
import logging
from urllib.parse import urljoin

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class FtvnewscomtwSpider(scrapy.Spider):
    name = "ftvnewscomtw"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_MIDDLEWARES': {'uyPro.middlewares.CloudScraperMiddleware': 543, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Android 7.1.2; Mobile; rv:53.0) Gecko/53.0 Firefox/53.0',
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
            # churl = 'https://www.ftvnews.com.tw/tag/%E6%94%BF%E6%B2%BB/'
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
            'https://www.ftvnews.com.tw/tag/%E6%94%BF%E6%B2%BB/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//ul[@class='row']/li/div/div[@class='content']/a/@href").getall()
        for link in links:
            if link:
                link = urljoin('https://www.ftvnews.com.tw/', link)
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
        next_url = response.xpath("//i[contains(@class, 'fa-solid fa-angle-right')]/ancestor::a["
                                  "@class='page-link']/@href").get()
        if next_url and if_new:
            next_url = urljoin('https://www.ftvnews.com.tw/', next_url)
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        lang = 'zh'
        item['tweet_url'] = link
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = lang
        tweet_func = get_map(link)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
