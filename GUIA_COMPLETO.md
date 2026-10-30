# Bot de coleta do Lords Mobile: guia completo

Versão online, editável: https://claude.ai/artifact/UycEjE9eobhBSLnJmbABop

## Visão geral

O bot envia marchas de coleta automaticamente nas suas contas farm, procurando recursos livres no mapa ao redor de cada castelo. Ele roda no seu PC, controla o BlueStacks pelo ADB e é configurado por um painel no navegador.

Ele funciona como um "dedo robô": tira prints da tela, reconhece botões e recursos comparando com imagens de referência que você recorta, e toca nos lugares certos. Não mexe nos arquivos do jogo nem conversa direto com os servidores.

**Risco de banimento.** Os termos de uso da IGG proíbem programas de automação. Mesmo sendo automação de tela, uma conta detectada pode ser banida, e a conta principal que recebe recursos das farms também pode ser atingida. Use por sua conta e risco, de preferência só nas contas farm.

**O que ele faz hoje:**

- Gira entre várias contas, uma instância do BlueStacks por conta
- Vai até o castelo da conta e procura recursos livres em espiral ao redor
- Pula recursos ocupados e envia até o número de marchas configurado
- Repete a cada intervalo definido no painel
- Pausa a conta e avisa se aparecer uma tela de verificação

**Funções extras (ligadas por recortes opcionais):** contar filas livres, reabrir o jogo se cair, filtrar tipo e nível de recurso, escolher formação, horários de funcionamento, aviso no Telegram, ajuda da guilda e recompensas diárias, enviar recursos à conta principal, trocar de personagem numa só instância, estatísticas por dia, prints automáticos quando trava e ajuste para outra resolução. Veja a seção Funções extras.

## Requisitos

Você precisa de um PC com Windows, o BlueStacks, Python, o ADB e as contas farm já criadas. Tudo é gratuito.

| Item | O que precisa | Observação |
| --- | --- | --- |
| Sistema | Windows 10 ou 11 | Os caminhos do guia são do Windows |
| Memória RAM | 8 GB para 1 a 2 contas, 16 GB para 3 a 5 | Cada instância usa cerca de 2 GB |
| Processador | 4 núcleos ou mais | Virtualização (VT) ligada na BIOS deixa tudo mais leve |
| BlueStacks | Versão 5 ou mais nova | Uma instância por conta farm |
| Python | 3.10 ou mais novo (3.12 recomendado) | Marcar "Add Python to PATH" na instalação |
| ADB | Android SDK Platform-Tools | Extraído em C:\platform-tools |
| Bibliotecas Python | opencv-python, numpy, flask | O iniciar_painel.bat instala sozinho |
| Contas | Contas farm logadas no jogo | Cada uma vinculada a um e-mail, para não perder |
| Navegador | Qualquer um (Chrome, Edge, Firefox) | Só para abrir o painel |

O PC precisa ficar ligado enquanto o bot roda. Se ele hibernar ou suspender, o bot para de enviar marchas.

## Instalação passo a passo

A instalação leva cerca de 20 minutos e só precisa ser feita uma vez.

1. **Instalar o Python**
   - Baixe o instalador em python.org, na seção Downloads, versão 3.12 para Windows.
   - Na primeira tela do instalador, marque **Add Python to PATH** antes de clicar em Install Now.
   - Para conferir: abra o Prompt de Comando (tecla Windows, digite cmd) e rode `python --version`.
2. **Instalar o ADB**
   - Procure "SDK Platform-Tools" no site developer.android.com e baixe a versão para Windows.
   - Extraia o zip de forma que fique a pasta `C:\platform-tools` com o arquivo `adb.exe` dentro.
   - Para conferir: rode `C:\platform-tools\adb.exe version` no Prompt.
3. **Criar a pasta do bot**
   - Extraia este zip em `C:\bot_lords`.
4. **Instalar as bibliotecas**
   - O `iniciar_painel.bat` faz isso automaticamente.
   - Se preferir manual, rode no Prompt: `pip install opencv-python numpy flask`.
5. **Abrir o painel pela primeira vez**
   - Dê dois cliques em `iniciar_painel.bat`.
   - Uma janela preta abre (não feche, é o servidor do painel) e o navegador abre em `http://127.0.0.1:8000`.

Se o Windows perguntar sobre o firewall ao abrir o painel: sem Tailscale, pode clicar em Cancelar; com Tailscale, clique em Permitir para o celular conseguir abrir o painel. Em qualquer caso, o painel só aceita o seu próprio PC e os aparelhos do seu Tailscale.

