import hashlib
import json
import logging

import scrapy
from scrapy.selector import Selector

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, translatetext, parse_date, update_ch_urls


class MuhsinlarSpider(scrapy.Spider):
    name = "muhsinlar"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        # 'AUTOTHROTTLE_DEBUG': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "muhsinlar"

    def start_requests(self):
        homepage = ''
        # homepage = 'https://www.muhsinlar.net/'
        # link = 'https://www.muhsinlar.net/kundilik-hewer-325/'
        # churl = 'https://www.muhsinlar.net/'
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            self.taskid = taskid
            self.bid = inputfilename.split('_')[3]
            self.crawler.stats.set_value('inputdata', inputdata)
            self.crawler.stats.set_value('inputfilename', inputfilename)
            self.crawler.stats.set_value('recent_files_append', recent_files_append)
            self.inc = False if dltype == 'full' else True
            if homepage:
                yield scrapy.Request(url=homepage, callback=self.parse)
            elif method == 'getchannel' and (churl == 'https://www.muhsinlar.net/' or churl == 'https://www.muhsinlar'
                                                                                               '.net'):
                yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl})
            elif method == 'getchannel':
                yield scrapy.Request(url=churl, callback=self.parse_ch_sec, meta={'ch_url': churl})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article_ch, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.muhsinlar.net/',
            'https://www.muhsinlar.net/category/dewet/',
            'https://www.muhsinlar.net/category/kitab/',
            'https://www.muhsinlar.net/category/awazlik/',
            'https://www.muhsinlar.net/category/heptilik_hewer/',
            'https://www.muhsinlar.net/category/video/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//ul[@class='news-gallery-items']/li/a/@href").getall()
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember(f'{self.proname}_new_done_urls', link_hash) and self.inc:
            #     logging.info(f'{link}: repetition')
            #     pass
            if (self.redis_conn.sismember(f'{self.proname}_new_done_urls', link_hash) or self.redis_conn.hexists(
                    f'{self.proname}_hash_done_urls', link_hash)) and self.inc:
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
        if if_new:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            page = 2
            data = f"action=tie_blocks_load_more&block%5Bicon%5D=fab+fa-buffer&block%5Border%5D=latest&block" \
                   f"%5Basc_or_desc%5D=DESC&block%5Bnumber%5D=12&block%5Bpagi%5D=load-more&block%5Bexcerpt%5D=true&block" \
                   f"%5Bmore%5D=true&block%5Bpost_meta%5D=true&block%5Bread_more%5D=true&block%5Bfilters%5D=true&block" \
                   f"%5Banimate_auto%5D=true&block%5Bbreaking_effect%5D=reveal&block%5Bsub_style%5D=row&block%5Bis_full" \
                   f"%5D=true&block%5Bajax_class%5D=news-gallery-items&block%5Bstyle%5D=grid&block%5Btitle_length%5D" \
                   f"=&block%5Bexcerpt_length%5D=&block%5Bmedia_overlay%5D=&block%5Bread_more_text%5D=&page={page}&width" \
                   f"=full "
            url = 'https://www.muhsinlar.net/wp-admin/admin-ajax.php'
            yield scrapy.FormRequest(url, method='post', body=data, callback=self.parse_trd, headers=headers,
                                     meta={'ch_url': ch_url, 'page': page + 1})

    def parse_trd(self, response):
        if_new = False
        json1 = json.loads(response.json())
        html_str = json1.get('code', '')
        selector = Selector(text=html_str)
        ch_url = response.meta['ch_url']
        page = response.meta['page']
        links = list(set(filter(None, selector.xpath('//a/@href').getall())))
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember(f'{self.proname}_new_done_urls', link_hash) and self.inc:
            #     logging.info(f'{link}: repetition')
            #     pass
            if (self.redis_conn.sismember(f'{self.proname}_new_done_urls', link_hash) or self.redis_conn.hexists(
                    f'{self.proname}_hash_done_urls', link_hash)) and self.inc:
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
        if if_new and not json1.get('hide_next'):
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            data = f"action=tie_blocks_load_more&block%5Bicon%5D=fab+fa-buffer&block%5Border%5D=latest&block" \
                   f"%5Basc_or_desc%5D=DESC&block%5Bnumber%5D=12&block%5Bpagi%5D=load-more&block%5Bexcerpt%5D=true&block" \
                   f"%5Bmore%5D=true&block%5Bpost_meta%5D=true&block%5Bread_more%5D=true&block%5Bfilters%5D=true&block" \
                   f"%5Banimate_auto%5D=true&block%5Bbreaking_effect%5D=reveal&block%5Bsub_style%5D=row&block%5Bis_full" \
                   f"%5D=true&block%5Bajax_class%5D=news-gallery-items&block%5Bstyle%5D=grid&block%5Btitle_length%5D" \
                   f"=&block%5Bexcerpt_length%5D=&block%5Bmedia_overlay%5D=&block%5Bread_more_text%5D=&page={page}&width" \
                   f"=full "
            url = 'https://www.muhsinlar.net/wp-admin/admin-ajax.php'
            yield scrapy.FormRequest(url, method='post', body=data, callback=self.parse_trd, headers=headers,
                                     meta={'ch_url': ch_url, 'page': page + 1})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_content'] = ''
        item['tweet_content_tslt'] = ''
        item['tweet_lang'] = 'ug'
        article_title = response.xpath(
            "string(//div[@class='entry-header']/h1[@class='post-title entry-title'])").get('').strip()
        article_title = article_title if article_title else response.xpath(
            "string(//meta[@property='og:title']/@content)").get('').strip()
        if article_title:
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            item['tweet_author'] = ''
            item['tweet_video'] = ''
            item['tweet_createtime'] = parse_date(
                response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip())
            item['tweet_img_url'] = response.xpath("//meta[@property='og:image']/@content").getall()
            item['tweet_table'] = ''
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                # self.redis_conn.sadd(f'{self.proname}_new_done_urls', link_hash)
            yield item

    def parse_ch_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//ul[@id='posts-container']/li/a/@href").getall()
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember(f'{self.proname}_done_urls', link_hash) and self.inc:
            #     logging.info(f'{link}: repetition')
            #     pass
            if (self.redis_conn.sismember(f'{self.proname}_done_urls', link_hash) or self.redis_conn.hexists(
                    f'{self.proname}_hash_done_urls', link_hash)) and self.inc:
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
                yield response.follow(link, callback=self.article_ch, meta={'ch_url': ch_url, 'link': link})
        if if_new:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            page = 2
            query = response.xpath("//div[@class='pages-nav']/a/@data-query").get('')
            dsettings = response.xpath("//ul[@id='posts-container']/@data-settings").get('')
            dmax = response.xpath("//div[@class='pages-nav']/a/@data-max").get('')
            data = {
                "action": "tie_archives_load_more",
                "query": query,
                "max": dmax,
                "page": str(page),
                "latest_post": "10",
                "layout": "large-above",
                "settings": dsettings
            }
            url = 'https://www.muhsinlar.net/wp-admin/admin-ajax.php'
            yield scrapy.FormRequest(url, method='post', formdata=data, callback=self.parse_ch_trd, headers=headers,
                                     meta={'ch_url': ch_url, 'page': page + 1, 'query': query, 'dsettings': dsettings,
                                           'dmax': dmax})

    def parse_ch_trd(self, response):
        if_new = False
        json1 = json.loads(response.json())
        html_str = json1.get('code', '')
        latest_post = json1.get('latest_post', '')
        selector = Selector(text=html_str)
        ch_url = response.meta['ch_url']
        query = response.meta['query']
        dsettings = response.meta['dsettings']
        dmax = response.meta['dmax']
        page = response.meta['page']
        links = list(set(filter(None, selector.xpath('//a/@href').getall())))
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember(f'{self.proname}_done_urls', link_hash) and self.inc:
            #     logging.info(f'{link}: repetition')
            #     pass
            if (self.redis_conn.sismember(f'{self.proname}_done_urls', link_hash) or self.redis_conn.hexists(
                    f'{self.proname}_hash_done_urls', link_hash)) and self.inc:
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
                yield response.follow(link, callback=self.article_ch, meta={'ch_url': ch_url, 'link': link})
        if if_new and not json1.get('hide_next'):
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            data = {
                "action": "tie_archives_load_more",
                "query": query,
                "max": dmax,
                "page": str(page),
                "latest_post": str(latest_post),
                "layout": "large-above",
                "settings": dsettings
            }
            url = 'https://www.muhsinlar.net/wp-admin/admin-ajax.php'
            yield scrapy.FormRequest(url, method='post', formdata=data, callback=self.parse_ch_trd, headers=headers,
                                     meta={'ch_url': ch_url, 'page': page + 1, 'query': query, 'dsettings': dsettings,
                                           'dmax': dmax})

    def article_ch(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_content'] = ''
        item['tweet_content_tslt'] = ''
        item['tweet_lang'] = 'ug'
        article_title = response.xpath(
            "string(//div[@class='entry-header']/h1[@class='post-title entry-title'])").get('').strip()
        article_title = article_title if article_title else response.xpath(
            "string(//meta[@property='og:title']/@content)").get('').strip()
        if article_title:
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            item['tweet_author'] = ''
            item['tweet_video'] = ''
            item['tweet_createtime'] = parse_date(
                response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip())
            item['tweet_img_url'] = response.xpath("//meta[@property='og:image']/@content").getall()
            item['tweet_table'] = ''
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
            yield item
