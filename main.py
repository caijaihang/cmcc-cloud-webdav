#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CMCC Cloud WebDAV - 主程序入口. 支持: WebDAV认证/自动重连/心跳检测/配置热重载/系统托盘/日志持久化/信号处理/安卓兼容"""
import os, sys, json, time, threading, argparse, webbrowser, signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cmcc_api import CMCCCloudAPI, create_api_from_cookie, create_api_from_creds
from webdav_provider import CMCCCloudProvider
from web_ui import WebUIManager
try:
    from wsgidav.wsgidav_app import WsgiDAVApp
except ImportError as e:
    print(f"[ERROR] 缺少依赖: {e}\n请运行: pip install -r requirements.txt"); sys.exit(1)

class CMCCCloudWebDAV:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.api = None; self.dav_app = None; self.dav_server = None
        self.ui_manager = None; self.tray_manager = None; self.running = False
        self._log_file = None; self._log_lock = threading.Lock()
        self._heartbeat_thread = None; self._heartbeat_stop = threading.Event()
        self._reconnect_attempts = 0; self._max_reconnect = 5
        self._init_log_file()
    def _init_log_file(self):
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        self._log_file = open(os.path.join(log_dir, f"cmcc-webdav-{time.strftime('%Y%m%d')}.log"), 'a', encoding='utf-8')
        self._log("INFO", "程序启动")
    def _log(self, level, message):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {message}\n"
        with self._log_lock:
            if self._log_file: self._log_file.write(line); self._log_file.flush()
        print(line.strip())
    def _load_config(self):
        default = {"webdav":{"host":"0.0.0.0","port":8081,"mount_path":"Z:","readonly":False,"auth_enabled":False,"username":"admin","password":"admin"},"auth":{"cookie":"","phone":"","auth_token":""},"ui":{"host":"127.0.0.1","port":8080},"auto_start":False,"minimize_to_tray":True,"auto_open_browser":True,"log_level":"INFO","heartbeat_interval":60,"auto_reconnect":True}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f: loaded = json.load(f)
                for k,v in default.items():
                    if k not in loaded: loaded[k] = v
                    elif isinstance(v, dict):
                        for sk,sv in v.items():
                            if sk not in loaded[k]: loaded[k][sk] = sv
                return loaded
            except Exception as e: print(f"[WARN] 配置读取失败: {e}")
        return default
    def _save_config(self):
        with open(self.config_path, 'w', encoding='utf-8') as f: json.dump(self.config, f, ensure_ascii=False, indent=2)
    def _init_api(self):
        auth = self.config.get("auth", {})
        cookie, phone, token = auth.get("cookie",""), auth.get("phone",""), auth.get("auth_token","")
        if cookie: self.api = create_api_from_cookie(cookie); self._log("INFO", "使用Cookie认证")
        elif phone and token: self.api = create_api_from_creds(phone, token); self._log("INFO", f"使用手机号+Token: {phone}")
        else: self._log("ERROR", "未配置认证信息"); return False
        r = self.api.list_files()
        if r.get("success"): self._log("INFO", "云盘连接成功"); self._reconnect_attempts = 0; return True
        else: self._log("ERROR", f"连接失败: {r.get('message','未知错误')}"); return False
    def _start_heartbeat(self):
        if self._heartbeat_thread and self._heartbeat_thread.is_alive(): return
        self._heartbeat_stop.clear(); interval = self.config.get("heartbeat_interval", 60)
        def loop():
            while not self._heartbeat_stop.is_set():
                self._heartbeat_stop.wait(interval)
                if self._heartbeat_stop.is_set(): break
                if not self.running or not self.api: continue
                try:
                    r = self.api.list_files(page_size=1, use_cache=False)
                    if not r.get("success"):
                        self._log("WARN", f"心跳失败: {r.get('message','')}")
                        if self.config.get("auto_reconnect", True): self._attempt_reconnect()
                    else: self._reconnect_attempts = 0
                except Exception as e:
                    self._log("WARN", f"心跳异常: {e}")
                    if self.config.get("auto_reconnect", True): self._attempt_reconnect()
        self._heartbeat_thread = threading.Thread(target=loop, daemon=True); self._heartbeat_thread.start(); self._log("INFO", f"心跳已启动({interval}s)")
    def _stop_heartbeat(self): self._heartbeat_stop.set(); self._heartbeat_thread and self._heartbeat_thread.join(timeout=2)
    def _attempt_reconnect(self):
        if self._reconnect_attempts >= self._max_reconnect: self._log("ERROR", "重连次数已达上限"); return
        self._reconnect_attempts += 1; self._log("INFO", f"重连 {self._reconnect_attempts}/{self._max_reconnect}")
        self._stop_webdav(); time.sleep(2); success, msg = self._start_webdav()
        if success: self._log("INFO", "重连成功"); self._reconnect_attempts = 0
        else: self._log("ERROR", f"重连失败: {msg}")
    def _start_webdav(self):
        if not self.api and not self._init_api(): return False, "API初始化失败"
        wc = self.config.get("webdav", {}); host, port = wc.get("host","0.0.0.0"), wc.get("port",8081)
        readonly, auth_en = wc.get("readonly",False), wc.get("auth_enabled",False)
        uname, pwd = wc.get("username","admin"), wc.get("password","admin")
        provider = CMCCCloudProvider(self.api)
        dav_cfg = {"host":host,"port":port,"provider_mapping":{"/":provider},"verbose":1,"logging":{"enable":False},"property_manager":None,"lock_manager":True,"acceptbasic":True,"acceptdigest":False,"defaultdigest":False}
        if auth_en: dav_cfg["simple_dc"] = {"user_mapping":{"*":{uname:{"password":pwd}}}}
        try:
            self.dav_app = WsgiDAVApp(dav_cfg)
            from cheroot.wsgi import Server as WSGIServer
            self.dav_server = WSGIServer((host, port), self.dav_app)
            def run_dav():
                try: self._log("INFO", f"WebDAV已启动: http://{host}:{port}"); self.dav_server.start()
                except Exception as e: self._log("ERROR", f"WebDAV异常: {e}")
            threading.Thread(target=run_dav, daemon=True).start()
            self.running = True; self._start_heartbeat(); return True, "服务已启动"
        except Exception as e: err = f"启动失败: {e}"; self._log("ERROR", err); import traceback; traceback.print_exc(); return False, err
    def _stop_webdav(self):
        self._stop_heartbeat()
        if self.dav_server:
            try: self.dav_server.stop()
            except: pass
        self.dav_server = None; self.dav_app = None; self.running = False; self._log("INFO", "WebDAV已停止")
    def _start_ui(self):
        uc = self.config.get("ui", {}); host, port = uc.get("host","127.0.0.1"), uc.get("port",8080)
        self.ui_manager = WebUIManager(host=host, port=port, config_path=self.config_path, control_callback=self._handle_control, status_callback=self._get_status, log_callback=self._handle_log)
        self.ui_manager.start(); return True
    def _start_tray(self):
        if not self.config.get("minimize_to_tray", True): return False
        try:
            from tray_icon import TrayIconManager
            uu = f"http://{self.config.get('ui',{}).get('host','127.0.0.1')}:{self.config.get('ui',{}).get('port',8080)}"
            self.tray_manager = TrayIconManager(ui_url=uu, on_exit=self.shutdown, on_show=self._show_ui, status_callback=self._get_status)
            return self.tray_manager.start()
        except Exception as e: self._log("WARN", f"托盘启动失败: {e}"); return False
    def _show_ui(self): webbrowser.open(f"http://{self.config.get('ui',{}).get('host','127.0.0.1')}:{self.config.get('ui',{}).get('port',8080)}")
    def _handle_control(self, action):
        if action=="start":
            if self.running: return {"success":True,"message":"服务已在运行"}
            self.config = self._load_config(); success, msg = self._start_webdav(); return {"success":success,"message":msg}
        elif action=="stop": self._stop_webdav(); return {"success":True,"message":"服务已停止"}
        elif action=="restart": self._stop_webdav(); time.sleep(1); success, msg = self._start_webdav(); return {"success":success,"message":msg}
        return {"success":False,"message":"未知命令"}
    def _get_status(self):
        s = {"running":self.running,"webdav_host":self.config.get("webdav",{}).get("host","0.0.0.0"),"webdav_port":self.config.get("webdav",{}).get("port",8081),"ui_host":self.config.get("ui",{}).get("host","127.0.0.1"),"ui_port":self.config.get("ui",{}).get("port",8080),"auth_enabled":self.config.get("webdav",{}).get("auth_enabled",False),"readonly":self.config.get("webdav",{}).get("readonly",False),"reconnect_attempts":self._reconnect_attempts}
        if self.api:
            try:
                c = self.api.get_capacity()
                if c.get("success"):
                    d = c.get("data",{}); total, used = d.get("totalCapacity",0), d.get("usedCapacity",0)
                    s.update({"capacity_total":total,"capacity_used":used,"capacity_available":d.get("availableCapacity",total-used)})
            except: pass
        return s
    def _handle_log(self, entry): pass
    def start(self):
        print("="*60+"\n  ☁️ 中国移动云盘 WebDAV v1.2\n"+"="*60)
        self._start_ui(); uu = f"http://{self.config.get('ui',{}).get('host','127.0.0.1')}:{self.config.get('ui',{}).get('port',8080)}"; self._log("INFO", f"管理界面: {uu}")
        self._start_tray()
        if self.config.get("auto_open_browser", True):
            try: webbrowser.open(uu)
            except: pass
        auth = self.config.get("auth", {})
        if (auth.get("cookie") or (auth.get("phone") and auth.get("auth_token"))) and self.config.get("auto_start", False):
            success, msg = self._start_webdav()
            if success: wc = self.config.get("webdav",{}); self._log("INFO", f"WebDAV: http://{wc.get('host','0.0.0.0')}:{wc.get('port',8081)}"); wc.get("auth_enabled") and self._log("INFO", f"认证: {wc.get('username')}/******")
            else: self._log("WARN", f"自动启动失败: {msg}")
        else: self._log("INFO", "请在管理界面配置认证信息后启动服务")
        self._log("INFO", "按 Ctrl+C 退出"); print("="*60)
        def handler(sig, frame): print("\n[INFO] 退出..."); self.shutdown(); sys.exit(0)
        signal.signal(signal.SIGINT, handler)
        if hasattr(signal, 'SIGBREAK'): signal.signal(signal.SIGBREAK, handler)
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt: print("\n[INFO] 关闭中..."); self.shutdown()
    def shutdown(self):
        self._stop_webdav()
        if self.ui_manager: self.ui_manager.stop()
        if self.tray_manager: self.tray_manager.stop()
        if self._log_file: self._log("INFO", "程序退出"); self._log_file.close(); self._log_file = None
        print("[INFO] 所有服务已关闭")

