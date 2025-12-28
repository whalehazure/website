import hashlib
import json
import logging

import scrapy

from uyPro.items import UyproItem
from uyPro.settings import redis_conn
from .utils import start_spider, update_ch_urls
from .webmod import get_map


class AcpcdSpider(scrapy.Spider):
    name = "acpcd"
    redis_conn = redis_conn
    custom_settings = {
        'ITEM_PIPELINES': {'uyPro.pipelines.CustomFilesPipeline': 300, },
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_MAX_DELAY': 10,
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                      '537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
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
            # churl = 'https://acp.cd/fil-actu/'
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
                yield scrapy.Request(url=churl, callback=self.parse_sec, meta={'ch_url': churl, 'page': 1})
            else:
                # gettweet
                yield scrapy.Request(url=tweeturl, callback=self.article, meta={'ch_url': churl, 'link': tweeturl})
        except TypeError as e:
            logging.info(f'exit:{e}')

    def parse(self, response, **kwargs):
        chlinks = [
            'https://acp.cd/fil-actu/',
        ]
        for link in chlinks:
            yield response.follow(link, callback=self.parse_sec, meta={'ch_url': link})

    def parse_sec(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        links = response.xpath("//div[@class='wpb_wrapper']/div/div[@id]//h2/a/@href").getall()
        for link in links:
            if not link:
                continue
            link = response.urljoin(link)
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

        next_url = 'https://acp.cd/wp/wp-admin/admin-ajax.php?td_theme_name=Newspaper&v=12.7.1'
        page = 2
        if if_new:
            data = {
                "action": "td_ajax_block",
                "td_atts": "{\"modules_on_row\":\"\",\"limit\":\"12\",\"hide_audio\":\"yes\",\"image_floated\":\"eyJhbGwiOiJmbG9hdF9yaWdodCIsInBob25lIjoiaGlkZGVuIn0=\",\"image_width\":\"eyJhbGwiOiIzMCIsInBob25lIjoiMTAwIn0=\",\"image_height\":\"60\",\"show_vid_t\":\"none\",\"autoplay_vid\":\"\",\"modules_category\":\"above\",\"modules_category_padding\":\"7px 10px 7px 10px\",\"modules_category_radius\":\"5\",\"cat_bg\":\"var(--accent-color)\",\"cat_bg_hover\":\"var(--accent-color)\",\"show_btn\":\"none\",\"show_audio\":\"none\",\"show_review\":\"none\",\"show_com\":\"none\",\"show_date\":\"\",\"show_author\":\"none\",\"f_title_font_size\":\"18\",\"f_title_font_family\":\"479\",\"f_title_font_weight\":\"700\",\"f_ex_font_size\":\"16\",\"f_ex_font_family\":\"99\",\"f_ex_font_weight\":\"400\",\"cat_txt\":\"#ffffff\",\"cat_txt_hover\":\"#ffffff\",\"ex_txt\":\"#7e7e7e\",\"meta_info_align\":\"eyJhbGwiOiJpbml0aWFsIiwicGhvbmUiOiJmbGV4LWVuZCJ9\",\"modules_category_margin\":\"0px 0px 11px 0px\",\"title_txt\":\"#000000\",\"title_txt_hover\":\"#000000\",\"mc1_el\":\"15\",\"art_title\":\"eyJhbGwiOiIwcHggMHB4IDBweCAwcHgiLCJwaG9uZSI6IjEwcHggMHB4IDBweCAwcHgifQ==\",\"art_excerpt\":\"eyJhbGwiOiIyMHB4IDIwcHggMHB4IDBweCIsInBob25lIjoiMTBweCAwcHggMHB4IDBweCJ9\",\"modules_border_color\":\"#d9d9d9\",\"modules_divider\":\"solid\",\"modules_divider_color\":\"#d9d9d9\",\"mc1_title_tag\":\"h2\",\"meta_padding\":\"0px 20px 0px 0px\",\"f_cat_font_family\":\"99\",\"f_cat_font_size\":\"12\",\"f_cat_font_weight\":\"400\",\"show_cat\":\"eyJwaG9uZSI6Im5vbmUiLCJhbGwiOiJub25lIn0=\",\"image_size\":\"td_1068x0\",\"mc1_tl\":\"15\",\"author_photo_size\":\"undefined\",\"author_photo_space\":\"undefined\",\"author_photo_radius\":\"undefined\",\"review_size\":\"undefined\",\"f_meta_font_family\":\"99\",\"f_meta_font_size\":\"16\",\"f_meta_font_line_height\":\"undefined\",\"f_meta_font_style\":\"undefined\",\"f_meta_font_weight\":\"undefined\",\"f_meta_font_transform\":\"undefined\",\"f_meta_font_spacing\":\"undefined\",\"author_txt\":\"undefined\",\"author_txt_hover\":\"undefined\",\"date_txt\":\"#fc0100\",\"ajax_pagination\":\"load_more\",\"pag_padding\":\"16px 20px 16px 20px\",\"pag_space\":\"100\",\"pag_border_width\":\"0\",\"pag_border_radius\":\"50\",\"pag_icons_size\":\"0\",\"pag_bg\":\"var(--accent-color)\",\"pag_h_bg\":\"var(--accent-color)\",\"pag_text\":\"#ffffff\",\"pag_h_text\":\"#ffffff\",\"f_more_font_family\":\"99\",\"f_more_font_size\":\"16\",\"time_ago\":\"yes\",\"time_ago_add_txt\":\"Il y a\",\"time_ago_txt_pos\":\"yes\",\"block_type\":\"td_flex_block_1\",\"separator\":\"\",\"custom_title\":\"\",\"custom_url\":\"\",\"block_template_id\":\"\",\"title_tag\":\"\",\"post_ids\":\"\",\"category_id\":\"\",\"taxonomies\":\"\",\"category_ids\":\"\",\"in_all_terms\":\"\",\"tag_slug\":\"\",\"autors_id\":\"\",\"installed_post_types\":\"\",\"include_cf_posts\":\"\",\"exclude_cf_posts\":\"\",\"sort\":\"\",\"popular_by_date\":\"\",\"linked_posts\":\"\",\"favourite_only\":\"\",\"offset\":\"\",\"open_in_new_window\":\"\",\"show_modified_date\":\"\",\"review_source\":\"\",\"el_class\":\"\",\"td_query_cache\":\"\",\"td_query_cache_expiration\":\"\",\"td_ajax_filter_type\":\"\",\"td_ajax_filter_ids\":\"\",\"td_filter_default_txt\":\"All\",\"td_ajax_preloading\":\"\",\"container_width\":\"\",\"modules_gap\":\"\",\"m_padding\":\"\",\"all_modules_space\":\"36\",\"modules_border_size\":\"\",\"modules_border_style\":\"\",\"modules_border_radius\":\"\",\"h_effect\":\"\",\"image_alignment\":\"50\",\"image_radius\":\"\",\"hide_image\":\"\",\"show_favourites\":\"\",\"fav_size\":\"2\",\"fav_space\":\"\",\"fav_ico_color\":\"\",\"fav_ico_color_h\":\"\",\"fav_bg\":\"\",\"fav_bg_h\":\"\",\"fav_shadow_shadow_header\":\"\",\"fav_shadow_shadow_title\":\"Shadow\",\"fav_shadow_shadow_size\":\"\",\"fav_shadow_shadow_offset_horizontal\":\"\",\"fav_shadow_shadow_offset_vertical\":\"\",\"fav_shadow_shadow_spread\":\"\",\"fav_shadow_shadow_color\":\"\",\"video_icon\":\"\",\"video_popup\":\"yes\",\"video_rec\":\"\",\"spot_header\":\"\",\"video_rec_title\":\"\",\"video_rec_color\":\"\",\"video_rec_disable\":\"\",\"vid_t_margin\":\"\",\"vid_t_padding\":\"\",\"video_title_color\":\"\",\"video_title_color_h\":\"\",\"video_bg\":\"\",\"video_overlay\":\"\",\"vid_t_color\":\"\",\"vid_t_bg_color\":\"\",\"f_vid_title_font_header\":\"\",\"f_vid_title_font_title\":\"Video pop-up article title\",\"f_vid_title_font_settings\":\"\",\"f_vid_title_font_family\":\"\",\"f_vid_title_font_size\":\"\",\"f_vid_title_font_line_height\":\"\",\"f_vid_title_font_style\":\"\",\"f_vid_title_font_weight\":\"\",\"f_vid_title_font_transform\":\"\",\"f_vid_title_font_spacing\":\"\",\"f_vid_title_\":\"\",\"f_vid_time_font_title\":\"Video duration text\",\"f_vid_time_font_settings\":\"\",\"f_vid_time_font_family\":\"\",\"f_vid_time_font_size\":\"\",\"f_vid_time_font_line_height\":\"\",\"f_vid_time_font_style\":\"\",\"f_vid_time_font_weight\":\"\",\"f_vid_time_font_transform\":\"\",\"f_vid_time_font_spacing\":\"\",\"f_vid_time_\":\"\",\"meta_info_horiz\":\"layout-default\",\"meta_width\":\"\",\"meta_margin\":\"\",\"meta_space\":\"\",\"art_btn\":\"\",\"meta_info_border_size\":\"\",\"meta_info_border_style\":\"\",\"meta_info_border_color\":\"#eaeaea\",\"meta_info_border_radius\":\"\",\"modules_cat_border\":\"\",\"modules_extra_cat\":\"\",\"author_photo\":\"\",\"review_space\":\"\",\"review_distance\":\"\",\"show_excerpt\":\"block\",\"excerpt_col\":\"1\",\"excerpt_gap\":\"\",\"excerpt_middle\":\"\",\"excerpt_inline\":\"\",\"art_audio\":\"\",\"art_audio_size\":\"1.5\",\"btn_title\":\"\",\"btn_margin\":\"\",\"btn_padding\":\"\",\"btn_border_width\":\"\",\"btn_radius\":\"\",\"prev_tdicon\":\"\",\"next_tdicon\":\"\",\"f_header_font_header\":\"\",\"f_header_font_title\":\"Block header\",\"f_header_font_settings\":\"\",\"f_header_font_family\":\"\",\"f_header_font_size\":\"\",\"f_header_font_line_height\":\"\",\"f_header_font_style\":\"\",\"f_header_font_weight\":\"\",\"f_header_font_transform\":\"\",\"f_header_font_spacing\":\"\",\"f_header_\":\"\",\"f_ajax_font_title\":\"Ajax categories\",\"f_ajax_font_settings\":\"\",\"f_ajax_font_family\":\"\",\"f_ajax_font_size\":\"\",\"f_ajax_font_line_height\":\"\",\"f_ajax_font_style\":\"\",\"f_ajax_font_weight\":\"\",\"f_ajax_font_transform\":\"\",\"f_ajax_font_spacing\":\"\",\"f_ajax_\":\"\",\"f_more_font_title\":\"Load more button\",\"f_more_font_settings\":\"\",\"f_more_font_line_height\":\"\",\"f_more_font_style\":\"\",\"f_more_font_weight\":\"\",\"f_more_font_transform\":\"\",\"f_more_font_spacing\":\"\",\"f_more_\":\"\",\"f_title_font_header\":\"\",\"f_title_font_title\":\"Article title\",\"f_title_font_settings\":\"\",\"f_title_font_line_height\":\"\",\"f_title_font_style\":\"\",\"f_title_font_transform\":\"\",\"f_title_font_spacing\":\"\",\"f_title_\":\"\",\"f_cat_font_title\":\"Article category tag\",\"f_cat_font_settings\":\"\",\"f_cat_font_line_height\":\"\",\"f_cat_font_style\":\"\",\"f_cat_font_transform\":\"\",\"f_cat_font_spacing\":\"\",\"f_cat_\":\"\",\"f_meta_font_title\":\"Article meta info\",\"f_meta_font_settings\":\"\",\"f_meta_\":\"\",\"f_ex_font_title\":\"Article excerpt\",\"f_ex_font_settings\":\"\",\"f_ex_font_line_height\":\"\",\"f_ex_font_style\":\"\",\"f_ex_font_transform\":\"\",\"f_ex_font_spacing\":\"\",\"f_ex_\":\"\",\"f_btn_font_title\":\"Article read more button\",\"f_btn_font_settings\":\"\",\"f_btn_font_family\":\"\",\"f_btn_font_size\":\"\",\"f_btn_font_line_height\":\"\",\"f_btn_font_style\":\"\",\"f_btn_font_weight\":\"\",\"f_btn_font_transform\":\"\",\"f_btn_font_spacing\":\"\",\"f_btn_\":\"\",\"mix_color\":\"\",\"mix_type\":\"\",\"fe_brightness\":\"1\",\"fe_contrast\":\"1\",\"fe_saturate\":\"1\",\"mix_color_h\":\"\",\"mix_type_h\":\"\",\"fe_brightness_h\":\"1\",\"fe_contrast_h\":\"1\",\"fe_saturate_h\":\"1\",\"m_bg\":\"\",\"color_overlay\":\"\",\"shadow_shadow_header\":\"\",\"shadow_shadow_title\":\"Module Shadow\",\"shadow_shadow_size\":\"\",\"shadow_shadow_offset_horizontal\":\"\",\"shadow_shadow_offset_vertical\":\"\",\"shadow_shadow_spread\":\"\",\"shadow_shadow_color\":\"\",\"all_underline_height\":\"\",\"all_underline_color\":\"\",\"cat_style\":\"\",\"cat_border\":\"\",\"cat_border_hover\":\"\",\"meta_bg\":\"\",\"com_bg\":\"\",\"com_txt\":\"\",\"rev_txt\":\"\",\"audio_btn_color\":\"\",\"audio_time_color\":\"\",\"audio_bar_color\":\"\",\"audio_bar_curr_color\":\"\",\"shadow_m_shadow_header\":\"\",\"shadow_m_shadow_title\":\"Meta info shadow\",\"shadow_m_shadow_size\":\"\",\"shadow_m_shadow_offset_horizontal\":\"\",\"shadow_m_shadow_offset_vertical\":\"\",\"shadow_m_shadow_spread\":\"\",\"shadow_m_shadow_color\":\"\",\"btn_bg\":\"\",\"btn_bg_hover\":\"\",\"btn_txt\":\"\",\"btn_txt_hover\":\"\",\"btn_border\":\"\",\"btn_border_hover\":\"\",\"pag_border\":\"\",\"pag_h_border\":\"\",\"ajax_pagination_next_prev_swipe\":\"\",\"ajax_pagination_infinite_stop\":\"\",\"css\":\"\",\"tdc_css\":\"\",\"td_column_number\":3,\"header_color\":\"\",\"color_preset\":\"\",\"border_top\":\"\",\"class\":\"tdi_147\",\"tdc_css_class\":\"tdi_147\",\"tdc_css_class_style\":\"tdi_147_rand_style\"}",
                "td_block_id": "tdi_147",
                "td_column_number": "3",
                "td_current_page": str(page),
                "block_type": "td_flex_block_1",
                "td_filter_value": "",
                "td_user_action": "",
                "td_magic_token": "f838c97e30"
            }
            yield scrapy.FormRequest(url=next_url, formdata=data, callback=self.parse_next, dont_filter=True,
                                     meta={'ch_url': ch_url, 'page': page + 1})

    def parse_next(self, response):
        if_new = False
        ch_url = response.meta['ch_url']
        html_content = response.json().get('td_data', '')
        selector = scrapy.Selector(text=html_content)
        links = selector.xpath("//h2/a/@href|//h3/a/@href").getall()
        for link in links:
            if not link:
                continue
            link = response.urljoin(link)
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

        next_url = 'https://acp.cd/wp/wp-admin/admin-ajax.php?td_theme_name=Newspaper&v=12.7.1'
        page = response.meta['page']
        if if_new:
            data = {
                "action": "td_ajax_block",
                "td_block_id": "tdi_147",
                "td_column_number": "3",
                "td_current_page": str(page),
                "block_type": "td_flex_block_1",
                "td_filter_value": "",
                "td_user_action": "",
                "td_magic_token": "f838c97e30"
            }
            yield scrapy.FormRequest(url=next_url, formdata=data, callback=self.parse_next, dont_filter=True,
                                     meta={'ch_url': ch_url, 'page': page + 1})

    def article(self, response):
        item = UyproItem()
        link = response.meta['link']
        item['ch_url'] = response.meta['ch_url']
        item['tweet_url'] = response.url
        item['tweet_id'] = link
        lang = 'fr'
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
