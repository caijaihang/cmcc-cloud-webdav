#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMCC Cloud WebDAV Web UI Manager
Provides: status monitor / config management / log viewer / manual control
"""

import os
import json
import time
import threading
from datetime import datetime

try:
    from cheroot.wsgi import Server as WSGIServer
except ImportError:
    from wsgidav.server.cheroot import CherootServer as WSGIServer


class WebUIManager:
    def __init__(self, host="127.0.0.1", port=8080, config_path="config.json",
                 log_callback=None, control_callback=None):
        self.host = host
        self.port = port
        self.config_path = config_path
        self.log_callback = log_callback
        self.control_callback = control_callback
        self.server = None
        self.running = False
        self._logs = []
        self._max_logs = 500

    def _load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return self._default_config()

    def _default_config(self):
        return {
            "webdav": {"host": "0.0.0.0", "port": 8081, "mount_path": "Z:", "readonly": False},
            "auth": {"cookie": "", "phone": "", "auth_token": ""},
            "ui": {"host": "127.0.0.1", "port": 8080},
            "auto_start": False, "minimize_to_tray": True
        }

    def _save_config(self, config):
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

    def add_log(self, level, message):
        entry = {"time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "level": level, "message": message}
        self._logs.append(entry)
        if len(self._logs) > self._max_logs:
            self._logs = self._logs[-self._max_logs:]
        if self.log_callback:
            self.log_callback(entry)

    def _html_page(self, content, title="CMCC Cloud WebDAV"):
        css = """
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Microsoft YaHei", sans-serif; background: #f0f2f5; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;
                  padding: 30px; border-radius: 12px; margin-bottom: 20px; }
        .header h1 { font-size: 28px; margin-bottom: 8px; }
        .card { background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
        .card h2 { font-size: 18px; margin-bottom: 16px; color: #444;
                   border-left: 4px solid #667eea; padding-left: 12px; }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
        .status-item { background: #f8f9fa; padding: 16px; border-radius: 8px; text-align: center; }
        .status-item .label { font-size: 12px; color: #888; margin-bottom: 6px; }
        .status-item .value { font-size: 20px; font-weight: bold; color: #667eea; }
        .btn { display: inline-block; padding: 10px 24px; border: none; border-radius: 6px;
               cursor: pointer; font-size: 14px; text-decoration: none; margin-right: 8px; }
        .btn-primary { background: #667eea; color: white; }
        .btn-success { background: #52c41a; color: white; }
        .btn-danger { background: #ff4d4f; color: white; }
        .form-group { margin-bottom: 16px; }
        .form-group label { display: block; margin-bottom: 6px; font-size: 13px; color: #666; }
        .form-group input, .form-group textarea { width: 100%; padding: 10px 12px;
            border: 1px solid #d9d9d9; border-radius: 6px; font-size: 14px; }
        .form-group textarea { min-height: 80px; resize: vertical; font-family: monospace; }
        .log-container { max-height: 400px; overflow-y: auto; background: #1e1e1e;
                         border-radius: 8px; padding: 12px; font-family: monospace; font-size: 12px; }
        .log-entry { padding: 3px 0; color: #d4d4d4; border-bottom: 1px solid #333; }
        .nav { display: flex; gap: 8px; margin-bottom: 20px; }
        .nav a { padding: 10px 20px; background: white; border-radius: 6px;
                 color: #666; text-decoration: none; font-size: 14px; }
        .nav a:hover, .nav a.active { background: #667eea; color: white; }
        .alert { padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; }
        .alert-success { background: #f6ffed; border: 1px solid #b7eb8f; color: #52c41a; }
        .alert-error { background: #fff2f0; border: 1px solid #ffccc7; color: #ff4d4f; }
        .footer { text-align: center; padding: 20px; color: #999; font-size: 12px; }
        """
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title><style>{css}</style></head>
<body><div class="container">
<div class="header"><h1>☁️ 中国移动云盘 WebDAV</h1>
<p>将移动云盘映射为本地磁盘 | 支持读写操作 | 便携单文件运行</p></div>
{content}
<div class="footer"><p>CMCC Cloud WebDAV v1.0 | 基于抓包API实现 | 仅供个人学习使用</p></div>
</div></body></html>"""

    def _wsgi_app(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")
        if path == "/" or path == "/index":
            return self._handle_index(environ, start_response)
        elif path == "/config":
            return self._handle_config(environ, start_response)
        elif path == "/logs":
            return self._handle_logs(environ, start_response)
        elif path == "/api/status":
            return self._api_status(environ, start_response)
        elif path == "/api/control":
            return self._api_control(environ, start_response)
        elif path == "/api/set_cookie":
            return self._api_set_cookie(environ, start_response)
        elif path == "/api/bookmark":
            return self._api_bookmark(environ, start_response)
        else:
            start_response("404 Not Found", [("Content-Type", "text/plain")])
            return [b"Not Found"]

    def _handle_index(self, environ, start_response):
        config = self._load_config()
        status_html = f"""
<div class="nav">
<a href="/" class="active">📊 状态面板</a>
<a href="/config">⚙️ 配置管理</a>
<a href="/logs">📝 日志查看</a>
</div>
<div class="card">
<h2>服务状态</h2>
<div class="status-grid">
<div class="status-item"><div class="label">WebDAV服务</div><div class="value">运行中</div></div>
<div class="status-item"><div class="label">监听地址</div><div class="value">{config["webdav"]["host"]}:{config["webdav"]["port"]}</div></div>
<div class="status-item"><div class="label">挂载路径</div><div class="value">{config["webdav"]["mount_path"]}</div></div>
<div class="status-item"><div class="label">写入模式</div><div class="value">{"只读" if config["webdav"]["readonly"] else "读写"}</div></div>
</div>
<div style="margin-top: 20px;">
<a href="/api/control?action=restart" class="btn btn-primary">🔄 重启服务</a>
<a href="/api/control?action=stop" class="btn btn-danger">⏹ 停止服务</a>
<a href="/api/control?action=start" class="btn btn-success">▶ 启动服务</a>
</div>
</div>
<div class="card">
<h2>使用说明</h2>
<p style="line-height: 1.8; color: #666;">
1. <b>获取Cookie</b>：登录 yun.139.com，按F12打开开发者工具，复制Cookie。<br>
2. <b>配置认证</b>：进入"配置管理"页面，粘贴Cookie。<br>
3. <b>启动服务</b>：点击"启动服务"，WebDAV服务器将在指定端口运行。<br>
4. <b>挂载磁盘</b>：在Windows资源管理器中映射网络驱动器。<br>
5. <b>注意事项</b>：Cookie有过期时间，失效后需要重新获取。
</p>
</div>
"""
        html = self._html_page(status_html, "状态面板")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [html.encode("utf-8")]

    def _handle_config(self, environ, start_response):
        config = self._load_config()
        message = ""
        if environ.get("REQUEST_METHOD") == "POST":
            try:
                cl = int(environ.get("CONTENT_LENGTH", 0))
                body = environ["wsgi.input"].read(cl).decode("utf-8")
                params = self._parse_form(body)
                config["auth"]["cookie"] = params.get("cookie", "")
                config["auth"]["phone"] = params.get("phone", "")
                config["auth"]["auth_token"] = params.get("auth_token", "")
                config["webdav"]["host"] = params.get("dav_host", "0.0.0.0")
                config["webdav"]["port"] = int(params.get("dav_port", "8081"))
                config["webdav"]["mount_path"] = params.get("mount_path", "Z:")
                config["webdav"]["readonly"] = params.get("readonly") == "on"
                config["auto_start"] = params.get("auto_start") == "on"
                config["minimize_to_tray"] = params.get("minimize_to_tray") == "on"
                self._save_config(config)
                message = '<div class="alert alert-success">✅ 配置已保存！</div>'
                self.add_log("info", "配置已更新")
            except Exception as e:
                message = f'<div class="alert alert-error">❌ 保存失败: {e}</div>'
                self.add_log("error", f"配置保存失败: {e}")

        config_html = f"""
<div class="nav">
<a href="/">📊 状态面板</a>
<a href="/config" class="active">⚙️ 配置管理</a>
<a href="/logs">📝 日志查看</a>
</div>
{message}
<div class="card">
<h2>认证配置</h2>
<div style="background:#f0f5ff;border:1px solid #667eea;border-radius:8px;padding:16px;margin-bottom:16px;">
<p style="margin:0 0 12px 0;color:#333;"><b>🚀 懒人模式：</b>无需手动复制Cookie，一键自动获取</p>
<a href="/api/bookmark" class="btn btn-primary" target="_blank">🚀 自动获取 Cookie（书签脚本）</a>
</div>
<form method="POST" action="/config">
<div class="form-group">
<label>Cookie字符串 (推荐，直接从浏览器复制)</label>
<textarea name="cookie" placeholder="从浏览器开发者工具中复制完整的Cookie字符串...">{config["auth"]["cookie"]}</textarea>
</div>
<div style="text-align:center;color:#999;margin:16px 0;">— 或 —</div>
<div class="form-group">
<label>手机号</label>
<input type="text" name="phone" placeholder="13800138000" value="{config["auth"]["phone"]}">
</div>
<div class="form-group">
<label>Auth Token</label>
<input type="text" name="auth_token" placeholder="从Cookie中提取的auth_token" value="{config["auth"]["auth_token"]}">
</div>
</div>
<div class="card">
<h2>WebDAV配置</h2>
<div class="form-group">
<label>监听地址</label>
<input type="text" name="dav_host" value="{config["webdav"]["host"]}">
</div>
<div class="form-group">
<label>监听端口</label>
<input type="number" name="dav_port" value="{config["webdav"]["port"]}">
</div>
<div class="form-group">
<label>挂载盘符</label>
<input type="text" name="mount_path" value="{config["webdav"]["mount_path"]}">
</div>
<div class="form-group">
<label><input type="checkbox" name="readonly" {"checked" if config["webdav"]["readonly"] else ""}> 只读模式</label>
</div>
</div>
<div class="card">
<h2>高级选项</h2>
<div class="form-group">
<label><input type="checkbox" name="auto_start" {"checked" if config["auto_start"] else ""}> 开机自动启动</label>
</div>
<div class="form-group">
<label><input type="checkbox" name="minimize_to_tray" {"checked" if config["minimize_to_tray"] else ""}> 最小化到系统托盘</label>
</div>
<div style="text-align:center;margin-top:20px;">
<button type="submit" class="btn btn-primary">💾 保存配置</button>
</div>
</form>
</div>
"""
        html = self._html_page(config_html, "配置管理")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [html.encode("utf-8")]

    def _handle_logs(self, environ, start_response):
        logs_html = "\n".join([
            f'<div class="log-entry"><span style="color:#858585">{l["time"]}</span> '
            f'<span style="color:{"#4ec9b0" if l["level"]=="info" else "#f44747"}">[{l["level"].upper()}]</span> {l["message"]}</div>'
            for l in reversed(self._logs[-200:])
        ])
        content = f"""
<div class="nav">
<a href="/">📊 状态面板</a>
<a href="/config">⚙️ 配置管理</a>
<a href="/logs" class="active">📝 日志查看</a>
</div>
<div class="card">
<h2>运行日志 (最近200条)</h2>
<div class="log-container">
{logs_html if self._logs else '<div style="color:#666;text-align:center;padding:20px;">暂无日志</div>'}
</div>
<div style="margin-top:12px;">
<a href="/logs" class="btn btn-primary">🔄 刷新</a>
<a href="/api/control?action=clear_logs" class="btn btn-danger">🗑 清空日志</a>
</div>
</div>
"""
        html = self._html_page(content, "日志查看")
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [html.encode("utf-8")]

    def _api_status(self, environ, start_response):
        status = {"running": self.running, "time": datetime.now().isoformat(), "logs_count": len(self._logs)}
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps(status).encode()]

    def _api_control(self, environ, start_response):
        query = environ.get("QUERY_STRING", "")
        action = None
        for param in query.split("&"):
            if param.startswith("action="):
                action = param.split("=")[1]
                break
        result = {"success": False, "message": "未知命令"}
        if action in ("start", "stop", "restart") and self.control_callback:
            result = self.control_callback(action)
        elif action == "clear_logs":
            self._logs = []
            result = {"success": True, "message": "日志已清空"}
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps(result).encode()]

    def _api_set_cookie(self, environ, start_response):
        """接收浏览器书签脚本发送的Cookie"""
        result = {"success": False, "message": "请求方式错误"}
        if environ.get("REQUEST_METHOD") == "POST":
            try:
                cl = int(environ.get("CONTENT_LENGTH", 0))
                body = environ["wsgi.input"].read(cl).decode("utf-8")
                data = json.loads(body)
                cookie = data.get("cookie", "")
                if cookie:
                    config = self._load_config()
                    config["auth"]["cookie"] = cookie
                    self._save_config(config)
                    result = {"success": True, "message": "Cookie已自动保存"}
                    self.add_log("info", "通过书签脚本自动获取Cookie成功")
                else:
                    result = {"success": False, "message": "Cookie为空"}
            except Exception as e:
                result = {"success": False, "message": str(e)}
        start_response("200 OK", [("Content-Type", "application/json")])
        return [json.dumps(result).encode()]

    def _api_bookmark(self, environ, start_response):
        """返回书签脚本获取页面"""
        port = self.port
        script = f"""javascript:(function(){{var c=document.cookie;if(!c){{alert('当前页面没有Cookie，请先登录yun.139.com');return;}}fetch('http://127.0.0.1:{port}/api/set_cookie',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{cookie:c}})}}).then(r=>r.json()).then(d=>{{if(d.success){{alert('Cookie自动获取成功！请返回管理界面点击启动服务。');}}else{{alert('失败:'+d.message);}}}}).catch(e=>{{alert('发送失败，请检查本地服务是否运行:'+e);}});}})();"""
        html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>自动获取Cookie</title>
<style>body{{font-family:sans-serif;max-width:800px;margin:40px auto;padding:20px;background:#f0f2f5;}}
.card{{background:white;border-radius:12px;padding:24px;box-shadow:0 2px 8px rgba(0,0,0,0.06);margin-bottom:20px;}}
h1{{color:#667eea;}}.btn{{display:inline-block;padding:12px 24px;background:#667eea;color:white;border-radius:6px;text-decoration:none;cursor:pointer;border:none;font-size:14px;}}
.code{{background:#1e1e1e;color:#d4d4d4;padding:16px;border-radius:8px;font-family:monospace;font-size:12px;word-break:break-all;}}
.step{{margin:16px 0;padding:16px;background:#f8f9fa;border-radius:8px;border-left:4px solid #667eea;}}
</style></head><body>
<div class="card"><h1>🚀 自动获取 Cookie（书签脚本）</h1>
<p>无需手动复制粘贴，一键自动同步 yun.139.com 的 Cookie。</p></div>
<div class="card"><h2>使用步骤</h2>
<div class="step"><b>步骤1：</b> 用 <b>Chrome/Edge</b> 登录 <a href="https://yun.139.com" target="_blank">yun.139.com</a></div>
<div class="step"><b>步骤2：</b> 把下面的按钮拖到浏览器<b>书签栏</b>（或右键收藏）</div>
<div style="text-align:center;margin:20px 0;"><a href="{script}" class="btn">📥 获取移动云盘Cookie</a></div>
<div class="step"><b>步骤3：</b> 保持登录状态，点击刚才保存的书签</div>
<div class="step"><b>步骤4：</b> 看到 "Cookie自动获取成功" 提示后，返回 <a href="/config">配置管理</a> 点击启动服务</div>
</div>
<div class="card"><h2>脚本源码（备用）</h2>
<p>如果拖拽无效，可以复制下面代码，在 yun.139.com 页面按 F12 → Console 粘贴执行：</p>
<div class="code">{script.replace('javascript:', '')}</div>
</div>
<div style="text-align:center;"><a href="/config" class="btn">返回配置管理</a></div>
</body></html>"""
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [html.encode("utf-8")]

    def _parse_form(self, body):
        result = {}
        for item in body.split("&"):
            if "=" in item:
                k, v = item.split("=", 1)
                result[k] = v.replace("+", " ")
        return result

    def start(self):
        if self.running:
            return
        self.running = True
        self.server = WSGIServer((self.host, self.port), self._wsgi_app)
        self.add_log("info", f"管理界面已启动: http://{self.host}:{self.port}")
        def run():
            try:
                self.server.start()
            except Exception as e:
                self.add_log("error", f"管理界面异常: {e}")
            finally:
                self.running = False
        threading.Thread(target=run, daemon=True).start()

    def stop(self):
        if self.server:
            self.server.stop()
        self.running = False
        self.add_log("info", "管理界面已停止")
