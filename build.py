#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PyInstaller 打包脚本
将项目打包为单个EXE文件 (Windows)
"""

import os
import sys
import subprocess
import shutil

# 项目根目录
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
SPEC_DIR = os.path.join(PROJECT_DIR, "spec")


def clean():
    """清理旧构建文件"""
    for d in [DIST_DIR, BUILD_DIR, SPEC_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
            print(f"[CLEAN] 已删除: {d}")


def build():
    """执行打包"""
    print("=" * 60)
    print("  CMCC Cloud WebDAV - PyInstaller 打包")
    print("=" * 60)
    
    # 检查PyInstaller
    try:
        import PyInstaller
    except ImportError:
        print("[ERROR] 未安装PyInstaller，正在安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "CMCCCloudWebDAV",
        "--onefile",           # 单文件模式
        "--windowed",          # Windows下不显示控制台窗口
        "--icon", "NONE",      # 使用默认图标 (可替换为.ico文件)
        "--add-data", f"requirements.txt{os.pathsep}.",
        "--hidden-import", "cheroot.wsgi",
        "--hidden-import", "wsgidav.wsgidav_app",
        "--hidden-import", "wsgidav.dav_provider",
        "--hidden-import", "wsgidav.dir_browser",
        "--hidden-import", "requests",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "PIL.ImageDraw",
        "--hidden-import", "pystray",
        "--hidden-import", "win32api",
        "--hidden-import", "win32con",
        "--clean",             # 清理临时文件
        "--noconfirm",         # 不确认覆盖
        os.path.join(PROJECT_DIR, "main.py"),
    ]
    
    print(f"[BUILD] 执行命令: {' '.join(cmd)}")
    print("-" * 60)
    
    try:
        result = subprocess.run(cmd, cwd=PROJECT_DIR, check=True)
        print("-" * 60)
        print("[SUCCESS] 打包完成!")
        
        exe_path = os.path.join(DIST_DIR, "CMCCCloudWebDAV.exe")
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"[INFO] 输出文件: {exe_path}")
            print(f"[INFO] 文件大小: {size_mb:.1f} MB")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] 打包失败: {e}")
        return False


def build_console():
    """打包为控制台版本 (带调试输出)"""
    print("=" * 60)
    print("  CMCC Cloud WebDAV - 控制台版本打包")
    print("=" * 60)
    
    try:
        import PyInstaller
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "CMCCCloudWebDAV-console",
        "--onefile",
        "--console",           # 显示控制台窗口 (调试用)
        "--hidden-import", "cheroot.wsgi",
        "--hidden-import", "wsgidav.wsgidav_app",
        "--hidden-import", "wsgidav.dav_provider",
        "--hidden-import", "requests",
        "--hidden-import", "PIL",
        "--hidden-import", "pystray",
        "--clean",
        "--noconfirm",
        os.path.join(PROJECT_DIR, "main.py"),
    ]
    
    print(f"[BUILD] 执行命令: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=PROJECT_DIR, check=True)
        print("[SUCCESS] 控制台版本打包完成!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] 打包失败: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="打包CMCC Cloud WebDAV为EXE")
    parser.add_argument("--clean-only", action="store_true", help="仅清理")
    parser.add_argument("--console", action="store_true", help="打包控制台版本")
    args = parser.parse_args()
    
    if args.clean_only:
        clean()
        return
        
    clean()
    if args.console:
        build_console()
    else:
        build()


if __name__ == "__main__":
    main()
