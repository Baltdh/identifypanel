#!/usr/bin/env python3
"""Download every DTBO asset published by the pinned ROCKNIX panel_overlays release.

No profile count or panel number is assumed. Original asset names are preserved.
"""
import argparse
import hashlib
import json
import struct
import os
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
    (total, off_struct, off_strings, off_rsvmap, version,
     last_comp, _boot_cpu, size_strings, size_struct) = struct.unpack(">9I", data[4:40])
    if total < 40 or total > len(data):
        return False, "tamanho FDT inconsistente"
    if version < 16 or last_comp < 16 or last_comp > version:
        return False, "versão FDT incompatível"
    if min(off_struct, off_strings, off_rsvmap) < 40:
        return False, "offset FDT dentro do cabeçalho"
    if off_struct % 4 or off_strings % 4 or off_rsvmap % 8:
        return False, "alinhamento dos offsets FDT inválido"
    if off_struct + size_struct > total or off_strings + size_strings > total or size_struct < 4:
        return False, "seções FDT fora dos limites"
    if max(off_struct, off_strings) < min(off_struct + size_struct, off_strings + size_strings):
        return False, "seções FDT sobrepostas"
    cursor, terminated = off_rsvmap, False
    while cursor + 16 <= total:
        address, size = struct.unpack_from(">QQ", data, cursor)
        cursor += 16
        if address == 0 and size == 0:
            terminated = True
            break
    if not terminated:
        return False, "mapa de reservas sem terminador"
    if not (cursor <= off_struct or off_rsvmap >= off_struct + size_struct):
        return False, "mapa de reservas sobrepõe estrutura"
    if not (cursor <= off_strings or off_rsvmap >= off_strings + size_strings):
        return False, "mapa de reservas sobrepõe strings"
    return True, f"FDT estruturalmente consistente ({total} bytes)"

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
