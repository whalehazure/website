import json
import logging
import scrapy
import hashlib
import os
import pandas as pd
from uyPro.items import UyproItem
from .utils import replace_spaces, translatetext, start_spider, update_ch_urls, detect_language
from scrapy.utils.python import to_bytes
from uyPro.settings import file_dir, redis_conn


class EthrwSpider(scrapy.Spider):
    name = "ethrw"
    allowed_domains = ["ethrw.org"]
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
        'CONCURRENT_REQUESTS_PER_IP': 16,
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "ethrw"

    def start_requests(self):
        # homepage = 'https://www.ethrw.org/'
        # link = 'https://www.ethrw.org/5-temmuz-urumci-katliami-raporu-2-baski/'
        # churl = 'https://www.ethrw.org/category/haberler/'
        homepage = ''
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://www.ethrw.org/category/raporlar/'
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
        links = [
            'https://www.ethrw.org/category/haberler/',
            'https://www.ethrw.org/category/makale-ve-analizler/',
            'https://www.ethrw.org/category/etkinlikler/',
            'https://www.ethrw.org/category/aciklamalar/',
            'https://www.ethrw.org/category/raporlar/',
        ]
        for link in links:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//h5[@class='elementor-post__title']/a/@href").getall()
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
        next_url = response.xpath("//ul[@class='page-numbers']/li/a[@class='next page-numbers']/@href").get()
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
        article_title = response.xpath("string(//meta[@property='og:title']/@content)").get()
        if article_title:
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            article_content = response.xpath(
                "string(//div[contains(@class,'elementor-widget-theme-post-content')]/div["
                "@class='elementor-widget-container'])").get().replace('\xa0', ' ')
            if article_content:
                article_content = replace_spaces(article_content)
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = translatetext(article_content)
            item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                article_title)
            item['tweet_video'] = ''
            item['tweet_author'] = ''
            item['tweet_createtime'] = response.xpath(
                "string(//meta[@itemprop='datePublished']/@content)").get('').strip()
            item['tweet_img_url'] = response.xpath("//meta[@property='og:image']/@content|//div["
                                                   "@class='elementor-widget-container']/figure/img/@src").getall()
            tweet_pdf_urls = response.xpath("//div[@class='elementor-button-wrapper']/a["
                                            "@class='elementor-button elementor-button-link "
                                            "elementor-size-sm']/@href").getall()
            item['tweet_pdf_url'] = [tweet_pdf_url for tweet_pdf_url in tweet_pdf_urls if
                                     tweet_pdf_url.endswith('.pdf')]
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
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
            yield item
