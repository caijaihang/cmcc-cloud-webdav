#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统托盘图标支持 (Windows)
提供最小化到托盘、右键菜单等功能
"""

import os
import sys
import threading
import webbrowser

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    print("[WARN] 未安装 pystray/Pillow，系统托盘功能不可用")


def create_icon_image():
    """生成托盘图标"""
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    # 绘制云盘图标 (蓝色圆形+白色云)
    dc.ellipse([4, 4, 60, 60], fill=(102, 126, 234, 255))
    dc.ellipse([16, 24, 48, 44], fill=(255, 255, 255, 255))
    dc.ellipse([20, 20, 36, 36], fill=(255, 255, 255, 255))
    dc.ellipse([28, 20, 44, 36], fill=(255, 255, 255, 255))
    return image


class TrayIconManager:
    """托盘图标管理器"""
    
    def __init__(self, ui_url="http://127.0.0.1:8080", on_exit=None, on_show=None):
        self.ui_url = ui_url
        self.on_exit = on_exit
        self.on_show = on_show
        self.icon = None
        self._running = False
        
    def _create_menu(self):
        """创建右键菜单"""
        return pystray.Menu(
            pystray.MenuItem("打开管理界面", self._show_ui),
            pystray.MenuItem("---", None),
            pystray.MenuItem("退出", self._exit_app),
        )
        
    def _show_ui(self):
        """打开管理界面"""
        webbrowser.open(self.ui_url)
        if self.on_show:
            self.on_show()
            
    def _exit_app(self):
        """退出程序"""
        if self.icon:
            self.icon.stop()
        if self.on_exit:
            self.on_exit()
            
    def start(self):
        """启动托盘图标"""
        if not HAS_TRAY:
            return False
        try:
            self.icon = pystray.Icon(
                "cmcc-cloud-webdav",
                create_icon_image(),
                "CMCC Cloud WebDAV",
                self._create_menu()
            )
            self._running = True
            # 在单独线程中运行托盘图标
            t = threading.Thread(target=self.icon.run, daemon=True)
            t.start()
            return True
        except Exception as e:
            print(f"[ERROR] 托盘图标启动失败: {e}")
            return False
            
    def stop(self):
        """停止托盘图标"""
        if self.icon:
            self.icon.stop()
        self._running = False


def setup_tray(ui_url="http://127.0.0.1:8080", on_exit=None):
    """便捷函数: 设置并启动托盘"""
    manager = TrayIconManager(ui_url=ui_url, on_exit=on_exit)
    manager.start()
    return manager
