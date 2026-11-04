"""Package the built chrome-mv3 folder as the release asset.

The landing page links to

    https://github.com/miks518/traba-hero/releases/latest/download/traba-hero-extension.zip

so the asset name has to stay exactly ``traba-hero-extension.zip`` across every
release. This script produces it from the build output, with ``manifest.json`` at
the root of the archive so that unzipping gives a folder Chrome can load as
unpacked.

Build first, with the self-distribution manifest:

    WXT_SELF_DISTRIBUTE=true WXT_API_BASE=https://... npm run build

then:

    python3 scripts/pack_release.py
"""

import json
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / ".output" / "chrome-mv3"
ASSET = ROOT / "traba-hero-extension.zip"

# A fixed timestamp keeps the archive byte-identical when nothing changed, so a
# rebuild without new commits does not churn the release asset's digest.
EPOCH = (2026, 1, 1, 0, 0, 0)


def main() -> int:
    manifest_path = SRC / "manifest.json"
    if not manifest_path.is_file():
        print(f"error: {manifest_path} not found - run the build first", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if "key" not in manifest:
        print(
            "error: the manifest has no key. Rebuild with WXT_SELF_DISTRIBUTE=true, "
            "otherwise the extension ID changes and the backend's CORS allowlist rejects it.",
            file=sys.stderr,
        )
        return 1

    files = sorted(p for p in SRC.rglob("*") if p.is_file())
    if not files:
        print(f"error: {SRC} is empty", file=sys.stderr)
        return 1

    with zipfile.ZipFile(ASSET, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            rel = path.relative_to(SRC).as_posix()
            info = zipfile.ZipInfo(rel, date_time=EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())

    print(f"asset        : {ASSET.name}")
    print(f"version      : {manifest['version']}")
    print(f"files        : {len(files)}")
    print(f"size         : {ASSET.stat().st_size / 1024:.1f} KB")
    print(f"key pinned   : {manifest['key'][:24]}...")
    print(f"host_perms   : {manifest.get('host_permissions')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
