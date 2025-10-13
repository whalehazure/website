import hashlib
import json
import logging

import scrapy
from newspaper import Article

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, translatetext, parse_date, replace_enter, update_ch_urls
from .webmod import get_map


class HabernidaSpider(scrapy.Spider):
    name = "habernida"
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
        self.proname = "habernida"

    def start_requests(self):
        homepage = ''
        # homepage = 'https://habernida.com/category/turk-dunyasi/'
        # link = 'https://habernida.com/isgalci-rusyanin-hapsettigi-fail-alsynova-yardim-icin-kullanilan-hesap-bloke' \
        #        '-edildi/ '
        # churl = 'https://habernida.com/category/turk-dunyasi/'
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
            elif method == 'getchannel':
                yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://habernida.com/category/turk-dunyasi/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//li/div[@class='li-con']/a/@href").getall()
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
        if if_new:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            page = 2
            data = {
                "page": str(page),
                "category": "3",
                "select": "kategori_loadmore",
                "action": "esenhaber"
            }
            url = 'https://habernida.com/wp-admin/admin-ajax.php'
            yield scrapy.FormRequest(url, method='post', formdata=data, callback=self.parse_trd, headers=headers,
                                     meta={'ch_url': ch_url, 'page': page + 1})

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        page = response.meta['page']
        links = list(set(filter(None, response.xpath('//a/@href').getall())))
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
        if if_new:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            data = {
                "page": str(page),
                "category": "3",
                "select": "kategori_loadmore",
                "action": "esenhaber"
            }
            url = 'https://habernida.com/wp-admin/admin-ajax.php'
            yield scrapy.FormRequest(url, method='post', formdata=data, callback=self.parse_trd, headers=headers,
                                     meta={'ch_url': ch_url, 'page': page + 1})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = 'tr'
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
                yield item
        else:
            article = Article('')
            article.download(input_html=response.text)
            article.parse()
            item['tweet_content'] = ''
            item['tweet_content_tslt'] = ''
            article_title = article.title
            if article_title:
                item['tweet_title'] = article_title
                item['tweet_title_tslt'] = translatetext(article_title)
                article_content = replace_enter(article.text)
                if article_content:
                    item['tweet_content'] = article_content
                    item['tweet_content_tslt'] = translatetext(article_content)
                item['tweet_author'] = article.meta_data.get('author', '')
                item['tweet_video'] = ''
                item['tweet_createtime'] = parse_date(str(article.publish_date))
                item['tweet_img_url'] = response.xpath("string(//meta[@property='og:image']/@content)").getall()
                item['tweet_table'] = ''
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
                yield item
