# UyPro 开发者指南

## 🎯 开发环境搭建

### 1. 环境要求
- Python 3.8+
- Redis 6.0+
- Google Chrome + ChromeDriver
- Git

### 2. 项目克隆和安装
```bash
# 克隆项目
git clone <repository-url>
cd uyPro

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置文件设置
```bash
# 复制配置模板
cp configlinux.ini.template configlinux.ini  # Linux
cp configwin.ini.template configwin.ini      # Windows

# 编辑配置文件
vim configlinux.ini
```

## 🏗️ 项目架构

### 目录结构
```
uyPro/
├── uyPro/                    # 主项目目录
│   ├── spiders/             # 爬虫模块
│   │   ├── webmod.py        # 核心解析模块
│   │   ├── utils.py         # 工具函数
│   │   ├── [网站].py        # 各网站爬虫
│   │   └── __init__.py
│   ├── items.py             # 数据项定义
│   ├── pipelines.py         # 数据处理管道
│   ├── middlewares.py       # 中间件
│   ├── settings.py          # 配置文件
│   └── __init__.py
├── proxy.list               # 代理列表
├── configlinux.ini          # Linux配置
├── configwin.ini            # Windows配置
├── requirements.txt         # 依赖列表
├── scrapy.cfg              # Scrapy配置
└── README.md               # 项目说明
```

### 核心组件

#### 1. 爬虫引擎 (Spider Engine)
- **位置**: `uyPro/spiders/`
- **功能**: 网站爬取和页面解析
- **主要文件**: 各网站的爬虫文件

#### 2. 解析引擎 (Parser Engine)
- **位置**: `uyPro/spiders/webmod.py`
- **功能**: 统一的内容解析和处理
- **核心函数**: `parsetweet()`, `parse_tweet_**()`

#### 3. 翻译引擎 (Translation Engine)
- **位置**: `uyPro/spiders/utils.py`
- **功能**: 多引擎翻译服务
- **支持引擎**: Google, Bing, Gemini, SiliconFlow

#### 4. 数据管道 (Data Pipeline)
- **位置**: `uyPro/pipelines.py`
- **功能**: 数据清洗、存储、后处理

## 🔧 添加新网站支持

### 步骤1: 创建爬虫文件

```python
# uyPro/spiders/newsite.py
import scrapy
from uyPro.items import UyproItem
from .webmod import parse_tweet_newsite

class NewsiteSpider(scrapy.Spider):
    name = 'newsite'
    allowed_domains = ['newsite.com']
    
    def start_requests(self):
        urls = [
            'https://newsite.com/news',
        ]
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)
    
    def parse(self, response):
        # 提取文章链接
        article_links = response.xpath("//a[@class='article-link']/@href").getall()
        
        for link in article_links:
            yield response.follow(link, self.parse_article)
    
    def parse_article(self, response):
        item = UyproItem()
        item['ch_url'] = 'https://newsite.com/news'
        item['tweet_url'] = response.url
        item['tweet_id'] = response.url
        item['taskid'] = 'newsite_task'
        item['bid'] = 'newsite_bid'
        item['tweet_lang'] = 'en'
        
        # 调用解析函数
        return parse_tweet_newsite(response, item)
```

### 步骤2: 添加解析函数

```python
# 在 uyPro/spiders/webmod.py 中添加
def parse_tweet_newsite(response, item):
    """
    新网站解析函数
    
    Args:
        response: Scrapy响应对象
        item: 数据项对象
    
    Returns:
        处理后的数据项
    """
    # 提取标题
    article_title = response.xpath("//h1[@class='title']/text()").get('').strip()
    
    # 提取内容
    content_nodes = response.xpath("//div[@class='content']//p")
    article_content = '\n'.join([
        p.xpath('string(.)').get('').strip() 
        for p in content_nodes if p
    ]).strip()
    
    # 提取作者
    tweet_author = response.xpath("//span[@class='author']/text()").get('').strip()
    
    # 提取时间
    tweet_createtime = response.xpath("//time/@datetime").get('').strip()
    
    # 提取图片
    img_url = response.xpath("//img/@src").getall()
    
    # 获取HTML内容
    html_content = response.xpath("//div[@class='content']").get('')
    
    # 调用统一处理函数
    return parsetweet(item, article_title, article_content, tweet_author, 
                     tweet_createtime, img_url, html_content, dt="UTC")
```

### 步骤3: 注册爬虫

在 `spider_mapping.json` 中添加新爬虫：
```json
{
    "newsite": {
        "name": "newsite",
        "description": "新网站爬虫",
        "domain": "newsite.com",
        "language": "en",
        "timezone": "UTC"
    }
}
```

## 🧪 测试和调试

### 1. 单元测试

```python
# tests/test_newsite.py
import unittest
from scrapy.http import HtmlResponse
from uyPro.items import UyproItem
from uyPro.spiders.webmod import parse_tweet_newsite

