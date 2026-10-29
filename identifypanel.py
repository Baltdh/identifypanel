#!/usr/bin/env python3
"""IdentifyPanel: safe offline ROCKNIX panel overlay utility."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import struct
import time
from pathlib import Path

MAGIC = b"\xd0\x0d\xfe\xed"
HEADER_SIZE = 40
STATE = ".identifypanel"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_fdt_bytes(data):
    if len(data) < HEADER_SIZE or data[:4] != MAGIC:
        return False, "FDT magic/header inválido"
    (total, off_struct, off_strings, off_rsvmap, version,
     last_comp, _boot_cpu, size_strings, size_struct) = struct.unpack(">9I", data[4:40])
    if total < HEADER_SIZE or total > len(data):
        return False, "tamanho total FDT inconsistente"
    if version < 16 or last_comp > version or last_comp < 16:
        return False, "versão FDT incompatível"
    if off_struct < HEADER_SIZE or off_strings < HEADER_SIZE or off_rsvmap < HEADER_SIZE:
        return False, "offset FDT aponta para dentro do cabeçalho"
    if off_struct % 4 or off_strings % 4 or off_rsvmap % 8:
        return False, "alinhamento dos offsets FDT inválido"
    if off_struct + size_struct > total or off_strings + size_strings > total:
        return False, "seções FDT ultrapassam o tamanho declarado"
    if size_struct < 4:
        return False, "bloco de estrutura FDT vazio ou truncado"
    if max(off_struct, off_strings) < min(off_struct + size_struct, off_strings + size_strings):
        return False, "seções de estrutura e strings FDT sobrepostas"
    # Reservation map is a sequence of big-endian (address, size) 64-bit pairs.
    # It must terminate with the 16-byte zero entry before the declared blob end.
    cursor = off_rsvmap
    terminated = False
    while cursor + 16 <= total:
        address, size = struct.unpack_from(">QQ", data, cursor)
        cursor += 16
        if address == 0 and size == 0:
            terminated = True
            break
    if not terminated:
        return False, "mapa de reservas FDT sem terminador válido"
    if not (cursor <= off_struct or off_rsvmap >= off_struct + size_struct):
        return False, "mapa de reservas sobrepõe bloco de estrutura"
    if not (cursor <= off_strings or off_rsvmap >= off_strings + size_strings):
        return False, "mapa de reservas sobrepõe bloco de strings"
    return True, f"FDT estruturalmente consistente ({total} bytes)"


def check(path):
    try:
        return validate_fdt_bytes(path.read_bytes())
    except OSError as exc:
        return False, str(exc)


def overlay_dir(root):
    for path in (root / "overlays", root / "ROCKNIX" / "overlays"):
        if path.is_dir():
            return path
    raise SystemExit("Pasta overlays não encontrada na partição informada.")


def manifest(root):
    path = root / STATE / "manifest.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") != 1:
                raise ValueError("formato inesperado")
            return path, data
        except (OSError, ValueError, json.JSONDecodeError):
            raise SystemExit("Manifesto IdentifyPanel inválido.")
    return path, {"format": 1, "history": [], "original_backup": None}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def inspect(args):
    root = Path(args.boot).resolve()
    directory = overlay_dir(root)
    active = directory / "mipi-panel.dtbo"
    print("Partição:", root, "\nOverlays:", directory)
    if active.exists():
        ok, message = check(active)
        print("Ativo:", ok, message, "SHA256:", digest(active))
    else:
        print("Overlay mipi-panel.dtbo ausente.")
    alternatives = sorted(directory.glob("mipi-panel.dtbo.*"))
    print("Alternativos:", len(alternatives))
    for path in alternatives:
        ok, message = check(path)
        print(("OK" if ok else "INVÁLIDO"), path.name, path.stat().st_size, digest(path), message)


def profiles(args):
    root = Path(args.profiles)
    files = sorted(path for path in root.rglob("*") if path.is_file() and
                   (path.suffix == ".dtbo" or ".dtbo." in path.name)) if root.exists() else []
    if not files:
        print("Nenhum DTBO encontrado. Execute tools/fetch_official_profiles.py.")
        return
    for path in files:
        ok, message = check(path)
        print(("OK" if ok else "INVÁLIDO"), path, digest(path), message)


def apply(args):
    root = Path(args.boot).resolve()
    source = Path(args.dtbo).resolve()
    if not root.is_dir() or not source.is_file():
        raise SystemExit("Caminho da partição ou DTBO não existe.")
    ok, message = check(source)
    if not ok:
        raise SystemExit("DTBO recusado: " + message)
    directory = overlay_dir(root)
    target = directory / "mipi-panel.dtbo"
    manifest_path, data = manifest(root)
    state = root / STATE
    state.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if target.exists():
        backup = state / ("mipi-panel.before-" + stamp + ".dtbo")
        shutil.copy2(target, backup)
        if not data.get("original_backup") and not data.get("original_missing"):
            data["original_backup"] = str(backup.relative_to(root))
    elif "original_missing" not in data and not data.get("original_backup"):
        data["original_missing"] = True
    temporary = target.with_name("mipi-panel.dtbo.new")
    shutil.copy2(source, temporary)
    valid, detail = check(temporary)
    if not valid:
        temporary.unlink(missing_ok=True)
        raise SystemExit("Cópia temporária inválida: " + detail)
    os.replace(temporary, target)
    data.setdefault("history", []).append({
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "profile": args.name or source.name,
        "sha256": digest(target),
        "visual_confirmation": "pending",
    })
    data["active_profile"] = args.name or source.name
    save(manifest_path, data)
    print("Instalado:", target, "\nSHA256:", digest(target))
    print("Teste visual necessário; o programa não confirma pixels visíveis.")


def restore(args):
    root = Path(args.boot).resolve()
    manifest_path, data = manifest(root)
    relative = data.get("original_backup")
    target = overlay_dir(root) / "mipi-panel.dtbo"
    if data.get("original_missing"):
        if target.exists():
            shutil.copy2(target, root / STATE /
                         ("before-restore-" + time.strftime("%Y%m%d-%H%M%S") + ".dtbo"))
            target.unlink()
        data.setdefault("history", []).append({"action": "restore-original-absence"})
        data["active_profile"] = "no-original-overlay"
        save(manifest_path, data)
        print("Estado original restaurado: overlay removido (não existia antes do primeiro teste).")
        return
    if not relative:
        raise SystemExit("Não há overlay original salvo pelo IdentifyPanel.")
    backup = (root / relative).resolve()
    if root not in backup.parents or not backup.is_file():
        raise SystemExit("Backup ausente ou caminho inseguro.")
    ok, message = check(backup)
    if not ok:
        raise SystemExit("Backup inválido: " + message)
    temporary = target.with_name("mipi-panel.dtbo.restore")
    shutil.copy2(backup, temporary)
    if target.exists():
        shutil.copy2(target, root / STATE /
                     ("before-restore-" + time.strftime("%Y%m%d-%H%M%S") + ".dtbo"))
    os.replace(temporary, target)
    data.setdefault("history", []).append({"action": "restore-original", "sha256": digest(target)})
    data["active_profile"] = "original-backup"
    save(manifest_path, data)
    print("Overlay original restaurado:", target)


def device_info(args):
    print("Sistema:", platform.platform())
    for label, path in (("model", Path("/proc/device-tree/model")),
                        ("compatible", Path("/proc/device-tree/compatible")),
                        ("cpuinfo", Path("/proc/cpuinfo"))):
        if path.exists():
            print("\n[" + label + "]\n",
                  path.read_bytes().replace(b"\0", b"\n").decode("utf-8", "replace")[:10000])
    drm = Path("/sys/class/drm")
    if drm.is_dir():
        print("\n[DRM — diagnóstico, não confirmação visual]")
        for path in sorted(drm.iterdir()):
            status = path / "status"
            if status.is_file():
                try:
                    print(path.name, status.read_text().strip())
                except OSError:
                    pass
    print("\nmodel/compatible identificam placa/SoC; connected não prova imagem visível.")


def main():
    parser = argparse.ArgumentParser(description="Diagnóstico e instalação segura de DTBO ROCKNIX")
    commands = parser.add_subparsers(required=True)
    command = commands.add_parser("inspect")
    command.add_argument("--boot", required=True)
    command.set_defaults(run=inspect)
    command = commands.add_parser("profiles")
    command.add_argument("--profiles", default="./profiles")
    command.set_defaults(run=profiles)
    command = commands.add_parser("apply")
    command.add_argument("--boot", required=True)
    command.add_argument("--dtbo", required=True)
    command.add_argument("--name")
    command.set_defaults(run=apply)
    command = commands.add_parser("restore")
    command.add_argument("--boot", required=True)
    command.set_defaults(run=restore)
    command = commands.add_parser("device-info")
    command.set_defaults(run=device_info)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
