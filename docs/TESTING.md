# Validação no R36H

## Preparação

1. Use um cartão ROCKNIX de teste e preserve o cartão DarkOS funcional.
2. Faça backup da partição de boot ROCKNIX e da pasta \`stock\`; registre qual era o overlay original.
3. Copie o pacote offline completo e confirme qual diretório realmente contém \`overlays/\`.
4. Execute \`./Selecionar-Tela.sh /CAMINHO/DA/PARTICAO-ROCKNIX\`.
5. Teste um DTBO por vez. Não altere o DTB principal.

## Tentativa transacional

- Ao selecionar um perfil e digitar \`TESTAR\`, o IdentifyPanel salva o estado pendente, guarda o overlay anterior e instala uma cópia validada como \`overlays/mipi-panel.dtbo\`.
- Reinicie o console e verifique a imagem.
- Se a imagem estiver correta, abra o menu e use \`C\`. Isso registra uma confirmação manual do usuário; não é uma detecção automática do LCD.
- Se o sistema iniciar mas a imagem estiver incorreta, use \`F\`, reinicie para carregar o overlay anterior e depois selecione outro perfil.
- Use \`R\` para restaurar o overlay de base capturado antes do primeiro teste.

## Limite do Reset

A documentação ROCKNIX para a família R35S/R36S orienta carregar o perfil como \`overlays/mipi-panel.dtbo\` na partição de boot e reiniciar para ver se a tela funciona: <https://rocknix.org/devices/unbranded/game-console-r35s-r36s/>.

O IdentifyPanel ainda não altera o bootloader. Se o kernel não chegar ao sistema de arquivos de usuário, o menu não consegue executar rollback. O Reset apenas repete o boot com os arquivos atuais; não consegue sozinho distinguir imagem visível de tela preta.

Para rollback automático após um boot quebrado, precisamos obter a partição real de boot usada por essa instalação e verificar o \`boot.ini\`, \`boot.scr\`, \`extlinux.conf\` ou mecanismo equivalente. Um mecanismo pré-boot teria de aplicar o perfil de teste e recuperar o anterior antes da próxima tentativa. Não se deve alterar esses arquivos por suposição: um patch incompatível pode impedir o boot.

## Registros de teste

Para cada perfil, anote:

- Nome do DTBO e SHA-256.
- Modelo/compatibilidade do device tree, quando disponível.
- Resultado visual: correto, parcialmente correto, preto, cores erradas ou travamento.
- Se o sistema terminou de iniciar, se houve imagem, e se foi necessário rollback.

Retroiluminação acesa e status DRM \`connected\` não provam que a imagem esteja visível. DTBO estruturalmente válido não significa compatibilidade comprovada com R36H.
