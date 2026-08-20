#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国移动云盘 WebDAV 提供者 (WsgiDAV Provider)
将云盘映射为WebDAV虚拟文件系统
支持: PROPFIND/GET/PUT/DELETE/MKCOL/MOVE/COPY
"""

import os
import io
import time
import json
import hashlib
from datetime import datetime

from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection

from cmcc_api import CMCCCloudAPI, ROOT_FOLDER_ID


class CMCCFileResource(DAVNonCollection):
    """云盘文件资源"""

    def __init__(self, path, environ, api, file_info):
        super().__init__(path, environ)
        self.api = api
        self.file_info = file_info
        self.file_id = file_info.get("fileId")
        self.file_name = file_info.get("fileName", "")
        self.file_size = file_info.get("fileSize", 0)
        self._content = None

    def get_content_length(self):
        return self.file_size

    def get_content_type(self):
        # 简单根据扩展名判断
        ext = os.path.splitext(self.file_name)[1].lower()
        mime_types = {
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.htm': 'text/html',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.json': 'application/json',
            '.xml': 'application/xml',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.mp4': 'video/mp4',
            '.mp3': 'audio/mpeg',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed',
            '.7z': 'application/x-7z-compressed',
        }
        return mime_types.get(ext, 'application/octet-stream')

    def get_creation_date(self):
        # 转换为HTTP日期格式
        created = self.file_info.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                return dt.timestamp()
            except:
                pass
        return time.time()

    def get_modified_date(self):
        updated = self.file_info.get("updated_at", "")
        if updated:
            try:
                dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                return dt.timestamp()
            except:
                pass
        return time.time()

    def get_etag(self):
        return hashlib.md5(f"{self.file_id}:{self.file_size}".encode()).hexdigest()

    def support_etag(self):
        return True

    def get_content(self):
        """下载文件内容"""
        if self._content is None:
            self._content = self.api.download_file(self.file_id)
        if self._content is None:
            self._content = b""
        return io.BytesIO(self._content)

    def begin_write(self, content_type=None):
        """开始写入（覆盖上传）"""
        return CMCCUploadBuffer(self.api, self.file_info.get("parentFileId"), self.file_name, self.file_id)

    def end_write(self, with_errors):
        pass

    def delete(self):
        """删除文件"""
        result = self.api.delete_file(self.file_id)
        return result.get("success", False)

    def move(self, dest_path):
        """移动文件"""
        # 解析目标路径
        dest_folder_path = os.path.dirname(dest_path)
        dest_name = os.path.basename(dest_path)

        dest_folder_id, _ = self.api.resolve_path(dest_folder_path)
        if dest_folder_id is None:
            return False

        # 如果目标文件夹不同，先移动
        current_parent = self.file_info.get("parentFileId")
        if dest_folder_id != current_parent:
            result = self.api.move_file(self.file_id, dest_folder_id)
            if not result.get("success"):
                return False

        # 如果名称不同，重命名
        if dest_name != self.file_name:
            # 需要重新获取file_id（移动后可能变化）
            new_file_id, _ = self.api.resolve_path(dest_path)
            if new_file_id:
                result = self.api.rename_file(new_file_id, dest_name)
                return result.get("success", False)

        return True

    def copy(self, dest_path):
        """复制文件"""
        dest_folder_path = os.path.dirname(dest_path)
        dest_folder_id, _ = self.api.resolve_path(dest_folder_path)
        if dest_folder_id is None:
            return False
        result = self.api.copy_file(self.file_id, dest_folder_id)
        return result.get("success", False)


class CMCCUploadBuffer:
    """上传缓冲区，用于接收PUT数据"""

    def __init__(self, api, parent_id, file_name, old_file_id=None):
        self.api = api
        self.parent_id = parent_id
        self.file_name = file_name
        self.old_file_id = old_file_id
        self.buffer = io.BytesIO()

    def write(self, data):
        self.buffer.write(data)

    def close(self):
        data = self.buffer.getvalue()
        self.buffer.close()

        # 如果有旧文件，先删除
        if self.old_file_id:
            self.api.delete_file(self.old_file_id)

        # 上传新文件
        self.api.upload_data(data, self.file_name, self.parent_id)


class CMCCFolderResource(DAVCollection):
    """云盘文件夹资源"""

    def __init__(self, path, environ, api, folder_id, folder_info=None):
        super().__init__(path, environ)
        self.api = api
        self.folder_id = folder_id
        self.folder_info = folder_info or {}
        self.folder_name = folder_info.get("fileName", "") if folder_info else ""

    def get_creation_date(self):
        created = self.folder_info.get("created_at", "") if self.folder_info else ""
        if created:
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                return dt.timestamp()
            except:
                pass
        return time.time()

    def get_modified_date(self):
        updated = self.folder_info.get("updated_at", "") if self.folder_info else ""
        if updated:
            try:
                dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                return dt.timestamp()
            except:
                pass
        return time.time()

    def get_etag(self):
        return hashlib.md5(self.folder_id.encode()).hexdigest()

    def support_etag(self):
        return True

    def get_member_names(self):
        """获取子项名称列表"""
        children = self.api.get_children(self.folder_id)
        return [child.get("fileName", "") for child in children]

    def get_member(self, name):
        """获取子项资源"""
        children = self.api.get_children(self.folder_id)
        for child in children:
            if child.get("fileName") == name:
                child_path = self.path + "/" + name if self.path != "/" else "/" + name
                if child.get("fileType") == 2:
                    return CMCCFolderResource(child_path, self.environ, self.api, 
                                             child.get("fileId"), child)
                else:
                    return CMCCFileResource(child_path, self.environ, self.api, child)
        return None

    def create_collection(self, name):
        """创建子文件夹 (MKCOL)"""
        result = self.api.create_folder(name, self.folder_id)
        return result.get("success", False)

    def create_empty_resource(self, name):
        """创建空文件资源 (用于PUT)"""
        # 返回一个临时资源，实际在begin_write时处理
        child_path = self.path + "/" + name if self.path != "/" else "/" + name
        temp_info = {
            "fileId": None,
            "fileName": name,
            "fileSize": 0,
            "parentFileId": self.folder_id,
            "fileType": 1
        }
        return CMCCFileResource(child_path, self.environ, self.api, temp_info)

    def delete(self):
        """删除文件夹"""
        if self.folder_id == ROOT_FOLDER_ID:
            return False  # 不能删除根目录
        result = self.api.delete_file(self.folder_id)
        return result.get("success", False)

    def move(self, dest_path):
        """移动文件夹"""
        if self.folder_id == ROOT_FOLDER_ID:
            return False

        dest_folder_path = os.path.dirname(dest_path)
        dest_name = os.path.basename(dest_path)

        dest_folder_id, _ = self.api.resolve_path(dest_folder_path)
        if dest_folder_id is None:
            return False

        current_parent = self.folder_info.get("parentFileId")
        if dest_folder_id != current_parent:
            result = self.api.move_file(self.folder_id, dest_folder_id)
            if not result.get("success"):
                return False

        if dest_name != self.folder_name:
            new_folder_id, _ = self.api.resolve_path(dest_path)
            if new_folder_id:
                result = self.api.rename_file(new_folder_id, dest_name)
                return result.get("success", False)

        return True

    def copy(self, dest_path):
        """复制文件夹"""
        if self.folder_id == ROOT_FOLDER_ID:
            return False
        dest_folder_path = os.path.dirname(dest_path)
        dest_folder_id, _ = self.api.resolve_path(dest_folder_path)
        if dest_folder_id is None:
            return False
        result = self.api.copy_file(self.folder_id, dest_folder_id)
        return result.get("success", False)


class CMCCCloudProvider(DAVProvider):
    """中国移动云盘 WebDAV 提供者"""

    def __init__(self, api):
        super().__init__()
        self.api = api

    def get_resource_inst(self, path, environ):
        """获取路径对应的资源实例"""
        self._count_get_resource_inst += 1

        if path == "/" or path == "":
            return CMCCFolderResource(path, environ, self.api, ROOT_FOLDER_ID)

        # 解析路径
        file_id, file_info = self.api.resolve_path(path)

        if file_id is None:
            return None

        if file_info and file_info.get("fileType") == 2:
            return CMCCFolderResource(path, environ, self.api, file_id, file_info)
        else:
            # 可能是文件，或者路径不存在但父文件夹存在（用于PUT创建）
            if file_info:
                return CMCCFileResource(path, environ, self.api, file_info)
            else:
                # 路径不存在，检查父文件夹是否存在
                parent_path = os.path.dirname(path)
                parent_id, _ = self.api.resolve_path(parent_path)
                if parent_id:
                    # 返回一个临时文件资源，允许PUT创建
                    file_name = os.path.basename(path)
                    temp_info = {
                        "fileId": None,
                        "fileName": file_name,
                        "fileSize": 0,
                        "parentFileId": parent_id,
                        "fileType": 1
                    }
                    return CMCCFileResource(path, environ, self.api, temp_info)
                return None

    def is_readonly(self):
        """是否只读 - 返回False支持写入"""
        return False
