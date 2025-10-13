import json
import logging
import os
import platform
import scrapy
import hashlib
import pandas as pd
from newspaper import Article

from uyPro.items import UyproItem
from .utils import replace_spaces, translatetext, parse_date, start_spider, replace_enter, update_ch_urls, \
    translatetext_bing, translate_text_siliconflow
from .webmod import get_map
from scrapy.utils.python import to_bytes
from uyPro.settings import file_dir, redis_conn
from scrapy_selenium import SeleniumRequest
from pathlib import Path


class UyghuraaSpider(scrapy.Spider):
    name = "uyghuraa"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_MIDDLEWARES': {'scrapy_selenium.SeleniumMiddleware': 800, },
        'AUTOTHROTTLE_ENABLED': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/117.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS_PER_IP': 16,
        'DOWNLOADER_CLIENT_TLS_CIPHERS': 'DEFAULT:!DH'
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "uyghuraa"

    def start_requests(self):
        # homepage = 'https://www.uyghuraa.org/'
        # link = 'https://www.uyghuraa.org/pressrelease/statement-on-the-26th-anniversary-of-the-ghulja-massacre'
        # churl = 'https://www.uyghuraa.org/pressrelease'
        homepage = ''
        maindomain = 'uyghuraa.org'
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
            elif maindomain in tweeturl:
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
            elif 'cardrates.com' in tweeturl:
                yield scrapy.Request(url=tweeturl, callback=self.article_sec, meta={'ch_url': churl, 'link': tweeturl},
                                     headers={'Host': 'www.cardrates.com'})
            elif 'axios.com' in tweeturl:
                yield SeleniumRequest(url=tweeturl, callback=self.article_sec, meta={'ch_url': churl, 'link': tweeturl})
            elif 'xinjiangpolicefiles.org' in tweeturl:
                file_path = Path(__file__).resolve().parent.parent / "xinjiangpolicefiles.org.html"
                url = f"file://{file_path.as_posix()}" if platform.system(
                ) != 'Windows' else f"file:///{file_path.as_posix()}"
                yield scrapy.Request(url, callback=self.article_xinjiangpolicefiles,
                                     meta={'ch_url': churl, 'link': tweeturl})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article_sec, meta={'ch_url': churl, 'link': tweeturl},
                                     dont_filter=True)
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.uyghuraa.org/pressrelease',
            'https://www.uyghuraa.org/reports',
            'https://www.uyghuraa.org/latestnews',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        ch_url = response.meta['ch_url']
        links = response.xpath("//article[@id='sections']/section//article//h1/a/@href|//div["
                               "@class='image-button-inner']/a/@href").getall()
        maindomain = 'uyghuraa.org'
        for link in links:
            link = response.urljoin(link)
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember('uyghuraa_done_urls', link_hash) and self.inc:
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
                    yield item
            elif maindomain in link:
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
            elif 'cardrates.com' in link:
                yield response.follow(link, callback=self.article_sec, meta={'ch_url': ch_url, 'link': link},
                                      headers={'Host': 'www.cardrates.com'})
            elif 'axios.com' in link:
                yield SeleniumRequest(url=link, callback=self.article_sec, meta={'ch_url': ch_url, 'link': link})
            elif 'ptvnews.ph' in link:
                yield SeleniumRequest(url=link, callback=self.article_sec, meta={'ch_url': ch_url, 'link': link})
            elif 'xinjiangpolicefiles.org' in link:
                file_path = Path(__file__).resolve().parent.parent / "xinjiangpolicefiles.org.html"
                url = f"file://{file_path.as_posix()}" if platform.system(
                ) != 'Windows' else f"file:///{file_path.as_posix()}"
                yield response.follow(url, callback=self.article_xinjiangpolicefiles,
                                      meta={'ch_url': ch_url, 'link': link})
            else:
                yield response.follow(link, callback=self.article_sec, meta={'ch_url': ch_url, 'link': link},
                                      dont_filter=True)

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
        item['tweet_lang'] = 'en'
        article_title = response.xpath("string(//div[@class='blog-item-title']/h1)").get('').strip()
        if article_title:
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            if not item['tweet_title_tslt']:
                item['tweet_title_tslt'] = translatetext_bing(article_title).strip()
            if not item['tweet_title_tslt']:
                item['tweet_title_tslt'] = translate_text_siliconflow(article_title).strip()
            article_content = response.xpath(
                "string(//div[@class='blog-item-content e-content'])").get('').strip()
            if article_content:
                article_content = replace_spaces(article_content)
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = translatetext(article_content)
                if not item['tweet_content_tslt']:
                    item['tweet_content_tslt'] = translatetext_bing(article_content).strip()
                if not item['tweet_content_tslt']:
                    item['tweet_content_tslt'] = translate_text_siliconflow(article_content).strip()
            item['tweet_author'] = response.xpath("string(//meta[@itemprop='author']/@content)").get('').strip()
            tweet_createtime = response.xpath("string(//meta[@itemprop='datePublished']/@content)").get('').strip()
            item['tweet_createtime'] = parse_date(tweet_createtime)
            item['tweet_img_url'] = response.xpath("//meta[@property='og:image']/@content").getall()
            item['tweet_video'] = ''
            item['tweet_table'] = ''
            if '<table' in response.xpath("//div[@class='blog-item-content e-content']").get(''):
                html_content = response.xpath("//div[@class='blog-item-content e-content']").get()
                tables = pd.read_html(html_content)
                tweet_table = []
                for i, df in enumerate(tables):
                    table_name = os.path.join(f'{file_dir}/csv', f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                    directory = os.path.dirname(table_name)
                    if not os.path.exists(directory): os.makedirs(directory)
                    df.to_csv(table_name, index=False, encoding='UTF-8')
                    tweet_table.append(os.path.basename(table_name))
                if tweet_table: item['tweet_table'] = tweet_table
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                # self.redis_conn.sadd('uyghuraa_done_urls', link_hash)
            yield item

    def article_sec(self, response):
        try:
            if hasattr(self, 'driver'):
                self.driver.quit()
        except:
            logging.info('driver quit error')
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = 'en'
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    # self.redis_conn.sadd('uyghuraa_done_urls', link_hash)
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
                if not item['tweet_title_tslt']:
                    item['tweet_title_tslt'] = translatetext_bing(article_title).strip()
                if not item['tweet_title_tslt']:
                    item['tweet_title_tslt'] = translate_text_siliconflow(article_title).strip()
                article_content = replace_enter(article.text)
                if article_content:
                    item['tweet_content'] = replace_enter(article.text)
                    item['tweet_content_tslt'] = translatetext(article_content)
                    if not item['tweet_content_tslt']:
                        item['tweet_content_tslt'] = translatetext_bing(article_content).strip()
                    if not item['tweet_content_tslt']:
                        item['tweet_content_tslt'] = translate_text_siliconflow(article_content).strip()
                item['tweet_author'] = article.meta_data.get('author', '')
                item['tweet_video'] = ''
                item['tweet_createtime'] = parse_date(str(article.publish_date))
                item['tweet_img_url'] = response.xpath("string(//meta[@property='og:image']/@content)").getall()
                item['tweet_table'] = ''
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    # self.redis_conn.sadd(f'uyghuraa_done_urls', link_hash)
                yield item

    def article_xinjiangpolicefiles(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        tweet_url = 'https://www.xinjiangpolicefiles.org/'
        item['tweet_url'] = tweet_url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = 'en'
        tweet_func = get_map(tweet_url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    # self.redis_conn.sadd('uyghuraa_done_urls', link_hash)
                yield item
