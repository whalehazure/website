import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class JpostSpider(scrapy.Spider):
    name = "jpost"
    redis_conn = redis_conn
    custom_settings = {
        'DOWNLOADER_CLIENT_TLS_CIPHERS': 'DEFAULT:!DH',
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/137.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True,
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
            # churl = 'https://www.jpost.com/Diaspora'
            # inputdata = {}
            # tweeturl = 'https://www.epochtimes.com/gb/24/10/7/n14345827.htm'
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
            'https://www.jpost.com/israel-news',
            'https://www.jpost.com/Middle-East',
            'https://www.jpost.com/international',
            'https://www.jpost.com/opinion',
            'https://www.jpost.com/Diaspora',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath(
            "//section[@class='main-page']//section/section[contains(@class,'category-page-main')]//h3/a[contains("
            "@class,'content-link')]/@href").getall()
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
        script_content = response.xpath('//script')
        lastArtPublishDate = script_content.re(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
        lastArtPublishDate = lastArtPublishDate[-1] if lastArtPublishDate else ''
        catID = script_content.re_first(r'var catID = (\d+);')
        if if_new and lastArtPublishDate:
            headers = {"next-action": "b52277adb1ca823b1c31d6067058ee81bcc016b2"}
            data = f'[{catID},"$undefined","{lastArtPublishDate}"]'
            yield scrapy.FormRequest(response.url, method='post', body=data, callback=self.parse_trd, headers=headers,
                                     meta={'ch_url': ch_url, 'catID': catID})

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        catID = response.meta['catID']
        json_match = response.xpath('*').re_first(r'1:({.*})')
        items = []
        links = []
        if json_match:
            try:
                data = json.loads(json_match)
                items = data.get('data', {}).get('dataItems', {}).get('itemsLst', [])
                links = [item['friendlyUrl'] for item in items if item.get('friendlyUrl')]
            except json.JSONDecodeError as e:
                logging.info(f"JSON解析错误: {e}")
                logging.info(f"错误片段: {json_match[max(0, e.pos - 50):e.pos + 50]}")
        else:
            logging.info("未找到JSON数据")

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
        lastArtPublishDate = items[-1].get('publishDate') if items else ''
        if if_new and lastArtPublishDate:
            headers = {"next-action": "b52277adb1ca823b1c31d6067058ee81bcc016b2"}
            data = f'[{catID},"$undefined","{lastArtPublishDate}"]'
            yield scrapy.FormRequest(response.url, method='post', body=data, callback=self.parse_trd, headers=headers,
                                     meta={'ch_url': ch_url, 'catID': catID})

    def article(self, response):
        ch_url = response.meta['ch_url']
        if 'live-updates-' in response.url:
            if_new = False
            links = response.xpath("//section[@id]/section[contains(@class,'post-item-body')]//a/@href").getall()
            for link in links:
                if not link or 'jpost.com/tags/' in link or ('jpost.com' not in link):
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
                    # print(link)
                    if_new = True
                    yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})
            next_url = response.xpath("//section[@class='pagination']/a[@class='notCurrentPage']/@href").get()
            if next_url and if_new:
                yield response.follow(url=next_url, callback=self.article, meta={'ch_url': ch_url})

        else:
            item = UyproItem()
            link = response.meta['link']
            item['ch_url'] = ch_url
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
