#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包脚本 - 将项目打包为单文件可执行程序
支持: Windows (.exe) / Linux / macOS
支持: 单文件模式 / 单目录模式 / UPX压缩

用法:
    python build.py
    python build.py --onefile      # 单文件模式
    python build.py --onedir       # 单目录模式 (默认)
    python build.py --upx          # 启用UPX压缩
    python build.py --clean        # 仅清理构建目录
"""

import os
import sys
import shutil
import subprocess
import argparse


def check_pyinstaller():
    """检查 PyInstaller 是否安装"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """安装 PyInstaller"""
    print("[INFO] 正在安装 PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean_build():
    """清理构建目录"""
    dirs_to_remove = ["build", "dist", "__pycache__"]
    for d in dirs_to_remove:
        if os.path.exists(d):
            print(f"[INFO] 清理 {d}/")
            shutil.rmtree(d)
    for f in os.listdir("."):
        if f.endswith(".spec"):
            print(f"[INFO] 清理 {f}")
            os.remove(f)


def build(onefile=False, upx=False):
    """执行打包"""
    if not check_pyinstaller():
        install_pyinstaller()

    clean_build()
    print("[INFO] 开始打包...")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "cmcc-webdav",
        "--noconfirm",
        "--clean",
    ]

    if onefile:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    if upx:
        cmd.append("--upx-dir=upx")

    # 隐藏导入（与 GitHub Actions 保持一致）
    hidden_imports = [
        "wsgidav",
        "wsgidav.dav_provider",
        "wsgidav.wsgidav_app",
        "wsgidav.dir_browser",
        "wsgidav.property_manager",
        "wsgidav.lock_manager",
        "cheroot.wsgi",
        "requests",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "pystray",
    ]
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # 数据文件
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    if os.path.exists(static_dir):
        cmd.extend(["--add-data", f"{static_dir}{os.pathsep}static"])

    # 图标
    icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.ico")
    if os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])

    # 主入口
    main_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    cmd.append(main_path)

    try:
        subprocess.check_call(cmd)
        print("\n" + "=" * 60)
        print("  ✅ 打包成功!")
        print("=" * 60)
        if onefile:
            print(f"  输出文件: dist/cmcc-webdav{'.exe' if sys.platform == 'win32' else ''}")
        else:
            print(f"  输出目录: dist/cmcc-webdav/")
            print(f"  可执行文件: dist/cmcc-webdav/cmcc-webdav{'.exe' if sys.platform == 'win32' else ''}")
        print("=" * 60)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] 打包失败: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="打包 CMCC Cloud WebDAV")
    parser.add_argument("--onefile", action="store_true", help="打包为单文件")
    parser.add_argument("--upx", action="store_true", help="启用UPX压缩")
    parser.add_argument("--clean", action="store_true", help="仅清理构建目录")
    args = parser.parse_args()

    if args.clean:
        clean_build()
        print("[INFO] 清理完成")
        return

    build(onefile=args.onefile, upx=args.upx)


if __name__ == "__main__":
    main()
