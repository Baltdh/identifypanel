# IdentifyPanel / AutoPanel

Ferramenta para diagnóstico e seleção local de overlays LCD em handhelds ROCKNIX baseados em RK3326.

## Pacote offline

O workflow **Build offline IdentifyPanel package** baixa os DTBOs publicados que passam na validação estrutural, grava-os em `profiles/official` na branch e monta um ZIP offline com o menu Shell, o instalador e o manifesto com hashes.

Para gerar o pacote:
1. Abra **Actions** no repositório.
2. Selecione **Build offline IdentifyPanel package**.
3. Clique em **Run workflow** e escolha a branch `autopanel-core`.
4. Ao terminar, baixe o artefato **IdentifyPanel-Offline-R36H**.

## Menu Shell de seleção de tela

O pacote inclui `Selecionar-Tela.sh`, um menu simples que lista os DTBOs encontrados na própria pasta `profiles/official`. O usuário escolhe o perfil; o instalador valida o FDT, faz backup do overlay anterior e instala uma cópia como `overlays/mipi-panel.dtbo`.

Exemplo:

```sh
cd /CAMINHO/IdentifyPanel-Offline
./Selecionar-Tela.sh /CAMINHO/DA/PARTICAO-ROCKNIX
```

Se a raiz da partição for omitida, o script tenta localizar os caminhos comuns `/flash`, `/storage/ROCKNIX` e `/ROCKNIX`; se não encontrar, solicita o caminho. O menu oferece:
- Número do perfil: aplicar esse DTBO.
- `R`: restaurar o overlay que estava presente antes do primeiro teste (ou restaurar a ausência, se não havia overlay).
- `0`: sair sem alterar arquivos.

Requisitos: Shell POSIX/BusyBox, Python 3 e permissões de escrita na partição ROCKNIX. O workflow verifica a sintaxe do Shell com `sh -n`.

## Procedimento de teste

1. Inicie o ROCKNIX e abra um terminal.
2. Execute o menu.
3. Escolha um único perfil e confirme.
4. Reinicie o R36H e observe se a imagem aparece.
5. Se funcionar, mantenha esse perfil. Se não funcionar, recupere o acesso ao armazenamento, abra o menu novamente e escolha outro perfil.
6. Se necessário, use `R` para restaurar o overlay original.

**Limitação importante:** o menu é executado depois que o ROCKNIX inicia. Se um DTBO causar tela preta, o menu não poderá ser aberto naquela inicialização. Para recuperação, será necessário acessar o cartão por outro sistema/dispositivo. Um menu realmente pré-boot exige modificar e validar o mecanismo de boot específico da imagem ROCKNIX usada no R36H; isso ainda não foi implementado.

## Salvaguardas e compatibilidade

- Valida a estrutura FDT antes de instalar.
- Faz cópia de segurança do overlay ativo e registra SHA-256/histórico.
- Instala atomicamente uma cópia como `mipi-panel.dtbo`; os DTBOs do catálogo permanecem intactos.
- Não altera o DTB principal.
- A validação estrutural não prova compatibilidade com o DTB base, pinagem, temporização ou imagem visível.
- Perfis publicados para R35S/R36S não são automaticamente compatíveis com R36H. Nenhum perfil deve ser marcado como compatível com R36H sem teste físico.

Referências: https://rocknix.org/devices/unbranded/game-console-r35s-r36s/ e https://github.com/stolen/rnix/releases/tag/panel_overlays
