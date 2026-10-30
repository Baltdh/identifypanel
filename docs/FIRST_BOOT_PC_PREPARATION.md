# Primeira inicialização do R36H: preparação inteiramente no PC

## Objetivo

Preparar o cartão ROCKNIX antes de inserir o microSD no R36H. Nenhum comando, menu, Python ou serviço precisa executar no console. O painel deve estar configurado no arquivo de overlay que o U-Boot carrega antes do kernel.

Esta estratégia resolve a configuração estática do painel para o primeiro boot. Ela não é o mesmo que implementar troca automática de perfis ou rollback pré-kernel.

## Fatos confirmados no código do ROCKNIX

Repositório: https://github.com/ROCKNIX/distribution, branch `next`.

- O arquivo RK3326 `projects/ROCKNIX/devices/RK3326/packages/u-boot/config/extlinux/extlinux.conf` declara `FDTOVERLAYS /overlays/mipi-panel.dtbo`.
- O README de `config/overlays` diz que o arquivo esperado para display é `mipi-panel.dtbo`.
- O utilitário upstream `projects/ROCKNIX/packages/linux-drivers/generic-dsi/scripts/importpanel.py` foi projetado para extrair os parâmetros de painel de um DTB de firmware original e gerar um overlay para o driver `rocknix,generic-dsi`.
- O importador procura o painel em `/dsi@ff450000/panel@0` ou `/dsi@fe060000/panel@0`; ele extrai formato, lanes, flags DSI, timings e sequência de inicialização.
- A imagem RK3326 contém variantes de U-Boot/boot script. Os arquivos `a_boot.ini` e `b_boot.ini` não devem ser substituídos por suposição. O pacote `u-boot` compila scripts e possui um processo de atualização que também escreve o binário do U-Boot em setores do disco.

Links diretos:
- https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/packages/u-boot/config/extlinux/extlinux.conf
- https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/packages/u-boot/config/overlays/README.txt
- https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/packages/linux-drivers/generic-dsi/scripts/importpanel.py
- https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/packages/u-boot/config/a_boot.ini
- https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/packages/u-boot/config/b_boot.ini

## Evidência específica dos DTBs comunitários R36H

O repositório comunitário https://github.com/southoz/dArkOSRE-R36 mantém DTBs separados para as placas `HL-R36H-V20 2024-05-18` e `HL-R36H-V21 2024-11-18`. A tabela de instalação trata as duas como variante `r36s`, mas são arquivos DTB diferentes. A própria documentação de instalação identifica essas placas pelo ID da motherboard e mantém o perfil R36S Panel 4 como outra entrada.

Foram inspecionados os blobs públicos do repositório, sem gravá-los no console:

| Arquivo | SHA-1 Git blob | Painel em `/dsi@ff450000/panel@0` | Dados principais |
|---|---|---|---|
| HL-R36H-V20 2024-05-18 | `e249a4841371725df6cbb6d5a11a21d24d4b9d39` | `elida,kd35t133` | 640×480, 4 lanes, sequência de init de 773 bytes, clock 29 MHz; 60 Hz usa V-front-porch 165 |
| HL-R36H-V21 2024-11-18 | `cd5eae473af8220563dba7605baa9527faed18a1` | `elida,kd35t133` | 640×480, 4 lanes, sequência de init de 763 bytes, clock 58 MHz; H porches 300/200/300 |
| R36S-V12 Panel 4 | `1b62e80c93a95e673cb2409698c59e668e13e17e` | `elida,kd35t133` | 640×480, 4 lanes, sequência de init de 773 bytes, clock 29 MHz; 60 Hz usa V-front-porch 16 |

Interpretação importante:

- V20 e R36S Panel 4 têm descritor de painel e dimensões semelhantes, mas não são idênticos: o timing vertical de 60 Hz difere.
- V21 tem timings e sequência de inicialização significativamente diferentes.
- Isso explica por que selecionar um arquivo apenas pelo rótulo “Panel 4” pode ser incorreto para uma placa R36H. A revisão da motherboard e o DTB original são mais confiáveis que o nome comercial do painel.
- Estes arquivos comunitários não substituem o DTB original do console e não certificam qualquer revisão não identificada.

Fonte da tabela de placas: https://github.com/southoz/dArkOSRE-R36/blob/main/files/BOOT/dtb/r36_devices.ini
Fonte da instalação e seleção por motherboard: https://github.com/southoz/dArkOSRE-R36/wiki/Firmware-Installation
Arquivos DTB:
- https://github.com/southoz/dArkOSRE-R36/tree/main/files/BOOT/dtb/r36s/HL-R36H-V20%202024-05-18
- https://github.com/southoz/dArkOSRE-R36/tree/main/files/BOOT/dtb/r36s/HL-R36H-V21%202024-11-18
- https://github.com/southoz/dArkOSRE-R36/tree/main/files/BOOT/dtb/r36s/R36S-V12%202023-08-18%20Panel%204

## Procedimento recomendado para o primeiro boot

### Entrada preferida: DTB original do DarkOS que funcionava

A informação de que Panel 4 funcionava no DarkOS é útil. O melhor artefato para preservar esse comportamento é o DTB original usado por aquela instalação, não um overlay R36S baixado por nome.

