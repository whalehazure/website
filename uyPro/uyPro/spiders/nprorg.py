import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class NprorgSpider(scrapy.Spider):
    name = "nprorg"
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
            # churl = 'https://www.npr.org/search/?query=china&page=1&sortType=byDate'
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
            elif method == 'getchannel' and 'www.npr.org/search' in churl:
                yield scrapy.Request(url=churl, callback=self.parse_trd, meta={'ch_url': churl})
            elif method == 'getchannel':
                yield scrapy.Request(url=churl, callback=self.parse_sec, meta={
                    'ch_url': churl, 'storyId': '', 'initialStories': 0})
            else:
                # gettweet
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.npr.org/sections/politics/',
            'https://www.npr.org/sections/world/',
            'https://www.npr.org/sections/national/',
            'https://www.npr.org/search/?query=china&page=1&sortType=byDate',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        storyId = response.meta['storyId']
        initialStories = response.meta['initialStories']
        links = response.xpath("//div[@class='item-info']/h2[@class='title']/a/@href").getall()
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

        if not storyId:
            initialStories = int(response.xpath("//script").re_first(r'"initialStories":\s*(\d+)')) + 1
            storyId = response.xpath("//script").re_first(r'"storyId":\s*"(\d+)"')
        if initialStories and if_new:
            next_url = f'https://www.npr.org/get/{storyId}/render/partial/next?start={initialStories}&count=24'
            yield response.follow(url=next_url, callback=self.parse_sec, meta={
                'ch_url': ch_url, 'initialStories': initialStories + 24, 'storyId': storyId})

    def parse_trd(self, response):
        # Extract the data-from-layout JSON from the page
        layout_data = response.xpath("//div[@id='search-container']/@data-from-layout").get()
        if not layout_data:
            self.logger.error("Failed to extract layout data.")
            return

        # Parse the JSON data
        layout_json = json.loads(layout_data)
        app_id = layout_json.get("nprOrgCdsAppId")
        api_key = layout_json.get("nprOrgCdsApiKey")
        index_name = layout_json.get("nprOrgCdsIndexName")

        # Construct the POST URL
        post_url = (
            f"https://{app_id.lower()}-3.algolianet.com/1/indexes/*/queries"
            f"?x-algolia-agent=Algolia%20for%20JavaScript%20(4.24.0)%3B%20Browser%20(lite)%3B%20JS%20Helper%20("
            f"3.14.0)%3B%20react%20(19.1.0)%3B%20react-instantsearch%20(6.40.4)"
            f"&x-algolia-api-key={api_key}"
            f"&x-algolia-application-id={app_id}"
        )

        # Define the POST payload
        page = 0
        payload = {
            "requests": [
                {
                    "indexName": index_name,
                    "params": (
                        f"analytics=true&analyticsTags=%5B%22npr.org%2Fsearch%22%5D&clickAnalytics=true&"
                        f"facets=%5B%22hasAudio%22%2C%22lastModifiedDate%22%2C%22showNames%22%5D&"
                        f"filters=type%3Astory%20OR%20type%3Aepisode%20OR%20type%3Aseries&"
                        f"highlightPostTag=%3C%2Fais-highlight-0000000000%3E&"
                        f"highlightPreTag=%3Cais-highlight-0000000000%3E&maxValuesPerFacet=10&"
                        f"page={page}&query=china&tagFilters="
                    ),
                }
            ]
        }
        headers = {
            'referer': response.url,
        }

        # Send the POST request
        yield scrapy.Request(
            url=post_url,
            method="POST",
            body=json.dumps(payload),
            callback=self.parse_results,
            meta={"app_id": app_id, "api_key": api_key, "index_name": index_name,
                  "ch_url": response.meta['ch_url'], 'page': page + 1}
        )

    def parse_results(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        app_id = response.meta['app_id']
        api_key = response.meta['api_key']
        index_name = response.meta['index_name']
        page = response.meta['page']
        hits = response.json().get('results', [])[0].get('hits', [])
        for hit in hits:
            link = hit.get('url')
            if not link:
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

        if if_new:
            post_url = (
                f"https://{app_id.lower()}-3.algolianet.com/1/indexes/*/queries"
                f"?x-algolia-agent=Algolia%20for%20JavaScript%20(4.24.0)%3B%20Browser%20(lite)%3B%20JS%20Helper%20("
                f"3.14.0)%3B%20react%20(19.1.0)%3B%20react-instantsearch%20(6.40.4)"
                f"&x-algolia-api-key={api_key}"
                f"&x-algolia-application-id={app_id}"
            )

            # Define the POST payload
            payload = {
                "requests": [
                    {
                        "indexName": index_name,
                        "params": (
                            f"analytics=true&analyticsTags=%5B%22npr.org%2Fsearch%22%5D&clickAnalytics=true&"
                            f"facets=%5B%22hasAudio%22%2C%22lastModifiedDate%22%2C%22showNames%22%5D&"
                            f"filters=type%3Astory%20OR%20type%3Aepisode%20OR%20type%3Aseries&"
                            f"highlightPostTag=%3C%2Fais-highlight-0000000000%3E&"
                            f"highlightPreTag=%3Cais-highlight-0000000000%3E&maxValuesPerFacet=10&"
                            f"page={page}&query=china&tagFilters="
                        ),
                    }
                ]
            }

            # Send the POST request
            yield scrapy.Request(
                url=post_url,
                method="POST",
                body=json.dumps(payload),
                callback=self.parse_results,
                meta={"app_id": app_id, "api_key": api_key, "index_name": index_name,
                      "ch_url": response.meta['ch_url'], 'page': page+1}
            )

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
