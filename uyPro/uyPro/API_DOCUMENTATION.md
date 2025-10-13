# UyPro 新闻爬虫系统 API 文档

## 📚 概述

本文档详细描述了UyPro新闻爬虫系统的API接口、函数说明和使用方法。

## 🏗️ 核心模块

### 1. webmod.py - 网站解析模块

#### 核心函数

##### `parsetweet()`
```python
def parsetweet(item, article_title, article_content, tweet_author, tweet_createtime, 
               tweet_img_url, html_content, dt="America/New_York", split_func=split_string, 
               translate=True, max_length=4800, _translatetext=translatetext, 
               convert_traditional=False)
```

**功能**: 统一的新闻文章数据处理和翻译函数

**参数**:
- `item` (UyproItem): 数据项对象
- `article_title` (str): 文章标题
- `article_content` (str): 文章内容
- `tweet_author` (str): 作者信息
- `tweet_createtime` (str): 发布时间
- `tweet_img_url` (list): 图片URL列表
- `html_content` (str): 原始HTML
- `dt` (str): 时区设置
- `split_func` (function): 文本分割函数
- `translate` (bool): 是否翻译
- `max_length` (int): 最大翻译长度
- `_translatetext` (function): 翻译函数
- `convert_traditional` (bool): 是否转换繁体中文

**返回值**: 
- `UyproItem`: 处理完成的数据项
- `None`: 处理失败

#### 网站解析函数

##### `parse_tweet_jpost(response, item)`
**功能**: Jerusalem Post网站解析
**特点**: 
- 支持客户端渲染页面
- 处理JavaScript中的JSON-LD数据
- 多重转义字符处理

##### `parse_tweet_bbc(response, item)`
**功能**: BBC新闻网站解析
**特点**:
- 标准HTML结构解析
- 多媒体内容提取
- 时间格式标准化

##### `parse_tweet_scmp(response, item)`
**功能**: South China Morning Post解析
**特点**:
- 付费墙内容处理
- 图片懒加载处理
- 作者信息提取

### 2. utils.py - 工具函数模块

#### 日期时间处理

##### `parse_date(date_input, default_timezone="America/New_York")`
```python
def parse_date(date_input, default_timezone="America/New_York")
```

**功能**: 解析各种格式的日期时间

**支持格式**:
- Unix时间戳
- ISO格式日期
- 波斯历日期
- 中文日期格式
- 俄语月份名称

**参数**:
- `date_input` (str|int): 输入日期
- `default_timezone` (str): 默认时区

**返回值**: 
- `str`: 格式化日期字符串 "YYYY-MM-DD HH:MM:SS"

#### 翻译服务

##### `translatetext(text, target_lang='zh')`
**功能**: Google翻译服务
**参数**:
- `text` (str): 待翻译文本
- `target_lang` (str): 目标语言

##### `translatetext_bing(text, target_lang='zh')`
**功能**: Bing翻译服务

##### `translate_text_gemini(text, target_lang='zh')`
**功能**: Google Gemini翻译服务

##### `translate_text_siliconflow(text, target_lang='zh')`
**功能**: SiliconFlow翻译服务

#### 文本处理

##### `split_string(text, max_length=4800)`
**功能**: 智能文本分割
**特点**:
- 按句子边界分割
- 保持语义完整性
- 支持多语言

##### `remove_font_tags(html_content)`
**功能**: 清理HTML字体标签

##### `detect_language(text)`
**功能**: 自动语言检测

### 3. items.py - 数据项定义

#### UyproItem类

