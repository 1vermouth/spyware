import os
import base64
from Crypto.Cipher import AES

AES_KEY_B64 = os.getenv("AES_KEY")
AES_KEY = base64.b64decode(AES_KEY_B64)

def encrypt_bytes(data):
    nonce      = os.urandom(12)
    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
    text, tag = cipher.encrypt_and_digest(data)
    return nonce + tag + text

def decrypt_bytes(encrypted):
    nonce      = encrypted[:12]
    tag = encrypted[12:28]
    text = encrypted[28:]
    cipher = AES.new(AES_KEY, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(text, tag)