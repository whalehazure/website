import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class QikanminghuiorgSpider(scrapy.Spider):
    name = "qikanminghuiorg"
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
            # churl = 'https://qikan.minghui.org/display.aspx?category_id=8'
            # inputdata = {}
            # tweeturl = 'https://ug.uyghurstudy.org/beryusselda_xelqara_uyghur_munbiri_muhakime_yighini_otkuzuldi/'
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
            'https://qikan.minghui.org/display.aspx?category_id=8'
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("///div[@class='qkinnercontent']/div/ul/li/a/@href").getall()
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
        page_number = response.xpath(
            "//div[@class='paging_arrow_right']/img[@class='arrow_right_active']/@onclick"
        ).re_first(r'GoToPage\((\d+)\)')
        if if_new and page_number:
            next_url = response.url.split('&page=')[0] + f'&page={page_number}'
            yield response.follow(next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        lang = 'zh'
        item['tweet_lang'] = lang
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                tweet_pdf_urls = response.xpath("///div[@class='qikan']//span[@id='lblOnline']/a/@href").getall()
                tweet_pdf_urls = [response.urljoin(url) for url in tweet_pdf_urls if 'pdf' in url]
                item['tweet_pdf_url'] = tweet_pdf_urls
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