## Configuração do BlueStacks

Toda instância precisa ter a mesma resolução e o ADB ligado; sem isso o bot não enxerga nem toca na tela.

1. **Resolução fixa:** Configurações → Tela → 1280x720 (ou 1600x900) e DPI 240. Use exatamente a mesma em todas as instâncias. Se mudar depois, todas as imagens de referência precisam ser recortadas de novo.
2. **Orientação:** paisagem (horizontal), como o jogo abre normalmente.
3. **Ligar o ADB:** Configurações → Avançado → Android Debug Bridge (ADB) ligado. Anote o endereço, por exemplo `127.0.0.1:5555`. O número depois dos dois-pontos é a porta.
4. **Desempenho por instância:** Configurações → Desempenho → 2 núcleos, 2 GB de RAM, 30 FPS. Com muitas contas, reduza a qualidade gráfica do jogo para Baixa.
5. **Instalar o jogo:** Play Store dentro do BlueStacks, instale o Lords Mobile e faça login na conta farm.
6. **Ajustes dentro do jogo:** desative notificações e animações que aparecem por cima da tela, se o jogo permitir.

**Várias contas:** abra o Gerenciador de múltiplas instâncias, clique em Nova instância e repita os passos acima. Cada instância ganha uma porta própria, normalmente 5555, 5565, 5575; confira em Configurações → Avançado de cada uma.

Sobre o aviso laranja do ADB: o endereço `127.0.0.1` só aceita conexões do próprio PC, então o risco é baixo. Desligue o ADB quando não for usar o bot.

## Arquivos do projeto

```
C:\bot_lords\
├── bot_lords.py          o bot em si
├── painel.py             servidor do painel
├── painel.html           a página do painel
├── iniciar_painel.bat    atalho para abrir tudo
├── config.json           guarda as configurações (o painel edita)
├── GUIA_COMPLETO.md      este guia
├── estatisticas.json     contadores por dia (criado sozinho)
├── logs\                 registro de cada dia (criado sozinho)
├── erros\                prints de onde travou (criado sozinho)
└── imagens\              recortes dos botões e recursos (.png)
```

| Arquivo | Função | Precisa editar? |
| --- | --- | --- |
| bot_lords.py | Conecta no BlueStacks, reconhece a tela, toca e envia as marchas | Não |
| painel.py | Servidor local que liga o painel ao bot | Não |
| painel.html | A tela do painel no navegador | Não |
| iniciar_painel.bat | Instala as bibliotecas e abre o painel | Não |
| config.json | Contas, intervalo, precisão e demais ajustes | Não, use o painel |
| imagens\*.png | Referências que o bot procura na tela | Sim, você recorta |

Para fazer backup, copie a pasta inteira.

## Imagens de referência

O bot precisa de 10 recortes de botões obrigatórios, pelo menos 1 recorte de recurso e, de preferência, 1 de verificação.

### Como capturar

1. Abra o jogo no BlueStacks e deixe na tela que você quer capturar.
2. Abra o Prompt na pasta do bot: `cd C:\bot_lords`.
3. Rode `python bot_lords.py print 5555` (troque 5555 pela porta da instância).
4. Vai aparecer `tela.png` na pasta. Renomeie antes de capturar a próxima tela (ex.: `tela_mapa.png`).

Nunca use prints do celular nem a captura do Windows: o tamanho fica diferente do que o bot enxerga.

### Como recortar

1. Abra o print no Paint.
2. Selecionar → Seleção retangular e marque só o botão ou ícone, bem justo.
3. Cortar, depois Arquivo → Salvar como → PNG, em `C:\bot_lords\imagens`, com o nome exato da tabela.

Pegue só a parte que nunca muda. Evite números, timers, nomes de jogadores e pedaços do chão do mapa. Não redimensione depois de recortar.

### Lista completa

| Arquivo | O que recortar | Em qual tela |
| --- | --- | --- |
| botao_mapa.png | Botão que leva da cidade para o mapa | Cidade, canto inferior esquerdo |
| botao_castelo.png | Botão do castelo que só aparece no mapa | Mapa, canto inferior esquerdo |
| lupa.png | A lupa ao lado das coordenadas no topo | Mapa |
| campo_k.png | Só o texto "K:" | Janela Buscar |
| campo_x.png | Só o texto "X:" | Janela Buscar |
| campo_y.png | Só o texto "Y:" | Janela Buscar |
| botao_ir.png | O botão azul "Ir" | Janela Buscar |
| botao_coletar.png | O botão que aparece ao tocar num recurso livre | Recurso livre clicado |
| botao_marchar.png | O botão que confirma o envio da tropa | Tela de marcha |
| fechar_x.png | O X vermelho de fechar janelas | Qualquer janela aberta |
| fechar_x2.png, fechar_x3.png… | Outros estilos de X, se o jogo tiver mais de um (opcional) | Outras janelas |
| recurso_*.png | Cada tipo de recurso no mapa, sem o número do nível | Mapa |
| verificacao.png | A tela de verificação, se aparecer (opcional) | Quando o jogo pedir |

