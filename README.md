# Bot Lords

Bot de coleta para Lords Mobile (BlueStacks + ADB + OpenCV) com painel web local.

- Guia completo de instalação e uso: [GUIA_COMPLETO.md](GUIA_COMPLETO.md)
- Início rápido (Windows): dois cliques em `iniciar_painel.bat` e abra http://127.0.0.1:8000
- Manual: `pip install -r requirements.txt` e `python painel.py`

## Pendências

- [ ] Recortar as imagens de referência em `imagens/` (10 obrigatórias + pelo menos um `recurso_*.png`)
- [ ] Testar numa instância real do BlueStacks e calibrar precisão e `offset_campo`
- [ ] Detectar filas de marcha livres
- [ ] Reabrir o jogo se ele fechar ou travar
- [ ] Salvar o registro em arquivo
- [ ] Não tentar de novo recursos já vistos/ocupados depois de arrastar o mapa
- [ ] Filtrar tipo e nível de recurso, escolher formação de tropas
- [ ] Horários de funcionamento e aviso no celular (Telegram)
