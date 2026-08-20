#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMCC Cloud WebDAV - 主程序入口
将中国移动云盘映射为本地WebDAV磁盘
支持: 列表/上传/下载/删除/重命名/创建文件夹/移动/复制
"""

import os
import sys
import json
import time
import threading
import argparse

# 确保当前目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cmcc_api import CMCCCloudAPI, create_api_from_cookie, create_api_from_creds
from webdav_provider import CMCCCloudProvider
from web_ui import WebUIManager

try:
    from wsgidav.wsgidav_app import WsgiDAVApp
    from wsgidav.dav_provider import DAVProvider
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
        self.running = False
        
    def _load_config(self):
        """加载配置"""
        default = {
            "webdav": {"host": "0.0.0.0", "port": 8081, "mount_path": "Z:", "readonly": False},
            "auth": {"cookie": "", "phone": "", "auth_token": ""},
            "ui": {"host": "127.0.0.1", "port": 8080},
            "auto_start": False,
            "minimize_to_tray": True
        }
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 合并默认值
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
            print("[INFO] 使用Cookie认证")
        elif phone and token:
            self.api = create_api_from_creds(phone, token)
            print(f"[INFO] 使用手机号+Token认证: {phone}")
        else:
            print("[ERROR] 未配置认证信息，请在管理界面配置")
            return False
            
        # 测试连接
        user_info = self.api.get_user_info()
        if user_info.get("success"):
            print("[INFO] 云盘连接成功")
            return True
        else:
            print(f"[ERROR] 云盘连接失败: {user_info.get('message', '未知错误')}")
            return False
            
    def _start_webdav(self):
        """启动WebDAV服务"""
        if not self.api:
            if not self._init_api():
                return False
                
        webdav_cfg = self.config.get("webdav", {})
        host = webdav_cfg.get("host", "0.0.0.0")
        port = webdav_cfg.get("port", 8081)
        readonly = webdav_cfg.get("readonly", False)
        
        # 创建提供者
        provider = CMCCCloudProvider(self.api)
        
        # WsgiDAV配置
        dav_config = {
            "host": host,
            "port": port,
            "provider_mapping": {"/": provider},
            "verbose": 1,
            "logging": {"enable": True, "enable_loggers": []},
            "property_manager": True,
            "lock_manager": True,
            "acceptbasic": True,
            "acceptdigest": False,
            "defaultdigest": False,
            "trusted_auth_header": False,
        }
        
        try:
            self.dav_app = WsgiDAVApp(dav_config)
            
            # 使用cheroot作为WSGI服务器
            from cheroot.wsgi import Server as WSGIServer
            self.dav_server = WSGIServer((host, port), self.dav_app)
            
            def run_dav():
                try:
                    print(f"[INFO] WebDAV服务已启动: http://{host}:{port}")
                    self.dav_server.start()
                except Exception as e:
                    print(f"[ERROR] WebDAV服务异常: {e}")
                    
            t = threading.Thread(target=run_dav, daemon=True)
            t.start()
            self.running = True
            return True
            
        except Exception as e:
            print(f"[ERROR] 启动WebDAV失败: {e}")
            return False
            
    def _stop_webdav(self):
        """停止WebDAV服务"""
        if self.dav_server:
            try:
                self.dav_server.stop()
            except:
                pass
        self.dav_server = None
        self.dav_app = None
        self.running = False
        print("[INFO] WebDAV服务已停止")
        
    def _start_ui(self):
        """启动管理界面"""
        ui_cfg = self.config.get("ui", {})
        host = ui_cfg.get("host", "127.0.0.1")
        port = ui_cfg.get("port", 8080)
        
        self.ui_manager = WebUIManager(
            host=host, port=port,
            config_path=self.config_path,
            control_callback=self._handle_control
        )
        self.ui_manager.start()
        return True
        
    def _handle_control(self, action):
        """处理UI控制命令"""
        if action == "start":
            if self.running:
                return {"success": True, "message": "服务已在运行"}
            success = self._start_webdav()
            return {"success": success, "message": "服务已启动" if success else "启动失败"}
        elif action == "stop":
            self._stop_webdav()
            return {"success": True, "message": "服务已停止"}
        elif action == "restart":
            self._stop_webdav()
            time.sleep(1)
            success = self._start_webdav()
            return {"success": success, "message": "服务已重启" if success else "重启失败"}
        return {"success": False, "message": "未知命令"}
        
    def start(self):
        """启动所有服务"""
        print("=" * 60)
        print("  ☁️ 中国移动云盘 WebDAV 服务")
        print("=" * 60)
        
        # 启动管理界面
        self._start_ui()
        ui_cfg = self.config.get("ui", {})
        print(f"[INFO] 管理界面: http://{ui_cfg.get('host','127.0.0.1')}:{ui_cfg.get('port',8080)}")
        
        # 如果配置了认证且设置了自动启动，则启动WebDAV
        auth = self.config.get("auth", {})
        if (auth.get("cookie") or (auth.get("phone") and auth.get("auth_token"))) \
           and self.config.get("auto_start", False):
            self._start_webdav()
            webdav_cfg = self.config.get("webdav", {})
            print(f"[INFO] WebDAV地址: http://{webdav_cfg.get('host','0.0.0.0')}:{webdav_cfg.get('port',8081)}")
        else:
            print("[INFO] 请在管理界面配置认证信息后启动WebDAV服务")
            
        print("[INFO] 按 Ctrl+C 退出程序")
        print("=" * 60)
        
        # 保持主线程运行
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
    args = parser.parse_args()
    
    app = CMCCCloudWebDAV(config_path=args.config)
    
    # 命令行参数覆盖配置
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
        
    app._save_config()
    app.start()


if __name__ == "__main__":
    main()
