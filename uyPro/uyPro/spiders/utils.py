#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UyPro新闻爬虫系统 - 工具函数模块

本模块提供了爬虫系统中使用的各种工具函数，包括：
- 日期时间解析和转换
- 多语言翻译服务（Google、Bing、Gemini、SiliconFlow）
- 文本处理和清理
- 文件操作和压缩
- 网络请求和代理处理
- 数据格式转换

主要功能：
1. 时间解析：支持多种时间格式的解析和时区转换
2. 翻译服务：集成多个翻译引擎，支持异步和批量翻译
3. 文本处理：HTML清理、特殊字符处理、格式化
4. 文件管理：文件压缩、移动、清理等操作
5. 网络工具：代理管理、请求重试、错误处理

"""

# ==================== 标准库导入 ====================
import asyncio
import ast
import base64
import functools
import html
import json
import logging
import os
import platform
import random
import re
import shutil
import subprocess
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

# ==================== 第三方库导入 ====================
import translators
from google import genai
from google.genai import types
import bcrypt
import httpx
import pytz
import requests
from bs4 import BeautifulSoup
from convertdate import persian
from dateutil import parser
from deep_translator import GoogleTranslator
from googletrans import Translator
from requests.exceptions import HTTPError, ProxyError

# ==================== 项目内部导入 ====================
from uyPro.settings import (
    dest_zip_file_path, zip_file_path, deviceid, pgmid,
    folder_path, processed_path, traproxylist, url_domain_list
)

# ==================== 全局配置 ====================

# 禁用httpx的INFO级别日志，减少日志噪音
logging.getLogger("httpx").setLevel(logging.WARNING)

# 为requests的get和post方法设置默认超时时间（30秒）
for method in ('get', 'post'):
    func = getattr(requests, method)
    setattr(requests, method, functools.partial(func, timeout=30))


# ==================== 日期时间处理函数 ====================

def _get_russian_month_mapping():
    """
    获取俄语月份名称到英语的映射表

    Returns:
        dict: 俄语月份缩写到英语月份缩写的映射字典
    """
    return {
        'янв': 'Jan', 'фев': 'Feb', 'мар': 'Mar', 'апр': 'Apr',
        'май': 'May', 'июн': 'Jun', 'июл': 'Jul', 'авг': 'Aug',
        'сен': 'Sep', 'окт': 'Oct', 'ноя': 'Nov', 'дек': 'Dec'
    }


def _parse_unix_timestamp(timestamp):
    """
    解析Unix时间戳为UTC datetime对象

    Args:
        timestamp (int): Unix时间戳

    Returns:
        datetime: UTC时区的datetime对象
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _parse_persian_date(date_string):
    """
    解析波斯历日期字符串为datetime对象

    波斯历格式示例: "1402/10/25-14:30"

    Args:
        date_string (str): 波斯历日期字符串，格式为"YYYY/MM/DD-HH:MM"

    Returns:
        datetime: 转换后的公历datetime对象

    Raises:
        ValueError: 当日期格式不正确时
    """
    try:
        # 分割日期和时间部分
        persian_year, persian_month, persian_day_time = date_string.split('/')
        persian_day, persian_time = persian_day_time.split('-')

        # 将波斯数字转换为阿拉伯数字
        # 波斯数字: ۰۱۲۳۴۵۶۷۸۹ 对应阿拉伯数字: 0123456789
        persian_to_arabic = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

        persian_year = int(persian_year.translate(persian_to_arabic))
        persian_month = int(persian_month.translate(persian_to_arabic))
        persian_day = int(persian_day.translate(persian_to_arabic).strip())

        # 解析时间部分
        hour, minute = map(int, persian_time.strip().split(':'))

        # 使用convertdate库将波斯历转换为公历
        gregorian_date = persian.to_gregorian(persian_year, persian_month, persian_day)

        # 创建datetime对象
        return datetime(gregorian_date[0], gregorian_date[1], gregorian_date[2], hour, minute)

    except (ValueError, IndexError) as e:
        raise ValueError(f"无法解析波斯历日期 '{date_string}': {e}")


def _parse_chinese_date(date_string):
    """
    解析中文日期格式

    中文日期格式示例: "2024年01月15日"

    Args:
        date_string (str): 中文日期字符串

    Returns:
        datetime: UTC时区的datetime对象
    """
    return datetime.strptime(date_string, "%Y年%m月%d日").replace(tzinfo=timezone.utc)


def _replace_russian_months(date_string):
    """
    将日期字符串中的俄语月份名称替换为英语

    Args:
        date_string (str): 包含俄语月份的日期字符串

    Returns:
        str: 替换后的日期字符串
    """
    months_ru_to_en = _get_russian_month_mapping()

    for ru, en in months_ru_to_en.items():
        if ru in date_string:
            return date_string.replace(ru, en)

    return date_string


def _parse_generic_date(date_string, default_timezone):
    """
    使用通用方法解析日期字符串

    Args:
        date_string (str): 日期字符串
        default_timezone (str): 默认时区

    Returns:
        datetime: 解析后的datetime对象

    Raises:
        ValueError: 当无法解析日期时
    """
    # 首先尝试替换俄语月份
    processed_string = _replace_russian_months(date_string)

    try:
        # 使用dateutil.parser进行智能解析
        dt = parser.parse(processed_string)
    except:
        try:
            # 尝试标准的英语日期格式
            dt = datetime.strptime(processed_string, "%B %d, %Y")
        except Exception as e:
            raise ValueError(f"无法解析日期格式: {e}")

    # 如果没有时区信息，添加默认时区
    if dt.tzinfo is None:
        tz = pytz.timezone(default_timezone)
        dt = tz.localize(dt)

    return dt


