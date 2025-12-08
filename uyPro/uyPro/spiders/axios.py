import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class AxiosSpider(scrapy.Spider):
    name = "axios"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_MIDDLEWARES': {'uyPro.middlewares.DrissionPageMiddleware': 543, },
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
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'inc', '', '1_1_1_1', '')
            # churl = 'https://www.axios.com/world/china'
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
            'https://www.axios.com/politics-policy',
            'https://www.axios.com/technology',
            'https://www.axios.com/world/china',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        divs = response.xpath("//div[@data-vars-content-id]|//article[@data-vars-content-id]")
        for div in divs:
            datavarscontentid = str(div.xpath("./@data-vars-content-id").get(''))
            link = div.xpath(".//a[@data-cy='top-table-story-headline' or @data-cy='content-card-header' or "
                             "@data-cy='story-promo-headline']/@href").get()
            if not link or not datavarscontentid:
                continue
            link = response.urljoin(link)
            link_hash = hashlib.sha1(datavarscontentid.encode('utf-8')).hexdigest()
            if self.redis_conn.hexists(f'{self.proname}_hash_done_urls', link_hash) and self.inc:
                ch_urls_json = self.redis_conn.hget(f'{self.proname}_hash_done_urls', link_hash)
                ch_urls = json.loads(ch_urls_json) if ch_urls_json else []
                if ch_url in ch_urls:
                    logging.info(f'{datavarscontentid} : repetition')
                else:
                    item = UyproItem()
                    item['ch_url'] = ch_url
                    item['tweet_id'] = datavarscontentid
                    item['taskid'] = self.taskid
                    item['bid'] = self.bid
                    ch_urls.append(ch_url)
                    self.redis_conn.hset(f'{self.proname}_hash_done_urls', link_hash, json.dumps(ch_urls))
                    if_new = True
                    yield item
            else:
                if_new = True
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'datavarscontentid': datavarscontentid})

        if if_new:
            json_data = response.xpath("//script[@id='__NEXT_DATA__']/text()").get()
            if json_data:
                try:
                    data = json.loads(json_data)
                    feedParams = data.get('props', {}).get('pageProps', {}).get('data', {}).get('feedParams', {})
                    topic_ids = ''
                    exclude_ids = []
                    subtopic_ids = ''
                    pageToken = data.get('props', {}).get('pageProps', {}).get('data', {}).get('nextPageToken', '')
                    if '/world/china' in ch_url:
                        subtopic_ids = feedParams.get('subtopic_ids', [])[0]
                        next_url = (f'https://www.axios.com/api/v1/mixed-content?subtopic_ids={subtopic_ids}'
                                    f'&page_size=5'
                                    f'&status=published'
                                    f'&include_on_site=true'
                                    f'&order_by=1'
                                    f'&include_sponsored=true'
                                    f'&content_type_filters=1'
                                    f'&pageToken={pageToken}')
                    else:
                        topic_ids = feedParams.get('topic_ids', [])[0]
                        exclude_ids = feedParams.get('exclude_ids', [])
                        next_url = (f'https://www.axios.com/api/v1/mixed-content?topic_ids={topic_ids}'
                                    f'&page_size=10'
                                    f'&exclude_ids={exclude_ids[0]}'
                                    f'&exclude_ids={exclude_ids[1]}'
                                    f'&exclude_ids={exclude_ids[2]}'
                                    f'&exclude_ids={exclude_ids[3]}'
                                    f'&exclude_ids={exclude_ids[4]}'
                                    f'&status=published'
                                    f'&include_on_site=true'
                                    f'&order_by=1'
                                    f'&include_sponsored=true'
                                    f'&content_type_filters=1'
                                    f'&content_type_filters=2'
                                    f'&pageToken={pageToken}')
                    yield response.follow(url=next_url, callback=self.parse_trd,
                                          meta={'ch_url': ch_url, 'topic_ids': topic_ids, 'exclude_ids': exclude_ids,
                                                'subtopic_ids': subtopic_ids, 'pageToken': pageToken})
                except json.JSONDecodeError as e:
                    logging.info(f'JSON decode error: {e}')
                except Exception as e:
                    logging.info(f'Unexpected error: {e}')

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        json_data = json.loads(response.xpath("//pre/text()").get(''))
        mixedContents = json_data.get('mixedContent', [])
        for content in mixedContents:
            id = content.get('storyContent', {}).get('id', '')
            datavarscontentid = str(id)
            link_hash = hashlib.sha1(datavarscontentid.encode('utf-8')).hexdigest()
            if self.redis_conn.hexists(f'{self.proname}_hash_done_urls', link_hash) and self.inc:
                ch_urls_json = self.redis_conn.hget(f'{self.proname}_hash_done_urls', link_hash)
                ch_urls = json.loads(ch_urls_json) if ch_urls_json else []
                if ch_url in ch_urls:
                    logging.info(f'{datavarscontentid} : repetition')
                else:
                    item = UyproItem()
                    item['ch_url'] = ch_url
                    item['tweet_id'] = datavarscontentid
                    item['taskid'] = self.taskid
                    item['bid'] = self.bid
                    ch_urls.append(ch_url)
                    self.redis_conn.hset(f'{self.proname}_hash_done_urls', link_hash, json.dumps(ch_urls))
                    if_new = True
                    yield item
            else:
                if_new = True
                link = f'https://www.axios.com/api/axios-web/dto/card/{id}?format=dto&type=PAC'
                yield response.follow(link, callback=self.parse_fou, meta={'ch_url': ch_url, 'datavarscontentid': datavarscontentid})
        if if_new:
            topic_ids = response.meta['topic_ids']
            exclude_ids = response.meta['exclude_ids']
            subtopic_ids = response.meta.get('subtopic_ids')
            pageToken = json_data.get('nextPage', '').get('nextPageToken', '')
            if pageToken:
                if '/world/china' in ch_url:
                    next_url = (f'https://www.axios.com/api/v1/mixed-content?subtopic_ids={subtopic_ids}'
                                f'&page_size=5'
                                f'&status=published'
                                f'&include_on_site=true'
                                f'&order_by=1'
                                f'&include_sponsored=true'
                                f'&content_type_filters=1'
                                f'&pageToken={pageToken}')
                else:
                    next_url = (f'https://www.axios.com/api/v1/mixed-content?topic_ids={topic_ids}'
                                f'&page_size=10'
                                f'&exclude_ids={exclude_ids[0]}'
                                f'&exclude_ids={exclude_ids[1]}'
                                f'&exclude_ids={exclude_ids[2]}'
                                f'&exclude_ids={exclude_ids[3]}'
                                f'&exclude_ids={exclude_ids[4]}'
                                f'&status=published'
                                f'&include_on_site=true'
                                f'&order_by=1'
                                f'&include_sponsored=true'
                                f'&content_type_filters=1'
                                f'&content_type_filters=2'
                                f'&pageToken={pageToken}')
                yield response.follow(url=next_url, callback=self.parse_trd,
                                      meta={'ch_url': ch_url, 'topic_ids': topic_ids, 'exclude_ids': exclude_ids,
                                            'subtopic_ids': subtopic_ids, 'pageToken': pageToken})

    def parse_fou(self, response):
        ch_url = response.meta['ch_url']
        datavarscontentid = response.meta['datavarscontentid']
        json_data = json.loads(response.xpath("//pre/text()").get(''))
        link = json_data.get('content', {}).get('permalink', '')
        yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'datavarscontentid': datavarscontentid})

    def article(self, response):
        item = UyproItem()
        datavarscontentid = response.meta['datavarscontentid']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = response.url
        lang = 'en'
        item['tweet_lang'] = lang
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(datavarscontentid.encode('utf-8')).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
