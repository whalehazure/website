import hashlib
import json
import logging
import os
import re

import pandas as pd
import scrapy
from scrapy.selector import Selector
from scrapy.utils.python import to_bytes

from uyPro.items import UyproItem
from uyPro.settings import redis_conn, file_dir
from .utils import start_spider, replace_encrypted_emails, translatetext, parse_date, update_ch_urls


class AmnestyusaSpider(scrapy.Spider):
    name = "amnestyusa"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
        'CONCURRENT_REQUESTS_PER_IP': 16,
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "amnestyusa"

    def start_requests(self):
        homepage = ''
        # homepage = 'https://www.amnestyusa.org/news/'
        # link = 'https://www.amnestyusa.org/press-releases/israel-opt-deal-to-release-hostages-and-prisoners-must' \
        #        '-pave-way-for-further-releases-and-a-sustained-ceasefire/'
        # churl = 'https://www.amnestyusa.org/news/'
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
            'https://www.amnestyusa.org/news/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath(
            "//div[@class='wp-block-post-content']//div[@class='card-md h-full relative']/a/@href").getall()
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
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
        next_url = response.xpath("//div[contains(@class,'next')]/a[contains(@class,'next')]/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

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
        article_title = response.xpath(
            "string(//meta[@property='og:title']/@content)").get('').strip()
        if article_title:
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            html_content = replace_encrypted_emails(response.body)
            new_response = Selector(text=html_content)
            article_content = new_response.xpath(
                "string(//div[@class='content-wrapper']/article/div[contains(@class,'wp-block-post-content')])").get(
                '').strip()
            if article_content:
                article_content = re.sub(r'\n+', '\n', article_content)
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = translatetext(article_content)
            item['tweet_lang'] = 'en'
            item['tweet_author'] = ''
            item['tweet_video'] = ''
            item['tweet_createtime'] = parse_date(
                response.xpath("//script").re_first(r'"datePublished":\s*"([^"]+)"', '').strip())
            tweet_img_url = response.xpath("//meta[@property='og:image']/@content").getall()
            item['tweet_img_url'] = tweet_img_url if tweet_img_url else [response.urljoin(response.xpath(
                "//div[@class='p-site xl:container ts-bg-white']/figure[@class='relative']/img/@data-src").get(''))]
            item['tweet_table'] = ''
            if '<table' in response.xpath(
                    "//div[@class='content-wrapper']/article/div[contains(@class,'wp-block-post-content')]").get(''):
                html_content = response.xpath(
                    "//div[@class='content-wrapper']/article/div[contains(@class,'wp-block-post-content')]").get()
                decrypted_content = replace_encrypted_emails(html_content)
                tables = pd.read_html(decrypted_content)
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
                # self.redis_conn.sadd('amnestyusa_done_urls', link_hash)
            yield item
