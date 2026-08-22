#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包脚本 - 支持: Windows/Linux/macOS/Android. 单文件/单目录/UPX压缩"""
import os, sys, shutil, subprocess, argparse

def check_pyinstaller():
    try: import PyInstaller; return True
    except ImportError: return False

def install_pyinstaller():
    print("[INFO] 安装 PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def clean_build():
    for d in ["build", "dist", "__pycache__"]:
        if os.path.exists(d): print(f"[INFO] 清理 {d}/"); shutil.rmtree(d)
    for f in os.listdir("."):
        if f.endswith(".spec"): print(f"[INFO] 清理 {f}"); os.remove(f)

def build(onefile=False, upx=False):
    if not check_pyinstaller(): install_pyinstaller()
    clean_build(); print("[INFO] 开始打包...")
    cmd = [sys.executable, "-m", "PyInstaller", "--name", "cmcc-webdav", "--noconfirm", "--clean"]
    if onefile: cmd.append("--onefile")
    else: cmd.append("--onedir")
    if upx: cmd.append("--upx-dir=upx")
    hidden = ["wsgidav","wsgidav.dav_provider","wsgidav.wsgidav_app","wsgidav.dir_browser","wsgidav.property_manager","wsgidav.lock_manager","cheroot.wsgi","requests","PIL","PIL.Image","PIL.ImageDraw","pystray"]
    for h in hidden: cmd.extend(["--hidden-import", h])
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    if os.path.exists(static_dir): cmd.extend(["--add-data", f"{static_dir}{os.pathsep}static"])
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(icon_path): cmd.extend(["--icon", icon_path])
    cmd.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py"))
    try:
        subprocess.check_call(cmd)
        print("\n" + "="*60 + "\n  ✅ 打包成功!\n" + "="*60)
        if onefile: print(f"  输出: dist/cmcc-webdav{'.exe' if sys.platform=='win32' else ''}")
        else: print(f"  输出目录: dist/cmcc-webdav/")
        print("="*60)
    except subprocess.CalledProcessError as e: print(f"\n[ERROR] 打包失败: {e}"); sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="打包 CMCC Cloud WebDAV")
    parser.add_argument("--onefile", action="store_true", help="单文件模式")
    parser.add_argument("--upx", action="store_true", help="UPX压缩")
    parser.add_argument("--clean", action="store_true", help="仅清理")
    args = parser.parse_args()
    if args.clean: clean_build(); print("[INFO] 清理完成"); return
    build(onefile=args.onefile, upx=args.upx)

if __name__ == "__main__": main()
