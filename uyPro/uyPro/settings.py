#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UyPro新闻爬虫系统 - Scrapy配置文件

本文件包含了Scrapy爬虫框架的所有配置设置，包括：
- 基础爬虫设置
- 中间件配置
- 管道配置
- 日志配置
- Redis配置
- 代理设置


参考文档:
- https://docs.scrapy.org/en/latest/topics/settings.html
- https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
- https://docs.scrapy.org/en/latest/topics/spider-middleware.html
"""

import configparser
import platform
import redis
import logging
from logging.handlers import RotatingFileHandler
from scrapy.utils.log import configure_logging

# ==================== 日志配置 ====================

# 禁用Scrapy默认日志，使用自定义日志配置
LOG_ENABLED = False
configure_logging(install_root_handler=False)

# 配置轮转日志文件
log_file = 'website.log'
root_logger = logging.getLogger()
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')

# 创建轮转文件处理器：最大5MB，保留2个备份文件
rotating_file_log = RotatingFileHandler(
    log_file,
    maxBytes=1024 * 1024 * 5,  # 5MB
    backupCount=2,
    encoding='utf-8'
)
rotating_file_log.setLevel(logging.INFO)
rotating_file_log.setFormatter(formatter)
root_logger.addHandler(rotating_file_log)

# ==================== 基础爬虫设置 ====================

BOT_NAME = "uyPro"
"""str: 爬虫项目名称"""

SPIDER_MODULES = ["uyPro.spiders"]
"""list: 爬虫模块路径"""

NEWSPIDER_MODULE = "uyPro.spiders"
"""str: 新爬虫的默认模块路径"""

# ==================== 用户代理设置 ====================

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"
"""str: 默认用户代理字符串，模拟Chrome浏览器"""

# ==================== 爬虫行为设置 ====================

ROBOTSTXT_OBEY = False
"""bool: 是否遵守robots.txt规则，设为False以绕过限制"""

# ==================== 并发和延迟设置 ====================

# 最大并发请求数（默认：16）
# CONCURRENT_REQUESTS = 32

# 同一网站的请求延迟（秒）
# DOWNLOAD_DELAY = 3

# 每个域名的并发请求数
# CONCURRENT_REQUESTS_PER_DOMAIN = 16

# 每个IP的并发请求数
# CONCURRENT_REQUESTS_PER_IP = 16

# ==================== Cookie和控制台设置 ====================

# 禁用Cookie（默认启用）
# COOKIES_ENABLED = False

# 禁用Telnet控制台（默认启用）
# TELNETCONSOLE_ENABLED = False

# ==================== 请求头设置 ====================

# 覆盖默认请求头
# DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
# }

# ==================== 中间件配置 ====================

# 爬虫中间件配置
# SPIDER_MIDDLEWARES = {
#    "uyPro.middlewares.UyproSpiderMiddleware": 543,
# }

# 下载器中间件配置
DOWNLOADER_MIDDLEWARES = {
   "uyPro.middlewares.UyproDownloaderMiddleware": 543,
}
"""dict: 下载器中间件配置，包含代理、用户代理轮换等功能"""

# ==================== 扩展配置 ====================

# Scrapy扩展配置
# EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
# }

# ==================== 数据管道配置 ====================

# 数据处理管道配置
# ITEM_PIPELINES = {
#    "uyPro.pipelines.UyproPipeline": 300,
# }

# ==================== 自动限速配置 ====================

# 启用自动限速扩展（默认禁用）
# AUTOTHROTTLE_ENABLED = True
# AUTOTHROTTLE_START_DELAY = 5        # 初始下载延迟
# AUTOTHROTTLE_MAX_DELAY = 60         # 最大下载延迟
# AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0  # 目标并发数
# AUTOTHROTTLE_DEBUG = False          # 显示限速统计信息

# ==================== HTTP缓存配置 ====================

# 启用HTTP缓存（默认禁用）
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 0       # 缓存过期时间（0表示永不过期）
# HTTPCACHE_DIR = "httpcache"         # 缓存目录
# HTTPCACHE_IGNORE_HTTP_CODES = []    # 忽略的HTTP状态码
# HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# ==================== 其他设置 ====================

# 设置未来兼容的默认值
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
"""str: 请求指纹实现版本"""

# 异步反应器设置（可选）
# TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

FEED_EXPORT_ENCODING = "utf-8"
"""str: 数据导出编码格式"""

# ==================== 配置文件加载 ====================

# 根据操作系统选择配置文件
config_file = 'configwin.ini' if platform.system() == 'Windows' else 'configlinux.ini'
config = configparser.ConfigParser()
config.read(config_file)

# ==================== 路径配置 ====================

folder_path = config.get('DEFAULT', 'folder_path')
"""str: 主文件夹路径，存储爬取数据的根目录"""

processed_path = config.get('DEFAULT', 'processed_path')
"""str: 已处理文件路径，存储处理完成的数据"""

file_dir = config.get('DEFAULT', 'file_dir')
"""str: 文件目录，存储下载的媒体文件"""

dest_zip_file_path = config.get('DEFAULT', 'dest_zip_file_path')
"""str: 目标压缩文件路径，用于数据打包"""

deviceid = config.get('DEFAULT', 'deviceid')
"""str: 设备ID，标识当前爬虫运行的设备"""

pgmid = config.get('DEFAULT', 'pgmid')
"""str: 程序ID，标识当前爬虫程序"""

zip_file_path = config.get('DEFAULT', 'zip_file_path')
"""str: 压缩文件路径，临时压缩文件存储位置"""

# ==================== 文件存储配置 ====================

FILES_STORE = file_dir
"""str: Scrapy文件存储路径"""

MEDIA_ALLOW_REDIRECTS = True
"""bool: 允许媒体文件下载时的重定向"""

# ==================== Redis配置 ====================

# 根据操作系统配置Redis连接
redis_conn = redis.Redis() if platform.system() == 'Windows' else redis.Redis(port=6363, password='zyredis2222')
"""Redis: Redis数据库连接对象，用于数据缓存和队列管理"""

# ==================== Selenium配置 ====================

SELENIUM_DRIVER_NAME = 'chrome'
"""str: Selenium使用的浏览器驱动名称"""

SELENIUM_DRIVER_ARGUMENTS = [
    '--headless',                    # 无头模式运行
    f'user-agent={USER_AGENT}',     # 设置用户代理
    "--incognito",                  # 隐身模式
    "--disable-dev-shm-usage",      # 禁用/dev/shm使用
    "--no-sandbox"                  # 禁用沙盒模式
]
"""list: Chrome浏览器启动参数列表"""

# ==================== 代理配置 ====================

# 加载主代理列表
with open('proxy.list') as f:
    proxy_list = [line.strip() for line in f if line.strip()]
"""list: 主代理服务器列表"""

# 加载备用代理列表
with open('proxy2.list') as f:
    traproxylist = [line.strip() for line in f if line.strip()]
"""list: 备用代理服务器列表"""

# 加载特定网站代理列表
with open('proxy_centcommil.list') as f:
    proxy_list_centcommil = [line.strip() for line in f if line.strip()]
"""list: 特定网站（centcommil）专用代理列表"""

# ==================== 特殊域名配置 ====================

url_domain_list = [
    'www.ethrw.org',
]
"""list: 需要特殊处理的域名列表"""

# ==================== 爬虫超时配置 ====================

CLOSESPIDER_TIMEOUT_NO_ITEM = 1800
"""int: 无数据项时的超时时间（秒），30分钟"""

CLOSESPIDER_ITEMCOUNT = 300
"""int: 最大爬取项目数量，达到后自动停止"""

CLOSESPIDER_TIMEOUT = 7200
"""int: 爬虫总超时时间（秒），2小时"""
