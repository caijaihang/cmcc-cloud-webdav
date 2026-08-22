#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中国移动云盘 WebDAV Provider. 支持: PROPFIND/GET/PUT/DELETE/MKCOL/MOVE/COPY/LOCK/UNLOCK/RANGE/流式/断点续传/80+MIME类型"""
import os, io, time, hashlib, threading, mimetypes
from datetime import datetime
from wsgidav.dav_provider import DAVProvider, DAVResource, DAVCollection, DAVNonCollection
from wsgidav.util import join_uri

ROOT_FOLDER_ID = "DFn_Mm9QAFQA0611WrpTl1Oy00019700101000000044"

MIME_TYPES = {
    ".txt": "text/plain", ".md": "text/markdown", ".csv": "text/csv",
    ".html": "text/html", ".htm": "text/html", ".css": "text/css",
    ".js": "application/javascript", ".json": "application/json",
    ".xml": "application/xml", ".yaml": "application/yaml", ".yml": "application/yaml",
    ".pdf": "application/pdf", ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".pages": "application/vnd.apple.pages", ".numbers": "application/vnd.apple.numbers",
    ".key": "application/vnd.apple.keynote",
    ".epub": "application/epub+zip", ".mobi": "application/x-mobipocket-ebook",
    ".azw3": "application/vnd.amazon.mobi8-ebook",
    ".zip": "application/zip", ".rar": "application/vnd.rar",
    ".7z": "application/x-7z-compressed", ".tar": "application/x-tar",
    ".gz": "application/gzip", ".bz2": "application/x-bzip2", ".xz": "application/x-xz",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".bmp": "image/bmp", ".webp": "image/webp",
    ".svg": "image/svg+xml", ".ico": "image/x-icon", ".tiff": "image/tiff",
    ".tif": "image/tiff", ".raw": "image/x-raw", ".psd": "image/vnd.adobe.photoshop",
    ".heic": "image/heic", ".heif": "image/heif",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".flac": "audio/flac",
    ".aac": "audio/aac", ".ogg": "audio/ogg", ".wma": "audio/x-ms-wma",
    ".m4a": "audio/mp4", ".opus": "audio/opus",
    ".mp4": "video/mp4", ".avi": "video/x-msvideo", ".mkv": "video/x-matroska",
    ".mov": "video/quicktime", ".wmv": "video/x-ms-wmv", ".flv": "video/x-flv",
    ".webm": "video/webm", ".m4v": "video/x-m4v", ".mpg": "video/mpeg",
    ".mpeg": "video/mpeg", ".3gp": "video/3gpp",
    ".exe": "application/x-msdownload", ".msi": "application/x-msi",
    ".dmg": "application/x-apple-diskimage", ".pkg": "application/x-newton-compatible-pkg",
    ".deb": "application/vnd.debian.binary-package", ".rpm": "application/x-rpm",
    ".appimage": "application/x-appimage",
    ".apk": "application/vnd.android.package-archive",
    ".ipa": "application/octet-stream",
    ".py": "text/x-python", ".java": "text/x-java-source", ".c": "text/x-c",
    ".cpp": "text/x-c++", ".h": "text/x-c-header", ".go": "text/x-go",
    ".rs": "text/x-rust", ".swift": "text/x-swift", ".kt": "text/x-kotlin",
    ".php": "text/x-php", ".rb": "text/x-ruby", ".pl": "text/x-perl",
    ".sh": "text/x-shellscript", ".bat": "text/x-batch", ".ps1": "text/x-powershell",
    ".sql": "text/x-sql", ".lua": "text/x-lua", ".r": "text/x-r",
    ".m": "text/x-matlab", ".scala": "text/x-scala", ".groovy": "text/x-groovy",
    ".dart": "text/x-dart", ".ts": "text/typescript", ".tsx": "text/tsx",
    ".jsx": "text/jsx", ".vue": "text/x-vue", ".svelte": "text/x-svelte",
    ".wasm": "application/wasm", ".crx": "application/x-chrome-extension",
    ".sketch": "application/sketch", ".fig": "application/figma",
    ".dwg": "application/acad", ".dxf": "application/dxf",
    ".iso": "application/x-iso9660-image", ".img": "application/x-raw-disk-image",
    ".vmdk": "application/x-vmdk", ".qcow2": "application/x-qemu-disk",
    ".db": "application/x-sqlite3", ".sqlite": "application/x-sqlite3",
    ".log": "text/plain", ".ini": "text/plain", ".conf": "text/plain",
    ".cfg": "text/plain", ".env": "text/plain", ".toml": "text/plain",
    ".gitignore": "text/plain", ".dockerignore": "text/plain",
    ".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2",
    ".eot": "application/vnd.ms-fontobject",
}

