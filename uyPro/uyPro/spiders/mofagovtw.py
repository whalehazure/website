import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class MofagovtwSpider(scrapy.Spider):
    name = "mofagovtw"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 7,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/122.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "mofagovtw"

    def start_requests(self):
        homepage = ''
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = ('https://www.mofa.gov.tw/News.aspx?n=95&sms=73'
            #          '&_Query=189712c4-c2ec-44a5-8dd5-f81f335795bd&page=1&PageSize=200')
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
                url = churl[:-1] if churl.endswith('/') else churl
                yield scrapy.Request(url=url, callback=self.parse_post, meta={'ch_url': churl})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.mofa.gov.tw/News.aspx?n=95&sms=73&_Query=c9f136e3-61ae-41b0-bfb6-6af9f57a6b3a&page=1'
            '&PageSize=200',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_post(self, response):
        ch_url = response.meta['ch_url']
        url = f'{response.url}&Create=1'
        VIEWSTATE = response.xpath("//input[@id='__VIEWSTATE']/@value").get('')
        jNewsModule_field_0 = response.xpath("//input[@id='jNewsModule_field_0']/@value").get('')
        jNewsModule_field_SDate_1 = response.xpath("//input[@id='jNewsModule_field_SDate_1']/@value").get('')
        jNewsModule_field_EDate_1 = response.xpath("//input[@id='jNewsModule_field_EDate_1']/@value").get('')
        jNewsModule_BtnSend = response.xpath("//input[@id='jNewsModule_BtnSend']/@value").get('')
        VIEWSTATEGENERATOR = response.xpath("//input[@id='__VIEWSTATEGENERATOR']/@value").get('')
        formdata = {
            "__VIEWSTATE": VIEWSTATE,
            "jNewsModule_field_2": "",
            "jNewsModule_field_0": jNewsModule_field_0,
            "jNewsModule_field_SDate_1": jNewsModule_field_SDate_1,
            "jNewsModule_field_EDate_1": jNewsModule_field_EDate_1,
            "jNewsModule_BtnSend": jNewsModule_BtnSend,
            "__VIEWSTATEGENERATOR": VIEWSTATEGENERATOR,
            "__VIEWSTATEENCRYPTED": ""
        }
        yield scrapy.FormRequest(url=url, method='post', formdata=formdata, callback=self.parse_post2,
                                 meta={'ch_url': ch_url})

    def parse_post2(self, response):
        ch_url = response.meta['ch_url']
        link = f'{response.url}&page=1&PageSize=200'
        yield response.follow(link, callback=self.parse_sec, meta={'ch_url': ch_url})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='in']/table/tbody/tr/td/span/a/@href").getall()
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
            elif 'www.mofa.gov.tw' not in link:
                logging.info(f'{link} : 111')
            else:
                if_new = True
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
        next_url = response.xpath(
            "//div[@class='area-customize pagination']/div[@class='in']/div[@class='ct']/div[@class='in']/ul["
            "@class='page']/li[@class='is-active']/following-sibling::li[1]/span/a/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

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
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
        else:
            logging.info(f'{link} : no function')

