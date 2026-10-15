"""A scan sends the provider an image under a label the bytes have to match.

The bug this covers was a hardcoded `data:image/png;base64,` on the scan path.
It is invisible from the extension's side — the panel receives a stream that
either starts or does not — and invisible from the provider's side too, which
answers `400 bad request` with no field naming the image. So the only place it
can be caught is here: at the boundary where the label is chosen.

Why the label cannot simply be read off the request. `imageUtils.ts` produces a
JPEG data URL and `ScamScanView.tsx:479` strips the prefix with
`screenshots.map((s) => s.split(',')[1])` before POSTing, so the backend receives
bare base64 and the format is gone. `capture.ts` produces PNG for resume
uploads and *also* has its prefix stripped, which is why one hardcoded label
served two disagreeing sources and happened to be right for the one that is
rarely sent to a vision model.

The tests below check two separate things on purpose. The sniffer is a pure
function and is cheap to pin exhaustively. The endpoint tests are the ones that
would have caught the original defect, because they read the payload that
actually goes to the provider rather than re-deriving what the code ought to
have done.
"""

import base64
import importlib
from unittest.mock import patch

import pytest
from starlette.requests import Request

from app.models.schemas import ScanRequest
from app.services.image import sniff_image_mime

# Real magic numbers, not invented ones: a JPEG that a decoder accepts begins
# with FFD8FF, and anything else here would test the table against itself.
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 16
GIF87 = b"GIF87a" + b"\x00" * 16
GIF89 = b"GIF89a" + b"\x00" * 16
BMP = b"BM" + b"\x00" * 32
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


# ── the sniffer ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    (
        (JPEG, "image/jpeg"),
        (PNG, "image/png"),
        (GIF87, "image/gif"),
        (GIF89, "image/gif"),
        (BMP, "image/bmp"),
        (WEBP, "image/webp"),
    ),
)
def test_each_format_is_identified_from_its_own_bytes(raw, expected):
    assert sniff_image_mime(raw) == expected


def test_a_jpeg_is_not_mistaken_for_a_png():
    """The specific defect, named separately from the table above so that
    deleting the JPEG row fails a test whose name says what broke."""
    assert sniff_image_mime(JPEG) == "image/jpeg"
    assert sniff_image_mime(JPEG) != sniff_image_mime(PNG)


def test_unidentifiable_bytes_keep_the_previous_default():
    """Not a new rejection. Bytes matching nothing are labelled as they were
    before this function existed, so nothing that used to be sent stops being
    sent — including, in this test suite and in one live probe, a body of base64
    that decodes to nonsense."""
    assert sniff_image_mime(b"AAAA") == "image/png"
    assert sniff_image_mime(b"") == "image/png"


def test_riff_alone_is_not_webp():
    """RIFF is a container and WAV begins with it too. Matching the container
    would label an audio file as an image."""
    assert sniff_image_mime(b"RIFF\x00\x00\x00\x00WAVEfmt ") != "image/webp"


def test_the_default_is_a_parameter_not_a_constant():
    """A caller needing a different fallback must not have to edit the table."""
    assert sniff_image_mime(b"AAAA", default="image/jpeg") == "image/jpeg"


# ── the payload that actually reaches the provider ────────────────────────────


async def _image_urls_sent(images: list[bytes]) -> list[str]:
    """Run the scan endpoint with the provider stream stubbed, and return the
    `image_url` values it built.

    Follows the pattern the rest of the suite uses to reach a rate-limited
    endpoint: `__wrapped__` drops the limiter, and `Request({"type": "http"})`
    supplies the one argument slowapi inspects.
    """
    scan_router = importlib.import_module("app.routers.scan")
    captured: dict = {}

    async def fake_stream(messages, **kwargs):
        captured["messages"] = messages
        return
        yield  # pragma: no cover - unreachable; makes this a generator

    with patch("app.routers.scan._scan_event_stream", fake_stream):
        endpoint = scan_router.scan.__wrapped__
        response = await endpoint(
            ScanRequest(images_base64=[b64(raw) for raw in images]),
            Request({"type": "http"}),
        )
        async for _ in response.body_iterator:
            pass

    # The system message's `content` is the prompt string, not a list of parts,
    # so it has to be filtered out before iterating or this walks its characters.
    return [
        part["image_url"]["url"]
        for message in captured["messages"]
        if isinstance(message.get("content"), list)
        for part in message["content"]
        if part.get("type") == "image_url"
    ]


@pytest.mark.asyncio
async def test_a_jpeg_screenshot_is_sent_to_the_provider_as_a_jpeg():
    """The test that would have caught the original bug.

    It asserts on the `image_url` the endpoint builds, not on what
    `sniff_image_mime` returns when called directly — a reimplementation of the
    same logic would satisfy the latter and still let a wrong label through.
    """
    urls = await _image_urls_sent([JPEG])

    assert len(urls) == 1
    assert urls[0].startswith("data:image/jpeg;base64,"), (
        f"a JPEG screenshot was labelled {urls[0][:32]!r}"
    )


@pytest.mark.asyncio
async def test_a_png_upload_is_still_sent_as_a_png():
    """The overcorrection. Sniffing could plausibly have been written to detect
    only JPEG and label everything else PNG, which passes the test above while
    breaking the uploads that really are PNG."""
    urls = await _image_urls_sent([PNG])

    assert urls[0].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_every_image_gets_its_own_label():
    """A loop that reused the first image's format for all of them would pass
    both single-image tests. `MAX_IMAGES_PER_SCAN` is 4, so a mixed batch is the
    realistic case."""
    urls = await _image_urls_sent([PNG, JPEG, GIF89])

    assert [u.split(";")[0] for u in urls] == [
        "data:image/png",
        "data:image/jpeg",
        "data:image/gif",
    ]