def main():
    parser = argparse.ArgumentParser(description="中国移动云盘 WebDAV 服务")
    parser.add_argument("--config","-c",default="config.json",help="配置文件路径")
    parser.add_argument("--cookie",help="Cookie字符串")
    parser.add_argument("--phone",help="手机号")
    parser.add_argument("--auth-token",help="移动云盘Auth Token（从Cookie提取）")
    parser.add_argument("--host",default="0.0.0.0",help="WebDAV监听地址")
    parser.add_argument("--port",type=int,default=8081,help="WebDAV端口")
    parser.add_argument("--ui-port",type=int,default=8080,help="管理界面端口")
    parser.add_argument("--readonly",action="store_true",help="只读模式")
    parser.add_argument("--auth",action="store_true",help="启用WebDAV认证")
    parser.add_argument("--username",default="admin",help="WebDAV用户名")
    parser.add_argument("--password",default="admin",help="WebDAV密码")
    parser.add_argument("--no-browser",action="store_true",help="不自动打开浏览器")
    parser.add_argument("--no-tray",action="store_true",help="不启用系统托盘")
    parser.add_argument("--no-reconnect",action="store_true",help="禁用自动重连")
    args = parser.parse_args()
    app = CMCCCloudWebDAV(config_path=args.config)
    if args.cookie: app.config["auth"]["cookie"] = args.cookie
    if args.phone: app.config["auth"]["phone"] = args.phone
    if args.token: app.config["auth"]["auth_token"] = args.token
    if args.host: app.config["webdav"]["host"] = args.host
    if args.port: app.config["webdav"]["port"] = args.port
    if args.ui_port: app.config["ui"]["port"] = args.ui_port
    if args.readonly: app.config["webdav"]["readonly"] = True
    if args.auth: app.config["webdav"]["auth_enabled"] = True
    if args.username: app.config["webdav"]["username"] = args.username
    if args.password: app.config["webdav"]["password"] = args.password
    if args.no_browser: app.config["auto_open_browser"] = False
    if args.no_tray: app.config["minimize_to_tray"] = False
    if args.no_reconnect: app.config["auto_reconnect"] = False
    app._save_config(); app.start()

if __name__ == "__main__": main()
