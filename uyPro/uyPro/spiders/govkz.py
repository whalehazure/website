import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls, generate_uuid, hash_with_bcrypt
from .webmod import get_map


class GovkzSpider(scrapy.Spider):
    name = "govkz"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
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
            # churl = 'https://www.gov.kz/memleket/entities/knb/press/news/1?lang=kk'
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
                yield scrapy.Request(url=churl, callback=self.parse_first, meta={'ch_url': churl})
            # else:
            #     # gettweet
            #     yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.gov.kz/memleket/entities/knb/press/news/1?lang=kk',
            'https://www.gov.kz/memleket/entities/knb/documents/1?lang=kk',
            'https://www.gov.kz/memleket/entities/shekaraknb/press/news/1?lang=kk',
            'https://www.gov.kz/memleket/entities/antiterrosticheskiy-centr/press/news/1?lang=kk',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_first(self, response):
        ch_url = response.meta['ch_url']
        base_url = 'https://www.gov.kz/api/v1/public/content-manager/'
        project_map = {
            'entities/knb/press/news': 'news?sort-by=created_date:DESC&projects=eq:knb&size=10&page=1',
            'entities/knb/documents': 'documents?sort-by=created_date:DESC&projects=eq:knb&size=10&page=1',
            'entities/shekaraknb/press/news': 'news?sort-by=created_date:DESC&projects=eq:shekaraknb&size=10&page=1',
            'entities/antiterrosticheskiy-centr/press/news': 'news?sort-by=created_date:DESC&projects=eq'
                                                             ':antiterrosticheskiy-centr&size=10&page=1'
        }
        link = next((base_url + project_map[key] for key in project_map if key in ch_url), '')
        token = generate_uuid()
        _hash = hash_with_bcrypt(token)
        headers = {
            "accept-language": "kk",
            "token": token,
            "hash": _hash,
        }
        yield response.follow(link, callback=self.parse_sec, headers=headers, meta={'ch_url': ch_url})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        _dates = response.json()
        for _date in _dates:
            if not _date:
                continue
            alink = ''
            if adilet := _date.get('adilet', ''):
                link = f"https://www.gov.kz/memleket/entities/knb/documents/details/adilet/{adilet}"
                alink = f"https://www.gov.kz/api/v1/public/legalacts/kaz/docs/{adilet}"
            else:
                _id = _date.get('id', '')
                link = f"{ch_url.rsplit('/', 1)[0]}/details/{_id}?lang=kk"
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
            elif alink:
                if_new = True
                headers = {
                    'accept-language': 'kk',
                    'accept': 'application/json'
                }
                yield response.follow(alink, callback=self.article, headers=headers,
                                      meta={'ch_url': ch_url, 'link': link, '_date': _date})
            else:
                if_new = True
                item = UyproItem()
                item['ch_url'] = response.meta['ch_url']
                item['tweet_url'] = link
                item['tweet_id'] = link
                lang = 'kk'
                item['tweet_lang'] = lang
                item['taskid'] = self.taskid
                item['bid'] = self.bid
                tweet_func = get_map(response.url)
                if tweet_func:
                    item = tweet_func(_date, item)
                    if item:
                        link_hash = hashlib.sha1(link.encode()).hexdigest()
                        if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                            update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                        yield item

        next_url = response.url.split('page=')[0] + "page=" + str(int(response.url.split('page=')[1]) + 1)
        if next_url and if_new:
            token = generate_uuid()
            _hash = hash_with_bcrypt(token)
            headers = {
                "accept-language": "kk",
                "token": token,
                "hash": _hash,
            }
            yield response.follow(url=next_url, callback=self.parse_sec, headers=headers, meta={'ch_url': ch_url})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        _date = response.meta['_date']
        _json = response.json()
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        lang = 'kk'
        item['tweet_lang'] = lang
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(_date, item, _json)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
