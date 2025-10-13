import hashlib
import json
import logging
import os
import platform
import random
import re
import string
import time

import pandas as pd
import scrapy
from DrissionPage import ChromiumPage, ChromiumOptions
from DrissionPage.common import Settings
from scrapy.http import HtmlResponse
from scrapy.utils.python import to_bytes

from uyPro.items import UyproItem
from uyPro.settings import redis_conn, file_dir, proxy_list
from .utils import start_spider, parse_date, replace_enter, update_ch_urls
from .webmod import convert_traditional_to_simplified


class ChinatimesSpider(scrapy.Spider):
    name = "chinatimes"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
        # 'LOG_ENABLED': True
    }

    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = "chinatimes"

    def create_proxy_auth_extension(self, proxy_host, proxy_port, proxy_username, proxy_password, scheme='http',
                                    plugin_path=None):
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "16YUN Proxy",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version":"22.0.0"
        }
        """

        background_js = string.Template(
            """
            var config = {
                mode: "fixed_servers",
                rules: {
                    singleProxy: {
                        scheme: "${scheme}",
                        host: "${host}",
                        port: parseInt(${port})
                    },
                    bypassList: ["localhost"]
                }
            };

            chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

            function callbackFn(details) {
                return {
                    authCredentials: {
                        username: "${username}",
                        password: "${password}"
                    }
                };
            }

            chrome.webRequest.onAuthRequired.addListener(
                callbackFn,
                {urls: ["<all_urls>"]},
                ['blocking']
            );
            """
        ).substitute(
            host=proxy_host,
            port=proxy_port,
            username=proxy_username,
            password=proxy_password,
            scheme=scheme,
        )

        os.makedirs(plugin_path, exist_ok=True)
        with open(os.path.join(plugin_path, "manifest.json"), "w+") as f:
            f.write(manifest_json)
        with open(os.path.join(plugin_path, "background.js"), "w+") as f:
            f.write(background_js)

        return str(os.path.join(plugin_path))

    def get_page(self):
        proxy_url = random.choice(proxy_list)
        pattern = re.compile(
            r'http://(?P<proxyUser>[^:]+):(?P<proxyPass>[^@]+)@(?P<proxyHost>[^:]+):(?P<proxyPort>\d+)')
        match = pattern.match(proxy_url)
        if match:
            proxyHost = match.group('proxyHost')
            proxyPort = match.group('proxyPort')
            proxyUser = match.group('proxyUser')
            proxyPass = match.group('proxyPass')
        else:
            proxyHost = proxyPort = proxyUser = proxyPass = ''
        userAgent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/126.0.0.0 Safari/537.36")
        page = self.setup_browser(proxyHost, proxyPort, proxyUser, proxyPass, userAgent, plugin_path="/tmp/111")
        return page

    def setup_browser(self, proxy_host, proxy_port, proxy_username, proxy_password, user_agent, plugin_path):
        proxy_auth_plugin_path = self.create_proxy_auth_extension(
            proxy_host=proxy_host,
            proxy_port=proxy_port,
            proxy_username=proxy_username,
            proxy_password=proxy_password,
            plugin_path=plugin_path
        )

        co = ChromiumOptions().auto_port()
        Settings.cdp_timeout = 60
        co.set_user_agent(user_agent=user_agent)
        co.set_load_mode('eager')
        co.headless()
        if platform.system() != 'Windows':
            co.set_argument('--disable-gpu')
            co.set_argument('--no-sandbox')
            co.add_extension(proxy_auth_plugin_path)
        page = ChromiumPage(co)
        page.set.window.max()
        return page

    def start_requests(self):
        homepage = ''
        # homepage = 'https://www.rfa.org/english/news/uyghur'
        # link = 'https://www.rfa.org/english/news/uyghur/detainee-01112024105257.html'
        # churl = 'hhttps://www.rfa.org/english/news/uyghur'
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://www.chinatimes.com/armament/total'
            # # tweeturl = 'https://boxun.com/archives/381007'
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
                url = 'https://www.bing.com'
                yield scrapy.Request(url=url, callback=self.parse_sec, meta={'ch_url': churl})
            else:
                url = 'https://www.bing.com'
                yield scrapy.Request(url=url, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.chinatimes.com/armament/total',
            'https://www.chinatimes.com/politic/total/',
            'https://www.chinatimes.com/chinese/total/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        ch_url = response.meta['ch_url']
        attempts = 5
        page = None
        urls = []

        while attempts > 0:
            page = self.get_page()
            page.get(ch_url)
            eles1 = page.eles("xpath://section[@class='article-list']/ul/li//h3/a")
            urls = [ele1.link for ele1 in eles1]

            if not urls:
                page.save('chinatimes.html')
                logging.info("URLs are empty, closing and re-initializing the page")
                page.refresh()
                page.quit()
                attempts -= 1
                if attempts <= 0:
                    logging.error("Max attempts reached, stopping process")
                    return
            else:
                break

        if page and attempts > 0:
            linkpool = []
            while True:
                if_new = False
                ele = page.ele("xpath://li[@class='page-item']/a[text()='下一頁']")
                next_url = ele.link if ele else None

                for link in urls:
                    time.sleep(0.1)
                    if link not in linkpool:
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
                            try:
                                page.get(link)
                                response = HtmlResponse(
                                    url=response.url,
                                    status=response.status,
                                    headers=response.headers,
                                    body=page.html.encode('utf-8'),
                                    encoding='utf-8'
                                )
                                article_title = response.xpath("string(//meta[@property='og:title']/@content)"
                                                               ).get('').rsplit('-', 1)[0].strip()
                                if article_title:
                                    item = UyproItem()
                                    img_url = ''
                                    try:
                                        tele = page.ele(
                                            "xpath://div[@class='main-figure']/figure/div[@class='photo-container']")
                                        img = tele('tag:img')
                                        img_url = img.attr('src')
                                        if img_url:
                                            imgname = f'{hashlib.sha1(to_bytes(img_url)).hexdigest()}.jpg'
                                            file_path = os.path.join(f'{file_dir}/jpg', imgname)
                                            if os.path.exists(file_path):
                                                logging.info('img exists')
                                            else:
                                                img.save(path=f'{file_dir}/jpg', name=imgname, timeout=5)
                                            item['tweet_img'] = [imgname]
                                        else:
                                            item['tweet_img'] = []
                                    except Exception as e:
                                        logging.info(f'get img error : {e} {img_url}')
                                    item['ch_url'] = ch_url
                                    lang = 'zh'
                                    item['taskid'] = self.taskid
                                    item['bid'] = self.bid
                                    item['tweet_lang'] = lang
                                    item['tweet_url'] = link
                                    item['tweet_id'] = link
                                    # 保留原始繁体标题，简体版本保存到 _tslt 字段
                                    item['tweet_title'] = article_title
                                    item['tweet_title_tslt'] = convert_traditional_to_simplified(article_title)
                                    ps = response.xpath("//div[@class='article-body']/p")
                                    article_content = '\n'.join(
                                        [p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
                                    if article_content:
                                        article_content = replace_enter(article_content)
                                        # 保留原始繁体内容，简体版本保存到 _tslt 字段
                                        item['tweet_content'] = article_content
                                        item['tweet_content_tslt'] = convert_traditional_to_simplified(article_content)
                                    tweet_author = response.xpath(
                                        "string(//div[@class='author']/a)").get('').strip()
                                    # 作者信息不再转换，保留原始繁体
                                    item['tweet_author'] = tweet_author
                                    tweet_createtime = response.xpath(
                                        "string(//meta[@property='article:published_time']/@content)").get('').strip()
                                    item['tweet_createtime'] = parse_date(tweet_createtime)
                                    html_content = response.xpath("//div[@class='article-body']").get('')
                                    if '<table' in html_content:
                                        try:
                                            tables = pd.read_html(html_content)
                                            tweet_table = []
                                            for i, df in enumerate(tables):
                                                table_name = os.path.join(f'{file_dir}/csv',
                                                                          f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                                                directory = os.path.dirname(table_name)
                                                if not os.path.exists(directory):
                                                    os.makedirs(directory)
                                                df.to_csv(table_name, index=False, encoding='UTF-8')
                                                tweet_table.append(os.path.basename(table_name))
                                            if tweet_table:
                                                item['tweet_table'] = tweet_table
                                        except Exception as e:
                                            logging.info(f'get table error : {e}')
                                    if item:
                                        link_hash = hashlib.sha1(link.encode()).hexdigest()
                                        if not item.get('tweet_content') or item.get(
                                                'tweet_content_tslt') or lang == 'zh':
                                            update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                                        linkpool.append(link)
                                        yield item
                            except Exception as e:
                                logging.info(f'get page error : {e} {page.url}')
                    else:
                        logging.info(f'{link} is in linkpool')

                # 检查是否有下一页
                if if_new and next_url and len(linkpool) < 101:
                    try:
                        page.get(next_url)
                        eles1 = page.eles("xpath://section[@class='article-list']/ul/li//h3/a")
                        urls = [ele1.link for ele1 in eles1]
                    except Exception as e:
                        logging.info(f'get new page error : {e} {page.url}')
                else:
                    break

            page.quit()

    def article(self, response):
        ch_url = response.meta['ch_url']
        link = response.meta['link']
        proxy_url = random.choice(proxy_list)
        pattern = re.compile(
            r'http://(?P<proxyUser>[^:]+):(?P<proxyPass>[^@]+)@(?P<proxyHost>[^:]+):(?P<proxyPort>\d+)')
        match = pattern.match(proxy_url)
        if match:
            proxyHost = match.group('proxyHost')
            proxyPort = match.group('proxyPort')
            proxyUser = match.group('proxyUser')
            proxyPass = match.group('proxyPass')
        else:
            proxyHost = proxyPort = proxyUser = proxyPass = ''
        userAgent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/124.0.0.0 Safari/537.36")
        page = self.setup_browser(proxyHost, proxyPort, proxyUser, proxyPass, userAgent, plugin_path="/tmp/111")
        page.get(link)
        response = HtmlResponse(
            url=response.url,
            status=response.status,
            headers=response.headers,
            body=page.html.encode('utf-8'),
            encoding='utf-8'
        )
        article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[
            0].strip()
        if article_title:
            item = UyproItem()
            item['ch_url'] = ch_url
            lang = 'zh'
            item['taskid'] = self.taskid
            item['bid'] = self.bid
            item['tweet_lang'] = lang
            item['tweet_url'] = link
            item['tweet_id'] = link
            # 保留原始繁体标题，简体版本保存到 _tslt 字段
            item['tweet_title'] = article_title
            item['tweet_title_tslt'] = convert_traditional_to_simplified(article_title)
            ps = response.xpath("//div[@class='article-body']/p")
            article_content = '\n'.join(
                [p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
            if article_content:
                article_content = replace_enter(article_content)
                # 保留原始繁体内容，简体版本保存到 _tslt 字段
                item['tweet_content'] = article_content
                item['tweet_content_tslt'] = convert_traditional_to_simplified(article_content)
            tweet_author = response.xpath(
                "string(//div[@class='author']/a)").get('').strip()
            # 作者信息不再转换，保留原始繁体
            item['tweet_author'] = tweet_author
            tweet_createtime = response.xpath(
                "string(//meta[@property='article:published_time']/@content)").get('').strip()
            item['tweet_createtime'] = parse_date(tweet_createtime)
            img_url = ''
            try:
                tele = page.ele(
                    "xpath://div[@class='main-figure']/figure/div[@class='photo-container']")
                img = tele('tag:img')
                img_url = img.attr('src')
                if img_url:
                    imgname = f'{hashlib.sha1(to_bytes(img_url)).hexdigest()}.jpg'
                    file_path = os.path.join(f'{file_dir}/jpg', imgname)
                    if os.path.exists(file_path):
                        logging.info('img exists')
                    else:
                        img.save(path=f'{file_dir}/jpg', name=imgname)
                    item['tweet_img'] = [imgname]
                else:
                    item['tweet_img'] = []
            except Exception as e:
                logging.info(f'get img error : {e} {img_url}')
            html_content = response.xpath("//div[@class='article-body']").get('')
            if '<table' in html_content:
                try:
                    tables = pd.read_html(html_content)
                    tweet_table = []
                    for i, df in enumerate(tables):
                        table_name = os.path.join(f'{file_dir}/csv',
                                                  f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                        directory = os.path.dirname(table_name)
                        if not os.path.exists(directory):
                            os.makedirs(directory)
                        df.to_csv(table_name, index=False, encoding='UTF-8')
                        tweet_table.append(os.path.basename(table_name))
                    if tweet_table:
                        item['tweet_table'] = tweet_table
                except Exception as e:
                    logging.info(f'get table error : {e}')
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get(
                        'tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
        page.close()
        page.quit()
