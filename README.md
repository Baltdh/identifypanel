# IdentifyPanel / AutoPanel

Ferramenta offline para inspecionar e testar overlays LCD no ROCKNIX, com foco experimental no R36H.

## Primeira inicialização do R36H (preparação no PC)

O R36H não precisa iniciar um sistema para esta etapa. Antes de inserir o cartão no console, prepare o overlay na partição de boot usando o DTB Linux da instalação DarkOS que funcionava. O ROCKNIX aplica `overlays/mipi-panel.dtbo` antes do kernel.

**Comece por [docs/FIRST_BOOT_PC_PREPARATION.md](docs/FIRST_BOOT_PC_PREPARATION.md).** A ferramenta gera o DTBO com o importador ROCKNIX, verifica o nó de destino no DTB base e, quando o `extlinux.conf` não tem uma diretiva `FDT` ativa, adiciona `FDT /rk3326-gameconsole-r36s.dtb` para não depender da detecção ADC/GPIO do U-Boot no R36H. Ela faz backup do overlay e do `extlinux.conf` antes de gravar. O documento também explica as diferenças entre DTBs comunitários HL-R36H-V20, HL-R36H-V21 e R36S Panel 4. Não escolha um perfil R36S só pelo número “Panel 4”.

## Seletor antes do ROCKNIX (beta experimental)

Existe um módulo de pré-boot para o **U-Boot legado da variante A**: segure R1 durante a partida para abrir o menu de perfis, escolha com o direcional/ABXY e o wrapper só então chama o script original do ROCKNIX. O instalador preserva o boot original como `boot0.scr` e o overlay de referência como `IPANEL/BASE.DTBO`.

**Não use na variante B/mainline.** O mapa de botões vem de uma referência R36S e ainda precisa ser confirmado na revisão R36H; a tela só aparece antes do kernel se o U-Boot conseguir inicializar o LCD. O pacote não troca o binário do bootloader nem grava setores raw.

Leia [docs/PREBOOT_SELECTOR.md](docs/PREBOOT_SELECTOR.md) antes de instalar. O instalador exige um `FDT` explícito e o overlay ROCKNIX esperado. Para remover, restaure `boot0.scr` usando `preboot/Restore-Original-Boot.ps1`.

## Pacote offline

O workflow **Build offline IdentifyPanel package** baixa os DTBOs publicados que passam na validação estrutural, salva os hashes e monta o ZIP offline.

1. Abra **Actions** neste repositório.
2. Escolha **Build offline IdentifyPanel package**.
3. Clique em **Run workflow** e selecione a branch `autopanel-core`.
4. Aguarde a execução terminar com sucesso e baixe o artefato `IdentifyPanel-Offline-R36H`.
5. Extraia a pasta completa, sem separar `identifypanel.py`, `Selecionar-Tela.sh` e `profiles/official`.

A validação estrutural confirma apenas que o arquivo tem uma estrutura FDT plausível. Ela não comprova compatibilidade elétrica ou de temporização com o R36H.

## Fluxo de teste pós-boot

Este seletor é uma alternativa para testes em que o ROCKNIX já inicia. **Preserve o cartão DarkOS que funciona.** Use um cartão ROCKNIX de teste e guarde uma cópia da pasta `stock` e do overlay original antes de começar.

No ROCKNIX, abra um terminal na pasta extraída:

```sh
./Selecionar-Tela.sh /CAMINHO/DA/PARTICAO-ROCKNIX
```

Se o caminho não for informado, o script tenta localizar os caminhos comuns `/flash`, `/storage/ROCKNIX` e `/ROCKNIX`, e depois pergunta o caminho manualmente. O programa exige Python 3 e permissão de escrita na partição. O menu tenta remontar temporariamente a partição para escrita quando ela está montada como somente leitura e volta a somente leitura ao terminar cada operação. Comandos diretos do Python não fazem esse remount automaticamente.

1. Selecione um único perfil e digite `TESTAR`.
2. O perfil será instalado como `overlays/mipi-panel.dtbo`, com estado **pendente**, para ser carregado no próximo boot.
3. Reinicie e verifique a imagem fisicamente.
4. Se a imagem estiver correta, abra o menu e use **C** para confirmar. Só então o perfil fica registrado como confirmado.
5. Se o sistema iniciar, mas a imagem estiver errada, use **F** para desfazer o teste; reinicie para carregar o overlay anterior e então teste outro perfil.
6. Use **R** para voltar ao overlay capturado antes da primeira tentativa.

