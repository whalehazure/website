import binascii
import hashlib
import json
import logging
import os

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


def generate_uuid_v4(buffer=None, offset=0):
    # 1. 获取 16 个随机字节 (对应 JS 中的 rng())
    # 使用 os.urandom 保证密码学安全，并转为 bytearray 以便修改
    rng = bytearray(os.urandom(16))

    # 2. 设置版本号 Version 4
    # JS: l[6] = 15 & l[6] | 64
    # 15 是 0x0f, 64 是 0x40
    rng[6] = (rng[6] & 0x0f) | 0x40

    # 3. 设置变体 Variant (RFC 4122)
    # JS: l[8] = 63 & l[8] | 128
    # 63 是 0x3f, 128 是 0x80
    rng[8] = (rng[8] & 0x3f) | 0x80

    # 4. 如果传入了 buffer (类似于数组引用)，则写入 buffer
    if buffer is not None:
        for i in range(16):
            # 确保 buffer 足够大且可变
            buffer[offset + i] = rng[i]
        return buffer

    # 5. 否则返回标准 UUID 字符串格式
    # 格式: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    hex_str = binascii.hexlify(rng).decode('utf-8')
    return f"{hex_str[0:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:]}"


class CnnSpider(scrapy.Spider):
    name = "cnn"
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
            # churl = 'https://www.cnn.com/search?q=china&from=0&size=10&page=1&sort=newest&types=all&section='
            # inputdata = {}
            self.taskid = taskid
            self.bid = inputfilename.split('_')[3]
            self.crawler.stats.set_value('inputdata', inputdata)
            self.crawler.stats.set_value('inputfilename', inputfilename)
            self.crawler.stats.set_value('recent_files_append', recent_files_append)
            self.inc = False if dltype == 'full' else True
            if homepage:
                yield scrapy.Request(url=homepage, callback=self.parse)
            elif method == 'getchannel' and 'search?q=china&from=0' in churl:
                page = 1
                url = (f'https://search.prod.di.api.cnn.io/content?q=china&size=10&from=0&page=1&sort=newest'
                       f'&request_id=stellar-search-{generate_uuid_v4()}&site=cnn')
                yield scrapy.Request(url=url, callback=self.parse_trd, meta={'ch_url': churl, 'page': page})
            elif method == 'getchannel':
                yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.cnn.com/politics',
            'https://www.cnn.com/world/asia',
            'https://www.cnn.com/search?q=china&from=0&size=10&page=1&sort=newest&types=all&section=',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@data-component-name='scope']//ul/li/a/@href|//div["
                               "@class='search__results-list']//ul/li/a/@href").getall()
        for link in links:
            if not link or any(excluded in link for excluded in ['/gallery/', '/interactive/', '/cnn.it/']):
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

        next_url = response.xpath("//section[@id='content']//li[@class='page-item']/a[@aria-label='Next']/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        results = response.json().get('result', [])
        for result in results:
            link = result.get('url', '')
            if not link or any(excluded in link for excluded in ['/gallery/', '/interactive/', '/cnn.it/']):
                continue
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

        meta_data = response.json().get('meta', {})
        if meta_data.get('end', 9) != meta_data.get('of', 59) and if_new:
            page = response.meta['page'] + 1
            next_url = (f'https://search.prod.di.api.cnn.io/content?q=china&size=10&from={(page - 1) * 10}&page={page}'
                        f'&sort=newest&request_id=stellar-search-{generate_uuid_v4()}&site=cnn')
            yield response.follow(url=next_url, callback=self.parse_trd, meta={'ch_url': ch_url, 'page': page})

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
