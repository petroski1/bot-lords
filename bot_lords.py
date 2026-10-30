"""
Bot de coleta - Lords Mobile (BlueStacks + ADB + OpenCV)

Normalmente é controlado pelo painel (python painel.py).
Também roda sozinho:
  python bot_lords.py              -> roda o bot com o config.json
  python bot_lords.py print 5555   -> salva um print da instância em tela.png
"""
import os
import re
import sys
import glob
import json
import time
import threading
import subprocess
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timedelta

import cv2
import numpy as np

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_IMG = os.path.join(PASTA, "imagens")
PASTA_LOGS = os.path.join(PASTA, "logs")
PASTA_ERROS = os.path.join(PASTA, "erros")
ARQ_CONFIG = os.path.join(PASTA, "config.json")
ARQ_ESTAT = os.path.join(PASTA, "estatisticas.json")
SEM_JANELA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
MAX_PRINTS_ERRO = 50

PADRAO = {
    "adb": r"C:\platform-tools\adb.exe",
    "reino": 1067,
    "marchas_por_conta": 2,
    "max_arrastos": 12,
    "intervalo_min": 30,
    "confianca": 0.85,
    "confianca_recurso": 0.75,
    "offset_campo": 60,
    "resolucao_base": [1280, 720],
    "pacote_jogo": "com.igg.android.lordsmobile",
    "espera_abrir_jogo": 40,
    "filas_total": 0,
    "recursos_tipos": [],
    "nivel_minimo": 1,
    "formacao": 0,
    "horarios": [],
    "ajuda_guilda": True,
    "recompensas": True,
    "prints_erro": True,
    "tailscale": True,
    "telegram_token": "",
    "telegram_chat": "",
    "telegram_resumo": False,
    "principal": {"ativo": False, "x": 0, "y": 0, "a_cada_rodadas": 4},
    "contas": [
        {"nome": "farm1", "porta": 5555, "castelo_x": 314, "castelo_y": 290, "ativa": True,
         "transportar": False, "troca": []}
    ],
}
PADRAO_CONTA = {"ativa": True, "transportar": False, "troca": []}

IMAGENS_OBRIGATORIAS = [
    "botao_mapa", "botao_castelo", "lupa", "campo_k", "campo_x", "campo_y",
    "botao_ir", "botao_coletar", "botao_marchar", "fechar_x",
]

# Recortes opcionais: cada um liga uma função extra quando está na pasta imagens.
IMAGENS_OPCIONAIS = {
    "verificacao": "Pausa a conta quando o jogo pede verificação",
    "fila_ocupada": "Ícone de marcha em andamento (conta filas livres)",
    "sem_filas": "Aviso de que não há filas livres",
    "ajuda_guilda": "Botão de ajudar a guilda na cidade",
    "recompensa": "Ícone das recompensas diárias",
    "botao_resgatar": "Botão de resgatar recompensa",
    "botao_transportar": "Botão Transportar no castelo da principal",
    "botao_max": "Botão de quantidade máxima no transporte",
    "botao_enviar": "Botão de enviar o transporte",
}


def copia(obj):
    return json.loads(json.dumps(obj))


