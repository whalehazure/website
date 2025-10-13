import hashlib
import json
import logging
import re
import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import parse_date, start_spider, update_ch_urls
from .webmod import get_map


class TurkistantimesSpider(scrapy.Spider):
    name = "turkistantimes"
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
        self.proname = "turkistantimes"

    def start_requests(self):
        homepage = ''
        # homepage = 'https://turkistantimes.com/'
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://turkistantimes.com/ar/category-112.html'
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
                yield scrapy.Request(url=churl, callback=self.parse_sec,
                                     meta={'ch_url': churl, 'data1': '', 'data2': 20})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            # 'https://turkistantimes.com/ar/category-112.html',
            # 'https://turkistantimes.com/ar/category-101.html',
            # 'https://turkistantimes.com/ar/category-83.html',
            # 'https://turkistantimes.com/ar/category-82.html',
            # 'https://turkistantimes.com/ar/category-81.html',
            # 'https://turkistantimes.com/en/category-86.html',
            # 'https://turkistantimes.com/en/category-87.html',
            # 'https://turkistantimes.com/en/category-102.html',
            # 'https://turkistantimes.com/en/category-103.html',
            # 'https://turkistantimes.com/en/category-107.html',
            # 'https://turkistantimes.com/en/category-113.html',
            # 'https://turkistantimes.com/ug/category-96.html',
            # 'https://turkistantimes.com/ug/category-104.html',
            # 'https://turkistantimes.com/ug/category-98.html',
            # 'https://turkistantimes.com/ug/category-106.html',
            # 'https://turkistantimes.com/tr/category-114.html',
            # 'https://turkistantimes.com/tr/category-115.html',
            # 'https://turkistantimes.com/tr/category-116.html',
            # 'https://turkistantimes.com/tr/category-117.html',
            # 'https://turkistantimes.com/tr/category-118.html',
            'https://turkistantimes.com/tr/category-119.html'
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link, 'data1': '', 'data2': 20})

    def parse_sec(self, response):
        if_new = False
        data1 = response.meta['data1']
        data2 = response.meta['data2']
        ch_url = response.meta['ch_url']
        divs = response.xpath("//div[@class='home-item-list']")
        for div in divs:
            link = div.xpath(".//div[@class='home-item-title']/a/@href").get('')
            createtime = div.xpath("string(.//div[@class='post-date mt-2'])").get('').strip()
            createtime = re.sub(r'\u200E', '', createtime)
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'createtime': createtime,
                                                                         'link': link})
        next_url = 'https://turkistantimes.com/ajax.php'
        data1 = data1 if data1 else response.xpath("//script").re_first(r"data1\s*:\s*'(\d+)'", '').strip()
        formdata = {
            'fname': 'load_category',
            'data1': data1,
            'data2': str(data2)
        }
        if divs and if_new:
            data2 += 20
            yield scrapy.FormRequest(url=next_url, method='POST', formdata=formdata, callback=self.parse_sec,
                                     meta={'ch_url': ch_url, 'data1': data1, 'data2': data2})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        ch_url = response.meta['ch_url']
        item['ch_url'] = ch_url
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        lang = 'ar' if '/ar/' in ch_url else 'en' if '/en/' in ch_url else 'ug' if '/ug/' in ch_url else 'tr'
        item['tweet_lang'] = lang
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item, lang)
            if item:
                item['tweet_createtime'] = parse_date(response.meta['createtime'])
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