class TestNewsiteParser(unittest.TestCase):
    def setUp(self):
        self.html_content = """
        <html>
            <h1 class="title">Test Title</h1>
            <div class="content">
                <p>Test content paragraph 1</p>
                <p>Test content paragraph 2</p>
            </div>
            <span class="author">Test Author</span>
            <time datetime="2024-01-15T10:30:00Z">Jan 15, 2024</time>
        </html>
        """
        
    def test_parse_article(self):
        response = HtmlResponse(
            url='https://newsite.com/article/123',
            body=self.html_content.encode('utf-8')
        )
        item = UyproItem()
        
        result = parse_tweet_newsite(response, item)
        
        self.assertEqual(result['tweet_title'], 'Test Title')
        self.assertIn('Test content', result['tweet_content'])
        self.assertEqual(result['tweet_author'], 'Test Author')

if __name__ == '__main__':
    unittest.main()
```

### 2. 调试技巧

#### 使用Scrapy Shell
```bash
# 启动Scrapy Shell
scrapy shell "https://newsite.com/article/123"

# 在Shell中测试XPath
>>> response.xpath("//h1[@class='title']/text()").get()
'Test Title'

>>> response.xpath("//div[@class='content']//p/text()").getall()
['Test content paragraph 1', 'Test content paragraph 2']
```

#### 日志调试
```python
import logging

def parse_tweet_newsite(response, item):
    logging.info(f"解析URL: {response.url}")
    
    title = response.xpath("//h1[@class='title']/text()").get('').strip()
    logging.info(f"提取标题: {title}")
    
    if not title:
        logging.warning("未找到标题")
        return None
    
    # ... 其他解析逻辑
```

## 🔄 翻译引擎扩展

### 添加新翻译引擎

```python
# 在 uyPro/spiders/utils.py 中添加
def translate_text_newengine(text, target_lang='zh'):
    """
    新翻译引擎函数
    
    Args:
        text: 待翻译文本
        target_lang: 目标语言
    
    Returns:
        翻译结果
    """
    try:
        # 实现翻译逻辑
        api_url = "https://api.newengine.com/translate"
        payload = {
            'text': text,
            'target': target_lang,
            'source': 'auto'
        }
        
        response = requests.post(api_url, json=payload, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        return result.get('translated_text', text)
        
    except Exception as e:
        logging.error(f"新翻译引擎错误: {e}")
        return text
```

### 集成到主翻译函数

```python
def translatetext_unified(text, target_lang='zh', engine='auto'):
    """
    统一翻译接口
    
    Args:
        text: 待翻译文本
        target_lang: 目标语言
        engine: 翻译引擎 ('google', 'bing', 'gemini', 'siliconflow', 'newengine', 'auto')
    
    Returns:
        翻译结果
    """
    engines = {
        'google': translatetext,
        'bing': translatetext_bing,
        'gemini': translate_text_gemini,
        'siliconflow': translate_text_siliconflow,
        'newengine': translate_text_newengine,
    }
    
    if engine == 'auto':
        # 自动选择可用引擎
        for engine_name, engine_func in engines.items():
            try:
                result = engine_func(text, target_lang)
                if result and result != text:
                    return result
            except:
                continue
        return text
    
    engine_func = engines.get(engine, translatetext)
    return engine_func(text, target_lang)
```

## 📊 性能优化

### 1. 并发优化
```python
# settings.py
CONCURRENT_REQUESTS = 32
CONCURRENT_REQUESTS_PER_DOMAIN = 8
DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = 0.5
```

### 2. 内存优化
```python
# 在解析函数中及时清理大对象
def parse_tweet_large_content(response, item):
    # 处理大量数据时
    content = response.xpath("//div[@class='content']").get('')
    
    # 处理完成后清理
    del content
    
    return result
```

### 3. 缓存优化
```python
# settings.py
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 3600  # 1小时缓存
HTTPCACHE_DIR = 'httpcache'
```

## 🚀 部署指南

### 1. 生产环境配置
```bash
# 安装生产依赖
pip install gunicorn supervisor

# 配置Supervisor
sudo vim /etc/supervisor/conf.d/uyPro.conf
```

### 2. Docker部署

```dockerfile
FROM python:3.8-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY .. .
CMD ["python", "run_spiders.py"]
```

### 3. 监控和日志
```python
# 配置日志轮转
LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'uyPro.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
        },
    },
}
```

## 📝 代码规范

### 1. 命名规范
- 函数名: `snake_case`
- 类名: `PascalCase`
- 常量: `UPPER_CASE`
- 变量: `snake_case`

### 2. 文档字符串
```python
def parse_tweet_example(response, item):
    """
    示例网站解析函数
    
    Args:
        response (HtmlResponse): Scrapy响应对象
        item (UyproItem): 数据项对象
    
    Returns:
        UyproItem: 处理后的数据项
        None: 解析失败时返回
    
    Raises:
        ValueError: 当必要字段缺失时
    """
    pass
```

### 3. 错误处理
```python
def safe_extract(response, xpath, default=''):
    """安全的数据提取"""
    try:
        return response.xpath(xpath).get(default).strip()
    except Exception as e:
        logging.error(f"提取失败 {xpath}: {e}")
        return default
```

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支: `git checkout -b feature/new-site`
3. 提交更改: `git commit -am 'Add new site support'`
4. 推送分支: `git push origin feature/new-site`
5. 创建Pull Request

## 📞 获取帮助

- 查看项目Wiki
- 提交GitHub Issue
- 参考API文档
- 查看示例代码
