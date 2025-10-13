import hashlib
import json
import logging

import scrapy
from newspaper import Article
from scrapy.selector import Selector
from uyPro.items import UyproItem
from uyPro.settings import redis_conn, pgmid, deviceid
from .utils import start_spider, update_ch_urls, createerrorlogfile, translatetext, replace_enter, parse_date, \
    replace_encrypted_emails_with_script
from .webmod import get_map


class HizbuttahrirSpider(scrapy.Spider):
    name = "hizbuttahrir"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/126.0.0.0 Safari/537.36',
        'CONCURRENT_REQUESTS_PER_IP': 16,
        'CLOSESPIDER_ITEMCOUNT': 30,
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.inputdata = {}
        self.inputfilename = ''
        self.proname = "hizbuttahrir"

    def start_requests(self):
        homepage = ''
        # homepage = 'https://www.hizb-ut-tahrir.info/en/index.php/press-releases/central-media-office.html'
        # homepage = 'https://www.hizb-ut-tahrir.info/en/index.php/2017-01-28-14-59-33/news-comment.html'
        # link = 'https://www.hizb-ut-tahrir.info/en/index.php/press-releases/central-media-office/25772.html'
        # churl = 'https://www.hizb-ut-tahrir.info/en/index.php/press-releases/central-media-office.html'
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            self.taskid = taskid
            self.bid = inputfilename.split('_')[3]
            self.inputdata = inputdata
            self.inputfilename = inputfilename
            self.crawler.stats.set_value('inputdata', inputdata)
            self.crawler.stats.set_value('inputfilename', inputfilename)
            self.crawler.stats.set_value('recent_files_append', recent_files_append)
            self.inc = False if dltype == 'full' else True
            if homepage:
                yield scrapy.Request(url=homepage, callback=self.parse, meta={'ch_url': homepage})
            elif method == 'getchannel':
                yield scrapy.Request(url=churl, callback=self.parse, meta={'ch_url': churl})
            else:
                yield scrapy.Request(url=tweeturl, callback=self.article,
                                     meta={'ch_url': churl, 'link': tweeturl, 'tweet_createtime': ''})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        # chlinks = [
        #     'https://www.hizb-ut-tahrir.info/en/index.php/press-releases/central-media-office.html',
        #     # 'https://www.hizb-ut-tahrir.info/en/index.php/2017-01-28-14-59-33/news-comment.html',
        # ]
        # for link in chlinks:
        #     yield response.follow(link, callback=self.parse_paging, meta={'ch_url': link})
        ch_url = response.meta['ch_url']
        if 'central-media-office.html' in ch_url:
            links = response.xpath("//nav[@id='gkExtraMenu']/ul/li[a[@title='Media Offices']]/div//a/@href").getall()
            for link in links:
                yield response.follow(link, callback=self.parse_sec, meta={'ch_url': ch_url}, dont_filter=True)
        elif 'news-comment.html' in ch_url:
            links = response.xpath("//nav[@id='gkExtraMenu']/ul/li[a[@title='Commentaries']]/div//a/@href").getall()
            for link in links:
                yield response.follow(link, callback=self.parse_sec, meta={'ch_url': ch_url}, dont_filter=True)
        else:
            jsontext = {"taskid": self.inputdata.get('tasklist', [{}])[0].get('taskid', ''), "count": 0,
                        "deviceid": deviceid, "pgmid": pgmid, "noresult": "config_error"}
            noresult = "config_error"
            createerrorlogfile(jsontext, self.inputfilename, self.inputdata, noresult)

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        divs = response.xpath("//div[@id='itemListPrimary']/div/div[@class='itemsContainerWrap']")
        for div in divs:
            link = div.xpath("./article/header/h4/a/@href").get('')
            if link:
                link = response.urljoin(link)
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                tweet_createtime = div.xpath("./article/header/ul/li[@class='itemDate']/time[@datetime]/@datetime").get(
                    '')
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
                    yield response.follow(link, callback=self.article,
                                          meta={'ch_url': ch_url, 'link': link, 'tweet_createtime': tweet_createtime})
        next_url = response.xpath("//ul/li[@class='pagination-next']/a[@title='Next']/@href").get()
        if next_url and if_new:
            yield response.follow(url=next_url, callback=self.parse_sec, meta={'ch_url': ch_url})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        tweet_createtime = parse_date(response.meta['tweet_createtime'])
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        item['tweet_lang'] = 'en'
        tweet_func = get_map(response.url)
        if tweet_func:
            html_content = replace_encrypted_emails_with_script(response.body)
            new_response = Selector(text=html_content)
            item = tweet_func(new_response, item)
            if item:
                item['tweet_createtime'] = tweet_createtime if tweet_createtime else item['tweet_createtime']
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
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
                    item['tweet_content'] = article_content
                    item['tweet_content_tslt'] = translatetext(article_content)
                item['tweet_author'] = article.meta_data.get('author', '')
                item['tweet_video'] = ''
                item['tweet_createtime'] = tweet_createtime if tweet_createtime else parse_date(
                    str(article.publish_date))
                item['tweet_img_url'] = response.xpath("string(//meta[@property='og:image']/@content)").getall()
                item['tweet_table'] = ''
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt'):
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                    # self.redis_conn.sadd(f'{self.proname}_done_urls', link_hash)
                yield item
