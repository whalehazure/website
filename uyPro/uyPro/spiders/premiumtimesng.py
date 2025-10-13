import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class PremiumtimesngSpider(scrapy.Spider):
    name = "premiumtimesng"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
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
            # churl = 'https://www.premiumtimesng.com/category/news/more-news'
            # inputdata = {}
            # tweeturl = 'https://www.epochtimes.com/gb/24/10/7/n14345827.htm'
            self.taskid = taskid
            self.bid = inputfilename.split('_')[3]
            self.crawler.stats.set_value('inputdata', inputdata)
            self.crawler.stats.set_value('inputfilename', inputfilename)
            self.crawler.stats.set_value('recent_files_append', recent_files_append)
            self.inc = False if dltype == 'full' else True
            if homepage:
                yield scrapy.Request(url=homepage, callback=self.parse)
            elif method == 'getchannel':
                yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl})
            else:
                # gettweet
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://www.premiumtimesng.com/category/news/headlines',
            'https://www.premiumtimesng.com/category/news/top-news',
            'https://www.premiumtimesng.com/category/news/more-news',
            'https://www.premiumtimesng.com/category/opinion',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath(
            "//article//div[@class='jeg_postblock_content']//*[@class='jeg_post_title']/a/@href").getall()
        for link in links:
            if not link:
                continue
            # link = response.urljoin(link)
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

        script_content = response.xpath('//script')
        include_category = script_content.re_first(r',"include_category":(\d+),')
        current_page = 2
        if if_new and include_category:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            data = (f'lang=en_GB&action=jnews_module_ajax_jnews_block_5&module=true&data%5Bfilter%5D=0&data'
                    f'%5Bfilter_type%5D=all&data%5Bcurrent_page%5D={current_page}&data%5Battribute%5D%5Bheader_icon'
                    f'%5D=&data'
                    f'%5Battribute%5D%5Bfirst_title%5D=&data%5Battribute%5D%5Bsecond_title%5D=&data%5Battribute%5D'
                    f'%5Burl%5D=&data%5Battribute%5D%5Bheader_type%5D=heading_6&data%5Battribute%5D'
                    f'%5Bheader_background%5D=&data%5Battribute%5D%5Bheader_secondary_background%5D=&data%5Battribute'
                    f'%5D%5Bheader_text_color%5D=&data%5Battribute%5D%5Bheader_line_color%5D=&data%5Battribute%5D'
                    f'%5Bheader_accent_color%5D=&data%5Battribute%5D%5Bheader_filter_category%5D=&data%5Battribute%5D'
                    f'%5Bheader_filter_author%5D=&data%5Battribute%5D%5Bheader_filter_tag%5D=&data%5Battribute%5D'
                    f'%5Bheader_filter_text%5D=All&data%5Battribute%5D%5Bsticky_post%5D=false&data%5Battribute%5D'
                    f'%5Bpost_type%5D=post&data%5Battribute%5D%5Bcontent_type%5D=all&data%5Battribute%5D%5Bsponsor%5D'
                    f'=false&data%5Battribute%5D%5Bnumber_post%5D=25&data%5Battribute%5D%5Bpost_offset%5D=3&data'
                    f'%5Battribute%5D%5Bunique_content%5D=disable&data%5Battribute%5D%5Binclude_post%5D=&data'
                    f'%5Battribute%5D%5Bincluded_only%5D=false&data%5Battribute%5D%5Bexclude_post%5D=&data'
                    f'%5Battribute%5D%5Binclude_category%5D={include_category}&data%5Battribute%5D%5Bexclude_category'
                    f'%5D=&data'
                    f'%5Battribute%5D%5Binclude_author%5D=&data%5Battribute%5D%5Binclude_tag%5D=&data%5Battribute%5D'
                    f'%5Bexclude_tag%5D=&data%5Battribute%5D%5Bsort_by%5D=latest&data%5Battribute%5D%5Bdate_format%5D'
                    f'=default&data%5Battribute%5D%5Bdate_format_custom%5D=Y%2Fm%2Fd&data%5Battribute%5D'
                    f'%5Bexcerpt_length%5D=20&data%5Battribute%5D%5Bexcerpt_ellipsis%5D=...&data%5Battribute%5D'
                    f'%5Bforce_normal_image_load%5D=&data%5Battribute%5D%5Bpagination_mode%5D=nextprev&data'
                    f'%5Battribute%5D%5Bpagination_nextprev_showtext%5D=&data%5Battribute%5D%5Bpagination_number_post'
                    f'%5D=25&data%5Battribute%5D%5Bpagination_scroll_limit%5D=0&data%5Battribute%5D%5Bads_type%5D'
                    f'=disable&data%5Battribute%5D%5Bads_position%5D=1&data%5Battribute%5D%5Bads_random%5D=&data'
                    f'%5Battribute%5D%5Bads_image%5D=&data%5Battribute%5D%5Bads_image_tablet%5D=&data%5Battribute%5D'
                    f'%5Bads_image_phone%5D=&data%5Battribute%5D%5Bads_image_link%5D=&data%5Battribute%5D'
                    f'%5Bads_image_alt%5D=&data%5Battribute%5D%5Bads_image_new_tab%5D=&data%5Battribute%5D'
                    f'%5Bgoogle_publisher_id%5D=&data%5Battribute%5D%5Bgoogle_slot_id%5D=&data%5Battribute%5D'
                    f'%5Bgoogle_desktop%5D=auto&data%5Battribute%5D%5Bgoogle_tab%5D=auto&data%5Battribute%5D'
                    f'%5Bgoogle_phone%5D=auto&data%5Battribute%5D%5Bcontent%5D=&data%5Battribute%5D%5Bads_bottom_text'
                    f'%5D=&data%5Battribute%5D%5Bboxed%5D=false&data%5Battribute%5D%5Bboxed_shadow%5D=false&data'
                    f'%5Battribute%5D%5Bel_id%5D=&data%5Battribute%5D%5Bel_class%5D=&data%5Battribute%5D%5Bscheme%5D'
                    f'=&data%5Battribute%5D%5Bcolumn_width%5D=auto&data%5Battribute%5D%5Btitle_color%5D=&data'
                    f'%5Battribute%5D%5Baccent_color%5D=&data%5Battribute%5D%5Balt_color%5D=&data%5Battribute%5D'
                    f'%5Bexcerpt_color%5D=&data%5Battribute%5D%5Bcss%5D=&data%5Battribute%5D%5Bpaged%5D=1&data'
                    f'%5Battribute%5D%5Bpagination_align%5D=center&data%5Battribute%5D%5Bpagination_navtext%5D=false'
                    f'&data%5Battribute%5D%5Bpagination_pageinfo%5D=false&data%5Battribute%5D%5Bbox_shadow%5D=false'
                    f'&data%5Battribute%5D%5Bpush_archive%5D=true&data%5Battribute%5D%5Bvideo_duration%5D=true&data'
                    f'%5Battribute%5D%5Bpost_meta_style%5D=style_2&data%5Battribute%5D%5Bauthor_avatar%5D=true&data'
                    f'%5Battribute%5D%5Bmore_menu%5D=true&data%5Battribute%5D%5Bcolumn_class%5D=jeg_col_2o3&data'
                    f'%5Battribute%5D%5Bclass%5D=jnews_block_5')
            url = 'https://www.premiumtimesng.com/?ajax-request=jnews'
            yield scrapy.FormRequest(url, method='post', headers=headers, body=data, callback=self.parse_trd,
                                     meta={'ch_url': ch_url, 'include_category': include_category,
                                           'current_page': current_page+1})

    def parse_trd(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        current_page = response.meta['current_page']
        include_category = response.meta['include_category']
        html_content = response.json().get('content', '')
        selector = scrapy.Selector(text=html_content)
        links = selector.xpath(
            "//article//div[@class='jeg_postblock_content']//*[@class='jeg_post_title']/a/@href").getall()
        for link in links:
            if not link:
                continue
            # link = response.urljoin(link)
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
        if if_new and include_category:
            headers = {
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest"
            }
            data = (f'lang=en_GB&action=jnews_module_ajax_jnews_block_5&module=true&data%5Bfilter%5D=0&data'
                    f'%5Bfilter_type%5D=all&data%5Bcurrent_page%5D={current_page}&data%5Battribute%5D%5Bheader_icon'
                    f'%5D=&data'
                    f'%5Battribute%5D%5Bfirst_title%5D=&data%5Battribute%5D%5Bsecond_title%5D=&data%5Battribute%5D'
                    f'%5Burl%5D=&data%5Battribute%5D%5Bheader_type%5D=heading_6&data%5Battribute%5D'
                    f'%5Bheader_background%5D=&data%5Battribute%5D%5Bheader_secondary_background%5D=&data%5Battribute'
                    f'%5D%5Bheader_text_color%5D=&data%5Battribute%5D%5Bheader_line_color%5D=&data%5Battribute%5D'
                    f'%5Bheader_accent_color%5D=&data%5Battribute%5D%5Bheader_filter_category%5D=&data%5Battribute%5D'
                    f'%5Bheader_filter_author%5D=&data%5Battribute%5D%5Bheader_filter_tag%5D=&data%5Battribute%5D'
                    f'%5Bheader_filter_text%5D=All&data%5Battribute%5D%5Bsticky_post%5D=false&data%5Battribute%5D'
                    f'%5Bpost_type%5D=post&data%5Battribute%5D%5Bcontent_type%5D=all&data%5Battribute%5D%5Bsponsor%5D'
                    f'=false&data%5Battribute%5D%5Bnumber_post%5D=25&data%5Battribute%5D%5Bpost_offset%5D=3&data'
                    f'%5Battribute%5D%5Bunique_content%5D=disable&data%5Battribute%5D%5Binclude_post%5D=&data'
                    f'%5Battribute%5D%5Bincluded_only%5D=false&data%5Battribute%5D%5Bexclude_post%5D=&data'
                    f'%5Battribute%5D%5Binclude_category%5D={include_category}&data%5Battribute%5D%5Bexclude_category'
                    f'%5D=&data'
                    f'%5Battribute%5D%5Binclude_author%5D=&data%5Battribute%5D%5Binclude_tag%5D=&data%5Battribute%5D'
                    f'%5Bexclude_tag%5D=&data%5Battribute%5D%5Bsort_by%5D=latest&data%5Battribute%5D%5Bdate_format%5D'
                    f'=default&data%5Battribute%5D%5Bdate_format_custom%5D=Y%2Fm%2Fd&data%5Battribute%5D'
                    f'%5Bexcerpt_length%5D=20&data%5Battribute%5D%5Bexcerpt_ellipsis%5D=...&data%5Battribute%5D'
                    f'%5Bforce_normal_image_load%5D=&data%5Battribute%5D%5Bpagination_mode%5D=nextprev&data'
                    f'%5Battribute%5D%5Bpagination_nextprev_showtext%5D=&data%5Battribute%5D%5Bpagination_number_post'
                    f'%5D=25&data%5Battribute%5D%5Bpagination_scroll_limit%5D=0&data%5Battribute%5D%5Bads_type%5D'
                    f'=disable&data%5Battribute%5D%5Bads_position%5D=1&data%5Battribute%5D%5Bads_random%5D=&data'
                    f'%5Battribute%5D%5Bads_image%5D=&data%5Battribute%5D%5Bads_image_tablet%5D=&data%5Battribute%5D'
                    f'%5Bads_image_phone%5D=&data%5Battribute%5D%5Bads_image_link%5D=&data%5Battribute%5D'
                    f'%5Bads_image_alt%5D=&data%5Battribute%5D%5Bads_image_new_tab%5D=&data%5Battribute%5D'
                    f'%5Bgoogle_publisher_id%5D=&data%5Battribute%5D%5Bgoogle_slot_id%5D=&data%5Battribute%5D'
                    f'%5Bgoogle_desktop%5D=auto&data%5Battribute%5D%5Bgoogle_tab%5D=auto&data%5Battribute%5D'
                    f'%5Bgoogle_phone%5D=auto&data%5Battribute%5D%5Bcontent%5D=&data%5Battribute%5D%5Bads_bottom_text'
                    f'%5D=&data%5Battribute%5D%5Bboxed%5D=false&data%5Battribute%5D%5Bboxed_shadow%5D=false&data'
                    f'%5Battribute%5D%5Bel_id%5D=&data%5Battribute%5D%5Bel_class%5D=&data%5Battribute%5D%5Bscheme%5D'
                    f'=&data%5Battribute%5D%5Bcolumn_width%5D=auto&data%5Battribute%5D%5Btitle_color%5D=&data'
                    f'%5Battribute%5D%5Baccent_color%5D=&data%5Battribute%5D%5Balt_color%5D=&data%5Battribute%5D'
                    f'%5Bexcerpt_color%5D=&data%5Battribute%5D%5Bcss%5D=&data%5Battribute%5D%5Bpaged%5D=1&data'
                    f'%5Battribute%5D%5Bpagination_align%5D=center&data%5Battribute%5D%5Bpagination_navtext%5D=false'
                    f'&data%5Battribute%5D%5Bpagination_pageinfo%5D=false&data%5Battribute%5D%5Bbox_shadow%5D=false'
                    f'&data%5Battribute%5D%5Bpush_archive%5D=true&data%5Battribute%5D%5Bvideo_duration%5D=true&data'
                    f'%5Battribute%5D%5Bpost_meta_style%5D=style_2&data%5Battribute%5D%5Bauthor_avatar%5D=true&data'
                    f'%5Battribute%5D%5Bmore_menu%5D=true&data%5Battribute%5D%5Bcolumn_class%5D=jeg_col_2o3&data'
                    f'%5Battribute%5D%5Bclass%5D=jnews_block_5')
            url = 'https://www.premiumtimesng.com/?ajax-request=jnews'
            yield scrapy.FormRequest(url, method='post', headers=headers, body=data, callback=self.parse_trd,
                                     meta={'ch_url': ch_url, 'include_category': include_category,
                                           'current_page': current_page + 1})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        lang = 'en'
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