def parse_date(date_input, default_timezone="America/New_York"):
    """
    解析各种格式的日期时间字符串并转换为标准格式

    支持的日期格式：
    - Unix时间戳（整数）
    - ISO格式日期时间
    - 波斯历日期（伊朗历法）
    - 中文日期格式（年月日）
    - 俄语月份名称
    - 其他常见日期格式

    Args:
        date_input (str|int): 输入的日期时间，可以是字符串或时间戳
        default_timezone (str): 默认时区，默认为"America/New_York"

    Returns:
        str: 格式化后的日期时间字符串，格式为"YYYY-MM-DD HH:MM:SS"
             如果解析失败则返回空字符串

    Examples:
        >>> parse_date("2024-01-15 10:30:00")
        "2024-01-15 10:30:00"

        >>> parse_date(1705312200)  # Unix时间戳
        "2024-01-15 10:30:00"

        >>> parse_date("1402/10/25-14:30")  # 波斯历
        "2024-01-15 14:30:00"
    """
    if not date_input:
        return ''

    try:
        # 预处理：如果是数字字符串，转换为整数
        if isinstance(date_input, str) and date_input.isdigit():
            date_input = int(date_input)

        # 根据输入类型和格式选择相应的解析方法
        if isinstance(date_input, int):
            # Unix时间戳
            dt = _parse_unix_timestamp(date_input)

        elif (isinstance(date_input, str) and len(date_input) == 18 and
              date_input[10] not in [' ', 'T'] and ':' in date_input):
            # 紧凑格式的ISO日期时间: "YYYY-MM-DDHH:MM:SS"
            dt = datetime.strptime(date_input, "%Y-%m-%d%H:%M:%S").replace(tzinfo=timezone.utc)

        elif (isinstance(date_input, str) and len(date_input) == 17 and
              date_input[10] == '-'):
            # 波斯历日期格式: "1402/10/25-14:30"
            dt = _parse_persian_date(date_input)

        elif (isinstance(date_input, str) and '年' in date_input and
              '月' in date_input and '日' in date_input):
            # 中文日期格式: "2024年01月15日"
            dt = _parse_chinese_date(date_input)

        else:
            # 其他格式，使用通用解析方法
            dt = _parse_generic_date(date_input, default_timezone)

        # 转换为UTC时区并格式化输出
        dt_utc = dt.astimezone(timezone.utc)
        target_format = "%a %b %d %H:%M:%S +0000 %Y"
        return dt_utc.strftime(target_format)

    except Exception as e:
        logging.info(f'日期解析失败: {date_input}, 错误: "{e}"')
        return ''


def extract_first_date(text):
    pattern = r'(\d{2}/\d{2}).*(\d{4})'
    match = re.search(pattern, text)
    if match:
        day_month = match.group(1)
        year = match.group(2)
        return f"{day_month}/{year}"
    else:
        return None


def replace_spaces(s: str) -> str:
    result = re.sub(r'\s+', ' ', s)
    return result


def replace_enter(s: str) -> str:
    result = re.sub(r'\n+', '\n', s)
    return result


def turkish_month_to_number(month_str):
    months_dict = dict(Ocak=1, Şubat=2, Mart=3, Nisan=4, Mayıs=5, Haziran=6, Temmuz=7, Ağustos=8, Eylül=9, Ekim=10,
                       Kasım=11, Aralık=12)
    return months_dict.get(month_str)


def convert_turkish_date_to_datetime(date_str):
    if not date_str:
        return ''
    try:
        date_parts = date_str.split(" ")
        day = int(date_parts[0])
        month_str = date_parts[1]
        month = turkish_month_to_number(month_str)
        year = int(date_parts[2])
        return datetime(year, month, day).strftime('%a %b %d %H:%M:%S +0000 %Y')
    except Exception as e:
        print(f'convert_turkish_date_to_datetime Error:{e}')
        return ''


def turkish_month_to_number_short(month_str):
    months_dict = dict(OCK=1, ŞBT=2, MRT=3, NSN=4, MAY=5, HZR=6, TMM=7, AĞS=8, EYL=9, EKM=10, KSM=11, ARL=12)
    return months_dict.get(month_str)


def uyghur_month_to_number_short(month_str):
    months_dict = dict(يانۋار=1, فېۋرال=2, مارت=3, ئاپرېل=4, ماي=5, ئىيۇن=6, تەممۇز=7, ئاۋغۇست=8, سېنتەبىر=9,
                       ئۆكتەبىر=10, نويابىر=11, دېكابىر=12)
    return months_dict.get(month_str)


def convert_turkish_date_to_datetime_short(date_str):
    if not date_str:
        return ''
    try:
        date_parts = date_str.split(" ")
        day = int(date_parts[0])
        month_str = date_parts[1]
        month = turkish_month_to_number_short(month_str)
        year = int(date_parts[2])
        return datetime(year, month, day).strftime('%a %b %d %H:%M:%S +0000 %Y')
    except Exception as e:
        print(f'convert_turkish_date_to_datetime_short Error:{e}')
        return ''


def _find_punctuation_positions(text):
    """
    查找文本中所有标点符号的位置

    支持的标点符号包括：
    - 英文标点: .,!?;:
    - 中文标点: 。，
    - 阿拉伯文标点: ،
    - 换行符: \n

    Args:
        text (str): 输入文本

    Returns:
        list: 标点符号位置列表（从小到大排序）
    """
    # 定义标点符号模式，包含多语言标点
    punctuation_pattern = r'[.,!?;:。،\n]'

    # 查找所有标点符号位置
    positions = [match.start() for match in re.finditer(punctuation_pattern, text)]

    return positions


def _find_optimal_split_position(text, start, max_end):
    """
    在指定范围内查找最佳的文本分割位置

    分割优先级：
    1. 空格位置（单词边界）
    2. 最大长度位置（强制分割）

    Args:
        text (str): 输入文本
        start (int): 搜索起始位置
        max_end (int): 搜索结束位置

    Returns:
        int: 最佳分割位置
    """
    # 在指定范围内查找最后一个空格
    space_index = text.rfind(' ', start, max_end)

    # 如果找到空格，使用空格位置；否则使用最大长度位置
    return space_index if space_index != -1 else max_end