def get_mime_type(filename):
    ext = os.path.splitext(filename)[1].lower()
    return MIME_TYPES.get(ext, mimetypes.guess_type(filename)[0] or "application/octet-stream")

def _file_to_resinfo(f):
    name = f.get("fileName", "")
    fid = f.get("fileId", "")
    size = f.get("fileSize", 0) or 0
    ftype = f.get("fileType", 1)
    updated = f.get("updated_at", "") or f.get("updatedAt", "") or ""
    created = f.get("created_at", "") or f.get("createdAt", "") or ""
    is_dir = ftype == 2
    try:
        if updated: mt = datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
        else: mt = time.time()
    except: mt = time.time()
    try:
        if created: ct = datetime.fromisoformat(created.replace("Z", "+00:00")).timestamp()
        else: ct = mt
    except: ct = mt
    etag = hashlib.md5(f"{fid}:{size}:{mt}".encode()).hexdigest()
    return {"name": name, "fileId": fid, "size": size, "is_dir": is_dir, "mtime": mt, "ctime": ct, "etag": etag}

class CMCCUploadBuffer:
    def __init__(self, api, file_name, parent_id):
        self.api, self.file_name, self.parent_id = api, file_name, parent_id
        self.buffer = io.BytesIO()
    def write(self, data):
        if isinstance(data, str): data = data.encode("utf-8")
        self.buffer.write(data)
    def flush(self): pass
    def close(self):
        data = self.buffer.getvalue()
        self.buffer.close()
        if data:
            self.api.upload_data(data, self.file_name, self.parent_id)
    def getvalue(self): return self.buffer.getvalue()

