import hashlib
import json
import logging
from urllib.parse import urlencode

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls, extract_segment_from_url
from .webmod import get_map


class ChinesealjazeeraSpider(scrapy.Spider):
    name = "chinesealjazeera"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 7,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/123.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "chinesealjazeera"

    def start_requests(self):
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://chinese.aljazeera.net/economy/'
            # inputdata = {}
            self.taskid = taskid
            self.bid = inputfilename.split('_')[3]
            self.crawler.stats.set_value('inputdata', inputdata)
            self.crawler.stats.set_value('inputfilename', inputfilename)
            self.crawler.stats.set_value('recent_files_append', recent_files_append)
            self.inc = False if dltype == 'full' else True
            if method == 'getchannel':
                yield scrapy.Request(url=churl, callback=self.parse, meta={'ch_url': churl})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='gc__content']/div[@class='gc__header-wrap']/h3[@class='gc__title']/a["
                               "@class='u-clickable-card__link']/@href").getall()
        for link in links:
            link = response.urljoin(link)
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
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
        base_url = "https://chinese.aljazeera.net/graphql"
        category = extract_segment_from_url(ch_url)
        offset = 14
        if category == 'opinion':
            query_params = {
                'wp-site': 'chinese',
                'operationName': 'ArchipelagoPostsQuery',
                'variables': json.dumps({
                    "offset": offset,
                    "postType": "opinion",
                    "quantity": 10
                }),
                'extensions': json.dumps({})
            }
        else:
            query_params = {
                'wp-site': 'chinese',
                'operationName': 'ArchipelagoAjeSectionPostsQuery',
                'variables': json.dumps({
                    "category": category,
                    "categoryType": "categories",
                    "postTypes": [
                        "blog", "episode", "opinion", "post", "video",
                        "external-article", "gallery", "podcast", "longform", "liveblog"
                    ],
                    "quantity": 10,
                    "offset": offset
                }),
                'extensions': json.dumps({})
            }
        next_url = f"{base_url}?{urlencode(query_params)}".replace('+', '')
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, headers={'wp-site': 'chinese'},
                                  meta={'ch_url': ch_url, 'offset': offset, 'category': category})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        offset = response.meta['offset']
        category = response.meta['category']
        links = response.json().get('data', {}).get('articles', [])
        if links:
            for link in links:
                link = link.get('link', '')
                link = response.urljoin(link)
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
                    yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
        base_url = "https://chinese.aljazeera.net/graphql"
        offset += 10
        if category == 'opinion':
            query_params = {
                'wp-site': 'chinese',
                'operationName': 'ArchipelagoPostsQuery',
                'variables': json.dumps({
                    "offset": offset,
                    "postType": "opinion",
                    "quantity": 10
                }),
                'extensions': json.dumps({})
            }
        else:
            query_params = {
                'wp-site': 'chinese',
                'operationName': 'ArchipelagoAjeSectionPostsQuery',
                'variables': json.dumps({
                    "category": category,
                    "categoryType": "categories",
                    "postTypes": [
                        "blog", "episode", "opinion", "post", "video",
                        "external-article", "gallery", "podcast", "longform", "liveblog"
                    ],
                    "quantity": 10,
                    "offset": offset
                }),
                'extensions': json.dumps({})
            }
        next_url = f"{base_url}?{urlencode(query_params)}".replace('+', '')
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, headers={'wp-site': 'chinese'},
                                  meta={'ch_url': ch_url, 'offset': offset, 'category': category})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        lang = 'zh'
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = lang
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                else:
                    if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                        update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