def _split_by_punctuation(text, max_length):
    """
    基于标点符号进行智能文本分割

    该算法优先在标点符号处分割文本，保持语义完整性。
    当片段长度超过限制时，会在单词边界进行二次分割。

    Args:
        text (str): 待分割的文本
        max_length (int): 每个片段的最大长度

    Returns:
        list: 分割后的文本片段列表
    """
    result = []
    punctuation_positions = _find_punctuation_positions(text)

    start = 0  # 当前片段的起始位置
    end = 0    # 当前片段的结束位置

    # 遍历所有标点符号位置
    for pos in punctuation_positions:
        # 计算包含当前标点的片段长度
        potential_end = pos + 1

        # 如果加上当前标点会超过最大长度
        if potential_end - start > max_length:
            # 添加当前片段（到上一个标点为止）
            if end > start:
                result.append(text[start:end])
                start = end

        # 更新片段结束位置
        end = potential_end

        # 如果当前片段已达到最大长度，进行强制分割
        if end - start >= max_length:
            split_pos = _find_optimal_split_position(text, start, end)
            result.append(text[start:split_pos])
            start = split_pos + 1 if split_pos < len(text) and text[split_pos] == ' ' else split_pos

    return result, start


def _split_remaining_text(text, start, max_length):
    """
    分割剩余的文本（没有标点符号的部分）

    Args:
        text (str): 原始文本
        start (int): 剩余文本的起始位置
        max_length (int): 每个片段的最大长度

    Returns:
        list: 剩余文本的分割片段
    """
    result = []

    # 处理剩余文本
    while start < len(text):
        remaining_length = len(text) - start

        # 如果剩余文本长度不超过最大长度，直接添加
        if remaining_length <= max_length:
            result.append(text[start:])
            break

        # 计算当前片段的结束位置
        end = min(len(text), start + max_length)

        # 查找最佳分割位置
        split_pos = _find_optimal_split_position(text, start, end)

        # 添加当前片段
        result.append(text[start:split_pos])

        # 更新起始位置，跳过空格
        start = split_pos + 1 if split_pos < len(text) and text[split_pos] == ' ' else split_pos

    return result


def split_string(s: str, max_length: int = 4800) -> list:
    """
    智能文本分割函数

    该函数将长文本分割为多个较短的片段，优先在标点符号和单词边界处分割，
    以保持文本的语义完整性。适用于翻译服务的文本预处理。

    分割策略：
    1. 优先在标点符号处分割（句子边界）
    2. 其次在空格处分割（单词边界）
    3. 最后进行强制分割（避免超长片段）

    Args:
        s (str): 待分割的文本字符串
        max_length (int): 每个片段的最大字符数，默认4800

    Returns:
        list: 分割后的文本片段列表

    Examples:
        >>> text = "Hello world. This is a test! How are you?"
        >>> result = split_string(text, max_length=20)
        >>> print(result)
        ['Hello world.', 'This is a test!', 'How are you?']

    注意事项：
        - 空字符串返回空列表
        - 单个字符超长的情况会进行强制分割
        - 保留原始文本的空格和标点符号
    """
    # 输入验证
    if not s or not isinstance(s, str):
        return []

    # 如果文本长度不超过最大长度，直接返回
    if len(s) <= max_length:
        return [s]

    # 基于标点符号进行初步分割
    result, remaining_start = _split_by_punctuation(s, max_length)

    # 处理剩余的文本
    remaining_parts = _split_remaining_text(s, remaining_start, max_length)
    result.extend(remaining_parts)

    # 过滤空字符串
    return [part for part in result if part.strip()]


def remove_arabic_and_adjacent_chars(s: str) -> str:
    """
    智能移除混合文本中的阿拉伯文字符

    该函数用于处理包含多种语言的混合文本，当英文内容占主导地位时，
    自动移除阿拉伯文字符及其相邻的标点符号，以提高翻译质量。

    处理逻辑：
    1. 统计文本中阿拉伯文和英文的词汇数量
    2. 如果英文词汇数量大于阿拉伯文词汇数量，则移除阿拉伯文内容
    3. 同时移除阿拉伯文字符相邻的特定标点符号

    Args:
        s (str): 输入的混合语言文本

    Returns:
        str: 处理后的文本，可能已移除阿拉伯文内容

    Unicode范围说明：
        - \\u0600-\\u06FF: 阿拉伯文字符范围
        - 包括阿拉伯字母、数字、标点符号等

    移除的标点符号：
        - []: 方括号
        - (): 圆括号
        - «»: 阿拉伯文引号

    Examples:
        >>> text = "Hello world [مرحبا] this is English text"
        >>> result = remove_arabic_and_adjacent_chars(text)
        >>> print(result)  # "Hello world  this is English text"

        >>> text = "مرحبا بك في العالم العربي [Hello] world"
        >>> result = remove_arabic_and_adjacent_chars(text)
        >>> print(result)  # 保持原文不变，因为阿拉伯文占主导
    """
    if not s or not isinstance(s, str):
        return s

    # 统计阿拉伯文词汇数量
    # 使用Unicode范围 \u0600-\u06FF 匹配所有阿拉伯文字符
    arabic_words = re.findall(r'[\u0600-\u06FF]+', s)
    arabic_count = len(arabic_words)

    # 统计英文词汇数量
    # 匹配连续的英文字母组成的单词
    english_words = re.findall(r'[A-Za-z]+', s)
    english_count = len(english_words)

    # 只有当英文词汇数量大于阿拉伯文词汇数量时才进行移除
    # 这样可以避免误删主要内容为阿拉伯文的文本
    if english_count > arabic_count:
        # 移除阿拉伯文字符及其相邻的标点符号
        # 模式说明：
        # [\[\]()«]*  : 阿拉伯文前的可选标点符号
        # [\u0600-\u06FF]+  : 一个或多个阿拉伯文字符
        # [\[\]()»]*  : 阿拉伯文后的可选标点符号
        s = re.sub(r'[\[\]()«]*[\u0600-\u06FF]+[\[\]()»]*', '', s)

        # 清理多余的空白字符
        s = re.sub(r'\s+', ' ', s).strip()

    return s