class CMCCFolderResource(DAVCollection):
    def __init__(self, path, environ, api, folder_id, folder_info=None):
        super().__init__(path, environ)
        self.api = api
        self.folder_id = folder_id or ROOT_FOLDER_ID
        self.folder_info = folder_info or {}
        self._children_cache = None
        self._cache_time = 0
        self._cache_ttl = 30
    def get_member_names(self):
        return [c["name"] for c in self.get_children_info()]
    def get_member(self, name):
        for c in self.get_children_info():
            if c["name"] == name:
                child_path = join_uri(self.path, name)
                if c["is_dir"]:
                    return CMCCFolderResource(child_path, self.environ, self.api, c["fileId"], c)
                return CMCCFileResource(child_path, self.environ, self.api, c)
        return None
    def get_children_info(self):
        now = time.time()
        if self._children_cache is not None and now - self._cache_time < self._cache_ttl:
            return self._children_cache
        files = self.api.list_all_files(self.folder_id, use_cache=False)
        res = [_file_to_resinfo(f) for f in files]
        self._children_cache = res
        self._cache_time = now
        return res
    def create_empty_resource(self, name):
        child_path = join_uri(self.path, name)
        return CMCCFileResource(child_path, self.environ, self.api, {"name": name, "fileId": "", "size": 0, "is_dir": False, "mtime": time.time(), "ctime": time.time(), "etag": ""})
    def create_collection(self, name):
        r = self.api.create_folder(name, self.folder_id)
        if not r.get("success"): raise Exception(f"创建文件夹失败: {r.get('message', '')}")
        self._children_cache = None
        child_path = join_uri(self.path, name)
        new_id = r.get("data", {}).get("fileId") or r.get("data", {}).get("catalogID")
        return CMCCFolderResource(child_path, self.environ, self.api, new_id, {"name": name, "fileId": new_id, "is_dir": True})
    def delete(self):
        if self.folder_id == ROOT_FOLDER_ID: raise Exception("不能删除根目录")
        r = self.api.delete_file(self.folder_id)
        if not r.get("success"): raise Exception(f"删除失败: {r.get('message', '')}")
    def copy(self, dest_path, depth="infinity"):
        dest_provider = self.environ["wsgidav.provider"]
        dest_res = dest_provider.get_resource_inst(dest_path, self.environ)
        if dest_res and not isinstance(dest_res, DAVCollection):
            raise Exception("目标必须是文件夹")
        dest_parent_path = dest_path.rsplit("/", 1)[0] or "/"
        dest_name = dest_path.rsplit("/", 1)[1]
        dest_parent = dest_provider.get_resource_inst(dest_parent_path, self.environ)
        if not dest_parent: raise Exception("目标父目录不存在")
        dest_parent_id = dest_parent.folder_id if hasattr(dest_parent, "folder_id") else ROOT_FOLDER_ID
        r = self.api.copy_file(self.folder_id, dest_parent_id)
        if not r.get("success"): raise Exception(f"复制失败: {r.get('message', '')}")
        new_id = r.get("data", {}).get("fileId")
        return CMCCFolderResource(dest_path, self.environ, self.api, new_id, {"name": dest_name, "fileId": new_id, "is_dir": True})
    def move(self, dest_path):
        dest_provider = self.environ["wsgidav.provider"]
        dest_parent_path = dest_path.rsplit("/", 1)[0] or "/"
        dest_name = dest_path.rsplit("/", 1)[1]
        dest_parent = dest_provider.get_resource_inst(dest_parent_path, self.environ)
        if not dest_parent: raise Exception("目标父目录不存在")
        dest_parent_id = dest_parent.folder_id if hasattr(dest_parent, "folder_id") else ROOT_FOLDER_ID
        r = self.api.move_file(self.folder_id, dest_parent_id)
        if not r.get("success"): raise Exception(f"移动失败: {r.get('message', '')}")
        new_id = r.get("data", {}).get("fileId")
        if dest_name != self.folder_info.get("name", ""):
            self.api.rename_file(new_id or self.folder_id, dest_name)
        return CMCCFolderResource(dest_path, self.environ, self.api, new_id or self.folder_id, {"name": dest_name, "fileId": new_id or self.folder_id, "is_dir": True})
    def support_recursive_move(self): return True
    def support_recursive_delete(self): return True
    def get_content_length(self): return 0
    def get_content_type(self): return "httpd/unix-directory"
    def get_creation_date(self): return self.folder_info.get("ctime", time.time())
    def get_last_modified(self): return self.folder_info.get("mtime", time.time())
    def get_etag(self): return hashlib.md5(f"{self.folder_id}:dir".encode()).hexdigest()
    def get_display_name(self): return self.folder_info.get("name", self.path.rstrip("/").rsplit("/", 1)[-1] or "root")

