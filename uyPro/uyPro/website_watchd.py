import configparser
import json
import logging
import os
import platform
import shutil
import subprocess
import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from urllib.parse import urlparse
import sys

if platform.system() != 'Windows':
    sys.path.append(os.path.abspath('/zhuoyue/website/uyPro'))

from uyPro.settings import deviceid, pgmid, processed_path
from uyPro.spiders.utils import createerrorlogfile


class MyLogger:
    _logger = None

    @classmethod
    def get_logger(cls, name, mfile):
        if cls._logger is None:
            cls._logger = logging.getLogger(name)
            cls._logger.setLevel(logging.INFO)
            handler = logging.FileHandler(mfile)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            cls._logger.addHandler(handler)
        return cls._logger


my_logger = MyLogger.get_logger('mylogger', 'watchdog_scrapy.log')


def notempty_error():
    if len(os.listdir(folder_path)) != 0:
        json_folder_entries = sorted(
            (entry for entry in os.scandir(folder_path) if entry.is_file() and entry.name.endswith('.json')),
            key=lambda entry: entry.stat().st_ctime)
        for njson_entry in json_folder_entries:
            with open(njson_entry.path, encoding='utf-8') as f:
                ndata = json.load(f)
            taskid = ndata.get('tasklist', [{}])[0].get('taskid', '').strip()
            jsontext = {"taskid": taskid, "count": 0, "deviceid": deviceid, "pgmid": pgmid,
                        "noresult": "unknown_error"}
            noresult = "unknown_error"
            my_logger.info(f'An unknown error occurred with file {njson_entry.name}, taskid is {taskid}')
            createerrorlogfile(jsontext, njson_entry.name, ndata, noresult)


def begincrawl(defaultsite='uyghuraa'):
    json_entries = sorted((entry for entry in os.scandir(input_path) if
                           entry.is_file() and entry.name.endswith('.json') and 'realtime' in entry.name),
                          key=lambda entry: entry.stat().st_ctime)
    if len(json_entries) == 0:
        json_entries = sorted(
            (entry for entry in os.scandir(input_path) if entry.is_file() and entry.name.endswith('.json')),
            key=lambda entry: entry.stat().st_ctime)
    json_entry = json_entries[0]
    if os.path.getsize(json_entry.path) > 0:
        with open(json_entry.path, encoding='utf-8') as f:
            data = json.load(f)
        new_file_path = os.path.join(folder_path, json_entry.name)
        shutil.move(json_entry.path, new_file_path) if platform.system() == 'Windows' else subprocess.call(
            ['mv', json_entry.path, new_file_path])
        my_logger.info("Folder is not empty. Restarting scrapy.")
        churl = data.get('tasklist', [{}])[0].get('churl', '').strip()
        if churl:
            domain = urlparse(churl).netloc
            with open("spider_mapping.json", encoding='utf-8') as file:
                spider_mapping = json.load(file)
            spider_name = next((value for key, value in spider_mapping.items() if key in domain), None)
            subprocess.run(['scrapy', 'crawl', spider_name]) if spider_name else subprocess.run(
                ['scrapy', 'crawl', defaultsite])
        else:
            subprocess.run(['scrapy', 'crawl', defaultsite])
    else:
        my_logger.info(f"{json_entry.name} is empty!!")
        new_file_path = os.path.join(processed_path, json_entry.name)
        shutil.move(json_entry.path, new_file_path) if platform.system() == 'Windows' else subprocess.call(
            ['mv', json_entry.path, new_file_path])


class WatchdogHandler(FileSystemEventHandler):

    def on_any_event(self, event):
        if event.is_directory:
            return None
        if event.event_type == 'created':
            notempty_error()
            my_logger.info(f"File {event.src_path} was {event.event_type}, restarting")
            time.sleep(1)
            begincrawl()


if __name__ == "__main__":
    my_logger.info("Observer Started")
    event_handler = WatchdogHandler()
    observer = Observer()
    config_file = 'configwin.ini' if platform.system() == 'Windows' else 'configlinux.ini'
    config = configparser.ConfigParser()
    config.read(config_file)
    input_path = config.get('DEFAULT', 'input_path')
    folder_path = config.get('DEFAULT', 'folder_path')

    while True:
        notempty_error()
        if len(os.listdir(input_path)) == 0:
            my_logger.info("Folder is empty. Exiting.")
            break
        begincrawl()
        time.sleep(1)
        if len(os.listdir(input_path)) > 0:
            my_logger.warning("Files still present in folder. Restarting.")
        else:
            my_logger.info("All files processed. Exiting.")
            break

    observer.schedule(event_handler, path=input_path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except Exception as e:
        my_logger.error(f"Exception occurred {e}", exc_info=True)
        observer.stop()
        my_logger.info("Observer Stopped")
    observer.join()