```python
class UyproItem(scrapy.Item):
    # 基础信息
    ch_url = scrapy.Field()              # 频道URL
    tweet_url = scrapy.Field()           # 文章URL
    tweet_id = scrapy.Field()            # 文章ID
    
    # 内容字段
    tweet_title = scrapy.Field()         # 原始标题
    tweet_title_tslt = scrapy.Field()    # 翻译标题
    tweet_content = scrapy.Field()       # 原始内容
    tweet_content_tslt = scrapy.Field()  # 翻译内容
    tweet_author = scrapy.Field()        # 作者
    tweet_lang = scrapy.Field()          # 语言
    
    # 时间字段
    tweet_createtime = scrapy.Field()    # 标准化时间
    tweet_createtime_original = scrapy.Field()  # 原始时间
    
    # 媒体文件
    tweet_img_url = scrapy.Field()       # 图片URL列表
    tweet_pdf_url = scrapy.Field()       # PDF URL列表
    tweet_table = scrapy.Field()         # 表格数据
    
    # 系统字段
    taskid = scrapy.Field()              # 任务ID
    deviceid = scrapy.Field()            # 设备ID
    bid = scrapy.Field()                 # 批次ID
    capture_time = scrapy.Field()        # 采集时间
```

## 🔧 配置说明

### settings.py 主要配置

#### 基础设置
```python
BOT_NAME = "uyPro"                    # 爬虫名称
USER_AGENT = "Mozilla/5.0..."         # 用户代理
ROBOTSTXT_OBEY = False                # 忽略robots.txt
```

#### 并发设置
```python
CONCURRENT_REQUESTS = 32              # 并发请求数
DOWNLOAD_DELAY = 3                    # 下载延迟
CONCURRENT_REQUESTS_PER_DOMAIN = 16   # 每域名并发数
```

#### 中间件配置
```python
DOWNLOADER_MIDDLEWARES = {
    "uyPro.middlewares.UyproDownloaderMiddleware": 543,
}
```

#### 超时设置
```python
CLOSESPIDER_TIMEOUT_NO_ITEM = 1800    # 无数据超时(30分钟)
CLOSESPIDER_ITEMCOUNT = 300           # 最大爬取数量
CLOSESPIDER_TIMEOUT = 7200            # 总超时时间(2小时)
```

## 🚀 使用示例

### 基本爬虫运行

```python
# 运行单个爬虫
scrapy crawl jpost

# 运行所有爬虫
python run_spiders.py
```

### 自定义解析函数

```python
def parse_tweet_custom(response, item):
    """自定义网站解析函数"""
    # 提取标题
    title = response.xpath("//h1/text()").get('')
    
    # 提取内容
    content_nodes = response.xpath("//div[@class='content']//p")
    content = '\n'.join([p.xpath('string(.)').get('') for p in content_nodes])
    
    # 提取作者
    author = response.xpath("//span[@class='author']/text()").get('')
    
    # 提取时间
    time_str = response.xpath("//time/@datetime").get('')
    
    # 提取图片
    images = response.xpath("//img/@src").getall()
    
    # 获取HTML内容
    html_content = response.xpath("//div[@class='content']").get('')
    
    # 调用统一处理函数
    return parsetweet(item, title, content, author, time_str, images, html_content)
```

### 翻译服务使用

```python
from uyPro.spiders.utils import translatetext, translate_text_gemini

# 使用Google翻译
result = translatetext("Hello World", target_lang='zh')

# 使用Gemini翻译
result = translate_text_gemini("Hello World", target_lang='zh')
```

## 📊 数据流程

```
1. 爬虫启动 → 2. 获取页面 → 3. 解析内容 → 4. 数据处理 → 5. 翻译服务 → 6. 存储数据
     ↓              ↓              ↓              ↓              ↓              ↓
  Spider        Response      parse_tweet_*    parsetweet    translatetext    Redis/File
```

## 🔍 调试和监控

### 日志配置
- `website.log` - 主要运行日志
- `task.log` - 任务执行日志
- `watchdog_scrapy.log` - 监控日志

### 常用调试命令
```bash
# 查看实时日志
tail -f website.log

# 检查Redis状态
redis-cli ping

# 测试单个URL
scrapy shell "https://example.com"
```

## ⚠️ 注意事项

1. **代理配置**: 确保代理列表有效且可用
2. **翻译限制**: 注意各翻译服务的API限制
3. **内存管理**: 大量数据处理时注意内存使用
4. **错误处理**: 实现适当的异常处理机制
5. **时区处理**: 正确设置各网站的时区信息

## 📞 技术支持

如有问题或需要技术支持，请查看：
- 项目README.md
- 日志文件分析
