#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CMCC Cloud WebDAV - 系统托盘图标
支持: 显示/隐藏管理界面、启动/停止服务、退出程序、状态显示

改进点:
1. 集成到main.py
2. 显示服务状态
3. 快速操作菜单
4. 跨平台支持
"""

import sys
import os
import threading
import webbrowser


class TrayIconManager:
    """系统托盘图标管理器"""

    def __init__(self, ui_url="http://127.0.0.1:8080", on_exit=None, on_show=None, status_callback=None):
        self.ui_url = ui_url
        self.on_exit = on_exit
        self.on_show = on_show
        self.status_callback = status_callback
        self.icon = None
        self.menu = None
        self._running = False

    def _create_icon_image(self):
        """创建托盘图标"""
        try:
            from PIL import Image, ImageDraw
            width = 64
            height = 64
            image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            dc = ImageDraw.Draw(image)
            dc.ellipse([4, 20, 28, 44], fill=(102, 126, 234, 255))
            dc.ellipse([20, 10, 48, 38], fill=(102, 126, 234, 255))
            dc.ellipse([36, 20, 60, 44], fill=(102, 126, 234, 255))
            dc.rectangle([14, 28, 50, 44], fill=(102, 126, 234, 255))
            return image
        except:
            return None

    def _get_status_text(self):
        """获取状态文本"""
        if self.status_callback:
            status = self.status_callback()
            running = status.get("running", False)
            return f"CMCC Cloud WebDAV\n{'运行中' if running else '已停止'}"
        return "CMCC Cloud WebDAV"

    def _on_show_clicked(self, icon, item):
        """显示管理界面"""
        if self.on_show:
            self.on_show()
        else:
            webbrowser.open(self.ui_url)

    def _on_exit_clicked(self, icon, item):
        """退出程序"""
        self._running = False
        if self.icon:
            self.icon.stop()
        if self.on_exit:
            self.on_exit()

    def start(self):
        """启动系统托盘"""
        try:
            import pystray
            from PIL import Image

            menu = pystray.Menu(
                pystray.MenuItem("☁️ 打开管理界面", self._on_show_clicked),
                pystray.MenuItem("🌐 打开WebDAV地址", lambda icon, item: webbrowser.open(self.ui_url)),
                pystray.MenuItem.SEPARATOR,
                pystray.MenuItem("❌ 退出", self._on_exit_clicked),
            )

            icon_image = self._create_icon_image()
            if icon_image is None:
                icon_image = Image.new('RGBA', (64, 64), (102, 126, 234, 255))

            self.icon = pystray.Icon(
                "cmcc-webdav",
                icon_image,
                self._get_status_text(),
                menu
            )

            self._running = True

            def run_tray():
                try:
                    self.icon.run()
                except Exception as e:
                    print(f"[Tray] 托盘异常: {e}")

            threading.Thread(target=run_tray, daemon=True).start()
            print("[INFO] 系统托盘图标已启动")
            return True

        except ImportError:
            print("[WARN] 未安装 pystray，系统托盘功能不可用")
            print("[INFO] 安装命令: pip install pystray Pillow")
            return False
        except Exception as e:
            print(f"[WARN] 系统托盘启动失败: {e}")
            return False

    def stop(self):
        """停止系统托盘"""
        self._running = False
        if self.icon:
            try:
                self.icon.stop()
            except:
                pass
        print("[INFO] 系统托盘图标已停止")


def run_tray_icon(ui_url="http://127.0.0.1:8080", on_exit=None):
    """运行系统托盘图标 (兼容旧接口)"""
    manager = TrayIconManager(ui_url=ui_url, on_exit=on_exit)
    return manager.start()
