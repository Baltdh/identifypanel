# Validação no R36H

1. Usar cartão ROCKNIX de teste; preservar o cartão DarkOS funcional.
2. Guardar a pasta stock e o DTB original ROCKNIX.
3. Inspecionar a partição com IdentifyPanel e registrar hashes.
4. Instalar apenas um DTBO validado por vez.
5. Inicializar e anotar: imagem correta, parcial, preta ou boot não concluído.
6. Se falhar, voltar ao PC e aplicar outro perfil; não automatizar ciclos de reboot sem confirmação do mecanismo pré-boot.

Backlight aceso não confirma que o kernel inicializou. DRM status connected também não confirma imagem visível. Se o kernel não executar userspace, um script pós-boot não recupera a tela.
