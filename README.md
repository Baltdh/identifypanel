# IdentifyPanel / AutoPanel

Ferramenta offline para inspecionar e testar overlays LCD no ROCKNIX, com foco experimental no R36H.

## Pacote offline

O workflow **Build offline IdentifyPanel package** baixa os DTBOs publicados que passam na validação estrutural, salva os hashes e monta o ZIP offline.

1. Abra **Actions** neste repositório.
2. Escolha **Build offline IdentifyPanel package**.
3. Clique em **Run workflow** e selecione a branch `autopanel-core`.
4. Aguarde a execução terminar com sucesso e baixe o artefato `IdentifyPanel-Offline-R36H`.
5. Extraia a pasta completa, sem separar `identifypanel.py`, `Selecionar-Tela.sh` e `profiles/official`.

A validação estrutural confirma apenas que o arquivo tem uma estrutura FDT plausível. Ela não comprova compatibilidade elétrica ou de temporização com o R36H.

## Fluxo de teste sugerido

**Preserve o cartão DarkOS que funciona.** Use um cartão ROCKNIX de teste e guarde uma cópia da pasta `stock` e do overlay original antes de começar.

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
- Os perfis publicados `r36s-panel*` e os demais candidatos não estão certificados para R36H. O nome “Panel 4” no DarkOS não prova que `r36s-panel4` seja o mesmo painel no ROCKNIX.

## Desenvolvimento e testes

```sh
python -m py_compile identifypanel.py tools/fetch_official_profiles.py tools/select_profile.py
sh -n Selecionar-Tela.sh
python -m unittest discover -s tests -v
```

Referências: [documentação ROCKNIX para R35S/R36S](https://rocknix.org/devices/unbranded/game-console-r35s-r36s/) e [release de perfis de painel](https://github.com/stolen/rnix/releases/tag/panel_overlays).
