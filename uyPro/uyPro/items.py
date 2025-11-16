#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UyPro新闻爬虫系统 - 数据项定义模块

本模块定义了爬虫系统中使用的数据结构和字段。
UyproItem类包含了新闻文章的所有相关信息，包括原始内容、翻译内容、
媒体文件、元数据等。

"""

import scrapy


class UyproItem(scrapy.Item):
    """
    新闻文章数据项类

    定义了爬取新闻文章时需要收集的所有字段信息。
    包括文章内容、翻译、媒体文件、时间信息等。
    """

    # ==================== 基础信息字段 ====================

    ch_url = scrapy.Field()
    """str: 频道URL，标识文章来源的频道或分类页面"""

    tweet_url = scrapy.Field()
    """str: 文章URL，文章的完整访问地址"""

    tweet_id = scrapy.Field()
    """str: 文章ID，文章的唯一标识符"""

    tweet_url_original = scrapy.Field()
    """str: 原始URL，文章的原始链接（可能经过重定向）"""

    # ==================== 内容字段 ====================

    tweet_title = scrapy.Field()
    """str: 文章标题，原始语言的标题"""

    tweet_title_tslt = scrapy.Field()
    """str: 翻译标题，翻译成中文的标题"""

    tweet_content = scrapy.Field()
    """str: 文章内容，原始语言的正文内容"""

    tweet_content_tslt = scrapy.Field()
    """str: 翻译内容，翻译成中文的正文内容"""

    tweet_author = scrapy.Field()
    """str: 文章作者，作者姓名或机构"""

    tweet_lang = scrapy.Field()
    """str: 文章语言，原始文章的语言代码（如：en, zh, ar等）"""

    tweet_ipv4 = scrapy.Field()
    """str: 发布者IPv4地址，文章发布者的IP地址"""

    # ==================== 时间字段 ====================

    tweet_createtime = scrapy.Field()
    """datetime: 创建时间，文章发布的标准化时间"""

    tweet_createtime_original = scrapy.Field()
    """str: 原始时间，网站上显示的原始时间格式"""

    tweet_createtime_str = scrapy.Field()
    """str: 时间字符串，格式化后的时间字符串"""

    # ==================== 媒体文件字段 ====================

    tweet_img = scrapy.Field()
    """list: 图片文件，下载后的图片文件路径列表"""

    tweet_pdf = scrapy.Field()
    """list: PDF文件，下载后的PDF文件路径列表"""

    tweet_img_url = scrapy.Field()
    """list: 图片URL列表，文章中包含的所有图片链接"""

    tweet_pdf_url = scrapy.Field()
    """list: PDF URL列表，文章中包含的所有PDF链接"""

    tweet_table = scrapy.Field()
    """list: 表格数据，文章中的表格内容"""

    tweet_video = scrapy.Field()
    """list: 视频文件，文章中的视频内容"""

    tweet_comments = scrapy.Field()
    """list: 评论数据列表，包含所有评论的详细信息"""

    # ==================== 系统字段 ====================

    taskid = scrapy.Field()
    """str: 任务ID，爬取任务的唯一标识"""

    deviceid = scrapy.Field()
    """str: 设备ID，执行爬取的设备标识"""

    pgmid = scrapy.Field()
    """str: 程序ID，爬虫程序的标识"""

    bid = scrapy.Field()
    """str: 批次ID，爬取批次的标识"""

    capture_time = scrapy.Field()
    """datetime: 采集时间，数据被爬取的时间戳"""