### Recursos

O bot carrega tudo que começar com `recurso_`. Um recorte por tipo e, se o visual mudar muito entre níveis, um por nível. Exemplos: `recurso_comida.png`, `recurso_pedra.png`, `recurso_madeira.png`, `recurso_minerio.png`, `recurso_ouro.png`, `recurso_riquezas_lv4.png`.

Para coletar só um tipo, deixe na pasta só os recortes desse tipo.

## Usando o painel

O painel abre em `http://127.0.0.1:8000`. Clique em **Salvar configurações** depois de qualquer mudança; com o bot rodando, ela vale a partir da próxima rodada.

### Topo e números

- **Luz e estado:** cinza = Parado, verde = Rodando, dourado = Aguardando próxima rodada.
- **Iniciar bot / Parar bot:** liga e desliga. Ao parar, ele termina o passo atual em poucos segundos.
- **Marchas enviadas, rodadas completas, próxima rodada:** contadores e contagem regressiva.

### Contas

| Coluna | O que colocar |
| --- | --- |
| Ativa | Ligado = o bot usa essa conta; desligado = pula |
| Nome | Qualquer apelido (farm1, farm2…) |
| Porta ADB | A porta da instância (5555, 5565…) |
| Castelo X / Y | Coordenadas do castelo dessa conta |
| Última rodada | Horário e resultado |

**Testar** confere a conexão; **✕** remove; **Adicionar conta** cria uma linha nova.

### Coleta

| Campo | Padrão | O que faz |
| --- | --- | --- |
| Reino (K) | 1067 | Número do seu reino |
| Marchas por conta | 2 | Marchas por rodada; não passe do número de filas da conta |
| Telas para procurar | 12 | Quantas vezes arrasta o mapa ao redor do castelo |
| Intervalo entre rodadas | 30 min | Espera depois de passar por todas as contas |

### Ajustes avançados

| Campo | Padrão | Quando mexer |
| --- | --- | --- |
| Caminho do ADB | C:\platform-tools\adb.exe | Se o ADB está em outro lugar |
| Precisão dos botões | 0.85 | Diminua se não acha botões; aumente se toca errado |
| Precisão dos recursos | 0.75 | Mesma lógica, para os recursos |
| Distância rótulo → campo | 60 px | Distância do "K:" até a caixa de digitar |

## Primeiro teste e calibração

Teste sempre com 1 conta e 1 marcha, olhando o BlueStacks.

1. **Conexão:** clique em Testar. Precisa aparecer "Conectado".
2. **Configuração de teste:** 1 conta ativa, Marchas = 1, Telas = 4, Intervalo = 5 min. Salve.
3. **Imagens:** todas as obrigatórias com ✓ e pelo menos um recurso listado.
4. **Iniciar** e acompanhar o BlueStacks e o Registro.
5. **Onde travou:** a mensagem "não achei 'nome'" indica o recorte a refazer.

### Calibrar a distância do campo

1. Abra a janela Buscar e tire um print com `python bot_lords.py print 5555`.
2. No Paint, passe o mouse no centro do "K:" e anote o X (aparece no canto inferior esquerdo).
3. Passe o mouse no centro da caixa do número do reino e anote o X.
4. A diferença é o valor certo. Coloque no painel e salve.

### Calibrar a precisão

| Sintoma | Ajuste |
| --- | --- |
| "não achei" um botão visível | Diminua a precisão dos botões em 0.05 ou refaça o recorte |
| Toca em lugar errado | Aumente a precisão dos botões em 0.05 |
| "0 recurso(s) vistos" com recursos na tela | Diminua a precisão dos recursos ou recorte mais justo |
| Toca em pedras ou castelos achando que é recurso | Aumente a precisão dos recursos |

## Rodando várias contas

1. Crie uma instância por conta, com a mesma resolução e DPI.
2. Ligue o ADB em cada uma e anote a porta.
3. Faça login em cada conta farm.
4. No painel, Adicionar conta para cada uma, preencha e use Testar.
5. Rode uma rodada de teste com todas ativas e 1 marcha.

