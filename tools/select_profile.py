#!/usr/bin/env python3
"""Menu local para escolher um DTBO já incluído no pacote IdentifyPanel."""
import argparse
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from identifypanel import apply, check


def main():
    parser = argparse.ArgumentParser(description="Selecionar um perfil DTBO local")
    parser.add_argument("--boot", required=True, help="Ponto de montagem da partição ROCKNIX que contém overlays/")
    parser.add_argument("--profiles", default=None, help="Pasta local dos perfis; padrão: profiles/official ao lado do pacote")
    args = parser.parse_args()

    package = Path(__file__).resolve().parent.parent
    profiles_dir = Path(args.profiles).resolve() if args.profiles else package / "profiles" / "official"
    if not profiles_dir.is_dir():
        raise SystemExit(f"Pasta de perfis não encontrada: {profiles_dir}")

    files = sorted(
        p for p in profiles_dir.rglob("*")
        if p.is_file() and (p.suffix == ".dtbo" or ".dtbo." in p.name)
    )
    valid = []
    print("\nIDENTIFYPANEL — PERFIS LOCAIS")
    print("Nenhum download será feito neste menu.\n")
    for path in files:
        ok, detail = check(path)
        if ok:
            valid.append(path)
            print(f"{len(valid):2d}. {path.name}  [{path.stat().st_size} bytes]")
        else:
            print(f" -- IGNORADO {path.name}: {detail}")

    if not valid:
        raise SystemExit("Nenhum DTBO passou na validação estrutural.")

    print("\nDigite o número do perfil para instalar.")
    print("0. Sair sem alterar nada")
    try:
        choice = int(input("> ").strip())
    except (ValueError, EOFError):
        raise SystemExit("Seleção inválida; nada foi alterado.")
    if choice == 0:
        print("Cancelado; nada foi alterado.")
        return
    if choice < 1 or choice > len(valid):
        raise SystemExit("Número fora da lista; nada foi alterado.")

    selected = valid[choice - 1]
    print(f"\nSelecionado: {selected.name}")
    print("A instalação substituirá overlays/mipi-panel.dtbo e salvará uma cópia do overlay existente.")
    confirm = input("Digite APLICAR para continuar: ").strip()
    if confirm != "APLICAR":
        raise SystemExit("Cancelado; nada foi alterado.")

    apply(SimpleNamespace(boot=args.boot, dtbo=str(selected), name=selected.name))


if __name__ == "__main__":
    main()
