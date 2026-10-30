#!/usr/bin/env python3
"""Prepare ROCKNIX's panel overlay on a PC before the R36H's first boot."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FDT_MAGIC = b"\xd0\x0d\xfe\xed"
HEADER_SIZE = 40
EXPECTED_OVERLAY = "/overlays/mipi-panel.dtbo"
MANIFEST_NAME = "IdentifyPanel-firstboot.json"


class PreparationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_fdt(data: bytes) -> dict[str, dict[str, bytes]]:
    """Parse the FDT structure block and return node paths and raw properties."""
    if len(data) < HEADER_SIZE or data[:4] != FDT_MAGIC:
        raise PreparationError("Arquivo sem cabeçalho FDT/DTB válido.")
    total = int.from_bytes(data[4:8], "big")
    off_struct = int.from_bytes(data[8:12], "big")
    off_strings = int.from_bytes(data[12:16], "big")
    version = int.from_bytes(data[20:24], "big")
    size_strings = int.from_bytes(data[32:36], "big")
    size_struct = int.from_bytes(data[36:40], "big")
    if total < HEADER_SIZE or total > len(data):
        raise PreparationError("Tamanho total FDT inconsistente.")
    if version < 16:
        raise PreparationError("Versão FDT antiga ou inválida.")
    if (
        off_struct < HEADER_SIZE
        or off_strings < HEADER_SIZE
        or off_struct + size_struct > total
        or off_strings + size_strings > total
    ):
        raise PreparationError("Offsets ou tamanhos dos blocos FDT inválidos.")

    strings = data[off_strings : off_strings + size_strings]
    cursor = off_struct
    struct_end = off_struct + size_struct
    stack: list[str] = []
    nodes: dict[str, dict[str, bytes]] = {}

    def read_c_string(buf: bytes, offset: int) -> str:
        if offset < 0 or offset >= len(buf):
            raise PreparationError("Offset de string FDT fora dos limites.")
        end = buf.find(b"\0", offset)
        if end < 0:
            raise PreparationError("String FDT sem terminador NUL.")
        try:
            return buf[offset:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PreparationError("String FDT não está em UTF-8.") from exc

    while cursor + 4 <= struct_end:
        token = int.from_bytes(data[cursor : cursor + 4], "big")
        cursor += 4
        if token == 1:  # FDT_BEGIN_NODE
            end = data.find(b"\0", cursor, struct_end)
            if end < 0:
                raise PreparationError("Nome de nó FDT truncado.")
            try:
                name = data[cursor:end].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise PreparationError("Nome de nó FDT inválido.") from exc
            cursor = (end + 4) & ~3
            stack.append(name)
            path = "/" + "/".join(stack[1:])
            nodes[path] = {}
        elif token == 2:  # FDT_END_NODE
            if not stack:
                raise PreparationError("FDT_END_NODE sem nó aberto.")
            stack.pop()
        elif token == 3:  # FDT_PROP
            if cursor + 8 > struct_end or not stack:
                raise PreparationError("Propriedade FDT truncada ou fora de nó.")
            length = int.from_bytes(data[cursor : cursor + 4], "big")
            nameoff = int.from_bytes(data[cursor + 4 : cursor + 8], "big")
            cursor += 8
            name = read_c_string(strings, nameoff)
            if cursor + length > struct_end:
                raise PreparationError(f"Propriedade FDT {name!r} ultrapassa o bloco.")
            value = data[cursor : cursor + length]
            cursor = (cursor + length + 3) & ~3
            path = "/" + "/".join(stack[1:])
            nodes[path][name] = value
        elif token == 4:  # FDT_NOP
            continue
        elif token == 9:  # FDT_END
            break
        else:
            raise PreparationError(f"Token FDT desconhecido: {token}.")
    if stack:
        raise PreparationError("Estrutura FDT terminou com nós ainda abertos.")
    if "/" not in nodes:
        raise PreparationError("Nó raiz ausente no FDT.")
    return nodes


def fdt_string(props: dict[str, bytes], name: str) -> str:
    value = props.get(name)
    if value is None:
        raise PreparationError(f"Propriedade FDT obrigatória ausente: {name}.")
    try:
        return value.split(b"\0", 1)[0].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PreparationError(f"Propriedade FDT {name} inválida.") from exc


def active_extlinux_value(text: str, directive: str) -> list[str]:
    values = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        match = re.match(rf"^{re.escape(directive)}\s+(.+?)\s*$", line, flags=re.IGNORECASE)
        if match:
            values.append(match.group(1).strip())
    return values


def safe_path(root: Path, value: str, label: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PreparationError(f"{label} precisa estar dentro da partição de boot.") from exc
    else:
        if ".." in candidate.parts:
            raise PreparationError(f"Caminho relativo inseguro para {label}.")
        resolved = (root / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PreparationError(f"{label} sai da partição de boot.") from exc
    if candidate.is_symlink() or resolved.is_symlink():
        raise PreparationError(f"{label} é link simbólico; operação bloqueada.")
    if not resolved.is_file():
        raise PreparationError(f"{label} não é um arquivo regular: {resolved}")
    return resolved


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def backup_existing(path: Path) -> Path | None:
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file():
        raise PreparationError(f"Destino existente não é arquivo regular: {path}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.before-identifypanel-{stamp}.bak")
    if backup.exists():
        raise PreparationError(f"Arquivo de backup já existe: {backup}")
    shutil.copy2(path, backup)
    if sha256_file(path) != sha256_file(backup):
        backup.unlink(missing_ok=True)
        raise PreparationError("Falha ao verificar o backup do overlay anterior.")
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Gera mipi-panel.dtbo a partir do DTB original e prepara a partição "
            "ROCKNIX no PC, antes do primeiro boot."
        )
    )
    parser.add_argument("--stock-dtb", required=True, help="DTB Linux original do DarkOS que funcionava")
    parser.add_argument("--boot", required=True, help="Raiz montada da partição de boot ROCKNIX")
    parser.add_argument(
        "--base-dtb",
        help=(
            "DTB base efetivamente selecionado pelo boot. Pode ser omitido somente "
            "quando extlinux.conf contém uma diretiva FDT explícita."
        ),
    )
    parser.add_argument(
        "--importer",
        default=str(Path(__file__).with_name("importpanel.py")),
        help="importpanel.py oficial ROCKNIX (padrão: tools/importpanel.py)",
    )
    parser.add_argument(
        "--install",
        action="store_true",
        help="grava o overlay após todas as validações; sem esta opção só faz prévia",
    )
    args = parser.parse_args()

    try:
        stock = Path(args.stock_dtb).expanduser().resolve()
        importer = Path(args.importer).expanduser().resolve()
        boot_input = Path(args.boot).expanduser()
        if boot_input.is_symlink():
            raise PreparationError("A raiz da partição de boot é link simbólico.")
        boot = boot_input.resolve()
        if not boot.is_dir():
            raise PreparationError(f"Partição de boot não encontrada: {boot}")
        if not stock.is_file() or stock.is_symlink():
            raise PreparationError(f"DTB original não encontrado ou inseguro: {stock}")
        if not importer.is_file() or importer.is_symlink():
            raise PreparationError(f"Importador ROCKNIX não encontrado: {importer}")

        extlinux = safe_path(boot, "extlinux/extlinux.conf", "extlinux.conf")
        extlinux_text = extlinux.read_text(encoding="utf-8", errors="replace")
        overlay_values = active_extlinux_value(extlinux_text, "FDTOVERLAYS")
        if len(overlay_values) != 1:
            raise PreparationError(
                "Esperava exatamente uma diretiva FDTOVERLAYS ativa em extlinux/extlinux.conf."
            )
        overlay_words = overlay_values[0].split()
        if EXPECTED_OVERLAY not in overlay_words:
            raise PreparationError(
                f"Este pacote gera {EXPECTED_OVERLAY}, mas extlinux.conf declara "
                f"{overlay_values[0]!r}. Nada foi alterado."
            )

        fdt_values = active_extlinux_value(extlinux_text, "FDT")
        if len(fdt_values) > 1:
            raise PreparationError(
                "extlinux.conf contém várias diretivas FDT. O script não identifica "
                "qual entrada será selecionada pelo U-Boot; não vou escolher a primeira."
            )
        if args.base_dtb:
            base = safe_path(boot, args.base_dtb, "DTB base")
            if len(fdt_values) == 1:
                fdt_declared = fdt_values[0].split()[0]
                declared_path = safe_path(boot, fdt_declared.lstrip("/"), "DTB indicado por FDT")
                if declared_path != base:
                    raise PreparationError(
                        f"--base-dtb ({base.name}) não coincide com FDT ({declared_path.name})."
                    )
        else:
            if len(fdt_values) != 1 or len(fdt_values[0].split()) != 1:
                raise PreparationError(
                    "extlinux.conf não seleciona um único DTB por FDT. "
                    "Informe --base-dtb com o arquivo que o U-Boot realmente carrega; "
                    "não vou adivinhar pelo nome do aparelho."
                )
            base = safe_path(boot, fdt_values[0].split()[0].lstrip("/"), "DTB indicado por FDT")

        stock_data = stock.read_bytes()
        stock_nodes = parse_fdt(stock_data)
        stock_panel = next(
            (
                path
                for path in ("/dsi@ff450000/panel@0", "/dsi@fe060000/panel@0")
                if path in stock_nodes
            ),
            None,
        )
        if stock_panel is None:
            raise PreparationError(
                "O DTB original não contém /dsi@ff450000/panel@0 nem "
                "/dsi@fe060000/panel@0; o importador ROCKNIX não é aplicável sem adaptação."
            )
        for required in ("dsi,format", "dsi,lanes", "dsi,flags", "panel-init-sequence"):
            if required not in stock_nodes[stock_panel]:
                raise PreparationError(f"O nó original de painel não contém {required}.")

        base_nodes = parse_fdt(base.read_bytes())

        with tempfile.TemporaryDirectory(prefix="identifypanel-firstboot-") as temp_dir:
            generated = Path(temp_dir) / "mipi-panel.dtbo"
            command = [
                sys.executable,
                str(importer),
                "-O",
                "dtbo",
                "-o",
                str(generated),
                str(stock),
            ]
            env = os.environ.copy()
            vendor_dir = Path(__file__).resolve().parent / "vendor"
            if vendor_dir.is_dir():
                existing_pythonpath = env.get("PYTHONPATH")
                env["PYTHONPATH"] = str(vendor_dir) + (
                    os.pathsep + existing_pythonpath if existing_pythonpath else ""
                )
            result = subprocess.run(
                command, capture_output=True, text=True, check=False, env=env
            )
            if result.returncode != 0 or not generated.is_file():
                detail = (result.stderr or result.stdout or "").strip()
                if "No module named 'fdt'" in detail:
                    detail += "\nInstale a dependência no PC com: python -m pip install fdt"
                raise PreparationError(
                    "O importador oficial ROCKNIX falhou"
                    + (f":\n{detail}" if detail else ".")
                )

            overlay_data = generated.read_bytes()
            overlay_nodes = parse_fdt(overlay_data)
            fragment = overlay_nodes.get("/fragment@0")
            overlay_node = overlay_nodes.get("/fragment@0/__overlay__")
            if fragment is None or overlay_node is None:
                raise PreparationError("O arquivo gerado não tem fragment@0/__overlay__.")
            target_path = fdt_string(fragment, "target-path")
            compatible = fdt_string(overlay_node, "compatible")
            if compatible != "rocknix,generic-dsi":
                raise PreparationError(
                    f"Compatibilidade inesperada no overlay: {compatible!r}."
                )
            if target_path not in base_nodes:
                raise PreparationError(
                    f"O DTB base selecionado não contém o alvo {target_path}. "
                    "Overlay recusado para evitar um primeiro boot incompatível."
                )
            if "panel_description" not in overlay_node:
                raise PreparationError("O overlay gerado não contém panel_description.")

            dest_rel = Path("overlays/mipi-panel.dtbo")
            dest = boot / dest_rel
            overlay_dir = boot / "overlays"
            manifest_path = boot / MANIFEST_NAME
            if overlay_dir.is_symlink():
                raise PreparationError("A pasta overlays é link simbólico.")
            if dest.is_symlink() or (dest.exists() and not dest.is_file()):
                raise PreparationError("O destino mipi-panel.dtbo é inseguro.")
            if manifest_path.is_symlink() or (manifest_path.exists() and not manifest_path.is_file()):
                raise PreparationError(f"{MANIFEST_NAME} é inseguro.")
            manifest = {
                "format": 1,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "source": {
                    "file": stock.name,
                    "sha256": hashlib.sha256(stock_data).hexdigest(),
                    "panel_node": stock_panel,
                },
                "base": {
                    "file": str(base.relative_to(boot)).replace("\\", "/"),
                    "sha256": sha256_file(base),
                    "target_exists": target_path,
                },
                "overlay": {
                    "path": EXPECTED_OVERLAY,
                    "sha256": hashlib.sha256(overlay_data).hexdigest(),
                    "compatible": compatible,
                    "target_path": target_path,
                },
                "extlinux": {
                    "file": "extlinux/extlinux.conf",
                    "overlay_directive": overlay_values[0],
                },
                "install_state": "preview_only" if not args.install else "to_be_installed",
                "note": (
                    "Prepared on host PC. First-boot visual verification is still required; "
                    "this does not implement automatic pre-kernel rollback."
                ),
            }

            print("Prévia de primeira inicialização — IdentifyPanel")
            print(f"DTB original: {stock}")
            print(f"Nó de painel original: {stock_panel}")
            print(f"DTB base verificado: {base}")
            print(f"Alvo do overlay: {target_path}")
            print(f"Destino: {dest}")
            print(f"SHA-256 DTBO: {manifest['overlay']['sha256']}")

            if not args.install:
                print("\nNenhum arquivo foi alterado. Revise os dados e rode novamente com --install.")
                return 0

            overlay_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_existing(dest)
            manifest_backup = backup_existing(manifest_path)
            try:
                atomic_write(dest, overlay_data)
                if sha256_file(dest) != manifest["overlay"]["sha256"]:
                    raise PreparationError(
                        "A verificação pós-gravação falhou. O overlay instalado não corresponde ao gerado."
                    )
                manifest["install_state"] = "installed"
                manifest["backup"] = (
                    str(backup.relative_to(boot)).replace("\\", "/") if backup else None
                )
                manifest["manifest_backup"] = (
                    str(manifest_backup.relative_to(boot)).replace("\\", "/")
                    if manifest_backup else None
                )
                manifest_payload = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
                atomic_write(manifest_path, manifest_payload)
            except Exception:
                # Keep the boot partition in its previous state if metadata or
                # post-write verification fails after staging the overlay.
                if backup:
                    atomic_write(dest, backup.read_bytes())
                else:
                    dest.unlink(missing_ok=True)
                if manifest_backup:
                    atomic_write(manifest_path, manifest_backup.read_bytes())
                else:
                    manifest_path.unlink(missing_ok=True)
                raise
            print("\nOverlay instalado e SHA-256 conferido.")
            if backup:
                print(f"Overlay anterior preservado em: {backup}")
            if manifest_backup:
                print(f"Manifesto anterior preservado em: {manifest_backup}")
            print(f"Manifesto: {manifest_path}")
            print("Ejete o cartão com segurança. Nenhum DTB base ou setor do U-Boot foi modificado.")
            return 0

    except (OSError, PreparationError, subprocess.SubprocessError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
