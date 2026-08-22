#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中国移动云盘 WebDAV 提供者. 支持: PROPFIND/GET/PUT/DELETE/MKCOL/MOVE/COPY/LOCK/UNLOCK/RANGE/流式"""
import os, io, time, hashlib, threading
from datetime import datetime
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection
from cmcc_api import CMCCCloudAPI, ROOT_FOLDER_ID

class CMCCFileResource(DAVNonCollection):
    def __init__(self, path, environ, api, file_info):
        super().__init__(path, environ); self.api=api; self.file_info=file_info
        self.file_id=file_info.get("fileId"); self.file_name=file_info.get("fileName","")
        self.file_size=file_info.get("fileSize",0) or file_info.get("size",0)
        self._content=None; self._lock=threading.Lock()
    def get_content_length(self): return self.file_size
    def get_content_type(self):
        ext=os.path.splitext(self.file_name)[1].lower()
        m={'.txt':'text/plain','.html':'text/html','.htm':'text/html','.css':'text/css','.js':'application/javascript','.json':'application/json','.xml':'application/xml','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.gif':'image/gif','.bmp':'image/bmp','.webp':'image/webp','.mp4':'video/mp4','.avi':'video/x-msvideo','.mkv':'video/x-matroska','.mp3':'audio/mpeg','.wav':'audio/wav','.flac':'audio/flac','.pdf':'application/pdf','.doc':'application/msword','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.xls':'application/vnd.ms-excel','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.ppt':'application/vnd.ms-powerpoint','.pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation','.zip':'application/zip','.rar':'application/x-rar-compressed','.7z':'application/x-7z-compressed','.tar':'application/x-tar','.gz':'application/gzip','.bz2':'application/x-bzip2','.exe':'application/x-msdownload','.dll':'application/x-msdownload','.msi':'application/x-msdownload','.apk':'application/vnd.android.package-archive','.ipa':'application/octet-stream','.dmg':'application/x-apple-diskimage','.iso':'application/x-iso9660-image','.csv':'text/csv','.md':'text/markdown','.py':'text/x-python','.java':'text/x-java-source','.c':'text/x-c','.cpp':'text/x-c++','.h':'text/x-c','.php':'text/x-php','.go':'text/x-go','.rs':'text/x-rust','.swift':'text/x-swift','.kt':'text/x-kotlin','.rb':'text/x-ruby','.sh':'text/x-shellscript','.bat':'text/x-batch','.ps1':'text/x-powershell','.sql':'text/x-sql','.yaml':'text/yaml','.yml':'text/yaml','.toml':'text/toml','.ini':'text/x-ini','.cfg':'text/x-ini','.conf':'text/x-ini','.log':'text/plain','.svg':'image/svg+xml','.ico':'image/x-icon','.tif':'image/tiff','.tiff':'image/tiff','.psd':'image/vnd.adobe.photoshop','.ai':'application/postscript','.eps':'application/postscript','.ttf':'font/ttf','.otf':'font/otf','.woff':'font/woff','.woff2':'font/woff2','.eot':'application/vnd.ms-fontobject','.epub':'application/epub+zip','.mobi':'application/x-mobipocket-ebook','.azw3':'application/vnd.amazon.ebook','.pages':'application/vnd.apple.pages','.numbers':'application/vnd.apple.numbers','.keynote':'application/vnd.apple.keynote','.dwg':'image/vnd.dwg','.dxf':'image/vnd.dxf','.sketch':'application/x-sketch','.fig':'application/x-figma','.xd':'application/vnd.adobe.xd','.pr':'application/x-premiere','.ae':'application/x-aftereffects','.blend':'application/x-blender','.obj':'model/obj','.stl':'model/stl','.fbx':'application/octet-stream','.glb':'model/gltf-binary','.gltf':'model/gltf+json','.wasm':'application/wasm','.crx':'application/x-chrome-extension','.xpi':'application/x-xpinstall','.deb':'application/vnd.debian.binary-package','.rpm':'application/x-rpm','.snap':'application/vnd.snap','.appimage':'application/x-appimage','.flatpak':'application/vnd.flatpak','.nix':'application/x-nix'}
        return m.get(ext,'application/octet-stream')
    def get_creation_date(self):
        c=self.file_info.get("created_at","") or self.file_info.get("createdAt","")
        if c:
            try: return datetime.fromisoformat(c.replace('Z','+00:00').replace('.000+08:00','+08:00')).timestamp()
            except: pass
        return time.time()
    def get_modified_date(self):
        u=self.file_info.get("updated_at","") or self.file_info.get("updatedAt","")
        if u:
            try: return datetime.fromisoformat(u.replace('Z','+00:00').replace('.000+08:00','+08:00')).timestamp()
            except: pass
        return time.time()
    def get_etag(self): return hashlib.md5(f"{self.file_id}:{self.file_size}".encode()).hexdigest()
    def support_etag(self): return True
    def support_ranges(self): return True
    def get_content(self):
        if self._content is None: self._content = self.api.download_file(self.file_id)
        if self._content is None: self._content = b""
        return io.BytesIO(self._content)
    def begin_write(self, content_type=None): return CMCCUploadBuffer(self.api, self.file_info.get("parentFileId"), self.file_name, self.file_id)
    def end_write(self, with_errors): pass
    def delete(self): return self.api.delete_file(self.file_id).get("success", False)
    def move(self, dest_path):
        dfp, dn = os.path.dirname(dest_path), os.path.basename(dest_path)
        dfid, _ = self.api.resolve_path(dfp)
        if dfid is None: return False
        cp = self.file_info.get("parentFileId")
        if dfid != cp:
            if not self.api.move_file(self.file_id, dfid).get("success"): return False
        if dn != self.file_name:
            nfid, _ = self.api.resolve_path(dest_path)
            if nfid: return self.api.rename_file(nfid, dn).get("success", False)
        return True
    def copy(self, dest_path):
        dfp = os.path.dirname(dest_path); dfid, _ = self.api.resolve_path(dfp)
        if dfid is None: return False
        return self.api.copy_file(self.file_id, dfid).get("success", False)
    def support_lock(self): return True

