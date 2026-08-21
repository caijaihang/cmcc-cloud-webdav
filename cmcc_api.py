#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国移动云盘 (yun.139.com) API 封装
基于 Chrome DevTools 抓包分析实现
支持: 列表/上传/下载/删除/重命名/创建文件夹/移动/复制
"""

import requests
import json
import base64
import time
import uuid
import hashlib
import os
import re
from datetime import datetime
from urllib.parse import quote, unquote

# 根目录ID
ROOT_FOLDER_ID = "DFn_Mm9QAFQA0611WrpTl1Oy00019700101000000044"

# API基础域名
BASE_URL = "https://personal-kd-njs.yun.139.com"
ORCH_URL = "https://yun.139.com"


class CMCCCloudAPI:
    """中国移动云盘API客户端"""

    def __init__(self, phone=None, auth_token=None, cookie_str=None):
        """
        初始化API客户端

        参数:
            phone: 手机号
            auth_token: 认证令牌 (从浏览器Cookie获取)
            cookie_str: 完整Cookie字符串 (可选，直接从浏览器复制)
        """
        self.phone = phone
        self.auth_token = auth_token
        self.cookie_str = cookie_str
        self.session = requests.Session()
        self.ud_id = None
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

        # 设置Authorization
        if self.cookie_str:
            self.session.headers.update({"Cookie": self.cookie_str})
            self._parse_cookie()
            # 从Cookie的authorization字段直接提取Authorization头，确保和浏览器一致
            match = re.search(r'authorization=([^;]+)', self.cookie_str)
            if match:
                auth_val = unquote(match.group(1)).strip()
                self.base_headers["Authorization"] = auth_val
                print(f"[DEBUG] Authorization from cookie: {auth_val[:50]}...")
        elif self.phone and self.auth_token:
            auth_raw = f"pc:{self.phone}:{self.auth_token}"
            auth_b64 = base64.b64encode(auth_raw.encode()).decode()
            self.base_headers["Authorization"] = f"Basic {auth_b64}"

    def _parse_cookie(self):
        """从Cookie字符串解析关键信息"""
        if not self.cookie_str:
            return
        # 提取auth_token
        match = re.search(r'auth_token=([^;]+)', self.cookie_str)
        if match:
            self.auth_token = unquote(match.group(1))
        # 提取phone (从authorization cookie)
        match = re.search(r'authorization=Basic(?:%20|\s)([^;]+)', self.cookie_str)
        if not match:
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
        # 提取ud_id
        match = re.search(r'ud_id=([^;]+)', self.cookie_str)
        if match:
            self.ud_id = match.group(1)

    def _make_sign(self):
        """生成mcloud-sign签名"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        random_str = uuid.uuid4().hex[:16]
        # 使用简单MD5 (实际算法可能更复杂，这里模拟)
        sign_str = f"{now},{random_str}"
        md5_hash = hashlib.md5(sign_str.encode()).hexdigest().upper()
        return f"{now},{random_str},{md5_hash}"

    def _request(self, method, url, data=None, headers=None, use_orchestration=False):
        """发送HTTP请求"""
        h = dict(self.base_headers)
        if headers:
            h.update(headers)
        h["mcloud-sign"] = self._make_sign()

        try:
            if method.upper() == "GET":
                resp = self.session.get(url, headers=h, timeout=30)
            else:
                resp = self.session.post(url, json=data, headers=h, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"[API Error] {method} {url}: {e}")
            return {"success": False, "code": -1, "message": str(e)}

    # ==================== 文件列表 ====================

    def list_files(self, parent_file_id=None, page_size=100, page_cursor=None, order_by="updated_at", order_direction="DESC"):
        """
        获取文件列表

        参数:
            parent_file_id: 父文件夹ID，None表示根目录
            page_size: 每页数量 (最大100)
            page_cursor: 分页游标
            order_by: 排序字段 (updated_at/name/size)
            order_direction: 排序方向 (DESC/ASC)

        返回:
            dict: API响应数据
        """
        url = f"{BASE_URL}/hcy/file/list"
        data = {
            "pageInfo": {
                "pageSize": page_size,
                "pageCursor": page_cursor
            },
            "orderBy": order_by,
            "orderDirection": order_direction,
            "parentFileId": parent_file_id or ROOT_FOLDER_ID,
            "imageThumbnailStyleList": ["Small", "Large"]
        }
        return self._request("POST", url, data)

    def get_file(self, file_id):
        """获取单个文件详情"""
        url = f"{BASE_URL}/hcy/file/get"
        data = {"fileId": file_id}
        return self._request("POST", url, data)

    def list_all_files(self, parent_file_id=None):
        """获取文件夹下所有文件（自动分页）"""
        all_files = []
        cursor = None
        while True:
            resp = self.list_files(parent_file_id=parent_file_id, page_cursor=cursor)
            if not resp.get("success"):
                break
            file_list = resp.get("data", {}).get("fileListAO", {}).get("fileList", [])
            all_files.extend(file_list)
            cursor = resp.get("data", {}).get("pageInfo", {}).get("pageCursor")
            if not cursor or len(file_list) == 0:
                break
        return all_files

    # ==================== 文件夹操作 ====================

    def create_folder(self, folder_name, parent_file_id=None):
        """
        创建文件夹

        参数:
            folder_name: 文件夹名称
            parent_file_id: 父文件夹ID

        返回:
            dict: 包含新文件夹fileId的响应
        """
        url = f"{BASE_URL}/hcy/folder/create"
        data = {
            "folderName": folder_name,
            "parentFileId": parent_file_id or ROOT_FOLDER_ID
        }
        return self._request("POST", url, data)

    # ==================== 文件上传 ====================

    def upload_file(self, file_path, parent_file_id=None, file_name=None):
        """
        上传文件 (简化版，直接上传)

        参数:
            file_path: 本地文件路径
            parent_file_id: 目标文件夹ID
            file_name: 自定义文件名 (可选)

        返回:
            dict: 上传结果
        """
        if not os.path.exists(file_path):
            return {"success": False, "message": "文件不存在"}

        file_name = file_name or os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        parent_id = parent_file_id or ROOT_FOLDER_ID

        # 1. 获取上传URL (预上传/秒传检查)
        # 实际实现需要调用 hcy/file/upload 或相关接口
        # 这里使用简化的直接上传方式

        url = f"{BASE_URL}/hcy/file/upload"

        # 读取文件内容
        with open(file_path, 'rb') as f:
            file_data = f.read()

        # 构建multipart表单
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"

        # 构建请求体
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
        del headers["mcloud-sign"]  # 上传时可能需要不同的签名

        try:
            resp = self.session.post(url, data=body_bytes, headers=headers, timeout=120)
            return resp.json()
        except Exception as e:
            return {"success": False, "message": f"上传失败: {e}"}

    def upload_data(self, data, file_name, parent_file_id=None):
        """
        上传二进制数据

        参数:
            data: 二进制数据
            file_name: 文件名
            parent_file_id: 目标文件夹ID
        """
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            temp_path = f.name
        try:
            result = self.upload_file(temp_path, parent_file_id, file_name)
        finally:
            os.unlink(temp_path)
        return result

    # ==================== 文件下载 ====================

    def download_file(self, file_id):
        """
        下载文件

        参数:
            file_id: 文件ID

        返回:
            bytes: 文件内容，失败返回None
        """
        # 先获取文件详情获取下载URL
        file_info = self.get_file(file_id)
        if not file_info.get("success"):
            return None

        # 尝试从响应中获取下载链接
        download_url = file_info.get("data", {}).get("downloadUrl")
        if not download_url:
            # 某些文件类型可能有不同的字段
            download_url = file_info.get("data", {}).get("contentUrl")

        if download_url:
            try:
                resp = self.session.get(download_url, timeout=60)
                return resp.content
            except:
                pass

        # 如果无法获取下载URL，尝试直接通过API下载
        # 实际实现可能需要调用特定的下载接口
        return None

    # ==================== 删除操作 ====================

    def delete_file(self, file_id):
        """
        删除单个文件 (移入回收站)

        参数:
            file_id: 文件ID

        返回:
            dict: 删除结果
        """
        return self.batch_delete([file_id])

    def batch_delete(self, file_ids):
        """
        批量删除文件 (移入回收站)

        参数:
            file_ids: 文件ID列表

        返回:
            dict: 删除结果
        """
        url = f"{BASE_URL}/hcy/recyclebin/batchTrash"
        data = {"fileIds": file_ids}
        return self._request("POST", url, data)

    # ==================== 重命名 ====================

    def rename_file(self, file_id, new_name):
        """
        重命名文件/文件夹

        参数:
            file_id: 文件ID
            new_name: 新名称

        返回:
            dict: 重命名结果
        """
        url = f"{BASE_URL}/hcy/file/rename"
        data = {
            "fileId": file_id,
            "fileName": new_name
        }
        return self._request("POST", url, data)

    # ==================== 移动/复制 ====================

    def move_file(self, file_ids, dest_parent_id):
        """
        移动文件

        参数:
            file_ids: 文件ID列表
            dest_parent_id: 目标文件夹ID
        """
        url = f"{BASE_URL}/hcy/file/batchMove"
        data = {
            "fileIds": file_ids if isinstance(file_ids, list) else [file_ids],
            "destParentFileId": dest_parent_id
        }
        return self._request("POST", url, data)

    def copy_file(self, file_ids, dest_parent_id):
        """
        复制文件

        参数:
            file_ids: 文件ID列表
            dest_parent_id: 目标文件夹ID
        """
        url = f"{BASE_URL}/hcy/file/batchCopy"
        data = {
            "fileIds": file_ids if isinstance(file_ids, list) else [file_ids],
            "destParentFileId": dest_parent_id
        }
        return self._request("POST", url, data)

    # ==================== 用户信息 ====================

    def get_user_info(self):
        """获取用户信息"""
        url = f"{BASE_URL}/hcy/user/get"
        data = {"account": self.phone} if self.phone else {}
        return self._request("POST", url, data)

    def get_capacity(self):
        """获取用户容量信息"""
        url = f"{ORCH_URL}/orchestration/personalCloud-rebuild/user/v1.0/qryUserCapacity"
        return self._request("POST", url, {})

    # ==================== 路径解析工具 ====================

    def resolve_path(self, path):
        """
        将路径解析为fileId

        参数:
            path: 类似 "/folder1/folder2/file.txt" 的路径

        返回:
            tuple: (file_id, file_info) 或 (None, None)
        """
        if not path or path == "/" or path == "":
            return ROOT_FOLDER_ID, {"fileType": 2, "fileName": "root"}

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

        return current_id, current_info

    def get_children(self, folder_id):
        """获取文件夹下的所有子项"""
        return self.list_all_files(folder_id)

    def get_parent_path(self, file_id):
        """
        根据fileId获取完整路径

        参数:
            file_id: 文件ID

        返回:
            str: 完整路径，如 "/folder1/file.txt"
        """
        if file_id == ROOT_FOLDER_ID:
            return "/"

        # 获取文件详情
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


# ==================== 便捷函数 ====================

def create_api_from_cookie(cookie_str):
    """从Cookie字符串创建API实例"""
    return CMCCCloudAPI(cookie_str=cookie_str)


def create_api_from_creds(phone, auth_token):
    """从手机号和token创建API实例"""
    return CMCCCloudAPI(phone=phone, auth_token=auth_token)
