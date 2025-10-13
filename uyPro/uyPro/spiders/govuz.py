import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class GovuzSpider(scrapy.Spider):
    name = "govuz"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
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

    def start_requests(self):
        homepage = ''
        try:
            taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = start_spider()
            # taskid, method, churl, tweeturl, dltype, inputdata, inputfilename, recent_files_append = (
            #     '45ca39c6ebcfa6449f672481fc4a084b_1705450920', 'getchannel', '', '', 'full', '', '1_1_1_1', '')
            # churl = 'https://gov.uz/uz/iiv/news/news'
            # inputdata = {}
            # tweeturl = 'https://www.ptv.com.pk/ptvNews/urduNewsDetail/79254'
            self.taskid = taskid
            self.bid = inputfilename.split('_')[3]
            self.crawler.stats.set_value('inputdata', inputdata)
            self.crawler.stats.set_value('inputfilename', inputfilename)
            self.crawler.stats.set_value('recent_files_append', recent_files_append)
            self.inc = False if dltype == 'full' else True
            if homepage:
                yield scrapy.Request(url=homepage, callback=self.parse)
            elif method == 'getchannel':
                yield scrapy.Request(url=f'{churl}?page=1', callback=self.parse_sec, meta={'ch_url': churl})
            else:
                # gettweet
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://gov.uz/uz/iiv/news/news',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        match = response.xpath('//script').re_first(r'\\"data\\":\[(.*?)\],\\"total_page\\"')
        if not match:
            logging.warning(f"未找到数据匹配: {ch_url}")
            return

        data_str = "[" + match.strip() + "]"

        try:
            import ast
            import re
            cleaned_data = data_str.replace('\\"', '"')
            fixed_data = re.sub(r'\\"([^"]*)\\"', r"'\1'", cleaned_data)

            try:
                data_list = json.loads(fixed_data)
                logging.info(f"JSON解析成功，获得 {len(data_list)} 条记录")
            except json.JSONDecodeError as json_err:
                logging.warning(f"JSON解析失败，尝试更激进的修复: {json_err}")

                try:
                    strategy1_data = fixed_data.replace('\\', '')
                    data_list = json.loads(strategy1_data)
                    logging.info(f"策略1修复成功，获得 {len(data_list)} 条记录")
                except json.JSONDecodeError:
                    try:
                        data_list = ast.literal_eval(fixed_data)
                        logging.info(f"AST解析成功，获得 {len(data_list)} 条记录")
                    except (ValueError, SyntaxError) as ast_err:
                        logging.error(f"所有解析方法都失败了: {ast_err}")
                        error_pos = getattr(json_err, 'pos', 0)
                        logging.error(f"JSON错误位置: {error_pos}")
                        logging.error(f"错误附近的数据: ...{fixed_data[max(0, error_pos-100):error_pos+100]}...")

                        try:
                            with open('debug_json_error.txt', 'w', encoding='utf-8') as f:
                                f.write(f"错误位置: {error_pos}\n")
                                f.write(f"URL: {ch_url}\n")
                                f.write(f"原始数据:\n{data_str}\n")
                                f.write(f"清理后数据:\n{cleaned_data}\n")
                                f.write(f"修复后数据:\n{fixed_data}\n")
                            logging.info("问题数据已保存到 debug_json_error.txt")
                        except Exception as save_err:
                            logging.warning(f"无法保存调试文件: {save_err}")
                        return

        except Exception as e:
            logging.error(f"数据解析发生未知错误: {e}")
            logging.error(f"原始数据长度: {len(data_str)}")
            return
        for data in data_list:
            if not data:
                continue
            _id = data.get('id')
            if not _id:
                continue
            link = f'https://gov.uz/uz/iiv/news/view/{_id}'
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
                # print(link)
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        next_url = 'https://api-portal.gov.uz/authorities/news/category?code_name=news&page=2'
        if next_url and if_new:
            headers = {"accept": "*/*", "code": "iiv"}
            yield response.follow(url=next_url, callback=self.parse_trd, headers=headers, meta={
                'ch_url': ch_url, 'page': 3})

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        page = response.meta['page']
        data_list = response.json().get('data')
        for data in data_list:
            if not data:
                continue
            _id = data.get('id')
            if not _id:
                continue
            link = f'https://gov.uz/uz/iiv/news/view/{_id}'
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
                # print(link)
                yield response.follow(link, callback=self.article, meta={'ch_url': ch_url, 'link': link})

        next_url = f'https://api-portal.gov.uz/authorities/news/category?code_name=news&page={page}'
        if next_url and if_new:
            headers = {"accept": "*/*", "code": "iiv"}
            yield response.follow(url=next_url, callback=self.parse_trd, headers=headers, meta={
                'ch_url': ch_url, 'page': page + 1})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        lang = 'uz'
        item['tweet_lang'] = lang
        item['taskid'] = self.taskid
        item['bid'] = self.bid
        tweet_func = get_map(response.url)
        if tweet_func:
            item = tweet_func(response, item)
            if item:
                link_hash = hashlib.sha1(link.encode()).hexdigest()
                if not item.get('tweet_content') or item.get('tweet_content_tslt') or lang == 'zh':
                    update_ch_urls(self.redis_conn, self.proname, link_hash, item['ch_url'])
                yield item