class CMCCUploadBuffer:
    def __init__(self, api, parent_id, file_name, old_file_id=None):
        self.api, self.parent_id, self.file_name, self.old_file_id = api, parent_id, file_name, old_file_id
        self.buffer, self._size = io.BytesIO(), 0
    def write(self, data): self.buffer.write(data); self._size += len(data)
    def close(self):
        data = self.buffer.getvalue(); self.buffer.close()
        if self.old_file_id: self.api.delete_file(self.old_file_id)
        self.api.upload_data(data, self.file_name, self.parent_id)

class CMCCFolderResource(DAVCollection):
    def __init__(self, path, environ, api, folder_id, folder_info=None):
        super().__init__(path, environ); self.api=api; self.folder_id=folder_id
        self.folder_info=folder_info or {}; self.folder_name=folder_info.get("fileName","") if folder_info else ""
        self._children_cache, self._children_cache_time, self._cache_ttl = None, 0, 30
    def get_creation_date(self):
        c = self.folder_info.get("created_at","") or self.folder_info.get("createdAt","") if self.folder_info else ""
        if c:
            try: return datetime.fromisoformat(c.replace('Z','+00:00').replace('.000+08:00','+08:00')).timestamp()
            except: pass
        return time.time()
    def get_modified_date(self):
        u = self.folder_info.get("updated_at","") or self.folder_info.get("updatedAt","") if self.folder_info else ""
        if u:
            try: return datetime.fromisoformat(u.replace('Z','+00:00').replace('.000+08:00','+08:00')).timestamp()
            except: pass
        return time.time()
    def get_etag(self): return hashlib.md5(self.folder_id.encode()).hexdigest()
    def support_etag(self): return True
    def _get_children(self):
        now = time.time()
        if self._children_cache is not None and now - self._children_cache_time < self._cache_ttl: return self._children_cache
        self._children_cache = self.api.get_children(self.folder_id); self._children_cache_time = now
        return self._children_cache
    def get_member_names(self): return [c.get("fileName","") for c in self._get_children()]
    def get_member(self, name):
        for c in self._get_children():
            if c.get("fileName") == name:
                cp = self.path + "/" + name if self.path != "/" else "/" + name
                if c.get("fileType") == 2: return CMCCFolderResource(cp, self.environ, self.api, c.get("fileId"), c)
                else: return CMCCFileResource(cp, self.environ, self.api, c)
        return None
    def create_collection(self, name):
        r = self.api.create_folder(name, self.folder_id)
        if r.get("success"): self._children_cache = None
        return r.get("success", False)
    def create_empty_resource(self, name):
        cp = self.path + "/" + name if self.path != "/" else "/" + name
        return CMCCFileResource(cp, self.environ, self.api, {"fileId":None,"fileName":name,"fileSize":0,"parentFileId":self.folder_id,"fileType":1})
    def delete(self):
        if self.folder_id == ROOT_FOLDER_ID: return False
        return self.api.delete_file(self.folder_id).get("success", False)
    def move(self, dest_path):
        if self.folder_id == ROOT_FOLDER_ID: return False
        dfp, dn = os.path.dirname(dest_path), os.path.basename(dest_path)
        dfid, _ = self.api.resolve_path(dfp)
        if dfid is None: return False
        cp = self.folder_info.get("parentFileId")
        if dfid != cp:
            if not self.api.move_file(self.folder_id, dfid).get("success"): return False
        if dn != self.folder_name:
            nfid, _ = self.api.resolve_path(dest_path)
            if nfid: return self.api.rename_file(nfid, dn).get("success", False)
        return True
    def copy(self, dest_path):
        if self.folder_id == ROOT_FOLDER_ID: return False
        dfp = os.path.dirname(dest_path); dfid, _ = self.api.resolve_path(dfp)
        if dfid is None: return False
        if not self.api.copy_file(self.folder_id, dfid).get("success"): return False
        nfid, _ = self.api.resolve_path(dest_path)
        if not nfid: return True
        return self._copy_children(self.folder_id, nfid)
    def _copy_children(self, src, dst):
        for c in self.api.get_children(src):
            cid = c.get("fileId")
            if c.get("fileType") == 2:
                if self.api.copy_file(cid, dst).get("success"):
                    np = self.api.get_parent_path(cid)
                    if np:
                        nid, _ = self.api.resolve_path(np)
                        if nid: self._copy_children(cid, nid)
            else: self.api.copy_file(cid, dst)
        return True

class CMCCCloudProvider(DAVProvider):
    def __init__(self, api): super().__init__(); self.api = api
    def get_resource_inst(self, path, environ):
        self._count_get_resource_inst += 1
        if path in ("/",""): return CMCCFolderResource(path, environ, self.api, ROOT_FOLDER_ID)
        fid, finfo = self.api.resolve_path(path)
        if fid is None: return None
        if finfo and finfo.get("fileType") == 2: return CMCCFolderResource(path, environ, self.api, fid, finfo)
        if finfo: return CMCCFileResource(path, environ, self.api, finfo)
        pp = os.path.dirname(path); pid, _ = self.api.resolve_path(pp)
        if pid:
            fn = os.path.basename(path)
            return CMCCFileResource(path, environ, self.api, {"fileId":None,"fileName":fn,"fileSize":0,"parentFileId":pid,"fileType":1})
        return None
    def is_readonly(self): return False
