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


# Magic numbers, most specific first. GIF87a and GIF89a are separate entries
# rather than a bare `GIF` prefix so that adding a format later means adding a
# row, not loosening a check that something else might also satisfy.
_MAGIC_NUMBERS: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
)


def sniff_image_mime(data: bytes, default: str = "image/png") -> str:
    """Identify an image format from its leading bytes.

    This exists because the format is not on the wire. The extension compresses
    screenshots with `canvas.toDataURL('image/jpeg', 0.8)` and then strips the
    data-URL prefix before POSTing, so the backend receives bare base64 with no
    record of what it was. There is no declared type left to trust, which is why
    this reads the bytes instead of parsing a header.

    Resume uploads go the other way — `capture.ts` uses `toDataURL('image/png')`
    — so a hardcoded `image/png` was accidentally correct for those and wrong
    for every scan. That is the shape of the bug: one label serving two sources
    that disagree, with the wrong one being the product's main path.

    `default` covers bytes matching nothing, which preserves the previous
    behaviour rather than introducing a rejection. Refusing unidentifiable bytes
    would be a stricter contract and arguably better — it would turn a provider
    400 into a clear client error instead of a spent call — but it is a
    behaviour change, and nothing here establishes that every format missed by
    this table is genuinely unusable.
    """
    # WEBP is a RIFF container, so the type sits at a fixed offset rather than
    # at the start, and `RIFF` on its own is also what WAV and AVI begin with.
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    for magic, mime in _MAGIC_NUMBERS:
        if data.startswith(magic):
            return mime
    return default
