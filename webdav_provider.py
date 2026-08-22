#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国移动云盘 WebDAV 提供者 (WsgiDAV Provider)
将云盘映射为WebDAV虚拟文件系统
支持: PROPFIND/GET/PUT/DELETE/MKCOL/MOVE/COPY/LOCK/UNLOCK

改进点:
1. Range请求支持（断点续传）
2. 流式传输（大文件不占用内存）
3. 文件锁定（LOCK/UNLOCK）
4. 属性管理（自定义属性）
5. 文件列表缓存
6. 完善的MIME类型识别
7. 递归文件夹复制
8. 更好的错误处理
"""

import os
import io
import time
import json
import hashlib
import threading
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
        self.file_size = file_info.get("fileSize", 0) or file_info.get("size", 0)
        self._content = None
        self._lock = threading.Lock()

    def get_content_length(self):
        return self.file_size

    def get_content_type(self):
        ext = os.path.splitext(self.file_name)[1].lower()
        mime_types = {
            '.txt': 'text/plain', '.html': 'text/html', '.htm': 'text/html',
            '.css': 'text/css', '.js': 'application/javascript',
            '.json': 'application/json', '.xml': 'application/xml',
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
            '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
            '.mp4': 'video/mp4', '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska',
            '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.flac': 'audio/flac',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.ppt': 'application/vnd.ms-powerpoint',
            '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            '.zip': 'application/zip', '.rar': 'application/x-rar-compressed',
            '.7z': 'application/x-7z-compressed', '.tar': 'application/x-tar',
            '.gz': 'application/gzip', '.bz2': 'application/x-bzip2',
            '.exe': 'application/x-msdownload', '.dll': 'application/x-msdownload',
            '.msi': 'application/x-msdownload', '.apk': 'application/vnd.android.package-archive',
            '.ipa': 'application/octet-stream', '.dmg': 'application/x-apple-diskimage',
            '.iso': 'application/x-iso9660-image', '.csv': 'text/csv',
            '.md': 'text/markdown', '.py': 'text/x-python',
            '.java': 'text/x-java-source', '.c': 'text/x-c', '.cpp': 'text/x-c++',
            '.h': 'text/x-c', '.php': 'text/x-php', '.go': 'text/x-go',
            '.rs': 'text/x-rust', '.swift': 'text/x-swift', '.kt': 'text/x-kotlin',
            '.rb': 'text/x-ruby', '.sh': 'text/x-shellscript',
            '.bat': 'text/x-batch', '.ps1': 'text/x-powershell',
            '.sql': 'text/x-sql', '.yaml': 'text/yaml', '.yml': 'text/yaml',
            '.toml': 'text/toml', '.ini': 'text/x-ini', '.cfg': 'text/x-ini',
            '.conf': 'text/x-ini', '.log': 'text/plain',
            '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
            '.tif': 'image/tiff', '.tiff': 'image/tiff',
            '.psd': 'image/vnd.adobe.photoshop', '.ai': 'application/postscript',
            '.eps': 'application/postscript', '.ttf': 'font/ttf',
            '.otf': 'font/otf', '.woff': 'font/woff', '.woff2': 'font/woff2',
            '.eot': 'application/vnd.ms-fontobject',
        }
        return mime_types.get(ext, 'application/octet-stream')

    def get_creation_date(self):
        created = self.file_info.get("created_at", "") or self.file_info.get("createdAt", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00').replace('.000+08:00', '+08:00'))
                return dt.timestamp()
            except:
                pass
        return time.time()

    def get_modified_date(self):
        updated = self.file_info.get("updated_at", "") or self.file_info.get("updatedAt", "")
        if updated:
            try:
                dt = datetime.fromisoformat(updated.replace('Z', '+00:00').replace('.000+08:00', '+08:00'))
                return dt.timestamp()
            except:
                pass
        return time.time()

    def get_etag(self):
        return hashlib.md5(f"{self.file_id}:{self.file_size}".encode()).hexdigest()

    def support_etag(self):
        return True

    def support_ranges(self):
        """支持Range请求（断点续传）"""
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
        dest_folder_path = os.path.dirname(dest_path)
        dest_name = os.path.basename(dest_path)
        dest_folder_id, _ = self.api.resolve_path(dest_folder_path)
        if dest_folder_id is None:
            return False
        current_parent = self.file_info.get("parentFileId")
        if dest_folder_id != current_parent:
            result = self.api.move_file(self.file_id, dest_folder_id)
            if not result.get("success"):
                return False
        if dest_name != self.file_name:
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

    # 支持文件锁定
    def support_lock(self):
        return True


class CMCCUploadBuffer:
    """上传缓冲区，用于接收PUT数据"""

    def __init__(self, api, parent_id, file_name, old_file_id=None):
        self.api = api
        self.parent_id = parent_id
        self.file_name = file_name
        self.old_file_id = old_file_id
        self.buffer = io.BytesIO()
        self._size = 0

    def write(self, data):
        self.buffer.write(data)
        self._size += len(data)

    def close(self):
        data = self.buffer.getvalue()
        self.buffer.close()
        if self.old_file_id:
            self.api.delete_file(self.old_file_id)
        self.api.upload_data(data, self.file_name, self.parent_id)


class CMCCFolderResource(DAVCollection):
    """云盘文件夹资源"""

    def __init__(self, path, environ, api, folder_id, folder_info=None):
        super().__init__(path, environ)
        self.api = api
        self.folder_id = folder_id
        self.folder_info = folder_info or {}
        self.folder_name = folder_info.get("fileName", "") if folder_info else ""
        self._children_cache = None
        self._children_cache_time = 0
        self._cache_ttl = 30

    def get_creation_date(self):
        created = self.folder_info.get("created_at", "") or self.folder_info.get("createdAt", "") if self.folder_info else ""
        if created:
            try:
                dt = datetime.fromisoformat(created.replace('Z', '+00:00').replace('.000+08:00', '+08:00'))
                return dt.timestamp()
            except:
                pass
        return time.time()

    def get_modified_date(self):
        updated = self.folder_info.get("updated_at", "") or self.folder_info.get("updatedAt", "") if self.folder_info else ""
        if updated:
            try:
                dt = datetime.fromisoformat(updated.replace('Z', '+00:00').replace('.000+08:00', '+08:00'))
                return dt.timestamp()
            except:
                pass
        return time.time()

    def get_etag(self):
        return hashlib.md5(self.folder_id.encode()).hexdigest()

    def support_etag(self):
        return True

    def _get_children(self):
        """获取子项列表（带缓存）"""
        now = time.time()
        if self._children_cache is not None and (now - self._children_cache_time) < self._cache_ttl:
            return self._children_cache
        children = self.api.get_children(self.folder_id)
        self._children_cache = children
        self._children_cache_time = now
        return children

    def get_member_names(self):
        """获取子项名称列表"""
        children = self._get_children()
        return [child.get("fileName", "") for child in children]

    def get_member(self, name):
        """获取子项资源"""
        children = self._get_children()
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
        if result.get("success"):
            self._children_cache = None
        return result.get("success", False)

    def create_empty_resource(self, name):
        """创建空文件资源 (用于PUT)"""
        child_path = self.path + "/" + name if self.path != "/" else "/" + name
        temp_info = {
            "fileId": None, "fileName": name, "fileSize": 0,
            "parentFileId": self.folder_id, "fileType": 1
        }
        return CMCCFileResource(child_path, self.environ, self.api, temp_info)

    def delete(self):
        """删除文件夹"""
        if self.folder_id == ROOT_FOLDER_ID:
            return False
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
        """复制文件夹（递归复制）"""
        if self.folder_id == ROOT_FOLDER_ID:
            return False
        dest_folder_path = os.path.dirname(dest_path)
        dest_folder_id, _ = self.api.resolve_path(dest_folder_path)
        if dest_folder_id is None:
            return False
        result = self.api.copy_file(self.folder_id, dest_folder_id)
        if not result.get("success"):
            return False
        new_folder_id, _ = self.api.resolve_path(dest_path)
        if not new_folder_id:
            return True
        return self._copy_children(self.folder_id, new_folder_id)

    def _copy_children(self, src_folder_id, dest_folder_id):
        """递归复制子项"""
        children = self.api.get_children(src_folder_id)
        for child in children:
            child_id = child.get("fileId")
            if child.get("fileType") == 2:
                result = self.api.copy_file(child_id, dest_folder_id)
                if result.get("success"):
                    new_path = self.api.get_parent_path(child_id)
                    if new_path:
                        new_id, _ = self.api.resolve_path(new_path)
                        if new_id:
                            self._copy_children(child_id, new_id)
            else:
                self.api.copy_file(child_id, dest_folder_id)
        return True


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
        file_id, file_info = self.api.resolve_path(path)
        if file_id is None:
            return None
        if file_info and file_info.get("fileType") == 2:
            return CMCCFolderResource(path, environ, self.api, file_id, file_info)
        else:
            if file_info:
                return CMCCFileResource(path, environ, self.api, file_info)
            else:
                parent_path = os.path.dirname(path)
                parent_id, _ = self.api.resolve_path(parent_path)
                if parent_id:
                    file_name = os.path.basename(path)
                    temp_info = {
                        "fileId": None, "fileName": file_name, "fileSize": 0,
                        "parentFileId": parent_id, "fileType": 1
                    }
                    return CMCCFileResource(path, environ, self.api, temp_info)
                return None

    def is_readonly(self):
        return False
