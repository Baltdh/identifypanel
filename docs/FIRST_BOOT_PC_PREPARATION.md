# Primeira inicialização do R36H: preparar o cartão no PC

## Objetivo e limite

Preparar o cartão ROCKNIX antes de inserir o microSD no R36H. Nenhum comando, menu, Python ou serviço precisa executar no console. O kernel deve receber o DTB base correto e o overlay do painel aplicado pelo U-Boot durante a primeira inicialização.

Esta estratégia configura um primeiro boot estático com DTB base fixado e overlay derivado do firmware original. Não implementa tentativa automática de vários painéis nem rollback pré-kernel. Não vamos substituir o bootloader ou gravar setores raw do U-Boot sem identificar a revisão da placa e a imagem exata.

## O que o código upstream do ROCKNIX confirma

Repositório: https://github.com/ROCKNIX/distribution, branch next.

- O RK3326 usa extlinux/extlinux.conf. A configuração upstream declara FDTDIR / e FDTOVERLAYS /overlays/mipi-panel.dtbo; a linha FDT de exemplo está comentada.
- O README upstream de config/extlinux explica que o U-Boot normalmente executa boot.scr, verifica hardware por ADC/GPIO, escolhe um DTB e passa a seleção para extlinux. Também diz que, em dispositivo raro ou com detecção incorreta, a diretiva FDT em extlinux.conf permite selecionar manualmente o DTB e tem precedência.
- O README de config/overlays informa que o arquivo esperado para display é mipi-panel.dtbo.
- O importpanel.py upstream gera um overlay para rocknix,generic-dsi a partir do DTB de firmware original. Ele extrai formato DSI, lanes, flags, timings e sequência de inicialização.
- O importador procura o nó /dsi@ff450000/panel@0 ou /dsi@fe060000/panel@0.
- Os boot scripts a_boot.ini e b_boot.ini têm tabelas de detecção distintas. O R36H não tem uma entrada oficialmente identificada nesses scripts. Não devemos pressupor que a detecção automática escolherá o DTB de R36S para o R36H.

Fontes:
- extlinux: https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/packages/u-boot/config/extlinux/extlinux.conf
- explicação sobre seleção de DTB e diretiva FDT: https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/packages/u-boot/config/extlinux/README.txt
- overlays: https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/devices/RK3326/packages/u-boot/config/overlays/README.txt
- importpanel.py: https://github.com/ROCKNIX/distribution/blob/next/projects/ROCKNIX/packages/linux-drivers/generic-dsi/scripts/importpanel.py
- boot scripts: https://github.com/ROCKNIX/distribution/tree/next/projects/ROCKNIX/devices/RK3326/packages/u-boot/config

## Evidência sobre o painel R36H

O R36H não aparece na lista oficial de dispositivos ROCKNIX. A página comunitária Handhelds Wiki recomenda usar a imagem R36S e instalar o DTBO do painel. Ela identifica o R36H como variante horizontal do R36S com Panel 4 (V5). É uma referência comunitária, não certificação oficial do ROCKNIX:
https://handhelds.wiki/R36H

Outro dump comunitário separado do R36H está em:
https://github.com/mstrblueskys/R36H

Nesse repositório, overlays.zip contém overlays/mipi-panel.dtbo. O arquivo tem SHA-256 846ee139c96f0c121116234c63025b97cf3f4f947147e6761185ab965f4b77f3, exatamente igual ao DTBO público mipi-panel.dtbo.r36s-panel4. O boot.ini do dump carrega rk3326-rg351mp-linux.dtb; a análise desse DTB encontrou 640×480, 4 lanes, sequência de init de 773 bytes e clock de 29 MHz, com timing de 60 Hz correspondente ao R36S Panel 4. Isso confirma que ao menos um dump comunitário de R36H usa esse DTBO/timing.

Não generalize esse resultado para todas as revisões: o próprio dump alerta que há revisões silenciosas. Outro repositório comunitário lista placas HL-R36H-V20 e HL-R36H-V21 com DTBs separados e parâmetros diferentes.

### Diferenças encontradas em DTBs comunitários

| DTB comunitário | Sequência init | Clock | Timing de 60 Hz |
|---|---:|---:|---|
| HL-R36H-V20 2024-05-18 | 773 bytes | 29 MHz | V-front-porch 165 |
| HL-R36H-V21 2024-11-18 | 763 bytes | 58 MHz | H porches 300/200/300 |
| R36S-V12 Panel 4 | 773 bytes | 29 MHz | V-front-porch 16 |

