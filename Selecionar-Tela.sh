#!/bin/sh
# IdentifyPanel — menu shell interativo para selecionar DTBOs locais.
# Uso: ./Selecionar-Tela.sh [raiz-da-particao-ROCKNIX]
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}
APP="$HERE/identifypanel.py"
PROFILES="$HERE/profiles/official"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "ERRO: Python 3 é necessário para validar e instalar o DTBO."
    echo "Nenhum arquivo foi alterado."
    exit 1
fi

if [ ! -f "$APP" ] || [ ! -d "$PROFILES" ]; then
    echo "ERRO: estrutura do pacote IdentifyPanel incompleta."
    exit 1
fi

BOOT=${1:-}
if [ -z "$BOOT" ]; then
    for candidate in /flash /storage/ROCKNIX /ROCKNIX; do
        if [ -d "$candidate/overlays" ] || [ -d "$candidate/ROCKNIX/overlays" ]; then
            BOOT=$candidate
            break
        fi
    done
fi
if [ -z "$BOOT" ]; then
    printf "Caminho da partição ROCKNIX (a pasta que contém overlays/): "
    IFS= read -r BOOT
fi
if [ ! -d "$BOOT" ]; then
    echo "ERRO: partição não encontrada: $BOOT"
    exit 1
fi

LIST="$HERE/.identifypanel-menu-list"
trap 'rm -f "$LIST"' EXIT HUP INT TERM
find "$PROFILES" -type f \( -name '*.dtbo' -o -name '*.dtbo.*' \) -print | sort > "$LIST"

while :; do
    echo
    echo "======================================"
    echo "       IDENTIFYPANEL — R36H"
    echo "======================================"
    echo "Partição ROCKNIX: $BOOT"
    echo
    echo "Perfis locais disponíveis:"
    n=0
    while IFS= read -r file; do
        [ -n "$file" ] || continue
        n=$((n + 1))
        printf " %2d) %s\n" "$n" "${file##*/}"
    done < "$LIST"
    echo
    echo " R) Restaurar overlay original"
    echo " 0) Sair"
    printf "Escolha o número do perfil: "
    IFS= read -r choice

    case "$choice" in
        0) exit 0 ;;
        R|r)
            "$PYTHON" "$APP" restore --boot "$BOOT"
            echo
            echo "Restauração concluída. Reinicie o console para carregar o overlay restaurado."
            ;;
        ''|*[!0-9]*)
            echo "Opção inválida."
            ;;
        *)
            selected=$(sed -n "${choice}p" "$LIST")
            if [ -z "$selected" ] || [ ! -f "$selected" ]; then
                echo "Número fora da lista."
                continue
            fi
            echo
            echo "Perfil escolhido: ${selected##*/}"
            echo "O overlay ativo será substituído por uma cópia deste DTBO."
            echo "O arquivo original do catálogo não será renomeado nem modificado."
            printf "Digite APLICAR para confirmar: "
            IFS= read -r confirm
            if [ "$confirm" != "APLICAR" ]; then
                echo "Cancelado; nenhum arquivo foi alterado."
                continue
            fi
            "$PYTHON" "$APP" apply --boot "$BOOT" --dtbo "$selected" --name "${selected##*/}"
            echo
            echo "Perfil instalado. Reinicie o R36H para testar a tela."
            echo "Se a imagem funcionar, pare aqui. Se não funcionar, recupere o acesso,"
            echo "abra novamente este menu e escolha outro perfil."
            printf "Pressione Enter para voltar ao menu (não reinicia automaticamente). "
            IFS= read -r _
            ;;
    esac
done
