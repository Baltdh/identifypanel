# Seletor pré-boot do IdentifyPanel (beta R36H)

## O que esta versão faz

Esta variante coloca o seletor **antes de o script original do ROCKNIX carregar o kernel**. O funcionamento é:

1. O U-Boot executa **boot.scr**.
2. Sem R1 pressionado, o wrapper chama o **boot.scr** original sem mudar o overlay.
3. Com R1 pressionado, aparece o menu; uma tecla escolhe o perfil.
4. O perfil é carregado para RAM, o overlay anterior é preservado em **IPANEL/BASE.DTBO**, e o candidato é gravado em **overlays/mipi-panel.dtbo**.
5. O arquivo gravado é lido novamente e comparado por MD5.
6. O wrapper chama o script de boot original, preservado como **boot0.scr**.

O DTB principal, U-Boot em setores brutos e a tabela de partições não são alterados.

## Compatibilidade estrita

**Este beta é somente para ROCKNIX RK3326 variante A, com U-Boot legado (a_uboot.bin). Não instale na variante B/mainline (b_uboot.bin).**

O atual fluxo de atualização ROCKNIX identifica a variante A como “Using legacy u-boot” e instala o script a_boot.scr; a variante B usa outro U-Boot. O U-Boot legado RK3326 da árvore ROCKNIX inclui CMD_GPIO, CMD_FAT, FAT_WRITE, CMD_SOURCE, CMD_SAVEENV, CMD_MD5SUM e vídeo. O menu genérico CONFIG_CMD_BOOTMENU está desativado, por isso este beta usa um seletor Hush acionado por GPIO, não o comando bootmenu.

O U-Boot mainline usado pela variante B possui outra configuração e não tem o mesmo conjunto de comandos de leitura/escrita FAT usado por este wrapper. Não tente forçar este arquivo na variante B. Um menu equivalente para B exige modificar e reconstruir o U-Boot mainline e validar o caminho de vídeo e entrada de teclas.

Fontes técnicas:
- Atualizador ROCKNIX RK3326: https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/bootloader/update.sh
- Defconfig U-Boot legado RK3326: https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/packages/u-boot-legacy/sources/configs/rocknix_rk3326_defconfig
- Comando cfgload do U-Boot legado (procura boot.ini e depois boot.scr): https://github.com/ROCKNIX/hardkernel-uboot/blob/2492a3e467e332e2350d987234ce6123700b3392/cmd/cfgload.c
- Referência comunitária PanCho para o mapeamento de botões R36S: https://github.com/icefirex/nixos-r36s/blob/main/assets/firmware/PanCho.ini

## Limites que precisam ser entendidos

- O mapa inicial de GPIO foi copiado da referência comunitária R36S: R1=c7, Vol-=c1, cima=b12, direita=b15, baixo=b13, esquerda=b14, A=b2, B=b5, X=b7, Y=b6. **Ele ainda não foi confirmado na revisão exata da sua placa R36H.**
- O menu chama lcd init e escreve no console de vídeo/UART. A imagem só aparece no LCD antes do kernel se o U-Boot instalado conseguir inicializar esse painel. Um script não consegue criar imagem em uma tela cujo controlador/sequência MIPI-DSI ainda não foi inicializado pelo próprio U-Boot.
- Este pacote não substitui o binário do U-Boot nem instala um firmware Armbian. Isso evita gravar um bootloader não validado para a sua revisão.
- O menu espera uma tecla enquanto R1 está ativo; não tem timeout. Para ignorá-lo, reinicie sem segurar R1. R1 + Vol- também cancela.
- Os perfis oficiais continuam sendo candidatos não certificados para R36H. O teste estrutural e o MD5 não provam compatibilidade elétrica ou visual.
- A seleção do overlay não corrige automaticamente um DTB base errado. O instalador exige uma diretiva FDT explícita e um arquivo DTB base existente na partição.

## Teclas no menu

