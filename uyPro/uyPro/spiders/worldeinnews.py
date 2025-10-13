import hashlib
import json
import logging

import scrapy
from newspaper import Article

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, translatetext, parse_date, replace_enter, update_ch_urls, detect_language, \
    translate_text_gemini, translate_text_siliconflow, translatetext_bing, translate_text_googleapi
from .webmod import get_map


class WorldeinnewsSpider(scrapy.Spider):
    name = "worldeinnews"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'DOWNLOADER_MIDDLEWARES': {'uyPro.middlewares.DrissionPageMiddleware': 543, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        # 'CONCURRENT_REQUESTS': 1,
        'CONCURRENT_REQUESTS_PER_IP': 1,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "worldeinnews"

    def start_requests(self):
        homepage = ''
        # homepage = 'https://world.einnews.com/news/pakistan-terrorism'
        # link = 'https://world.einnews.com/pr_news/671992652/new-novel-from-jeffrey-stephens-presents-story-of-' \
        #        'terrorist-plot-and-cia-that-mirrors-reality'
        # churl = 'https://world.einnews.com/news/pakistan-terrorism'
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://world.einnews.com/news/pakistan-terrorism'
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
                yield scrapy.Request(url=tweeturl, callback=self.article,
                                     meta={'ch_url': churl, 'link': tweeturl, 'full_link': tweeturl, 'createtime': ''})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://world.einnews.com/news/pakistan-terrorism',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_se(self, response):
        churl = response.meta['ch_url']
        yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl}, dont_filter=True)

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        divs = response.xpath("//div[@class='row-fluid'][1]/section[@class='span-p-m']/div/ul["
                              "@class='pr-feed']/li/div[@class='article-content']")
        for div in divs:
            link = div.xpath("./h3/a[@class='title']/@href").get('').split('&pg=')[0]
            createtime = div.xpath("string(./div[@class='pretitle']/span[@class='date'])").get('').strip()
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
                    item['tweet_id'] = response.urljoin(link)
                    item['taskid'] = self.taskid
                    item['bid'] = self.bid
                    ch_urls.append(ch_url)
                    self.redis_conn.hset(f'{self.proname}_hash_done_urls', link_hash, json.dumps(ch_urls))
                    if_new = True
                    yield item
            else:
                if_new = True
                full_link = response.urljoin(link)
                yield response.follow(link, callback=self.article,
                                      meta={'ch_url': ch_url, 'createtime': createtime, 'link': link,
                                            'full_link': full_link})
        next_url = response.xpath("//ul[@class='pagination']/li/a[text()='»']/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        full_link = response.meta['full_link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = full_link
        item['tweet_id'] = full_link
        item['tweet_url_original'] = response.url
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
                tweet_createtime = item['tweet_createtime']
                if tweet_createtime:
                    item['tweet_createtime'] = tweet_createtime
                    item['tweet_createtime_str'] = tweet_createtime
                else:
                    item['tweet_createtime'] = parse_date(response.meta['createtime'])
                    item['tweet_createtime_original'] = parse_date(response.meta['createtime'], 'UTC')
                    item['tweet_createtime_str'] = response.meta['createtime']
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
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
                item['tweet_title_tslt'] = translate_text_googleapi(article_title)
                if not item['tweet_title_tslt']:
                    item['tweet_title_tslt'] = translatetext_bing(article_title)
                if not item['tweet_title_tslt']:
                    item['tweet_title_tslt'] = translate_text_gemini(article_title).strip()
                if not item['tweet_title_tslt']:
                    item['tweet_title_tslt'] = translate_text_siliconflow(article_title).strip()
                article_content = replace_enter(article.text)
                if article_content:
                    item['tweet_content'] = replace_enter(article.text)
                    item['tweet_content_tslt'] = translate_text_googleapi(article_content)
                    if not item['tweet_content_tslt']:
                        item['tweet_content_tslt'] = translatetext_bing(article_content).strip()
                    if not item['tweet_content_tslt']:
                        item['tweet_content_tslt'] = translate_text_gemini(article_content).strip()
                    if not item['tweet_content_tslt']:
                        item['tweet_content_tslt'] = translate_text_siliconflow(article_content).strip()
                item['tweet_lang'] = detect_language(article_content) if article_content else detect_language(
                    article_title)
                item['tweet_author'] = article.meta_data.get('author', '')
                item['tweet_video'] = ''
                published_time = response.xpath("string(//meta[@property='article:published_time']/@content)").get(
                    '').strip()
                if published_time:
                    item['tweet_createtime'] = parse_date(published_time)
                    item['tweet_createtime_original'] = parse_date(published_time, 'UTC')
                    item['tweet_createtime_str'] = published_time
                elif article.publish_date:
                    item['tweet_createtime'] = parse_date(str(article.publish_date))
                    item['tweet_createtime_original'] = parse_date(str(article.publish_date), 'UTC')
                    item['tweet_createtime_str'] = str(article.publish_date)
                else:
                    item['tweet_createtime'] = parse_date(response.meta['createtime'])
                    item['tweet_createtime_original'] = parse_date(response.meta['createtime'], 'UTC')
                    item['tweet_createtime_str'] = response.meta['createtime']
                item['tweet_img_url'] = response.xpath("string(//meta[@property='og:image']/@content)").getall()
                item['tweet_table'] = ''
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
