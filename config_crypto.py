#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""配置文件加密模块 - AES-256-GCM 加密保护敏感配置"""
import os, json, base64, hashlib, getpass
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SALT_LEN, NONCE_LEN, TAG_LEN = 16, 12, 16

def _derive_key(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, 32)

def encrypt_config(data: dict, password: str = None) -> str:
    if password is None:
        password = getpass.getpass("设置配置加密密码: ")
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(password, salt)
    plaintext = json.dumps(data, ensure_ascii=False).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    blob = salt + nonce + ciphertext
    return base64.b64encode(blob).decode("ascii")

def decrypt_config(blob: str, password: str = None) -> dict:
    if password is None:
        password = getpass.getpass("输入配置解密密码: ")
    raw = base64.b64decode(blob.encode("ascii"))
    salt, nonce, ciphertext = raw[:SALT_LEN], raw[SALT_LEN:SALT_LEN+NONCE_LEN], raw[SALT_LEN+NONCE_LEN:]
    key = _derive_key(password, salt)
    plaintext = AESGCM(key).decrypt(nonce, ciphertext, None)
    return json.loads(plaintext.decode("utf-8"))

def load_config(path: str, password: str = None) -> dict:
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    if not content: return {}
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return decrypt_config(content, password)

def save_config(path: str, data: dict, encrypt: bool = False, password: str = None):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    if encrypt:
        content = encrypt_config(data, password)
    else:
        content = json.dumps(data, indent=2, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