def split_mixed_text(s, max_length=4800):
    s = remove_arabic_and_adjacent_chars(s)
    result = split_string(s, max_length)
    return result


def translate_segment(segment, proxies, target):
    translator = GoogleTranslator(target=target, proxies=proxies)
    return translator.translate(segment)


def translatetext(text, language='zh-CN', max_length=4500, split_func=split_string, timeout=30):
    if not text or isinstance(text, (int, float)):
        return str(text) if text else ''

    for _ in range(2):
        try:
            proxies = {p: random.choice(traproxylist) for p in
                       ('http', 'https')} if traproxylist and platform.system() != 'Windows' else {}

            if split_func == split_mixed_text:
                text = remove_arabic_and_adjacent_chars(text)

            segments = [text] if len(text) <= max_length else split_func(text, max_length)
            results = [None] * len(segments)

            with ThreadPoolExecutor(min(len(segments), 10)) as executor:
                for idx, segment in enumerate(s.strip() for s in segments if s.strip()):
                    try:
                        result = executor.submit(translate_segment, segment, proxies, language).result(timeout=timeout)
                        if result and "Error 500" in result:
                            logging.warning(f"GoogleTranslator Error 500: {segment}, {result}")
                            return ''
                        results[idx] = result if result else ""
                    except Exception as e:
                        logging.warning(f"Translation error: {e}")
                        return ''

            return ' '.join(filter(None, results))

        except Exception as e:
            logging.warning(f'Error: {e}')
            time.sleep(0.1)
            max_length = 450

    return ''


def translate_text_siliconflow(input_text: str, max_retries: int = 3, sleep_seconds: int = 2) -> str:
    if isinstance(input_text, (int, float)):
        return str(input_text)
    if not input_text:
        return ''

    url = "https://api.siliconflow.cn/v1/chat/completions"
    headers = {
        "Authorization": "Bearer sk-hijeoxjqdogtxgzayfoxivuuusallvojmpqeapnfxvwqaicw",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "THUDM/glm-4-9b-chat",
        "messages": [
            {"role": "system",
             "content": "你是一个翻译专家，把下一行文本作为纯文本输入，并将其翻译为简体中文，仅输出翻译。如果某些内容无需翻译（如专有名词、代码等），则保持原文不变"},
            {"role": "user", "content": input_text}
        ],
        "max_tokens": 4096,
        "temperature": 0.7,
        "top_p": 0.7,
        "top_k": 50,
        "frequency_penalty": 0.0,
    }

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=300)
            choices = response.json().get("choices")
            if choices and choices[0].get("message") and choices[0]["message"].get("content"):
                return choices[0]["message"]["content"]
            else:
                logging.warning(f"第 {attempt} 次请求：未获取到有效的翻译结果。")
        except Exception as e:
            logging.warning(f"第 {attempt} 次请求时发生异常: {e}")

        if attempt < max_retries:
            time.sleep(sleep_seconds)

    return ""


def translate_text_gemini(input_text: str, max_retries: int = 3, sleep_seconds: int = 2) -> str:
    if isinstance(input_text, (int, float)):
        return str(input_text)
    if not input_text:
        return ''

    client = genai.Client(api_key="AIzaSyAA4NCSYDHIusYCdXOoiiStSJUXe5HccgQ")
    sys_instruct = "你是一个翻译专家，把下一行文本作为纯文本输入，并将其翻译为简体中文，仅输出翻译。如果某些内容无需翻译（如专有名词、代码等），则保持原文不变"

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(system_instruction=sys_instruct),
                contents=input_text,
            )
            return response.text
        except Exception as e:
            logging.warning(f"第 {attempt} 次请求时发生异常: {e}")

        if attempt < max_retries:
            time.sleep(sleep_seconds)

    return ""


def translate_text_googleapi(text, language='zh-CN', max_length=5000, split_func=split_string, timeout=30):
    """Google API翻译函数"""
    # 避免未使用参数警告
    _ = language, max_length, split_func

    if isinstance(text, (int, float)):
        return str(text)
    if not text:
        return ''

    api_key = "AIzaSyATBXajvzQLTDHEQbcpq0Ihe0vWDHmO520"
    source = "auto"
    target = "zh"

    headers = {
        "content-type": "application/json+protobuf",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/135.0.0.0 Safari/537.36",
        "x-goog-api-key": api_key
    }

    url = "https://translate-pa.googleapis.com/v1/translateHtml"

    data_dict = [[[text], source, target], "te_lib"]

    # 正确的httpx代理配置
    proxy = None
    if traproxylist and platform.system() != 'Windows':
        proxy = random.choice(traproxylist)

    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(proxy=proxy, timeout=timeout) as client:
                response = client.post(url, headers=headers, json=data_dict)

                if response.status_code == 200:
                    result_text = response.text
                    try:
                        result = json.loads(result_text)
                    except json.JSONDecodeError:
                        try:
                            result = ast.literal_eval(result_text)
                        except (SyntaxError, ValueError):
                            logging.warning(f"Google API响应无法解析: {result_text[:100]}")
                            continue

                    if (isinstance(result, list) and len(result) > 0 and
                            isinstance(result[0], list) and len(result[0]) > 0):
                        return result[0][0]

        except Exception as e:
            logging.warning(f"第 {attempt} 次Google API请求时发生异常: {e}")

        if attempt < max_retries:
            time.sleep(2)

    return ""


async def translate_segment_a(segment, translator, proxies, target):
    try:
        result = await translator.translate(segment, dest=target, proxies=proxies)
        return result.text
    except Exception as e:
        logging.warning(f"翻译段落失败: {segment}, 错误信息: {e}")
        return ''


