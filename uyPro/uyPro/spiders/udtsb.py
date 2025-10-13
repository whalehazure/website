import hashlib
import json
import logging
import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls, detect_language
from .webmod import get_map


class UdtsbSpider(scrapy.Spider):
    name = "udtsb"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
        'CONCURRENT_REQUESTS_PER_IP': 16,
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = 'udtsb'

    def start_requests(self):
        homepage = ''
        # homepage = 'https://udtsb.com/cat/haberler/194'
        # link = 'https://udtsb.com//page/dogu-turkistanlilar-8-milyon-nakdi-ve-ayni-yardimda-bulundu/339'
        # churl = 'https://udtsb.com/cat/haberler/194'
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
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://udtsb.com/cat/haberler/194',
            'https://udtsb.com/en//cat/news/194',
            'https://udtsb.com/en//cat/we-in-the-press/196',
            'https://udtsb.com/en//cat/programs/200',
            'https://udtsb.com/en//cat/statements/197',
            # 'https://udtsb.com//cat/haberler/194',
            'https://udtsb.com//cat/basinda-biz/196',
            'https://udtsb.com//cat/programlar/200',
            'https://udtsb.com//cat/bildiriler/197',
            'https://udtsb.com/uy//cat/194',
            'https://udtsb.com/uy//cat/196',
            'https://udtsb.com/uy//cat/200',
            'https://udtsb.com/uy//cat/197',

        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='grid']/article[@class='event']/a/@href").getall()
        for link in links:
            link = response.urljoin(link)
            link_hash = hashlib.sha1(link.encode()).hexdigest()
            # if self.redis_conn.sismember(f'{self.proname}_done_urls', link_hash) and self.inc:
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
                    yield item
            else:
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                article_content = item.get('tweet_content', '')
                article_title = item.get('tweet_title', '')
                item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                    article_title)
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
                yield item