1. No PC, preserve o backup completo do cartão/instalação antiga do DarkOS.
2. Extraia do backup a partição BOOT e localize o DTB Linux efetivamente usado, normalmente chamado `rk3326-r36s-linux.dtb` em firmwares desta família. Não confundir com `rg351mp-uboot.dtb`, usado por alguns bootloaders para display inicial.
3. Grave a imagem ROCKNIX RK3326 em um cartão de teste, mas ainda não o coloque no console.
4. No PC, abra a partição de boot da nova imagem e inspecione `extlinux/extlinux.conf`, o DTB selecionado (se indicado por `FDT`) e os arquivos de boot. Não altere o DTB base nem o U-Boot.
5. Gere e instale o overlay no PC com a ferramenta incluída no ZIP IdentifyPanel. O pacote offline já inclui PyFDT (`fdt==0.3.3`) em `tools/vendor`; basta ter Python 3 no computador. Não é necessário instalar dependências nem ter internet. Para um checkout do código-fonte fora do ZIP, instale `fdt` com `python -m pip install fdt==0.3.3`.

Faça uma prévia (não grava nada):
```sh
python tools/prepare_first_boot.py --stock-dtb /caminho/para/rk3326-r36s-linux.dtb --boot /caminho/da/particao-BOOT
```

Se `extlinux.conf` tiver uma diretiva `FDT /arquivo.dtb` ativa, a ferramenta consegue inferir o DTB base. Se não tiver um `FDT` único e explícito, informe `--base-dtb` com o arquivo que o boot script/U-Boot realmente carrega. Não escolha esse arquivo só pelo nome do console.

Depois de conferir a prévia, repita com `--install`:
```sh
python tools/prepare_first_boot.py --stock-dtb /caminho/para/rk3326-r36s-linux.dtb --boot /caminho/da/particao-BOOT --base-dtb rk3326-gameconsole-r36s.dtb --install
```

O exemplo de `--base-dtb` é apenas ilustrativo; use o DTB comprovadamente selecionado na imagem gravada. O script verifica a diretiva `FDTOVERLAYS`, gera o arquivo com `tools/importpanel.py`, confirma que `target-path` existe no DTB base, faz backup de um overlay anterior e instala em `overlays/mipi-panel.dtbo`. Sem `--install`, nenhum arquivo é modificado.

6. Antes de instalar o resultado, confirme que o DTB base que o novo ROCKNIX realmente selecionará contém o nó alvo apontado pelo overlay (`/dsi@ff450000/panel@0` ou `/dsi@fe060000/panel@0`). Se a configuração de boot não deixar claro qual DTB será carregado, pare e resolva essa seleção no PC; não escolha um DTB aleatório.
7. Faça backup de qualquer `overlays/mipi-panel.dtbo` existente na partição de boot.
8. Copie o DTBO gerado para o caminho exato `overlays/mipi-panel.dtbo`. O `extlinux.conf` oficial aponta para esse nome e caminho.
9. Ejete o cartão com segurança. Só então faça o primeiro boot.
### Se o DTB original do DarkOS não estiver disponível

Use a revisão real da motherboard para escolher o DTB comunitário específico HL-R36H-V20 ou HL-R36H-V21 como fonte de importação, depois gere o overlay com o importador ROCKNIX. Não use o perfil R36S Panel 4 como substituto automático. As duas revisões R36H listadas não compartilham os mesmos timings.

## Verificações obrigatórias antes de ejetar o cartão

- [ ] `extlinux/extlinux.conf` da imagem aponta para `/overlays/mipi-panel.dtbo`.
- [ ] O arquivo gerado é um FDT/DTBO válido.
- [ ] O overlay aponta para o caminho de painel que existe no DTB base selecionado.
- [ ] O arquivo está no caminho `overlays/mipi-panel.dtbo`, não apenas ao lado do `extlinux.conf`.
- [ ] Foi guardada uma cópia do overlay que já existia.
- [ ] Não foram modificados `boot.scr`, `boot.ini`, o DTB base, a tabela de partições ou os setores raw do U-Boot.

## O que não fazer

- Não substituir o DTB base por um DTB de outra placa só para tentar acertar a tela.
- Não gravar `uboot.bin`, `idbloader`, `boot.scr` ou variáveis persistentes do U-Boot sem identificar a imagem e a variante exatas.
- Não assumir que um menu ou script de pós-boot consegue recuperar uma falha ocorrida antes do kernel.
- Não transplantar o U-Boot do projeto NixOS/Armbian para ROCKNIX: esse projeto documenta um bootloader Armbian modificado e fluxo próprio de detecção; não é o bootloader ROCKNIX e não certifica R36H.

## Limite atual e próxima implementação

A aplicação do overlay em `extlinux.conf` ocorre antes de o kernel iniciar, portanto preparar `mipi-panel.dtbo` no PC é suficiente para corrigir o primeiro boot quando o DTB base e o painel estão corretamente identificados.

Isso não implementa fallback automático entre vários painéis. Um seletor com tentativas automáticas antes do kernel exigiria um boot script/bootloader validado para a imagem exata, com armazenamento durável do índice de tentativa e confirmação escrita por um sistema iniciado. O próximo desenvolvimento deve ser uma ferramenta host-side que valide a imagem/cartão, gere o overlay a partir do DTB original e instale-o com backup — sem exigir inicialização do R36H.