Fontes:
- tabela de revisões: https://github.com/southoz/dArkOSRE-R36/blob/main/files/BOOT/dtb/r36_devices.ini
- instalação e seleção por placa: https://github.com/southoz/dArkOSRE-R36/wiki/Firmware-Installation
- DTBs HL-R36H-V20/V21 e R36S Panel 4: https://github.com/southoz/dArkOSRE-R36/tree/main/files/BOOT/dtb/r36s

**Conclusão prática:** a informação de que Panel 4 funcionava no DarkOS é útil, mas a melhor fonte é o DTB Linux efetivamente utilizado pelo DarkOS que funcionava no seu aparelho. Não escolha um perfil apenas pelo nome do painel quando podemos importar os parâmetros originais.

## Procedimento recomendado

### 1. Extrair o DTB original do DarkOS

1. Preserve o backup completo do cartão DarkOS.
2. Abra a partição BOOT desse backup no computador.
3. Leia boot.ini, extlinux.conf ou a instrução de boot usada pelo DarkOS para identificar qual DTB Linux é realmente carregado.
4. Copie esse DTB para uma pasta no PC. Não confunda um DTB de splash/logo do U-Boot com o DTB entregue ao kernel Linux.
5. Se o backup for uma imagem completa do cartão, monte a partição BOOT da imagem em modo somente leitura. Não modifique o backup.

Não presuma que o arquivo se chama rk3326-r36s-linux.dtb: no dump comunitário citado acima, por exemplo, o boot.ini carrega rk3326-rg351mp-linux.dtb. O arquivo certo é o que a configuração daquele DarkOS efetivamente usa.

### 2. Gravar ROCKNIX e identificar a partição de boot

1. Grave a imagem ROCKNIX RK3326 destinada a R36S em um microSD de teste. A gravação apaga o cartão.
2. Ainda não coloque o cartão no R36H.
3. Monte no computador a partição identificada como ROCKNIX.
4. Confirme que existem extlinux/extlinux.conf e o DTB base do sistema. No código-fonte RK3326/R36S, o DTB de dispositivo é rk3326-gameconsole-r36s.dtb.
5. Não use a partição de jogos/ROMs como argumento --boot.

Se a imagem concreta não tiver extlinux/extlinux.conf ou não tiver rk3326-gameconsole-r36s.dtb, pare. Não aplique este procedimento sem inspecionar a estrutura real da imagem.

### 3. Gerar uma prévia do overlay no PC

O pacote IdentifyPanel inclui:
- tools/prepare_first_boot.py
- tools/importpanel.py, o importador ROCKNIX
- dependência PyFDT vendorizada em tools/vendor

Requer Python 3 no computador. Não requer Python, internet, Wi-Fi ou terminal no R36H.

No terminal do computador, dentro da pasta IdentifyPanel-Offline, execute a prévia:

~~~sh
python tools/prepare_first_boot.py --stock-dtb "/caminho/DTB-original-DarkOS.dtb" --boot "/caminho/particao-ROCKNIX" --base-dtb rk3326-gameconsole-r36s.dtb
~~~

No Windows, use caminhos entre aspas, por exemplo:

~~~powershell
python .\tools\prepare_first_boot.py --stock-dtb "D:\DarkOS\BOOT\DTB-original.dtb" --boot 'E:\' --base-dtb rk3326-gameconsole-r36s.dtb
~~~

A prévia não altera arquivos. Ela valida:
- estrutura FDT do DTB original e do DTB base ROCKNIX;
- existência do nó de painel no DTB original;
- propriedades necessárias para importar o painel;
- FDTOVERLAYS /overlays/mipi-panel.dtbo no extlinux.conf;
- existência do caminho-alvo do overlay no DTB base ROCKNIX;
- compatibilidade do overlay gerado com rocknix,generic-dsi.

O código também calcula o SHA-256 do overlay produzido.

### 4. Fixar o DTB base e instalar antes do primeiro boot

O extlinux.conf upstream normalmente não tem uma diretiva FDT ativa. Nesse caso, o U-Boot pode escolher o DTB por ADC/GPIO, e essa seleção pode não reconhecer o R36H.

Ao receber --base-dtb rk3326-gameconsole-r36s.dtb, o IdentifyPanel insere uma diretiva explícita:

~~~text
FDT /rk3326-gameconsole-r36s.dtb
~~~

