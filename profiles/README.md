# Perfis DTBO ROCKNIX

## Fonte oficial

Release usada pelo projeto: https://github.com/stolen/rnix/releases/tag/panel_overlays

A página da release declara **11 assets no total**. O número de arquivos DTBO não deve ser presumido a partir desse total: o downloader consulta a API da release, seleciona os assets cujo nome contém `.dtbo`, preserva os nomes originais e registra o número realmente encontrado.

## Baixar todos os perfis disponíveis

Na raiz do repositório, em um computador com Python 3.9+ e internet:

```bash
python tools/fetch_official_profiles.py --output profiles/official
python identifypanel.py profiles --profiles profiles/official
```

O script valida o cabeçalho FDT, salva cada arquivo válido e gera `profiles/official/manifest.json` com origem, tamanho, SHA-256 e ID do asset. A validação estrutural não prova compatibilidade semântica com o DTB base nem funcionamento no R36H.

Também é possível executar o workflow **Fetch official panel profiles** em GitHub Actions; ele cria um artefato ZIP com os perfis e manifesto.

## Compatibilidade

Os overlays da release são publicados para painéis R35S/R36S. Não existe confirmação de que todos sejam compatíveis com R36H. O usuário relatou que **Panel 4 funciona no DarkOS**, mas isso não prova equivalência com `r36s-panel4` do ROCKNIX.

Nenhum perfil deve ser marcado como compatível com R36H antes de teste visual real. Preserve o DTB/overlay original e teste um perfil por vez em cartão separado.
