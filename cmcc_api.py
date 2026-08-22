#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国移动云盘 (yun.139.com) API 封装
基于 Chrome DevTools 抓包分析实现

支持功能:
- 文件/文件夹: 列表、创建、重命名、移动、复制、删除
- 上传下载: 小文件直传、大文件分片、秒传检查、流式下载、断点续传
- 分享: 创建分享、获取分享列表、取消分享、保存分享文件
- 回收站: 列表、还原、彻底删除、清空
- 星标: 添加、取消、列表
- 分类: 图片、视频、音频、文档、应用等分类浏览
- 最近文件、文件历史版本、离线下载
- 用户信息、容量查询、存储统计
- 搜索: 全盘/文件夹内搜索
- 缓存: 文件列表缓存、路径解析缓存

改进点:
1. 完整的API覆盖（文档中所有接口）
2. 签名算法更接近实际
3. 上传支持分片、秒传、进度回调
4. 下载支持真实URL获取、流式、断点续传
5. 请求重试、限流、超时控制
6. 多级缓存机制
7. 完善的错误处理
"""

import requests
import json
import base64
import time
import uuid
import hashlib
import os
import re
import threading
from datetime import datetime
from urllib.parse import quote, unquote

# 根目录ID
ROOT_FOLDER_ID = "DFn_Mm9QAFQA0611WrpTl1Oy00019700101000000044"

# API基础域名
BASE_URL = "https://personal-kd-njs.yun.139.com"
ORCH_URL = "https://yun.139.com"

# 文件分类常量
CATEGORY_IMAGE = 1
CATEGORY_VIDEO = 2
CATEGORY_AUDIO = 3
CATEGORY_DOCUMENT = 4
CATEGORY_APPLICATION = 5
CATEGORY_OTHER = 6
CATEGORY_ALL = 0


class CMCCCloudAPI:
    """中国移动云盘API客户端"""

    def __init__(self, phone=None, auth_token=None, cookie_str=None):
        self.phone = phone
        self.auth_token = auth_token
        self.cookie_str = cookie_str
        self.session = requests.Session()
        self.ud_id = None
        self._cache = {}
        self._cache_time = {}
        self._cache_lock = threading.Lock()
        self._path_cache = {}
        self._path_cache_time = {}
        self._cache_ttl = 30
        self._last_request_time = 0
        self._min_interval = 0.1
        self._init_headers()

    def _init_headers(self):
        """初始化通用请求头"""
        self.base_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "CMS-DEVICE": "default",
            "Content-Type": "application/json;charset=UTF-8",
            "INNER-HCY-ROUTER-HTTPS": "1",
            "Origin": "https://yun.139.com",
            "Referer": "https://yun.139.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36",
            "X-Deviceinfo": "||9|7.17.11|chrome|103.0.0.0||dW5kZWZpbmVk||",
            "caller": "web",
            "mcloud-channel": "1000101",
            "mcloud-client": "10701",
            "mcloud-route": "001",
            "mcloud-version": "7.17.11",
            "x-SvcType": "1",
            "x-huawei-channelSrc": "10000034",
            "x-inner-ntwk": "2",
            "x-m4c-caller": "PC",
            "x-m4c-src": "10002",
            "x-yun-api-version": "v1",
            "x-yun-app-channel": "10000034",
            "x-yun-channel-source": "10000034",
            "x-yun-client-info": "||9|7.17.11|chrome|103.0.0.0||dW5kZWZpbmVk||",
            "x-yun-module-type": "100",
            "x-yun-svc-type": "1",
        }

        if self.cookie_str:
            self.session.headers.update({"Cookie": self.cookie_str})
            self._parse_cookie()
            match = re.search(r'authorization=([^;]+)', self.cookie_str)
            if match:
                auth_val = unquote(match.group(1)).strip()
                self.base_headers["Authorization"] = auth_val
        elif self.phone and self.auth_token:
            auth_raw = f"pc:{self.phone}:{self.auth_token}"
            auth_b64 = base64.b64encode(auth_raw.encode()).decode()
            self.base_headers["Authorization"] = f"Basic {auth_b64}"

    def _parse_cookie(self):
        """从Cookie字符串解析关键信息"""
        if not self.cookie_str:
            return
        match = re.search(r'auth_token=([^;]+)', self.cookie_str)
        if match:
            self.auth_token = unquote(match.group(1))
        match = re.search(r'authorization=([^;]+)', self.cookie_str)
        if match:
            try:
                auth_val = unquote(match.group(1)).strip()
                if auth_val.startswith('Basic '):
                    auth_val = auth_val[6:]
                auth_decoded = base64.b64decode(auth_val).decode()
                parts = auth_decoded.split(':')
                if len(parts) >= 2:
                    self.phone = parts[1]
            except:
                pass
        match = re.search(r'ud_id=([^;]+)', self.cookie_str)
        if match:
            self.ud_id = match.group(1)

    def _make_sign(self):
        """生成mcloud-sign签名"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        random_str = uuid.uuid4().hex[:16]
        sign_str = f"{now},{random_str}"
        md5_hash = hashlib.md5(sign_str.encode()).hexdigest().upper()
        return f"{now},{random_str},{md5_hash}"

    def _rate_limit(self):
        """请求限流"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _request(self, method, url, data=None, headers=None, retry=3, timeout=30):
        """发送HTTP请求，带重试"""
        self._rate_limit()
        h = dict(self.base_headers)
        if headers:
            h.update(headers)
        h["mcloud-sign"] = self._make_sign()

        last_error = None
        for attempt in range(retry):
            try:
                if method.upper() == "GET":
                    resp = self.session.get(url, headers=h, timeout=timeout)
                else:
                    resp = self.session.post(url, json=data, headers=h, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout:
                last_error = "请求超时"
                if attempt < retry - 1:
                    time.sleep(1 * (attempt + 1))
            except requests.exceptions.ConnectionError as e:
                last_error = f"连接失败: {e}"
                if attempt < retry - 1:
                    time.sleep(1 * (attempt + 1))
            except Exception as e:
                last_error = str(e)
                break
        return {"success": False, "code": -1, "message": last_error or "未知错误"}

    def _get_cache_key(self, folder_id):
        return folder_id or ROOT_FOLDER_ID

    def _get_cached_files(self, folder_id):
        with self._cache_lock:
            key = self._get_cache_key(folder_id)
            if key in self._cache:
                cache_time = self._cache_time.get(key, 0)
                if time.time() - cache_time < self._cache_ttl:
                    return self._cache[key]
            return None

    def _set_cached_files(self, folder_id, files):
        with self._cache_lock:
            key = self._get_cache_key(folder_id)
            self._cache[key] = files
            self._cache_time[key] = time.time()

    def _invalidate_cache(self, folder_id=None):
        with self._cache_lock:
            if folder_id:
                key = self._get_cache_key(folder_id)
                self._cache.pop(key, None)
                self._cache_time.pop(key, None)
            else:
                self._cache.clear()
                self._cache_time.clear()
            self._path_cache.clear()
            self._path_cache_time.clear()

    # ==================== 文件列表 ====================

    def list_files(self, parent_file_id=None, page_size=100, page_cursor=None,
                   order_by="updated_at", order_direction="DESC", use_cache=True):
        """获取文件列表"""
        if use_cache and page_cursor is None:
            cached = self._get_cached_files(parent_file_id)
            if cached is not None:
                return {
                    "success": True, "code": 0, "message": "ok",
                    "data": {
                        "getFileCount": len(cached),
                        "fileListAO": {"fileList": cached, "fileListSize": len(cached)}
                    }
                }
        url = f"{BASE_URL}/hcy/file/list"
        data = {
            "pageInfo": {"pageSize": page_size, "pageCursor": page_cursor},
            "orderBy": order_by, "orderDirection": order_direction,
            "parentFileId": parent_file_id or ROOT_FOLDER_ID,
            "imageThumbnailStyleList": ["Small", "Large"]
        }
        result = self._request("POST", url, data)
        if use_cache and result.get("success") and page_cursor is None:
            files = result.get("data", {}).get("fileListAO", {}).get("fileList", [])
            self._set_cached_files(parent_file_id, files)
        return result

    def get_file(self, file_id):
        """获取单个文件详情"""
        url = f"{BASE_URL}/hcy/file/get"
        data = {"fileId": file_id}
        return self._request("POST", url, data)

    def list_all_files(self, parent_file_id=None, use_cache=True):
        """获取文件夹下所有文件（自动分页）"""
        if use_cache:
            cached = self._get_cached_files(parent_file_id)
            if cached is not None:
                return cached
        all_files = []
        cursor = None
        while True:
            resp = self.list_files(parent_file_id=parent_file_id, page_cursor=cursor, use_cache=False)
            if not resp.get("success"):
                break
            file_list = resp.get("data", {}).get("fileListAO", {}).get("fileList", [])
            all_files.extend(file_list)
            cursor = resp.get("data", {}).get("pageInfo", {}).get("pageCursor")
            if not cursor or len(file_list) == 0:
                break
        if use_cache:
            self._set_cached_files(parent_file_id, all_files)
        return all_files

    def get_file_count(self, parent_file_id=None):
        """获取文件夹下文件数量统计"""
        url = f"{BASE_URL}/hcy/file/getFileCount"
        data = {"parentFileId": parent_file_id or ROOT_FOLDER_ID}
        return self._request("POST", url, data)

    def get_folder_size(self, folder_id):
        """获取文件夹大小"""
        url = f"{BASE_URL}/hcy/folder/getSize"
        data = {"folderId": folder_id}
        return self._request("POST", url, data)

    # ==================== 搜索 ====================

    def search_files(self, keyword, parent_file_id=None):
        """搜索文件（递归搜索）"""
        all_files = []
        def search_recursive(folder_id, depth=0):
            if depth > 10:
                return
            files = self.list_all_files(folder_id, use_cache=True)
            for f in files:
                name = f.get("fileName", "")
                if keyword.lower() in name.lower():
                    all_files.append(f)
                if f.get("fileType") == 2:
                    search_recursive(f.get("fileId"), depth + 1)
        search_recursive(parent_file_id or ROOT_FOLDER_ID)
        return all_files

    def search_files_api(self, keyword, parent_file_id=None, page_size=100):
        """使用API搜索文件（如果服务端支持）"""
        url = f"{BASE_URL}/hcy/file/search"
        data = {
            "keyword": keyword,
            "parentFileId": parent_file_id or ROOT_FOLDER_ID,
            "pageInfo": {"pageSize": page_size, "pageCursor": None}
        }
        return self._request("POST", url, data)

    # ==================== 分类浏览 ====================

    def get_category_files(self, category=CATEGORY_ALL, page_size=100, page_cursor=None):
        """
        按分类获取文件
        category: 0=全部, 1=图片, 2=视频, 3=音频, 4=文档, 5=应用, 6=其他
        """
        url = f"{BASE_URL}/hcy/file/listByCategory"
        data = {
            "category": category,
            "pageInfo": {"pageSize": page_size, "pageCursor": page_cursor}
        }
        return self._request("POST", url, data)

    def get_recent_files(self, days=30, page_size=100):
        """获取最近文件"""
        url = f"{BASE_URL}/hcy/file/listRecent"
        data = {"days": days, "pageInfo": {"pageSize": page_size, "pageCursor": None}}
        return self._request("POST", url, data)

    # ==================== 文件夹操作 ====================

    def create_folder(self, folder_name, parent_file_id=None):
        """创建文件夹"""
        url = f"{BASE_URL}/hcy/folder/create"
        data = {"folderName": folder_name, "parentFileId": parent_file_id or ROOT_FOLDER_ID}
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache(parent_file_id)
        return result

    def create_folders(self, folder_path, parent_file_id=None):
        """
        递归创建文件夹路径
        例如: create_folders("a/b/c") 会创建 a -> a/b -> a/b/c
        """
        parts = [p for p in folder_path.split("/") if p]
        current_id = parent_file_id or ROOT_FOLDER_ID
        for part in parts:
            children = self.list_all_files(current_id, use_cache=False)
            found = False
            for child in children:
                if child.get("fileName") == part and child.get("fileType") == 2:
                    current_id = child.get("fileId")
                    found = True
                    break
            if not found:
                result = self.create_folder(part, current_id)
                if result.get("success"):
                    current_id = result.get("data", {}).get("fileId") or result.get("data", {}).get("catalogID")
                    if not current_id:
                        return None
                else:
                    return None
        return current_id

    # ==================== 上传 ====================

    def check_file_exists(self, file_name, file_size, parent_file_id=None):
        """秒传检查 - 检查文件是否已存在"""
        url = f"{BASE_URL}/hcy/file/checkExist"
        data = {
            "fileName": file_name,
            "fileSize": file_size,
            "parentFileId": parent_file_id or ROOT_FOLDER_ID
        }
        return self._request("POST", url, data)

    def get_upload_url(self, file_name, file_size, parent_file_id=None):
        """获取上传URL（预上传）"""
        url = f"{BASE_URL}/hcy/file/upload"
        data = {
            "fileName": file_name, "fileSize": file_size,
            "parentFileId": parent_file_id or ROOT_FOLDER_ID,
            "checkNameMode": 1
        }
        return self._request("POST", url, data)

    def upload_file(self, file_path, parent_file_id=None, file_name=None, progress_callback=None):
        """上传文件（自动选择小文件直传或大文件分片）"""
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}
        file_name = file_name or os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        parent_id = parent_file_id or ROOT_FOLDER_ID

        # 秒传检查
        check = self.check_file_exists(file_name, file_size, parent_id)
        if check.get("success") and check.get("data", {}).get("isExist"):
            if progress_callback:
                progress_callback(100, file_size, file_size)
            return {"success": True, "message": "秒传成功", "data": check.get("data")}

        if file_size < 10 * 1024 * 1024:
            return self._upload_small_file(file_path, file_name, file_size, parent_id, progress_callback)
        return self._upload_large_file(file_path, file_name, file_size, parent_id, progress_callback)

    def _upload_small_file(self, file_path, file_name, file_size, parent_id, progress_callback=None):
        """上传小文件（<10MB）"""
        url = f"{BASE_URL}/hcy/file/upload"
        with open(file_path, 'rb') as f:
            file_data = f.read()
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"
        body = []
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="parentFileId"')
        body.append('')
        body.append(parent_id)
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="fileName"')
        body.append('')
        body.append(file_name)
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="fileSize"')
        body.append('')
        body.append(str(file_size))
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"')
        body.append('Content-Type: application/octet-stream')
        body.append('')
        body_bytes = '\r\n'.join(body).encode('utf-8') + b'\r\n'
        body_bytes += file_data + b'\r\n'
        body_bytes += f'--{boundary}--\r\n'.encode('utf-8')
        headers = dict(self.base_headers)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        del headers["mcloud-sign"]
        try:
            resp = self.session.post(url, data=body_bytes, headers=headers, timeout=300)
            result = resp.json()
            if result.get("success"):
                self._invalidate_cache(parent_id)
                if progress_callback:
                    progress_callback(100, file_size, file_size)
            return result
        except Exception as e:
            return {"success": False, "message": f"上传失败: {e}"}

    def _upload_large_file(self, file_path, file_name, file_size, parent_id, progress_callback=None):
        """分片上传大文件"""
        chunk_size = 4 * 1024 * 1024
        chunks = (file_size + chunk_size - 1) // chunk_size
        uploaded = 0
        chunk_md5s = []
        with open(file_path, 'rb') as f:
            for i in range(chunks):
                chunk_data = f.read(chunk_size)
                chunk_md5 = hashlib.md5(chunk_data).hexdigest()
                chunk_md5s.append(chunk_md5)
                result = self._upload_chunk(chunk_data, chunk_md5, i, chunks, file_name, parent_id)
                if not result.get("success"):
                    return result
                uploaded += len(chunk_data)
                if progress_callback:
                    percent = int(uploaded / file_size * 100)
                    progress_callback(percent, uploaded, file_size)
        return self._merge_chunks(file_name, file_size, parent_id, chunk_md5s)

    def _upload_chunk(self, chunk_data, chunk_md5, chunk_index, total_chunks, file_name, parent_id):
        """上传单个分片"""
        url = f"{BASE_URL}/hcy/file/uploadChunk"
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"
        body = []
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="parentFileId"')
        body.append('')
        body.append(parent_id)
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="fileName"')
        body.append('')
        body.append(file_name)
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="chunkIndex"')
        body.append('')
        body.append(str(chunk_index))
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="totalChunks"')
        body.append('')
        body.append(str(total_chunks))
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="chunkMd5"')
        body.append('')
        body.append(chunk_md5)
        body.append(f'--{boundary}')
        body.append(f'Content-Disposition: form-data; name="file"; filename="chunk_{chunk_index}"')
        body.append('Content-Type: application/octet-stream')
        body.append('')
        body_bytes = '\r\n'.join(body).encode('utf-8') + b'\r\n'
        body_bytes += chunk_data + b'\r\n'
        body_bytes += f'--{boundary}--\r\n'.encode('utf-8')
        headers = dict(self.base_headers)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        del headers["mcloud-sign"]
        try:
            resp = self.session.post(url, data=body_bytes, headers=headers, timeout=120)
            return resp.json()
        except Exception as e:
            return {"success": False, "message": f"分片上传失败: {e}"}

    def _merge_chunks(self, file_name, file_size, parent_id, chunk_md5s):
        """合并分片"""
        url = f"{BASE_URL}/hcy/file/mergeChunks"
        data = {"fileName": file_name, "fileSize": file_size, "parentFileId": parent_id, "chunkMd5s": chunk_md5s}
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache(parent_id)
        return result

    def upload_data(self, data, file_name, parent_file_id=None, progress_callback=None):
        """上传二进制数据"""
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            temp_path = f.name
        try:
            return self.upload_file(temp_path, parent_file_id, file_name, progress_callback)
        finally:
            os.unlink(temp_path)

    def cancel_upload(self, upload_id):
        """取消上传"""
        url = f"{BASE_URL}/hcy/file/cancelUpload"
        data = {"uploadId": upload_id}
        return self._request("POST", url, data)

    # ==================== 下载 ====================

    def get_download_url(self, file_id):
        """获取文件下载URL"""
        file_info = self.get_file(file_id)
        if not file_info.get("success"):
            return None
        file_data = file_info.get("data", {})
        download_url = (
            file_data.get("downloadUrl") or file_data.get("contentUrl") or
            file_data.get("url") or file_data.get("fileUrl") or
            file_data.get("downloadURL") or file_data.get("presignedUrl")
        )
        if download_url and isinstance(download_url, str) and download_url.startswith("http"):
            return download_url
        url = f"{BASE_URL}/hcy/file/getDownloadUrl"
        data = {"fileId": file_id}
        result = self._request("POST", url, data)
        if result.get("success"):
            url_data = result.get("data", {})
            if isinstance(url_data, str) and url_data.startswith("http"):
                return url_data
            return url_data.get("downloadUrl") or url_data.get("url") or url_data.get("fileUrl")
        return None

    def download_file(self, file_id):
        """下载文件内容"""
        download_url = self.get_download_url(file_id)
        if not download_url:
            return None
        try:
            resp = self.session.get(download_url, timeout=300, stream=True)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            print(f"[Download Error] {e}")
            return None

    def download_file_stream(self, file_id, chunk_size=64*1024):
        """流式下载文件（生成器）"""
        download_url = self.get_download_url(file_id)
        if not download_url:
            yield None
            return
        try:
            resp = self.session.get(download_url, timeout=300, stream=True)
            resp.raise_for_status()
            for chunk in resp.iter_content(chunk_size=chunk_size):
                if chunk:
                    yield chunk
        except Exception as e:
            print(f"[Stream Download Error] {e}")
            yield None

    def download_file_range(self, file_id, start, end):
        """断点续传下载指定范围"""
        download_url = self.get_download_url(file_id)
        if not download_url:
            return None
        try:
            headers = {"Range": f"bytes={start}-{end}"}
            resp = self.session.get(download_url, headers=headers, timeout=300)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            print(f"[Range Download Error] {e}")
            return None

    def get_file_md5(self, file_id):
        """获取文件MD5"""
        url = f"{BASE_URL}/hcy/file/getMd5"
        data = {"fileId": file_id}
        return self._request("POST", url, data)

    def get_file_preview(self, file_id):
        """获取文件预览信息"""
        url = f"{BASE_URL}/hcy/file/preview"
        data = {"fileId": file_id}
        return self._request("POST", url, data)

    def get_file_thumbnail(self, file_id, size="Small"):
        """获取文件缩略图URL"""
        url = f"{BASE_URL}/hcy/file/thumbnail"
        data = {"fileId": file_id, "size": size}
        return self._request("POST", url, data)

    # ==================== 删除 ====================

    def delete_file(self, file_id):
        """删除单个文件（移入回收站）"""
        return self.batch_delete([file_id])

    def batch_delete(self, file_ids):
        """批量删除（移入回收站）"""
        url = f"{BASE_URL}/hcy/recyclebin/batchTrash"
        data = {"fileIds": file_ids if isinstance(file_ids, list) else [file_ids]}
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache()
        return result

    def restore_from_trash(self, file_ids):
        """从回收站还原"""
        url = f"{BASE_URL}/hcy/recyclebin/batchRestore"
        data = {"fileIds": file_ids if isinstance(file_ids, list) else [file_ids]}
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache()
        return result

    def permanent_delete(self, file_ids):
        """彻底删除"""
        url = f"{BASE_URL}/hcy/recyclebin/batchDelete"
        data = {"fileIds": file_ids if isinstance(file_ids, list) else [file_ids]}
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache()
        return result

    def list_trash(self, page_size=100, page_cursor=None):
        """获取回收站列表"""
        url = f"{BASE_URL}/hcy/recyclebin/list"
        data = {"pageInfo": {"pageSize": page_size, "pageCursor": page_cursor}}
        return self._request("POST", url, data)

    def get_recyclebin_info(self):
        """获取回收站信息（数量、大小）"""
        url = f"{BASE_URL}/hcy/recyclebin/getInfo"
        return self._request("POST", url, {})

    def empty_recyclebin(self):
        """清空回收站"""
        url = f"{BASE_URL}/hcy/recyclebin/empty"
        result = self._request("POST", url, {})
        if result.get("success"):
            self._invalidate_cache()
        return result

    # ==================== 重命名 ====================

    def rename_file(self, file_id, new_name):
        """重命名文件/文件夹"""
        url = f"{BASE_URL}/hcy/file/rename"
        data = {"fileId": file_id, "fileName": new_name}
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache()
        return result

    def batch_rename(self, renames):
        """
        批量重命名
        renames: [{"fileId": "xxx", "fileName": "new_name"}, ...]
        """
        url = f"{BASE_URL}/hcy/file/batchRename"
        data = {"renameList": renames}
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache()
        return result

    # ==================== 移动/复制 ====================

    def move_file(self, file_ids, dest_parent_id):
        """移动文件"""
        url = f"{BASE_URL}/hcy/file/batchMove"
        data = {
            "fileIds": file_ids if isinstance(file_ids, list) else [file_ids],
            "destParentFileId": dest_parent_id
        }
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache()
        return result

    def copy_file(self, file_ids, dest_parent_id):
        """复制文件"""
        url = f"{BASE_URL}/hcy/file/batchCopy"
        data = {
            "fileIds": file_ids if isinstance(file_ids, list) else [file_ids],
            "destParentFileId": dest_parent_id
        }
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache(dest_parent_id)
        return result

    # ==================== 分享 ====================

    def share_file(self, file_ids, share_name=None, expire_days=7, share_type=1, password=None):
        """
        创建分享
        share_type: 1=公开分享, 2=私密分享(带密码)
        """
        url = f"{BASE_URL}/hcy/share/create"
        data = {
            "fileIds": file_ids if isinstance(file_ids, list) else [file_ids],
            "shareName": share_name,
            "expireDays": expire_days,
            "shareType": share_type,
            "password": password
        }
        return self._request("POST", url, data)

    def get_share_list(self, page_size=100, page_cursor=None):
        """获取我的分享列表"""
        url = f"{BASE_URL}/hcy/share/list"
        data = {"pageInfo": {"pageSize": page_size, "pageCursor": page_cursor}}
        return self._request("POST", url, data)

    def cancel_share(self, share_ids):
        """取消分享"""
        url = f"{BASE_URL}/hcy/share/cancel"
        data = {"shareIds": share_ids if isinstance(share_ids, list) else [share_ids]}
        return self._request("POST", url, data)

    def get_share_detail(self, share_id):
        """获取分享详情"""
        url = f"{BASE_URL}/hcy/share/detail"
        data = {"shareId": share_id}
        return self._request("POST", url, data)

    def save_shared_file(self, share_id, file_ids, dest_parent_id=None, password=None):
        """保存分享文件到我的云盘"""
        url = f"{BASE_URL}/hcy/share/save"
        data = {
            "shareId": share_id,
            "fileIds": file_ids if isinstance(file_ids, list) else [file_ids],
            "destParentFileId": dest_parent_id or ROOT_FOLDER_ID,
            "password": password
        }
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache(dest_parent_id)
        return result

    def get_share_access_url(self, share_id, password=None):
        """获取分享访问链接"""
        url = f"{BASE_URL}/hcy/share/getAccessUrl"
        data = {"shareId": share_id, "password": password}
        return self._request("POST", url, data)

    # ==================== 星标 ====================

    def star_file(self, file_ids):
        """添加星标"""
        url = f"{BASE_URL}/hcy/file/star"
        data = {"fileIds": file_ids if isinstance(file_ids, list) else [file_ids]}
        return self._request("POST", url, data)

    def unstar_file(self, file_ids):
        """取消星标"""
        url = f"{BASE_URL}/hcy/file/unstar"
        data = {"fileIds": file_ids if isinstance(file_ids, list) else [file_ids]}
        return self._request("POST", url, data)

    def get_starred_files(self, page_size=100, page_cursor=None):
        """获取星标文件列表"""
        url = f"{BASE_URL}/hcy/file/listStarred"
        data = {"pageInfo": {"pageSize": page_size, "pageCursor": page_cursor}}
        return self._request("POST", url, data)

    # ==================== 文件历史版本 ====================

    def get_file_history(self, file_id, page_size=100):
        """获取文件历史版本"""
        url = f"{BASE_URL}/hcy/file/history"
        data = {"fileId": file_id, "pageInfo": {"pageSize": page_size, "pageCursor": None}}
        return self._request("POST", url, data)

    def restore_file_version(self, file_id, version_id):
        """恢复到指定版本"""
        url = f"{BASE_URL}/hcy/file/restoreVersion"
        data = {"fileId": file_id, "versionId": version_id}
        result = self._request("POST", url, data)
        if result.get("success"):
            self._invalidate_cache()
        return result

    # ==================== 离线下载 ====================

    def add_offline_download(self, url, file_name=None, parent_file_id=None):
        """添加离线下载任务"""
        api_url = f"{BASE_URL}/hcy/offlineDownload/add"
        data = {
            "url": url,
            "fileName": file_name,
            "parentFileId": parent_file_id or ROOT_FOLDER_ID
        }
        return self._request("POST", api_url, data)

    def get_offline_download_list(self, page_size=100, page_cursor=None):
        """获取离线下载任务列表"""
        url = f"{BASE_URL}/hcy/offlineDownload/list"
        data = {"pageInfo": {"pageSize": page_size, "pageCursor": page_cursor}}
        return self._request("POST", url, data)

    def get_offline_download_status(self, task_id):
        """获取离线下载任务状态"""
        url = f"{BASE_URL}/hcy/offlineDownload/status"
        data = {"taskId": task_id}
        return self._request("POST", url, data)

    def cancel_offline_download(self, task_id):
        """取消离线下载任务"""
        url = f"{BASE_URL}/hcy/offlineDownload/cancel"
        data = {"taskId": task_id}
        return self._request("POST", url, data)

    # ==================== 用户/容量 ====================

    def get_user_info(self):
        """获取用户信息"""
        url = f"{BASE_URL}/hcy/user/get"
        data = {"account": self.phone} if self.phone else {}
        return self._request("POST", url, data)

    def get_capacity(self):
        """获取用户容量信息"""
        url = f"{ORCH_URL}/orchestration/personalCloud-rebuild/user/v1.0/qryUserCapacity"
        return self._request("POST", url, {})

    def get_user_domain(self):
        """查询用户域名"""
        url = f"{ORCH_URL}/orchestration/personalCloud-rebuild/user/v1.0/qryUserDomain"
        return self._request("POST", url, {})

    def get_index_catalog(self):
        """查询首页目录"""
        url = f"{ORCH_URL}/orchestration/personalCloud-rebuild/index/v1.0/qryIndexCatalog"
        return self._request("POST", url, {})

    def get_storage_info(self):
        """获取存储详细信息"""
        url = f"{BASE_URL}/hcy/user/storageInfo"
        return self._request("POST", url, {})

    def get_family_storage_info(self):
        """获取家庭云存储信息"""
        url = f"{BASE_URL}/hcy/family/storageInfo"
        return self._request("POST", url, {})

    # ==================== 任务查询 ====================

    def get_task_status(self, task_id):
        """查询异步任务状态"""
        url = f"{BASE_URL}/hcy/task/get"
        data = {"taskId": task_id}
        return self._request("POST", url, data)

    # ==================== 路径解析工具 ====================

    def resolve_path(self, path):
        """将路径解析为fileId，返回 (file_id, file_info)"""
        if not path or path == "/" or path == "":
            return ROOT_FOLDER_ID, {"fileType": 2, "fileName": "root"}
        with self._cache_lock:
            if path in self._path_cache:
                cache_time = self._path_cache_time.get(path, 0)
                if time.time() - cache_time < self._cache_ttl:
                    return self._path_cache[path]
        parts = [p for p in path.split("/") if p]
        if not parts:
            return ROOT_FOLDER_ID, {"fileType": 2, "fileName": "root"}
        current_id = ROOT_FOLDER_ID
        current_info = None
        for part in parts:
            found = False
            files = self.list_all_files(current_id)
            for f in files:
                if f.get("fileName") == part:
                    current_id = f.get("fileId")
                    current_info = f
                    found = True
                    break
            if not found:
                return None, None
        with self._cache_lock:
            self._path_cache[path] = (current_id, current_info)
            self._path_cache_time[path] = time.time()
        return current_id, current_info

    def get_children(self, folder_id):
        """获取文件夹下的所有子项"""
        return self.list_all_files(folder_id)

    def get_child_by_name(self, folder_id, name):
        """根据名称获取子项"""
        children = self.get_children(folder_id)
        for child in children:
            if child.get("fileName") == name:
                return child
        return None

    def get_parent_path(self, file_id):
        """根据fileId获取完整路径"""
        if file_id == ROOT_FOLDER_ID:
            return "/"
        info = self.get_file(file_id)
        if not info.get("success"):
            return None
        file_data = info.get("data", {})
        file_name = file_data.get("fileName", "")
        parent_id = file_data.get("parentFileId")
        if parent_id == ROOT_FOLDER_ID or not parent_id:
            return "/" + file_name
        parent_path = self.get_parent_path(parent_id)
        if parent_path is None:
            return None
        return parent_path + "/" + file_name

    def path_exists(self, path):
        """检查路径是否存在"""
        file_id, _ = self.resolve_path(path)
        return file_id is not None

    def is_folder(self, path):
        """检查路径是否是文件夹"""
        file_id, info = self.resolve_path(path)
        if info:
            return info.get("fileType") == 2
        return False


def create_api_from_cookie(cookie_str):
    """从Cookie字符串创建API实例"""
    return CMCCCloudAPI(cookie_str=cookie_str)


def create_api_from_creds(phone, auth_token):
    """从手机号和token创建API实例"""
    return CMCCCloudAPI(phone=phone, auth_token=auth_token)
