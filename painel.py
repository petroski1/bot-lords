"""
Painel do bot. Rode:  python painel.py
e abra http://127.0.0.1:8000 no navegador (abre sozinho).
"""
import os
import glob
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


@app.post("/api/config")
def gravar_config():
    novo = request.get_json(silent=True) or {}
    try:
        cfg = bl.carregar_config()
        for chave in ("reino", "marchas_por_conta", "max_arrastos", "intervalo_min", "offset_campo"):
            cfg[chave] = int(novo[chave])
        for chave in ("confianca", "confianca_recurso"):
            cfg[chave] = max(0.5, min(0.99, float(novo[chave])))
        cfg["adb"] = str(novo["adb"]).strip()
        contas = []
        for c in novo["contas"]:
            contas.append({"nome": str(c["nome"]).strip() or "conta",
                           "porta": int(c["porta"]),
                           "castelo_x": int(c["castelo_x"]),
                           "castelo_y": int(c["castelo_y"]),
                           "ativa": bool(c.get("ativa", True))})
        cfg["contas"] = contas
    except (KeyError, ValueError, TypeError) as e:
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
                   recursos=recursos, verificacao=existe("verificacao"))


@app.post("/api/testar")
def testar():
    dados = request.get_json(silent=True) or {}
    cfg = bl.carregar_config()
    ok, msg = bl.testar_conexao(dados.get("adb") or cfg["adb"], int(dados["porta"]))
    return jsonify(ok=ok, mensagem=msg)


if __name__ == "__main__":
    os.makedirs(bl.PASTA_IMG, exist_ok=True)
    bl.carregar_config()
    threading.Timer(1.2, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    app.run(host="127.0.0.1", port=8000, debug=False)
