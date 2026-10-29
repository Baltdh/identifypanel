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


def save(path, data):
    """Write JSON state atomically; never expose a partially written manifest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".tmp-{os.getpid()}-{time.time_ns()}")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def state_dir(root):
    state = root / STATE
    if state.is_symlink():
        raise SystemExit("Diretório de estado IdentifyPanel é um link simbólico; operação bloqueada.")
    return state


def overlay_dir(root):
    for path in (root / "overlays", root / "ROCKNIX" / "overlays"):
        if path.is_symlink():
            raise SystemExit(f"Pasta de overlays é link simbólico: {path}; operação bloqueada.")
        if path.is_dir():
            return path
    raise SystemExit("Pasta overlays não encontrada na partição informada.")


def manifest(root):
    state = state_dir(root)
    path = state / "manifest.json"
    if path.is_symlink():
        raise SystemExit("Manifesto é link simbólico; operação bloqueada.")
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("format") not in (1, 2):
                raise ValueError("formato inesperado")
            data["format"] = 2
            data.setdefault("history", [])
            data.setdefault("original_backup", None)
            return path, data
        except (OSError, ValueError, json.JSONDecodeError):
            raise SystemExit("Manifesto IdentifyPanel inválido; não vou sobrescrever o estado.")
    return path, {"format": 2, "history": [], "original_backup": None}


def _safe_state_file(root, relative):
    if not isinstance(relative, str) or not relative:
        raise SystemExit("Caminho de backup ausente ou inválido.")
    state = state_dir(root).resolve()
    raw = root / relative
    if raw.is_symlink():
        raise SystemExit("Backup é link simbólico; operação bloqueada.")
    candidate = raw.resolve()
    if candidate.parent != state:
        raise SystemExit("Caminho de backup fora do diretório de estado; operação bloqueada.")
    if not candidate.is_file():
        raise SystemExit("Arquivo de backup ausente ou inseguro.")
    return candidate


def _copy_atomic(source, target):
    """Copy, validate as an FDT, then atomically replace the target."""
    if target.is_symlink():
        raise SystemExit(f"Arquivo de destino é link simbólico; operação bloqueada: {target}")
    temporary = target.with_name(target.name + f".tmp-{os.getpid()}-{time.time_ns()}")
    try:
        shutil.copy2(source, temporary)
        ok, detail = check(temporary)
        if not ok:
            raise SystemExit("Cópia temporária inválida: " + detail)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _copy_backup(source, state, prefix):
    state.mkdir(parents=True, exist_ok=True)
    destination = state / (prefix + f"-{time.time_ns()}.dtbo")
    temporary = destination.with_name(destination.name + ".tmp")
    try:
        shutil.copy2(source, temporary)
        ok, detail = check(temporary)
        if not ok:
            raise SystemExit("Não foi possível validar backup: " + detail)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return str(destination.relative_to(state.parent))


def _ensure_original_backup(root, data, target):
    """Capture the pre-IdentifyPanel overlay only once, across all trials."""
    if data.get("original_backup"):
        backup = _safe_state_file(root, data["original_backup"])
        ok, detail = check(backup)
        if not ok:
            raise SystemExit("Backup original inválido: " + detail)
        return
    if data.get("original_missing") is True:
        return
    if target.exists():
        relative = _copy_backup(target, state_dir(root), "original-mipi-panel")
        data["original_backup"] = relative
    else:
        data["original_missing"] = True


def inspect(args):
    root = Path(args.boot).resolve()
    directory = overlay_dir(root)
    active = directory / "mipi-panel.dtbo"
    print("Partição:", root, "\nOverlays:", directory)
    if active.is_symlink():
        raise SystemExit("Overlay ativo é link simbólico; operação bloqueada.")
    if active.exists():
        ok, message = check(active)
        print("Ativo:", ok, message, "SHA256:", digest(active))
    else:
        print("Overlay mipi-panel.dtbo ausente.")
    alternatives = sorted(directory.glob("mipi-panel.dtbo.*"))
    print("Alternativos:", len(alternatives))
    for path in alternatives:
        if path.is_symlink():
            print("IGNORADO", path.name, "link simbólico")
            continue
        ok, message = check(path)
        print(("OK" if ok else "INVÁLIDO"), path.name, path.stat().st_size, digest(path), message)


def profiles(args):
    root = Path(args.profiles)
    files = sorted(path for path in root.rglob("*") if path.is_file() and not path.is_symlink() and
                   (path.suffix == ".dtbo" or ".dtbo." in path.name)) if root.exists() else []
    if not files:
        print("Nenhum DTBO encontrado. Execute tools/fetch_official_profiles.py.")
        return
    for path in files:
        ok, message = check(path)
        print(("OK" if ok else "INVÁLIDO"), path, digest(path), message)


def stage(args):
    """Stage one candidate for a reboot; it remains pending until visual confirmation."""
    root = Path(args.boot).resolve()
    source = Path(args.dtbo).resolve()
    if not root.is_dir() or not source.is_file():
        raise SystemExit("Caminho da partição ou DTBO não existe.")
    ok, message = check(source)
    if not ok:
        raise SystemExit("DTBO recusado: " + message)

    directory = overlay_dir(root)
    target = directory / "mipi-panel.dtbo"
    if target.is_symlink():
        raise SystemExit("Overlay ativo é link simbólico; operação bloqueada.")
    state = state_dir(root)
    manifest_path, data = manifest(root)
    if data.get("pending"):
        pending = data["pending"]
        raise SystemExit(
            f"Já existe teste pendente ({pending.get('profile', 'perfil desconhecido')}). "
            "Use confirm após verificar a imagem ou rollback antes de iniciar outro teste."
        )

    state.mkdir(parents=True, exist_ok=True)
    _ensure_original_backup(root, data, target)
    previous_missing = not target.exists()
    previous_backup = None
    if not previous_missing:
        previous_backup = _copy_backup(target, state, "previous-active")
    profile = args.name or source.name
    trial_id = str(time.time_ns())
    history = data.setdefault("history", [])
    history_index = len(history)
    history.append({
        "trial_id": trial_id,
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "profile": profile,
        "sha256": digest(source),
        "result": "applying",
    })
    data["pending"] = {
        "trial_id": trial_id,
        "profile": profile,
        "sha256": digest(source),
        "status": "applying",
        "staged_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "previous_profile": data.get("active_profile"),
        "previous_overlay_backup": previous_backup,
        "previous_overlay_missing": previous_missing,
        "history_index": history_index,
    }
    # Persist recovery metadata before changing the boot-time overlay.
    save(manifest_path, data)
    try:
        _copy_atomic(source, target)
        data["pending"]["status"] = "pending"
        data["history"][history_index]["result"] = "pending"
        save(manifest_path, data)
    except BaseException as stage_error:
        # Best-effort synchronous rollback if staging itself fails.
        pending = data.get("pending", {})
        try:
            if pending.get("previous_overlay_backup"):
                backup = _safe_state_file(root, pending["previous_overlay_backup"])
                _copy_atomic(backup, target)
            elif pending.get("previous_overlay_missing") and target.exists():
                if target.is_symlink():
                    raise SystemExit("Overlay virou link simbólico durante rollback.")
                target.unlink()
            data["history"][history_index]["result"] = "stage-error-rolled-back"
            data.pop("pending", None)
            save(manifest_path, data)
        except BaseException as rollback_error:
            raise SystemExit(
                f"Falha ao aplicar perfil e falha no rollback: {rollback_error}. "
                f"Estado preservado em {manifest_path}"
            )
        raise stage_error
    print("TESTE PENDENTE:", profile)
    print("Overlay preparado para o próximo boot:", target)
    print("Reinicie o console. Só use 'confirm' depois de ver a imagem funcionando.")
    print("Se falhar e o sistema voltar a iniciar, execute 'rollback' antes de escolher outro perfil.")
    print("Aviso: este programa pós-boot não consegue executar rollback se o kernel travar antes do sistema iniciar.")


def apply(args):
    """Compatibility alias: apply now follows the safer staged-test transaction."""
    return stage(args)


def _set_history_result(data, pending, result):
    history = data.get("history", [])
    index = pending.get("history_index")
    if isinstance(index, int) and 0 <= index < len(history):
        if isinstance(history[index], dict):
            history[index]["result"] = result
            history[index]["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")


def confirm(args):
    root = Path(args.boot).resolve()
    directory = overlay_dir(root)
    target = directory / "mipi-panel.dtbo"
    if target.is_symlink():
        raise SystemExit("Overlay ativo é link simbólico; operação bloqueada.")
    manifest_path, data = manifest(root)
    pending = data.get("pending")
    if not isinstance(pending, dict) or pending.get("status") != "pending":
        raise SystemExit("Não há teste pronto para confirmar.")
    if not target.is_file() or digest(target) != pending.get("sha256"):
        raise SystemExit("O overlay ativo não corresponde ao teste pendente; não será confirmado.")
    _set_history_result(data, pending, "confirmed-visually")
    data["active_profile"] = pending["profile"]
    data["last_confirmed"] = {
        "profile": pending["profile"],
        "sha256": pending["sha256"],
        "confirmed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "confirmation": "manual-user-visual",
    }
    data.pop("pending", None)
    save(manifest_path, data)
    print("Perfil confirmado pelo usuário:", data["active_profile"])
    print("A confirmação foi registrada após a solicitação manual; não houve detecção automática da tela.")


def rollback(args):
    root = Path(args.boot).resolve()
    directory = overlay_dir(root)
    target = directory / "mipi-panel.dtbo"
    if target.is_symlink():
        raise SystemExit("Overlay ativo é link simbólico; operação bloqueada.")
    manifest_path, data = manifest(root)
    pending = data.get("pending")
    if not isinstance(pending, dict):
        raise SystemExit("Não existe teste pendente para desfazer.")
    if pending.get("previous_overlay_backup"):
        backup = _safe_state_file(root, pending["previous_overlay_backup"])
        ok, detail = check(backup)
        if not ok:
            raise SystemExit("Backup anterior inválido: " + detail)
        _copy_atomic(backup, target)
    elif pending.get("previous_overlay_missing") is True:
        if target.exists():
            target.unlink()
    else:
        raise SystemExit("Estado anterior incompleto; rollback automático interrompido para não arriscar o cartão.")
    _set_history_result(data, pending, "rejected-rolled-back")
    data["active_profile"] = pending.get("previous_profile")
    data["last_rejected"] = {
        "profile": pending.get("profile"),
        "sha256": pending.get("sha256"),
        "rejected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    data.pop("pending", None)
    save(manifest_path, data)
    print("Teste desfeito. Perfil anterior restaurado.")
    print("Reinicie para carregar o overlay restaurado; depois selecione o próximo perfil.")


def restore(args):
    """Restore the baseline captured before the first IdentifyPanel test."""
    root = Path(args.boot).resolve()
    directory = overlay_dir(root)
    target = directory / "mipi-panel.dtbo"
    if target.is_symlink():
        raise SystemExit("Overlay ativo é link simbólico; operação bloqueada.")
    manifest_path, data = manifest(root)
    pending = data.get("pending")
    if isinstance(pending, dict):
        _set_history_result(data, pending, "abandoned-restored-original")
        data.pop("pending", None)
    relative = data.get("original_backup")
    if data.get("original_missing") is True:
        if target.exists():
            _copy_backup(target, state_dir(root), "before-restore")
            target.unlink()
        data["active_profile"] = "no-original-overlay"
        save(manifest_path, data)
        print("Estado original restaurado: overlay removido (não existia antes do primeiro teste).")
        return
    if not relative:
        raise SystemExit("Não há overlay original salvo pelo IdentifyPanel.")
    backup = _safe_state_file(root, relative)
    ok, message = check(backup)
    if not ok:
        raise SystemExit("Backup original inválido: " + message)
    _copy_backup(target, state_dir(root), "before-restore")
    _copy_atomic(backup, target)
    data["active_profile"] = "original-backup"
    data["last_restore"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    save(manifest_path, data)
    print("Overlay original restaurado:", target)
    print("Reinicie o console para carregar o estado restaurado.")


def status(args):
    root = Path(args.boot).resolve()
    directory = overlay_dir(root)
    target = directory / "mipi-panel.dtbo"
    manifest_path, data = manifest(root)
    print("Partição:", root)
    print("Overlay ativo:", "ausente" if not target.exists() else digest(target))
    print("Perfil registrado:", data.get("active_profile", "não confirmado"))
    pending = data.get("pending")
    if isinstance(pending, dict):
        print("TESTE PENDENTE:", pending.get("profile"), "| estado:", pending.get("status"))
        print("Este perfil ainda não deve ser considerado definitivo.")
    else:
        print("Teste pendente: nenhum")
    print("Manifesto:", manifest_path)
    if data.get("original_backup"):
        print("Backup original:", data["original_backup"])
    elif data.get("original_missing"):
        print("Overlay original: não existia no primeiro teste")

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
    parser = argparse.ArgumentParser(description="Diagnóstico e seleção transacional de DTBO ROCKNIX")
    commands = parser.add_subparsers(required=True)

    command = commands.add_parser("inspect")
    command.add_argument("--boot", required=True)
    command.set_defaults(run=inspect)

    command = commands.add_parser("profiles")
    command.add_argument("--profiles", default="./profiles")
    command.set_defaults(run=profiles)

    for name in ("stage", "apply"):
        command = commands.add_parser(name, help="prepara um teste pendente para o próximo boot")
        command.add_argument("--boot", required=True)
        command.add_argument("--dtbo", required=True)
        command.add_argument("--name")
        command.set_defaults(run=stage)

    command = commands.add_parser("confirm", help="confirma após inspeção visual manual")
    command.add_argument("--boot", required=True)
    command.set_defaults(run=confirm)

    command = commands.add_parser("rollback", help="desfaz o teste pendente e restaura o overlay anterior")
    command.add_argument("--boot", required=True)
    command.set_defaults(run=rollback)

    command = commands.add_parser("restore", help="restaura o overlay original anterior ao IdentifyPanel")
    command.add_argument("--boot", required=True)
    command.set_defaults(run=restore)

    command = commands.add_parser("status", help="mostra o estado de teste")
    command.add_argument("--boot", required=True)
    command.set_defaults(run=status)

    command = commands.add_parser("device-info")
    command.set_defaults(run=device_info)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
