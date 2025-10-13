import hashlib
import json
import logging
from urllib.parse import urlencode
from urllib.parse import urljoin

import scrapy
from jsonpath_ng.ext import parse

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class ScmpSpider(scrapy.Spider):
    name = "scmp"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "scmp"

    def start_requests(self):
        homepage = ''
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://www.scmp.com/news/china?module=oneline_menu_section_int&pgtype=live'
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
        chlinks = [
            'https://www.scmp.com/live?module=oneline_menu_section_int&pgtype=live',
            'https://www.scmp.com/news/china?module=oneline_menu_section_int&pgtype=live',
            'https://www.scmp.com/news/hong-kong?module=oneline_menu_section_int&pgtype=section',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        if 'https://www.scmp.com/live?' in ch_url:
            links = response.xpath(
                "//div[@id='__next']//div[@data-qa='LivePage-Container']/div/div[@data-qa='ContentItemLivePrimary-Headline']/a/@href").getall()
        else:
            links = response.xpath("//div[@data-qa='Component-Container' or @data-qa='Component-Primary' or @data-qa='Component-Content']/a/@href").getall()
        base_url = "https://www.scmp.com"
        for link in links:
            if ('/magazines/style/' in link) or ('/video/' in link):
                continue
            link = link.split('?')[0]
            link = urljoin(base_url, link)
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
        json_data = response.xpath('//script[@id="__NEXT_DATA__"]/text()').get()
        if json_data and if_new and ('https://www.scmp.com/live?' in ch_url):
            json_data = json.loads(json_data)
            end_cursor = parse('$.props.pageProps.payload.data.contents.pageInfo.endCursor').find(json_data)
            end_cursor = end_cursor[0].value if end_cursor else ''
            params = {
                "extensions": "{\"persistedQuery\":{\"sha256Hash\":\"f01973f68048d06d05bfb92eb0e8b602f795b111d12dd129059d6040a1f2e668\",\"version\":1}}",
                "operationName": "livePageLatestPaginationQuery",
                "variables": f"""{{"after": "{end_cursor}","applicationIds": [null, "2695b2c9-96ef-4fe4-96f8-ba20d0a020b3"],"count": 30,"excludeArticleTypeIds": ["c8774510-c0e0-4117-99a5-48c444acc219"],"excludeSectionIds": ["c53d30d7-9375-4516-869f-8e62e130b2bd", "2a786249-ee3e-4fda-9991-0d757340f9a7"],"scmpPlusPaywallTypeIds": ["716f570e-3083-4138-a080-47d3830fafe3"]}}"""
            }
            next_url = f"https://apigw.scmp.com/content-delivery/v2?{urlencode(params)}"
            headers = {
                "accept": "*/*",
                "apikey": "MyYvyg8M9RTaevVlcIRhN5yRIqqVssNY",
                "content-type": "application/json",
            }
            yield response.follow(url=next_url, headers=headers, callback=self.parse_trd, meta={'ch_url': ch_url})

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        expression = parse("$.data.contents.edges[*].node.urlAlias")
        links = [match.value for match in expression.find(response.json())]
        base_url = "https://www.scmp.com"
        for link in links:
            if ('/magazines/style/' in link) or ('/video/' in link):
                continue
            link = link.split('?')[0]
            link = urljoin(base_url, link)
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
        end_cursor = parse('$.data.contents.pageInfo.endCursor').find(response.json())
        end_cursor = end_cursor[0].value if end_cursor else ''
        if end_cursor and if_new:
            params = {
                "extensions": "{\"persistedQuery\":{\"sha256Hash\":\"f01973f68048d06d05bfb92eb0e8b602f795b111d12dd129059d6040a1f2e668\",\"version\":1}}",
                "operationName": "livePageLatestPaginationQuery",
                "variables": f"""{{"after": "{end_cursor}","applicationIds": [null, "2695b2c9-96ef-4fe4-96f8-ba20d0a020b3"],"count": 30,"excludeArticleTypeIds": ["c8774510-c0e0-4117-99a5-48c444acc219"],"excludeSectionIds": ["c53d30d7-9375-4516-869f-8e62e130b2bd", "2a786249-ee3e-4fda-9991-0d757340f9a7"],"scmpPlusPaywallTypeIds": ["716f570e-3083-4138-a080-47d3830fafe3"]}}"""
            }
            next_url = f"https://apigw.scmp.com/content-delivery/v2?{urlencode(params)}"
            headers = {
                "accept": "*/*",
                "apikey": "MyYvyg8M9RTaevVlcIRhN5yRIqqVssNY",
                "content-type": "application/json",
            }
            yield response.follow(url=next_url, headers=headers, callback=self.parse_trd, meta={'ch_url': ch_url})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        lang = 'en'
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
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