async def translate_segments(segments, proxies, target, timeout):
    async with Translator() as translator:
        tasks = [
            asyncio.wait_for(
                translate_segment_a(segment, translator, proxies, target),
                timeout=timeout
            )
            for segment in segments
        ]
        results = list(await asyncio.gather(*tasks, return_exceptions=True))
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logging.warning(f"段落 {segments[idx]} 翻译出错，错误信息：{result}")
                results[idx] = ''
        return ' '.join(filter(None, results))


async def translatetext_a(text, language='zh-CN', max_length=4500, split_func=None, timeout=30):
    if isinstance(text, (int, float)):
        return str(text)
    if not text:
        return ''

    for _ in range(2):
        try:
            proxies = {}
            if traproxylist and platform.system() != 'Windows':
                proxies = {protocol: random.choice(traproxylist) for protocol in ['http', 'https']}
            if split_func == split_mixed_text:
                text = remove_arabic_and_adjacent_chars(text)
            segments = [text] if len(text) <= max_length else split_func(text, max_length)
            return await translate_segments(segments, proxies, target=language, timeout=timeout)
        except (HTTPError, ProxyError, TypeError, IndexError) as e:
            logging.warning(f'Error: {e}')
            await asyncio.sleep(2)
        except Exception as e:
            logging.warning(f'Unknown Error: {e}')
            max_length = 450
            await asyncio.sleep(2)
            continue

    return ''


def _get_translation_proxies():
    """
    获取翻译服务使用的代理配置

    Returns:
        dict: 代理配置字典，Windows系统返回空字典
    """
    if not traproxylist or platform.system() == 'Windows':
        return {}

    proxy = random.choice(traproxylist)
    return {protocol: proxy for protocol in ['http', 'https']}


def _prepare_text_for_translation(text, split_func):
    """
    为翻译准备文本，处理特殊字符和格式

    Args:
        text (str): 原始文本
        split_func (function): 文本分割函数

    Returns:
        str: 处理后的文本
    """
    if split_func == split_mixed_text:
        # 移除阿拉伯字符和相邻字符，提高翻译质量
        text = remove_arabic_and_adjacent_chars(text)
    return text


def _split_text_for_translation(text, max_length, split_func):
    """
    将长文本分割为适合翻译的片段

    Args:
        text (str): 待分割的文本
        max_length (int): 每个片段的最大长度
        split_func (function): 文本分割函数

    Returns:
        list: 文本片段列表
    """
    if len(text) <= max_length:
        return [text]
    return split_func(text, max_length)


def _execute_parallel_translation(segments, translate_func, proxies, timeout, max_workers=10):
    """
    并行执行文本片段翻译

    Args:
        segments (list): 文本片段列表
        translate_func (function): 翻译函数
        proxies (dict): 代理配置
        timeout (int): 超时时间
        max_workers (int): 最大并发数

    Returns:
        str: 翻译后的完整文本

    Raises:
        Exception: 当翻译失败时
    """
    # 限制并发数，避免过多请求
    worker_count = min(len(segments), max_workers)

    with ThreadPoolExecutor(worker_count) as executor:
        # 提交所有翻译任务
        future_to_segment = [
            (executor.submit(translate_func, segment, proxies), idx)
            for idx, segment in enumerate(segments)
            if segment.strip()  # 跳过空片段
        ]

        # 初始化结果数组
        results = [None] * len(segments)

        # 收集翻译结果
        for future, idx in future_to_segment:
            try:
                result = future.result(timeout=timeout)
                results[idx] = result
            except (TimeoutError, Exception) as e:
                logging.warning(f"翻译片段失败 (索引 {idx}): {e}")
                raise e

        # 合并非空结果
        return ' '.join(filter(None, results))


def _translate_with_retry(text, translate_func, max_length=900, split_func=split_string,
                         timeout=30, max_workers=10, max_retries=2):
    """
    带重试机制的翻译函数

    Args:
        text (str): 待翻译文本
        translate_func (function): 翻译函数
        max_length (int): 最大片段长度
        split_func (function): 文本分割函数
        timeout (int): 超时时间
        max_workers (int): 最大并发数
        max_retries (int): 最大重试次数

    Returns:
        str: 翻译结果
    """
    current_max_length = max_length

    for attempt in range(max_retries):
        try:
            # 获取代理配置
            proxies = _get_translation_proxies()

            # 预处理文本
            processed_text = _prepare_text_for_translation(text, split_func)

            # 分割文本
            segments = _split_text_for_translation(processed_text, current_max_length, split_func)

            # 执行并行翻译
            return _execute_parallel_translation(segments, translate_func, proxies, timeout, max_workers)

        except (HTTPError, ProxyError, TypeError, IndexError) as e:
            logging.warning(f'翻译错误 (尝试 {attempt + 1}): {e}')
            time.sleep(0.1)

        except Exception as e:
            logging.warning(f'翻译未知错误 (尝试 {attempt + 1}): {e}')
            # 减少片段长度重试
            current_max_length = 100

    return ''


def translate_segment_bing(segment, proxies):
    """
    使用Bing翻译单个文本片段

    Args:
        segment (str): 文本片段
        proxies (dict): 代理配置

    Returns:
        str: 翻译结果
    """
    return translators.translate_text(
        segment,
        translator='bing',
        to_language='zh',
        proxies=proxies,
        timeout=30
    )


def translatetext_bing(text: str, max_length: int = 900, split_func=split_string, timeout=30) -> str:
    """
    使用Bing翻译服务翻译文本

    Args:
        text (str): 待翻译文本
        max_length (int): 最大片段长度，默认900字符
        split_func (function): 文本分割函数
        timeout (int): 超时时间

    Returns:
        str: 翻译后的中文文本
    """
    # 输入验证和预处理
    if not text or isinstance(text, (int, float)):
        return str(text) if text else ''

    return _translate_with_retry(
        text=text,
        translate_func=translate_segment_bing,
        max_length=max_length,
        split_func=split_func,
        timeout=timeout,
        max_workers=10
    )


