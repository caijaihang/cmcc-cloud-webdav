# ☁️ 中国移动云盘 WebDAV v1.2

将中国移动云盘 (yun.139.com) 映射为本地 WebDAV 磁盘，支持读写操作。

## 功能特性

- **文件浏览**：像操作本地磁盘一样浏览云盘文件
- **文件上传**：小文件直传、大文件分片（>10MB自动分片）、秒传检查
- **文件下载**：流式下载、断点续传（Range请求）
- **文件夹操作**：创建、删除、重命名、移动、复制（递归复制）
- **回收站**：移入回收站、还原、彻底删除、清空
- **文件搜索**：全盘/文件夹内递归搜索
- **分享管理**：创建分享（公开/私密/密码）、列表、取消、保存他人分享
- **星标文件**：添加/取消星标、查看列表
- **分类浏览**：图片、视频、音频、文档、应用
- **最近文件**：查看最近访问的文件
- **文件历史**：查看和恢复历史版本
- **离线下载**：添加/管理离线下载任务
- **容量显示**：实时显示总/已用/可用空间
- **系统托盘**：最小化到托盘
- **管理界面**：Web UI 配置管理，一键获取 Cookie
- **日志持久化**：运行日志自动保存
- **WebDAV认证**：可选 Basic Auth 保护
- **自动重连**：API 断开自动恢复
- **心跳检测**：定期检测连接状态
- **全平台支持**：Windows / Linux / macOS / Android

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Cookie

**方法 A：书签脚本自动获取（推荐）**
1. 用 Chrome/Edge 登录 [yun.139.com](https://yun.139.com)
2. 启动程序：`python main.py`
3. 浏览器自动打开 `http://127.0.0.1:8080`
4. 进入 **配置管理** → 点击 **"自动获取 Cookie"**
5. 按提示将按钮拖到书签栏，在 yun.139.com 页面点击该书签

**方法 B：手动复制**
1. 登录 [yun.139.com](https://yun.139.com)
2. 按 F12 → Application → Cookies → `https://yun.139.com`
3. 复制完整 Cookie 字符串

### 3. 启动服务

```bash
python main.py
```

或带参数：
```bash
python main.py --cookie "你的Cookie" --port 8081 --auth --username admin --password 123456
```

### 4. 映射网络驱动器

**Windows：**
1. 此电脑 → 右键 → 映射网络驱动器
2. 输入：`http://127.0.0.1:8081/`
3. 如果启用了认证，输入用户名密码

**Windows 7 额外配置：**
```cmd
reg add "HKLM\SYSTEM\CurrentControlSet\Services\WebClient\Parameters" /v BasicAuthLevel /t REG_DWORD /d 2 /f
net stop webclient && net start webclient
```

**macOS：** Finder → 前往 → 连接服务器 → `http://127.0.0.1:8081/`

**Linux：** `sudo mount -t davfs http://127.0.0.1:8081/ /mnt/cloud`

## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--config` | 配置文件路径 | `config.json` |
| `--cookie` | Cookie 字符串 | - |
| `--phone` | 手机号 | - |
| `--auth-token` / `--token` | 移动云盘 Auth Token（从Cookie提取） | - |
| `--host` | WebDAV 监听地址 | `0.0.0.0` |
| `--port` | WebDAV 端口 | `8081` |
| `--ui-port` | 管理界面端口 | `8080` |
| `--readonly` | 只读模式 | - |
| `--auth` | 启用 WebDAV 认证 | - |
| `--username` | WebDAV 用户名 | `admin` |
| `--password` | WebDAV 密码 | `admin` |
| `--no-browser` | 不自动打开浏览器 | - |
| `--no-tray` | 不启用系统托盘 | - |
| `--no-reconnect` | 禁用自动重连 | - |

## 项目结构

```
cmcc-cloud-webdav/
├── main.py              # 主程序入口
├── cmcc_api.py          # 移动云盘 API 封装（40+接口）
├── webdav_provider.py   # WebDAV 提供者（Range/流式/锁定）
├── web_ui.py            # Web 管理界面（7页面）
├── tray_icon.py         # 系统托盘图标
├── build.py             # 本地打包脚本
├── buildozer.spec       # Android 打包配置
├── requirements.txt     # 依赖列表
├── config.json          # 配置文件（自动生成）
├── logs/                # 日志目录
└── static/              # 静态资源
```

## API 接口列表

### 文件操作
`list_files`, `list_all_files`, `get_file`, `get_file_count`, `get_folder_size`, `create_folder`, `create_folders`, `rename_file`, `batch_rename`, `move_file`, `copy_file`, `delete_file`, `batch_delete`

### 上传下载
`upload_file`, `upload_data`, `check_file_exists`, `cancel_upload`, `get_download_url`, `download_file`, `download_file_stream`, `download_file_range`, `get_file_md5`, `get_file_preview`, `get_file_thumbnail`

### 分享
`share_file`, `get_share_list`, `cancel_share`, `get_share_detail`, `save_shared_file`, `get_share_access_url`

### 回收站
`list_trash`, `restore_from_trash`, `permanent_delete`, `get_recyclebin_info`, `empty_recyclebin`

### 星标
`star_file`, `unstar_file`, `get_starred_files`

### 分类/搜索
`get_category_files`, `get_recent_files`, `search_files`, `search_files_api`

### 历史/离线
`get_file_history`, `restore_file_version`, `add_offline_download`, `get_offline_download_list`, `get_offline_download_status`, `cancel_offline_download`

### 用户/容量
`get_user_info`, `get_capacity`, `get_storage_info`, `get_family_storage_info`, `get_user_domain`, `get_index_catalog`

## 打包

### 本地打包
```bash
python build.py --onefile
```

### Android 打包
```bash
pip install buildozer cython
buildozer android debug
```

### GitHub Actions 自动打包
Push 到 main 分支自动触发，支持 Windows/Linux/macOS/Android。

## 注意事项

1. Cookie 有过期时间，失效后需重新获取
2. 基于抓包分析实现，API 可能随时变更
3. 仅供个人学习研究使用
4. Win7 需修改注册表启用 Basic 认证

## 技术栈

Python 3.8+ / WsgiDAV / requests / cheroot / pystray / Pillow / buildozer
