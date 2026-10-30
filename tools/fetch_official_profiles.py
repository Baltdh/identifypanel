#!/usr/bin/env python3
"""Download every DTBO asset published by the pinned ROCKNIX panel_overlays release.

No profile count or panel number is assumed. Original asset names are preserved.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/stolen/rnix/releases/tags/panel_overlays"

def request(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "IdentifyPanel-profile-fetcher/1.0",
    })
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read()

def validate(data):
    # When executed as tools/fetch_official_profiles.py, Python puts only tools/
    # at sys.path[0]. Add the repository root so the shared validator is importable.
    repository_root = str(Path(__file__).resolve().parent.parent)
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)
    # Keep download-time validation identical to the installer/CLI validator.
    from identifypanel import validate_fdt_bytes
    return validate_fdt_bytes(data)

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
    old_manifest_path = out / "manifest.json"
    old_names = set()
    if old_manifest_path.is_file():
        try:
            previous = json.loads(old_manifest_path.read_text(encoding="utf-8"))
            old_names = {item["file"] for item in previous.get("profiles", [])
                         if isinstance(item, dict) and isinstance(item.get("file"), str)
                         and Path(item["file"]).name == item["file"]}
        except (OSError, ValueError, TypeError):
            print("Aviso: manifesto anterior inválido; arquivos antigos não serão removidos.", file=sys.stderr)
    manifest = {
        "source": API,
        "tag": tag,
        "release_name": release.get("name"),
        "published_at": release.get("published_at"),
        "assets_found": len(assets),
        "dtbo_candidates": len(candidates),
        "profiles": [],
    }
    successful_names = set()
    for asset in candidates:
        raw_name = asset.get("name", "")
        name = Path(raw_name).name
        if name != raw_name or name in ("", ".", ".."):
            print(f"SKIP nome inseguro: {raw_name!r}", file=sys.stderr)
            continue
        expected_size = asset.get("size")
        if not isinstance(expected_size, int) or expected_size < 40 or expected_size > 16 * 1024 * 1024:
            print(f"SKIP tamanho ausente ou fora do limite: {name}", file=sys.stderr)
            continue
        path = out / name
        temporary = out / (name + ".download.tmp")
        try:
            data = request(asset["browser_download_url"])
            if len(data) != expected_size:
                raise ValueError(f"tamanho recebido {len(data)} != esperado {expected_size}")
            ok, detail = validate(data)
            if not ok:
                raise ValueError(detail)
            digest = hashlib.sha256(data).hexdigest()
            advertised_digest = asset.get("digest")
            if advertised_digest and advertised_digest.lower() != "sha256:" + digest:
                raise ValueError("SHA-256 diverge do digest publicado pela API")
            temporary.write_bytes(data)
            os.replace(temporary, path)
            successful_names.add(name)
            entry = {
                "file": name,
                "size": len(data),
                "sha256": digest,
                "asset_id": asset.get("id"),
                "source_url": asset.get("browser_download_url"),
                "validation": detail,
                "compatibility": "unverified-on-R36H",
            }
            manifest["profiles"].append(entry)
            print(f"OK {name} | {len(data)} bytes | {digest}")
        except (OSError, ValueError, KeyError, urllib.error.URLError) as exc:
            temporary.unlink(missing_ok=True)
            print(f"REJECT {name}: {exc}", file=sys.stderr)
            continue
    # Remove only files listed by the previous generated manifest and no longer successful.
    for stale in old_names - successful_names:
        stale_path = out / stale
        if stale_path.is_file():
            stale_path.unlink()
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
