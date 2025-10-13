import json
import logging
import os
import scrapy
import hashlib
import pandas as pd
from uyPro.items import UyproItem
from .utils import replace_spaces, translatetext, parse_date, extract_date, start_spider, update_ch_urls, \
    detect_language
from scrapy.utils.python import to_bytes
from uyPro.settings import file_dir, redis_conn


class UhrpSpider(scrapy.Spider):
    name = "uhrp"
    allowed_domains = ["uhrp.org"]
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
        self.proname = "uhrp"

    def start_requests(self):
        # homepage = 'https://uhrp.org/'
        # link = 'https://uhrp.org/board-of-directors/'
        # churl = 'https://uhrp.org/statements/'
        homepage = ''
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
            'https://uhrp.org/statements/',
            'https://uhrp.org/events/',
            'https://uhrp.org/research/',
        ]
        links = [
            'https://uhrp.org/staff/',
            'https://uhrp.org/board-of-directors/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})
        for link in links:
            yield response.follow(link, callback=self.article, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath(
            "//div[contains(@class,'fl-post-grid')]/div[@class='fl-post-column']/div//h3/a/@href").getall()
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember('uhrp_done_urls', link_hash) and self.inc:
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
        next_url = response.xpath("//a[@class='next page-numbers']/@href").get()
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
        article_title = response.xpath("string(//*[self::h1 or self::h2]/span[contains(@class,'-heading-text')])").get(
            '').strip()
        if article_title:
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = translatetext(article_title)
            article_content = ' '.join(response.xpath("//div[@class='fl-rich-text' and not(ancestor::*["
                                                      "@data-node='5f6e42fa983f2'])]/descendant-or-self::*[not("
                                                      "self::style) and not(self::script)]/text()[normalize-space("
                                                      ")]|//div[contains(@class,'fl-post-content')]/div["
                                                      "@class='fl-module-content "
                                                      "fl-node-content']/descendant-or-self::*[not(self::style) and "
                                                      "not(self::script)]/text()[normalize-space()]|//div["
                                                      "@class='uabb-infobox-content' and ancestor::*["
                                                      "@data-node='5fac36f86ca79' or "
                                                      "@data-node='3iz4em70gvno']]/descendant-or-self::*[not( "
                                                      "self::style) and not(self::script)]/text()[normalize-space("
                                                      ")]").getall()).strip()
            if article_content:
                article_content = replace_spaces(article_content)
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = translatetext(article_content)
            item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                article_title)
            item['tweet_author'] = ''
            tweet_createtime = response.xpath("string(//div[@id='fl-main-content'])").get()
            item['tweet_video'] = ''
            item['tweet_createtime'] = parse_date(extract_date(tweet_createtime))
            item['tweet_img_url'] = response.xpath("//div[contains(@class,'fl-photo-content "
                                                   "fl-photo-img-')]/img/@src|//div[@id='fl-main-content']//figure/img["
                                                   "@height>'100']/@src|//div[@id='fl-main-content']//div["
                                                   "@class='uabb-image-content']/img[@height>'100']/@src").getall()
            item['tweet_table'] = ''
            if '<table' in response.xpath("//div[@class='fl-col-content fl-node-content']/div[contains(@class,"
                                          "'fl-post-content')]/div[@class='fl-module-content fl-node-content']|//div["
                                          "@class='fl-rich-text' and not(ancestor::*["
                                          "@data-node='5f6e42fa983f2'])]").get(''):
                html_content = response.xpath("//div[@class='fl-col-content fl-node-content']/div[contains(@class,"
                                              "'fl-post-content')]/div[@class='fl-module-content "
                                              "fl-node-content']|//div[@class='fl-rich-text' and not(ancestor::*["
                                              "@data-node='5f6e42fa983f2'])]").get()
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
                # self.redis_conn.sadd('uhrp_done_urls', link_hash)
            yield item
