#!/usr/bin/env python3
"""Local DTBO selector with a persistent, one-profile-at-a-time test sequence."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from identifypanel import stage, check

def discover(root):
    found = sorted(p for p in root.rglob("*")
                   if p.is_file() and (p.suffix == ".dtbo" or ".dtbo." in p.name))
    valid = []
    for path in found:
        ok, detail = check(path)
        if ok:
            valid.append(path)
            print(f"OK {path.name} [{path.stat().st_size} bytes]")
        else:
            print(f"IGNORADO {path.name}: {detail}")
    return valid

def main():
    parser = argparse.ArgumentParser(description="IdentifyPanel — perfis DTBO locais")
    parser.add_argument("--boot", required=True, help="Partição ROCKNIX contendo overlays/")
    parser.add_argument("--profiles", default=None, help="Catálogo local; padrão profiles/official")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--next", action="store_true", help="Prepara o próximo perfil como teste pendente")
    mode.add_argument("--reset-sequence", action="store_true", help="Reinicia o índice da sequência")
    args = parser.parse_args()

    package = Path(__file__).resolve().parent.parent
    profiles_dir = Path(args.profiles).resolve() if args.profiles else package / "profiles" / "official"
    if not profiles_dir.is_dir():
        raise SystemExit(f"Catálogo não encontrado: {profiles_dir}")
    valid = discover(profiles_dir)
    if not valid:
        raise SystemExit("Nenhum DTBO válido encontrado no catálogo local.")

    boot = Path(args.boot).resolve()
    state_dir = boot / ".identifypanel"
    sequence_file = state_dir / "test-sequence.json"
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {"format": 1, "last_applied": -1, "profiles": [p.name for p in valid]}

    if sequence_file.exists():
        try:
            old = json.loads(sequence_file.read_text(encoding="utf-8"))
            if old.get("profiles") == state["profiles"]:
                state.update(old)
        except (OSError, ValueError, TypeError):
            raise SystemExit("Estado da sequência inválido; não vou sobrescrevê-lo.")
    if args.reset_sequence:
        state["last_applied"] = -1
        sequence_file.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        print("Sequência reiniciada. Nenhum overlay foi alterado.")
        return

    if args.next:
        index = int(state.get("last_applied", -1)) + 1
        if index >= len(valid):
            raise SystemExit("Todos os perfis foram aplicados. Use --reset-sequence para recomeçar.")
        selected = valid[index]
        print(f"\nPróximo perfil: {index + 1}/{len(valid)} — {selected.name}")
        print("Será instalado como teste PENDENTE em overlays/mipi-panel.dtbo.")
        print("Reinicie e verifique a imagem. Se funcionar, rode o comando confirm;")
        print("se falhar e o sistema iniciar, rode rollback antes de tentar outro perfil.")
        print("A ferramenta não faz detecção automática da imagem nem rollback pré-boot.")
        confirm = input("Digite TESTAR para preparar o próximo boot: ").strip()
        if confirm != "TESTAR":
            raise SystemExit("Cancelado; nenhum arquivo foi alterado.")
        stage(SimpleNamespace(boot=str(boot), dtbo=str(selected), name=selected.name))
        state["last_applied"] = index
        state["profiles"] = [p.name for p in valid]
        temporary = sequence_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        temporary.replace(sequence_file)
        print(f"Sequência: perfil {index + 1} de {len(valid)} aplicado.")
        return

    print("\nIDENTIFYPANEL — PERFIS LOCAIS")
    for i, path in enumerate(valid, 1):
        print(f"{i:2d}. {path.name}")
    print("\nDigite o número do perfil ou 0 para sair.")
    try:
        choice = int(input("> ").strip())
    except (ValueError, EOFError):
        raise SystemExit("Seleção inválida; nada foi alterado.")
    if choice == 0:
        return
    if not 1 <= choice <= len(valid):
        raise SystemExit("Número fora da lista.")
    selected = valid[choice - 1]
    if input(f"Digite TESTAR para preparar {selected.name}: ").strip() != "TESTAR":
        raise SystemExit("Cancelado.")
    stage(SimpleNamespace(boot=str(boot), dtbo=str(selected), name=selected.name))
    print("Reinicie para testar. Só confirme depois de ver a imagem funcionando.")
    print("Confirmação: python3 identifypanel.py confirm --boot CAMINHO")
    print("Se falhar mas o sistema iniciar: python3 identifypanel.py rollback --boot CAMINHO")

if __name__ == "__main__":
    main()
