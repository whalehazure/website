import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class PtvcompkSpider(scrapy.Spider):
    name = "ptvcompk"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_MIDDLEWARES': {'uyPro.middlewares.DrissionPageMiddleware': 543, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
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
            # churl = 'https://www.ptv.com.pk/ptvNews/ur/%D9%82%D9%88%D9%85%DB%8C'
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
                # 旧URL到新URL的映射
                old_urls = [
                    'https://www.ptv.com.pk/ptvNews/ur/%D9%82%D9%88%D9%85%DB%8C',
                    'https://www.ptv.com.pk/ptvNews/ur/%D8%A8%DB%8C%D9%86%20%D8%A7%D9%84%D8%A7%D9%82%D9%88%D8%A7%D9'
                    '%85%DB%8C',
                    'https://www.ptv.com.pk/ptvNews/ur/%D8%A7%DB%81%D9%85%20%D8%AE%D8%A8%D8%B1%DB%8C%DA%BA',
                    'https://www.ptv.com.pk/ptvNews/ur/%D9%B9%D8%A7%D9%BE%20%D8%B3%D9%B9%D9%88%D8%B1%DB%8C'
                ]
                new_urls = [
                    'https://ptv.com.pk/ptvnews/urdunewscategory/%D9%BE%D8%A7%DA%A9%D8%B3%D8%AA%D8%A7%D9%86',
                    'https://ptv.com.pk/ptvnews/urdunewscategory/%D8%AF%D9%86%DB%8C%D8%A7',
                    'https://ptv.com.pk/ptvnews/urdunewscategory/%D8%A7%DB%81%D9%85%20%D8%AE%D8%A8%D8%B1%DB%8C%DA%BA',
                    'https://ptv.com.pk/ptvnews/urdunewscategory/%D9%B9%D8%A7%D9%BE%20%D8%B3%D9%B9%D9%88%D8%B1%DB%8C'
                ]

                churl = churl.strip('/')
                new_churl = churl
                if churl in old_urls:
                    index = old_urls.index(churl)
                    new_churl = new_urls[index]
                    logging.info(f'URL已更新: {churl} -> {new_churl}')

                yield scrapy.Request(url=new_churl, callback=self.parse_sec, meta={'ch_url': new_churl})
            else:
                # gettweet
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.ptv.com.pk/ptvNews/ur/%D9%82%D9%88%D9%85%DB%8C',
            'https://www.ptv.com.pk/ptvNews/ur/%D8%A8%DB%8C%D9%86%20%D8%A7%D9%84%D8%A7%D9%82%D9%88%D8%A7%D9%85%DB%8C',
            'https://www.ptv.com.pk/ptvNews/ur/%D8%A7%DB%81%D9%85%20%D8%AE%D8%A8%D8%B1%DB%8C%DA%BA',
            'https://www.ptv.com.pk/ptvNews/ur/%D9%B9%D8%A7%D9%BE%20%D8%B3%D9%B9%D9%88%D8%B1%DB%8C',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='post-content']/h3/a/@href").getall()
        for link in links:
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        next_url = response.xpath("//ul[contains(@class,'pagination')]/li/a[@rel='next']/@href").get()
        if next_url and if_new:
            next_url = next_url.replace('http://', 'https://')
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        lang = 'ur'
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
