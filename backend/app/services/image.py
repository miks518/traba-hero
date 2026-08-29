import base64
import re


def decode_base64_image(data: str) -> bytes:
    if data.startswith("data:image"):
        data = data.split(",", 1)[1]
    data = re.sub(r"\s+", "", data)
    try:
        return base64.b64decode(data)
    except Exception:
        raise ValueError("Invalid base64 image data")