class CMCCFileResource(DAVNonCollection):
    def __init__(self, path, environ, api, file_info):
        super().__init__(path, environ)
        self.api = api
        self.file_info = file_info or {}
        self._lock = threading.Lock()
    def get_content_length(self): return self.file_info.get("size", 0)
    def get_content_type(self): return get_mime_type(self.file_info.get("name", ""))
    def get_creation_date(self): return self.file_info.get("ctime", time.time())
    def get_last_modified(self): return self.file_info.get("mtime", time.time())
    def get_etag(self): return self.file_info.get("etag", hashlib.md5(self.path.encode()).hexdigest())
    def get_display_name(self): return self.file_info.get("name", self.path.rsplit("/", 1)[-1])
    def support_ranges(self): return True
    def get_content(self):
        fid = self.file_info.get("fileId")
        if not fid: return io.BytesIO(b"")
        return CMCCStream(self.api, fid)
    def begin_write(self, content_type=None):
        parent_path = self.path.rsplit("/", 1)[0] or "/"
        parent = self.api.resolve_path(parent_path)[0]
        if not parent: parent = ROOT_FOLDER_ID
        return CMCCUploadBuffer(self.api, self.file_info.get("name", ""), parent)
    def end_write(self, with_errors):
        pass
    def delete(self):
        fid = self.file_info.get("fileId")
        if not fid: raise Exception("文件ID为空")
        r = self.api.delete_file(fid)
        if not r.get("success"): raise Exception(f"删除失败: {r.get('message', '')}")
    def copy(self, dest_path, depth="0"):
        dest_provider = self.environ["wsgidav.provider"]
        dest_parent_path = dest_path.rsplit("/", 1)[0] or "/"
        dest_name = dest_path.rsplit("/", 1)[1]
        dest_parent = dest_provider.get_resource_inst(dest_parent_path, self.environ)
        if not dest_parent: raise Exception("目标父目录不存在")
        dest_parent_id = dest_parent.folder_id if hasattr(dest_parent, "folder_id") else ROOT_FOLDER_ID
        r = self.api.copy_file(self.file_info.get("fileId"), dest_parent_id)
        if not r.get("success"): raise Exception(f"复制失败: {r.get('message', '')}")
        new_id = r.get("data", {}).get("fileId")
        if dest_name != self.file_info.get("name", ""):
            self.api.rename_file(new_id, dest_name)
        return CMCCFileResource(dest_path, self.environ, self.api, {"name": dest_name, "fileId": new_id, "size": self.file_info.get("size", 0), "is_dir": False, "mtime": time.time(), "ctime": time.time(), "etag": hashlib.md5(f"{new_id}:{self.file_info.get('size',0)}".encode()).hexdigest()})
    def move(self, dest_path):
        dest_provider = self.environ["wsgidav.provider"]
        dest_parent_path = dest_path.rsplit("/", 1)[0] or "/"
        dest_name = dest_path.rsplit("/", 1)[1]
        dest_parent = dest_provider.get_resource_inst(dest_parent_path, self.environ)
        if not dest_parent: raise Exception("目标父目录不存在")
        dest_parent_id = dest_parent.folder_id if hasattr(dest_parent, "folder_id") else ROOT_FOLDER_ID
        fid = self.file_info.get("fileId")
        r = self.api.move_file(fid, dest_parent_id)
        if not r.get("success"): raise Exception(f"移动失败: {r.get('message', '')}")
        if dest_name != self.file_info.get("name", ""):
            self.api.rename_file(fid, dest_name)
        return CMCCFileResource(dest_path, self.environ, self.api, {"name": dest_name, "fileId": fid, "size": self.file_info.get("size", 0), "is_dir": False, "mtime": time.time(), "ctime": time.time(), "etag": hashlib.md5(f"{fid}:{self.file_info.get('size',0)}".encode()).hexdigest()})

class CMCCStream(io.RawIOBase):
    def __init__(self, api, file_id):
        self.api = api
        self.file_id = file_id
        self._generator = None
        self._buffer = b""
        self._closed = False
    def readable(self): return True
    def read(self, size=-1):
        if self._closed: return b""
        if self._generator is None:
            self._generator = self.api.download_file_stream(self.file_id, chunk_size=64*1024)
        if size is None or size < 0:
            chunks = [self._buffer]
            self._buffer = b""
            for chunk in self._generator:
                if chunk is None: break
                chunks.append(chunk)
            return b"".join(chunks)
        while len(self._buffer) < size:
            try:
                chunk = next(self._generator)
                if chunk is None: break
                self._buffer += chunk
            except StopIteration: break
        result, self._buffer = self._buffer[:size], self._buffer[size:]
        return result
    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)
    def close(self):
        self._closed = True
        self._generator = None
    def __enter__(self): return self
    def __exit__(self, *args): self.close()

class CMCCCloudProvider(DAVProvider):
    def __init__(self, api):
        super().__init__()
        self.api = api
    def get_resource_inst(self, path, environ):
        if path == "/" or not path:
            return CMCCFolderResource("/", environ, self.api, ROOT_FOLDER_ID, {"name": "root", "fileId": ROOT_FOLDER_ID, "is_dir": True})
        parent_path = path.rsplit("/", 1)[0] or "/"
        name = path.rsplit("/", 1)[1]
        parent = self.get_resource_inst(parent_path, environ)
        if not parent: return None
        for child_name in parent.get_member_names():
            if child_name == name:
                return parent.get_member(name)
        return None
    def exists(self, path, environ):
        if path == "/" or not path: return True
        return self.get_resource_inst(path, environ) is not None
