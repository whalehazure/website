import hashlib
import json
import logging
import os

import pandas as pd
import scrapy
from scrapy.selector import Selector
from scrapy.utils.python import to_bytes

from uyPro.items import UyproItem
from uyPro.settings import file_dir, redis_conn
from .utils import replace_spaces, translatetext, parse_date, replace_encrypted_emails, start_spider, update_ch_urls, \
    detect_language, translatetext_bing, translate_text_siliconflow


class UyghurcongressSpider(scrapy.Spider):
    name = "uyghurcongress"
    allowed_domains = ["uyghurcongress.org"]
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_MIDDLEWARES': {'uyPro.middlewares.DrissionPageMiddleware': 543, },
        'AUTOTHROTTLE_ENABLED': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS_PER_IP': 1,
        'CLOSESPIDER_ITEMCOUNT': 50,
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "uyghurcongress"
        self.domain_ = "uyghurcongress.org"

    def start_requests(self):
        # homepage = 'https://www.uyghurcongress.org/en'
        # link = 'https://www.uyghurcongress.org/en/introducing-the-world-uyghur-congress/fifth-general-assembly-of' \
        #        '-the-world-uyghur-congress/wuc-1st-general-assembly/ '
        # churl = 'https://ar.uyghurcongress.org/category/%D8%A7%D9%84%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1/'
        homepage = ''
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://www.uyghurcongress.org/en/category/press-release/'
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
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.uyghurcongress.org/en/category/press-release/',
            'https://tr.uyghurcongress.org/category/4-0/',
            'https://ar.uyghurcongress.org/category/%D8%A7%D9%84%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1/',
            'https://www.uyghurcongress.org/en/category/news/wuc-in-the-news/',
            'https://www.uyghurcongress.org/en/category/news/wuc-events/',
            'https://www.uyghurcongress.org/en/category/reports/world-uyghur-congress/',
        ]
        links = [
            'https://www.uyghurcongress.org/en/steering-committee/',
            'https://www.uyghurcongress.org/en/introducing-the-world-uyghur-congress/fifth-general-assembly-of-the'
            '-world-uyghur-congress/wuc-1st-general-assembly/',
            'https://www.uyghurcongress.org/en/affiliate-organizations/',
            'https://ar.uyghurcongress.org/%d8%af-%d8%a6%db%87-%d9%82-%d8%ba%d8%a7-%d8%a6%db%95%d8%b2%d8%a7-%d8%aa%db'
            '%95%d8%b4%d9%83%d9%89%d9%84%d8%a7%d8%aa%d9%84%d8%a7%d8%b1/'
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})
        for link in links:
            yield response.follow(link, callback=self.article, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='content-inner']/h2[@class='entry-title']/a/@href").getall()
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember('uyghurcongress_done_urls', link_hash) and self.inc:
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
        next_url = response.xpath("//div[@class='pager']/div[@class='paginations']/a[@class='next_page']/@href").get()
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
            "string(//div[@id='wp-content']/article/h1[@class='entry-title'])").get('').strip()
        if article_title:
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            if not item['tweet_title_tslt']:
                item['tweet_title_tslt'] = translatetext_bing(article_title).strip()
            if not item['tweet_title_tslt']:
                item['tweet_title_tslt'] = translate_text_siliconflow(article_title).strip()
            html_content = replace_encrypted_emails(response.body)
            new_response = Selector(text=html_content)
            article_content = new_response.xpath(
                "string(//div[@id='wp-content']/article/div[@class='entry-content']/div["
                "@class='content-inner'])").get('').strip()
            if article_content:
                article_content = replace_spaces(article_content)
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = translatetext(article_content)
                if not item['tweet_content_tslt']:
                    item['tweet_content_tslt'] = translatetext_bing(article_content).strip()
                if not item['tweet_content_tslt']:
                    item['tweet_content_tslt'] = translate_text_siliconflow(article_content).strip()
            item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                article_title)
            item['tweet_author'] = ''
            item['tweet_video'] = ''
            tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get(
                '').strip()
            item['tweet_createtime'] = parse_date(tweet_createtime) if tweet_createtime else parse_date(response.xpath(
                "string(//div[@id='wp-content']/article//time[@class='entry-date'])").get())
            item['tweet_img_url'] = response.xpath(
                "//div[@id='wp-content']/article/div[@class='post-thumbnail']/img/@src").getall()
            item['tweet_table'] = ''
            if '<table' in response.xpath("//div[@id='wp-content']/article").get(''):
                html_content = response.xpath("//div[@id='wp-content']/article").get()
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
                # self.redis_conn.sadd('uyghurcongress_done_urls', link_hash)
            yield item
        else:
            article_title = response.xpath(
                "string(//div[@class='content-page-inner']/div/h1[@class='title'])").get('').strip()
            if article_title:
                item['tweet_title'] = article_title
                item['tweet_title_tslt'] = translatetext(article_title)
                if not item['tweet_title_tslt']:
                    item['tweet_title_tslt'] = translatetext_bing(article_title).strip()
                if not item['tweet_title_tslt']:
                    item['tweet_title_tslt'] = translate_text_siliconflow(article_title).strip()
            html_content = replace_encrypted_emails(response.body)
            new_response = Selector(text=html_content)
            list1 = new_response.xpath("//div[@class='content-page-inner']/div/p/text()").getall()
            str1 = new_response.xpath("string(//div[@class='content-page-inner']/div/h1[2])").get('').strip()
            list1.append(str1)
            article_content = ' '.join(list1)
            if article_content:
                article_content = replace_spaces(article_content)
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = translatetext(article_content)
                if not item['tweet_content_tslt']:
                    item['tweet_content_tslt'] = translatetext_bing(article_content).strip()
                if not item['tweet_content_tslt']:
                    item['tweet_content_tslt'] = translate_text_siliconflow(article_content).strip()
            item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                article_title)
            item['tweet_author'] = ''
            item['tweet_video'] = ''
            tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get(
                '').strip()
            item['tweet_createtime'] = parse_date(tweet_createtime) if tweet_createtime else parse_date(response.xpath(
                "string(//div[@id='wp-content']/article//time[@class='entry-date'])").get())
            item['tweet_img_url'] = response.xpath(
                "//div[@id='wp-content']/article/div[@class='post-thumbnail']/img/@src").getall()
            item['tweet_table'] = ''
            if '<table' in response.xpath("//div[@class='content-page-inner']").get(''):
                tables = pd.read_html(response.xpath("//div[@class='content-page-inner']").get())
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
                # self.redis_conn.sadd('uyghurcongress_done_urls', link_hash)
            yield item
