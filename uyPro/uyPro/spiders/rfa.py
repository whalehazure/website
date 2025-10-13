import hashlib
import json
import logging

import scrapy
from newspaper import Article

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, translatetext, parse_date, replace_enter, update_ch_urls, detect_language
from .webmod import get_map


class RfaSpider(scrapy.Spider):
    name = "rfa"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_CLIENT_TLS_CIPHERS': 'DEFAULT:!DH',
        # 'DOWNLOADER_MIDDLEWARES': {
        #     "uyPro.middlewares.UyproDownloaderMiddleware": None,
        # },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'DEFAULT_REQUEST_HEADERS': {
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept": "*/*",
            "accept-language": "*",
            "priority": "u=0, i",
            "sec-fetch-dest": "document",
            "Connection": "keep-alive"
        },
        # 'DOWNLOAD_HANDLERS': {
        #     "https": "scrapy.core.downloader.handlers.http2.H2DownloadHandler",
        # },
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/130.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True,
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "rfa"

    def start_requests(self):
        homepage = ''
        # homepage = 'https://www.rfa.org/english/news/uyghur'
        # link = 'https://www.rfa.org/english/news/uyghur/detainee-01112024105257.html'
        # churl = 'hhttps://www.rfa.org/english/news/uyghur'
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://www.rfa.org/mandarin'
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
            'https://www.rfa.org/english/news/uyghur/',
            'https://www.rfa.org/uyghur/',
            'https://www.rfa.org/mandarin/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[contains(@class,'mosaic-grid-cell') and not(contains(@class,"
                               "'newRFAbelow'))]//span[@class]/parent::a/@href|//article/div[contains(@class,"
                               "'c-stack')]/h2[@class='c-heading']/a[@class='c-link']/@href").getall()
        for link in links:
            link = response.urljoin(link)
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
        next_url = response.xpath("//div[@class='gotoarchive']/a/@href|//div/a[div[@style]]/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_trd, meta={'ch_url': ch_url})

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@id='storycontent']/div[@class='sectionteaser archive']/h2/a/@href|"
                               "//div/div[contains(@class,'c-stack')]/h2[@class='c-heading']/a[@class='c-link']/@href"
                               ).getall()
        for link in links:
            link = response.urljoin(link)
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
        next_url = response.xpath("//nav[@class='pagination']/ul/li[@class='next']/a/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_trd, meta={'ch_url': ch_url})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        tweet_func = get_map(response.url)
        if tweet_func and ('/mandarin' in response.meta['ch_url']):
            item = tweet_func(response, item, False)
            if item:
                item['tweet_lang'] = 'zh'
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
        elif tweet_func:
            item = tweet_func(response, item)
            if item:
                article_content = item.get('tweet_content', '')
                article_title = item.get('tweet_title', '')
                item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                    article_title)
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
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
                item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                    article_title)
                item['tweet_author'] = article.meta_data.get('author', '')
                item['tweet_video'] = ''
                item['tweet_createtime'] = parse_date(str(article.publish_date))
                item['tweet_img_url'] = response.xpath("string(//meta[@property='og:image']/@content)").getall()
                item['tweet_table'] = ''
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
