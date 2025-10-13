import hashlib
import logging
import json
import scrapy
from scrapy.selector import Selector
from newspaper import Article

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, translatetext, parse_date, replace_enter, update_ch_urls
from .webmod import get_map, parse_tweet_zrumbeshold


class ZrumbeshSpider(scrapy.Spider):
    name = "zrumbesh"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/119.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS_PER_IP': 16,
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "zrumbesh"

    def start_requests(self):
        homepage = ''
        # homepage = 'https://zrumbesh.com/english/archive-2023/post/archives'
        # link = 'https://zrumbesh.com/english/archive-2023/post/entry/BLA-Jeeyand-29-12-23'
        # churl = 'https://zrumbesh.com/english/archive-2023/post/archives'
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
            elif method == 'getchannel' and 'zrumbesh.com/english' in churl:
                yield scrapy.Request(url=churl, callback=self.parse_list_old, meta={'ch_url': churl})
            elif method == 'getchannel' and 'english.zrumbesh.com' in churl:
                yield scrapy.Request(url=churl, callback=self.parse_new, meta={'ch_url': churl})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article_new,
                                     meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://zrumbesh.com/english/archive-2023/post/archives',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec_old, meta={'ch_url': link})
        chlinks = [
            'https://english.zrumbesh.com/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_new, meta={'ch_url': link})

    def parse_list_old(self, response):
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='blog-post-content']/div/ul/li/a/@href").getall()
        yield from response.follow_all(links, callback=self.parse_post_old, meta={'ch_url': ch_url})

    def parse_post_old(self, response):
        ch_url = response.meta['ch_url']
        changeStateArchive = response.xpath("//input[@id='changeStateArchive']/@value").get('')
        formdata = {
            "flag": "true",
            "changeState2": "DATENEW",
            "changeState3": "40",
            "changeState4": "0",
            "changeState5": "1",
            "changeState6": "",
            "changeState7": "0",
            "changePostType": "1",
            "changePostViewType": "1",
            "changeStateArchive": changeStateArchive
        }
        url = 'https://zrumbesh.com/english/archive-2023/post/fetchPostsAjax'
        yield scrapy.FormRequest(url, method='post', formdata=formdata, callback=self.parse_sec_old,
                                 meta={'ch_url': ch_url, 'changeStateArchive': changeStateArchive})

    def parse_sec_old(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        changeStateArchive = response.meta['changeStateArchive']
        html_str = response.json().get('html', '')
        selector = Selector(text=html_str)
        links = list(set(filter(None, selector.xpath('//a/@href').getall())))
        for link in links:
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
                    if_new = True
                    yield item
            else:
                if_new = True
                yield response.follow(link, callback=self.article_old, meta={'ch_url': ch_url, 'link': link})
        page = selector.xpath("string(//nav/ul[@class='pagination']/li[last()]/a[@class='page-link'])").get('')
        if page and if_new:
            for i in range(2, int(page) + 1):
                formdata = {
                    "flag": "true",
                    "changeState2": "DATENEW",
                    "changeState3": "40",
                    "changeState4": "0",
                    "changeState5": "1",
                    "changeState6": "",
                    "changeState7": "0",
                    "changePostType": "1",
                    "changePostViewType": "1",
                    "changeStateArchive": changeStateArchive
                }
                url = f'https://zrumbesh.com/english/archive-2023/post/fetchPostsAjax/{i}'
                yield scrapy.FormRequest(url, method='post', formdata=formdata, callback=self.parse_trd_old,
                                         meta={'ch_url': ch_url})

    def parse_trd_old(self, response):
        ch_url = response.meta['ch_url']
        html_str = response.json().get('html', '')
        selector = Selector(text=html_str)
        links = list(set(filter(None, selector.xpath('//a/@href').getall())))
        for link in links:
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
                yield response.follow(link, callback=self.article_old, meta={'ch_url': ch_url, 'link': link})

    def article_old(self, response):
        item = UyproItem()
        link = response.meta['link']
        ch_url = response.meta['ch_url']
        item['ch_url'] = ch_url
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = 'en'
        tweet_func = parse_tweet_zrumbeshold
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, ch_url)
                    # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
                yield item

    def parse_new(self, response):
        ch_url = response.meta['ch_url']
        links = response.xpath("//ul[@class='wp-block-archives-list wp-block-archives']/li/a/@href").getall()
        yield from response.follow_all(links, callback=self.parse_list_new, meta={'ch_url': ch_url})

    def parse_list_new(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='twp-archive-post-list']/div[@class='twp-row']/article//h3["
                               "@class='entry-title']/a/@href").getall()
        for link in links:
            link_hash = hashlib.sha1(link.encode()).hexdigest()
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
                    if_new = True
                    yield item
            else:
                if_new = True
                yield response.follow(link, callback=self.article_new, meta={'ch_url': ch_url, 'link': link})
        next_url = response.xpath("//div[@class='nav-links']/a[@class='next page-numbers']/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_list_new, meta={'ch_url': ch_url})

    def article_new(self, response):
        item = UyproItem()
        link = response.meta['link']
        ch_url = response.meta['ch_url']
        item['ch_url'] = ch_url
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = 'en'
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, ch_url)
                    # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
                yield item
        else:
            article = Article('')
            article.download(input_html=response.text)
            article.parse()
            item['tweet_content'] = ''
            item['tweet_content_tslt'] = ''
            article_title = article.title
            if article_title:
                item['tweet_title'] = article_title
                item['tweet_title_tslt'] = translatetext(article_title)
                article_content = replace_enter(article.text)
                if article_content:
                    item['tweet_content'] = replace_enter(article.text)
                    item['tweet_content_tslt'] = translatetext(article_content)
                item['tweet_author'] = article.meta_data.get('author', '')
                item['tweet_video'] = ''
                item['tweet_createtime'] = parse_date(str(article.publish_date))
                item['tweet_img_url'] = response.xpath("string(//meta[@property='og:image']/@content)").getall()
                item['tweet_table'] = ''
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, ch_url)
                    # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
                yield item
