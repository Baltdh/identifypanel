#!/usr/bin/env python3
"""Download every DTBO asset published by the pinned ROCKNIX panel_overlays release.

No profile count or panel number is assumed. Original asset names are preserved.
"""
import argparse
import hashlib
import json
import struct
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/stolen/rnix/releases/tags/panel_overlays"
MAGIC = b"\xd0\x0d\xfe\xed"

def request(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "IdentifyPanel-profile-fetcher/1.0",
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()

def validate(data):
    if len(data) < 40 or data[:4] != MAGIC:
        return False, "FDT magic/header ausente"
    total = struct.unpack(">I", data[4:8])[0]
    if total < 40 or total > len(data):
        return False, "tamanho FDT inconsistente"
    return True, f"FDT estrutural ({total} bytes)"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="profiles/official")
    args = ap.parse_args()
    try:
        release = json.loads(request(API))
    except Exception as exc:
        raise SystemExit(f"Falha ao consultar release oficial: {exc}")
    tag = release.get("tag_name")
    if tag != "panel_overlays":
        raise SystemExit(f"Tag inesperada: {tag!r}")
    assets = release.get("assets", [])
    candidates = [a for a in assets if ".dtbo" in a.get("name", "").lower()]
    if not candidates:
        raise SystemExit("A release não publicou assets DTBO reconhecíveis; nada foi instalado.")
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": API,
        "tag": tag,
        "release_name": release.get("name"),
        "published_at": release.get("published_at"),
        "assets_found": len(assets),
        "dtbo_candidates": len(candidates),
        "profiles": [],
    }
    for asset in candidates:
        name = Path(asset["name"]).name
        if name != asset["name"] or name in ("", ".", ".."):
            print(f"SKIP nome inseguro: {asset.get('name')!r}", file=sys.stderr)
            continue
        data = request(asset["browser_download_url"])
        ok, detail = validate(data)
        if not ok:
            print(f"REJECT {name}: {detail}", file=sys.stderr)
            continue
        path = out / name
        path.write_bytes(data)
        entry = {
            "file": name,
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "asset_id": asset.get("id"),
            "source_url": asset.get("browser_download_url"),
            "validation": detail,
            "compatibility": "unverified-on-R36H",
        }
        manifest["profiles"].append(entry)
        print(f"OK {name} | {len(data)} bytes | {entry['sha256']}")
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"\nPerfis válidos baixados: {len(manifest['profiles'])}/{len(candidates)}")
    print(f"Manifesto: {out / 'manifest.json'}")
    if not manifest["profiles"]:
        raise SystemExit("Nenhum DTBO válido foi instalado.")

if __name__ == "__main__":
    main()
