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
from uyPro.settings import redis_conn, proxy_list, file_dir
from .utils import start_spider, update_ch_urls, parse_date, replace_enter, translate_text_googleapi


class IrrawaddySpider(scrapy.Spider):
    name = "irrawaddy"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        # 'AUTOTHROTTLE_DEBUG': True,
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
        userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        page = self.setup_browser(proxyHost, proxyPort, proxyUser, proxyPass, userAgent, plugin_path="/tmp/irrawaddy")
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
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'inc', '', '1_1_1_1', '')
            # churl = 'https://www.irrawaddy.com/category/news'
            # inputdata = {}
            # tweeturl = 'https://www.irrawaddy.com/news/burma/...'
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
                # gettweet
                pass
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.irrawaddy.com/category/news',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        """解析频道页面，提取文章链接并使用 DrissionPage 点击 Load More 按钮翻页"""
        ch_url = response.meta['ch_url']

        # 创建 DrissionPage 浏览器实例
        page = self.get_page()

        try:
            # 访问页面
            page.get(ch_url)
            page.wait.doc_loaded()

            # 等待页面加载完成
            time.sleep(random.uniform(1, 3))

            # 循环点击 "Load More" 按钮
            max_clicks = 20
            click_count = 0
            linkpool = []  # 用于收集所有文章链接

            while click_count < max_clicks:
                # 提取当前页面的文章链接
                article_links = page.eles('xpath://article/div/h3/a')

                if_new = False
                for link_ele in article_links:
                    link = link_ele.attr('href')
                    if not link:
                        continue

                    # 如果链接已经在 linkpool 中，跳过
                    if link in linkpool:
                        continue

                    link_hash = hashlib.sha1(link.encode()).hexdigest()
                    if self.redis_conn.hexists(f'{self.proname}_hash_done_urls', link_hash) and self.inc:
                        ch_urls_json = self.redis_conn.hget(f'{self.proname}_hash_done_urls', link_hash)
                        ch_urls = json.loads(ch_urls_json) if ch_urls_json else []
                        if ch_url in ch_urls:
                            logging.info(f'{link} : repetition')
                        else:
                            # 将链接添加到 linkpool，稍后处理
                            linkpool.append(link)
                            if_new = True
                    else:
                        # 新链接，添加到 linkpool
                        linkpool.append(link)
                        if_new = True
                        logging.info(f'新链接: {link}')

                # 如果没有发现新链接，停止翻页
                if not if_new:
                    logging.info('未发现新链接，停止翻页')
                    break
                time.sleep(3)

                # 滚动到页面底部，确保按钮可见
                page.scroll.to_bottom()
                time.sleep(1)

                # 尝试多种方式查找 "Load More" 按钮
                load_more_button = None

                # 方法1: CSS 选择器 - .jeg_block_loadmore a
                try:
                    load_more_button = page.ele('.jeg_block_loadmore a', timeout=2)
                    if load_more_button:
                        logging.info('方法1成功: CSS 选择器 .jeg_block_loadmore a')
                except:
                    pass

                # 方法2: XPath 选择器
                if not load_more_button:
                    try:
                        load_more_button = page.ele('xpath://div[@class="jeg_block_loadmore"]/a', timeout=2)
                        if load_more_button:
                            logging.info('方法2成功: XPath 选择器')
                    except:
                        pass

                # 方法3: 文本匹配
                if not load_more_button:
                    try:
                        load_more_button = page.ele('text=Load More', timeout=2)
                        if load_more_button:
                            logging.info('方法3成功: 文本匹配 text=Load More')
                    except:
                        pass

                # 方法4: 包含文本匹配
                if not load_more_button:
                    try:
                        load_more_button = page.ele('text:Load More', timeout=2)
                        if load_more_button:
                            logging.info('方法4成功: 包含文本匹配 text:Load More')
                    except:
                        pass

                # 方法5: 查找所有链接，通过文本过滤
                if not load_more_button:
                    try:
                        all_links = page.eles('tag:a')
                        for link in all_links:
                            if link.text and 'Load More' in link.text:
                                load_more_button = link
                                logging.info('方法5成功: 遍历所有链接找到按钮')
                                break
                    except:
                        pass

                if not load_more_button:
                    # 调试：打印页面底部的 HTML
                    logging.error('所有方法都未找到 "Load More" 按钮')
                    try:
                        # 尝试查找父元素
                        parent = page.ele('.jeg_block_loadmore', timeout=2)
                        if parent:
                            logging.info(f'找到父元素 .jeg_block_loadmore: {parent.html[:500]}')
                        else:
                            logging.error('连父元素 .jeg_block_loadmore 都未找到')
                    except Exception as e:
                        logging.error(f'查找父元素时出错: {e}')
                    break

                # 检查按钮文本，如果是 "No More Posts" 或正在加载则跳过
                button_text = load_more_button.text
                if button_text and ('No More' in button_text or 'Loading' in button_text):
                    logging.info(f'按钮文本为 "{button_text}"，等待或停止翻页')
                    if 'No More' in button_text:
                        break
                    # 如果是 Loading 状态，等待加载完成
                    time.sleep(5)
                    continue

                # 点击按钮
                logging.info(f'点击 "Load More" 按钮（第 {click_count + 1} 次）')
                load_more_button.click()

                # 等待按钮状态变为 Loading
                time.sleep(1)

                # 等待按钮恢复为 Load More（表示加载完成）
                max_wait = 15  # 最多等待15秒
                wait_count = 0
                while wait_count < max_wait:
                    try:
                        current_button = page.ele('.jeg_block_loadmore a', timeout=1)
                        if current_button and 'Loading' not in current_button.text:
                            logging.info('新内容加载完成')
                            break
                    except:
                        pass
                    time.sleep(1)
                    wait_count += 1

                # 额外等待确保内容渲染完成
                time.sleep(2)

                click_count += 1

            # 翻页完成，开始处理收集到的链接
            logging.info(f'翻页完成，共点击 {click_count} 次 "Load More" 按钮，收集到 {len(linkpool)} 个链接')

            # 遍历 linkpool，访问每个链接并提取内容
            for link in linkpool:
                try:
                    logging.info(f'正在访问文章: {link}')
                    page.get(link)
                    page.wait.doc_loaded()
                    time.sleep(random.uniform(1, 2))

                    # 创建 HtmlResponse 对象以便使用 XPath
                    html_response = HtmlResponse(
                        url=link,
                        status=200,
                        headers={},
                        body=page.html.encode('utf-8'),
                        encoding='utf-8'
                    )

                    # 提取文章标题
                    article_title = html_response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
                    if not article_title:
                        article_title = html_response.xpath("string(//h1[@class='entry-title']//text())").get('').strip()

                    if article_title:
                        item = UyproItem()
                        item['ch_url'] = ch_url
                        item['tweet_lang'] = 'en'  # irrawaddy 是英文网站
                        item['taskid'] = self.taskid
                        item['bid'] = self.bid
                        item['tweet_url'] = link
                        item['tweet_id'] = link
                        item['tweet_title'] = article_title
                        item['tweet_title_tslt'] = translate_text_googleapi(article_title)

                        # 提取文章内容
                        ps = html_response.xpath("//div[@class='content-inner ']/p")
                        article_content = '\n'.join(
                            [p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
                        if article_content:
                            article_content = replace_enter(article_content)
                            item['tweet_content'] = article_content
                            item['tweet_content_tslt'] = translate_text_googleapi(article_content)

                        # 提取作者
                        item['tweet_author'] = html_response.xpath(
                            "string(//meta[@name='author']/@content)").get('').strip()

                        # 提取发布时间
                        tweet_createtime = html_response.xpath(
                            "string(//meta[@property='article:published_time']/@content)").get('').strip()
                        if tweet_createtime:
                            item['tweet_createtime'] = parse_date(tweet_createtime)

                        # 提取图片
                        try:
                            img_ele = page.ele('xpath://div[@class="jeg_inner_content"]/div/a/div/img/@src')
                            if img_ele:
                                img_url = img_ele.attr('src')
                                if img_url:
                                    imgname = f'{hashlib.sha1(to_bytes(img_url)).hexdigest()}.jpg'
                                    file_path = os.path.join(f'{file_dir}/jpg', imgname)
                                    if os.path.exists(file_path):
                                        logging.info('图片已存在')
                                    else:
                                        img_ele.save(path=f'{file_dir}/jpg', name=imgname)
                                    item['tweet_img'] = [imgname]
                        except Exception as e:
                            logging.info(f'提取图片时出错: {e} {link}')

                        # 提取表格
                        html_content = html_response.xpath("//div[@class='content-inner ']").get('')
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
                                logging.info(f'提取表格时出错: {e}')

                        # 更新 Redis
                        if item:
                            link_hash = hashlib.sha1(link.encode()).hexdigest()
                            update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                            yield item
                            logging.info(f'成功提取文章: {article_title}')
                    else:
                        logging.warning(f'未找到文章标题: {link}')

                except Exception as e:
                    logging.error(f'处理文章时出错: {e} {link}')
                    continue

            # 关闭浏览器
            page.quit()
            logging.info(f'所有文章处理完成')

        except Exception as e:
            logging.error(f'使用 DrissionPage 翻页时出错: {e}')
            if 'page' in locals():
                page.quit()


