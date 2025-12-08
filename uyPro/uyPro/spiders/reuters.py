import hashlib
import json
import logging
from urllib.parse import urlencode

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class ReutersSpider(scrapy.Spider):
    name = "reuters"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_MIDDLEWARES': {'uyPro.middlewares.DrissionPageMiddleware': 543, },
        'CONCURRENT_REQUESTS_PER_IP': 1,
        'DOWNLOAD_DELAY': 3,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 '
                      'Safari/537.36',
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
            # churl = 'https://www.reuters.com/world/china/'
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
                yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl})
            else:
                # gettweet
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.reuters.com/world/china/',
            'https://www.reuters.com/world/asia-pacific/',
            'https://www.reuters.com/world/japan/',
            'https://www.reuters.com/world/us/',
            'https://www.reuters.com/investigations/'
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        # print(response.text)
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath(
            "//ul/li/div/a[@data-testid='TitleLink']/@href|//div[@data-testid='common/single-section-block']//a["
            "@data-testid='TitleLink']/@href|//ul/li/div/div//a[@data-testid='Heading']/@href|//ul/li/div/div//h3["
            "@data-testid='Heading']/a/@href").getall()
        for link in links:
            if not link:
                continue
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
                # print(link)
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        if if_new:
            current_section = response.xpath("//script").re_first(r'"section_id":\s*"(.*?)"', '')
            d = response.xpath("//script[@id='preload-ads']/@data-deployment-id").get('')
            if 'investigations' in ch_url:
                offset = 23
                requestId = 2
                inner_payload = {
                    "collection_id": "BYAJX34ZEJEFHHII4OLDLH3HK4",
                    "offset": offset,
                    "requestId": requestId,
                    "size": "10",
                    "website": "reuters"
                }
                query_string = json.dumps(inner_payload, ensure_ascii=False)
                base_url = "https://www.reuters.com/pf/api/v3/content/fetch/articles-by-collection-alias-or-id-v1"
            else:
                offset = 20
                requestId = 1
                inner_payload = {
                    "arc-site": "reuters",
                    "fetch_type": "collection",
                    "offset": offset,
                    "requestId": requestId,
                    "section_id": current_section,
                    "size": "20",
                    "uri": current_section,
                    "website": "reuters"
                }
                query_string = json.dumps(inner_payload, ensure_ascii=False)
                base_url = "https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1"
            params = {
                "query": query_string,
                "d": d,
                "mxId": "00000000",
                "_website": "reuters"
            }
            query_params = urlencode(params)
            full_url = f"{base_url}?{query_params}"
            yield response.follow(url=full_url, callback=self.parse_trd,
                                  meta={'ch_url': ch_url, 'offset': offset, 'd': d, 'current_section': current_section,
                                        'requestId': requestId})

    def parse_trd(self, response):
        # print(response.text)
        if_new = False
        ch_url = response.meta['ch_url']
        offset = response.meta['offset']
        d = response.meta['d']
        current_section = response.meta['current_section']
        requestId = response.meta['requestId'] + 1
        itms = response.json().get('result', {}).get('articles', [])
        for itm in itms:
            link = itm.get('canonical_url', '')
            if not link:
                continue
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
                # print(link)
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        if if_new:
            if 'investigations' in ch_url:
                offset += 10
                inner_payload = {
                    "collection_id": "BYAJX34ZEJEFHHII4OLDLH3HK4",
                    "offset": offset,
                    "requestId": requestId,
                    "size": "10",
                    "website": "reuters"
                }
                query_string = json.dumps(inner_payload, ensure_ascii=False)
                base_url = "https://www.reuters.com/pf/api/v3/content/fetch/articles-by-collection-alias-or-id-v1"
            else:
                offset += 20
                inner_payload = {
                    "arc-site": "reuters",
                    "fetch_type": "collection",
                    "offset": offset,
                    "requestId": requestId,
                    "section_id": current_section,
                    "size": "20",
                    "uri": current_section,
                    "website": "reuters"
                }
                query_string = json.dumps(inner_payload, ensure_ascii=False)
                base_url = "https://www.reuters.com/pf/api/v3/content/fetch/articles-by-section-alias-or-id-v1"
            params = {
                "query": query_string,
                "d": d,
                "mxId": "00000000",
                "_website": "reuters"
            }
            query_params = urlencode(params)
            full_url = f"{base_url}?{query_params}"
            yield response.follow(url=full_url, callback=self.parse_trd,
                                  meta={'ch_url': ch_url, 'offset': offset, 'd': d, 'current_section': current_section,
                                        'requestId': requestId})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        lang = 'en'
        item['tweet_lang'] = lang
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