O menu também oferece **I** para inspecionar os arquivos de boot de forma somente de leitura. O diagnóstico não altera o cartão e mostra se há arquivos como `boot.ini`, `boot.scr` ou `extlinux.conf`, destaca a carga/aplicação do overlay e procura referências a `fatload`, `fatwrite`, `saveenv`, `bootcount` e `bootlimit`. A presença de um comando no texto não comprova que o U-Boot instalado o suporte; o diagnóstico não altera o bootloader.

Para registrar o layout antes de projetar recuperação automática, execute:

```sh
python3 identifypanel.py boot-info --boot /CAMINHO/DA/PARTICAO-ROCKNIX
```

O pacote também aceita os comandos diretos:

```sh
python3 identifypanel.py status --boot /CAMINHO/DA/PARTICAO-ROCKNIX
python3 identifypanel.py confirm --boot /CAMINHO/DA/PARTICAO-ROCKNIX
python3 identifypanel.py rollback --boot /CAMINHO/DA/PARTICAO-ROCKNIX
python3 identifypanel.py restore --boot /CAMINHO/DA/PARTICAO-ROCKNIX
```

**Não confirme apenas porque o sistema parece ter iniciado.** A confirmação é uma decisão visual manual; a ferramenta não consegue ler os pixels do LCD nem comprovar que a imagem está visível.

## Limite importante: Reset e tela preta

O seletor é executado depois que o ROCKNIX inicia. Em imagens com o fluxo de boot usual dessa família, o bootloader carrega `overlays/mipi-panel.dtbo` e aplica o DTBO ao device tree antes de iniciar o kernel. Se o painel provocar falha antes de chegar ao espaço de usuário, o menu do IdentifyPanel não vai executar naquela inicialização.

Por isso, **pressionar Reset sozinho não faz rollback automático nesta versão**. O rollback manual só funciona quando o sistema consegue iniciar ou quando a partição pode ser editada por outro computador/sistema. Não está incluído um patch genérico de bootloader: isso depende dos arquivos reais de boot e das capacidades do U-Boot da imagem instalada. Alterar `boot.ini`, `boot.scr` ou o DTB sem confirmar esse layout pode impedir o boot.

## Salvaguardas e compatibilidade

- Mantém um backup do overlay original, sem sobrescrevê-lo a cada teste.
- Guarda o overlay anterior de cada tentativa para permitir rollback.
- Confere o SHA-256 de cada DTBO do catálogo contra `profiles/official/manifest.json` antes de listar ou preparar o teste; arquivos alterados ou manifesto inconsistente são recusados.
- Instala cópias verificadas atomicamente e registra SHA-256, estado pendente, confirmação manual ou rejeição.
- Recusa manifesto inválido e alguns caminhos de link simbólico que podem desviar as gravações.
- Não altera o DTB principal.
- Não reinicia nem confirma automaticamente um perfil.
- Os perfis publicados `r36s-panel*` e os demais candidatos não estão certificados para R36H.

## Desenvolvimento e testes

```sh
python -m py_compile identifypanel.py tools/fetch_official_profiles.py tools/select_profile.py tools/prepare_first_boot.py tools/importpanel.py
sh -n Selecionar-Tela.sh
python -m unittest discover -s tests -v
```

Referências: [documentação ROCKNIX para R35S/R36S](https://rocknix.org/devices/unbranded/game-console-r35s-r36s/) e [release de perfis de painel](https://github.com/stolen/rnix/releases/tag/panel_overlays).

## Recuperação pré-kernel (pesquisa técnica)

A arquitetura e os requisitos para um rollback real pelo U-Boot estão documentados em [docs/ROCKNIX_PREBOOT_RECOVERY.md](docs/ROCKNIX_PREBOOT_RECOVERY.md). `bootcount`/`altbootcmd` não restaura automaticamente um arquivo da partição; `fdt apply` só altera o device tree em memória. A recuperação persistente exigiria comprovar a escrita FAT, a numeração MMC, a persistência do ambiente e o caminho de boot da imagem específica. Até obter esses dados, o IdentifyPanel mantém o modo manual e não modifica scripts de boot.
