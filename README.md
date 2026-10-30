# Bot Lords

Bot de coleta para Lords Mobile (BlueStacks + ADB + OpenCV) com painel web local.

- Guia completo de instalação e uso: [GUIA_COMPLETO.md](GUIA_COMPLETO.md)
- Início rápido (Windows): dois cliques em `iniciar_painel.bat` e abra http://127.0.0.1:8000
- Manual: `pip install -r requirements.txt` e `python painel.py`

## Pendências

- [ ] Recortar as imagens de referência em `imagens/` (10 obrigatórias + pelo menos um `recurso_*.png`)
- [ ] Recortar as imagens opcionais das funções extras que quiser usar (lista no guia, seção Funções extras)
- [ ] Testar numa instância real do BlueStacks e calibrar precisão e `offset_campo`