Ela é colocada antes de FDTOVERLAYS. Assim, o primeiro boot não depende da seleção automática de DTB por ADC/GPIO. A diretiva FDT é o mecanismo previsto pelo próprio extlinux do ROCKNIX para escolher manualmente o DTB.

Depois de conferir a prévia e confirmar que o arquivo base existe na partição, execute novamente com --install:

~~~sh
python tools/prepare_first_boot.py --stock-dtb "/caminho/DTB-original-DarkOS.dtb" --boot "/caminho/particao-ROCKNIX" --base-dtb rk3326-gameconsole-r36s.dtb --install
~~~

Na instalação, o script:
- grava o DTBO gerado como overlays/mipi-panel.dtbo;
- fixa o DTB base em extlinux/extlinux.conf, caso a imagem não tenha uma diretiva FDT ativa;
- guarda backups do overlay anterior, de extlinux.conf e do manifesto, quando já existirem;
- verifica SHA-256 após gravar;
- restaura os arquivos anteriores se ocorrer falha na gravação ou na verificação;
- escreve IdentifyPanel-firstboot.json com fontes, hashes, destino e backups.

Se extlinux.conf já tiver uma diretiva FDT diferente do arquivo informado em --base-dtb, a ferramenta aborta. Não substitui uma escolha explícita existente sem análise.

### 5. Verificações antes de inserir o cartão no R36H

- [ ] O DTB fonte é o DTB Linux efetivamente usado pelo DarkOS que funcionava.
- [ ] A imagem é ROCKNIX RK3326/R36S.
- [ ] O caminho fornecido em --boot é a partição ROCKNIX de boot.
- [ ] Existe rk3326-gameconsole-r36s.dtb na raiz dessa partição.
- [ ] A prévia confirmou que o overlay aponta para um nó existente no DTB base.
- [ ] extlinux.conf contém FDT /rk3326-gameconsole-r36s.dtb e FDTOVERLAYS /overlays/mipi-panel.dtbo.
- [ ] Existe backup do overlay e de extlinux.conf, se já havia versões anteriores.

Ejete o microSD com segurança. Só então coloque-o no slot do sistema do R36H e faça o primeiro boot.

## O que o procedimento altera e preserva

Pode criar ou alterar somente:
- overlays/mipi-panel.dtbo;
- uma diretiva FDT /... em extlinux/extlinux.conf, se não houver uma ativa;
- IdentifyPanel-firstboot.json e arquivos de backup.

Não altera:
- DTB base ROCKNIX;
- boot.ini, boot.scr ou outros scripts do U-Boot;
- SPL, U-Boot, BootROM, variáveis de ambiente ou setores raw do cartão;
- tabela de partições;
- partição de sistema/jogos.

## Limitações

- R36H ainda não é oficialmente listado pelo ROCKNIX. Usar a imagem R36S e o DTB de dispositivo R36S é uma adaptação comunitária, não certificação oficial.
- O teste de estrutura, SHA-256 e caminho do nó prova integridade e compatibilidade estrutural básica; não prova funcionamento elétrico, reset GPIO, temporização real nem visibilidade do LCD.
- Fixar rk3326-gameconsole-r36s.dtb evita que o U-Boot escolha um DTB arbitrário, mas também fixa o restante da configuração da placa R36S. A comunidade relata que a imagem R36S funciona no R36H; ainda assim, se o R36H tiver uma revisão de placa muito diferente, o primeiro boot pode exigir um DTB específico.
- O processo não testa pixels nem executa fallback automático. Ele prepara uma configuração inicial fundamentada em DTB de origem e overlay. O cartão original do DarkOS deve continuar preservado.
- Se o DTB original do DarkOS não estiver disponível, a alternativa é identificar fisicamente a revisão da motherboard e importar o DTB comunitário HL-R36H-V20 ou HL-R36H-V21 correspondente. Não assuma que os dois são intercambiáveis.

## Referências

- ROCKNIX R35S/R36S — procedimento de DTBO e importpanel: https://rocknix.org/devices/unbranded/game-console-r35s-r36s/
- ROCKNIX install: https://rocknix.org/play/install/
- Handhelds Wiki — R36H: https://handhelds.wiki/R36H
- Dump comunitário R36H e overlays: https://github.com/mstrblueskys/R36H
- Revisões comunitárias R36H e DTBs: https://github.com/southoz/dArkOSRE-R36
