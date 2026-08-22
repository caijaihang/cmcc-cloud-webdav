# ☁️ 中国移动云盘 WebDAV v1.1

将中国移动云盘 (yun.139.com) 映射为本地 WebDAV 磁盘，支持读写操作。

## 功能特性

- **文件浏览**：像操作本地磁盘一样浏览云盘文件
- **文件上传**：支持小文件直传、大文件分片上传（>10MB自动分片）、秒传检查
- **文件下载**：支持流式下载、断点续传（Range请求）
- **文件夹操作**：创建、删除、重命名、移动、复制（含递归复制）
- **回收站**：支持移入回收站、还原、彻底删除、清空回收站
- **文件搜索**：支持全盘/文件夹内递归搜索
- **分享管理**：创建分享、获取分享列表、取消分享、保存他人分享
- **星标文件**：添加/取消星标、查看星标列表
- **分类浏览**：按图片、视频、音频、文档、应用分类浏览
- **最近文件**：查看最近访问的文件
- **文件历史**：查看和恢复文件历史版本
- **离线下载**：添加和管理离线下载任务
- **容量显示**：实时显示总容量、已用、可用空间
- **系统托盘**：最小化到托盘，方便管理
- **管理界面**：Web UI 配置管理，支持一键获取 Cookie
- **日志持久化**：运行日志自动保存到文件
- **WebDAV认证**：可选Basic Auth认证保护
- **自动重连**：API连接断开自动恢复
- **心跳检测**：定期检测云盘连接状态

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Cookie

1. 用 Chrome/Edge 登录 [yun.139.com](https://yun.139.com)
2. 按 F12 打开开发者工具 → Application/Storage → Cookies
3. 复制完整的 Cookie 字符串

或使用书签脚本自动获取（推荐）：
1. 启动程序后打开管理界面 `http://127.0.0.1:8080`
2. 进入"配置管理" → "自动获取 Cookie"
3. 按提示操作

### 3. 启动服务

```bash
python main.py
```

或使用命令行参数：

```bash
python main.py --cookie "你的Cookie字符串" --port 8081 --ui-port 8080
```

### 4. 映射网络驱动器

Windows 资源管理器 → 此电脑 → 映射网络驱动器：

```
http://127.0.0.1:8081/
```

认证方式：Basic 认证（如果启用了认证，使用配置的用户名密码；否则任意用户名密码）

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config` | 配置文件路径 | `config.json` |
| `--cookie` | Cookie 字符串 | - |
| `--phone` | 手机号 | - |
| `--token` | Auth Token | - |
| `--host` | WebDAV 监听地址 | `0.0.0.0` |
| `--port` | WebDAV 端口 | `8081` |
| `--ui-port` | 管理界面端口 | `8080` |
| `--readonly` | 只读模式 | `False` |
| `--auth` | 启用WebDAV认证 | `False` |
| `--username` | WebDAV用户名 | `admin` |
| `--password` | WebDAV密码 | `admin` |
| `--no-browser` | 不自动打开浏览器 | `False` |
| `--no-tray` | 不启用系统托盘 | `False` |
| `--no-reconnect` | 禁用自动重连 | `False` |

## 项目结构

```
cmcc-cloud-webdav/
├── main.py              # 主程序入口
├── cmcc_api.py          # 移动云盘 API 封装（完整接口）
├── webdav_provider.py   # WebDAV 提供者（Range/流式/锁定）
├── web_ui.py            # Web 管理界面（文件/分享/回收站/星标）
├── tray_icon.py         # 系统托盘图标
├── build.py             # 打包脚本
├── requirements.txt     # 依赖列表
├── config.json          # 配置文件（自动生成）
├── logs/                # 日志目录
└── static/              # 静态资源
```

## API 接口列表

### 文件操作
- `list_files()` - 获取文件列表
- `list_all_files()` - 获取所有文件（自动分页）
- `get_file()` - 获取文件详情
- `create_folder()` - 创建文件夹
- `create_folders()` - 递归创建文件夹路径
- `rename_file()` - 重命名
- `batch_rename()` - 批量重命名
- `move_file()` - 移动文件
- `copy_file()` - 复制文件
- `delete_file()` - 删除文件（移入回收站）
- `batch_delete()` - 批量删除

### 上传下载
- `upload_file()` - 上传文件（自动分片）
- `upload_data()` - 上传二进制数据
- `check_file_exists()` - 秒传检查
- `cancel_upload()` - 取消上传
- `get_download_url()` - 获取下载URL
- `download_file()` - 下载文件内容
- `download_file_stream()` - 流式下载
- `download_file_range()` - 断点续传
- `get_file_md5()` - 获取文件MD5
- `get_file_preview()` - 文件预览
- `get_file_thumbnail()` - 缩略图

### 分享
- `share_file()` - 创建分享
- `get_share_list()` - 获取分享列表
- `cancel_share()` - 取消分享
- `get_share_detail()` - 获取分享详情
- `save_shared_file()` - 保存分享文件
- `get_share_access_url()` - 获取分享访问链接

### 回收站
- `list_trash()` - 回收站列表
- `restore_from_trash()` - 还原文件
- `permanent_delete()` - 彻底删除
- `get_recyclebin_info()` - 回收站信息
- `empty_recyclebin()` - 清空回收站

### 星标
- `star_file()` - 添加星标
- `unstar_file()` - 取消星标
- `get_starred_files()` - 星标文件列表

### 分类/搜索
- `get_category_files()` - 按分类获取文件
- `get_recent_files()` - 最近文件
- `search_files()` - 搜索文件
- `search_files_api()` - API搜索

### 其他
- `get_file_history()` - 文件历史版本
- `restore_file_version()` - 恢复版本
- `add_offline_download()` - 添加离线下载
- `get_offline_download_list()` - 离线下载列表
- `get_offline_download_status()` - 离线下载状态
- `cancel_offline_download()` - 取消离线下载
- `get_user_info()` - 用户信息
- `get_capacity()` - 容量查询
- `get_storage_info()` - 存储信息
- `get_file_count()` - 文件统计
- `get_folder_size()` - 文件夹大小

## 打包为单文件

```bash
python build.py
```

输出：`dist/cmcc-webdav.exe`（Windows）或 `dist/cmcc-webdav`（Linux/macOS）

## 注意事项

1. **Cookie 过期**：移动云盘 Cookie 有过期时间，失效后需重新获取
2. **API 限制**：基于抓包分析实现，API 可能随时变更
3. **仅供学习**：本项目仅供个人学习研究使用
4. **Win7 用户**：需修改注册表启用 Basic 认证（见管理界面说明）

## 技术栈

- Python 3.8+
- WsgiDAV：WebDAV 服务器框架
- requests：HTTP 客户端
- cheroot：WSGI 服务器
- pystray：系统托盘
- Pillow：图标生成
