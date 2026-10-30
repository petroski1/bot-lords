"""
Bot de coleta - Lords Mobile (BlueStacks + ADB + OpenCV)

Normalmente é controlado pelo painel (python painel.py).
Também roda sozinho:
  python bot_lords.py              -> roda o bot com o config.json
  python bot_lords.py print 5555   -> salva um print da instância em tela.png
"""
import os
import sys
import glob
import json
import time
import threading
import subprocess
from collections import deque
from datetime import datetime

import cv2
import numpy as np

PASTA = os.path.dirname(os.path.abspath(__file__))
PASTA_IMG = os.path.join(PASTA, "imagens")
ARQ_CONFIG = os.path.join(PASTA, "config.json")
SEM_JANELA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

PADRAO = {
    "adb": r"C:\platform-tools\adb.exe",
    "reino": 1067,
    "marchas_por_conta": 2,
    "max_arrastos": 12,
    "intervalo_min": 30,
    "confianca": 0.85,
    "confianca_recurso": 0.75,
    "offset_campo": 60,
    "contas": [
        {"nome": "farm1", "porta": 5555, "castelo_x": 314, "castelo_y": 290, "ativa": True}
    ],
}

IMAGENS_OBRIGATORIAS = [
    "botao_mapa", "botao_castelo", "lupa", "campo_k", "campo_x", "campo_y",
    "botao_ir", "botao_coletar", "botao_marchar", "fechar_x",
]


