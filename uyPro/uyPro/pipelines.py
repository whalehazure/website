#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UyPro新闻爬虫系统 - 数据处理管道模块

本模块定义了Scrapy数据处理管道，负责处理爬取到的数据项，包括：
- 数据验证和清洗
- 文件下载和存储
- 数据格式转换
- 日志记录和监控
- 文件压缩和归档

主要管道类：
1. UyproPipeline: 主要数据处理管道
2. UyproFilesPipeline: 文件下载管道
3. 日志处理函数

数据流程：
爬虫数据 → 数据验证 → 文件下载 → 格式转换 → 存储 → 压缩归档


参考文档:
- https://docs.scrapy.org/en/latest/topics/item-pipeline.html
"""

# ==================== 标准库导入 ====================
import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import time
import datetime
from zipfile import ZipFile

# ==================== 第三方库导入 ====================
import scrapy
from itemadapter import ItemAdapter
from scrapy.pipelines.files import FilesPipeline
from scrapy.utils.python import to_bytes
from logging.handlers import RotatingFileHandler

# ==================== 项目内部导入 ====================
from uyPro.settings import (
    dest_zip_file_path, zip_file_path, deviceid, pgmid,
    file_dir, processed_path, folder_path
)

# ==================== 日志处理函数 ====================


def log_task_info(taskjson, taskfile=None):
    """
    记录任务信息到日志文件

    将任务执行信息以JSON格式记录到指定的日志文件中，
    用于任务监控、统计和问题排查。

    Args:
        taskjson (dict): 任务信息字典，包含任务详细数据
        taskfile (str, optional): 日志文件路径，默认为None时使用'task.log'

    功能:
        - 创建轮转日志处理器（最大5MB，保留3个备份）
        - 以JSON格式记录任务信息
        - 自动处理日志文件轮转
        - 使用UTF-8编码确保中文正常显示

    日志格式:
        每条日志包含完整的任务JSON数据，便于后续分析和处理

    Examples:
        >>> task_data = {
        ...     'task_id': 'task_001',
        ...     'spider': 'jpost',
        ...     'items_count': 10,
        ...     'status': 'completed'
        ... }
        >>> log_task_info(task_data, 'custom_task.log')
    """
    logger = logging.getLogger()
    rotating_file_log = RotatingFileHandler(taskfile, maxBytes=1024 * 1024 * 5, backupCount=3, encoding='utf-8')
    logger.addHandler(rotating_file_log)
    logger.info(taskjson)
    logger.removeHandler(rotating_file_log)


def compare_time_strings(time_str1, time_str2):
    try:
        time_format = '%a %b %d %H:%M:%S %z %Y'
        time_obj1 = datetime.datetime.strptime(time_str1, time_format)
        time_obj2 = datetime.datetime.strptime(time_str2, time_format)
        return time_obj1 > time_obj2
    except Exception as e:
        logging.error(e)
        return False


class CustomFilesPipeline(FilesPipeline):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.finish_count = 0
        self.data_list = []
        self.data_ch_list = []
        self.comment_list = []  # 存储评论数据

    def get_media_requests(self, item, info):
        for img_url in item.get("tweet_img_url", []):
            if img_url and ('https://image.storm.mg' in img_url):
                yield scrapy.Request(img_url,
                                     meta={'type': 'jpg', 'item': item, "download_timeout": 10, "dont_retry": True})
            elif img_url and ('http' in img_url):
                yield scrapy.Request(img_url,
                                     meta={'type': 'jpg', 'item': item, "download_timeout": 10, "dont_retry": True,
                                           'dont_redirect': True})
        for pdf_url in item.get("tweet_pdf_url", []):
            if pdf_url:
                yield scrapy.Request(pdf_url,
                                     meta={'type': 'pdf', 'item': item, "download_timeout": 20, "dont_retry": True})

    def file_path(self, request, response=None, info=None, *, item=None):
        file_type = request.meta['type']
        name = hashlib.sha1(to_bytes(request.url)).hexdigest()
        return f'{file_type}/{name}.{file_type}'

    def item_completed(self, results, item, info):
        if not item.get('tweet_img'):
            item['tweet_img'] = [x['path'].split("/")[-1] for ok, x in results if ok and x['path'].startswith('jpg/')]
        item['tweet_pdf'] = [x['path'].split("/")[-1] for ok, x in results if ok and x['path'].startswith('pdf/')]
        item['deviceid'] = deviceid
        item['pgmid'] = pgmid
        item['capture_time'] = datetime.datetime.utcnow().strftime('%a %b %d %H:%M:%S +0000 %Y')
        if item.get('tweet_createtime', '') and compare_time_strings(item.get('tweet_createtime', ''),
                                                                     item['capture_time']):
            logging.error(f"tweet_createtime:{item.get('tweet_createtime', '')} > capture_time:{item['capture_time']}")
            item['tweet_createtime'] = item['capture_time']
        bid = item['bid']
        adapter = ItemAdapter(item)

        # 处理评论数据
        if adapter.get("tweet_comments"):
            comments = adapter.get("tweet_comments")
            self.comment_list.extend(comments)
            logging.info(f"添加 {len(comments)} 条评论到评论列表")
        if adapter.get("tweet_url", ''):
            data = {}
            for field in ["ch_url", "tweet_id", "tweet_title", "tweet_title_tslt", "tweet_url", "tweet_content",
                          "tweet_url_original", "tweet_content_tslt", "tweet_author", "tweet_createtime",
                          "tweet_createtime_original", "tweet_createtime_str", "tweet_img",
                          "tweet_lang", "tweet_pdf", "tweet_video", "tweet_table", "taskid", "deviceid", "pgmid",
                          "capture_time"]:
                data[field] = adapter.get(field, '')
            data = {k: v for k, v in data.items() if v is not None and v != "" and v != [] and v != {}}
            self.data_list.append(data)
            self.finish_count += 1
            data = {}
            for field in ["ch_url", "tweet_id", "taskid", "deviceid", "pgmid", "capture_time"]:
                data[field] = adapter.get(field, '')
            data = {k: v for k, v in data.items() if v is not None and v != "" and v != [] and v != {}}
            self.data_ch_list.append(data)
            self.finish_count += 1
        elif adapter.get("tweet_id", ''):
            data = {}
            for field in ["ch_url", "tweet_id", "taskid", "deviceid", "pgmid", "capture_time"]:
                data[field] = adapter.get(field, '')
            data = {k: v for k, v in data.items() if v is not None and v != "" and v != [] and v != {}}
            self.data_ch_list.append(data)
            self.finish_count += 1

        if len(self.data_list) >= 20:
            elements = self.data_list[:20]
            self.data_list = self.data_list[20:]
            ch_elements = self.data_ch_list
            self.data_ch_list = []
            comment_elements = self.comment_list
            self.comment_list = []
            tim = str(time.time())
            zipname = f"website-{bid}-{deviceid}-{pgmid}-{tim[:10]}-{tim.split('.')[-1][:3]}.zip"
            zip_path = os.path.join(zip_file_path, zipname)
            json_name = f"website_tweet-{bid}-{deviceid}-{pgmid}-{tim[:10]}-{tim.split('.')[-1][:3]}.bcp"
            json_path = os.path.join(zip_file_path, f'{json_name}')
            json_ch_name = f"website_channel-{bid}-{deviceid}-{pgmid}-{tim[:10]}-{tim.split('.')[-1][:3]}.bcp"
            json_ch_path = os.path.join(zip_file_path, f'{json_ch_name}')

            # 生成评论 BCP 文件（只在有评论时）
            comment_path = ''
            if comment_elements:
                comment_name = f"website_tc-{bid}-{deviceid}-{tim[:10]}-{tim.split('.')[-1][:3]}.bcp"
                comment_path = os.path.join(zip_file_path, f'{comment_name}')

            with open(json_path, "w", encoding='utf-8') as f:
                for element in elements:
                    json_data = json.dumps(element, ensure_ascii=False) + "\n"
                    f.write(json_data)

            with open(json_ch_path, "w", encoding='utf-8') as f:
                for ch_element in ch_elements:
                    json_data = json.dumps(ch_element, ensure_ascii=False) + "\n"
                    f.write(json_data)

            # 写入评论数据（只在有评论且路径已生成时）
            if comment_elements and comment_path:
                with open(comment_path, "w", encoding='utf-8') as f:
                    for comment in comment_elements:
                        # 每行一个 JSON 对象
                        json_data = json.dumps(comment, ensure_ascii=False) + "\n"
                        f.write(json_data)
                logging.info(f"生成评论 BCP 文件: {os.path.basename(comment_path)}, 共 {len(comment_elements)} 条评论")

            files_path = []
            for element in elements:
                for tweet_img in element.get('tweet_img', []):
                    files_path.append(os.path.join(f'{file_dir}/jpg', tweet_img))
                for tweet_pdf in element.get('tweet_pdf', []):
                    files_path.append(os.path.join(f'{file_dir}/pdf', tweet_pdf))
                for tweet_table in element.get('tweet_table', []):
                    files_path.append(os.path.join(f'{file_dir}/csv', tweet_table))
            files_path = list(set(files_path))
            with ZipFile(zip_path, "w") as zipfile:
                zipfile.write(json_path, os.path.basename(json_path))
                zipfile.write(json_ch_path, os.path.basename(json_ch_path))
                # 添加评论 BCP 文件到 zip（只在有评论且文件存在时）
                if comment_path and os.path.exists(comment_path):
                    zipfile.write(comment_path, os.path.basename(comment_path))
                if files_path:
                    for path in files_path:
                        zipfile.write(path, os.path.basename(path))
            os.remove(json_path)
            os.remove(json_ch_path)
            # 删除评论 BCP 文件（只在文件存在时）
            if comment_path and os.path.exists(comment_path):
                os.remove(comment_path)
            dest_zip_path = os.path.join(dest_zip_file_path, zipname)
            shutil.move(zip_path, dest_zip_path) if platform.system() == 'Windows' else subprocess.call(
                ['mv', zip_path, dest_zip_path])

        return item

    def close_spider(self, spider):
        inputdata = spider.crawler.stats.get_value('inputdata')
        if inputdata:
            taskid = inputdata.get('tasklist', [{}])[0].get('taskid', '').strip()
            inputfilename = spider.crawler.stats.get_value('inputfilename')
            bid = inputfilename.split('_')[3]
            tim = str(time.time())
            zipname = f"website-{bid}-{deviceid}-{pgmid}-{tim[:10]}-{tim.split('.')[-1][:3]}.zip"
            zip_path = os.path.join(zip_file_path, f'{zipname}')
            files_path = []
            json_path = ''
            json_ch_path = ''
            if self.data_list:
                json_name = f"website_tweet-{bid}-{deviceid}-{pgmid}-{tim[:10]}-{tim.split('.')[-1][:3]}.bcp"
                json_path = os.path.join(zip_file_path, f'{json_name}')
                with open(json_path, "w", encoding='utf-8') as f:
                    for element in self.data_list:
                        json_data = json.dumps(element, ensure_ascii=False) + "\n"
                        f.write(json_data)
                for element in self.data_list:
                    for tweet_img in element.get('tweet_img', []):
                        files_path.append(os.path.join(f'{file_dir}/jpg', tweet_img))
                    for tweet_pdf in element.get('tweet_pdf', []):
                        files_path.append(os.path.join(f'{file_dir}/pdf', tweet_pdf))
                    for tweet_table in element.get('tweet_table', []):
                        files_path.append(os.path.join(f'{file_dir}/csv', tweet_table))
            if self.data_ch_list:
                json_ch_name = f"website_channel-{bid}-{deviceid}-{pgmid}-{tim[:10]}-{tim.split('.')[-1][:3]}.bcp"
                json_ch_path = os.path.join(zip_file_path, f'{json_ch_name}')
                with open(json_ch_path, "w", encoding='utf-8') as f:
                    for ch_element in self.data_ch_list:
                        json_data = json.dumps(ch_element, ensure_ascii=False) + "\n"
                        f.write(json_data)

            # 处理剩余的评论数据（只在有评论时）
            comment_path = ''
            if self.comment_list:
                comment_name = f"website_tc-{bid}-{deviceid}-{tim[:10]}-{tim.split('.')[-1][:3]}.bcp"
                comment_path = os.path.join(zip_file_path, f'{comment_name}')
                with open(comment_path, "w", encoding='utf-8') as f:
                    for comment in self.comment_list:
                        # 每行一个 JSON 对象
                        json_data = json.dumps(comment, ensure_ascii=False) + "\n"
                        f.write(json_data)
                logging.info(f"close_spider: 生成评论 BCP 文件: {comment_name}, 共 {len(self.comment_list)} 条评论")

            taskname = f"website_task-{bid}-{deviceid}-{pgmid}-{tim[:10]}-{tim.split('.')[-1][:3]}.bcp"
            task_path = os.path.join(zip_file_path, f'{taskname}')
            noresult = False if self.finish_count else True
            capture_time = datetime.datetime.utcnow().strftime('%a %b %d %H:%M:%S +0000 %Y')
            task_text = {"taskid": taskid, "count": self.finish_count, "deviceid": deviceid,
                         "pgmid": pgmid, "capture_time": capture_time, "noresult": noresult}
            with open(task_path, 'w', encoding='utf-8') as f:
                lin = json.dumps(dict(task_text), ensure_ascii=False) + "\n"
                f.write(lin)
            files_path = list(set(files_path))
            with ZipFile(zip_path, "w") as zipfile:
                if json_path:
                    zipfile.write(json_path, os.path.basename(json_path))
                    if files_path:
                        for path in files_path:
                            zipfile.write(path, os.path.basename(path))
                if json_ch_path:
                    zipfile.write(json_ch_path, os.path.basename(json_ch_path))
                # 添加评论 BCP 文件到 zip
                if comment_path and os.path.exists(comment_path):
                    zipfile.write(comment_path, os.path.basename(comment_path))
                zipfile.write(task_path, os.path.basename(task_path))
            if json_path:
                os.remove(json_path)
            if json_ch_path:
                os.remove(json_ch_path)
            # 删除评论 BCP 文件
            if comment_path and os.path.exists(comment_path):
                os.remove(comment_path)
            os.remove(task_path)
            dest_zip_path = os.path.join(dest_zip_file_path, zipname)
            shutil.move(zip_path, dest_zip_path) if platform.system() == 'Windows' else subprocess.call(
                ['mv', zip_path, dest_zip_path])

            taskdesc = inputdata.get('tasklist', [{}])[0]
            end_time = datetime.datetime.now(datetime.timezone.utc)
            start_time = spider.crawler.stats.get_value('start_time')
            error_count = spider.crawler.stats.get_value('log_count/ERROR', 0)
            taskjson = {
                'taskfile': inputfilename,
                'taskid': taskid,
                'app': taskdesc.get('app', ''),
                'method': taskdesc.get('method', ''),
                'churl': taskdesc.get('churl', ''),
                'dltype': taskdesc.get('dltype', ''),
                'count': self.finish_count,
                'isnoresult': noresult,
                'zipfilename': zipname,
                'endtime': time.strftime('%Y-%m-%d %H:%M:%S'),
                'costtime': int(tim[:10]) - int(inputfilename.split('_')[-2]),
                'elapsedtime': round((end_time - start_time).total_seconds(), 1),
                'error_count': error_count
            }
            log_task_info(taskjson, 'task.log')
            old_file_path = os.path.join(folder_path, inputfilename)
            new_file_path = os.path.join(processed_path, inputfilename)
            shutil.move(old_file_path, new_file_path) if platform.system() == 'Windows' else subprocess.call(
                ['mv', old_file_path, new_file_path])
