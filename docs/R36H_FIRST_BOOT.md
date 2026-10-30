# R36H: preparar o ROCKNIX antes da primeira inicialização

Status: procedimento preventivo para a primeira tentativa; o perfil Panel 4 é uma hipótese fortemente apoiada por referências comunitárias, mas ainda não foi validado no console físico desta instalação.

## Decisão para o primeiro boot

O procedimento não exige que o R36H já tenha um sistema inicializável. A preparação é feita no computador, depois de gravar a imagem ROCKNIX no microSD e antes de inserir o cartão no console:

1. Gravar a imagem ROCKNIX RK3326/R36S recomendada pela documentação comunitária para R36H.
2. Sem inserir o cartão no R36H, abrir no computador a partição de boot identificada como ROCKNIX.
3. Instalar o arquivo mipi-panel.dtbo.r36s-panel4 como overlays/mipi-panel.dtbo.
4. Ejetar o cartão com segurança.
5. Fazer a primeira inicialização com o overlay presente desde o início.

A preparação não depende do menu do ROCKNIX, de SSH, de Wi-Fi, nem de a tela conseguir mostrar a interface.

## Por que Panel 4 é o primeiro candidato

Há três evidências que convergem:

- A página comunitária do R36H no Handhelds Wiki descreve o R36H como variante horizontal do R36S com painel **Panel 4 (V5)**. Na seção ROCKNIX, diz que a imagem R36S funciona no R36H e orienta copiar o DTBO do painel para overlays/mipi-panel.dtbo.
- O histórico fornecido pelo proprietário deste console informa que o perfil “Panel 4” funcionava no DarkOS.
- A documentação oficial do ROCKNIX para R35S/R36S documenta o nome de destino overlays/mipi-panel.dtbo e disponibiliza arquivos mipi-panel.dtbo.r36s-panel*; ela observa que o panel4 inclui modos de 50, 60 e 75 Hz.

Isso justifica escolher mipi-panel.dtbo.r36s-panel4 como **primeiro candidato**, em vez de começar por uma sequência aleatória. Não equivale a uma confirmação oficial para o R36H: a página ROCKNIX consultada cobre R35S/R36S, e o arquivo no catálogo do IdentifyPanel continua marcado unverified-on-R36H.

## Procedimento no Windows

Requisitos: Windows 10/11, PowerShell, pacote IdentifyPanel extraído e microSD já gravado com a imagem ROCKNIX.

1. Grave a imagem ROCKNIX RK3326/R36S no microSD usando Rufus, Etcher ou ferramenta equivalente. A gravação apaga o conteúdo anterior do cartão.
2. Não coloque o cartão no R36H ainda.
3. No Explorador de Arquivos, localize a partição de boot ROCKNIX que o Windows montou e anote a letra, por exemplo E:.
4. Abra PowerShell na pasta IdentifyPanel-Offline.
5. Execute:

       Set-ExecutionPolicy -Scope Process Bypass
       .\Preparar-Primeiro-Boot-R36H.ps1 -BootDrive E:

6. Confira o rótulo da unidade, o sistema de arquivos, o perfil e o SHA-256 exibidos. Digite PREPARAR somente quando a unidade mostrada for a partição de boot ROCKNIX do cartão novo.
7. Ejete o cartão com segurança e faça a primeira inicialização no R36H.

O script lê o manifesto do pacote, verifica tamanho e SHA-256 do DTBO, faz backup de um eventual overlays/mipi-panel.dtbo anterior e grava o arquivo de destino por uma cópia temporária verificada. Também escreve IDENTIFYPANEL-FIRST-BOOT.txt na raiz da partição para registrar a preparação.

O script recusa unidades sem sinais mínimos de serem uma partição de boot. Não selecione a partição de ROMs/jogos. Se o Windows não montar a partição de boot ou mostrar sistema de arquivos desconhecido, não formate a unidade; pare e use um método de leitura/gravação apropriado para essa partição.

## O que o procedimento altera

Único arquivo ativo de configuração de painel:

    ROCKNIX:\overlays\mipi-panel.dtbo

Pode criar, quando necessário, a pasta overlays/, um backup de um DTBO preexistente e o relatório IDENTIFYPANEL-FIRST-BOOT.txt.

Não altera:
- boot.ini, extlinux.conf, boot.scr, uEnv.txt ou outros scripts de boot;
- o DTB principal;
- U-Boot, SPL, BootROM ou variáveis de ambiente;
- a partição de sistema/jogos.

## Limitações e plano de segurança

- O catálogo usa o arquivo público mipi-panel.dtbo.r36s-panel4 da release panel_overlays, de 4.865 bytes, SHA-256 846ee139c96f0c121116234c63025b97cf3f4f947147e6761185ab965f4b77f3.
- A validação FDT e SHA-256 prova a integridade e a estrutura do arquivo, não que os sinais MIPI, a sequência de inicialização ou os timings sejam compatíveis com cada revisão do R36H.
- A imagem ROCKNIX usada deve ser a imagem RK3326/R36S indicada para essa família; a página do R36H relata que a imagem R36S funciona, mas ROCKNIX não lista formalmente o R36H como dispositivo oficialmente suportado.
- A imagem pode expandir partições ou reiniciar durante a primeira inicialização. Por isso o overlay precisa estar na partição de boot antes de ligar o console.
- O procedimento não implementa fallback por U-Boot. Um rollback pré-kernel dependeria de inspecionar e adaptar o bootloader real da imagem escolhida. O método atual preserva o cartão de origem e permite recuperar a partição de boot no computador.
- Se Panel 4 ainda não funcionar, não teste outros DTBOs no escuro. O próximo passo de maior confiança é extrair o DTB do firmware original DarkOS do backup do proprietário e gerar um DTBO a partir desse DTB com o mecanismo importpanel.py do ROCKNIX. A própria documentação ROCKNIX descreve essa geração como alternativa para quando há um DTB original.

## Referências

- ROCKNIX Wiki, Game Console R35S/R36S, seção “New displays”: https://rocknix.org/devices/unbranded/game-console-r35s-r36s/#new-displays-r36s-of-year-2024
- Handhelds Wiki, R36H: https://handhelds.wiki/R36H
- ArchR, documentação de instalação e geração de overlays a partir do DTB original (referência técnica de processo, não uma imagem ROCKNIX): https://arch-r.io/pt-BR/docs/installation/
- Release pública de perfis usada pelo catálogo: https://github.com/stolen/rnix/releases/tag/panel_overlays
