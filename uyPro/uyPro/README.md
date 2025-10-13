# UyPro 新闻爬虫系统

## 📖 项目简介

UyPro是一个基于Scrapy框架的分布式新闻爬虫系统，专门用于从多个国际新闻网站采集、处理和翻译新闻内容。系统支持80+个新闻网站，具备智能内容提取、多语言翻译、图片下载等功能。

### 🎯 主要特性

- **多网站支持**: 支持80+个国际新闻网站的内容采集
- **智能解析**: 自适应不同网站的页面结构和内容格式
- **多语言翻译**: 集成多个翻译引擎（Google、Bing、Gemini、SiliconFlow）
- **图片处理**: 自动下载和处理新闻图片
- **分布式架构**: 支持多机器分布式爬取
- **实时监控**: 内置监控和日志系统
- **代理支持**: 支持代理池和IP轮换

### 🏗️ 系统架构

```
uyPro/
├── uyPro/                    # 主项目目录
│   ├── spiders/             # 爬虫模块
│   │   ├── webmod.py        # 核心解析模块
│   │   ├── utils.py         # 工具函数
│   │   └── [网站爬虫].py    # 各网站专用爬虫
│   ├── items.py             # 数据项定义
│   ├── pipelines.py         # 数据处理管道
│   ├── middlewares.py       # 中间件
│   ├── settings.py          # 配置文件
│   └── run_spiders.py       # 爬虫运行器
├── scrapy.cfg               # Scrapy配置
└── README.md               # 项目文档
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Redis
- Google Chrome
- ChromeDriver
- Node.js (可选，用于某些翻译功能)

### 安装步骤

#### 1. 安装Google Chrome

```bash
# CentOS/RHEL
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
yum install ./google-chrome-stable_current_x86_64.rpm

# Ubuntu/Debian
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install google-chrome-stable

# 验证安装
google-chrome --version
```

#### 2. 安装ChromeDriver

```bash
# 下载与Chrome版本对应的ChromeDriver
# 从 https://chromedriver.chromium.org/ 下载

# 赋予执行权限
sudo chmod +x /usr/local/bin/chromedriver
```

#### 3. 安装Python依赖

```bash
# 安装基础依赖
pip install -r requirements.txt

# 主要依赖包括：
pip install scrapy
pip install selenium
pip install scrapy-selenium
pip install redis
pip install DrissionPage
pip install httpx
pip install lxml
```

#### 4. 安装Redis

```bash
# CentOS/RHEL
sudo yum install redis
sudo systemctl start redis
sudo systemctl enable redis

# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

#### 5. 安装Node.js (可选)

```bash
# 添加NodeSource仓库
curl -sL https://rpm.nodesource.com/setup_18.x | sudo bash -

# 安装Node.js
sudo dnf install nodejs

# 验证安装
node -v
npm -v
```

### 配置设置

#### 1. 修改配置文件

根据你的环境编辑配置文件：
- `configwin.ini` - Windows环境配置
- `configlinux.ini` - Linux环境配置

```ini
[DEFAULT]
folder_path = /path/to/your/data
redis_host = localhost
redis_port = 6379
redis_db = 0
```

#### 2. 配置代理（可选）

编辑代理文件：
- `proxy.list` - 主代理列表
- `proxy2.list` - 备用代理列表

#### 3. 修改Scrapy-Selenium中间件

用项目中的`scrapy_selenium_middlewares.txt`内容替换scrapy_selenium包中的middlewares.py文件。

## 🎮 使用方法

### 运行单个爬虫

```bash
# 运行特定网站爬虫
scrapy crawl jpost

# 运行BBC爬虫
scrapy crawl bbc

# 运行所有爬虫
python run_spiders.py
```

### 监控和日志

```bash
# 查看实时日志
tail -f website.log

# 查看监控日志
tail -f watchdog_scrapy.log
```

### 数据输出

爬取的数据会保存到：
- Redis数据库（实时数据）
- 本地文件系统（图片和HTML）
- 日志文件（运行记录）

## 📚 详细文档

### 核心模块说明

#### webmod.py - 核心解析模块
包含所有网站的内容解析函数，支持：
- 标题提取
- 内容解析
- 作者信息
- 发布时间
- 图片链接
- 多语言翻译

#### utils.py - 工具函数模块
提供通用功能：
- 翻译服务
- 图片处理
- 文本清理
- 时间转换

#### items.py - 数据项定义
定义爬取数据的结构和字段。

#### pipelines.py - 数据处理管道
处理爬取的数据：
- 数据清洗
- 翻译处理
- 图片下载
- 数据存储

#### middlewares.py - 中间件
提供请求和响应处理：
- 代理轮换
- 用户代理设置
- 请求重试
- 错误处理

### 支持的网站列表

系统支持80+个新闻网站，包括：

**国际新闻**
- BBC (bbc.py)
- Jerusalem Post (jpost.py)
- South China Morning Post (scmp.py)
- The Diplomat (thediplomat.py)

**政府网站**
- 各国外交部网站
- 政府新闻发布

**人权组织**
- Human Rights Watch (hrworg.py)
- Amnesty International (amnestyusa.py)
- Freedom House (freedomhouseorg.py)

**地区新闻**
- 中亚地区新闻网站
- 非洲新闻网站
- 亚太地区新闻

## 🔧 开发指南

### 添加新网站爬虫

1. 在`spiders/`目录创建新的爬虫文件
2. 在`webmod.py`中添加解析函数
3. 在`spider_mapping.json`中注册新爬虫
4. 测试和调试

### 自定义翻译引擎

在`utils.py`中添加新的翻译函数，支持的引擎：
- Google Translate
- Microsoft Bing
- Google Gemini
- SiliconFlow

### 配置代理池

编辑代理文件，支持：
- HTTP代理
- HTTPS代理
- SOCKS代理

## 🐛 故障排除

### 常见问题

1. **ChromeDriver版本不匹配**
   - 确保ChromeDriver版本与Chrome浏览器版本匹配

2. **Redis连接失败**
   - 检查Redis服务是否运行
   - 验证连接配置

3. **代理连接问题**
   - 检查代理列表有效性
   - 验证网络连接

4. **翻译服务失败**
   - 检查API密钥配置
   - 验证网络连接

### 日志分析

- `website.log` - 主要运行日志
- `task.log` - 任务执行日志
- `watchdog_scrapy.log` - 监控日志