As mesmas imagens servem para todas as contas se a resolução for igual. Cada instância usa cerca de 2 GB de RAM; com 16 GB, 4 a 5 instâncias é o limite confortável. Cada conta leva de 1 a 3 minutos por rodada, então com 5 contas use intervalo de 20 a 30 minutos. O Eco Mode do Gerenciador de instâncias economiza processamento.

## Solução de problemas

| Problema ou mensagem | Causa provável | Solução |
| --- | --- | --- |
| "python não é reconhecido" | Python sem PATH | Reinstale marcando Add Python to PATH |
| "ADB não encontrado" | adb.exe em outra pasta | Corrija o Caminho do ADB |
| "Instância não respondeu" | BlueStacks fechado, ADB desligado ou porta errada | Abra a instância, ligue o ADB, confira a porta |
| "offline" ou "unauthorized" | Conexão ADB travada | `C:\platform-tools\adb.exe kill-server` e teste de novo |
| "Falta a imagem X.png" | Recorte ausente ou nome errado | Confira o nome exato |
| "Nenhuma imagem recurso_*.png" | Nenhum recurso recortado | Recorte pelo menos um |
| "não achei 'nome'" | Recorte ruim ou precisão alta | Refaça o recorte ou diminua a precisão |
| "campo 'campo_k' não encontrado" | Janela Buscar não abriu | Refaça lupa.png e campo_k.png |
| Digita no lugar errado | Distância rótulo → campo errada | Calibre |
| "Não consegui chegar ao castelo" | Busca falhou ou coordenadas erradas | Confira Castelo X/Y |
| "0 recurso(s) vistos" | Recortes não batem | Recorte de novo ou diminua a precisão |
| Toca em tudo menos recurso | Precisão baixa demais | Aumente para 0.80 ou mais |
| Fica tentando sem filas livres | Marchas todas fora | Ajuste Marchas por conta |
| "Pausada: Tela de verificação" | O jogo pediu verificação | Resolva manualmente |
| Painel não abre | Janela preta fechada ou porta 8000 ocupada | Rode o .bat de novo |
| "Painel desconectado" | Servidor fechou | Abra o .bat de novo |
| Parou após atualização do jogo | Botões mudaram | Refaça os recortes |
| Bot lento | PC sobrecarregado | Menos instâncias, Eco Mode, gráfico baixo |

## Como o bot funciona por dentro

A cada rodada o bot relê o config.json e passa por cada conta ativa:

1. Conecta na instância pela porta ADB.
2. Fecha janelas abertas tocando no X vermelho.
3. Se não estiver no mapa, toca no botão do mapa.
4. Toca na lupa, preenche K, X e Y com o castelo e toca em Ir.
5. Tira um print e procura os ícones de recurso.
6. Para cada ícone: toca; se aparecer coletar, toca e depois marchar; senão, fecha e tenta o próximo.
7. Se faltam marchas, arrasta o mapa um passo da espiral e volta ao passo 5.
8. Para ao atingir as marchas ou o limite de telas e registra o resultado.

Depois da última conta, espera o intervalo. Se aparecer `verificacao.png`, a conta é pausada até a próxima rodada. O bot também roda sem painel com `python bot_lords.py`.

## Acessar o painel de qualquer lugar (Tailscale)

O Tailscale cria uma rede privada entre os seus aparelhos. Com ele, você abre o painel no celular ou em outro computador de qualquer lugar (4G, trabalho, viagem), sem abrir portas no roteador e sem deixar o painel na internet. Só aparelhos logados na sua conta do Tailscale conseguem entrar. É grátis para uso pessoal.

1. **No PC do bot:** baixe o Tailscale em tailscale.com/download, instale e entre com uma conta (Google, Microsoft ou e-mail).
2. **No celular:** instale o app Tailscale (Play Store ou App Store) e entre com a **mesma conta**. Deixe ligado.
3. **Abra o painel de novo no PC** (feche a janela preta e rode o `iniciar_painel.bat`). A janela mostra `Painel no celular (Tailscale): http://100.x.y.z:8000` e o mesmo endereço aparece no topo do painel.
4. Se o Windows perguntar sobre o firewall, clique em **Permitir**.
5. **No celular**, com o Tailscale ligado, abra esse endereço no navegador. Salve nos favoritos ou adicione à tela inicial.

Também funciona pelo nome do PC, se o MagicDNS do Tailscale estiver ligado (vem ligado por padrão): `http://nome-do-pc:8000`.

