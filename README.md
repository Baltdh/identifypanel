# IdentifyPanel / AutoPanel

Ferramenta offline para diagnosticar e selecionar overlays LCD em handhelds ROCKNIX baseados em RK3326.

## Estado
O repositório começou vazio. Esta primeira versão adiciona diagnóstico de hardware, inspeção da partição ROCKNIX e aplicação/restauração segura de DTBO. Ainda **não contém os binários DTBO oficiais** e não declara compatibilidade de nenhum perfil com R36H sem teste físico.

## Uso no PC (Python 3.9+)
```bash
python identifypanel.py inspect --boot /caminho/da/particao
python identifypanel.py profiles --profiles ./profiles
python identifypanel.py apply --boot /caminho/da/particao --dtbo ./profiles/mipi-panel.dtbo.r36s-panel4 --name r36s-panel4
python identifypanel.py restore --boot /caminho/da/particao
```
No Windows, informe a letra da unidade, por exemplo `E:\\`.

## No ROCKNIX
```bash
python3 identifypanel.py device-info
```

## Salvaguardas
- Valida o cabeçalho FDT/DTBO antes de copiar.
- Faz backup do overlay atual e registra SHA-256.
- Não altera o DTB principal.
- Não avança perfis automaticamente nem interpreta DRM connected como imagem visível.
- A confirmação final é visual. Se o kernel não executar userspace, scripts pós-boot não conseguem recuperar a tela.

## Próximas etapas
1. Importar DTBOs reais da release ROCKNIX e registrar hashes.
2. Obter DTB ROCKNIX e, se possível, DTB DarkOS que funciona.
3. Comparar MIPI-DSI, timings, GPIOs, reguladores e init sequence.
4. Validar cada perfil no R36H real.
5. Implementar fluxo pré-boot só após confirmar o mecanismo real da versão ROCKNIX alvo.

Referências: https://rocknix.org/devices/unbranded/game-console-r35s-r36s/ e https://github.com/stolen/rnix/releases/tag/panel_overlays
