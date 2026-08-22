#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中国移动云盘 (yun.139.com) API 封装
支持: 列表/上传/下载/删除/重命名/创建文件夹/移动/复制/回收站/容量查询/分享/星标/分类/搜索/历史版本/离线下载
改进: 签名算法/分片上传/秒传/流式下载/断点续传/请求重试/限流/缓存/skey-token备用认证/全文件类型支持
"""
import requests, json, base64, time, uuid, hashlib, os, re, threading
from datetime import datetime
from urllib.parse import quote, unquote
ROOT_FOLDER_ID = "DFn_Mm9QAFQA0611WrpTl1Oy00019700101000000044"
BASE_URL = "https://personal-kd-njs.yun.139.com"
ORCH_URL = "https://yun.139.com"
CATEGORY_IMAGE, CATEGORY_VIDEO, CATEGORY_AUDIO, CATEGORY_DOCUMENT, CATEGORY_APPLICATION, CATEGORY_OTHER, CATEGORY_ALL = 1, 2, 3, 4, 5, 6, 0

class CMCCCloudAPI:
    def __init__(self, phone=None, auth_token=None, cookie_str=None):
        self.phone, self.auth_token, self.cookie_str, self.ud_id = phone, auth_token, cookie_str, None
        self.session = requests.Session()
        self._cache, self._cache_time, self._path_cache, self._path_cache_time = {}, {}, {}, {}
        self._cache_lock, self._cache_ttl, self._last_request_time, self._min_interval = threading.Lock(), 30, 0, 0.1
        self._init_headers()

    def _init_headers(self):
        self.base_headers = {"Accept":"application/json, text/plain, */*","Accept-Language":"zh-CN,zh;q=0.9","Accept-Encoding":"gzip, deflate, br","CMS-DEVICE":"default","Content-Type":"application/json;charset=UTF-8","INNER-HCY-ROUTER-HTTPS":"1","Origin":"https://yun.139.com","Referer":"https://yun.139.com/","User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36","X-Deviceinfo":"||9|7.17.11|chrome|103.0.0.0||dW5kZWZpbmVk||","caller":"web","mcloud-channel":"1000101","mcloud-client":"10701","mcloud-route":"001","mcloud-version":"7.17.11","x-SvcType":"1","x-huawei-channelSrc":"10000034","x-inner-ntwk":"2","x-m4c-caller":"PC","x-m4c-src":"10002","x-yun-api-version":"v1","x-yun-app-channel":"10000034","x-yun-channel-source":"10000034","x-yun-client-info":"||9|7.17.11|chrome|103.0.0.0||dW5kZWZpbmVk||","x-yun-module-type":"100","x-yun-svc-type":"1"}
        if self.cookie_str:
            self.session.headers.update({"Cookie": self.cookie_str})
            self._parse_cookie()
            m = re.search(r'authorization=([^;]+)', self.cookie_str)
            if m: self.base_headers["Authorization"] = unquote(m.group(1)).strip()
        elif self.phone and self.auth_token:
            self.base_headers["Authorization"] = "Basic " + base64.b64encode(f"pc:{self.phone}:{self.auth_token}".encode()).decode()

    def _parse_cookie(self):
        if not self.cookie_str: return
        m = re.search(r'auth_token=([^;]+)', self.cookie_str)
        if m: self.auth_token = unquote(m.group(1))
        m = re.search(r'skey=([^;]+)', self.cookie_str)
        if m and not self.auth_token: self.auth_token = unquote(m.group(1))
        m = re.search(r'token=([^;]+)', self.cookie_str)
        if m and not self.auth_token: self.auth_token = unquote(m.group(1))
        m = re.search(r'authorization=([^;]+)', self.cookie_str)
        if m:
            try:
                v = unquote(m.group(1)).strip()
                if v.startswith('Basic '): v = v[6:]
                p = base64.b64decode(v).decode().split(':')
                if len(p) >= 2: self.phone = p[1]
            except: pass
        m = re.search(r'ud_id=([^;]+)', self.cookie_str)
        if m: self.ud_id = m.group(1)
        m = re.search(r'ORCHES-I-ACCOUNT-ENCRYPT=([^;]+)', self.cookie_str)
        if m and not self.phone:
            try: self.phone = base64.b64decode(unquote(m.group(1))).decode()
            except: pass
        m = re.search(r'ORCHES-I-ACCOUNT-SIMPLIFY=([^;]+)', self.cookie_str)
        if m and not self.phone:
            v = unquote(m.group(1)).replace('*','')
            if v.isdigit(): self.phone = v

    def _make_sign(self):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r = uuid.uuid4().hex[:16]
        return f"{now},{r},{hashlib.md5(f'{now},{r}'.encode()).hexdigest().upper()}"
    def _rate_limit(self):
        e = time.time() - self._last_request_time
        if e < self._min_interval: time.sleep(self._min_interval - e)
        self._last_request_time = time.time()
    def _request(self, method, url, data=None, headers=None, retry=3, timeout=30):
        self._rate_limit()
        h = dict(self.base_headers)
        if headers: h.update(headers)
        h["mcloud-sign"] = self._make_sign()
        last_err = None
        for a in range(retry):
            try:
                if method.upper() == "GET": r = self.session.get(url, headers=h, timeout=timeout)
                else: r = self.session.post(url, json=data, headers=h, timeout=timeout)
                r.raise_for_status()
                return r.json()
            except requests.exceptions.Timeout: last_err = "超时"; time.sleep(1*(a+1))
            except requests.exceptions.ConnectionError as e: last_err = f"连接失败:{e}"; time.sleep(1*(a+1))
            except Exception as e: last_err = str(e); break
        return {"success":False,"code":-1,"message":last_err or "未知错误"}

    def _get_cache_key(self, fid): return fid or ROOT_FOLDER_ID
    def _get_cached_files(self, fid):
        with self._cache_lock:
            k = self._get_cache_key(fid)
            if k in self._cache and time.time() - self._cache_time.get(k,0) < self._cache_ttl: return self._cache[k]
        return None
    def _set_cached_files(self, fid, files):
        with self._cache_lock:
            k = self._get_cache_key(fid)
            self._cache[k], self._cache_time[k] = files, time.time()
    def _invalidate_cache(self, fid=None):
        with self._cache_lock:
            if fid:
                self._cache.pop(self._get_cache_key(fid), None)
                self._cache_time.pop(self._get_cache_key(fid), None)
            else: self._cache.clear(); self._cache_time.clear(); self._path_cache.clear(); self._path_cache_time.clear()

    def list_files(self, parent_file_id=None, page_size=100, page_cursor=None, order_by="updated_at", order_direction="DESC", use_cache=True):
        if use_cache and page_cursor is None:
            c = self._get_cached_files(parent_file_id)
            if c is not None: return {"success":True,"code":0,"message":"ok","data":{"getFileCount":len(c),"fileListAO":{"fileList":c,"fileListSize":len(c)}}}
        url, data = f"{BASE_URL}/hcy/file/list", {"pageInfo":{"pageSize":page_size,"pageCursor":page_cursor},"orderBy":order_by,"orderDirection":order_direction,"parentFileId":parent_file_id or ROOT_FOLDER_ID,"imageThumbnailStyleList":["Small","Large"]}
        r = self._request("POST", url, data)
        if use_cache and r.get("success") and page_cursor is None:
            self._set_cached_files(parent_file_id, r.get("data",{}).get("fileListAO",{}).get("fileList",[]))
        return r
    def get_file(self, file_id): return self._request("POST", f"{BASE_URL}/hcy/file/get", {"fileId":file_id})
    def list_all_files(self, parent_file_id=None, use_cache=True):
        if use_cache:
            c = self._get_cached_files(parent_file_id)
            if c is not None: return c
        all_files, cursor = [], None
        while True:
            r = self.list_files(parent_file_id=parent_file_id, page_cursor=cursor, use_cache=False)
            if not r.get("success"): break
            fl = r.get("data",{}).get("fileListAO",{}).get("fileList",[])
            all_files.extend(fl); cursor = r.get("data",{}).get("pageInfo",{}).get("pageCursor")
            if not cursor or not fl: break
        if use_cache: self._set_cached_files(parent_file_id, all_files)
        return all_files
    def get_file_count(self, parent_file_id=None): return self._request("POST", f"{BASE_URL}/hcy/file/getFileCount", {"parentFileId":parent_file_id or ROOT_FOLDER_ID})
    def get_folder_size(self, folder_id): return self._request("POST", f"{BASE_URL}/hcy/folder/getSize", {"folderId":folder_id})

    def search_files(self, keyword, parent_file_id=None):
        all_files = []
        def rec(fid, d=0):
            if d>10: return
            for f in self.list_all_files(fid, use_cache=True):
                if keyword.lower() in f.get("fileName","").lower(): all_files.append(f)
                if f.get("fileType")==2: rec(f.get("fileId"), d+1)
        rec(parent_file_id or ROOT_FOLDER_ID)
        return all_files
    def search_files_api(self, keyword, parent_file_id=None, page_size=100): return self._request("POST", f"{BASE_URL}/hcy/file/search", {"keyword":keyword,"parentFileId":parent_file_id or ROOT_FOLDER_ID,"pageInfo":{"pageSize":page_size,"pageCursor":None}})

    def get_category_files(self, category=CATEGORY_ALL, page_size=100, page_cursor=None): return self._request("POST", f"{BASE_URL}/hcy/file/listByCategory", {"category":category,"pageInfo":{"pageSize":page_size,"pageCursor":page_cursor}})
    def get_recent_files(self, days=30, page_size=100): return self._request("POST", f"{BASE_URL}/hcy/file/listRecent", {"days":days,"pageInfo":{"pageSize":page_size,"pageCursor":None}})

    def create_folder(self, folder_name, parent_file_id=None):
        r = self._request("POST", f"{BASE_URL}/hcy/folder/create", {"folderName":folder_name,"parentFileId":parent_file_id or ROOT_FOLDER_ID})
        if r.get("success"): self._invalidate_cache(parent_file_id)
        return r
    def create_folders(self, folder_path, parent_file_id=None):
        parts, cur = [p for p in folder_path.split("/") if p], parent_file_id or ROOT_FOLDER_ID
        for part in parts:
            found = False
            for c in self.list_all_files(cur, use_cache=False):
                if c.get("fileName")==part and c.get("fileType")==2: cur, found = c.get("fileId"), True; break
            if not found:
                r = self.create_folder(part, cur)
                if r.get("success"): cur = r.get("data",{}).get("fileId") or r.get("data",{}).get("catalogID")
                else: return None
        return cur

    def check_file_exists(self, file_name, file_size, parent_file_id=None): return self._request("POST", f"{BASE_URL}/hcy/file/checkExist", {"fileName":file_name,"fileSize":file_size,"parentFileId":parent_file_id or ROOT_FOLDER_ID})
    def get_upload_url(self, file_name, file_size, parent_file_id=None): return self._request("POST", f"{BASE_URL}/hcy/file/upload", {"fileName":file_name,"fileSize":file_size,"parentFileId":parent_file_id or ROOT_FOLDER_ID,"checkNameMode":1})

    def upload_file(self, file_path, parent_file_id=None, file_name=None, progress_callback=None):
        if not os.path.exists(file_path): return {"success":False,"message":"文件不存在"}
        file_name, file_size, parent_id = file_name or os.path.basename(file_path), os.path.getsize(file_path), parent_file_id or ROOT_FOLDER_ID
        check = self.check_file_exists(file_name, file_size, parent_id)
        if check.get("success") and check.get("data",{}).get("isExist"):
            if progress_callback: progress_callback(100, file_size, file_size)
            return {"success":True,"message":"秒传成功","data":check.get("data")}
        if file_size < 10*1024*1024: return self._upload_small(file_path, file_name, file_size, parent_id, progress_callback)
        return self._upload_large(file_path, file_name, file_size, parent_id, progress_callback)

    def _upload_small(self, file_path, file_name, file_size, parent_id, progress_callback=None):
        with open(file_path,'rb') as f: file_data = f.read()
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"
        body = []
        for k,v in [("parentFileId",parent_id),("fileName",file_name),("fileSize",str(file_size))]:
            body.extend([f'--{boundary}',f'Content-Disposition: form-data; name="{k}"','',v])
        body.extend([f'--{boundary}',f'Content-Disposition: form-data; name="file"; filename="{file_name}"','Content-Type: application/octet-stream',''])
        body_bytes = '\r\n'.join(body).encode('utf-8')+b'\r\n'+file_data+b'\r\n'+f'--{boundary}--\r\n'.encode('utf-8')
        h = dict(self.base_headers); h["Content-Type"] = f"multipart/form-data; boundary={boundary}"; del h["mcloud-sign"]
        try:
            r = self.session.post(f"{BASE_URL}/hcy/file/upload", data=body_bytes, headers=h, timeout=300).json()
            if r.get("success"): self._invalidate_cache(parent_id); progress_callback and progress_callback(100, file_size, file_size)
            return r
        except Exception as e: return {"success":False,"message":f"上传失败:{e}"}

    def _upload_large(self, file_path, file_name, file_size, parent_id, progress_callback=None):
        chunk_size, chunks, uploaded, chunk_md5s = 4*1024*1024, (file_size+4*1024*1024-1)//(4*1024*1024), 0, []
        with open(file_path,'rb') as f:
            for i in range(chunks):
                chunk_data = f.read(chunk_size); chunk_md5 = hashlib.md5(chunk_data).hexdigest(); chunk_md5s.append(chunk_md5)
                r = self._upload_chunk(chunk_data, chunk_md5, i, chunks, file_name, parent_id)
                if not r.get("success"): return r
                uploaded += len(chunk_data); progress_callback and progress_callback(int(uploaded/file_size*100), uploaded, file_size)
        return self._merge_chunks(file_name, file_size, parent_id, chunk_md5s)

    def _upload_chunk(self, chunk_data, chunk_md5, chunk_index, total_chunks, file_name, parent_id):
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"
        body = []
        for k,v in [("parentFileId",parent_id),("fileName",file_name),("chunkIndex",str(chunk_index)),("totalChunks",str(total_chunks)),("chunkMd5",chunk_md5)]:
            body.extend([f'--{boundary}',f'Content-Disposition: form-data; name="{k}"','',v])
        body.extend([f'--{boundary}',f'Content-Disposition: form-data; name="file"; filename="chunk_{chunk_index}"','Content-Type: application/octet-stream',''])
        body_bytes = '\r\n'.join(body).encode('utf-8')+b'\r\n'+chunk_data+b'\r\n'+f'--{boundary}--\r\n'.encode('utf-8')
        h = dict(self.base_headers); h["Content-Type"] = f"multipart/form-data; boundary={boundary}"; del h["mcloud-sign"]
        try: return self.session.post(f"{BASE_URL}/hcy/file/uploadChunk", data=body_bytes, headers=h, timeout=120).json()
        except Exception as e: return {"success":False,"message":f"分片上传失败:{e}"}

    def _merge_chunks(self, file_name, file_size, parent_id, chunk_md5s):
        r = self._request("POST", f"{BASE_URL}/hcy/file/mergeChunks", {"fileName":file_name,"fileSize":file_size,"parentFileId":parent_id,"chunkMd5s":chunk_md5s})
        if r.get("success"): self._invalidate_cache(parent_id)
        return r

    def upload_data(self, data, file_name, parent_file_id=None, progress_callback=None):
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as f: f.write(data); tp = f.name
        try: return self.upload_file(tp, parent_file_id, file_name, progress_callback)
        finally: os.unlink(tp)
    def cancel_upload(self, upload_id): return self._request("POST", f"{BASE_URL}/hcy/file/cancelUpload", {"uploadId":upload_id})

    def get_download_url(self, file_id):
        fi = self.get_file(file_id)
        if not fi.get("success"): return None
        fd = fi.get("data",{})
        du = fd.get("downloadUrl") or fd.get("contentUrl") or fd.get("url") or fd.get("fileUrl") or fd.get("downloadURL") or fd.get("presignedUrl")
        if du and isinstance(du,str) and du.startswith("http"): return du
        r = self._request("POST", f"{BASE_URL}/hcy/file/getDownloadUrl", {"fileId":file_id})
        if r.get("success"):
            ud = r.get("data",{})
            if isinstance(ud,str) and ud.startswith("http"): return ud
            return ud.get("downloadUrl") or ud.get("url") or ud.get("fileUrl")
        return None
    def download_file(self, file_id):
        du = self.get_download_url(file_id)
        if not du: return None
        try: return self.session.get(du, timeout=300, stream=True).content
        except Exception as e: print(f"[Download Error] {e}"); return None
    def download_file_stream(self, file_id, chunk_size=64*1024):
        du = self.get_download_url(file_id)
        if not du: yield None; return
        try:
            for c in self.session.get(du, timeout=300, stream=True).iter_content(chunk_size=chunk_size):
                if c: yield c
        except Exception as e: print(f"[Stream Error] {e}"); yield None
    def download_file_range(self, file_id, start, end):
        du = self.get_download_url(file_id)
        if not du: return None
        try: return self.session.get(du, headers={"Range":f"bytes={start}-{end}"}, timeout=300).content
        except Exception as e: print(f"[Range Error] {e}"); return None
    def get_file_md5(self, file_id): return self._request("POST", f"{BASE_URL}/hcy/file/getMd5", {"fileId":file_id})
    def get_file_preview(self, file_id): return self._request("POST", f"{BASE_URL}/hcy/file/preview", {"fileId":file_id})
    def get_file_thumbnail(self, file_id, size="Small"): return self._request("POST", f"{BASE_URL}/hcy/file/thumbnail", {"fileId":file_id,"size":size})

    def delete_file(self, file_id): return self.batch_delete([file_id])
    def batch_delete(self, file_ids):
        r = self._request("POST", f"{BASE_URL}/hcy/recyclebin/batchTrash", {"fileIds":file_ids if isinstance(file_ids,list) else [file_ids]})
        if r.get("success"): self._invalidate_cache()
        return r
    def restore_from_trash(self, file_ids):
        r = self._request("POST", f"{BASE_URL}/hcy/recyclebin/batchRestore", {"fileIds":file_ids if isinstance(file_ids,list) else [file_ids]})
        if r.get("success"): self._invalidate_cache()
        return r
    def permanent_delete(self, file_ids):
        r = self._request("POST", f"{BASE_URL}/hcy/recyclebin/batchDelete", {"fileIds":file_ids if isinstance(file_ids,list) else [file_ids]})
        if r.get("success"): self._invalidate_cache()
        return r
    def list_trash(self, page_size=100, page_cursor=None): return self._request("POST", f"{BASE_URL}/hcy/recyclebin/list", {"pageInfo":{"pageSize":page_size,"pageCursor":page_cursor}})
    def get_recyclebin_info(self): return self._request("POST", f"{BASE_URL}/hcy/recyclebin/getInfo", {})
    def empty_recyclebin(self):
        r = self._request("POST", f"{BASE_URL}/hcy/recyclebin/empty", {})
        if r.get("success"): self._invalidate_cache()
        return r

    def rename_file(self, file_id, new_name):
        r = self._request("POST", f"{BASE_URL}/hcy/file/rename", {"fileId":file_id,"fileName":new_name})
        if r.get("success"): self._invalidate_cache()
        return r
    def batch_rename(self, renames):
        r = self._request("POST", f"{BASE_URL}/hcy/file/batchRename", {"renameList":renames})
        if r.get("success"): self._invalidate_cache()
        return r

    def move_file(self, file_ids, dest_parent_id):
        r = self._request("POST", f"{BASE_URL}/hcy/file/batchMove", {"fileIds":file_ids if isinstance(file_ids,list) else [file_ids],"destParentFileId":dest_parent_id})
        if r.get("success"): self._invalidate_cache()
        return r
    def copy_file(self, file_ids, dest_parent_id):
        r = self._request("POST", f"{BASE_URL}/hcy/file/batchCopy", {"fileIds":file_ids if isinstance(file_ids,list) else [file_ids],"destParentFileId":dest_parent_id})
        if r.get("success"): self._invalidate_cache(dest_parent_id)
        return r

    def share_file(self, file_ids, share_name=None, expire_days=7, share_type=1, password=None): return self._request("POST", f"{BASE_URL}/hcy/share/create", {"fileIds":file_ids if isinstance(file_ids,list) else [file_ids],"shareName":share_name,"expireDays":expire_days,"shareType":share_type,"password":password})
    def get_share_list(self, page_size=100, page_cursor=None): return self._request("POST", f"{BASE_URL}/hcy/share/list", {"pageInfo":{"pageSize":page_size,"pageCursor":page_cursor}})
    def cancel_share(self, share_ids): return self._request("POST", f"{BASE_URL}/hcy/share/cancel", {"shareIds":share_ids if isinstance(share_ids,list) else [share_ids]})
    def get_share_detail(self, share_id): return self._request("POST", f"{BASE_URL}/hcy/share/detail", {"shareId":share_id})
    def save_shared_file(self, share_id, file_ids, dest_parent_id=None, password=None):
        r = self._request("POST", f"{BASE_URL}/hcy/share/save", {"shareId":share_id,"fileIds":file_ids if isinstance(file_ids,list) else [file_ids],"destParentFileId":dest_parent_id or ROOT_FOLDER_ID,"password":password})
        if r.get("success"): self._invalidate_cache(dest_parent_id)
        return r
    def get_share_access_url(self, share_id, password=None): return self._request("POST", f"{BASE_URL}/hcy/share/getAccessUrl", {"shareId":share_id,"password":password})

    def star_file(self, file_ids): return self._request("POST", f"{BASE_URL}/hcy/file/star", {"fileIds":file_ids if isinstance(file_ids,list) else [file_ids]})
    def unstar_file(self, file_ids): return self._request("POST", f"{BASE_URL}/hcy/file/unstar", {"fileIds":file_ids if isinstance(file_ids,list) else [file_ids]})
    def get_starred_files(self, page_size=100, page_cursor=None): return self._request("POST", f"{BASE_URL}/hcy/file/listStarred", {"pageInfo":{"pageSize":page_size,"pageCursor":page_cursor}})

    def get_file_history(self, file_id, page_size=100): return self._request("POST", f"{BASE_URL}/hcy/file/history", {"fileId":file_id,"pageInfo":{"pageSize":page_size,"pageCursor":None}})
    def restore_file_version(self, file_id, version_id):
        r = self._request("POST", f"{BASE_URL}/hcy/file/restoreVersion", {"fileId":file_id,"versionId":version_id})
        if r.get("success"): self._invalidate_cache()
        return r

    def add_offline_download(self, url, file_name=None, parent_file_id=None): return self._request("POST", f"{BASE_URL}/hcy/offlineDownload/add", {"url":url,"fileName":file_name,"parentFileId":parent_file_id or ROOT_FOLDER_ID})
    def get_offline_download_list(self, page_size=100, page_cursor=None): return self._request("POST", f"{BASE_URL}/hcy/offlineDownload/list", {"pageInfo":{"pageSize":page_size,"pageCursor":page_cursor}})
    def get_offline_download_status(self, task_id): return self._request("POST", f"{BASE_URL}/hcy/offlineDownload/status", {"taskId":task_id})
    def cancel_offline_download(self, task_id): return self._request("POST", f"{BASE_URL}/hcy/offlineDownload/cancel", {"taskId":task_id})

    def get_user_info(self): return self._request("POST", f"{BASE_URL}/hcy/user/get", {"account":self.phone} if self.phone else {})
    def get_capacity(self): return self._request("POST", f"{ORCH_URL}/orchestration/personalCloud-rebuild/user/v1.0/qryUserCapacity", {})
    def get_user_domain(self): return self._request("POST", f"{ORCH_URL}/orchestration/personalCloud-rebuild/user/v1.0/qryUserDomain", {})
    def get_index_catalog(self): return self._request("POST", f"{ORCH_URL}/orchestration/personalCloud-rebuild/index/v1.0/qryIndexCatalog", {})
    def get_storage_info(self): return self._request("POST", f"{BASE_URL}/hcy/user/storageInfo", {})
    def get_family_storage_info(self): return self._request("POST", f"{BASE_URL}/hcy/family/storageInfo", {})
    def get_task_status(self, task_id): return self._request("POST", f"{BASE_URL}/hcy/task/get", {"taskId":task_id})

    def resolve_path(self, path):
        if not path or path in ("/",""): return ROOT_FOLDER_ID, {"fileType":2,"fileName":"root"}
        with self._cache_lock:
            if path in self._path_cache and time.time()-self._path_cache_time.get(path,0)<self._cache_ttl: return self._path_cache[path]
        parts = [p for p in path.split("/") if p]
        if not parts: return ROOT_FOLDER_ID, {"fileType":2,"fileName":"root"}
        cur, info = ROOT_FOLDER_ID, None
        for part in parts:
            found = False
            for f in self.list_all_files(cur):
                if f.get("fileName")==part: cur, info, found = f.get("fileId"), f, True; break
            if not found: return None, None
        with self._cache_lock: self._path_cache[path], self._path_cache_time[path] = (cur, info), time.time()
        return cur, info
    def get_children(self, folder_id): return self.list_all_files(folder_id)
    def get_child_by_name(self, folder_id, name):
        for c in self.get_children(folder_id):
            if c.get("fileName")==name: return c
        return None
    def get_parent_path(self, file_id):
        if file_id==ROOT_FOLDER_ID: return "/"
        fi = self.get_file(file_id)
        if not fi.get("success"): return None
        fd = fi.get("data",{}); fn, pid = fd.get("fileName",""), fd.get("parentFileId")
        if pid==ROOT_FOLDER_ID or not pid: return "/"+fn
        pp = self.get_parent_path(pid)
        return None if pp is None else pp+"/"+fn
    def path_exists(self, path): return self.resolve_path(path)[0] is not None
    def is_folder(self, path):
        fid, info = self.resolve_path(path)
        return info.get("fileType")==2 if info else False

def create_api_from_cookie(cookie_str): return CMCCCloudAPI(cookie_str=cookie_str)
def create_api_from_creds(phone, auth_token): return CMCCCloudAPI(phone=phone, auth_token=auth_token)
