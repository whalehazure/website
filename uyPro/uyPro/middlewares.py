#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UyPro新闻爬虫系统 - 中间件模块

本模块定义了Scrapy中间件，用于处理请求和响应，包括：
- 代理服务器轮换和管理
- 用户代理动态设置
- 浏览器自动化处理（DrissionPage）
- 反爬虫机制绕过
- 请求重试和错误处理
- 特殊网站的定制化处理

主要中间件类：
1. UyproSpiderMiddleware: 爬虫中间件（处理爬虫输入输出）
2. UyproDownloaderMiddleware: 下载器中间件（处理请求响应）

核心功能：
- 智能代理池管理
- 浏览器实例复用
- 动态用户代理选择
- CloudScraper反爬虫处理
- 特殊域名定制处理


参考文档:
- https://docs.scrapy.org/en/latest/topics/spider-middleware.html
- https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
"""

# ==================== 标准库导入 ====================
import base64
import hashlib
import os
import platform
import random
import re
import shutil
import string
import tempfile
import time

# ==================== 第三方库导入 ====================
import certifi
import cloudscraper
from DrissionPage import ChromiumOptions, WebPage
from DrissionPage.common import Settings
from scrapy import signals
from scrapy.http import HtmlResponse
from scrapy.utils.log import logger
from scrapy.utils.python import to_bytes

# ==================== 项目内部导入 ====================
from uyPro.settings import proxy_list, file_dir, proxy_list_centcommil

# ==================== 中间件类定义 ====================


class UyproSpiderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the spider middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def process_spider_input(self, response, spider):
        # Called for each response that goes through the spider
        # middleware and into the spider.

        # Should return None or raise an exception.
        return None

    def process_spider_output(self, response, result, spider):
        # Called with the results returned from the Spider, after
        # it has processed the response.

        # Must return an iterable of Request, or item objects.
        for i in result:
            yield i

    def process_spider_exception(self, response, exception, spider):
        # Called when a spider or process_spider_input() method
        # (from other spider middleware) raises an exception.

        # Should return either None or an iterable of Request or item objects.
        pass

    def process_start_requests(self, start_requests, spider):
        # Called with the start requests of the spider, and works
        # similarly to the process_spider_output() method, except
        # that it doesn’t have a response associated.

        # Must return only requests (not items).
        for r in start_requests:
            yield r

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class UyproDownloaderMiddleware:
    # Not all methods need to be defined. If a method is not defined,
    # scrapy acts as if the downloader middleware does not modify the
    # passed objects.

    @classmethod
    def from_crawler(cls, crawler):
        # This method is used by Scrapy to create your spiders.
        s = cls()
        crawler.signals.connect(s.spider_opened, signal=signals.spider_opened)
        return s

    def _setup_proxy(self, request, proxy_url):
        """Helper method to set up proxy for a request"""
        proxy_scheme = 'https' if request.url.startswith('https://') else 'http'
        if '://' in proxy_url:
            proxy_url = proxy_url.split('://')[1]
        proxy = f"{proxy_scheme}://{proxy_url}"
        request.meta['proxy'] = proxy

        # Add proxy authorization if credentials are present
        if "@" in proxy_url:
            credentials = proxy_url.split("@")[0]
            username, password = credentials.split(":")
            request.headers['Proxy-Authorization'] = b'Basic ' + base64.b64encode(
                f'{username}:{password}'.encode()).strip()
        return proxy_url

    def process_request(self, request, spider):
        # Called for each request that goes through the downloader
        # middleware.
        if platform.system() != 'Windows' and proxy_list:
            proxy_url = random.choice(proxy_list)
            if 'www.centcom.mil' in request.url:
                proxy_url = random.choice(proxy_list_centcommil)
            self._setup_proxy(request, proxy_url)

        # Must either:
        # - return None: continue processing this request
        # - or return a Response object
        # - or return a Request object
        # - or raise IgnoreRequest: process_exception() methods of
        #   installed downloader middleware will be called
        return None

    def process_response(self, request, response, spider):
        # Called with the response returned from the downloader.

        # Must either;
        # - return a Response object
        # - return a Request object
        # - or raise IgnoreRequest
        return response

    def process_exception(self, request, exception, spider):
        # Called when a download handler or a process_request()
        # (from other downloader middleware) raises an exception.

        # Must either:
        # - return None: continue processing this exception
        # - return a Response object: stops process_exception() chain
        # - return a Request object: stops process_exception() chain
        pass

    def spider_opened(self, spider):
        spider.logger.info("Spider opened: %s" % spider.name)


class CloudScraperMiddleware:
    def __init__(self):
        # 初始化 CloudScraper 对象
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'firefox',
                'platform': 'android',
                'mobile': True,
                'custom': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 '
                          'Mobile Safari/537.36'
            }
        )

    def process_request(self, request, spider):
        # 获取代理信息，如果有代理的话
        proxy = random.choice(proxy_list) if (platform.system() != 'Windows' and proxy_list) else None
        proxies = None

        if proxy:
            # 配置 HTTP 和 HTTPS 代理
            proxies = {
                'http': proxy,
                'https': proxy,
            }

        # 使用 cloudscraper 发送请求，并使用代理（如果有）
        response = self.scraper.get(request.url, verify=certifi.where(), proxies=proxies)

        # 返回 Scrapy 格式的 HtmlResponse
        return HtmlResponse(
            url=request.url,
            status=response.status_code,
            body=response.content,
            encoding='utf-8',
            request=request
        )


class DrissionPageMiddleware:
    # 默认用户代理
    DEFAULT_USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 "
                          "Safari/537.36")
    # 代理URL正则表达式模式
    PROXY_PATTERN = re.compile(
        r'http://(?P<proxyUser>[^:]+):(?P<proxyPass>[^@]+)@'
        r'(?P<proxyHost>[^:]+):(?P<proxyPort>\d+)'
    )

    # 为不同网站定义不同的 User-Agent
    USER_AGENTS = {
        'uyghurcongress.org': [
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile "
            "Safari/537.36",
        ],
        'default': [
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        ]
    }

    @classmethod
    def from_crawler(cls, crawler):
        # 从爬虫中获取churl参数
        domain_ = None
        if hasattr(crawler.spider, 'domain_') and crawler.spider.domain_:
            domain_ = crawler.spider.domain_
            logger.info(f"从爬虫中获取到domain_: {domain_}")

        # 初始化中间件，传递churl参数
        s = cls(crawler.settings, domain_=domain_)
        crawler.signals.connect(s.spider_closed, signal=signals.spider_closed)

        return s

    def __init__(self, settings, domain_=None):
        # 从设置中获取代理列表
        self.proxy_list = proxy_list

        # 记录当前请求的URL
        self.current_url = domain_

        # 根据URL选择合适的User-Agent
        if self.current_url:
            self.user_agent = self.get_user_agent_for_url(self.current_url)
            logger.info(f"初始化时根据URL选择User-Agent: {self.user_agent[:50]}...")
        else:
            self.user_agent = self.DEFAULT_USER_AGENT
            logger.info(f"初始化时使用默认User-Agent: {self.user_agent[:50]}...")

        self.page = None  # 初始化 page 对象
        self.mode = 'd'

        # 创建临时目录用于存储代理插件
        self.plugin_path = tempfile.mkdtemp()
        self.proxy_url = None

        # 不再在初始化时创建浏览器，而是在第一次请求时创建

    def get_user_agent_for_url(self, url):
        """根据URL选择合适的User-Agent

        Args:
            url: 请求的URL

        Returns:
            str: 适合该URL的User-Agent
        """
        # 如果没有URL，返回默认User-Agent
        if not url:
            return random.choice(self.USER_AGENTS['default'])

        # 从 URL 中提取域名
        try:
            # 检查是否有针对该域名的User-Agent
            for key in self.USER_AGENTS:
                if key in url:
                    return random.choice(self.USER_AGENTS[key])

        except Exception as e:
            logger.warning(f"解析URL域名失败: {e}, URL: {url}")

            # 如果解析URL失败，返回默认User-Agent
            pass

        # 如果没有找到匹配的域名，返回默认User-Agent
        return random.choice(self.USER_AGENTS['default'])

    def _initialize_browser(self, request_url=None):
        """初始化浏览器实例

        Args:
            request_url: 请求URL
        """
        # # 如果提供了请求URL，更新User-Agent
        # if request_url:
        #     self.user_agent = self.get_user_agent_for_url(request_url)
        #     logger.info(f"根据请求URL({request_url})选择User-Agent: {self.user_agent[:50]}...")

        if not self.proxy_list:
            # 如果没有代理，初始化无代理的浏览器
            self.page = self.setup_browser(plugin_path=self.plugin_path, url=request_url)
            return

        # 选择一个代理
        proxy_url = random.choice(self.proxy_list)
        logger.info(f"选择代理: {proxy_url}")
        self.proxy_url = proxy_url

        # 解析代理URL
        match = self.PROXY_PATTERN.match(proxy_url)
        if match:
            proxy_info = match.groupdict()
            self.page = self.setup_browser(
                proxy_host=proxy_info.get('proxyHost'),
                proxy_port=proxy_info.get('proxyPort'),
                proxy_username=proxy_info.get('proxyUser'),
                proxy_password=proxy_info.get('proxyPass'),
                plugin_path=self.plugin_path,
                url=request_url
            )
        else:
            # 如果代理信息无效，初始化无代理的浏览器
            self.page = self.setup_browser(plugin_path=self.plugin_path, url=request_url)

    def _setup_proxy(self, request, proxy_url):
        """设置请求的代理

        Args:
            request: 请求对象
            proxy_url: 代理URL

        Returns:
            str: 处理后的代理URL
        """
        proxy_scheme = 'https' if request.url.startswith('https://') else 'http'
        if '://' in proxy_url:
            proxy_url = proxy_url.split('://')[1]
        proxy = f"{proxy_scheme}://{proxy_url}"
        request.meta['proxy'] = proxy

        # 如果存在代理认证信息，添加认证头
        if "@" in proxy_url:
            credentials = proxy_url.split("@")[0]
            username, password = credentials.split(":")
            request.headers['Proxy-Authorization'] = b'Basic ' + base64.b64encode(
                f'{username}:{password}'.encode()).strip()
        return proxy_url

    def _should_use_direct_proxy(self, request):
        """判断是否应该使用直接代理处理请求"""
        return ((request.meta.get('type') in ['jpg', 'pdf'] or 'www.bing.com' in request.url)
                and 'uyghurcongress.org' not in request.url)

    def _get_proxies_dict(self):
        """获取代理字典配置"""
        if self.proxy_url:
            return {
                'http': self.proxy_url,
                'https': self.proxy_url,
            }
        return None

    def _is_image_url(self, url):
        """判断 URL 是否指向图片资源"""
        image_formats = ['.jpeg', '.jpg', '.png', '.gif', '.bmp', '.tiff', '.webp']
        return any(fmt in url for fmt in image_formats)

    def _is_einnews_image(self, request):
        """判断是否是world.einnews.com网站的图片URL

        使用request.meta中的ch_url进行判断，如果不存在则使用request.url

        Args:
            request: 请求对象

        Returns:
            bool: 是否是world.einnews.com网站的图片
        """
        # 优先使用meta中的ch_url
        ch_url = request.meta.get('ch_url', '')
        url = ch_url if ch_url else request.url
        return 'world.einnews.com' in url

    def _get_page_response(self, request, status=200):
        """创建并返回页面响应"""
        return HtmlResponse(
            url=self.page.url,
            status=status,
            body=self.page.html.encode() if isinstance(self.page.html, str) else self.page.html,
            encoding='utf-8',
            request=request
        )

    def _is_ein_news_pakistan_terrorism(self, url):
        """判断是否是 EIN News Pakistan Terrorism 页面

        Args:
            url: 请求URL

        Returns:
            bool: 是否是目标页面
        """
        return url in [
            'https://world.einnews.com/news/pakistan-terrorism/',
            'https://world.einnews.com/news/pakistan-terrorism'
        ]

    def _handle_ein_news_pakistan_terrorism(self, spider):
        """处理 EIN News Pakistan Terrorism 页面

        这个方法处理特定页面的验证码和点击操作

        Args:
            spider: 爬虫实例，用于日志记录

        Returns:
            bool: 是否成功处理页面
        """
        # 尝试点击“Click”链接
        self._try_click_element('tag:a@text():Click', 'tmp', 'picb.jpg', 'pica.jpg', spider)

        # 如果需要处理验证码
        if not self._handle_captcha(spider):
            # 再次尝试点击“Click”链接
            self._try_click_element('tag:a@text():Click', 'tmp', 'pic2.jpg', 'pic3.jpg', spider)
            spider.logger.error("验证码处理失败，无法继续处理页面")
            return False

        # 验证码处理成功后，再次尝试点击"Click"链接
        self._try_click_element('tag:a@text():Click', 'tmp', 'pic2.jpg', 'pic3.jpg', spider)

        # 尝试点击“no”输入框
        self._try_click_element('tag:input@id:no', 'tmp', 'pic4.jpg', 'pic5.jpg', spider)

        # 尝试点击“Click here to continue”链接
        self._try_click_element('tag:a@text()^Click here to continue', 'tmp', 'pic6.jpg', 'pic7.jpg', spider)

        return True

    def _try_click_element(self, selector, path, screenshot_before, screenshot_after, spider):
        """尝试点击元素并捕获屏幕截图

        Args:
            selector: 元素选择器
            path: 截图保存路径
            screenshot_before: 点击前截图文件名
            screenshot_after: 点击后截图文件名
            spider: 爬虫实例

        Returns:
            bool: 是否成功点击元素
        """
        link = self.page.ele(selector)
        if link:
            self.page.get_screenshot(path=path, name=screenshot_before)
            link.click()
            self.page.wait.load_start()
            self.page.get_screenshot(path=path, name=screenshot_after)
            return True
        return False

    def _has_captcha(self):
        """检查页面是否包含验证码

        Returns:
            bool: 是否存在验证码
        """
        return any(phrase in self.page.title.lower() for phrase in ["请稍候…", "just a moment..."])

    def _handle_captcha(self, spider):
        """处理 EIN News 页面的验证码

        Args:
            spider: 爬虫实例，用于日志记录

        Returns:
            bool: 是否成功处理验证码
        """
        # 如果没有验证码，直接返回
        if not self._has_captcha():
            return True

        self.page.set.load_mode.normal()

        self.page.get_screenshot(path='tmp', name='we.jpg')
        spider.logger.info(f'Captcha detected!')

        # 尝试绕过验证码
        bypass_failed_times = 0
        while bypass_failed_times < 5:
            try:
                # 如果页面标题不再显示验证码提示，则跳出
                if not self._has_captcha():
                    return True

                # 寻找验证码元素
                wrapper = self.page.ele(".main-content")
                spacer = wrapper.eles("tag:div")[0]
                div1 = spacer.ele("tag:div")
                div2 = div1.ele("tag:div")
                iframe = div2.shadow_root.ele("tag:iframe", timeout=15)
                spider.logger.info(iframe)

                self.page.wait(2)
                iframeRoot = iframe("tag:body").shadow_root
                cbLb = iframeRoot.ele(".cb-lb", timeout=10)
                link = cbLb.ele("tag:input", timeout=10)
                spider.logger.info(link)

                if link:
                    self.page.wait(2)
                    self.page.get_screenshot(path='tmp', name='pic.jpg')
                    link.click(by_js=None)
                    self.page.wait(10)
                    self.page.get_screenshot(path='tmp', name='pic1.jpg')
                    self.page.wait.load_start()
                    self.page.set.load_mode.eager()
                    return True
                break
            except Exception:
                bypass_failed_times += 1
                spider.logger.info(f"{bypass_failed_times=}/5")
                self.page.refresh()
                time.sleep(2.0)

        # 等待一下再继续
        self.page.wait(3)
        self.page.set.load_mode.eager()
        return False

    def _handle_special_domain_captcha(self, spider, max_attempts=3):
        """处理特定域名的验证码

        Args:
            spider: 爬虫实例，用于日志记录
            max_attempts: 最大尝试次数

        Returns:
            bool: 是否成功处理验证码
        """
        spider.logger.info('Captcha detected!')

        for _ in range(max_attempts):
            try:
                # 如果验证码已经消失，返回成功
                if not self._has_captcha():
                    return True

                # 定位验证码元素
                iframe = self.page.ele(".main-content").eles("tag:div")[0].ele("tag:div").ele(
                    "tag:div").shadow_root.ele("tag:iframe", timeout=15)
                spider.logger.info(iframe)

                self.page.wait(2)
                link = iframe("tag:body").shadow_root.ele(".cb-lb", timeout=10).ele("tag:input", timeout=10)
                spider.logger.info(link)

                if link:
                    self.page.wait(2)
                    self.page.get_screenshot(path='tmp', name='pic.jpg')
                    link.click(by_js=None)
                    self.page.wait(10)
                    self.page.get_screenshot(path='tmp1', name='pic1.jpg')
                    self.page.wait.load_start()

                    # 如果验证码仍然存在，继续尝试
                    if self._has_captcha():
                        continue

                # 如果成功处理或无法找到元素，跳出循环
                break
            except Exception as e:
                spider.logger.info(e)
                time.sleep(2.0)

        # 检查最终结果
        return not self._has_captcha()

    def _download_gknb_images(self, url, spider):
        """下载 gknb.gov.kg 域名的图片

        Args:
            url: 请求URL
            spider: 爬虫实例，用于日志记录

        Returns:
            list: 下载的图片文件名列表
        """
        tweet_img = []
        # 使用XPath选择器定位所有图片元素
        for img in self.page.eles("xpath://div[contains(@class,'post-content')]//figure/img"):
            img_url = ''
            try:
                # 获取图片URL
                img_url = img.attr('src')
                # 生成唯一的文件名
                imgname = f'{hashlib.sha1(to_bytes(img_url)).hexdigest()}.jpg'
                file_path = os.path.join(f'{file_dir}/jpg', imgname)

                # 如果文件不存在，则下载
                if not os.path.exists(file_path):
                    img.save(path=f'{file_dir}/jpg', name=imgname, timeout=3)
                else:
                    spider.logger.info('img exists')

                tweet_img.append(imgname)
            except Exception as e:
                spider.logger.error(f'下载图片 {img_url} 时出错: {e}')

        return tweet_img

    def process_request(self, request, spider):
        # 处理需要直接代理的请求
        if self._should_use_direct_proxy(request):
            if platform.system() != 'Windows' and proxy_list:
                proxy_url = random.choice(proxy_list)
                if 'www.centcom.mil' in request.url:
                    proxy_url = random.choice(proxy_list_centcommil)
                self._setup_proxy(request, proxy_url)
            return None

        try:
            # 如果浏览器实例不存在，则初始化浏览器
            if self.page is None:
                spider.logger.info(f"初始化浏览器，请求URL: {request.url}")
                self._initialize_browser(request_url=request.url)

            proxies = self._get_proxies_dict()

            # 处理图片URL
            if self._is_image_url(request.url):
                # 对于world.einnews.com网站的图片，使用Scrapy本身的下载器
                if self._is_einnews_image(request):
                    logger.info(f"处理world.einnews.com图片: {request.url}")
                    ch_url = request.meta.get('ch_url', request.url)
                    spider.logger.info(f"使用Scrapy下载器处理world.einnews.com图片: {ch_url}")
                    # 设置代理（如果有）
                    if platform.system() != 'Windows' and proxy_list:
                        proxy_url = random.choice(proxy_list)
                        self._setup_proxy(request, proxy_url)
                    return None  # 返回None，让Scrapy继续处理
                # 对于其他网站的图片，使用self.page下载
                elif self.mode == 'd' or platform.system() == 'Windows':
                    self.page.get(request.url, stream=True)
                else:
                    self.page.get(request.url, stream=True, proxies=proxies)
                return self._get_page_response(request)

            # 处理普通URL
            if self.mode == 'd' or platform.system() == 'Windows':
                self.page.get(request.url)
            else:
                self.page.get(request.url, proxies=proxies)
            # 处理 EIN News Pakistan Terrorism 页面
            if self._is_ein_news_pakistan_terrorism(request.url):
                if not self._handle_ein_news_pakistan_terrorism(spider):
                    spider.logger.error("EIN News Pakistan Terrorism 页面处理失败")
                    return self._get_page_response(request, status=403)
            if 'world.einnews.com' in request.url and self._has_captcha():
                if not self._handle_captcha(spider):
                    return self._get_page_response(request, status=403)
            # 处理 uyghurcongress.org 和 gknb.gov.kg 域名的验证码
            if any(domain in request.url for domain in ['uyghurcongress.org', 'gknb.gov.kg']) and \
                    self._has_captcha():
                if not self._handle_special_domain_captcha(spider):
                    return self._get_page_response(request, status=403)
            # 处理 gknb.gov.kg 域名的图片下载
            if 'gknb.gov.kg' in request.url:
                request.meta['tweet_img'] = self._download_gknb_images(request.url, spider)
                return self._get_page_response(request)
            self.page.wait.doc_loaded()
            changemodelist = [
                'vot.org',
            ]
            if self.mode == 'd' and any(domain in request.url for domain in changemodelist):
                if platform.system() == 'Windows':
                    self.page.change_mode()
                else:
                    self.page.change_mode(go=False)
                    self.page.get(request.url, proxies=proxies)
                self.mode = 's'

            return self._get_page_response(request)
        except Exception as e:
            # spider.logger.error(f'处理请求 {request.url} 时出错: {e}')
            spider.logger.exception(f'处理请求 {request.url} 时出错: {e}')
            self.page.get_screenshot(path='tmp3', name='pic3.jpg')
            return None

    def setup_browser(self, proxy_host=None, proxy_port=None, proxy_username=None, proxy_password=None,
                      scheme='http', plugin_path=None, url=None):
        co = ChromiumOptions().auto_port()
        Settings.cdp_timeout = 60
        co.set_user_agent(user_agent=self.user_agent)
        co.headless()
        co.set_timeouts(base=10)

        # 对于world.einnews.com域名，设置eager加载模式以加快页面加载
        if url and 'world.einnews.com' in url:
            co.set_load_mode('eager')
            co.no_imgs()
            co.incognito()
            co.auto_port()
            logger.info(f"为 {url} 设置eager加载模式")

        if platform.system() != 'Windows':
            co.set_argument('--disable-gpu')
            co.set_argument('--no-sandbox')

            # 如果提供了完整的代理信息，创建代理认证扩展
            if all([proxy_host, proxy_port, proxy_username, proxy_password]):
                proxy_auth_plugin_path = self.create_proxy_auth_extension(
                    proxy_host=proxy_host,
                    proxy_port=proxy_port,
                    proxy_username=proxy_username,
                    proxy_password=proxy_password,
                    scheme=scheme,
                    plugin_path=plugin_path
                )
                co.add_extension(proxy_auth_plugin_path)

        # 初始化 ChromiumPage 对象
        page = WebPage(chromium_options=co)
        page.set.window.max()
        return page

    def create_proxy_auth_extension(self, proxy_host, proxy_port, proxy_username, proxy_password, scheme='http',
                                    plugin_path=None):
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "代理扩展",
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
        with open(os.path.join(plugin_path, "manifest.json"), "w+", encoding='utf-8') as f:
            f.write(manifest_json)
        with open(os.path.join(plugin_path, "background.js"), "w+", encoding='utf-8') as f:
            f.write(background_js)

        return plugin_path

    def spider_closed(self, spider):
        """在爬虫关闭时清理资源

        该方法在爬虫关闭时被调用，用于关闭浏览器实例和清理临时文件。

        Args:
            spider: 爬虫实例，由Scrapy框架提供
        """
        # 关闭浏览器实例
        if self.page:
            self.page.quit()

        # 清理临时目录
        if os.path.exists(self.plugin_path):
            shutil.rmtree(self.plugin_path)
