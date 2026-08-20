# ☁️ 中国移动云盘 WebDAV

将中国移动云盘 (yun.139.com) 映射为本地 WebDAV 磁盘，支持 Windows 资源管理器直接访问、上传、下载、删除、重命名等操作。

## 功能特性

| 功能 | 状态 | 说明 |
|------|------|------|
| 文件列表 | ✅ | 浏览云盘文件夹结构 |
| 文件下载 | ✅ | 通过WebDAV读取文件 |
| 文件上传 | ✅ | 通过WebDAV写入文件 |
| 删除文件 | ✅ | 移入回收站 |
| 创建文件夹 | ✅ | MKCOL支持 |
| 重命名 | ✅ | MOVE支持 |
| 移动/复制 | ✅ | MOVE/COPY支持 |
| 网页管理界面 | ✅ | 内置配置管理、日志查看 |
| 系统托盘 | ✅ | 最小化到托盘 |
| 单文件运行 | ✅ | PyInstaller打包为单EXE |

## 快速开始

### 方式一：源码运行 (需要Python环境)

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 获取Cookie
# 登录 https://yun.139.com
# 按F12打开开发者工具 -> Network面板
# 刷新页面，找到任意请求，复制Request Headers中的Cookie

# 3. 运行程序
python main.py --cookie "your_cookie_string"

# 或先运行再配置
python main.py
# 然后打开 http://127.0.0.1:8080 在网页中配置
```

### 方式二：单EXE运行 (Windows)

```bash
# 1. 安装打包依赖
pip install pyinstaller

# 2. 执行打包
python build.py

# 3. 运行生成的EXE
dist/CMCCCloudWebDAV.exe
```

## 使用方法

### 1. 获取Cookie

1. 用浏览器登录 [yun.139.com](https://yun.139.com)
2. 按 `F12` 打开开发者工具
3. 切换到 **Network** (网络) 面板
4. 刷新页面，找到任意请求（如 `list` 或 `get`）
5. 在请求头中找到 `Cookie:` 字段，复制完整内容
6. 粘贴到管理界面的"配置管理"页面

### 2. 配置认证

打开管理界面 `http://127.0.0.1:8080`，进入"配置管理"：

- **Cookie方式**（推荐）：直接粘贴完整Cookie字符串
- **手机号+Token方式**：填写手机号和从Cookie中提取的 `auth_token`

### 3. 启动WebDAV服务

在管理界面点击"启动服务"，或命令行：

```bash
python main.py --cookie "xxx" --port 8081
```

### 4. 映射网络驱动器

在Windows资源管理器中：

1. 点击"此电脑" -> "映射网络驱动器"
2. 输入WebDAV地址：`http://127.0.0.1:8081/`
3. 选择盘符（如 Z:）
4. 点击"完成"

> 注意：Windows 7可能需要先安装WebDAV重定向功能或修改注册表以支持基本认证。

### 5. Win7特殊配置

Windows 7默认对WebDAV支持有限，可能需要：

```cmd
# 启用基本认证 (以管理员运行cmd)
reg add "HKLM\SYSTEM\CurrentControlSet\Services\WebClient\Parameters" /v BasicAuthLevel /t REG_DWORD /d 2 /f

# 重启WebClient服务
net stop webclient
net start webclient
```

## 命令行参数

```
python main.py [选项]

  --config, -c    配置文件路径 (默认: config.json)
  --cookie        Cookie字符串
  --phone         手机号
  --token         Auth Token
  --host          WebDAV监听地址 (默认: 0.0.0.0)
  --port          WebDAV监听端口 (默认: 8081)
  --ui-port       管理界面端口 (默认: 8080)
  --readonly      只读模式
```

## 项目结构

```
cmcc-cloud-webdav/
├── main.py              # 主程序入口
├── cmcc_api.py          # 中国移动云盘API封装
├── webdav_provider.py   # WsgiDAV自定义提供者
├── web_ui.py            # 网页管理界面
├── tray_icon.py         # 系统托盘支持
├── build.py             # PyInstaller打包脚本
├── requirements.txt     # Python依赖
└── README.md            # 使用说明
```

## 技术原理

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                      Windows 资源管理器                      │
│                         (Z: 盘符)                           │
└────────────────────┬────────────────────────────────────────┘
                     │ WebDAV协议
┌────────────────────▼────────────────────────────────────────┐
│                   WsgiDAV 服务器                             │
│              (cheroot WSGI server)                          │
└────────────────────┬────────────────────────────────────────┘
                     │ CMCCCloudProvider
┌────────────────────▼────────────────────────────────────────┐
│              中国移动云盘 API 封装层                         │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│   │  file/  │ │ folder/ │ │recycle/ │ │  task/  │        │
│   │  list   │ │ create  │ │batchTrash│ │  get   │        │
│   │  get    │ │         │ │         │ │         │        │
│   │batchMove│ │         │ │         │ │         │        │
│   │batchCopy│ │         │ │         │ │         │        │
│   └─────────┘ └─────────┘ └─────────┘ └─────────┘        │
└────────────────────┬────────────────────────────────────────┘
                     │ HTTPS POST / JSON
┌────────────────────▼────────────────────────────────────────┐
│              中国移动云盘服务器                              │
│         https://personal-kd-njs.yun.139.com                │
└─────────────────────────────────────────────────────────────┘
```

### 核心流程

1. **文件列表 (PROPFIND)**：调用 `hcy/file/list` 获取文件夹内容，转换为WebDAV属性
2. **文件下载 (GET)**：调用 `hcy/file/get` 获取下载URL，流式传输文件内容
3. **文件上传 (PUT)**：接收二进制数据，调用 `hcy/file/upload` 上传到云盘
4. **删除 (DELETE)**：调用 `hcy/recyclebin/batchTrash` 移入回收站
5. **创建文件夹 (MKCOL)**：调用 `hcy/folder/create` 创建新文件夹
6. **重命名 (MOVE)**：调用 `hcy/file/rename` 修改文件名

### 认证机制

- 使用浏览器Cookie中的 `auth_token` 进行 Basic 认证
- 请求头包含 `Authorization: Basic base64(pc:手机号:token)`
- 每个请求附带 `mcloud-sign` 时间戳签名

## 注意事项

1. **Cookie有效期**：中国移动云盘的Cookie会过期，失效后需要重新获取
2. **上传限制**：大文件上传可能需要较长时间，建议分批操作
3. **API限制**：频繁操作可能触发限流，建议适当控制请求频率
4. **仅供学习**：本项目基于抓包分析，仅供个人学习研究使用
5. **Win7兼容**：Windows 7可能需要额外配置WebDAV客户端支持

## 依赖说明

| 包名 | 版本 | 用途 |
|------|------|------|
| requests | >=2.28 | HTTP请求 |
| WsgiDAV | >=4.0 | WebDAV服务器框架 |
| cheroot | >=9.0 | WSGI服务器 |
| pystray | >=0.19 | 系统托盘 |
| Pillow | >=9.0 | 图标绘制 |
| pywin32 | >=304 | Windows API (Win7) |

## 开源协议

MIT License - 仅供学习研究使用

> ⚠️ 免责声明：本项目与中国移动官方无关，使用风险自负。请遵守相关法律法规和服务条款。
