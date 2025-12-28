import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls, translate_text_googleapi, translatetext_bing, translate_text_gemini, parse_date
from scrapy import Selector


class TopcongoliveSpider(scrapy.Spider):
    name = "topcongolive"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
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
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://www.topcongo.live/articles'
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
                yield scrapy.Request(url=churl, callback=self.parse_fir, meta={'ch_url': churl})
            else:
                # gettweet
                pass
                # yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.topcongo.live/articles',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_fir(self, response):
        ch_url = response.meta['ch_url']
        if ch_url == 'https://www.topcongo.live/articles' or ch_url == 'https://www.topcongo.live/articles/':
            link = 'https://admin.topcongo.live/api/blog?page=1'
            headers = {
                "token": "wZ12CTK4qCywaYTTJoTTyGMkkyHVeDO469Z023JFReEdbIY52HAmjqbH6cB4jhaNe4q02nZbEiA1biJK"
            }
            yield scrapy.Request(url=link, headers=headers, callback=self.parse_sec, meta={'ch_url': ch_url})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        posts = response.json().get('data', [])
        for post in posts:
            if not post:
                continue
            _id = post.get('slug')
            if not _id:
                continue
            link = f'https://www.topcongo.live/articles/{_id}'
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
                item = UyproItem()
                item['ch_url'] = ch_url
                item['tweet_url'] = link
                item['tweet_id'] = link
                item['taskid'] = self.taskid
                item['bid'] = self.bid
                item['tweet_content'] = ''
                item['tweet_content_tslt'] = ''
                article_title = post.get('title', '')
                if article_title:
                    item['tweet_title'] = article_title
                    item['tweet_title_tslt'] = translate_text_googleapi(article_title)
                    if not item['tweet_title_tslt']:
                        item['tweet_title_tslt'] = translatetext_bing(article_title).strip()
                    if not item['tweet_title_tslt']:
                        item['tweet_title_tslt'] = translate_text_gemini(article_title).strip()
                    html_content = post.get('content', '')
                    new_response = Selector(text=html_content)
                    article_content = new_response.xpath("string(.)").get('').strip()
                    if article_content:
                        item['tweet_content'] = article_content
                        item['tweet_content_tslt'] = translate_text_googleapi(article_content)
                        if not item['tweet_content_tslt']:
                            item['tweet_content_tslt'] = translatetext_bing(article_content).strip()
                        if not item['tweet_content_tslt']:
                            item['tweet_content_tslt'] = translate_text_gemini(article_content).strip()
                    lang = 'fr'
                    item['tweet_lang'] = lang
                    item['tweet_author'] = ''
                    item['tweet_video'] = ''
                    item['tweet_createtime'] = parse_date(post.get('date', ''), 'Africa/Kinshasa')
                    item['tweet_img_url'] = [post.get('cover', '').strip() or None]
                    item['tweet_table'] = ''
                    link_hash = hashlib.sha1(link.encode()).hexdigest()
                    if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                        update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    yield item
        next_page_url = response.json().get('metas', {}).get('next_page_url')
        if if_new and next_page_url:
            headers = {
                "token": "wZ12CTK4qCywaYTTJoTTyGMkkyHVeDO469Z023JFReEdbIY52HAmjqbH6cB4jhaNe4q02nZbEiA1biJK"
            }
            yield scrapy.Request(url=next_page_url, headers=headers, callback=self.parse_sec, meta={'ch_url': ch_url})
