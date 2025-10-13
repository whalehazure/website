import json
import logging
import os
import scrapy
import hashlib
import pandas as pd
from newspaper import Article

from uyPro.items import UyproItem
from .utils import replace_spaces, translatetext, parse_date, start_spider, replace_enter, update_ch_urls, \
    detect_language, translatetext_bing, translate_text_gemini, translate_text_siliconflow
from scrapy.utils.python import to_bytes
from .webmod import get_map
from uyPro.settings import file_dir, redis_conn
from scrapy_selenium import SeleniumRequest


class CampaignforuyghursSpider(scrapy.Spider):
    name = "campaignforuyghurs"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_MIDDLEWARES': {'scrapy_selenium.SeleniumMiddleware': 800, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/130.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS_PER_IP': 16,
        'DOWNLOADER_CLIENT_TLS_CIPHERS': 'DEFAULT:!DH',
        'DEFAULT_REQUEST_HEADERS': {
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept": "*/*",
            "accept-language": "*",
            "priority": "u=0, i",
            "sec-fetch-dest": "document",
            "Connection": "keep-alive"
        },
        # 'LOG_ENABLED': True,
        'DOWNLOAD_TIMEOUT': 13,
        'RETRY_TIMES': 1
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "campaignforuyghurs"

    def start_requests(self):
        # homepage = 'https://campaignforuyghurs.org/'
        # link = 'https://campaignforuyghurs.org/about-us/'
        # churl = 'https://campaignforuyghurs.org/ar/%d8%aa%d8%b5%d8%b1%d9%8a%d8%ad%d8%a7%d8%aa-%d8%b5%d8%ad%d9%81%d9' \
        #         '%8a%d9%87/ '
        homepage = ''
        maindomain = 'campaignforuyghurs.org'
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
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article_sec, meta={'ch_url': churl, 'link': tweeturl},
                                     dont_filter=True)
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://campaignforuyghurs.org/press-releases/',
            'https://campaignforuyghurs.org/tr/basin-yayinlari/',
            'https://campaignforuyghurs.org/ar/%d8%aa%d8%b5%d8%b1%d9%8a%d8%ad%d8%a7%d8%aa-%d8%b5%d8%ad%d9%81%d9%8a%d9'
            '%87/',
            'https://campaignforuyghurs.org/organization-activities/',
            'https://campaignforuyghurs.org/about-us/',
            'https://campaignforuyghurs.org/cfu-in-the-news/',
        ]
        links = [
            'https://campaignforuyghurs.org/about-us/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link}, dont_filter=True)
        for link in links:
            yield response.follow(link, callback=self.article, meta={'ch_url': link}, dont_filter=True)

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='elementor-post__text']/h3/a/@href|"
                               "//div[@class='elementor-image-box-content']/h3/a/@href").getall()
        maindomain = 'campaignforuyghurs.org'
        if 'campaignforuyghurs.org/about-us' in response.url:
            yield response.follow(response.url, callback=self.article, meta={'ch_url': ch_url, 'link': response.url},
                                  dont_filter=True)
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember('campaignforuyghurs_done_urls', link_hash) and self.inc:
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
            elif maindomain in link:
                if_new = True
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
            elif 'cardrates.com' in link:
                if_new = True
                yield response.follow(link, callback=self.article_sec, meta={'ch_url': ch_url, 'link': link},
                                      headers={'Host': 'www.cardrates.com'})
            elif 'axios.com' in link:
                if_new = True
                yield SeleniumRequest(url=link, callback=self.article_sec, meta={'ch_url': ch_url, 'link': link})
            else:
                if_new = True
                yield response.follow(link, callback=self.article_sec, meta={'ch_url': ch_url, 'link': link})
        next_url = response.xpath("string(//div[@class='e-load-more-anchor']/@data-next-page)").get()
        if next_url and if_new and 'campaignforuyghurs.org/organization-activities/' in next_url:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})
        elif next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url}, dont_filter=True)

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
        article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').split(' - ')[0].strip()
        if response.url == 'https://campaignforuyghurs.org/about-us/':
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            article_content = response.xpath(
                "string(//main[@id='content']/div[@class='page-content'])").get('').strip()
            if article_content:
                article_content = replace_spaces(article_content)
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = translatetext(article_content)
                if article_content and not item['tweet_content_tslt']:
                    item['tweet_content_tslt'] = translatetext_bing(article_content)
            item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(article_title)
            item['tweet_author'] = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
            tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get(
                '').strip()
            item['tweet_createtime'] = parse_date(tweet_createtime)
            item['tweet_video'] = ''
            item['tweet_img_url'] = response.xpath("//meta[@property='og:image']/@content|//div["
                                                   "@class='elementor-image']/img/@src").getall()
            item['tweet_table'] = ''
            if '<table' in response.xpath("//main[@id='content']/div[@class='page-content']").get(''):
                html_content = response.xpath("//main[@id='content']/div[@class='page-content']").get()
                tables = pd.read_html(html_content)
                tweet_table = []
                for i, df in enumerate(tables):
                    table_name = os.path.join(f'{file_dir}/csv', f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                    df.to_csv(table_name, index=False, encoding='UTF-8')
                    tweet_table.append(os.path.basename(table_name))
                if tweet_table: item['tweet_table'] = tweet_table
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                # self.redis_conn.sadd('campaignforuyghurs_done_urls', link_hash)
            yield item

        elif article_title:
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            article_content = response.xpath("string(//div[contains(@class,"
                                             "'elementor-widget-theme-post-content')]/div["
                                             "@class='elementor-widget-container'])").get('').strip()
            if article_content:
                article_content = replace_spaces(article_content)
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = translatetext(article_content)
                if article_content and not item['tweet_content_tslt']:
                    item['tweet_content_tslt'] = translatetext_bing(article_content)
            item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(article_title)
            item['tweet_author'] = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
            tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get(
                '').strip()
            item['tweet_createtime'] = parse_date(tweet_createtime)
            item['tweet_video'] = ''
            item['tweet_img_url'] = response.xpath("//meta[@property='og:image']/@content").getall()
            item['tweet_table'] = ''
            if '<table' in response.xpath("//div[contains(@class,'elementor-widget-theme-post-content')]/div["
                                          "@class='elementor-widget-container']").get(''):
                html_content = response.xpath("//div[contains(@class,'elementor-widget-theme-post-content')]/div["
                                              "@class='elementor-widget-container']").get()
                tables = pd.read_html(html_content)
                tweet_table = []
                for i, df in enumerate(tables):
                    table_name = os.path.join(f'{file_dir}/csv', f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                    df.to_csv(table_name, index=False, encoding='UTF-8')
                    tweet_table.append(os.path.basename(table_name))
                if tweet_table: item['tweet_table'] = tweet_table
            link_hash = hashlib.sha1(response.url.encode()).hexdigest()
            if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                # self.redis_conn.sadd('campaignforuyghurs_done_urls', link_hash)
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
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                article_content = item.get('tweet_content', '')
                article_title = item.get('tweet_title', '')
                item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                    article_title)
                link_hash = hashlib.sha1(response.url.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    # self.redis_conn.sadd('campaignforuyghurs_done_urls', link_hash)
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
                    if not item['tweet_title_tslt']:
                        item['tweet_title_tslt'] = translate_text_gemini(article_title).strip()
                    if not item['tweet_title_tslt']:
                        item['tweet_title_tslt'] = translate_text_siliconflow(article_title).strip()
                    if article_content and not item['tweet_content_tslt']:
                        item['tweet_content_tslt'] = translatetext_bing(article_content)
                        if not item['tweet_content_tslt']:
                            item['tweet_content_tslt'] = translate_text_gemini(article_content).strip()
                        if not item['tweet_content_tslt']:
                            item['tweet_content_tslt'] = translate_text_siliconflow(article_content).strip()
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
                    # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
                yield item
