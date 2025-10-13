# -*- coding: utf-8 -*-
"""
httpbin 爬虫

自动生成的爬虫模板，基于网站结构分析
域名: httpbin.org
语言: en
网站类型: general
"""

import scrapy
import json
import logging
from uyPro.items import UyproItem
from uyPro.spiders.utils import start_spider
from uyPro.spiders.webmod import get_map


class HttpbinSpider(scrapy.Spider):
    name = "httpbin"
    allowed_domains = ["httpbin.org"]
    
    def __init__(self, name=None):
        super().__init__(name)
        self.taskid = ''
        self.bid = ''
        self.inc = ''
        self.proname = self.name
    
    def start_requests(self):
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            self.taskid = taskid
            self.bid = inputfilename.split('_')[3]
            self.crawler.stats.set_value('inputdata', inputdata)
            self.crawler.stats.set_value('inputfilename', inputfilename)
            self.crawler.stats.set_value('recent_files_append', recent_files_append)
            self.inc = False if dltype == 'full' else True
            
            if method == 'ch':
                yield scrapy.Request(
                    url=churl,
                    callback=self.parse,
                    meta={'ch_url': churl}
                )
            else:
                yield scrapy.Request(
                    url=tweeturl,
                    callback=self.parse_article,
                    meta={'ch_url': tweeturl}
                )
                
        except TypeError as e:
            logging.info(f'exit:{e}')
    
    def parse(self, response):
        """解析列表页"""
        ch_url = response.meta.get('ch_url', response.url)
        
        
        # 提取文章链接
        article_links = response.css('a[href]::attr(href)').getall()
        for link in article_links:
            if link:
                article_url = response.urljoin(link)
                yield scrapy.Request(
                    url=article_url,
                    callback=self.parse_article,
                    meta={'ch_url': article_url}
                )
    
    def parse_article(self, response):
        """解析文章页"""
        ch_url = response.meta.get('ch_url', response.url)
        
        # 使用webmod进行内容解析
        parse_func = get_map().get('httpbin.org')
        if parse_func:
            try:
                result = parse_func(response.text, ch_url)
                if result:
                    item = UyproItem()
                    item.update(result)
                    item['taskid'] = self.taskid
                    item['bid'] = self.bid
                    yield item
            except Exception as e:
                logging.error(f"解析文章失败: {e}")
        else:
            logging.warning(f"未找到 httpbin.org 的解析函数")
