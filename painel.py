"""
Painel do bot. Rode:  python painel.py
e abra http://127.0.0.1:8000 no navegador (abre sozinho).
"""
import os
import glob
from datetime import datetime
import threading
import webbrowser
from collections import deque

from flask import Flask, jsonify, request, send_file

import bot_lords as bl

app = Flask(__name__)
HOSTS_OK = {"127.0.0.1:8000", "localhost:8000"}
LOGS = deque(maxlen=400)
ativo = {"bot": None, "thread": None, "parar": None}


@app.before_request
def so_local():
    # Bloqueia outros sites abertos no navegador de mexer no painel (CSRF / DNS rebinding).
    if request.host not in HOSTS_OK:
        return "Host não permitido", 403
    origem = request.headers.get("Origin")
    if request.method == "POST" and origem and origem.split("://", 1)[-1] not in HOSTS_OK:
        return "Origem não permitida", 403


def rodando():
    return ativo["thread"] is not None and ativo["thread"].is_alive()


@app.get("/")
def pagina():
    return send_file(os.path.join(bl.PASTA, "painel.html"))


@app.get("/api/config")
def ler_config():
    return jsonify(bl.carregar_config())


def horarios_de_texto(texto):
    """'08:00-12:00, 14:00-23:30' -> [{"inicio": "08:00", "fim": "12:00"}, …]"""
    saida = []
    for parte in str(texto).replace(";", ",").split(","):
        parte = parte.strip()
        if not parte:
            continue
        ini, fim = (p.strip() for p in parte.split("-"))
        for h in (ini, fim):
            datetime.strptime(h, "%H:%M")
        saida.append({"inicio": f"{int(ini[:-3]):02d}:{ini[-2:]}", "fim": f"{int(fim[:-3]):02d}:{fim[-2:]}"})
    return saida


def lista_de_texto(valor):
    partes = valor if isinstance(valor, list) else str(valor).split(",")
    return [str(p).strip() for p in partes if str(p).strip()]


@app.post("/api/config")
def gravar_config():
    novo = request.get_json(silent=True) or {}
    try:
        cfg = bl.carregar_config()
        for chave in ("reino", "marchas_por_conta", "max_arrastos", "intervalo_min", "offset_campo",
                      "filas_total", "nivel_minimo", "formacao", "espera_abrir_jogo"):
            cfg[chave] = max(0, int(novo[chave]))
        cfg["intervalo_min"] = max(1, cfg["intervalo_min"])
        for chave in ("confianca", "confianca_recurso"):
            cfg[chave] = max(0.5, min(0.99, float(novo[chave])))
        for chave in ("adb", "pacote_jogo", "telegram_token", "telegram_chat"):
            cfg[chave] = str(novo[chave]).strip()
        for chave in ("ajuda_guilda", "recompensas", "prints_erro", "telegram_resumo"):
            cfg[chave] = bool(novo[chave])
        cfg["resolucao_base"] = [int(v) for v in str(novo["resolucao_base"]).lower().split("x")]
        cfg["recursos_tipos"] = [t.lower() for t in lista_de_texto(novo["recursos_tipos"])]
        cfg["horarios"] = horarios_de_texto(novo["horarios"])
        p = novo["principal"]
        cfg["principal"] = {"ativo": bool(p["ativo"]), "x": int(p["x"]), "y": int(p["y"]),
                            "a_cada_rodadas": max(1, int(p["a_cada_rodadas"]))}
        contas = []
        for c in novo["contas"]:
            contas.append({"nome": str(c["nome"]).strip() or "conta",
                           "porta": int(c["porta"]),
                           "castelo_x": int(c["castelo_x"]),
                           "castelo_y": int(c["castelo_y"]),
                           "ativa": bool(c.get("ativa", True)),
                           "transportar": bool(c.get("transportar", False)),
                           "troca": lista_de_texto(c.get("troca", ""))})
        cfg["contas"] = contas
    except (KeyError, ValueError, TypeError, AttributeError) as e:
        return jsonify(ok=False, erro=f"Valor inválido: {e}"), 400
    bl.salvar_config(cfg)
    aviso = "Salvo. Vale a partir da próxima rodada." if rodando() else "Salvo."
    return jsonify(ok=True, mensagem=aviso)


@app.post("/api/iniciar")
def iniciar():
    if rodando():
        return jsonify(ok=True)
    parar = threading.Event()
    bot = bl.Bot(parar, LOGS)
    t = threading.Thread(target=bot.rodar, daemon=True)
    ativo.update(bot=bot, thread=t, parar=parar)
    t.start()
    return jsonify(ok=True)


@app.post("/api/parar")
def parar():
    if ativo["parar"]:
        ativo["parar"].set()
    return jsonify(ok=True)


@app.get("/api/status")
def status():
    bot = ativo["bot"]
    st = dict(bot.status) if bot else {"estado": "parado", "marchas": 0, "rodadas": 0,
                                       "proxima": None, "conta_atual": None, "contas": {}}
    if not rodando():
        st["estado"] = "parado"
    st["log"] = list(LOGS)[-200:]
    return jsonify(st)


@app.get("/api/imagens")
def imagens():
    existe = lambda n: os.path.exists(os.path.join(bl.PASTA_IMG, n + ".png"))
    recursos = sorted(os.path.splitext(os.path.basename(p))[0]
                      for p in glob.glob(os.path.join(bl.PASTA_IMG, "recurso_*.png")))
    return jsonify(obrigatorias=[{"nome": n, "ok": existe(n)} for n in bl.IMAGENS_OBRIGATORIAS],
                   recursos=recursos,
                   opcionais=[{"nome": n, "uso": u, "ok": existe(n)} for n, u in bl.IMAGENS_OPCIONAIS.items()],
                   extras=sorted(os.path.splitext(os.path.basename(p))[0]
                                 for p in glob.glob(os.path.join(bl.PASTA_IMG, "*.png"))
                                 if os.path.basename(p).startswith(("nivel_", "formacao_"))))


@app.post("/api/testar")
def testar():
    dados = request.get_json(silent=True) or {}
    cfg = bl.carregar_config()
    ok, msg = bl.testar_conexao(dados.get("adb") or cfg["adb"], int(dados["porta"]))
    return jsonify(ok=ok, mensagem=msg)


@app.get("/api/estatisticas")
def estatisticas():
    dados = bl.Estatisticas().carregar()
    dias = sorted(dados, reverse=True)[:14]
    return jsonify(dias=[{"dia": d, "contas": dados[d]} for d in dias])


@app.post("/api/telegram")
def testar_telegram():
    dados = request.get_json(silent=True) or {}
    ok, msg = bl.enviar_telegram(str(dados.get("token", "")).strip(), str(dados.get("chat", "")).strip(),
                                 "Teste do Bot Lords: o aviso no Telegram está funcionando.")
    return jsonify(ok=ok, mensagem=msg)


if __name__ == "__main__":
    os.makedirs(bl.PASTA_IMG, exist_ok=True)
    bl.carregar_config()
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    app.run(host="127.0.0.1", port=8000, debug=False)