| Tecla | Perfil selecionado |
|---|---|
| Cima | R36S Panel 1 |
| Direita | R36S Panel 2 |
| Baixo | R36S Panel 3 |
| Esquerda | R36S Panel 4 |
| A | R36H.DTBO, overlay importado do DTB original que funcionava |
| B | BASE.DTBO, backup do overlay anterior |
| X | R36S Clone |
| Y | RG351MP v2 |

Os candidatos cb408, rg351v-v2 e x35s continuam no catálogo offline, mas não têm atalho físico neste primeiro mapa.

R36H.DTBO deve ser um **overlay DTBO gerado** a partir do DTB Linux original com tools/prepare_first_boot.py. Não renomeie um DTB bruto para .dtbo.

## Preparação no PC

1. Use um microSD ROCKNIX de teste. Preserve o cartão DarkOS que funciona.
2. Prepare a partição de boot de modo que extlinux/extlinux.conf tenha:
   - FDT /caminho/do/dtb-base.dtb ativo, apontando para um DTB que realmente exista na partição;
   - FDTOVERLAYS /overlays/mipi-panel.dtbo ativo.
3. Se ainda não tiver o overlay original R36H, use tools/prepare_first_boot.py com o DTB Linux efetivamente carregado pelo DarkOS funcional e com o DTB base ROCKNIX correto. Faça primeiro a prévia, depois a instalação em um cartão de teste.
4. Copie o overlays/mipi-panel.dtbo gerado para o PC com o nome r36h-original.dtbo. O arquivo deve ser um DTBO FDT válido.
5. Identifique a variante do U-Boot. Se update.log contiver “Using legacy u-boot”, a variante A foi registrada pelo atualizador. Se não houver esse log, só use a opção -ConfirmLegacyUboot depois de confirmar independentemente que o cartão usa a_uboot.bin.
6. No PowerShell, substitua E: pela letra da partição de boot:

~~~powershell
Set-ExecutionPolicy -Scope Process Bypass
.\preboot\Install-PanelSelector.ps1 -BootRoot "E:" -R36HOriginalOverlay "C:\R36H\r36h-original.dtbo"
~~~

Se update.log não existir, e você já tiver confirmado que se trata de U-Boot legado A:

~~~powershell
.\preboot\Install-PanelSelector.ps1 -BootRoot "E:" -ConfirmLegacyUboot -R36HOriginalOverlay "C:\R36H\r36h-original.dtbo"
~~~

O instalador:
- recusa boot.ini ativo, porque ele tem precedência sobre boot.scr;
- exige o FDT explícito e FDTOVERLAYS esperado;
- verifica se o DTB base apontado por FDT existe;
- guarda o boot.scr original como boot0.scr;
- copia os perfis para IPANEL com nomes curtos FAT 8.3;
- guarda o overlay anterior como IPANEL/BASE.DTBO;
- instala o wrapper como boot.scr.

## Teste

1. Ejete o cartão com segurança e ligue o R36H segurando R1.
2. Quando o menu aparecer, pressione a tecla correspondente ao perfil desejado.
3. O sistema deve continuar pelo script de boot original.
4. Verifique a imagem fisicamente antes de considerar o perfil correto.
5. Para restaurar o overlay de referência, abra o seletor novamente e pressione B.

Se o LCD ficar preto **antes de o menu aparecer**, não faça seleção às cegas. Isso indica que o U-Boot não está conseguindo inicializar a tela nesta configuração ou que os GPIOs não correspondem ao mapa padrão.

## Desinstalar o wrapper

Com a partição de boot conectada ao PC:

~~~powershell
.\preboot\Restore-Original-Boot.ps1 -BootRoot "E:"
~~~

Isso restaura boot0.scr como boot.scr. O backup boot0.scr, o diretório IPANEL e os overlays ficam preservados.

## Segurança

O wrapper só grava overlays/mipi-panel.dtbo; guarda a baseline antes do primeiro teste e confere o arquivo após a escrita. Ele não grava a_uboot.bin, b_uboot.bin, SPL, setores raw, variáveis de ambiente fora de saveenv nem tabela de partições. A confirmação visual permanece responsabilidade do usuário.