def carregar_config():
    if not os.path.exists(ARQ_CONFIG):
        salvar_config(PADRAO)
        return copia(PADRAO)
    with open(ARQ_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in PADRAO.items():
        cfg.setdefault(k, copia(v))
    for k, v in PADRAO["principal"].items():
        cfg["principal"].setdefault(k, v)
    for conta in cfg["contas"]:
        for k, v in PADRAO_CONTA.items():
            conta.setdefault(k, copia(v))
    return cfg


def salvar_config(cfg):
    with open(ARQ_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def rodar_adb(adb, *args, texto=True):
    return subprocess.run([adb, *map(str, args)], capture_output=True,
                          text=texto, creationflags=SEM_JANELA)


def testar_conexao(adb, porta):
    serial = f"127.0.0.1:{porta}"
    try:
        rodar_adb(adb, "connect", serial)
        r = rodar_adb(adb, "devices")
    except FileNotFoundError:
        return False, "ADB não encontrado no caminho configurado"
    for linha in r.stdout.splitlines():
        partes = linha.split()
        if len(partes) == 2 and partes[0] == serial:
            if partes[1] == "device":
                return True, "Conectado"
            return False, f"Estado: {partes[1]}"
    return False, "Instância não respondeu. O BlueStacks está aberto com ADB ligado?"


def enviar_telegram(token, chat, texto):
    """Manda uma mensagem pelo bot do Telegram. Devolve (ok, mensagem)."""
    if not token or not chat:
        return False, "Token ou chat do Telegram não configurado"
    dados = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage",
                                    dados, timeout=10) as r:
            return json.load(r).get("ok", False), "Enviado"
    except Exception as e:
        return False, f"Falhou: {e}"


def info_recurso(nome):
    """recurso_minerio_lv4 -> ("minerio", 4); recurso_madeira -> ("madeira", None)."""
    m = re.fullmatch(r"recurso_(.+?)(?:_lv(\d+))?", nome)
    return (m.group(1), int(m.group(2)) if m.group(2) else None) if m else (nome, None)


def dentro_do_horario(horarios, agora=None):
    """horarios = [{"inicio": "08:00", "fim": "23:00"}]; lista vazia = sempre. Aceita virar a meia-noite."""
    if not horarios:
        return True
    agora = (agora or datetime.now()).strftime("%H:%M")
    for h in horarios:
        ini, fim = h["inicio"], h["fim"]
        if (ini <= agora < fim) if ini <= fim else (agora >= ini or agora < fim):
            return True
    return False


class Estatisticas:
    """Contadores por dia e por conta, gravados em estatisticas.json."""
    def __init__(self):
        self.trava = threading.Lock()

    def carregar(self):
        try:
            with open(ARQ_ESTAT, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def somar(self, conta, campo, n=1):
        with self.trava:
            dados = self.carregar()
            dia = dados.setdefault(datetime.now().strftime("%Y-%m-%d"), {})
            c = dia.setdefault(conta, {})
            c[campo] = c.get(campo, 0) + n
            with open(ARQ_ESTAT, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=1, ensure_ascii=False)


class Parado(Exception):
    pass


class ContaPausada(Exception):
    pass


class SemFilas(Exception):
    pass


class Bot:
    def __init__(self, parar, log=None):
        self.parar = parar
        self.logs = log if log is not None else deque(maxlen=400)
        self.cfg = carregar_config()
        self.cache = {}
        self.estat = Estatisticas()
        self.trava_log = threading.Lock()
        self.status = {"estado": "parado", "marchas": 0, "rodadas": 0,
                       "proxima": None, "conta_atual": None, "contas": {}}

    # ---------- utilidades ----------
    def log(self, msg):
        agora = datetime.now()
        linha = f"{agora:%H:%M:%S}  {msg}"
        self.logs.append(linha)
        print(linha)
        try:
            os.makedirs(PASTA_LOGS, exist_ok=True)
            with self.trava_log, open(os.path.join(PASTA_LOGS, f"{agora:%Y-%m-%d}.txt"),
                                      "a", encoding="utf-8") as f:
                f.write(linha + "\n")
        except OSError:
            pass

    def avisar(self, msg):
        """Registra e, se configurado, manda no Telegram sem travar o bot."""
        self.log(f"  ⚠ {msg}")
        if self.cfg["telegram_token"] and self.cfg["telegram_chat"]:
            threading.Thread(target=enviar_telegram, daemon=True,
                             args=(self.cfg["telegram_token"], self.cfg["telegram_chat"],
                                   f"Bot Lords: {msg}")).start()

    def checar(self):
        if self.parar.is_set():
            raise Parado()

    def dormir(self, s):
        if self.parar.wait(s):
            raise Parado()

    def imagem(self, nome, escala=1.0):
        chave = (nome, round(escala, 3))
        if chave not in self.cache:
            img = cv2.imread(os.path.join(PASTA_IMG, nome + ".png"), cv2.IMREAD_COLOR)
            if img is None:
                raise FileNotFoundError(f"Falta a imagem {nome}.png na pasta imagens")
            if abs(escala - 1) > 0.01:
                h, w = img.shape[:2]
                img = cv2.resize(img, (max(1, round(w * escala)), max(1, round(h * escala))),
                                 interpolation=cv2.INTER_AREA if escala < 1 else cv2.INTER_CUBIC)
            self.cache[chave] = img
        return self.cache[chave]

    def tem_imagem(self, nome):
        return os.path.exists(os.path.join(PASTA_IMG, nome + ".png"))

    def modelos_recurso(self):
        """Recortes de recurso que passam no filtro de tipo e nível."""
        tipos = [t.lower() for t in self.cfg["recursos_tipos"]]
        nomes = []
        for p in glob.glob(os.path.join(PASTA_IMG, "recurso_*.png")):
            nome = os.path.splitext(os.path.basename(p))[0]
            tipo, nivel = info_recurso(nome)
            if tipos and tipo.lower() not in tipos:
                continue
            if nivel is not None and nivel < self.cfg["nivel_minimo"]:
                continue
            nomes.append(nome)
        if not nomes:
            raise FileNotFoundError("Nenhuma imagem recurso_*.png que passe no filtro de tipo/nível")
        return nomes

    # ---------- fluxo do jogo ----------
    def verificar_bloqueio(self, emu, tela=None):
        """Se existir verificacao.png e ela aparecer, pausa a conta para você resolver."""
        if self.tem_imagem("verificacao") and emu.achar("verificacao", tela=tela):
            raise ContaPausada("Tela de verificação apareceu. Resolva manualmente.")

    def garantir_jogo(self, emu):
        if not emu.jogo_aberto():
            self.log("    jogo fechado, abrindo…")
            emu.abrir_jogo()

    def ir_para_mapa(self, emu):
        emu.fechar_janelas()
        if emu.achar("botao_castelo"):
            return True
        return emu.esperar_e_tocar("botao_mapa", espera_depois=3)

    def ir_para_cidade(self, emu):
        emu.fechar_janelas()
        if emu.achar("botao_mapa"):
            return True
        return emu.esperar_e_tocar("botao_castelo", espera_depois=3)

    def preencher_campo(self, emu, rotulo, valor):
        pos = emu.achar(rotulo)
        if not pos:
            self.log(f"    campo '{rotulo}' não encontrado")
            emu.salvar_erro(f"campo_{rotulo}")
            return False
        emu.tocar(pos[0] + self.cfg["offset_campo"] * emu.escala, pos[1])
        self.dormir(0.8)
        emu.apagar()
        emu.digitar(valor)
        self.dormir(0.5)
        return True

    def ir_para_coordenada(self, emu, x, y):
        if not self.ir_para_mapa(emu) or not emu.esperar_e_tocar("lupa"):
            return False
        for rotulo, valor in (("campo_k", self.cfg["reino"]), ("campo_x", x), ("campo_y", y)):
            if not self.preencher_campo(emu, rotulo, valor):
                emu.fechar_janelas()
                return False
        return emu.esperar_e_tocar("botao_ir", espera_depois=3)

    def trocar_personagem(self, emu, passos):
        """Toca, em ordem, nos recortes da lista 'troca' da conta (ex.: avatar, configuracoes, …)."""
        self.log(f"    trocando de personagem ({len(passos)} passo(s))")
        for nome in passos:
            if not emu.esperar_e_tocar(nome, tempo=15, espera_depois=2):
                raise ContaPausada(f"Troca de personagem travou em '{nome}'")
        self.dormir(self.cfg["espera_abrir_jogo"] / 2)
        emu.fechar_janelas()

    def tarefas_extras(self, emu, nome):
        """Ajuda da guilda e recompensas diárias, feitas na cidade se os recortes existirem."""
        quer_ajuda = self.cfg["ajuda_guilda"] and self.tem_imagem("ajuda_guilda")
        quer_recomp = (self.cfg["recompensas"] and self.tem_imagem("recompensa")
                       and self.tem_imagem("botao_resgatar"))
        if not (quer_ajuda or quer_recomp) or not self.ir_para_cidade(emu):
            return
        if quer_ajuda:
            ajudas = 0
            while ajudas < 5 and emu.esperar_e_tocar("ajuda_guilda", tempo=2, avisar=False):
                ajudas += 1
            if ajudas:
                self.log(f"    ajudou a guilda ({ajudas}x)")
                self.estat.somar(nome, "ajudas", ajudas)
        if quer_recomp and emu.esperar_e_tocar("recompensa", tempo=2, avisar=False):
            resgates = 0
            while resgates < 10 and emu.esperar_e_tocar("botao_resgatar", tempo=3, avisar=False):
                resgates += 1
            emu.fechar_janelas()
            if resgates:
                self.log(f"    resgatou {resgates} recompensa(s)")
                self.estat.somar(nome, "recompensas", resgates)

    def transportar(self, emu, nome):
        """Leva recursos ao castelo da conta principal."""
        p = self.cfg["principal"]
        if not all(self.tem_imagem(n) for n in ("botao_transportar", "botao_max", "botao_enviar")):
            self.log("    transporte ligado, mas faltam botao_transportar/botao_max/botao_enviar.png")
            return
        if not self.ir_para_coordenada(emu, p["x"], p["y"]):
            return
        tela = emu.print_tela()
        if tela is None:
            return
        h, w = tela.shape[:2]
        emu.tocar(w / 2, h / 2)          # depois do "Ir" o castelo fica no centro da tela
        self.dormir(1.5)
        if not emu.esperar_e_tocar("botao_transportar", tempo=5, espera_depois=2):
            emu.fechar_janelas()
            return
        for x, y in emu.achar_todos("botao_max", emu.print_tela(), self.cfg["confianca"]):
            emu.tocar(x, y)
            self.dormir(0.4)
        if emu.esperar_e_tocar("botao_enviar", tempo=5):
            self.log("    recursos enviados à conta principal")
            self.estat.somar(nome, "transportes")
        emu.fechar_janelas()

    def filas_livres(self, emu):
        """Quantas filas de marcha estão livres, ou None se não dá para saber."""
        total = self.cfg["filas_total"]
        if total <= 0 or not self.tem_imagem("fila_ocupada"):
            return None
        tela = emu.print_tela()
        if tela is None:
            return None
        ocupadas = len(emu.achar_todos("fila_ocupada", tela, self.cfg["confianca"]))
        return max(0, total - ocupadas)

    def nivel_no_popup(self, emu):
        """Lê o nível do recurso tocado comparando com nivel_1.png … nivel_9.png, se existirem."""
        tela = emu.print_tela()
        melhor, nivel = 0, None
        for n in range(1, 10):
            if self.tem_imagem(f"nivel_{n}"):
                v = emu.pontuacao(f"nivel_{n}", tela)
                if v > melhor:
                    melhor, nivel = v, n
        return nivel if melhor >= self.cfg["confianca"] else None

    def tentar_coletar(self, emu, x, y, nivel_conhecido):
        self.checar()
        emu.tocar(x, y)
        self.dormir(1.5)
        self.verificar_bloqueio(emu)
        if nivel_conhecido is None and self.cfg["nivel_minimo"] > 1:
            nivel = self.nivel_no_popup(emu)
            if nivel is not None and nivel < self.cfg["nivel_minimo"]:
                self.log(f"    recurso nível {nivel}, abaixo do mínimo")
                emu.fechar_janelas()
                return False
        if not emu.esperar_e_tocar("botao_coletar", tempo=3, avisar=False):
            emu.fechar_janelas()
            return False
        n = self.cfg["formacao"]
        if n > 0 and self.tem_imagem(f"formacao_{n}"):
            emu.esperar_e_tocar(f"formacao_{n}", tempo=4, espera_depois=0.8)
        if not emu.esperar_e_tocar("botao_marchar", tempo=6):
            semfila = self.tem_imagem("sem_filas") and emu.achar("sem_filas")
            emu.fechar_janelas()
            if semfila:
                raise SemFilas()
            return False
        if self.tem_imagem("sem_filas") and emu.achar("sem_filas"):
            emu.fechar_janelas()
            raise SemFilas()
        self.log(f"    marcha enviada (toque em {x},{y})")
        self.status["marchas"] += 1
        return True

    @staticmethod
    def caminho_espiral(passos):
        direcoes = [(1, 0), (0, 1), (-1, 0), (0, -1)]
        seq, tamanho, i = [], 1, 0
        while len(seq) < passos:
            for _ in range(2):
                seq += [direcoes[i % 4]] * tamanho
                i += 1
            tamanho += 1
        return seq[:passos]

    def coletar(self, emu, limite):
        """Procura recursos em espiral. Devolve (enviadas, tentados, filas_cheias)."""
        nomes = self.modelos_recurso()
        enviadas, tentados = 0, 0
        deslocamento = [0.0, 0.0]     # quanto o mapa andou desde o castelo, em pixels da tela
        vistos = []                   # recursos já tentados, na posição do mapa
        for passo in [None] + self.caminho_espiral(self.cfg["max_arrastos"]):
            self.checar()
            if passo:
                tela = emu.print_tela()
                if tela is None:
                    continue
                h, w = tela.shape[:2]
                dx, dy = passo
                emu.arrastar(w / 2 + dx * w * 0.3, h / 2 + dy * h * 0.3,
                             w / 2 - dx * w * 0.3, h / 2 - dy * h * 0.3)
                deslocamento[0] += dx * w * 0.6
                deslocamento[1] += dy * h * 0.6
                self.dormir(2)
            tela = emu.print_tela()
            if tela is None:
                continue
            self.verificar_bloqueio(emu, tela)
            alvos = []
            for n in nomes:
                mh, mw = self.imagem(n, emu.escala).shape[:2]
                nivel = info_recurso(n)[1]
                alvos += [(x, y, mw, mh, nivel)
                          for x, y in emu.achar_todos(n, tela, self.cfg["confianca_recurso"])]
            for x, y, mw, mh, nivel in alvos:
                mx, my = x + deslocamento[0], y + deslocamento[1]
                if any(abs(mx - vx) < mw and abs(my - vy) < mh for vx, vy in vistos):
                    continue
                vistos.append((mx, my))
                tentados += 1
                try:
                    if self.tentar_coletar(emu, x, y, nivel):
                        enviadas += 1
                        if enviadas >= limite:
                            return enviadas, tentados, False
                except SemFilas:
                    return enviadas, tentados, True
        return enviadas, tentados, False

    def processar_conta(self, conta, transporte_vez):
        nome = conta["nome"]
        self.status["conta_atual"] = nome
        self.log(f"=== Conta {nome} (porta {conta['porta']}) ===")
        emu = Emulador(self, conta["porta"], nome)
        try:
            self.garantir_jogo(emu)
            if conta["troca"]:
                self.trocar_personagem(emu, conta["troca"])
            self.tarefas_extras(emu, nome)
            if transporte_vez and conta["transportar"] and self.cfg["principal"]["ativo"]:
                self.transportar(emu, nome)
            limite = self.cfg["marchas_por_conta"]
            livres = self.filas_livres(emu)
            if livres is not None:
                self.log(f"    {livres} fila(s) livre(s)")
                limite = min(limite, livres)
            if limite <= 0:
                resultado = "Sem filas livres"
            else:
                chegou = self.ir_para_coordenada(emu, conta["castelo_x"], conta["castelo_y"])
                if not chegou:
                    self.log("    não cheguei ao castelo, reiniciando o jogo")
                    emu.reiniciar_jogo()
                    chegou = self.ir_para_coordenada(emu, conta["castelo_x"], conta["castelo_y"])
                if not chegou:
                    raise ContaPausada("Não consegui chegar ao castelo")
                enviadas, tentados, cheias = self.coletar(emu, limite)
                resultado = f"{enviadas} marcha(s), {tentados} recurso(s) vistos"
                if cheias:
                    resultado += ", filas cheias"
                if enviadas:
                    self.estat.somar(nome, "marchas", enviadas)
        except ContaPausada as e:
            resultado = f"Pausada: {e}"
            emu.salvar_erro("pausada")
            self.estat.somar(nome, "pausas")
            self.avisar(f"{nome}: {e}")
        except (Parado, FileNotFoundError):
            raise
        except Exception as e:
            resultado = f"Erro: {e}"
            self.log(f"  [erro] {e}")
            emu.salvar_erro("erro")
            self.estat.somar(nome, "erros")
            self.avisar(f"{nome}: erro {e}")
            try:
                emu.fechar_janelas()
            except Exception:
                pass
        self.estat.somar(nome, "rodadas")
        self.status["contas"][nome] = {"resultado": resultado,
                                       "hora": datetime.now().strftime("%H:%M")}
        self.log(f"  {nome}: {resultado}")
        return resultado

    def esperar_horario(self):
        avisou = False
        while not dentro_do_horario(self.cfg["horarios"]):
            if not avisou:
                self.log("Fora do horário de funcionamento, aguardando.")
                avisou = True
            self.status.update(estado="fora_do_horario", proxima=None)
            self.dormir(30)
            self.cfg = carregar_config()

    def rodar(self):
        self.log("Bot iniciado.")
        try:
            while True:
                self.cfg = carregar_config()     # mudanças do painel valem a cada rodada
                self.cache.clear()
                self.esperar_horario()
                self.status["estado"] = "rodando"
                self.status["proxima"] = None
                cada = max(1, self.cfg["principal"]["a_cada_rodadas"])
                transporte_vez = self.status["rodadas"] % cada == 0
                resumo = []
                for conta in self.cfg["contas"]:
                    if conta.get("ativa", True):
                        resumo.append(f"{conta['nome']}: {self.processar_conta(conta, transporte_vez)}")
                self.status["conta_atual"] = None
                self.status["rodadas"] += 1
                espera = self.cfg["intervalo_min"] * 60
                self.status["proxima"] = time.time() + espera
                self.status["estado"] = "aguardando"
                self.log(f"Rodada concluída. Próxima em {self.cfg['intervalo_min']} min.")
                if self.cfg["telegram_resumo"] and resumo:
                    enviar_telegram(self.cfg["telegram_token"], self.cfg["telegram_chat"],
                                    "Bot Lords, rodada concluída:\n" + "\n".join(resumo))
                self.dormir(espera)
        except Parado:
            self.log("Bot parado.")
        except FileNotFoundError as e:
            self.log(f"Bot parado: {e}")
            self.avisar(f"Bot parado: {e}")
        finally:
            self.status.update(estado="parado", conta_atual=None, proxima=None)


class Emulador:
    def __init__(self, bot, porta, nome="conta"):
        self.bot = bot
        self.nome = nome
        self.serial = f"127.0.0.1:{porta}"
        self.escala = 1.0
        self.ultima_tela = None
        rodar_adb(bot.cfg["adb"], "connect", self.serial)

    def adb(self, *args, texto=False):
        return rodar_adb(self.bot.cfg["adb"], "-s", self.serial, *args, texto=texto)

    def print_tela(self):
        r = self.adb("exec-out", "screencap", "-p")
        if not r.stdout:
            return None
        tela = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)
        if tela is not None:
            # Recortes feitos numa resolução são ajustados para a resolução atual.
            base_w = self.bot.cfg["resolucao_base"][0]
            self.escala = tela.shape[1] / base_w if base_w else 1.0
            self.ultima_tela = tela
        return tela

    def tocar(self, x, y):
        self.adb("shell", "input", "tap", int(x), int(y))

    def arrastar(self, x1, y1, x2, y2, ms=600):
        self.adb("shell", "input", "swipe", int(x1), int(y1), int(x2), int(y2), ms)

    def digitar(self, texto):
        self.adb("shell", "input", "text", texto)

    def apagar(self, vezes=8):
        # Uma chamada só com várias teclas: bem mais rápido que um adb por tecla.
        self.adb("shell", "input", "keyevent", *(["67"] * vezes))

    # ---------- jogo ----------
    def jogo_aberto(self):
        r = self.adb("shell", "pidof", self.bot.cfg["pacote_jogo"], texto=True)
        return bool(r.stdout.strip())

    def abrir_jogo(self):
        self.adb("shell", "monkey", "-p", self.bot.cfg["pacote_jogo"],
                 "-c", "android.intent.category.LAUNCHER", "1")
        self.bot.dormir(self.bot.cfg["espera_abrir_jogo"])
        self.fechar_janelas()

    def reiniciar_jogo(self):
        self.adb("shell", "am", "force-stop", self.bot.cfg["pacote_jogo"])
        self.bot.dormir(2)
        self.abrir_jogo()

    # ---------- reconhecimento ----------
    def pontuacao(self, nome, tela):
        if tela is None:
            return 0
        modelo = self.bot.imagem(nome, self.escala)
        if modelo.shape[0] > tela.shape[0] or modelo.shape[1] > tela.shape[1]:
            return 0
        return cv2.minMaxLoc(cv2.matchTemplate(tela, modelo, cv2.TM_CCOEFF_NORMED))[1]

    def achar(self, nome, confianca=None, tela=None):
        confianca = confianca or self.bot.cfg["confianca"]
        tela = tela if tela is not None else self.print_tela()
        if tela is None:
            return None
        modelo = self.bot.imagem(nome, self.escala)
        if modelo.shape[0] > tela.shape[0] or modelo.shape[1] > tela.shape[1]:
            return None
        res = cv2.matchTemplate(tela, modelo, cv2.TM_CCOEFF_NORMED)
        _, valor, _, pos = cv2.minMaxLoc(res)
        if valor < confianca:
            return None
        h, w = modelo.shape[:2]
        return (pos[0] + w // 2, pos[1] + h // 2)

    def achar_todos(self, nome, tela, confianca):
        if tela is None:
            return []
        modelo = self.bot.imagem(nome, self.escala)
        h, w = modelo.shape[:2]
        if h > tela.shape[0] or w > tela.shape[1]:
            return []
        res = cv2.matchTemplate(tela, modelo, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= confianca)
        pontos = sorted(zip(xs, ys), key=lambda p: -res[p[1], p[0]])
        achados = []
        for x, y in pontos:
            c = (int(x) + w // 2, int(y) + h // 2)
            if all(abs(c[0] - a[0]) > w // 2 or abs(c[1] - a[1]) > h // 2 for a in achados):
                achados.append(c)
        return achados

    def esperar_e_tocar(self, nome, tempo=10, espera_depois=1.5, avisar=True):
        fim = time.time() + tempo
        while time.time() < fim:
            self.bot.checar()
            pos = self.achar(nome)
            if pos:
                self.tocar(*pos)
                self.bot.dormir(espera_depois)
                return True
            self.bot.dormir(0.7)
        if avisar:
            self.bot.log(f"    não achei '{nome}'")
            self.salvar_erro(f"nao_achei_{nome}")
        return False

    def fechar_janelas(self):
        # Aceita vários estilos de X: fechar_x.png, fechar_x2.png, fechar_x_popup.png…
        nomes = sorted(os.path.splitext(os.path.basename(p))[0]
                       for p in glob.glob(os.path.join(PASTA_IMG, "fechar_x*.png"))) or ["fechar_x"]
        for _ in range(3):
            tela = self.print_tela()
            pos = next((p for p in (self.achar(n, tela=tela) for n in nomes) if p), None)
            if not pos:
                return
            self.tocar(*pos)
            self.bot.dormir(1)

    def salvar_erro(self, motivo):
        """Guarda o último print em erros/ para ver onde travou (mantém os 50 mais novos)."""
        if not self.bot.cfg["prints_erro"]:
            return
        tela = self.ultima_tela if self.ultima_tela is not None else self.print_tela()
        if tela is None:
            return
        try:
            os.makedirs(PASTA_ERROS, exist_ok=True)
            seguro = re.sub(r"[^\w-]", "_", f"{self.nome}_{motivo}")
            cv2.imwrite(os.path.join(PASTA_ERROS, f"{datetime.now():%Y%m%d_%H%M%S}_{seguro}.png"), tela)
            antigos = sorted(glob.glob(os.path.join(PASTA_ERROS, "*.png")))[:-MAX_PRINTS_ERRO]
            for p in antigos:
                os.remove(p)
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "print":
        porta = sys.argv[2] if len(sys.argv) > 2 else "5555"
        bot = Bot(threading.Event())
        img = Emulador(bot, porta).print_tela()
        if img is None:
            print("Não consegui tirar print. O BlueStacks está aberto e o ADB ligado?")
        else:
            cv2.imwrite("tela.png", img)
            print(f"Print salvo em tela.png ({img.shape[1]}x{img.shape[0]})")
    else:
        try:
            Bot(threading.Event()).rodar()
        except KeyboardInterrupt:
            pass
