#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UyPro新闻爬虫系统 - 网站解析模块

本模块是整个爬虫系统的核心解析引擎，包含了80+个新闻网站的内容解析函数。
每个网站都有专门的解析函数，用于提取文章的标题、内容、作者、时间、图片等信息。

主要功能：
1. 网站内容解析：支持80+个国际新闻网站
2. 多语言处理：自动检测语言并进行翻译
3. 时间格式化：统一不同网站的时间格式
4. 图片处理：提取和处理文章图片
5. 文本清理：去除HTML标签、格式化文本
6. 数据标准化：将不同网站的数据统一为标准格式

支持的网站类型：
- 国际新闻媒体（BBC、Jerusalem Post、SCMP等）
- 政府官方网站（各国外交部、政府新闻）
- 人权组织网站（HRW、Amnesty等）
- 地区性新闻网站（中亚、非洲、亚太等）
- 专业媒体（军事、外交、文化等）

核心函数：
- parsetweet(): 统一的数据处理和翻译函数
- parse_tweet_[网站名](): 各网站专用解析函数
- 时间处理、文本清理、图片提取等辅助函数

"""

# ==================== 标准库导入 ====================
import base64
import hashlib
import io
import json
import logging
import os
import re
from datetime import datetime
from urllib.parse import urlparse, urljoin

# ==================== 第三方库导入 ====================
import pandas as pd
from bs4 import BeautifulSoup
from lxml import html
from scrapy.http import HtmlResponse
from scrapy.utils.python import to_bytes

# ==================== 项目内部导入 ====================
from uyPro.settings import file_dir
from .utils import (
    translatetext, parse_date, replace_enter, convert_turkish_date_to_datetime_short,
    extract_first_date, split_string, split_mixed_text, translatetext_bing,
    translatetext_bo, remove_font_tags, detect_language, translate_text_siliconflow,
    translate_text_gemini, translate_text_googleapi
)

# ==================== 可选依赖处理 ====================

# 繁体转简体中文转换器（可选依赖）
try:
    from opencc import OpenCC

    cc = OpenCC('t2s')  # 繁体转简体转换器
except ImportError:
    cc = None
    logging.warning("opencc-python-reimplemented 库未安装，繁体转简体功能将被禁用")


def convert_traditional_to_simplified(text):
    """将繁体中文转换为简体中文"""
    if not text or not cc:
        return text
    try:
        return cc.convert(text)
    except Exception as e:
        logging.warning(f"繁体转简体转换失败: {e}")
        return text


def extract_datetime(input_str: str):
    match = re.search(r'(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})', input_str)
    if not match:
        return None
    combined_str = f"{match.group(1)} {match.group(2)}"
    return str(datetime.strptime(combined_str, '%d.%m.%Y %H:%M'))


def clean_html_script(_html: str):
    pattern = r'<\s*script.*?/\s*script\s*>'
    return re.sub(pattern, '', _html, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)


def process_response(response: HtmlResponse) -> HtmlResponse:
    encoding = response.encoding
    cleaned_html = clean_html_script(response.text)
    return HtmlResponse(
        url=response.url,
        status=response.status,
        headers=response.headers,
        body=cleaned_html.encode(encoding),
        encoding=encoding,
        request=response.request
    )


def parsetweet_bing(item, article_title, article_content, tweet_author, tweet_createtime, tweet_img_url, html_content,
                    dt="America/New_York", split_func=split_string, translate=True):
    item['tweet_content'] = ''
    item['tweet_content_tslt'] = ''
    if article_title:
        item['tweet_title'] = article_title
        item['tweet_title_tslt'] = translatetext_bing(article_title) if translate else ''
        if article_content:
            article_content = replace_enter(article_content)
            item['tweet_content'] = article_content
            item['tweet_content_tslt'] = translatetext_bing(article_content, split_func=split_func) if translate else ''
        item['tweet_author'] = tweet_author
        item['tweet_createtime'] = parse_date(tweet_createtime, dt)
        item['tweet_img_url'] = list(set(tweet_img_url))
        item['tweet_video'] = ''
        item['tweet_table'] = ''
        if '<table' in html_content:
            try:
                tables = pd.read_html(html_content)
                tweet_table = []
                for i, df in enumerate(tables):
                    table_name = os.path.join(f'{file_dir}/csv', f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                    directory = os.path.dirname(table_name)
                    if not os.path.exists(directory):
                        os.makedirs(directory)
                    df.to_csv(table_name, index=False, encoding='UTF-8')
                    tweet_table.append(os.path.basename(table_name))
                if tweet_table:
                    item['tweet_table'] = tweet_table
            except Exception as e:
                logging.info(f'get table error : {e}')
        return item
    else:
        return None


def parsetweet_bo(item, article_title, article_content, tweet_author, tweet_createtime, tweet_img_url, html_content,
                  dt="America/New_York", split_func=split_string, translate=True):
    item['tweet_content'] = ''
    item['tweet_content_tslt'] = ''
    if article_title:
        item['tweet_title'] = article_title
        item['tweet_title_tslt'] = translatetext_bo(article_title) if translate else ''
        if article_content:
            article_content = replace_enter(article_content)
            item['tweet_content'] = article_content
            item['tweet_content_tslt'] = translatetext_bo(article_content, split_func=split_func) if translate else ''
        item['tweet_author'] = tweet_author
        item['tweet_createtime'] = parse_date(tweet_createtime, dt)
        item['tweet_img_url'] = list(set(tweet_img_url))
        item['tweet_video'] = ''
        item['tweet_table'] = ''
        if '<table' in html_content:
            try:
                tables = pd.read_html(html_content)
                tweet_table = []
                for i, df in enumerate(tables):
                    table_name = os.path.join(f'{file_dir}/csv', f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                    directory = os.path.dirname(table_name)
                    if not os.path.exists(directory):
                        os.makedirs(directory)
                    df.to_csv(table_name, index=False, encoding='UTF-8')
                    tweet_table.append(os.path.basename(table_name))
                if tweet_table:
                    item['tweet_table'] = tweet_table
            except Exception as e:
                logging.info(f'get table error : {e}')
        return item
    else:
        return None


def parsetweet_pdf(item, article_title, article_content, tweet_author, tweet_createtime, tweet_img_url, html_content,
                   dt="America/New_York", split_func=split_string, translate=True, tweet_pdf_url=None):
    if tweet_pdf_url is None:
        tweet_pdf_url = []
    item['tweet_content'] = ''
    item['tweet_content_tslt'] = ''
    if article_title:
        item['tweet_title'] = article_title
        item['tweet_title_tslt'] = translatetext(article_title) if translate else ''
        if article_content:
            article_content = replace_enter(article_content)
            item['tweet_content'] = article_content
            item['tweet_content_tslt'] = translatetext(article_content, split_func=split_func) if translate else ''
        item['tweet_author'] = tweet_author
        item['tweet_createtime'] = parse_date(tweet_createtime, dt)
        item['tweet_img_url'] = list(set(tweet_img_url))
        item['tweet_pdf_url'] = list(set(tweet_pdf_url))
        if '<table' in html_content:
            try:
                tables = pd.read_html(html_content)
                tweet_table = []
                for i, df in enumerate(tables):
                    table_name = os.path.join(f'{file_dir}/csv', f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                    directory = os.path.dirname(table_name)
                    if not os.path.exists(directory):
                        os.makedirs(directory)
                    df.to_csv(table_name, index=False, encoding='UTF-8')
                    tweet_table.append(os.path.basename(table_name))
                if tweet_table:
                    item['tweet_table'] = tweet_table
            except Exception as e:
                logging.info(f'get table error : {e}')
        return item
    else:
        return None


# ==================== 核心数据处理函数 ====================

def _should_skip_translation(item, site_exclusions=None):
    """
    判断是否应该跳过翻译

    Args:
        item (UyproItem): 数据项对象
        site_exclusions (list): 需要排除翻译的网站列表

    Returns:
        bool: True表示跳过翻译，False表示需要翻译
    """
    if site_exclusions is None:
        site_exclusions = ['istiqlalhaber.com', '/uyghur-j.org/']

    ch_url = item.get('ch_url', '')
    return any(exclusion in ch_url for exclusion in site_exclusions)


def _translate_text_with_fallback(text, translate, item, split_func=split_string, max_length=4800,
                                  _translatetext=translatetext):
    """
    使用多个翻译引擎进行文本翻译，带降级机制

    翻译优先级：
    1. 主翻译引擎 (_translatetext)
    2. Bing翻译 (translatetext_bing)
    3. SiliconFlow翻译 (translate_text_siliconflow)
    4. Gemini翻译 (translate_text_gemini)

    Args:
        text (str): 待翻译文本
        translate (bool): 是否启用翻译
        item (UyproItem): 数据项对象，用于检查网站排除列表
        split_func (function): 文本分割函数
        max_length (int): 最大文本长度
        _translatetext (function): 主翻译函数

    Returns:
        str: 翻译后的文本，如果翻译失败则返回空字符串
    """
    if not translate or not text:
        return ''

    # 检查是否需要跳过翻译
    if _should_skip_translation(item, ['istiqlalhaber.com']):
        return ''

    # 尝试主翻译引擎
    try:
        if text == text:  # 简单的文本验证
            result = _translatetext(text, split_func=split_func, max_length=max_length)
            if result and result.strip():
                return result
    except Exception as e:
        logging.warning(f"主翻译引擎失败: {e}")

    # 检查特定网站排除
    if _should_skip_translation(item, ['/uyghur-j.org/']):
        return ''

    # 尝试Bing翻译
    try:
        result = translatetext_bing(text, split_func=split_func)
        if result and result.strip():
            return result
    except Exception as e:
        logging.warning(f"Bing翻译失败: {e}")

    # 尝试SiliconFlow翻译
    try:
        result = translate_text_siliconflow(text)
        if result and result.strip():
            return result.strip()
    except Exception as e:
        logging.warning(f"SiliconFlow翻译失败: {e}")

    # 尝试Gemini翻译
    try:
        result = translate_text_gemini(text)
        if result and result.strip():
            return result.strip()
    except Exception as e:
        logging.warning(f"Gemini翻译失败: {e}")

    return ''


def _process_title(item, article_title, translate, convert_traditional, split_func, _translatetext):
    """
    处理文章标题，包括繁简转换和翻译

    Args:
        item (UyproItem): 数据项对象
        article_title (str): 原始标题
        translate (bool): 是否翻译
        convert_traditional (bool): 是否转换繁体中文
        split_func (function): 文本分割函数
        _translatetext (function): 翻译函数
    """
    if not article_title:
        return

    # 设置原始标题（保留繁体）
    item['tweet_title'] = article_title

    # 处理 _tslt 字段
    if convert_traditional:
        # 繁体转简体，保存到 _tslt 字段
        simplified_title = convert_traditional_to_simplified(article_title)
        item['tweet_title_tslt'] = simplified_title
    else:
        # 翻译标题
        item['tweet_title_tslt'] = _translate_text_with_fallback(
            article_title, translate, item, split_func, 4800, _translatetext
        )


def _process_content(item, article_content, translate, convert_traditional, split_func, max_length, _translatetext):
    """
    处理文章内容，包括文本清理、繁简转换和翻译

    Args:
        item (UyproItem): 数据项对象
        article_content (str): 原始内容
        translate (bool): 是否翻译
        convert_traditional (bool): 是否转换繁体中文
        split_func (function): 文本分割函数
        max_length (int): 最大文本长度
        _translatetext (function): 翻译函数
    """
    if not article_content:
        return

    # 文本清理：替换换行符和特殊字符
    cleaned_content = replace_enter(article_content)

    # 设置原始内容（保留繁体）
    item['tweet_content'] = cleaned_content

    # 处理 _tslt 字段
    if convert_traditional:
        # 繁体转简体，保存到 _tslt 字段
        simplified_content = convert_traditional_to_simplified(cleaned_content)
        item['tweet_content_tslt'] = simplified_content
    else:
        # 翻译内容
        item['tweet_content_tslt'] = _translate_text_with_fallback(
            cleaned_content, translate, item, split_func, max_length, _translatetext
        )


def _extract_tables_from_html(html_content):
    """
    从HTML内容中提取表格数据并保存为CSV文件

    Args:
        html_content (str): HTML内容

    Returns:
        list: 保存的CSV文件名列表
    """
    if '<table' not in html_content:
        return []

    try:
        # 使用pandas解析HTML表格
        tables = pd.read_html(io.StringIO(html_content))
        tweet_table = []

        for _, df in enumerate(tables):
            # 跳过只有一行或空表格
            if df.shape[0] <= 1:
                continue

            # 生成唯一的文件名（基于表格内容的SHA1哈希）
            table_hash = hashlib.sha1(to_bytes(str(df))).hexdigest()
            table_name = os.path.join(f'{file_dir}/csv', f'{table_hash}.csv')

            # 确保目录存在
            directory = os.path.dirname(table_name)
            if not os.path.exists(directory):
                os.makedirs(directory)

            # 保存表格为CSV文件
            df.to_csv(table_name, index=False, encoding='UTF-8')
            tweet_table.append(os.path.basename(table_name))

        return tweet_table

    except Exception as e:
        logging.info(f'表格提取错误: {e}')
        return []


def parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, tweet_img_url, html_content,
               dt="America/New_York", split_func=split_string, translate=True, max_length=4800,
               _translatetext=translatetext, convert_traditional=False):
    """
    统一的新闻文章数据处理和翻译函数

    这是整个爬虫系统的核心函数，负责处理从各个网站提取的原始数据，
    包括文本清理、时间格式化、翻译处理、图片提取等功能。

    Args:
        item (UyproItem): Scrapy数据项对象，用于存储处理后的数据
        article_title (str): 文章标题（原始语言）
        article_content (str): 文章内容（原始语言）
        tweet_author (str): 文章作者
        tweet_createtime (str): 文章发布时间
        tweet_img_url (list): 图片URL列表
        html_content (str): 原始HTML内容
        dt (str): 时区设置，默认为"America/New_York"
        split_func (function): 文本分割函数，默认为split_string
        translate (bool): 是否进行翻译，默认为True
        max_length (int): 翻译文本的最大长度，默认为4800字符
        _translatetext (function): 翻译函数，默认为translatetext
        convert_traditional (bool): 是否转换繁体中文为简体，默认为False

    Returns:
        UyproItem: 处理完成的数据项，包含原始内容和翻译内容
        None: 如果处理失败或内容为空

    功能说明：
        1. 文本清理：去除HTML标签、特殊字符、多余空白
        2. 时间处理：解析和格式化发布时间
        3. 翻译处理：将原始内容翻译为中文
        4. 图片处理：提取和验证图片URL
        5. 表格提取：从HTML中提取表格数据
        6. 数据验证：确保数据完整性和有效性

    Examples:
        >>> item = UyproItem()
        >>> result = parsetweet(
        ...     item,
        ...     "Breaking News",
        ...     "This is news content",
        ...     "Reporter Name",
        ...     "2024-01-15 10:30:00",
        ...     ["http://example.com/image.jpg"],
        ...     "<html>...</html>"
        ... )
        >>> print(result['tweet_title_tslt'])  # 翻译后的标题
    """
    # 初始化内容字段
    item['tweet_content'] = ''
    item['tweet_content_tslt'] = ''

    # 验证必要的输入
    if not article_title:
        return None

    # 处理标题
    _process_title(item, article_title, translate, convert_traditional, split_func, _translatetext)

    # 处理内容
    _process_content(item, article_content, translate, convert_traditional, split_func, max_length, _translatetext)

    # 处理作者信息（不再进行繁体转换）
    item['tweet_author'] = tweet_author

    # 处理时间信息
    item['tweet_createtime'] = parse_date(tweet_createtime, dt)

    # 处理图片URL（去重）
    item['tweet_img_url'] = list(set(tweet_img_url)) if tweet_img_url else []

    # 初始化其他字段
    item['tweet_video'] = ''

    # 提取表格数据
    tweet_table = _extract_tables_from_html(html_content)
    item['tweet_table'] = tweet_table if tweet_table else ''

    return item


def parsetweet_bing_new(item, article_title, article_content, tweet_author, tweet_createtime, tweet_img_url,
                        html_content, dt="America/New_York", split_func=split_string, translate=True,
                        _translatetext=translatetext):
    item['tweet_content'] = ''
    item['tweet_content_tslt'] = ''
    if article_title:
        item['tweet_title'] = article_title
        item['tweet_title_tslt'] = translatetext_bing(article_title) if translate else ''
        if translate and not item['tweet_title_tslt']:
            item['tweet_title_tslt'] = translate_text_gemini(article_title).strip()
        if translate and not item['tweet_title_tslt']:
            item['tweet_title_tslt'] = translate_text_siliconflow(article_title).strip()
        if article_content:
            article_content = replace_enter(article_content)
            item['tweet_content'] = article_content
            item['tweet_content_tslt'] = translatetext_bing(article_content, split_func=split_func) if translate else ''
            if translate and not item['tweet_content_tslt']:
                item['tweet_content_tslt'] = translate_text_gemini(article_content).strip()
            if translate and not item['tweet_content_tslt']:
                item['tweet_content_tslt'] = translate_text_siliconflow(article_content).strip()
        item['tweet_author'] = tweet_author
        item['tweet_createtime'] = parse_date(tweet_createtime, dt)
        item['tweet_img_url'] = list(set(tweet_img_url))
        item['tweet_video'] = ''
        item['tweet_table'] = ''
        if '<table' in html_content:
            try:
                tables = pd.read_html(html_content)
                tweet_table = []
                for i, df in enumerate(tables):
                    if df.shape[0] <= 1:
                        continue
                    table_name = os.path.join(f'{file_dir}/csv', f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                    directory = os.path.dirname(table_name)
                    if not os.path.exists(directory):
                        os.makedirs(directory)
                    df.to_csv(table_name, index=False, encoding='UTF-8')
                    tweet_table.append(os.path.basename(table_name))
                if tweet_table:
                    item['tweet_table'] = tweet_table
            except Exception as e:
                logging.info(f'get table error : {e}')
        return item
    else:
        return None


def parsetweet_ug(item, article_title, article_content, tweet_author, tweet_createtime, tweet_img_url, html_content,
                  dt="America/New_York", split_func=split_string, translate=True, _translatetext=translatetext):
    item['tweet_content'] = ''
    item['tweet_content_tslt'] = ''
    if article_title:
        item['tweet_title'] = article_title
        item['tweet_title_tslt'] = translate_text_gemini(article_title).strip() if translate else ''
        if translate and not item['tweet_title_tslt']:
            item['tweet_title_tslt'] = translate_text_siliconflow(article_title).strip()
        if translate and not item['tweet_title_tslt']:
            item['tweet_title_tslt'] = translatetext_bing(article_title, split_func=split_func)
        if article_content:
            article_content = replace_enter(article_content)
            item['tweet_content'] = article_content
            item['tweet_content_tslt'] = translate_text_gemini(article_content).strip() if translate else ''
            if translate and not item['tweet_content_tslt']:
                item['tweet_content_tslt'] = translate_text_siliconflow(article_content).strip()
            if translate and not item['tweet_content_tslt']:
                item['tweet_content_tslt'] = translatetext_bing(article_content, split_func=split_func)
        item['tweet_author'] = tweet_author
        item['tweet_createtime'] = parse_date(tweet_createtime, dt)
        item['tweet_img_url'] = list(set(tweet_img_url))
        item['tweet_video'] = ''
        item['tweet_table'] = ''
        if '<table' in html_content:
            try:
                tables = pd.read_html(html_content)
                tweet_table = []
                for i, df in enumerate(tables):
                    if df.shape[0] <= 1:
                        continue
                    table_name = os.path.join(f'{file_dir}/csv', f'{hashlib.sha1(to_bytes(str(df))).hexdigest()}.csv')
                    directory = os.path.dirname(table_name)
                    if not os.path.exists(directory):
                        os.makedirs(directory)
                    df.to_csv(table_name, index=False, encoding='UTF-8')
                    tweet_table.append(os.path.basename(table_name))
                if tweet_table:
                    item['tweet_table'] = tweet_table
            except Exception as e:
                logging.info(f'get table error : {e}')
        return item
    else:
        return None


def parse_tweet_rfa(response, item, translate=True):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    script_data = response.xpath("//script[@type='application/ld+json']/text()").get()
    if script_data:
        jsontext = json.loads(script_data)
        article_content = response.xpath("string(//div[@id='storytext'])").get('').strip()
        if not article_content:
            script_text = response.xpath('//script[@id="fusion-metadata"]').re_first(
                r'Fusion\.globalContent\s*=\s*(\{.*?\});')
            if script_text:
                try:
                    global_content = json.loads(script_text)
                except Exception as e:
                    logging.error(f"json.loads error: {e}")
                else:
                    text_contents = [elem.get("content", "") for elem in global_content.get(
                        "content_elements", []) if elem.get("type") == "text"]
                    article_content = BeautifulSoup('\n'.join(text_contents), 'lxml').get_text()
            else:
                logging.info("Fusion.globalContent not found")
        tweet_author = jsontext.get('author', '').strip() if isinstance(jsontext.get(
            'author', ''), str) else ','.join([author.get('name', '') for author in jsontext.get('author', [])])
        tweet_author = tweet_author.replace('记者：', '').replace('for RFA Uyghur', '').strip()
        tweet_createtime = jsontext.get('datePublished', '').strip()
        tweet_createtime = tweet_createtime if tweet_createtime else response.xpath(
            "string(//span[@id='story_date'])").get('').strip()
        img_url = response.xpath(
            "//meta[@property='og:image']/@content|//div[@id='storytext']/figure/img[@alt]/@src").getall()
        html_content = response.xpath("//div[@id='storytext']").get('')
    else:
        ps = response.xpath("//article[@class='b-article-body']//node()[self::p or self::ol]")
        article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
        tweet_author = response.xpath(
            "string(//div[@class='c-attribution b-byline']/span[@class='b-byline__names'])").get(
            '').replace('记者：', '').replace('for RFA Uyghur', '').strip()
        tweet_createtime = response.xpath("string(//time[contains(@class,'date')]/@datetime)").get('').strip()
        img_url = response.xpath(
            "//meta[@property='og:image']/@content|//article[@class='b-article-body']/figure/img/@src").getall()
        html_content = response.xpath("//article[@class='b-article-body']").get('')
    return parsetweet_ug(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                         translate=translate)


def parse_tweet_foxnews(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[@class='article-content']/div[@class='article-body']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='dc.creator']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//span[@class='article-date']/time)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='article-content']/div[@class='article-body']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_bbc(response, item):
    if 'bbc.com/zhongwen/' in response.url:
        article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[
            0].strip()
        ps = response.xpath("//main//div[@dir='ltr']/node()[self::p or self::h2]")
        article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
        tweet_author = response.xpath("string(//li[@class='bbc-1a3w4ok euvj3t11'])").get('').strip()
        tweet_createtime = response.xpath("string(//meta[@name='article:published_time']/@content)").get('').strip()
        img_url = response.xpath("//main/figure/div/picture/img/@src").getall()
        html_content = response.xpath("//main").get('')
        return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                          translate=False)
    else:
        article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
        ps = response.xpath("//main[@id='main-content']/article/div[@data-component='text-block']//p")
        article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
        tweet_author = response.xpath("string(//div[contains(@class,'TextContributorName')])").get('').replace(
            'By ', '').strip()
        tweet_createtime = response.xpath("string(//main[@id='main-content']/article/header//time)").get('').strip()
        img_url = response.xpath("//meta[@property='og:image']/@content").getall()
        html_content = response.xpath("//main[@id='main-content']/article").get('')
        return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_nytimes(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//article[@id='story']/section[@name='articleBody']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='byl']/@content)").get('').replace('By ', '').strip()
    tweet_createtime = response.xpath("string(//meta[@name='pdate']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//article[@id='story']/section[@name='articleBody']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_washingtonpost(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[@class='teaser-content grid-center']//p|//div[@class='article-body']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = ','.join(response.xpath("//header//span[@data-qa='author-name']/text()").getall())
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='teaser-content grid-center']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_washingtontimes(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[@class='storyareawrapper']/div/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("//meta[@name='Author']/@content").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@name='cXenseParse:publishtime']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='storyareawrapper']/div").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_vox(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//main[@id='content']/article//div[contains(@class,'c-entry-content')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("//meta[@property='author']/@content").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//main[@id='content']/article//div[contains(@class,'c-entry-content')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_bushcenter(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='article__content-wysiwyg']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//div[@class='meta']/div[@class='name styles__bold color__navy'])").get(
        '').strip()
    tweet_createtime = response.xpath("string(//div[@class='article__header-content']//time/@datetime)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='article__content-wysiwyg']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_cardrates(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='content']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("//meta[@name='author']/@content").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@class='content']//img/@src").getall()
    html_content = response.xpath("//div[@class='content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_haaretz(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@data-test='articleBody']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("//meta[@name='author']/@content").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='publishDate']/@content").get('').strip()
    img_url = response.xpath(
        "//meta[@property='og:image']/@content|//div[@data-test='articleBody']/figure//img/@src").getall()
    html_content = response.xpath("//div[@data-test='articleBody']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_hrw(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'article-body')]//node()[self::p or self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath(
        "string(//meta[@name='citation_author']/@content|//div[@class='byline__name flex']/a/span)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'article-body')]").get('')
    translate = False if 'zh-hans' in response.url else True
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=translate)


def parse_tweet_newsweek(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'article-body')]//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//span[@class='author']/a[@class='author-name'])").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'article-body')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_usatoday(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='gnt_ar_b']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@property='article:author']/@content)").get('').strip()
    tweet_createtime = next(iter(response.xpath('//script').re(r'"contentDatePublished":\s*"([^"]+)"')), '').strip()
    imgurls = response.xpath("//div[@class='gnt_ar_b']/figure//img/@data-gl-src").getall()
    img_url = [urljoin('https://www.usatoday.com/', imgurl) for imgurl in imgurls if imgurl.strip()]
    html_content = response.xpath("//div[@class='gnt_ar_b']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_theguardian(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@id='maincontent']/div//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@property='article:author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@id='maincontent']/div").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_axios(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@data-vars-category='story']//div[contains(@class,"
                        "'DraftjsBlocks_draftjs')]/p|//div[@data-vars-category='story']//div[contains(@class,"
                        "'DraftjsBlocks_draftjs')]/ul/li")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@name='date']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath(
        "//div[@data-vars-category='story']//div[contains(@class,'DraftjsBlocks_draftjs')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_economist(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//main[@id='content']//section[contains(@data-body-id,'cp')]/div/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//time/@datetime)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//main[@id='content']//section[contains(@data-body-id,'cp')]/div").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_bitterwinter(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//main[@id='genesis-content']/article/div/p|//main[@id='genesis-content']/article/div/h2")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//span[@class='entry-author-name'])").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content|//main["
                             "@id='genesis-content']/article/div/figure//img/@src").getall()
    html_content = response.xpath("//main[@id='genesis-content']/article/div").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_chinadigitaltimes(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='post-content entry-content']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='post-content entry-content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_delano(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//p[@class='article-introduction']|//div[@class='article-content']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//p[@class='article-author__written-by'])").get('').split('Written by')[
        -1].strip()
    tweet_createtime = response.xpath("string(//p[contains(text(),'Published on ')])").get('').split(
        'Published on')[-1].split('•')[0].strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='article-content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_thechinaproject(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get(
        '').rsplit('– The China Project', 1)[0].strip()
    ps = response.xpath("//div[@class='row']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='uncontainer post__content-wrap']/div[@class='row']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_thehill(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'article__text')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='dcterms.creator']/@content)").get(
        '').split(', opinion contributor')[0].strip()
    tweet_createtime = response.xpath("//meta[@name='dcterms.date']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'article__text')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_foreignpolicy(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//article[@class='article']//div[contains(@class,'content-gated--main-article')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@property='article:author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@name='parsely-pub-date']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath(
        "//article[@class='article']//div[contains(@class,'content-gated--main-article')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_cnn(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='article__content']/p|//div[@id='app']/main/article/div[@class='wrapP']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='article__content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_victimsofcommunism(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'page-content')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//ul[@class='meta-bar']/li[3])").get('').strip()
    tweet_createtime = response.xpath("string(//ul[@class='meta-bar']/li[1])").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'page-content')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_xinjiangpolicefiles(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='elementor-widget-container']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = ''
    tweet_createtime = ''
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='elementor-widget-container']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_cbc(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='story']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//div[@class='bylineDetails']/span[@class='authorText'])").get('').strip()
    tweet_createtime = response.xpath("//script").re_first(r'"publishedAtVerbal":"([^"]+)"').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='story']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_rollingstone(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='pmc-paywall']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@class='pmc-paywall']/div//img/@src").getall()
    html_content = response.xpath("//div[@class='pmc-paywall']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_dailyutahchronicle(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@id='sno-story-body-content']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath(
        "//meta[@property='og:image']/@content|//div[@id='sno-story-body-content']/figure//img/@src").getall()
    html_content = response.xpath("//div[@id='sno-story-body-content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_theepochtimes(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@id='post_content']/p|//div[@id='post_content']/div[@class='my-5']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps])
    tweet_author = response.xpath("//script").re_first(r'"name":"(.*?)"').strip()
    tweet_createtime = response.xpath("//script").re_first(r'"datePublished":"([^"]+)"', '').strip()
    imgurls = response.xpath(
        "//meta[@property='og:image']/@content|//div[@id='post_content']/div/figure/img/@src").getall()
    img_url = [urljoin('https://www.theepochtimes.com/', imgurl) for imgurl in imgurls if imgurl.strip()]
    html_content = response.xpath("//div[@id='post_content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_kabulnow(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//main/article/div[contains(@class,'entry-content-wrap')]//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//main/article/div[contains(@class,'entry-content-wrap')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_dawn(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//article//div[contains(@class,'story__content')]/node()[self::p or self::h2 or self::h3]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published_time']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//article//div[contains(@class,'story__content')]").get('')
    return parsetweet_bing_new(item, article_title, article_content, tweet_author, tweet_createtime, img_url,
                               html_content)


def parse_tweet_aninewsin(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//article/div[@class='content count-br']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//meta[@property='article:published']/@content").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//article/div[@class='content count-br']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_afintl(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//article/div[contains(@class,'article__content')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//main//amp-timeago/time/@datetime)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//article/div[contains(@class,'article__content')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      'Asia/Kabul')


def parse_tweet_avapress(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@id='doctextarea']|//div[@id='docDivLead1']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    article_content = re.sub(r'\$\((document|window)\)\.ready\(function\(\)\{.*?\}\);', '', article_content,
                             flags=re.DOTALL)
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@name='dcterms.modified']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@id='doctextarea']|//div[@id='docDivLead1']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_khaama(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('- Khaama Press', 1)[
        0].strip()
    ps = response.xpath("//div[@class='wpb_wrapper']/div/div[@class='tdb-block-inner td-fix-index']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//div[@class='tdb-author-name-wrap']/a[@class='tdb-author-name'])").get(
        '').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='wpb_wrapper']/div/div[@class='tdb-block-inner td-fix-index']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_arynewstv(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='tdb-block-inner td-fix-index']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='tdb-block-inner td-fix-index']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_pakistantoday(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'tdb_single_content')]//div[@class='tdb-block-inner td-fix-index']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//a[@class='tdb-author-name'])").get('').strip()
    tweet_createtime = response.xpath("string(//div[@class='tdb-block-inner td-fix-index']/time/@datetime)").get(
        '').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='tdb-block-inner td-fix-index']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_pakobserver(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit(
        '- Pakistan Observer', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'content-inner')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'content-inner')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_ptvnewsph(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='tdb-block-inner td-fix-index']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='tdb-block-inner td-fix-index']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_cninformkz(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='article__body-text']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@name='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='article__body-text']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_rusputnikkz(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='article__body']/div[@class='article__block']/div[@class='article__text']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@name='analytics:p_ts']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='article__body']/div[@class='article__block']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_uyghurj(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[@id='contents']//div[@class='post clearfix']/node()[self::p or self::h4]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@name='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@id='contents']//div[@class='post clearfix']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      max_length=900)


def parse_tweet_24kg(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[
        0].strip().strip('-').strip()
    ps = response.xpath("//div[@class='cont']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='cont']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_riaru(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath(
        "//div[contains(@class,'article__body')]/div[@class='article__block']/div[@class='article__text']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@property='article:author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'article__body')]/div[@class='article__block']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_dzenru(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='mg-snippets-group']/div[@class='mg-snippets-group__body']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@property='article:author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='mg-snippets-group']/div[@class='mg-snippets-group__body']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_kaktusmedia(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='Article--text']/div[@class='BbCode']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//div[@class='Article--info']/a[@class='Article--author'])").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='og:updated_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='Article--text']/div[@class='BbCode']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_vlastkz(response, item):
    article_title = \
        response.xpath("string(//ol[@class='breadcrumb']/li[@class='has-title']/h1[@class='title'])").get('').rsplit(
            '|', 1)[0].strip()
    ps = response.xpath("//div[@class='default-item-desc']/p|//div[contains(@class,'default-item-in js-editor')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//time[@class='news-date js-date-long']/@datetime)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'default-item-in js-editor')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_totalkz(response, item):
    article_title = response.xpath("string(//meta[@name='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='article__post__body']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//script").re_first(r'"datePublished": "([^"]+)"', '').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='article__post__body']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_informburokz(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//h3[@class='article-excerpt']|//div[@class='article']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='article']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      'Europe/Moscow')


def parse_tweet_centralasianews(response, item):
    article_title = \
        response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('» Новости Центральной Азии', 1)[
            0].strip()
    ps = response.xpath("//div[@class='s-4__kz-main-content']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//div[@class='kz-main-aside-date']/span)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='s-4__kz-main-content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_spotuz(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath(
        "//div[@class='articleContent']/div[@id='redactor']//p|//div[@class='articleContent']/div[@id='redactor']/h3")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='articleContent']/div[@id='redactor']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_freedomhouseorg(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'paragraph--type--text')]//div[contains(@class,"
                        "'field--name-field-text')]//node()[self::p or self::h2 or self::h3 or self::h4 or self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//script").re_first(r'"datePublished": "([^"]+)"', '').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'paragraph--type--text')]//div[contains(@class,"
                                  "'field--name-field-text')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_turkistantimes(response, item, lang='ar'):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath(
        "//div[@class='post-text']//node()[self::p or self::h4 or self::h2]|//div[@class='post-text']//div["
        "@dir='auto' or @data-testid or @class='newsentry']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//div[@class='published']/span[@class='date']/time/@datetime)").get(
        '').strip()
    img_url = response.xpath("//div[@class='post-image']/img[@class='img-fluid']/@src").getall()
    html_content = response.xpath("//div[@class='post-text']").get('')
    max_length = 4500 if lang == 'en' else 900
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      max_length=max_length, dt="Asia/Urumqi")


def parse_tweet_amnestyusa(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[@class='content-wrapper']/article/div[contains(@class,'wp-block-post-content')]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//script").re_first(r'"datePublished":\s*"([^"]+)"', '').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath(
        "//div[@class='content-wrapper']/article/div[contains(@class,'wp-block-post-content')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_mshulbacbe(response, item):
    article_title = response.xpath("string(//div[@class='text__inner']/h1[@class='detail__title'])").get('').strip()
    ps = response.xpath("//div[@class='detail__content body']/node()")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//div[@class='text__inner']/time[@class='publication-date']/@datetime|"
                                      "//div[@class='text__inner']/h2[@class='detail__time'])").get('').strip()
    if any(word in tweet_createtime for word in ["From", "Le", "Du"]):
        tweet_createtime = extract_first_date(tweet_createtime)
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='detail__content body']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_remotexuar(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@id='events-details-page-root']//section//div[@class='hkRpBl ZZw42R']/node()")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("//script").re_first(r'"startDate":\s*"([^"]+)"').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@id='events-details-page-root']//section//div[@class='hkRpBl ZZw42R']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_udtsb(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='detayalan']/div[@class='container']//node()[self::p or self::h5]|//div["
                        "@class='detayalan']/div[@class='container']//div[@dir='auto']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = convert_turkish_date_to_datetime_short(
        response.xpath("string(//div[@class='anabaslik']/div[@class='container']//div[@class='tarih']/p)").get(
            '').strip())
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='detayalan']/div[@class='container']").get('')
    tweet_lang = detect_language(article_content) if article_content else detect_language(
        article_title)
    if tweet_lang == 'ug':
        return parsetweet_bing_new(item, article_title, article_content, tweet_author, tweet_createtime, img_url,
                                   html_content, 'Europe/Istanbul')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      'Europe/Istanbul')


def parse_tweet_farsnewsir(response, item):
    article_title = response.xpath("string(/html/head/title)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//main/div[@class='container']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath(
        "string(//div[@class='container']/div[@class='row pt-3']//div/span[@class='time'])").get('').strip()
    img_url = response.xpath("//div[@class='img-title mt-3']/img/@src").getall()
    html_content = response.xpath("//main/div[@class='container']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_daijiworld(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//span[@id='Desc']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//div[@class='title-post']/ul[@class='post-tags']/li/span)").get(
        '').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//span[@id='Desc']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      'Asia/Kolkata')


def parse_tweet_southasiantribune(response, item):
    article_title = response.xpath("string(/html/head/title)").get('').rsplit('– SOUTH ASIAN TRIBUNE', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'single-post-contents')]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'single-post-contents')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_scrippsnews(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@id='story-transcript']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='parsely-author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@name='parsely-pub-date']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@id='story-transcript']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_zrumbeshold(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='blog-post-content']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath(
        "string(//div[@class='blog-list-left']/div[@class='blog-title-box mt-3']/span[1])").get('').replace(' ',
                                                                                                            '').strip()
    parts = tweet_createtime.split('/')
    tweet_createtime = f"{parts[1]}/{parts[0]}/{parts[2]}"
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='blog-post-content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_zrumbeshnew(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit(
        '- Zrumbesh English', 1)[0].strip()
    ps = response.xpath("//article/div[@class='entry-content']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//footer[@class='author-bio-section']/p[@class='author-name'])").get('')
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//article/div[@class='entry-content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_habernida(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    ps = response.xpath("//h2[contains(@class,'post-excerpt')]|"
                        "//article/div[contains(@class,'entry-content')]/node()[self::p or self::h4]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("string(//meta[@property='og:image']/@content)").getall()
    html_content = response.xpath("//article/div[contains(@class,'entry-content')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_hizbuttahrir(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[contains(@class,'itemFullText')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//div[@class='row-fluid']/div[@class='span12']/table//tr[2]/td[1]/b/span|"
                                      "//li[@class='itemDate']/time[@datetime]/"
                                      "@datetime)").get('').split(',')[-1].strip()
    img_url = response.xpath("string(//meta[@property='og:image']/@content)").getall()
    html_content = response.xpath("//div[contains(@class,'itemFullText')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      split_func=split_mixed_text)


def parse_tweet_votorg(response, item, translate=True):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    ps = response.xpath("//div[starts-with(@data-td-block-uid, 'tdi_')]/div[@class='tdb-block-inner td-fix-index']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath(
        "//meta[@property='og:image']/@content|//div[starts-with(@data-td-block-uid, 'tdi_')]/"
        "div[@class='tdb-block-inner td-fix-index']/figure/img/@src").getall()
    html_content = response.xpath(
        "//div[starts-with(@data-td-block-uid, 'tdi_')]/div[@class='tdb-block-inner td-fix-index']").get('')
    return parsetweet_bo(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                         translate=translate)


def parse_tweet_ceccgov(response, item, translate=True):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    article_content = response.xpath("string(//div[contains(@class,'content')]/article)").get('').strip()
    tweet_author = ''
    tweet_createtime = ''
    img_url = []
    img_pdf = response.xpath(
        "//div[contains(@class,'content')]/article//div[@class='field__item']//a/@href").getall()
    img_pdf = [response.urljoin(url) for url in img_pdf if url and url.endswith('.pdf')] if img_pdf else []
    html_content = response.xpath("//div[contains(@class,'content')]/article").get('')
    return parsetweet_pdf(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                          split_func=split_mixed_text, translate=translate, tweet_pdf_url=img_pdf)


def parse_tweet_mofagovtw(response, item, translate=False):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[@class='essay']/div[@class='p']/p|//ul/li[@class='is-img']/p")
    article_content = '\n'.join(
        [p.xpath('string(.)').get('').replace('\r', '').replace('\xa0', ' ').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = \
        response.xpath("string(//div[@class='list-text detail']//ul/li/span[contains(., '發布時間')]/text())").get(
            '').split("：")[-1].strip()
    img_url = response.xpath("//div[@class='list-pic pic-download']//ul/li[@class='is-img']/span/a/@href").getall()
    html_content = response.xpath("//div[@class='essay']/div[@class='p']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=translate, dt="Asia/Taipei", convert_traditional=True)


def parse_tweet_cnacomtw(response, item, translate=False):
    article_title = response.xpath("string(//div[@class='centralContent']/h1)").get('').strip()
    ps = response.xpath("//div[@class='centralContent']/div[@class='paragraph'][1]/p|//div["
                        "@class='centralContent']/div[@class='fullPic']//figcaption[@class='picinfo']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//div[@class='centralContent']/div[@class='fullPic']//img/@src").getall()
    html_content = response.xpath("//div[@class='centralContent']/div[@class='paragraph'][1]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=translate, dt="Asia/Taipei", convert_traditional=True)


def parse_tweet_tibetanreview(response, item, translate=True):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'vc_column')]/div[@class='wpb_wrapper']/div/div["
                        "@class='tdb-block-inner td-fix-index']/p|//article[@id]//div[@class='td-post-content "
                        "tagdiv-type']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@class='td-post-content "
                             "tagdiv-type']/figure/a/img/@src").getall()
    html_content = response.xpath("//div[@class='vc_column-inner']/div[@class='wpb_wrapper']/div/div["
                                  "@class='tdb-block-inner td-fix-index']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=translate)


def parse_tweet_chinesealjazeera(response, item, translate=False):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath(
        "//main[@id='main-content-area']/div[contains(@class,'wysiwyg')]/"
        "node()[self::p or self::h3 or self::ul or self::ol]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@name='publishedDate']/@content)").get('').strip()
    img_url = response.xpath("//figure//img/@src").getall()
    img_url = [response.urljoin(url) for url in img_url if url] if img_url else []
    html_content = response.xpath("//main[@id='main-content-area']/div[contains(@class,'wysiwyg')]").get('')
    if 'liveblog' in response.url:
        post_id = response.xpath('//meta[@name="postID"]/@content').get()
        base64_string = response.xpath('//script').re_first(r'window\.__APOLLO_STATE__\s*=\s*"(.*?)"')
        if base64_string:
            json_data = base64.b64decode(base64_string).decode()
            try:
                json_object = json.loads(json_data)
                content_value = json_object.get(f"Post:{post_id}", {}).get("content", '')
                tree = html.fromstring(content_value)
                article_content = tree.xpath('string(.)').strip()
                new_img_url = tree.xpath('//img/@src')
                new_img_url = [response.urljoin(url) for url in new_img_url if url] if new_img_url else []
                img_url += new_img_url
            except json.JSONDecodeError:
                logging.error("Failed to decode JSON.")
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      dt="UTC", translate=translate)


def parse_tweet_thekhorasandiary(response, item):
    article_title = response.xpath("string(//div[@class='article-v2']/h2[@class='title'])").get('').strip()
    article_title = article_title if article_title else response.xpath(
        "string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[@class='contents']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ','.join(
        response.xpath("//div[@class='opinions-authors-list']//p[@class='descriptions']/text()").getall()).strip()
    tweet_createtime = response.xpath("string(//meta[@name='og:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='contents']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_voachinese(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[@class='wsw']//p|//div[@class='intro m-t-md']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='Author']/@content)").get('').strip()
    tweet_author = tweet_author if tweet_author != '美国之音' else ''
    tweet_createtime = response.xpath("string(//div[@class='hdr-container']//span[@class='date']/time/@datetime)").get(
        '').strip()
    img_url = response.xpath(
        "//meta[@property='og:image']/@content|//div[@class='wsw']/div/figure//div/img/@src").getall()
    html_content = response.xpath("//div[@class='wsw']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False)


def parse_tweet_zaobao(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//article[@id='article-body']/p|//div[@class='article-content-rawhtml']/p|//div[contains("
                        "@class,'articleBody')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("//script").re_first(r'"datePublished"\s*:\s*"([^"]+)"', '').strip()
    tweet_createtime = tweet_createtime if tweet_createtime else response.xpath(
        "//script").re_first(r'"created"\s*:\s*"([^"]+)"').strip()
    img_url = response.xpath(
        "//div[@class='figure-media']/img/@data-src|//div[@class='fluid-iframe']/img/@src").getall()
    img_url_sg = response.xpath("//script").re_first(r'"thumbnailUrl"\s*:\s*"([^"]+)"', '').strip()
    if img_url_sg:
        img_url.append(img_url_sg)
    html_content = response.xpath("//article[@id='article-body']|//div[@class='article-content-rawhtml']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, dt="Asia/Taipei")


def parse_tweet_xizangzhiye(response, item):
    article_title = response.xpath("string(//meta[@itemprop='name']/@content)").get('').strip()
    ps = response.xpath("//div[@class='w-post-elm post_content']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).replace(
        '《西藏之页》首发，转载请注明出处', '').strip()
    tweet_author = response.xpath("string(//div[@class='w-post-elm post_content']/p/strong[contains(text(),"
                                  "'记者')]/following-sibling::text()[1])").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//div[@class='w-post-elm post_content']//figure[@id]/img/@srcset|//div["
                             "@class='w-post-elm post_content']//p/img/@srcset").getall()
    img_url = [srcset.split(",")[-1].strip().split()[0] for srcset in img_url]
    html_content = response.xpath("//div[@class='w-post-elm post_content']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False)


def parse_tweet_scmp(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//div[contains(@data-qa,'Article-Content')]/section/node()[@data-qa='Component-Component']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='cXenseParse:author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//div[@data-qa='ArticleImage-ImageContainer']//img/@src").getall()
    html_content = response.xpath("//div[contains(@data-qa,'Article-Content')]/section").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_defensenews(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    ps = response.xpath("//article[contains(@class,'articleBody')]/node()[self::p or self::ul]|//div["
                        "@id='fusion-app']/div[@class=' t-base']/section/article//h6")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ','.join(response.xpath("//meta[@name='author']/@content").getall()).strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//article[contains(@class,'articleBody')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_airandspaceforces(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath(
        "//div[@class='post-body']/node()[self::p or self::ul]|//div[@class='post-body "
        "post-with-banner']/div/div/node()[self::p or self::h2]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ','.join(response.xpath("//meta[@name='author']/@content").getall()).strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='post-body']|//div[@class='post-body post-with-banner']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_defltncomtw(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    ps = response.xpath("//div[contains(@class,'article')]/div[contains(@class,'text')]/p[not(@class)]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@class,'article')]/div[contains(@class,'text')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, convert_traditional=True)


def parse_tweet_breakingdefense(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    ps = response.xpath("//div[@id]/div[@class='entry']/node()[self::p or self::h2]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//div[@id]/div[@class='entry']/div/img/@src").getall()
    html_content = response.xpath("//div[@id]/div[@class='entry']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_newsusniorg(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    ps = response.xpath(
        "//article//div[contains(@class,'entry-content')]/node()[self::p or self::ul or self::h2 or self::h3]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).replace(
        'Download the document here.', '').strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//article//div[contains(@class,'entry-content')]/figure/img/@src").getall()
    html_content = response.xpath("//article//div[contains(@class,'entry-content')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_newsltncomtw(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].replace(
        '- 政治', '').strip()
    ps = response.xpath("//div[contains(@itemprop,'articleBody')]//div[contains(@class,'text')]/p[not(@class)]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ps.re_first(r'記者([a-zA-Z\u4e00-\u9fa5\s]+)／', '')
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[contains(@itemprop,'articleBody')]/div[contains(@class,'text')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, convert_traditional=True)


def parse_tweet_myformosa(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit(':', 1)[0].strip()
    ps = response.xpath("//div[@class='row-fluid']/div[@class='item']/div[@class='Bigcontent']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = response.xpath("string(//div[@class='span12']/div[@class='news-item']/article/h4)").get('').strip()
    tweet_createtime = response.xpath("string(//div[@class='pull-right']/small[@class='date'])").get('').strip()
    imgurls = response.xpath("//meta[@property='og:image']/@content|//div[@class='row-fluid']/div["
                             "@class='item']/figure/img/@src").getall()
    img_url = [urljoin('http://my-formosa.com/', imgurl) for imgurl in imgurls if imgurl.strip()]
    html_content = response.xpath("//div[@class='row-fluid']/div[@class='item']/div[@class='Bigcontent']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, dt="Asia/Taipei")


def parse_tweet_new7stormmg(section, item):
    article_title = section.get('article_title', '')
    html_content = section.get('article_premium_content', '')
    html_content = html_content if html_content else section.get('article_content', '')
    article_content = BeautifulSoup(html_content, 'html.parser').get_text()
    tweet_author = ','.join(section.get('article_authors', []))
    tweet_createtime = section.get('article_date_publish', '')
    article_image_origin = section.get('article_image_origin', '')
    img_url = [(f'https://image.storm.mg/cloud?resize=fill&g=ce&url={article_image_origin}&w=800&h=533&wm_position=soea'
                f'&wm_opacity=1&wm_x=14&wm_y=14&wm_scale=0.18&&wmu=https://image.cache.storm.mg/logo/logo_white.svg')]
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, convert_traditional=True)


def parse_tweet_taiwanreports(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').replace(
        '- 臺灣導報-臺灣導報.', '').replace('- 臺灣導報', '').strip()
    ps = response.xpath("//main//article//div[contains(@class,'entry-content')]/node()[self::p or self::section]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    if not article_content:
        ps = response.xpath("//main//article//div[contains(@class,'entry-content')]/div[not(@class)]")
        article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    if not article_content:
        ps = response.xpath("//main//article//div[contains(@class,'entry-content')]//p")
        article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content|//main//article//div[contains(@class,"
                             "'entry-content')]/p/img/@src").getall()
    html_content = response.xpath("//main//article//div[contains(@class,'entry-content')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, convert_traditional=True)


def parse_tweet_icdforgtw(response, item):
    article_title = response.xpath("string(/html/head/title)").get('').replace('財團法人國際合作發展基金會 -',
                                                                               '').strip()
    ps = response.xpath("//div[@id='center']//section[@class='cp']/div/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//ul[@class='publish_info']/li[contains(text(),'更新日期:')])").get(
        '').replace('更新日期:', '').strip()
    imgurls = response.xpath("//div[@class='lightbox_slider_block']//a/@href").getall()
    img_url = [urljoin('https://www.icdf.org.tw/wSite/', imgurl) for imgurl in imgurls if imgurl.strip()]
    html_content = response.xpath("//div[@id='center']//section[@class='cp']/div").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, dt="Asia/Taipei", convert_traditional=True)


def parse_tweet_ftvnewscomtw(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    ps = response.xpath("//div[@id='preface']|//div[@id='newscontent']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).rsplit('更多新聞：', 1)[
        0].strip()
    tweet_author = \
        response.xpath("//script").re_first(r'ArticleAuthor\'\s*:\s*\'([\u4e00-\u9fa5a-zA-Z\s（）]+)', '').strip().split(
            '（')[0]
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@id='newscontent']/figure//img/@src").getall()
    html_content = response.xpath("//div[@id='newscontent']").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, convert_traditional=True)


def parse_tweet_enactafricaorg(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    ps = response.xpath("//div[@class='row']//article/node()[self::p or self::ul]|//div["
                        "@id='u_content_text_1']/div/node()[self::p or self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath(
        "string(//div[@class='img-container']/div[@class='text']/div[@class='date'])").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    html_content = response.xpath("//div[@class='row']//article").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_uyghurstudyorg(response, item):
    article_title = response.xpath("string(//div[@class='container']//h1)").get('').strip()
    ps = response.xpath("//div[@class='row']//div//div[contains(@class,'detail-desc')]/node()[self::p or self::div]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    tweet_author = ''
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@class='row']//div//div[contains(@class,"
                             "'detail-desc')]/p/img/@src").getall()
    html_content = response.xpath("//div[@class='row']//div//div[contains(@class,'detail-desc')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_uscirfgov(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@id='main']//div[@class='content']//div[@class='full-content']/node()[self::p or "
                        "self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='main']//div[@class='content']//div[@class='full-content']").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_thediplomat(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("//script").re_first(r'"datePublished":\s*"([^"]+)"', '').strip()
    tweet_author = response.xpath("//script").re_first(r'"@type": "Person", "name": "(.*?)"', '').strip()
    ps = response.xpath("//main/section[@id='tda-gated-body']/node()[self::p or self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//main/section[@id='tda-gated-body']").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_centcommil(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@itemprop='datePublished']/@content)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@id='news-content']/div[@class='body']/node()[self::p or self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='news-content']/div[@class='body']").get('')
    img_url = response.xpath("//div[@class='item']/div[@class='image']/img/@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_minghuiorg(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content|//div[@class='qikan']/div["
                                   "@class='title']/span[@id='lblTitle'])").get('').strip()
    article_title = remove_font_tags(article_title) if '<' in article_title else article_title
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_createtime = tweet_createtime if tweet_createtime else response.xpath(
        "string(//meta[@property='article:modified_time']/@content)").get('').strip()
    tweet_createtime = tweet_createtime if tweet_createtime else response.xpath("string(//div[@class='qikan']/div["
                                                                                "@class='htmlcontent']/div["
                                                                                "@class='publish_date']/span["
                                                                                "@id='lblPublishDate'])").get(
        '').replace('(发稿日期：', '').replace(')', '').strip()
    tweet_author = ''
    ps = response.xpath("//div[@id='ar_bArticleContent']|//div[@class='htmlcontent']/span[@id='lblHtmlCode']")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='ar_bArticleContent']").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    img_url = [i for i in img_url if i != 'https://www.minghui.org/']
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, dt="Asia/Taipei")


def parse_tweet_epochtimes(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').split('|')[0].strip()
    tweet_createtime = response.xpath("//script").re_first(r'"datePublished"\s*:\s*"([^"]+)"', '').replace('Z',
                                                                                                           '').strip()
    tweet_author = response.xpath("//script").re_first(r"djy_public_authors\s*=\s*'([^']+)'", '').split('-')[0].strip()
    ps = response.xpath("//div[@class='article']/div[@id='artbody']/node()[self::p or self::h2 or self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='article']/div[@id='artbody']").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      translate=False, dt="Asia/Taipei")


def parse_tweet_childrenofafricango(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').split('-')[0].strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    ps = response.xpath("//div[@id='page']/section//node()[self::p or self::h1]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='page']/section").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@id='page']/section//article//img/@src"
                             ).getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_trustafricaorg(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@id='main-content']//div[@class]/node()[self::p or self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='main-content']//div[@class]/p").get('')
    img_url = response.xpath(
        "//meta[@property='og:image']/@content|//div[@id='main-content']//div[@class]//figure/img/@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_developafricaorg(response, item):
    article_title = response.xpath("string(/html/head/title)").get('').rsplit('|', 1)[0].strip()
    tweet_createtime = ''
    tweet_author = ''
    ps = response.xpath("//div[@id='page-main-content']//article//div/node()[self::p or self::h6]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='page-main-content']//article//div/p").get('')
    imgurls = response.xpath("//li/div[@class='item-image']/img/@src").getall()
    img_url = [urljoin('https://www.developafrica.org/', imgurl) for imgurl in imgurls if imgurl.strip()]
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_africahumanitarianorg(response, item):
    article_title = response.xpath("string(/html/head/title)").get('').rsplit('-', 1)[0].strip()
    tweet_createtime = response.xpath(
        "string(//span[@class='ae-element-post-date']/a[@class='ae-element-post-date'])").get('').strip()
    tweet_author = ''
    ps = response.xpath(
        "//main[@id='main']/article//div[@class='ae-element-post-content']/node()[self::p or self::h2 or self::h3]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//main[@id='main']/article//div[@class='ae-element-post-content']").get('')
    img_url = response.xpath(
        "//div[@class='elementor-inner']/div[@class='elementor-section-wrap']/section["
        "@data-ae-bg]/@data-ae-bg|//main[@id='main']/article//div["
        "@class='ae-element-post-content']/p//img/@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_phayul(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@class='elementor-widget-wrap']/div/div[@class='elementor-widget-container']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath(
        "//div[@class='elementor-widget-wrap']/div/div[@class='elementor-widget-container']").get('')
    imgurls = response.xpath("//meta[@property='og:image']/@content").getall()
    img_url = [imgurl.replace('http://', 'https://') for imgurl in imgurls if imgurl.strip()]
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_tibetanyouthcongress(response, item):
    article_title = response.xpath("string(//head/title)").get('').rsplit('–', 1)[0].strip()
    tweet_createtime = response.xpath("string(//main[@id='main']/article/header//time/@datetime)").get('').strip()
    tweet_author = response.xpath("string(//main[@id='main']/article/header//span[@class='author vcard'])").get(
        '').strip()
    ps = response.xpath("//main[@id='main']/article/div[@class='entry-content']/node()[self::p or self::div]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//main[@id='main']/article/div[@class='entry-content']").get('')
    img_url = response.xpath("//main[@id='main']/article/div[@class='entry-content']//img/@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_savetibetorg(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("//script").re_first(r'"datePublished"\s*:\s*"([^"]+)"', '').strip()
    tweet_author = ''
    ps = response.xpath(
        "//main[@id='main']/div/section[@id='content']/article/div[@class='post-content']/node()[self::p or self::h3 "
        "or self::ul]|//section[@id='content']/article/div[@class='project-content']/div/div[contains(@class,"
        "'fusion-builder-row-3')]/div[@class='fusion-builder-row fusion-row']/div[contains(@class,"
        "'fusion-builder-column-6 ')]/div/div//node()[self::p or self::em or self::h2 or self::ol or self::ul]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath(
        "//main[@id='main']/div/section[@id='content']/article/div[@class='post-content']").get('')
    img_url = response.xpath("//main[@id='main']/div/section[@id='content']/article/div["
                             "@class='post-content']//img/@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_studentsforafreetibet(response, item):
    article_title = response.xpath("string(//head/title)").get('').rsplit('–', 1)[0].strip()
    tweet_createtime = response.xpath(
        "string(//main[@class='main']/section/div[@class='col']/p[@class='small-text gray-text'])").get('').strip()
    tweet_author = ''
    ps = response.xpath(
        "//main[@class='main']/section/div[@class='col col--main-content']/node()[self::p or self::ul or self::ol]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//main[@class='main']/section/div[@class='col col--main-content']").get('')
    img_url = response.xpath("//main[@class='main']/section//@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_tibetnetworkorg(response, item):
    article_title = response.xpath("string(//head/title)").get('').rsplit('–', 1)[0].strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@id='wrapper']/section/article/div/div[contains(@class,'post-content')]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='wrapper']/section/article/div/div[contains(@class,'post-content')]").get(
        '')
    img_url = response.xpath(
        "//meta[@property='og:image']/@content|//div[@id='wrapper']/section/article/div/div[contains(@class,"
        "'post-content')]//img/@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_mfagovir(response, item):
    article_title = response.xpath("string(//head/title)").get('').split('-', 1)[-1].strip()
    tweet_createtime = response.xpath(
        "string(//div[@class='post-content']/div[@class='nv-info-bar']/div[@class='nv-info-item pull-left']/span["
        "@class='nv-info'])").get(
        '').strip()
    tweet_author = ''
    ps = response.xpath(
        "//div[@class='row']//div[@class='post-content']/div[@class='news-text-full']/node()[self::p or self::ul or "
        "self::ol or self::text() or self::h4]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='row']//div[@class='post-content']/div[@class='news-text-full']").get(
        '')
    imgurls = response.xpath(
        "//main[@class='main-content']/div[@class='container']/div[@class='row']//div["
        "@class='news-text-full']//img/@src").getall()
    img_url = [urljoin('https://mfa.gov.ir/', imgurl) for imgurl in imgurls if imgurl.strip()]
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      dt="Asia/Tehran")


# ==================== 网站专用解析函数 ====================

def _get_jpost_article_regex_patterns():
    """
    获取Jerusalem Post网站文章内容提取的正则表达式模式

    Returns:
        list: 正则表达式模式列表，按优先级排序
    """
    return [
        # 标准JSON格式 - 简单的articleBody字段
        r'"articleBody":"([^"]+)"',
        # 标准JSON格式 - 带转义字符的articleBody字段
        r'"articleBody":\s*"([^"]*(?:\\.[^"]*)*)"',
        # Next.js格式 - 嵌套在children中的转义JSON
        r'\\"articleBody\\":\s*\\"([^"]*(?:\\.[^"]*)*)\\"',
        # children字段中的JSON-LD - 复杂嵌套结构
        r'"children":\s*"[^"]*\\"articleBody\\":\s*\\"([^"]*(?:\\.[^"]*)*)\\"',
    ]


def _clean_jpost_escaped_content(content):
    """
    清理Jerusalem Post网站文章内容中的转义字符

    该函数处理从JavaScript代码中提取的文章内容，这些内容通常包含
    多重转义字符，需要逐步解码才能得到可读的文本。

    Args:
        content (str): 包含转义字符的原始内容

    Returns:
        str: 清理后的可读文本内容

    处理的转义字符类型：
        - \\\\n -> \\n -> \n (双重转义的换行符)
        - \\\\" -> \\" -> " (双重转义的引号)
        - \\/ -> / (转义的斜杠)
        - \\\\ -> \\ -> \ (双重转义的反斜杠)
        - \\xa0, \\u00a0 -> 空格 (特殊空白字符)
    """
    if not content:
        return ''

    # 按顺序处理各种转义字符，避免处理顺序导致的问题
    escape_replacements = [
        ('\\\\n', '\n'),  # 双重转义的换行符
        ('\\n', '\n'),  # 单重转义的换行符
        ('\\\\"', '"'),  # 双重转义的引号
        ('\\"', '"'),  # 单重转义的引号
        ('\\/', '/'),  # 转义的斜杠
        ('\\\\', '\\'),  # 双重转义的反斜杠
        ('\\xa0', ' '),  # 特殊空白字符
        ('\\u00a0', ' '),  # Unicode空白字符
    ]

    # 逐步替换转义字符
    for escaped, unescaped in escape_replacements:
        content = content.replace(escaped, unescaped)

    # 清理多余的空白字符，将连续空白合并为单个空格
    content = re.sub(r'\s+', ' ', content).strip()

    return content


def _extract_jpost_content_from_scripts(response):
    """
    从JavaScript代码中提取Jerusalem Post文章内容

    Jerusalem Post网站使用客户端渲染技术，文章内容通常嵌套在
    JavaScript代码的JSON-LD结构中，需要通过正则表达式提取。

    Args:
        response (HtmlResponse): Scrapy响应对象

    Returns:
        str: 提取的文章内容，如果未找到则返回空字符串

    提取策略：
        1. 遍历所有script标签
        2. 查找包含'articleBody'的脚本
        3. 使用多个正则表达式模式尝试匹配
        4. 选择最长的匹配结果（通常最完整）
        5. 清理转义字符
    """
    article_content = ''
    all_scripts = response.xpath("//script/text()").getall()
    patterns = _get_jpost_article_regex_patterns()

    for script in all_scripts:
        # 只处理包含articleBody的脚本，提高效率
        if 'articleBody' not in script:
            continue

        # 尝试所有正则表达式模式
        for pattern in patterns:
            matches = re.findall(pattern, script, re.DOTALL)
            if matches:
                # 获取第一个匹配结果
                raw_content = matches[0]

                # 清理转义字符
                cleaned_content = _clean_jpost_escaped_content(raw_content)

                # 选择最长的内容（通常最完整）
                if len(cleaned_content) > len(article_content):
                    article_content = cleaned_content

                # 找到匹配就跳出内层循环
                break

        # 如果已经找到内容，跳出外层循环
        if article_content:
            break

    return article_content


def _extract_jpost_content_from_html(response):
    """
    从HTML结构中提取Jerusalem Post文章内容（备用方法）

    当JavaScript提取失败时，尝试从HTML结构中直接提取内容。
    这种方法适用于部分静态渲染的页面或旧版页面。

    Args:
        response (HtmlResponse): Scrapy响应对象

    Returns:
        str: 提取的文章内容
    """
    # 定义可能包含文章内容的XPath选择器
    content_selectors = [
        "//section[@itemprop='articleBody']//section[contains(@class, 'article-body-paragraph')]",
        "//section[@class='blog-container']/section",
        "//section[@class='post-list-wrapper']/section[@class='post-item-wrap']"
    ]

    # 尝试所有选择器，合并结果
    all_paragraphs = []
    for selector in content_selectors:
        paragraphs = response.xpath(selector)
        all_paragraphs.extend(paragraphs)

    # 提取文本内容并合并
    article_content = '\n'.join([
        p.xpath('string(.)').get('').strip()
        for p in all_paragraphs
        if p and p.xpath('string(.)').get('').strip()
    ]).strip()

    return article_content


def _extract_jpost_basic_info(response):
    """
    提取Jerusalem Post文章的基本信息

    Args:
        response (HtmlResponse): Scrapy响应对象

    Returns:
        tuple: (article_title, tweet_createtime, tweet_author)
    """
    # 提取标题，移除网站后缀
    article_title = response.xpath(
        "string(//meta[@property='og:title']/@content)"
    ).get('').rsplit('| The Jerusalem Post', 1)[0].strip()

    # 提取发布时间，支持多种时间元素格式
    tweet_createtime = response.xpath(
        "string(//section/time/@datetime|"
        "//section[@class='post-item-content']/p[@class='post-publish-date']/time/@datetime)"
    ).get('').strip()

    # 提取作者信息，移除"By"前缀
    tweet_author = response.xpath(
        "string(//section[@class='article-info-wrap']//span[@class='reporters'])"
    ).get('').split('By', 1)[-1].strip()

    return article_title, tweet_createtime, tweet_author


def _extract_jpost_media_urls(response):
    """
    提取Jerusalem Post文章的图片URL

    Args:
        response (HtmlResponse): Scrapy响应对象

    Returns:
        tuple: (img_url_list, html_content)
    """
    # 提取图片URL，包括og:image和文章内图片
    img_url = response.xpath(
        "//meta[@property='og:image']/@content|"
        "//section[@itemprop='articleBody']/figure/img[@title]/@src"
    ).getall()

    # 提取HTML内容用于表格处理
    html_content = response.xpath("//section[@itemprop='articleBody']").get('')

    return img_url, html_content


def parse_tweet_jpost(response, item):
    """
    Jerusalem Post网站文章解析函数

    解析Jerusalem Post (jpost.com) 网站的新闻文章，提取标题、内容、
    作者、发布时间和图片等信息。该网站使用客户端渲染，需要从
    JavaScript代码中提取文章内容。

    Args:
        response (HtmlResponse): Scrapy响应对象，包含页面HTML内容
        item (UyproItem): 数据项对象，用于存储提取的数据

    Returns:
        UyproItem: 包含文章信息的数据项
        None: 如果解析失败

    提取字段：
        - article_title: 文章标题（从og:title元标签提取）
        - tweet_createtime: 发布时间（从time元素的datetime属性提取）
        - tweet_author: 作者信息（从reporters类元素提取）
        - article_content: 文章内容（从JavaScript中的articleBody提取）
        - img_url: 图片URL列表（从og:image和文章图片提取）
        - html_content: 原始HTML内容

    特殊处理：
        - 支持客户端渲染页面的内容提取
        - 处理Next.js格式的JSON-LD数据
        - 多重转义字符的清理和处理
        - 时区设置为"Asia/Jerusalem"

    网站特点：
        - 使用客户端渲染技术
        - 文章内容嵌套在JavaScript代码中
        - 支持多种内容格式（新闻、博客、专栏等）
        - 图片使用CDN服务
    """
    # 提取基本信息
    article_title, tweet_createtime, tweet_author = _extract_jpost_basic_info(response)

    # 尝试从JavaScript中提取文章内容
    article_content = _extract_jpost_content_from_scripts(response)

    # 如果JavaScript提取失败，尝试从HTML中提取
    if not article_content:
        article_content = _extract_jpost_content_from_html(response)

    # 提取媒体URL和HTML内容
    img_url, html_content = _extract_jpost_media_urls(response)

    # 使用统一的数据处理函数
    return parsetweet(
        item=item,
        article_title=article_title,
        article_content=article_content,
        tweet_author=tweet_author,
        tweet_createtime=tweet_createtime,
        tweet_img_url=img_url,
        html_content=html_content,
        dt="Asia/Jerusalem",
        _translatetext=translate_text_googleapi
    )


def parse_tweet_ptvcompk(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//div[@class='post-meta']/ul/li[2]/span[@class='rt-meta'])").get(
        '').strip()
    tweet_author = ''
    ps = response.xpath("//div[@class='container']//div/p[contains(@class, 'rt')]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='container']//div").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      dt="Asia/Karachi", _translatetext=translate_text_googleapi)


def parse_tweet_premiumtimesng(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    ps = response.xpath("//div[@class='jeg_inner_content']//div[contains(@class,'content-inner')]/node()[self::p or "
                        "self::ul or self::h2 or self::h3]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@class='jeg_inner_content']//div[contains("
                             "@class,'content-inner')]/node()[self::p or self::figure]/img/@src").getall()
    html_content = response.xpath("//div[@class='jeg_inner_content']//div[contains(@class,'content-inner')]").get('')
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_actualitecd(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@class='views-row']/div/div[@class='field-content']//node()[self::p or "
                        "self::ul or self::h2 or self::h3]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='views-row']/div/div[@class='field-content']").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@class='jeg_inner_content']//div[contains("
                             "@class,'content-inner')]/node()[self::p or self::figure]/img/@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      _translatetext=translate_text_googleapi)


def parse_tweet_govkz(_date, item, _json=None):
    _json = _json or {}
    article_title = _date.get('title', '').strip()
    tweet_createtime = _date.get('created_date', '').strip()
    tweet_author = ''
    body_content = _date.get('body', '') or _date.get('content', '') or _json.get('content', '')
    response = HtmlResponse(
        url=f"https://www.gov.kz/{_date.get('id', '')}",
        body=body_content.encode(),
        encoding='utf-8'
    )
    article_content = response.xpath("string(/html)").get('').replace('\xa0', ' ').strip()
    html_content = response.xpath("string(/html)").get('')
    img_url = [urljoin('https://www.gov.kz/', _date.get('heropic', '').strip())] if _date.get('heropic', '') else []
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      max_length=900)


def parse_tweet_mvdgovkg(_date, item):
    article_title = _date.get('title', '').strip()
    tweet_createtime = _date.get('created', '').strip()
    tweet_author = ''
    body_content = _date.get('content', '')
    response = HtmlResponse(
        url=f"https://mvd.gov.kg/news/{_date.get('id', '')}",
        body=body_content.encode(),
        encoding='utf-8'
    )
    article_content = response.xpath("string(/html)").get('').strip()
    html_content = response.xpath("string(/html)").get('')
    img_url = [img['image'] for img in _date.get('images', []) if 'image' in img]
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      dt="Asia/Bishkek", max_length=900)


def parse_tweet_gknbgovkg(response, item):
    article_title = response.xpath("string(/html/head/title)").get('').rsplit('-', 1)[0].strip()
    tweet_createtime = response.xpath("string(//li[@itemprop='datePublished']/a)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[contains(@class,'post-content')]/div")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).replace('\xa0', '').strip()
    html_content = response.xpath("//div[contains(@class,'post-content')]").get('')
    img_url = []
    return parsetweet_bing_new(item, article_title, article_content, tweet_author, tweet_createtime, img_url,
                               html_content)


def parse_tweet_govuz(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath('//script').re_first(r'\\"date\\":\\"(.*?)\\"').strip()
    tweet_author = ''
    ps = response.xpath("//div[@class='data-zoomable']/div[contains(@class,'body')]//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='article-content']/div[@class='article-text']").get('')
    imgurls = response.xpath("//div[@class='data-zoomable']//div[@class='slick-track']/div[contains(@class,"
                             "'slick-slide')]//img/@src").getall()
    img_url = [urljoin('https://gov.uz/', imgurl) for imgurl in imgurls if imgurl.strip()]
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      dt="Asia/Tashkent", _translatetext=translate_text_googleapi)


def parse_tweet_asudagovtm(response, item):
    article_title = response.xpath("string(//div[@class='entry clearfix']/div[@class='entry-title']/h2)").get(
        '').strip()
    tweet_createtime = response.xpath("string(//div[@class='entry clearfix']/ul[@class='entry-meta clearfix']/li["
                                      "1]/span)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@class='entry clearfix']/div[@class='entry-content']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='entry clearfix']/div[@class='entry-content']").get('')
    img_url = response.xpath("//div[@class='entry clearfix']//img/@src").getall()
    return parsetweet_ug(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                         dt="Asia/Ashgabat")


def parse_tweet_mvdtj(response, item):
    article_title = response.xpath("string(//main[@class='main clearfix']/article/h1)").get('').strip()
    tweet_createtime = response.xpath("string(//div[@class='main-item-date icon-l'][1])").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@id='full-text']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='full-text']").get('')
    imgurls = response.xpath("//div[@id='full-text']//a[@class='highslide']/img/@src").getall()
    img_url = [urljoin('https://www.mvd.tj/', imgurl) for imgurl in imgurls if imgurl.strip()]
    return parsetweet_ug(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                         dt="Asia/Dushanbe")


def parse_tweet_bitterwinterorg(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = response.xpath("string(//span[@class='entry-author'])").get('').strip()
    ps = response.xpath("//article[@id]/div[@class='entry-content clearfix']/node()[self::p or self::h2 or self::ul "
                        "or self::ol]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//article[@id]/div[@class='entry-content clearfix']").get('')
    img_url = response.xpath("//article[@id]/div[@class='entry-content clearfix']//figure//img/@data-src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      max_length=900)


def parse_tweet_istiqlalhaber(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//section[@class='detay_kutu']/div[@class='haberhit'][2])").get(
        '').strip()
    if len(tweet_createtime) == 19:
        try:
            tweet_createtime = datetime.strptime(tweet_createtime, "%d/%m/%Y %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
    tweet_author = ''
    ps = response.xpath("//section[@class='detay_kutu']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//section[@class='detay_kutu']").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    return parsetweet_ug(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                         dt="Asia/Urumqi")


def parse_tweet_nzzch(response, item):
    article_title = response.xpath("string(//h1[@class='headline__title'])").get('').strip()
    tweet_createtime = response.xpath("string(//meta[@name='date']/@content)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@class='article']/section//node()[self::p or self::h2 or self::ul or self::ol]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).replace(
        'NZZ.ch benötigt JavaScript für wichtige Funktionen. Ihr Browser oder Adblocker verhindert dies momentan.',
        '').replace('Bitte passen Sie die Einstellungen an.', '').strip()
    html_content = response.xpath("//div[@class='article']/section").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      _translatetext=translate_text_googleapi)


def parse_tweet_turkistanpress(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//section[@class='detay_kutu']/div[@class='haberhit'][2])").get(
        '').strip()
    if len(tweet_createtime) == 10:
        try:
            tweet_createtime = '-'.join(reversed(tweet_createtime.split('/')))
        except ValueError:
            pass
    tweet_author = response.xpath("//section[@class='detay_kutu']/p").xpath("string(.)").re_first(r'إعداد:\s*(.+)',
                                                                                                  '').strip()
    ps = response.xpath("//section[@class='detay_kutu']/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//section[@class='detay_kutu']").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      max_length=900, dt="Asia/Urumqi")


def parse_tweet_haberajandanet(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//span[@class='article-post-date'])").get('').strip()
    tweet_createtime = extract_datetime(tweet_createtime)
    tweet_author = response.xpath("string(//a[@class='author-name'])").get('').strip()
    ps = response.xpath("//div[@class='article-inner']/div[@class='article-description']|//div["
                        "@class='article-inner']/node()[self::p or self::blockquote]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='article-inner']").get('')
    imgurls = response.xpath("//div[@class='article-inner']//img/@src").getall()
    img_url = [urljoin('https://haberajandanet.com/', imgurl) for imgurl in imgurls if imgurl.strip()]
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                      max_length=900, dt="Europe/Istanbul", _translatetext=translate_text_googleapi)


def parse_tweet_presidentmn(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('-', 1)[0].strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@class='entry-content']/node()[not(self::div)]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='entry-content']").get('')
    img_url = response.xpath("//meta[@property='og:image']/@content|//div[@class='entry-content']//img/@src").getall()
    return parsetweet_ug(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content)


def parse_tweet_parliamentmn(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').strip()
    tweet_createtime = response.xpath("string(//div[contains(@class,'entry')]/div[@class='entry-meta']/ul/li/span[1])"
                                      ).get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[contains(@class,'entry-content')]/p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[contains(@class,'entry-content')]").get('')
    img_url = response.xpath("//div[contains(@class,'entry-content')]/p/img/@src").getall()
    return parsetweet_ug(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content,
                         dt="Asia/Ulaanbaatar")


def parse_tweet_smhricorg(response, item, translate=True, title=None):
    article_title = response.xpath("string(//td[@class='sh'][2]|"
                                   "//blockquote/p[@class='MsoNormal'][1]/b/u/span|"
                                   "//blockquote/p/u/b|"
                                   "//blockquote/p[3]/span|"
                                   "//blockquote/center/p/b|"
                                   "//blockquote/h3)").get(
        '').strip().replace('\n', '').replace('\t', '').replace('\r', '').replace('<Back>', '')
    article_title = ' '.join(article_title.split())
    article_title = article_title if article_title else title
    tweet_createtime = response.xpath("string(//div[@id='articleCopy']/table[@id='table3']/tr[2]/td|"
                                      "//table[@id='AutoNumber1']/tr[1]/td/address|"
                                      "//table/tr[2]/td[@class='tw'][2]/div[@align='left'])").get('').strip()
    tweet_author = ''
    ps = response.xpath("//div[@class='intro']|"
                        "//div[@id='storytext']|"
                        "//div[@id='article-wrapper']|"
                        "//span[@id='intelliTxt']|"
                        "//td[@align='center']/p|"
                        "//table/tr[2]/td[@class='tw'][2]|"
                        "//td[@class='c1']/table/tr[3]/td/blockquote|"
                        "//blockquote/div|"
                        "//div[@id='articleCopy']/p/font|"
                        "//blockquote/p|"
                        "//div[@id='articleCopy']/div[@class='firstPar']//font")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip().replace('\n', '').replace(
        '\t', '').replace('\r', '').replace('< 返回目录 >', '') for p in ps if p]).strip()
    article_content = ' '.join(article_content.split())
    html_content = response.xpath("//div[@class='intro']|"
                                  "//div[@id='storytext']|"
                                  "//div[@id='article-wrapper']|"
                                  "//span[@id='intelliTxt']|"
                                  "//td[@align='center']/p|"
                                  "//table/tr[2]/td[@class='tw'][2]|"
                                  "//td[@class='c1']/table/tr[3]/td/blockquote|"
                                  "//blockquote/div|"
                                  "//div[@id='articleCopy']/p/font|"
                                  "//blockquote/p").get('')
    imgurls = response.xpath(
        "//div[@class='firstPar']//img/@src|"
        "//table[@id='table1']//img/@src|"
        "//td[@class='tw']/p/img/@src").getall()
    img_url = [urljoin('https://www.smhric.org/', imgurl) for imgurl in imgurls if imgurl.strip()]
    return parsetweet_bing_new(item, article_title, article_content, tweet_author, tweet_createtime, img_url,
                               html_content, translate=translate)


def parse_tweet_southmongoliaorg(response, item):
    article_title = response.xpath("string(/html/head/title)").get('').rsplit('–', 1)[0].strip()
    tweet_createtime = response.xpath("string(//span[contains(@class,'entry-meta-date')]/a)").get('').strip()
    tweet_author = ''
    ps = response.xpath("//article/div[contains(@class,'entry-content')]//node()[self::p or self::h2]")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//article/div[contains(@class,'entry-content')]").get('')
    img_url = response.xpath("//article/div[contains(@class,'entry-content')]/figure/img/@src").getall()
    return parsetweet_bing_new(item, article_title, article_content, tweet_author, tweet_createtime, img_url,
                               html_content,
                               dt="Asia/Tokyo")


def parse_tweet_newsmn(response, item):
    article_title = response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('|', 1)[0].strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    ps = response.xpath("//div[@class='entry-post']/div//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@class='entry-post']/div").get('')
    img_url = response.xpath(
        "//meta[@property='og:image']/@content|//div[@class='entry-post']/div//p/img/@src").getall()
    return parsetweet_bing_new(item, article_title, article_content, tweet_author, tweet_createtime, img_url,
                               html_content)


def parse_tweet_lynasrareearths(response, item):
    article_title = \
        response.xpath("string(//meta[@property='og:title']/@content)").get('').rsplit('- Lynas Rare Earths', 1)[
            0].strip()
    tweet_createtime = response.xpath("string(//meta[@property='article:published_time']/@content)").get('').strip()
    tweet_author = response.xpath("string(//meta[@name='author']/@content)").get('').strip()
    ps = response.xpath("//div[@id='content']/section/div[@class='container']/div[@class='row']//p")
    article_content = '\n'.join([p.xpath('string(.)').get('').strip() for p in ps if p]).strip()
    html_content = response.xpath("//div[@id='content']/section/div[@class='container']/div[@class='row']").get('')
    img_url = response.xpath(
        "//div[@id='content']/section/div[@class='container']/div[@class='row']//img/@src").getall()
    return parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, img_url, html_content
                      , _translatetext=translate_text_googleapi)


tweet_mapping = {
    'rfa.org': parse_tweet_rfa,
    'foxnews.com': parse_tweet_foxnews,
    'bbc.com': parse_tweet_bbc,
    'bbc.co.uk': parse_tweet_bbc,
    'nytimes.com': parse_tweet_nytimes,
    'washingtonpost.com': parse_tweet_washingtonpost,
    'washingtontimes.com': parse_tweet_washingtontimes,
    'vox.com': parse_tweet_vox,
    'bushcenter.org': parse_tweet_bushcenter,
    'cardrates.com': parse_tweet_cardrates,
    'haaretz.com': parse_tweet_haaretz,
    '.hrw.org': parse_tweet_hrw,
    'newsweek.com': parse_tweet_newsweek,
    'usatoday.com': parse_tweet_usatoday,
    'theguardian.com': parse_tweet_theguardian,
    'axios.com': parse_tweet_axios,
    'economist.com': parse_tweet_economist,
    # 'bitterwinter.org': parse_tweet_bitterwinter,
    'chinadigitaltimes.net': parse_tweet_chinadigitaltimes,
    'delano.lu': parse_tweet_delano,
    'thechinaproject.com': parse_tweet_thechinaproject,
    'thehill.com': parse_tweet_thehill,
    'foreignpolicy.com': parse_tweet_foreignpolicy,
    'cnn.com': parse_tweet_cnn,
    'victimsofcommunism.org': parse_tweet_victimsofcommunism,
    'xinjiangpolicefiles.org': parse_tweet_xinjiangpolicefiles,
    'cbc.ca': parse_tweet_cbc,
    'rollingstone.com': parse_tweet_rollingstone,
    'dailyutahchronicle.com': parse_tweet_dailyutahchronicle,
    'theepochtimes.com': parse_tweet_theepochtimes,
    'kabulnow.com': parse_tweet_kabulnow,
    '.dawn.com': parse_tweet_dawn,
    'aninews.in': parse_tweet_aninewsin,
    'afintl.com': parse_tweet_afintl,
    'avapress.com': parse_tweet_avapress,
    'khaama.com': parse_tweet_khaama,
    'arynews.tv': parse_tweet_arynewstv,
    'pakistantoday.com': parse_tweet_pakistantoday,
    'pakobserver.net': parse_tweet_pakobserver,
    'ptvnews.ph': parse_tweet_ptvnewsph,
    'cn.inform.kz': parse_tweet_cninformkz,
    'ru.sputnik.kz': parse_tweet_rusputnikkz,
    'ru.sputnik.kg': parse_tweet_rusputnikkz,
    'oz.sputniknews.uz': parse_tweet_rusputnikkz,
    'tj.sputniknews.ru': parse_tweet_rusputnikkz,
    'uyghur-j.org': parse_tweet_uyghurj,
    '24.kg': parse_tweet_24kg,
    'ria.ru': parse_tweet_riaru,
    'dzen.ru': parse_tweet_dzenru,
    'kaktus.media': parse_tweet_kaktusmedia,
    'vlast.kz': parse_tweet_vlastkz,
    'total.kz': parse_tweet_totalkz,
    'informburo.kz': parse_tweet_informburokz,
    'centralasia.news': parse_tweet_centralasianews,
    'spot.uz': parse_tweet_spotuz,
    'freedomhouse.org': parse_tweet_freedomhouseorg,
    'turkistantimes.com': parse_tweet_turkistantimes,
    'amnestyusa.org': parse_tweet_amnestyusa,
    'msh.ulb.ac.be': parse_tweet_mshulbacbe,
    'remote-xuar.com': parse_tweet_remotexuar,
    'udtsb.com': parse_tweet_udtsb,
    'farsnews.ir': parse_tweet_farsnewsir,
    'daijiworld.com': parse_tweet_daijiworld,
    'southasiantribune.com': parse_tweet_southasiantribune,
    'scrippsnews.com': parse_tweet_scrippsnews,
    'english.zrumbesh.com': parse_tweet_zrumbeshnew,
    'habernida.com': parse_tweet_habernida,
    'hizb-ut-tahrir.info': parse_tweet_hizbuttahrir,
    'vot.org': parse_tweet_votorg,
    'cecc.gov': parse_tweet_ceccgov,
    'mofa.gov.tw': parse_tweet_mofagovtw,
    'cna.com.tw': parse_tweet_cnacomtw,
    'tibetanreview.net': parse_tweet_tibetanreview,
    'chinese.aljazeera.net': parse_tweet_chinesealjazeera,
    'thekhorasandiary.com': parse_tweet_thekhorasandiary,
    'voachinese.com': parse_tweet_voachinese,
    'zaobao.com': parse_tweet_zaobao,
    'xizang-zhiye.org': parse_tweet_xizangzhiye,
    'scmp.com': parse_tweet_scmp,
    'defensenews.com': parse_tweet_defensenews,
    'airandspaceforces.com': parse_tweet_airandspaceforces,
    'def.ltn.com.tw': parse_tweet_defltncomtw,
    'breakingdefense.com': parse_tweet_breakingdefense,
    'news.usni.org': parse_tweet_newsusniorg,
    'news.ltn.com.tw': parse_tweet_newsltncomtw,
    'my-formosa.com': parse_tweet_myformosa,
    'new7.storm.mg': parse_tweet_new7stormmg,
    'taiwan-reports.com': parse_tweet_taiwanreports,
    'taiwanreports.com': parse_tweet_taiwanreports,
    'icdf.org.tw': parse_tweet_icdforgtw,
    'ftvnews.com.tw': parse_tweet_ftvnewscomtw,
    'enactafrica.org': parse_tweet_enactafricaorg,
    'uyghurstudy.org': parse_tweet_uyghurstudyorg,
    'uscirf.gov': parse_tweet_uscirfgov,
    'thediplomat.com': parse_tweet_thediplomat,
    'centcom.mil': parse_tweet_centcommil,
    'minghui.org': parse_tweet_minghuiorg,
    'epochtimes.com': parse_tweet_epochtimes,
    'childrenofafrica.ngo': parse_tweet_childrenofafricango,
    'trustafrica.org': parse_tweet_trustafricaorg,
    'developafrica.org': parse_tweet_developafricaorg,
    'africahumanitarian.org': parse_tweet_africahumanitarianorg,
    'phayul.com': parse_tweet_phayul,
    'tibetanyouthcongress.org': parse_tweet_tibetanyouthcongress,
    'savetibet.org': parse_tweet_savetibetorg,
    'studentsforafreetibet.org': parse_tweet_studentsforafreetibet,
    'tibetnetwork.org': parse_tweet_tibetnetworkorg,
    'mfa.gov.ir': parse_tweet_mfagovir,
    'jpost.com': parse_tweet_jpost,
    'ptv.com.pk': parse_tweet_ptvcompk,
    'premiumtimesng.com': parse_tweet_premiumtimesng,
    'actualite.cd': parse_tweet_actualitecd,
    'gov.kz': parse_tweet_govkz,
    'mvd.gov.kg': parse_tweet_mvdgovkg,
    'gknb.gov.kg': parse_tweet_gknbgovkg,
    'gov.uz': parse_tweet_govuz,
    'asuda.gov.tm': parse_tweet_asudagovtm,
    'mvd.tj': parse_tweet_mvdtj,
    'bitterwinter.org': parse_tweet_bitterwinterorg,
    'istiqlalhaber.com': parse_tweet_istiqlalhaber,
    'nzz.ch': parse_tweet_nzzch,
    'turkistanpress.com': parse_tweet_turkistanpress,
    'haberajandanet.com': parse_tweet_haberajandanet,
    'president.mn': parse_tweet_presidentmn,
    'parliament.mn': parse_tweet_parliamentmn,
    'smhric.org': parse_tweet_smhricorg,
    'southmongolia.org': parse_tweet_southmongoliaorg,
    'news.mn': parse_tweet_newsmn,
    'lynasrareearths.com': parse_tweet_lynasrareearths
}


def get_map(tweet_url):
    udomain = urlparse(tweet_url).netloc
    tweet_func = next((value for key, value in tweet_mapping.items() if key in udomain), None)
    return tweet_func