def translate_segment_bo(segment, proxies):
    """
    使用Bing翻译单个藏语文本片段

    Args:
        segment (str): 藏语文本片段
        proxies (dict): 代理配置

    Returns:
        str: 翻译结果
    """
    return translators.translate_text(
        segment,
        translator='bing',
        to_language='zh',
        proxies=proxies,
        timeout=30,
        from_language='bo'
    )


def translatetext_bo(text: str, max_length: int = 900, split_func=split_string, timeout=30) -> str:
    """
    使用Bing翻译服务翻译藏语文本

    Args:
        text (str): 待翻译的藏语文本
        max_length (int): 最大片段长度，默认900字符
        split_func (function): 文本分割函数
        timeout (int): 超时时间

    Returns:
        str: 翻译后的中文文本
    """
    # 输入验证和预处理
    if isinstance(text, (int, float)):
        return str(text)
    if not text:
        return ''

    return _translate_with_retry(
        text=text,
        translate_func=translate_segment_bo,
        max_length=max_length,
        split_func=split_func,
        timeout=timeout,
        max_workers=5  # 藏语翻译使用较少的并发数
    )


def decrypt(hex_string):
    if not re.match(r'^[0-9a-fA-F]+$', hex_string):
        raise ValueError(f"Invalid hex string: {hex_string}")
    result = ""
    key = int(hex_string[0:2], 16)
    i = 2
    while i < len(hex_string):
        char_code = int(hex_string[i:i + 2], 16) ^ key
        result += chr(char_code)
        i += 2
    try:
        result = bytes(result, "latin-1").decode("utf-8")
    except Exception as e:
        print(e)
    return result


def replace_encrypted_emails(html_fragment):
    soup = BeautifulSoup(html_fragment, 'html.parser')
    email_tags = soup.find_all(class_="__cf_email__", attrs={"data-cfemail": True})
    for email_tag in email_tags:
        encrypted_email = email_tag['data-cfemail']
        decrypted_email = decrypt(encrypted_email)
        new_tag = soup.new_string(decrypted_email)
        email_tag.replace_with(new_tag)
    return str(soup)


def extract_date(text):
    pattern = r'(January\b|February\b|March\b|April\b|May\b|June\b|July\b|August\b|September\b' \
              r'|October\b|November\b|December\b) (\d{1,2}), (\d{4})'
    dates = re.findall(pattern, text)
    if dates:
        dates = [' '.join(date) for date in dates]
        return dates[0]
    else:
        return ''


def _get_oldest_json_file():
    """
    获取任务目录中最旧的JSON文件

    Returns:
        os.DirEntry: 最旧的JSON文件条目，如果没有文件则返回None
    """
    try:
        # 扫描任务目录，获取所有JSON文件
        json_entries = [
            entry for entry in os.scandir(folder_path)
            if entry.is_file() and entry.name.endswith('.json')
        ]

        if not json_entries:
            return None

        # 按创建时间排序，返回最旧的文件
        json_entries.sort(key=lambda entry: entry.stat().st_ctime)
        return json_entries[0]

    except (OSError, PermissionError) as e:
        logging.error(f"扫描任务目录失败: {e}")
        return None


def _load_task_data(file_path):
    """
    加载任务JSON文件数据

    Args:
        file_path (str): JSON文件路径

    Returns:
        dict: 任务数据字典，加载失败时返回空字典
    """
    try:
        with open(file_path, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, UnicodeDecodeError) as e:
        logging.error(f"加载任务文件失败 {file_path}: {e}")
        return {}


def _extract_task_parameters(data):
    """
    从任务数据中提取关键参数

    Args:
        data (dict): 任务数据字典

    Returns:
        dict: 包含提取参数的字典
    """
    # 安全获取任务列表中的第一个任务
    task_info = data.get('tasklist', [{}])[0] if data.get('tasklist') else {}

    return {
        'app': task_info.get('app', '').strip(),
        'method': task_info.get('method', '').strip(),
        'churl': task_info.get('churl', '').strip(),
        'dltype': task_info.get('dltype', '').strip(),
        'tweeturl': task_info.get('tweeturl', '').strip(),
        'taskid': task_info.get('taskid', '').strip()
    }


def _validate_task_parameters(params):
    """
    验证任务参数的有效性

    Args:
        params (dict): 任务参数字典

    Returns:
        tuple: (is_valid, error_type)
            - is_valid (bool): 参数是否有效
            - error_type (str): 错误类型，有效时为None
    """
    # 检查必需参数
    if not params['taskid']:
        return False, "config_error"

    # 检查方法参数
    if params['method'] not in ['getchannel', 'gettweet']:
        return False, "config_error"

    # 检查应用类型
    if params['app'] != 'website':
        return False, "config_error"

    # 检查下载类型
    if params['dltype'] not in ['inc', 'full', '']:
        return False, "config_error"

    # 检查URL是否在不支持的域名列表中
    if any(domain in params['churl'] for domain in url_domain_list):
        return False, "not_support"

    return True, None


def _create_error_response(data, filename, error_type, capture_time):
    """
    创建错误响应并记录日志

    Args:
        data (dict): 任务数据
        filename (str): 任务文件名
        error_type (str): 错误类型
        capture_time (str): 捕获时间
    """
    # 构建错误信息JSON
    jsontext = {
        "taskid": data.get('tasklist', [{}])[0].get('taskid', ''),
        "count": 0,
        "deviceid": deviceid,
        "pgmid": pgmid,
        "capture_time": capture_time,
        "noresult": error_type
    }

    # 创建错误日志文件
    createerrorlogfile(jsontext, filename, data, error_type)