def carregar_config():
    if not os.path.exists(ARQ_CONFIG):
        salvar_config(PADRAO)
        return json.loads(json.dumps(PADRAO))
    with open(ARQ_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in PADRAO.items():
        cfg.setdefault(k, v)
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


class Parado(Exception):
    pass


class ContaPausada(Exception):
    pass


class Bot:
    def __init__(self, parar, log=None):
        self.parar = parar
        self.logs = log if log is not None else deque(maxlen=400)
        self.cfg = carregar_config()
        self.cache = {}
        self.status = {"estado": "parado", "marchas": 0, "rodadas": 0,
                       "proxima": None, "conta_atual": None, "contas": {}}

    # ---------- utilidades ----------
    def log(self, msg):
        linha = f"{datetime.now():%H:%M:%S}  {msg}"
        self.logs.append(linha)
        print(linha)

    def checar(self):
        if self.parar.is_set():
            raise Parado()

    def dormir(self, s):
        if self.parar.wait(s):
            raise Parado()

    def imagem(self, nome):
        if nome not in self.cache:
            img = cv2.imread(os.path.join(PASTA_IMG, nome + ".png"), cv2.IMREAD_COLOR)
            if img is None:
                raise FileNotFoundError(f"Falta a imagem {nome}.png na pasta imagens")
            self.cache[nome] = img
        return self.cache[nome]

    def tem_imagem(self, nome):
        return os.path.exists(os.path.join(PASTA_IMG, nome + ".png"))

    def modelos_recurso(self):
        nomes = [os.path.splitext(os.path.basename(p))[0]
                 for p in glob.glob(os.path.join(PASTA_IMG, "recurso_*.png"))]
        if not nomes:
            raise FileNotFoundError("Nenhuma imagem recurso_*.png na pasta imagens")
        return nomes

    # ---------- fluxo do jogo ----------
    def verificar_bloqueio(self, emu, tela=None):
        """Se existir verificacao.png e ela aparecer, pausa a conta para você resolver."""
        if self.tem_imagem("verificacao") and emu.achar("verificacao", tela=tela):
            raise ContaPausada("Tela de verificação apareceu. Resolva manualmente.")

    def ir_para_mapa(self, emu):
        emu.fechar_janelas()
        if emu.achar("botao_castelo"):
            return True
        return emu.esperar_e_tocar("botao_mapa", espera_depois=3)

    def preencher_campo(self, emu, rotulo, valor):
        pos = emu.achar(rotulo)
        if not pos:
            self.log(f"    campo '{rotulo}' não encontrado")
            return False
        emu.tocar(pos[0] + self.cfg["offset_campo"], pos[1])
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

    def tentar_coletar(self, emu, x, y):
        self.checar()
        emu.tocar(x, y)
        self.dormir(1.5)
        self.verificar_bloqueio(emu)
        if not emu.esperar_e_tocar("botao_coletar", tempo=3, avisar=False):
            emu.fechar_janelas()
            return False
        if not emu.esperar_e_tocar("botao_marchar", tempo=6):
            emu.fechar_janelas()
            return False
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

    def processar_conta(self, conta):
        nome = conta["nome"]
        self.status["conta_atual"] = nome
        self.log(f"=== Conta {nome} (porta {conta['porta']}) ===")
        emu = Emulador(self, conta["porta"])
        enviadas, tentados = 0, 0
        try:
            if not self.ir_para_coordenada(emu, conta["castelo_x"], conta["castelo_y"]):
                raise ContaPausada("Não consegui chegar ao castelo")
            nomes = self.modelos_recurso()
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
                    self.dormir(2)
                tela = emu.print_tela()
                if tela is None:
                    continue
                self.verificar_bloqueio(emu, tela)
                alvos = []
                for n in nomes:
                    alvos += emu.achar_todos(n, tela, self.cfg["confianca_recurso"])
                for x, y in alvos:
                    tentados += 1
                    if self.tentar_coletar(emu, x, y):
                        enviadas += 1
                        if enviadas >= self.cfg["marchas_por_conta"]:
                            raise StopIteration
            resultado = f"{enviadas} marcha(s), {tentados} recurso(s) vistos"
        except StopIteration:
            resultado = f"{enviadas} marcha(s) enviadas"
        except ContaPausada as e:
            resultado = f"Pausada: {e}"
            self.log(f"  ⚠ {nome}: {e}")
        except (Parado, FileNotFoundError):
            raise
        except Exception as e:
            resultado = f"Erro: {e}"
            self.log(f"  [erro] {e}")
            try:
                emu.fechar_janelas()
            except Exception:
                pass
        self.status["contas"][nome] = {"resultado": resultado,
                                       "hora": datetime.now().strftime("%H:%M")}
        self.log(f"  {nome}: {resultado}")

    def rodar(self):
        self.log("Bot iniciado.")
        try:
            while True:
                self.cfg = carregar_config()     # mudanças do painel valem a cada rodada
                self.cache.clear()
                self.status["estado"] = "rodando"
                self.status["proxima"] = None
                for conta in self.cfg["contas"]:
                    if conta.get("ativa", True):
                        self.processar_conta(conta)
                self.status["conta_atual"] = None
                self.status["rodadas"] += 1
                espera = self.cfg["intervalo_min"] * 60
                self.status["proxima"] = time.time() + espera
                self.status["estado"] = "aguardando"
                self.log(f"Rodada concluída. Próxima em {self.cfg['intervalo_min']} min.")
                self.dormir(espera)
        except Parado:
            self.log("Bot parado.")
        except FileNotFoundError as e:
            self.log(f"Bot parado: {e}")
        finally:
            self.status.update(estado="parado", conta_atual=None, proxima=None)


class Emulador:
    def __init__(self, bot, porta):
        self.bot = bot
        self.serial = f"127.0.0.1:{porta}"
        rodar_adb(bot.cfg["adb"], "connect", self.serial)

    def adb(self, *args, texto=False):
        return rodar_adb(self.bot.cfg["adb"], "-s", self.serial, *args, texto=texto)

    def print_tela(self):
        r = self.adb("exec-out", "screencap", "-p")
        if not r.stdout:
            return None
        return cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR)

    def tocar(self, x, y):
        self.adb("shell", "input", "tap", int(x), int(y))

    def arrastar(self, x1, y1, x2, y2, ms=600):
        self.adb("shell", "input", "swipe", int(x1), int(y1), int(x2), int(y2), ms)

    def digitar(self, texto):
        self.adb("shell", "input", "text", texto)

    def apagar(self, vezes=8):
        for _ in range(vezes):
            self.adb("shell", "input", "keyevent", 67)

    def achar(self, nome, confianca=None, tela=None):
        confianca = confianca or self.bot.cfg["confianca"]
        tela = tela if tela is not None else self.print_tela()
        if tela is None:
            return None
        modelo = self.bot.imagem(nome)
        res = cv2.matchTemplate(tela, modelo, cv2.TM_CCOEFF_NORMED)
        _, valor, _, pos = cv2.minMaxLoc(res)
        if valor < confianca:
            return None
        h, w = modelo.shape[:2]
        return (pos[0] + w // 2, pos[1] + h // 2)

    def achar_todos(self, nome, tela, confianca):
        modelo = self.bot.imagem(nome)
        h, w = modelo.shape[:2]
        res = cv2.matchTemplate(tela, modelo, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= confianca)
        pontos = sorted(zip(xs, ys), key=lambda p: -res[p[1], p[0]])
        achados = []
        for x, y in pontos:
            c = (x + w // 2, y + h // 2)
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
        return False

    def fechar_janelas(self):
        for _ in range(3):
            pos = self.achar("fechar_x")
            if not pos:
                return
            self.tocar(*pos)
            self.bot.dormir(1)


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
