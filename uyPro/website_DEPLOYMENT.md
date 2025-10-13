# UyPro新闻爬虫系统部署文档

## 📋 部署前准备

### 目标部署路径
```bash
/zhuoyue
```

## 🚀 部署流程

### 1. 从SVN仓库拷贝代码


## 🔧 环境配置

### 2. Python环境配置

#### 2.1 安装Python 3.9

#### 2.2 安装Python依赖
```bash
# 切换到项目目录
cd /zhuoyue/website2/uyPro/uyPro

# 安装依赖包
pipenv install

```

### 3. Redis服务配置

#### 3.1 安装Redis

#### 3.2 Redis配置调优
```bash
# 编辑Redis配置文件
sudo vim /etc/redis/redis.conf

# 建议配置项：
# maxmemory 2gb
# maxmemory-policy allkeys-lru
# save 900 1
# save 300 10
# save 60 10000

# 重启Redis服务
sudo systemctl restart redis
```

## ⚙️ 配置文件详解

### 4. configlinux.ini 配置说明

#### 4.1 配置文件内容
```ini
[DEFAULT]
input_path = /zhuoyue/website2/tasklist
processed_path = /zhuoyue/website2/tasklistbk
folder_path = /zhuoyue/website2/tasklistworking
file_dir = /zhuoyue/website2/images
dest_zip_file_path = /zhuoyue/website2/data
zip_file_path = /zhuoyue/website2/zips
deviceid = 65000600000001
pgmid = 002
```

#### 4.2 配置项在程序中的实际用途

**input_path** - 任务输入目录
- **程序用途**: 监控此目录下的任务文件，作为爬虫任务的输入源
- **变量引用**: `settings.py`中可能引用为任务队列监控目录
- **文件格式**: JSON格式的任务配置文件
- **监控机制**: 程序定期扫描此目录的新任务文件

**processed_path** - 已处理任务备份目录
- **程序用途**: 处理完成的任务文件移动到此目录进行备份
- **变量引用**: `settings.py`中的`processed_path`
- **文件命名**: 保持原文件名，按处理时间组织目录结构

**folder_path** - 任务工作目录
- **程序用途**: 正在处理中的任务文件临时存放目录
- **变量引用**: `settings.py`中的`folder_path`
- **工作流程**: input_path → folder_path → processed_path
- **状态标识**: 文件在此目录表示正在处理中，避免重复处理

**file_dir** - 媒体文件存储目录
- **程序用途**: 新闻文章中的图片、PDF等媒体文件下载存储目录
- **变量引用**: `settings.py`中的`FILES_STORE`和`file_dir`
- **目录结构**: 
  ```
  /zhuoyue/website2/images/
  ├── images/     # 图片文件
  ├── pdfs/       # PDF文档
  ├── csv/        # 表格数据
  └── videos/     # 视频文件(如有)
  ```
- **文件命名**: 使用SHA1哈希值命名，避免重复下载

**dest_zip_file_path** - 最终数据交付目录
- **程序用途**: 打包后的数据文件最终存放位置，供下游系统使用
- **变量引用**: `settings.py`中的`dest_zip_file_path`
- **文件格式**: ZIP压缩包，包含文章数据和媒体文件
- **命名规则**: `{deviceid}_{pgmid}_{timestamp}.zip`

**zip_file_path** - 临时压缩包目录
- **程序用途**: 数据打包过程中的临时文件存储目录
- **变量引用**: `settings.py`中的`zip_file_path`
- **工作流程**: 数据收集 → zip_file_path打包 → dest_zip_file_path交付
- **自动清理**: 打包完成后自动清理临时文件

**deviceid** - 设备唯一标识符
- **程序用途**: 标识当前爬虫设备，用于数据溯源和设备管理
- **变量引用**: `settings.py`中的`deviceid`
- **使用场景**: 数据文件命名、日志标识、监控统计

**pgmid** - 程序实例标识符
- **程序用途**: 区分同一设备上的不同爬虫程序实例
- **变量引用**: `settings.py`中的`pgmid`
- **格式说明**: `002` 表示第2个程序实例
- **应用场景**: 多实例部署时避免数据冲突，实现负载均衡

### 5. 代理配置文件使用说明

#### 5.1 proxy.list - 主代理池
```bash
# 代理格式示例
http://username:password@proxy1.example.com:8080
http://username:password@proxy2.example.com:8080
socks5://username:password@proxy3.example.com:1080
```

**程序中的使用**:
- **变量名**: `proxy_list`
- **用途**: 主要用于一般新闻网站的数据采集

#### 5.2 proxy2.list - 备用代理池
```bash
# 备用代理配置
http://backup1.proxy.com:8080
http://backup2.proxy.com:8080
```

**程序中的使用**:
- **变量名**: `traproxylist`
- **用途**: 当主代理池全部失效时的故障转移机制

#### 5.3 proxy_centcommil.list - 特定网站专用代理
```bash
# 特定网站专用代理
http://special1.proxy.com:8080
http://special2.proxy.com:8080
```

**程序中的使用**:
- **变量名**: `proxy_list_centcommil`
- **用途**: 专门用于centcommil等对IP来源有特殊要求的网站
- **特点**: 针对特定网站优化的代理配置，IP地理位置匹配
- **配置原因**: 某些网站限制特定地区IP访问或有反爬虫机制
- **使用条件**: 仅在访问特定域名时使用，由中间件自动判断

### 6. Chrome和ChromeDriver配置

#### 6.1 安装Chrome浏览器
```bash
# 下载Chrome RPM包
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm

# 安装Chrome
sudo yum install ./google-chrome-stable_current_x86_64.rpm

# 或者Ubuntu/Debian
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update
sudo apt install google-chrome-stable
```

#### 6.2 安装ChromeDriver
```bash
# 检查Chrome版本
google-chrome --version

# 下载对应版本的ChromeDriver
# 从 https://chromedriver.chromium.org/ 下载对应版本

# 安装ChromeDriver
sudo wget https://chromedriver.storage.googleapis.com/108.0.5359.71/chromedriver_linux64.zip
sudo unzip chromedriver_linux64.zip
sudo mv chromedriver /usr/bin/chromedriver_108
sudo chmod +x /usr/bin/chromedriver_108

# 创建软链接
sudo ln -sf /usr/bin/chromedriver_108 /usr/bin/chromedriver
```

#### 6.3 验证安装
```bash
# 检查Chrome版本
google-chrome --version
# 输出: Google Chrome 108.0.5359.124

# 检查ChromeDriver
chromedriver --version
# 输出: ChromeDriver 108.0.5359.71

# 测试Chrome无头模式
google-chrome --headless --disable-gpu --dump-dom https://www.google.com
```

### 7. 创建必要目录

## 🚀 程序启动

### 8. 启动和监控

#### 8.1 启动监控程序
```bash
# 切换到程序目录
cd /zhuoyue/website2/uyPro/uyPro

# 启动监控程序（推荐方式）
nohup pipenv run python3.9 website_watchd.py &

```