def start_spider():
    """
    启动爬虫任务处理器

    该函数负责扫描任务目录，获取最旧的任务文件，验证任务参数，
    并根据验证结果决定是否执行任务或记录错误。

    处理流程：
    1. 扫描任务目录获取最旧的JSON文件
    2. 加载并解析任务数据
    3. 提取关键任务参数
    4. 验证参数有效性
    5. 检查任务重复性
    6. 返回有效任务参数或记录错误

    Returns:
        tuple: 成功时返回 (taskid, method, churl, tweeturl, dltype, data, filename, recent_files_append)
        None: 没有任务或处理失败时返回None

    错误处理：
        - repeat: 任务重复
        - config_error: 配置参数错误
        - not_support: 不支持的域名
    """
    # 获取最旧的JSON任务文件
    json_entry = _get_oldest_json_file()
    if not json_entry:
        return None

    # 短暂延迟，确保文件写入完成
    time.sleep(1)

    # 加载任务数据
    data = _load_task_data(json_entry.path)
    if not data:
        return None

    # 提取任务参数
    params = _extract_task_parameters(data)

    # 生成检查链接和捕获时间
    checklink = params['tweeturl'] if params['tweeturl'] else params['churl']
    capture_time = datetime.now(timezone.utc).strftime('%a %b %d %H:%M:%S +0000 %Y')

    # 检查任务重复性
    rep = process_json(json_entry.name, params['taskid'], checklink)

    if rep.get('repeat'):
        # 任务重复，记录错误
        _create_error_response(data, json_entry.name, rep.get('repeat'), capture_time)
        return None

    # 验证任务参数
    is_valid, error_type = _validate_task_parameters(params)

    if not is_valid:
        # 参数无效，记录错误
        _create_error_response(data, json_entry.name, error_type, capture_time)
        return None

    # 任务有效，返回参数
    return (
        params['taskid'],
        params['method'],
        params['churl'],
        params['tweeturl'],
        params['dltype'],
        data,
        json_entry.name,
        rep.get('recent_files_append')
    )


def generate_names(filename):
    ti = str(time.time())
    file_name = f"website_task-{filename.split('_')[3]}-{deviceid}-{pgmid}-{ti[:10]}-{ti.split('.')[-1][:3]}.bcp"
    zip_file_name = f"website-{filename.split('_')[3]}-{deviceid}-{pgmid}-{ti[:10]}-{ti.split('.')[-1][:3]}.zip"
    return file_name, zip_file_name


