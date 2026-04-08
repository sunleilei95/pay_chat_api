import hashlib
import base64

def generate_unique_nickname(phone: str) -> str:
    h = hashlib.sha256(phone.encode()).digest()
    short = base64.b64encode(h)[:4].decode()  # 取 4 个字符
    safe = short.replace("+","").replace("/","").replace("=","")
    while len(safe) <4:
        safe += "0"
    return safe