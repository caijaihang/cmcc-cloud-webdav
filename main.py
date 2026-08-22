#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMCC Cloud WebDAV - 主程序入口
将中国移动云盘映射为本地WebDAV磁盘

改进点:
1. WebDAV Basic Auth认证保护
2. 自动重连机制（API连接断开自动恢复）
3. 心跳检测（定期检测云盘连接状态）
4. 配置热重载
5. 集成系统托盘
6. 日志持久化
7. 信号处理
8. 命令行参数支持
"""

import os
import sys
import json
import time
import threading
import argparse
import webbrowser
import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cmcc_api import CMCCCloudAPI, create_api_from_cookie, create_api_from_creds
from webdav_provider import CMCCCloudProvider
from web_ui import WebUIManager

try:
    from wsgidav.wsgidav_app import WsgiDAVApp
except ImportError as e:
    print(f"[ERROR] 缺少依赖: {e}")
    print("请运行: pip install -r requirements.txt")
    sys.exit(1)


class CMCCCloudWebDAV:
    """主控制器"""

    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.api = None
        self.dav_app = None
        self.dav_server = None
        self.ui_manager = None
        self.tray_manager = None
        self.running = False
        self._log_file = None
        self._log_lock = threading.Lock()
        self._heartbeat_thread = None
        self._heartbeat_stop = threading.Event()
        self._reconnect_attempts = 0
        self._max_reconnect = 5
        self._init_log_file()

    def _init_log_file(self):
        """初始化日志文件"""
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"cmcc-webdav-{time.strftime('%Y%m%d')}.log")
        self._log_file = open(log_file, 'a', encoding='utf-8')
        self._log("INFO", "程序启动")

    def _log(self, level, message):
        """写入日志"""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        log_line = f"[{timestamp}] [{level}] {message}\n"
        with self._log_lock:
            if self._log_file:
                self._log_file.write(log_line)
                self._log_file.flush()
        print(log_line.strip())

    def _load_config(self):
        """加载配置"""
        default = {
            "webdav": {
                "host": "0.0.0.0", "port": 8081, "mount_path": "Z:",
                "readonly": False, "auth_enabled": False,
                "username": "admin", "password": "admin"
            },
            "auth": {"cookie": "", "phone": "", "auth_token": ""},
            "ui": {"host": "127.0.0.1", "port": 8080},
            "auto_start": False,
            "minimize_to_tray": True,
            "auto_open_browser": True,
            "log_level": "INFO",
            "heartbeat_interval": 60,
            "auto_reconnect": True
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    for k, v in default.items():
                        if k not in loaded:
                            loaded[k] = v
                        elif isinstance(v, dict):
                            for sk, sv in v.items():
                                if sk not in loaded[k]:
                                    loaded[k][sk] = sv
                    return loaded
            except Exception as e:
                print(f"[WARN] 配置文件读取失败: {e}，使用默认配置")
        return default

    def _save_config(self):
        """保存配置"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def _init_api(self):
        """初始化API客户端"""
        auth = self.config.get("auth", {})
        cookie = auth.get("cookie", "")
        phone = auth.get("phone", "")
        token = auth.get("auth_token", "")

        if cookie:
            self.api = create_api_from_cookie(cookie)
            self._log("INFO", "使用Cookie认证")
        elif phone and token:
            self.api = create_api_from_creds(phone, token)
            self._log("INFO", f"使用手机号+Token认证: {phone}")
        else:
            self._log("ERROR", "未配置认证信息")
            return False

        result = self.api.list_files()
        if result.get("success"):
            self._log("INFO", "云盘连接成功")
            self._reconnect_attempts = 0
            return True
        else:
            self._log("ERROR", f"云盘连接失败: {result.get('message', '未知错误')}")
            return False

    def _start_heartbeat(self):
        """启动心跳检测线程"""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return
        self._heartbeat_stop.clear()
        interval = self.config.get("heartbeat_interval", 60)

        def heartbeat_loop():
            while not self._heartbeat_stop.is_set():
                self._heartbeat_stop.wait(interval)
                if self._heartbeat_stop.is_set():
                    break
                if not self.running or not self.api:
                    continue
                try:
                    result = self.api.list_files(page_size=1, use_cache=False)
                    if not result.get("success"):
                        self._log("WARN", f"心跳检测失败: {result.get('message', '未知错误')}")
                        if self.config.get("auto_reconnect", True):
                            self._attempt_reconnect()
                    else:
                        self._reconnect_attempts = 0
                except Exception as e:
                    self._log("WARN", f"心跳异常: {e}")
                    if self.config.get("auto_reconnect", True):
                        self._attempt_reconnect()

        self._heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        self._log("INFO", f"心跳检测已启动（间隔{interval}秒）")

    def _stop_heartbeat(self):
        """停止心跳检测"""
        self._heartbeat_stop.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2)

    def _attempt_reconnect(self):
        """尝试自动重连"""
        if self._reconnect_attempts >= self._max_reconnect:
            self._log("ERROR", f"重连次数已达上限({self._max_reconnect})，停止重连")
            return
        self._reconnect_attempts += 1
        self._log("INFO", f"尝试重连... ({self._reconnect_attempts}/{self._max_reconnect})")
        self._stop_webdav()
        time.sleep(2)
        success, msg = self._start_webdav()
        if success:
            self._log("INFO", "重连成功")
            self._reconnect_attempts = 0
        else:
            self._log("ERROR", f"重连失败: {msg}")

    def _start_webdav(self):
        """启动WebDAV服务"""
        if not self.api:
            if not self._init_api():
                return False, "API初始化失败"

        webdav_cfg = self.config.get("webdav", {})
        host = webdav_cfg.get("host", "0.0.0.0")
        port = webdav_cfg.get("port", 8081)
        readonly = webdav_cfg.get("readonly", False)
        auth_enabled = webdav_cfg.get("auth_enabled", False)
        username = webdav_cfg.get("username", "admin")
        password = webdav_cfg.get("password", "admin")

        provider = CMCCCloudProvider(self.api)

        dav_config = {
            "host": host,
            "port": port,
            "provider_mapping": {"/": provider},
            "verbose": 1,
            "logging": {"enable": False},
            "property_manager": None,
            "lock_manager": True,
            "acceptbasic": True,
            "acceptdigest": False,
            "defaultdigest": False,
        }

        # 启用认证
        if auth_enabled:
            dav_config["simple_dc"] = {"user_mapping": {"*": {username: {"password": password}}}}

        try:
            self.dav_app = WsgiDAVApp(dav_config)
            from cheroot.wsgi import Server as WSGIServer
            self.dav_server = WSGIServer((host, port), self.dav_app)

            def run_dav():
                try:
                    self._log("INFO", f"WebDAV服务已启动: http://{host}:{port}")
                    self.dav_server.start()
                except Exception as e:
                    self._log("ERROR", f"WebDAV服务异常: {e}")

            t = threading.Thread(target=run_dav, daemon=True)
            t.start()
            self.running = True
            self._start_heartbeat()
            return True, "服务已启动"

        except Exception as e:
            err_msg = f"启动WebDAV失败: {str(e)}"
            self._log("ERROR", err_msg)
            import traceback
            traceback.print_exc()
            return False, err_msg

    def _stop_webdav(self):
        """停止WebDAV服务"""
        self._stop_heartbeat()
        if self.dav_server:
            try:
                self.dav_server.stop()
            except:
                pass
        self.dav_server = None
        self.dav_app = None
        self.running = False
        self._log("INFO", "WebDAV服务已停止")

    def _start_ui(self):
        """启动管理界面"""
        ui_cfg = self.config.get("ui", {})
        host = ui_cfg.get("host", "127.0.0.1")
        port = ui_cfg.get("port", 8080)

        self.ui_manager = WebUIManager(
            host=host, port=port,
            config_path=self.config_path,
            control_callback=self._handle_control,
            status_callback=self._get_status,
            log_callback=self._handle_log
        )
        self.ui_manager.start()
        return True

    def _start_tray(self):
        """启动系统托盘"""
        if not self.config.get("minimize_to_tray", True):
            return False
        try:
            from tray_icon import TrayIconManager
            ui_cfg = self.config.get("ui", {})
            ui_url = f"http://{ui_cfg.get('host', '127.0.0.1')}:{ui_cfg.get('port', 8080)}"

            self.tray_manager = TrayIconManager(
                ui_url=ui_url,
                on_exit=self.shutdown,
                on_show=self._show_ui,
                status_callback=self._get_status
            )
            return self.tray_manager.start()
        except Exception as e:
            self._log("WARN", f"系统托盘启动失败: {e}")
            return False

    def _show_ui(self):
        """显示管理界面"""
        ui_cfg = self.config.get("ui", {})
        ui_url = f"http://{ui_cfg.get('host', '127.0.0.1')}:{ui_cfg.get('port', 8080)}"
        webbrowser.open(ui_url)

    def _handle_control(self, action):
        """处理UI控制命令"""
        if action == "start":
            if self.running:
                return {"success": True, "message": "服务已在运行"}
            self.config = self._load_config()
            success, msg = self._start_webdav()
            return {"success": success, "message": msg}
        elif action == "stop":
            self._stop_webdav()
            return {"success": True, "message": "服务已停止"}
        elif action == "restart":
            self._stop_webdav()
            time.sleep(1)
            success, msg = self._start_webdav()
            return {"success": success, "message": msg}
        return {"success": False, "message": "未知命令"}

    def _get_status(self):
        """获取当前状态"""
        status = {
            "running": self.running,
            "webdav_host": self.config.get("webdav", {}).get("host", "0.0.0.0"),
            "webdav_port": self.config.get("webdav", {}).get("port", 8081),
            "ui_host": self.config.get("ui", {}).get("host", "127.0.0.1"),
            "ui_port": self.config.get("ui", {}).get("port", 8080),
            "auth_enabled": self.config.get("webdav", {}).get("auth_enabled", False),
            "readonly": self.config.get("webdav", {}).get("readonly", False),
            "reconnect_attempts": self._reconnect_attempts,
        }
        if self.api:
            try:
                cap = self.api.get_capacity()
                if cap.get("success"):
                    data = cap.get("data", {})
                    total = data.get("totalCapacity", 0)
                    used = data.get("usedCapacity", 0)
                    status["capacity_total"] = total
                    status["capacity_used"] = used
                    status["capacity_available"] = data.get("availableCapacity", total - used)
            except:
                pass
        return status

    def _handle_log(self, entry):
        pass

    def start(self):
        """启动所有服务"""
        print("=" * 60)
        print("  ☁️ 中国移动云盘 WebDAV 服务 v1.1")
        print("=" * 60)

        self._start_ui()
        ui_cfg = self.config.get("ui", {})
        ui_url = f"http://{ui_cfg.get('host','127.0.0.1')}:{ui_cfg.get('port',8080)}"
        self._log("INFO", f"管理界面: {ui_url}")

        self._start_tray()

        if self.config.get("auto_open_browser", True):
            try:
                webbrowser.open(ui_url)
            except:
                pass

        auth = self.config.get("auth", {})
        if (auth.get("cookie") or (auth.get("phone") and auth.get("auth_token"))) \
           and self.config.get("auto_start", False):
            success, msg = self._start_webdav()
            if success:
                webdav_cfg = self.config.get("webdav", {})
                self._log("INFO", f"WebDAV地址: http://{webdav_cfg.get('host','0.0.0.0')}:{webdav_cfg.get('port',8081)}")
                if webdav_cfg.get("auth_enabled"):
                    self._log("INFO", f"WebDAV认证: {webdav_cfg.get('username')}/******")
            else:
                self._log("WARN", f"自动启动WebDAV失败: {msg}")
        else:
            self._log("INFO", "请在管理界面配置认证信息后启动WebDAV服务")

        self._log("INFO", "按 Ctrl+C 退出程序")
        print("=" * 60)

        def signal_handler(sig, frame):
            print("\n[INFO] 收到退出信号...")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, signal_handler)

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[INFO] 正在关闭服务...")
            self.shutdown()

    def shutdown(self):
        """关闭所有服务"""
        self._stop_webdav()
        if self.ui_manager:
            self.ui_manager.stop()
        if self.tray_manager:
            self.tray_manager.stop()
        if self._log_file:
            self._log("INFO", "程序退出")
            self._log_file.close()
            self._log_file = None
        print("[INFO] 所有服务已关闭")


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(description="中国移动云盘 WebDAV 服务")
    parser.add_argument("--config", "-c", default="config.json", help="配置文件路径")
    parser.add_argument("--cookie", help="Cookie字符串 (覆盖配置文件)")
    parser.add_argument("--phone", help="手机号 (覆盖配置文件)")
    parser.add_argument("--token", help="Auth Token (覆盖配置文件)")
    parser.add_argument("--host", default="0.0.0.0", help="WebDAV监听地址")
    parser.add_argument("--port", type=int, default=8081, help="WebDAV监听端口")
    parser.add_argument("--ui-port", type=int, default=8080, help="管理界面端口")
    parser.add_argument("--readonly", action="store_true", help="只读模式")
    parser.add_argument("--auth", action="store_true", help="启用WebDAV认证")
    parser.add_argument("--username", default="admin", help="WebDAV用户名")
    parser.add_argument("--password", default="admin", help="WebDAV密码")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--no-tray", action="store_true", help="不启用系统托盘")
    parser.add_argument("--no-reconnect", action="store_true", help="禁用自动重连")
    args = parser.parse_args()

    app = CMCCCloudWebDAV(config_path=args.config)

    if args.cookie:
        app.config["auth"]["cookie"] = args.cookie
    if args.phone:
        app.config["auth"]["phone"] = args.phone
    if args.token:
        app.config["auth"]["auth_token"] = args.token
    if args.host:
        app.config["webdav"]["host"] = args.host
    if args.port:
        app.config["webdav"]["port"] = args.port
    if args.ui_port:
        app.config["ui"]["port"] = args.ui_port
    if args.readonly:
        app.config["webdav"]["readonly"] = True
    if args.auth:
        app.config["webdav"]["auth_enabled"] = True
    if args.username:
        app.config["webdav"]["username"] = args.username
    if args.password:
        app.config["webdav"]["password"] = args.password
    if args.no_browser:
        app.config["auto_open_browser"] = False
    if args.no_tray:
        app.config["minimize_to_tray"] = False
    if args.no_reconnect:
        app.config["auto_reconnect"] = False

    app._save_config()
    app.start()


if __name__ == "__main__":
    main()