def createerrorlogfile(jsontext, filename, data, noresult):
    file_name, zip_file_name = generate_names(filename)
    file_path = Path(zip_file_path) / file_name
    with file_path.open('w', encoding='utf-8') as f:
        line = json.dumps(dict(jsontext), ensure_ascii=False) + "\n"
        f.write(line)

    zip_path = Path(zip_file_path) / zip_file_name
    with zipfile.ZipFile(zip_path, 'a', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write(file_path, file_name)
    file_path.unlink()

    dest_zip_path = Path(dest_zip_file_path) / zip_file_name
    shutil.move(zip_path, dest_zip_path) if platform.system() == 'Windows' else subprocess.call(
        ['mv', zip_path, dest_zip_path])

    taskdesc = data.get('tasklist', [{}])[0]
    taskjson = {
        'taskfile': filename,
        'taskid': taskdesc.get('taskid', ''),
        'app': taskdesc.get('app', ''),
        'method': taskdesc.get('method', ''),
        'churl': taskdesc.get('churl', ''),
        'dltype': taskdesc.get('dltype', ''),
        'count': 0,
        'isnoresult': noresult,
        'zipfilename': zip_file_name,
        'endtime': time.strftime('%Y-%m-%d %H:%M:%S'),
        'costtime': int(time.time()) - int(filename.split('_')[-2]),
        'elapsedtime': -1,
        'error_count': -1
    }
    taskjson_str = json.dumps(taskjson)
    log_file = 'task.log'
    with open(log_file, 'a') as file:
        file.write(taskjson_str + '\n')
    old_file_path = os.path.join(folder_path, filename)
    new_file_path = os.path.join(processed_path, filename)
    shutil.move(old_file_path, new_file_path) if platform.system() == 'Windows' else subprocess.call(
        ['mv', old_file_path, new_file_path])


def process_json(filename, task_id, checklink):
    recentfiles = []
    infofile = 'info.json'
    if os.path.exists(infofile) and os.path.getsize(infofile) != 0:
        with open(infofile) as fi:
            recentfiles = json.load(fi)
    cutoff_time = datetime.now() - timedelta(minutes=60)
    last_taskid = recentfiles[-1].get('task_id', '') if recentfiles else ''
    recentfiles = [recent_file for recent_file in recentfiles if
                   datetime.strptime(recent_file['timestamp'], '%Y-%m-%d %H:%M:%S') > cutoff_time]

    filename_set = set()
    task_id_set = set()
    checklink_set = set()
    recentfiles_append = {}
    for recent_file in recentfiles:
        filename_set.add(recent_file.get('filename', ''))
        task_id_set.add(recent_file.get('task_id', ''))
        checklink_set.add(recent_file.get('checklink', ''))
    if task_id == last_taskid:
        repeat = 'unknown_error'
    elif filename and (filename in filename_set):
        repeat = 'duplicate_filename'
    elif task_id and (task_id in task_id_set):
        repeat = 'duplicate_taskid'
    # elif checklink and (checklink in checklink_set):
    #     repeat = 'duplicate_content'
    else:
        repeat = False
        recentfiles_append = {
            'filename': filename,
            'checklink': checklink,
            'task_id': task_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    repe = {'repeat': repeat, 'recent_files_append': recentfiles_append}

    if recentfiles_append:
        recentfiles.append(recentfiles_append)
        with open('info.json', 'w') as f:
            json.dump(recentfiles, f)

    return repe


def update_ch_urls(redis_conn, proname, link_hash, new_ch_url):
    key = f'{proname}_hash_done_urls'
    ch_urls_json = redis_conn.hget(key, link_hash)
    ch_urls = set(json.loads(ch_urls_json)) if ch_urls_json else set()
    original_size = len(ch_urls)
    ch_urls.add(new_ch_url)
    if len(ch_urls) > original_size:
        redis_conn.hset(key, link_hash, json.dumps(list(ch_urls)))


def extract_email_from_js(js_code):
    import execjs
    email_var_name = None
    email_code_lines = []
    for line in js_code.split('\n'):
        if 'var ' in line or '=' in line:
            if 'document.getElementById' not in line:
                email_code_lines.append(line.strip())
                match = re.search(r'var (addy\w+)', line)
                if match:
                    email_var_name = match.group(1)

    if not email_var_name:
        return "Email variable name not found."

    get_email_function = f"""
    function getEmail() {{
        {' '.join(email_code_lines)}
        return {email_var_name};
    }}
    """

    ctx = execjs.compile(get_email_function)
    email_encoded = ctx.call("getEmail")

    email_decoded = execjs.eval(f"decodeURIComponent(escape('{email_encoded}'))")
    decoded_email = html.unescape(email_decoded)

    return decoded_email


def replace_encrypted_emails_with_script(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    script_tags = soup.find_all('script')
    for script in script_tags:
        if 'document.getElementById' in script.text and 'addy' in script.text:
            decrypted_email = extract_email_from_js(script.text)
            cloak_id_match = re.search(r"document.getElementById\('([^']+)'\)", script.text)
            if cloak_id_match:
                cloak_id = cloak_id_match.group(1)
                cloak_tag = soup.find(id=cloak_id)
                if cloak_tag:
                    new_tag = soup.new_tag("a", href=f"mailto:{decrypted_email}")
                    new_tag.string = decrypted_email
                    cloak_tag.replace_with(new_tag)
                    script.decompose()
    return str(soup)


def decrypt_email(encoded_email):
    # 根据 Cloudflare 的编码格式解密电子邮件
    decoded_chars = []
    key = int(encoded_email[0:2], 16)  # 获取前两个字符的十六进制值
    for i in range(2, len(encoded_email), 2):
        char_code = int(encoded_email[i:i + 2], 16) ^ key
        decoded_chars.append(chr(char_code))
    return ''.join(decoded_chars)


# 处理网页中的电子邮件
def process_emails(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    email_elements = soup.select("span.__cf_email__, a.__cf_email__")  # 找到所有具有 __cf_email__ 类的元素

    for element in email_elements:
        encoded_email = element['data-cfemail']
        decoded_email = decrypt_email(encoded_email)  # 解密邮件地址
        mailto_link = f"mailto:{decoded_email}"

        # 替换元素内容为可点击的链接
        new_tag = soup.new_tag("a", href=mailto_link)
        new_tag.string = decoded_email
        element.replace_with(new_tag)  # 替换原元素

    return str(soup)


def detect_language(dtext, max_length=1000):
    from py3langid import langid
    try:
        if len(dtext) > max_length:
            dtext = dtext[:max_length]
        lang, _ = langid.classify(dtext)
        if lang == 'dz':
            lang = 'bo'
        return lang
    except Exception as e:
        print(f"Error in language detection: {e}")
        return 'und'


def extract_segment_from_url(url, segment_index=-1):
    parsed_url = urlparse(url)

    path_segments = parsed_url.path.strip('/').split('/')

    if -len(path_segments) <= segment_index < len(path_segments):
        return path_segments[segment_index]
    else:
        return ''


def increment_url(url):
    try:
        pattern = re.compile(r'(.*\D)(\d+)(\D*)$')

        match = pattern.match(url)
        if not match:
            logging.info("URL中没有可递增的数字部分")
            return ''

        prefix = match.group(1)
        number = match.group(2)
        suffix = match.group(3)

        incremented_number = int(number) + 1

        new_url = f"{prefix}{incremented_number}{suffix}"
        return new_url
    except Exception as e:
        logging.error(f'increment_url:::{e}')
        return ''


def decode_base32(data):
    missing_padding = len(data) % 8
    if missing_padding:
        data += '=' * (8 - missing_padding)
    return int.from_bytes(base64.b32decode(data), byteorder='big')


def sort_and_replace_p_tags(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    article_body = soup.find('article', {'class': 'article-body'})

    if not article_body:
        return html_content

    p_tags_with_data_s = []
    p_tags_without_data_s = []

    for p in article_body.find_all('p'):
        data_s = p.get('data-s')
        if data_s:
            try:
                decoded_value = decode_base32(data_s[3:])
                p_tags_with_data_s.append((decoded_value, p))
            except Exception as e:
                logging.error(f"decode_base32 error: {e}")
                p_tags_without_data_s.append(p)
        else:
            p_tags_without_data_s.append(p)

    if not p_tags_with_data_s:
        return html_content

    p_tags_with_data_s.sort(key=lambda x: x[0])

    for p in article_body.find_all('p'):
        p.extract()

    for _, p_tag in p_tags_with_data_s:
        article_body.append(p_tag)

    for p_tag in p_tags_without_data_s:
        article_body.append(p_tag)

    return str(soup)


def remove_font_tags(text: str) -> str:
    # 使用正则表达式匹配并去除<font>标签及其内容
    cleaned_text = re.sub(r'<font[^>]*>.*?</font>', '', text)
    return cleaned_text.strip()  # 去除前后空白


def generate_uuid():
    def e():
        return format(random.randint(0, 0xffff), '04x')

    return f"{e()}{e()}-{e()}-{e()}-{e()}-{e()}{e()}{e()}"


def hash_with_bcrypt(input_str, salt='$2a$10$HxyKf0Cy3Ecnp874AXBXOe'):
    input_bytes = input_str.encode('utf-8')
    salt = salt.encode()
    return bcrypt.hashpw(input_bytes, salt)
