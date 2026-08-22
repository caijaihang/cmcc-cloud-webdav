#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标准日志模块 - 支持控制台+文件双输出、日志轮转、级别过滤
用法: from logger import get_logger; log = get_logger('cmcc'); log.info('msg')"""
import os, logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_FMT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

def get_logger(name: str = "cmcc", level: str = "INFO", log_to_file: bool = True) -> logging.Logger:
    """获取配置好的日志器"""
    logger = logging.getLogger(name)
    if logger.handlers: return logger
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    # 控制台处理器
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
    logger.addHandler(console)
    # 文件处理器（轮转，单个10MB，保留5个备份）
    if log_to_file:
        file_path = os.path.join(LOG_DIR, f"{name}.log")
        file_handler = RotatingFileHandler(file_path, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(_FMT, _DATE_FMT))
        logger.addHandler(file_handler)
    return logger
