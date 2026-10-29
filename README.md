# IdentifyPanel / AutoPanel

Ferramenta para diagnóstico e seleção local de overlays LCD em handhelds ROCKNIX baseados em RK3326.

## Pacote offline (objetivo principal)

O workflow **Build offline IdentifyPanel package** monta um ZIP completo com os DTBOs encontrados na release de perfis, o manifesto, o validador e um menu local. Depois de baixar esse ZIP em um computador ou celular, basta copiar a pasta extraída para o cartão/armazenamento do R36H. O R36H não precisa de internet para listar ou selecionar os perfis.

O pacote é gerado em GitHub Actions:
1. Abra **Actions** no repositório.
2. Selecione **Build offline IdentifyPanel package**.
3. Clique em **Run workflow**.
4. Quando terminar, baixe o artefato **IdentifyPanel-Offline-R36H**.
5. Extraia a pasta no cartão ou em um armazenamento acessível ao aparelho.

O ZIP só conterá DTBOs que a coleta conseguir baixar e validar. O manifesto registra a quantidade real; não se presume que os 11 assets da release sejam todos DTBOs.

## Seleção local no ROCKNIX

O pacote inclui `Selecionar-Perfil.sh`. Exemplo:

```sh
./Selecionar-Perfil.sh /flash
```

`/flash` é apenas um caminho padrão ilustrativo: confirme o ponto de montagem da partição que contém `overlays/` na sua versão ROCKNIX. O seletor mostra os arquivos DTBO locais, permite escolher um e pede confirmação antes de instalar. Não faz download.

Requisito: Python 3 disponível no ROCKNIX. Se a imagem não tiver Python 3, o pacote continua podendo ser usado em um computador para preparar a partição; não se deve presumir que o script rode no console sem verificar esse requisito.

## Uso manual no PC (Python 3.9+)

```bash
python identifypanel.py inspect --boot /caminho/da/particao
python identifypanel.py profiles --profiles ./profiles/official
python identifypanel.py apply --boot /caminho/da/particao --dtbo ./profiles/official/ARQUIVO.dtbo
python identifypanel.py restore --boot /caminho/da/particao
```

No Windows, informe a letra da unidade, por exemplo `E:\\`.

## Salvaguardas e limites

- Valida a estrutura FDT antes de copiar.
- Faz backup do overlay ativo e registra SHA-256.
- Se não havia overlay antes do primeiro teste, registra essa condição para permitir restaurar a ausência.
- Não altera o DTB principal.
- Não troca perfis automaticamente: cada seleção exige confirmação e reinicialização/teste manual.
- A validação estrutural não prova compatibilidade com o DTB base nem imagem visível.
- Perfis publicados para R35S/R36S não são automaticamente compatíveis com R36H. Nenhum perfil deve ser marcado como compatível com R36H sem teste físico.

Referências: https://rocknix.org/devices/unbranded/game-console-r35s-r36s/ e https://github.com/stolen/rnix/releases/tag/panel_overlays
