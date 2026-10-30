#!/bin/sh
# IdentifyPanel — seletor com tentativa pendente, confirmação visual e rollback manual.
# Uso: ./Selecionar-Tela.sh [raiz-da-particao-ROCKNIX]
set -eu

HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}
APP="$HERE/identifypanel.py"
PROFILES="$HERE/profiles/official"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "ERRO: Python 3 é necessário para validar, testar e restaurar DTBOs."
    echo "Nenhum arquivo foi alterado."
    exit 1
fi
if [ ! -f "$APP" ] || [ ! -d "$PROFILES" ]; then
    echo "ERRO: pacote incompleto. Mantenha identifypanel.py e profiles/official juntos."
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

# ROCKNIX commonly mounts /flash read-only. Remount only around write operations.
run_write() {
    write_mount_opts=$(awk -v mp="$BOOT" '$2 == mp { print $4; exit }' /proc/mounts 2>/dev/null || true)
    restore_read_only=0
    case ",$write_mount_opts," in
        *,ro,*)
            if ! mount -o remount,rw "$BOOT"; then
                echo "ERRO: não foi possível remontar $BOOT para escrita."
                return 1
            fi
            restore_read_only=1
            ;;
    esac

    if "$@"; then
        write_status=0
    else
        write_status=$?
    fi
    sync

    if [ "$restore_read_only" -eq 1 ]; then
        if ! mount -o remount,ro "$BOOT"; then
            echo "AVISO: a partição não voltou para somente leitura. Verifique a montagem."
            return 1
        fi
    fi
    return "$write_status"
}

LIST="${TMPDIR:-/tmp}/identifypanel-menu-$$"
trap 'rm -f "$LIST"' 0
trap 'exit 130' HUP INT TERM
find "$PROFILES" -type f \( -name '*.dtbo' -o -name '*.dtbo.*' \) -print | sort > "$LIST"

if [ ! -s "$LIST" ]; then
    echo "Nenhum DTBO encontrado em $PROFILES."
    exit 1
fi

while :; do
    echo
    echo "======================================"
    echo "       IDENTIFYPANEL — R36H"
    echo "======================================"
    echo "Partição ROCKNIX: $BOOT"
    echo
    "$PYTHON" "$APP" status --boot "$BOOT" || {
        echo "Não foi possível ler o estado do teste."
        exit 1
    }
    echo
    echo "Perfis locais disponíveis:"
    n=0
    while IFS= read -r file; do
        [ -n "$file" ] || continue
        n=$((n + 1))
        printf " %2d) %s\n" "$n" "${file##*/}"
    done < "$LIST"
    echo
    echo " C) Confirmar perfil pendente (somente após ver a imagem funcionando)"
    echo " F) Rejeitar teste e restaurar o overlay anterior"
    echo " I) Inspecionar arquivos de boot (somente leitura)"
    echo " R) Restaurar o overlay original anterior ao IdentifyPanel"
    echo " 0) Sair"
    printf "Escolha o número do perfil ou uma ação: "
    IFS= read -r choice

    case "$choice" in
        0) exit 0 ;;
        C|c)
            if run_write "$PYTHON" "$APP" confirm --boot "$BOOT"; then
                echo "Confirmação registrada. O perfil agora está marcado como confirmado."
            else
                echo "Não foi possível confirmar. O estado pendente foi preservado."
            fi
            ;;
        F|f)
            if run_write "$PYTHON" "$APP" rollback --boot "$BOOT"; then
                echo "Rollback concluído. Reinicie para carregar o overlay anterior."
            else
                echo "Rollback não concluído. Preserve o cartão e consulte o diagnóstico."
            fi
            ;;
        I|i)
            "$PYTHON" "$APP" boot-info --boot "$BOOT"
            ;;
        R|r)
            if run_write "$PYTHON" "$APP" restore --boot "$BOOT"; then
                echo "Reinicie para carregar o overlay original restaurado."
            else
                echo "Restauração não concluída. Preserve o cartão e consulte o diagnóstico."
            fi
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
            echo "O perfil será apenas um TESTE PENDENTE; não será definitivo agora."
            echo "A cópia do catálogo não será alterada. O overlay anterior e o original"
            echo "serão preservados para permitir rollback quando o sistema voltar a iniciar."
            printf "Digite TESTAR para preparar este perfil para o próximo boot: "
            IFS= read -r confirm
            if [ "$confirm" != "TESTAR" ]; then
                echo "Cancelado; nenhum arquivo foi alterado."
                continue
            fi
            if ! run_write "$PYTHON" "$APP" stage --boot "$BOOT" --dtbo "$selected" --name "${selected##*/}"; then
                echo "A preparação falhou. Nenhum teste foi confirmado."
                continue
            fi
            echo
            echo "Agora reinicie o R36H e verifique a imagem."
            echo "Se a imagem aparecer corretamente, volte aqui e use C para confirmar."
            echo "Se o sistema iniciar mas a imagem estiver ruim, use F para desfazer"
            echo "e depois selecione o próximo perfil."
            echo "Se o kernel travar ou a tela ficar preta antes do menu abrir, este script"
            echo "não consegue executar: será preciso recuperar a partição por outro sistema"
            echo "ou leitor de cartão. Reset sozinho não executa rollback pré-boot."
            printf "Pressione Enter para voltar ao menu. "
            IFS= read -r _
            ;;
    esac
done