| Problema | Solução |
| --- | --- |
| A janela diz "Tailscale não encontrado" | Confira se o Tailscale está aberto e conectado no PC e abra o painel de novo |
| O celular não abre o endereço | Ligue o Tailscale no celular, com a mesma conta do PC |
| Abre no PC, mas não no celular | Libere o Python no firewall do Windows (Painel de Controle → Firewall → Permitir um app) |
| Não quer o acesso remoto | Desligue "Abrir no celular pelo Tailscale" nos Ajustes avançados e abra o painel de novo |

O PC precisa estar ligado e com o painel aberto: o Tailscale só faz a ponte até ele.

## Funções extras

Cada função só age se o recorte dela estiver na pasta `imagens`. Sem o recorte, o bot pula a função e segue a coleta normal. O painel mostra, em Imagens de referência → Opcionais, quais recortes já existem.

| Função | Como ligar | Recortes |
| --- | --- | --- |
| Contar filas livres | "Filas de marcha da conta" maior que 0 | `fila_ocupada.png` (ícone de marcha em andamento no mapa) |
| Parar quando as filas enchem | Automático | `sem_filas.png` (aviso de filas cheias) |
| Reabrir o jogo | Automático; ajuste "Pacote do jogo" e "Espera ao abrir o jogo" | Nenhum |
| Filtrar tipo de recurso | "Tipos de recurso", ex.: `minerio, ouro` | Nome do recorte: `recurso_minerio.png` |
| Nível mínimo | "Nível mínimo do recurso" | Nome `recurso_minerio_lv4.png` ou `nivel_1.png` … `nivel_9.png` (o "Lv." da janela do recurso) |
| Formação de tropas | "Formação de tropas" = N | `formacao_N.png` (botão da predefinição na tela de marcha) |
| Horários | Ex.: `08:00-12:00, 22:00-06:00` | Nenhum |
| Aviso no Telegram | Token e Chat ID, botão Testar Telegram | Nenhum |
| Ajuda da guilda | Chave "Ajudar a guilda" | `ajuda_guilda.png` |
| Recompensas diárias | Chave "Resgatar recompensas" | `recompensa.png`, `botao_resgatar.png` |
| Enviar à conta principal | Seção "Enviar recursos à conta principal" + "Transportar" na conta | `botao_transportar.png`, `botao_max.png`, `botao_enviar.png` |
| Trocar de personagem | Coluna "Troca de personagem": nomes dos recortes tocados em ordem | Os recortes que você listar, ex.: `avatar, trocar_personagem, farm2` |
| Estatísticas | Automático, em `estatisticas.json` e no painel | Nenhum |
| Registro em arquivo | Automático, em `logs\AAAA-MM-DD.txt` | Nenhum |
| Prints de erro | Chave "Salvar print quando travar"; ficam em `erros\` (50 mais novos) | Nenhum |
| Outra resolução | "Resolução dos recortes" = a do BlueStacks quando recortou | Nenhum |

**Trocar de personagem numa só instância:** coloque várias contas com a mesma porta e preencha a coluna Troca de personagem de cada uma com os botões que levam até aquele personagem. O bot faz as contas em ordem, trocando antes de cada uma.

**Outra resolução:** o bot redimensiona os recortes na proporção da largura da tela. Funciona bem para mudanças de tamanho mantendo a proporção 16:9; se errar muito, recorte de novo na resolução nova.

## Checklist final

**Instalação**
- [ ] Python com PATH (`python --version` funciona)
- [ ] ADB em C:\platform-tools
- [ ] Zip extraído em C:\bot_lords
- [ ] Painel abre pelo iniciar_painel.bat

**BlueStacks**
- [ ] Resolução fixa e igual em todas as instâncias
- [ ] ADB ligado e portas anotadas
- [ ] Jogo instalado e logado em cada conta farm

**Imagens**
- [ ] Prints tirados com `python bot_lords.py print`
- [ ] 10 obrigatórias com ✓ no painel
- [ ] Pelo menos um recurso_*.png
- [ ] verificacao.png (opcional)

**Configuração e teste**
- [ ] Contas cadastradas e Testar mostrando Conectado
- [ ] Coordenadas do castelo preenchidas
- [ ] Distância rótulo → campo calibrada
- [ ] Teste com 1 conta e 1 marcha sem travar
- [ ] Rodada com todas as contas sem travar
- [ ] Valores normais salvos

**Rotina**
- [ ] PC sem suspender enquanto o bot roda
- [ ] Conferir o Registro de vez em quando
- [ ] Refazer recortes após atualizações do jogo
- [ ] Desligar o ADB quando não usar
