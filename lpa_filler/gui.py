"""Janela gráfica do lpa_filler — aspeto Exceltic.

Mesma lógica de sempre (corre ``cli.main`` dentro do processo, sem terminal à
vista). Só o aspeto mudou: fundo branco, régua laranja, os passos como fluxo com
estado (feito / seguinte / em espera) em vez de cinco botões iguais.

Para mudar o aspeto, ver PALETA e ``assets/logo.png`` — nada mais depende delas.
"""
from __future__ import annotations

import csv
import queue
import sys
import threading
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import pipeline
from .pipeline import Config

# --------------------------------------------------------------------------- #
# Aspeto Exceltic: uma cor de marca (laranja), branco, cinzas e réguas.

PALETA = {
    "marca": "#F15722",
    "marca_escura": "#D94E14",
    "marca_clara": "#FDE7D9",
    "fundo": "#F2F2F2",
    "cartao": "#FFFFFF",
    "texto": "#1A1A1A",
    "texto_2": "#4A4A4A",
    "apagado": "#7A7A7A",
    "linha": "#C1C2C4",
    "bom": "#2E7D4F",
    "aviso": "#C98A1C",
    "mau": "#C62828",
    "consola_fundo": "#12181F",
    "consola_texto": "#E4E8EC",
}

MARCA = "EXCELTIC"
TITULO = "AUTOMATIZACIÓN DE LPA"
SUBTITULO = "Listado de Puntos Abiertos · RAMS & Validación"

FONTE = "Arial"


def _recurso(nome: str) -> Path:
    """Caminho de um recurso, dentro do .exe (``sys._MEIPASS``) ou no repositório."""
    base = getattr(sys, "_MEIPASS", None)
    raiz = Path(base) if base else Path(__file__).resolve().parent.parent
    return raiz / nome


def _pasta_app() -> Path:
    """Pasta onde vivem os dados do próprio programa (a base de hallazgos).

    Não pode ser ``sys._MEIPASS``: essa é a pasta temporária onde o PyInstaller
    descomprime o .exe a cada arranque — só de leitura, e apagada ao fechar. A
    base tem de sobreviver e crescer, por isso fica ao lado do executável (ou,
    a correr da fonte, na raiz do repositório)."""
    if getattr(sys, "_MEIPASS", None):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_PADRAO = "base_hallazgos.csv"


# --------------------------------------------------------------------------- #


class _Escritor:
    """Encaminha o que os comandos imprimem para a consola da janela, linha a linha."""

    def __init__(self, fila: queue.Queue) -> None:
        self._fila = fila
        self._resto = ""

    def write(self, texto: str) -> int:
        self._resto += texto
        while "\n" in self._resto:
            linha, self._resto = self._resto.split("\n", 1)
            self._fila.put(("linha", linha))
        return len(texto)

    def flush(self) -> None:
        if self._resto:
            self._fila.put(("linha", self._resto))
            self._resto = ""


# Âncoras de cor da consola. Aceitam as duas línguas de propósito: as mensagens
# passaram a espanhol, mas basta um `print` esquecido em português — ou um
# ficheiro por traduzir — para um aviso deixar de ser âmbar sem ninguém reparar.
_MAU = ("✗", "Erro", "erro:", "Error", "error:", "Traceback")
_BOM = ("Escrito:", "Gerado:", "Generado:", "==", "✓")
_AVISO = ("ATENÇÃO", "ATENCIÓN")


def _classificar(linha: str) -> str:
    """Etiqueta de cor a partir do conteúdo — os comandos escrevem nos dois canais."""
    t = linha.strip()
    if not t:
        return "normal"
    if t.startswith(_MAU):
        return "mau"
    if t.startswith(("!", "?")) or any(a in t for a in _AVISO):
        return "aviso"
    if t.startswith(_BOM):
        return "bom"
    if t.startswith("#"):
        return "apagado"
    return "normal"


class _CartaoPasso(tk.Frame):
    """Um passo do fluxo: número, estado, título e descrição. Clicável."""

    def __init__(self, pai: tk.Widget, indice: int, passo, correr) -> None:
        super().__init__(pai, bg=PALETA["linha"])
        self._indice = indice
        self._correr = correr
        self._estado = "espera"

        self._dentro = tk.Frame(self, bg=PALETA["cartao"])
        self._dentro.pack(fill="both", expand=True, padx=1, pady=1)

        topo = tk.Frame(self._dentro, bg=PALETA["cartao"])
        topo.pack(fill="x", padx=10, pady=(10, 0))
        self._num = tk.Label(topo, text=str(indice), width=2, height=1,
                             font=(FONTE, 9, "bold"), bg=PALETA["cartao"],
                             fg=PALETA["apagado"], relief="solid", bd=1)
        self._num.pack(side="left")
        self._etiqueta = tk.Label(topo, text="EN ESPERA", font=(FONTE, 7, "bold"),
                                  bg=PALETA["cartao"], fg=PALETA["apagado"])
        self._etiqueta.pack(side="right")

        self._titulo = tk.Label(self._dentro, text=passo.titulo.split("·", 1)[-1].strip(),
                                font=(FONTE, 9, "bold"), bg=PALETA["cartao"],
                                fg=PALETA["texto_2"], wraplength=150, justify="left",
                                anchor="w")
        self._titulo.pack(fill="x", padx=10, pady=(8, 2))

        self._desc = tk.Label(self._dentro, text=passo.descricao, font=(FONTE, 7),
                              bg=PALETA["cartao"], fg=PALETA["apagado"],
                              wraplength=150, justify="left", anchor="nw")
        self._desc.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        for w in (self, self._dentro, topo, self._num, self._etiqueta,
                  self._titulo, self._desc):
            w.bind("<Button-1>", lambda _e: self._correr(self._indice))
            w.configure(cursor="hand2")

    def _pintar(self, fundo: str, borda: str, num_fundo: str, num_cor: str,
                etiqueta: str, etiqueta_cor: str, titulo_cor: str, num_texto: str) -> None:
        self.configure(bg=borda)
        for w in (self._dentro, self._titulo, self._desc, self._num.master):
            w.configure(bg=fundo)
        self._num.configure(text=num_texto, bg=num_fundo, fg=num_cor)
        self._etiqueta.configure(text=etiqueta, fg=etiqueta_cor, bg=fundo)
        self._titulo.configure(fg=titulo_cor, bg=fundo)
        self._desc.configure(bg=fundo)

    def estado(self, estado: str) -> None:
        self._estado = estado
        if estado == "feito":
            self._pintar(PALETA["cartao"], PALETA["linha"], PALETA["bom"], "#FFFFFF",
                         "HECHO", PALETA["bom"], PALETA["texto"], "✓")
        elif estado == "correr":
            self._pintar(PALETA["marca_clara"], PALETA["marca"], PALETA["marca"],
                         "#FFFFFF", "CORRIENDO", PALETA["marca_escura"], PALETA["texto"],
                         str(self._indice))
        elif estado == "seguinte":
            self._pintar(PALETA["marca_clara"], PALETA["marca"], PALETA["marca"],
                         "#FFFFFF", "SIGUIENTE", PALETA["marca_escura"], PALETA["texto"],
                         str(self._indice))
        elif estado == "dispensavel":
            # Continua clicável: não é proibido, é só desnecessário aqui.
            self._pintar(PALETA["cartao"], PALETA["linha"], PALETA["cartao"],
                         PALETA["apagado"], "PRESCINDIBLE", PALETA["apagado"],
                         PALETA["apagado"], str(self._indice))
        else:
            self._pintar(PALETA["cartao"], PALETA["linha"], PALETA["cartao"],
                         PALETA["apagado"], "EN ESPERA", PALETA["apagado"],
                         PALETA["texto_2"], str(self._indice))


class Janela(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{MARCA} · LPA")
        self.geometry("1240x820")
        self.minsize(1060, 700)
        self.configure(bg=PALETA["fundo"])

        icone = _recurso("assets/logo.ico")
        if icone.exists():
            try:
                self.iconbitmap(str(icone))
            except tk.TclError:
                pass

        self._fila: queue.Queue = queue.Queue()
        self._a_correr = False
        self._campos: dict[str, tk.StringVar] = {}
        self._cartoes: dict[int, _CartaoPasso] = {}
        self._feitos = 0

        self._estilos()
        self._cabecalho()

        corpo = tk.Frame(self, bg=PALETA["linha"])
        corpo.pack(fill="both", expand=True)
        grelha = tk.Frame(corpo, bg=PALETA["cartao"])
        grelha.pack(fill="both", expand=True)
        grelha.columnconfigure(0, minsize=392)
        grelha.columnconfigure(1, weight=1)
        grelha.rowconfigure(0, weight=1)

        esquerda = tk.Frame(grelha, bg=PALETA["cartao"], highlightthickness=0)
        esquerda.grid(row=0, column=0, sticky="nsew")
        tk.Frame(grelha, bg=PALETA["linha"], width=1).grid(row=0, column=0, sticky="nse")
        self._coluna_entradas(esquerda)

        direita = tk.Frame(grelha, bg=PALETA["cartao"])
        direita.grid(row=0, column=1, sticky="nsew")
        self._painel_fluxo(direita)
        self._painel_consola(direita)

        self._marcar_passos()
        self._atualizar_contagem_base()
        self._escrever(f"{MARCA} · listo.", "bom")
        self._escrever("Elige las entradas a la izquierda y ejecuta los pasos en orden.", "apagado")
        self.after(60, self._drenar)

    # ---------------------------------------------------------------- aspeto
    def _estilos(self) -> None:
        e = ttk.Style(self)
        try:
            e.theme_use("clam")
        except tk.TclError:
            pass
        e.configure("TFrame", background=PALETA["cartao"])
        e.configure("TLabel", background=PALETA["cartao"], foreground=PALETA["texto"])
        e.configure("TCheckbutton", background=PALETA["cartao"], foreground=PALETA["texto"])
        e.map("TCheckbutton", background=[("active", PALETA["cartao"])])
        e.configure("Marca.TButton", background=PALETA["marca"], foreground="#FFFFFF",
                    padding=(20, 10), borderwidth=0, font=(FONTE, 9, "bold"))
        e.map("Marca.TButton",
              background=[("active", PALETA["marca_escura"]), ("disabled", PALETA["linha"])],
              foreground=[("disabled", PALETA["apagado"])])
        e.configure("Contorno.TButton", background=PALETA["cartao"], foreground=PALETA["marca"],
                    padding=(14, 10), borderwidth=1, font=(FONTE, 9, "bold"))
        e.map("Contorno.TButton", background=[("active", PALETA["marca_clara"])])
        e.configure("Procurar.TButton", background=PALETA["cartao"], foreground=PALETA["marca"],
                    padding=(9, 4), borderwidth=1, font=(FONTE, 8, "bold"))
        e.map("Procurar.TButton", background=[("active", PALETA["marca_clara"])])
        e.configure("Marca.Horizontal.TProgressbar", background=PALETA["marca"],
                    troughcolor=PALETA["fundo"], borderwidth=0, thickness=6)

    def _cabecalho(self) -> None:
        barra = tk.Frame(self, bg=PALETA["cartao"], height=68)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        caixa = tk.Frame(barra, bg=PALETA["cartao"])
        caixa.pack(side="left", padx=20)
        logo = _recurso("assets/logo.png")
        posto = False
        if logo.exists():
            try:
                self._logo = tk.PhotoImage(file=str(logo))
                tk.Label(caixa, image=self._logo, bg=PALETA["cartao"]).pack(side="left")
                posto = True
            except tk.TclError:
                posto = False
        if not posto:
            tk.Label(caixa, text=MARCA, bg=PALETA["cartao"], fg=PALETA["texto"],
                     font=(FONTE, 17, "bold")).pack(side="left")

        tk.Frame(barra, bg=PALETA["linha"], width=1, height=30).pack(side="left", padx=(0, 16))
        titulos = tk.Frame(barra, bg=PALETA["cartao"])
        titulos.pack(side="left")
        tk.Label(titulos, text=TITULO, bg=PALETA["cartao"], fg=PALETA["texto"],
                 font=(FONTE, 11, "bold")).pack(anchor="w")
        tk.Label(titulos, text=SUBTITULO, bg=PALETA["cartao"], fg=PALETA["apagado"],
                 font=(FONTE, 8)).pack(anchor="w")

        self._estado = tk.Label(barra, text="● Listo", bg=PALETA["cartao"],
                                fg=PALETA["bom"], font=(FONTE, 8))
        self._estado.pack(side="right", padx=20)

        tk.Frame(self, bg=PALETA["marca"], height=3).pack(fill="x")

    def _secao(self, pai: tk.Widget, titulo: str) -> tk.Frame:
        tk.Label(pai, text=titulo.upper(), bg=PALETA["cartao"], fg=PALETA["apagado"],
                 font=(FONTE, 8, "bold")).pack(anchor="w", padx=20, pady=(16, 8))
        corpo = tk.Frame(pai, bg=PALETA["cartao"])
        corpo.pack(fill="x", padx=20)
        return corpo

    def _regua(self, pai: tk.Widget) -> None:
        tk.Frame(pai, bg=PALETA["linha"], height=1).pack(fill="x", padx=20, pady=(16, 0))

    # -------------------------------------------------------------- entradas
    def _linha_caminho(self, pai: tk.Widget, chave: str, rotulo: str, tipo: str, escolher) -> None:
        cabeca = tk.Frame(pai, bg=PALETA["cartao"])
        cabeca.pack(fill="x")
        tk.Label(cabeca, text=rotulo, bg=PALETA["cartao"], fg=PALETA["texto"],
                 font=(FONTE, 9, "bold")).pack(side="left")
        tk.Label(cabeca, text=tipo.upper(), bg=PALETA["cartao"], fg=PALETA["apagado"],
                 font=(FONTE, 7)).pack(side="left", padx=(8, 0))

        fila = tk.Frame(pai, bg=PALETA["cartao"])
        fila.pack(fill="x", pady=(3, 11))
        var = tk.StringVar()
        self._campos[chave] = var
        moldura = tk.Frame(fila, bg=PALETA["linha"])
        moldura.pack(side="left", fill="x", expand=True)
        interior = tk.Frame(moldura, bg=PALETA["cartao"])
        interior.pack(fill="x", padx=1, pady=1)
        marca = tk.Label(interior, text="!", bg=PALETA["cartao"], fg=PALETA["aviso"],
                         font=(FONTE, 9, "bold"), width=2)
        marca.pack(side="left")
        tk.Entry(interior, textvariable=var, relief="flat", bd=0, bg=PALETA["cartao"],
                 fg=PALETA["texto"], font=(FONTE, 9)).pack(side="left", fill="x",
                                                           expand=True, ipady=4)

        def ao_mudar(*_a: object) -> None:
            cheio = bool(var.get().strip())
            marca.configure(text="✓" if cheio else "!",
                            fg=PALETA["bom"] if cheio else PALETA["aviso"])
            moldura.configure(bg=PALETA["linha"] if cheio else PALETA["aviso"])

        var.trace_add("write", ao_mudar)
        ttk.Button(fila, text="Buscar", style="Procurar.TButton",
                   command=lambda: self._escolher(var, escolher)).pack(side="left", padx=(6, 0))

    def _escolher(self, var: tk.StringVar, escolher) -> None:
        caminho = escolher()
        if caminho:
            var.set(caminho)

    def _linha_texto(self, pai: tk.Widget, chave: str, rotulo: str, dica: str) -> None:
        tk.Label(pai, text=rotulo, bg=PALETA["cartao"], fg=PALETA["texto"],
                 font=(FONTE, 9, "bold")).pack(anchor="w")
        var = tk.StringVar()
        self._campos[chave] = var
        tk.Entry(pai, textvariable=var, relief="solid", bd=1, bg=PALETA["cartao"],
                 fg=PALETA["texto"], font=(FONTE, 9)).pack(fill="x", ipady=4, pady=(3, 2))
        tk.Label(pai, text=dica, bg=PALETA["cartao"], fg=PALETA["apagado"],
                 font=(FONTE, 7), wraplength=340, justify="left").pack(anchor="w", pady=(0, 10))

    def _coluna_entradas(self, pai: tk.Widget) -> None:
        c = self._secao(pai, "Qué vas a hacer")
        self._revisao = tk.BooleanVar(value=False)
        ttk.Checkbutton(c, text="Revisión de un LPA ya existente",
                        variable=self._revisao,
                        command=self._modo_mudou).pack(anchor="w")
        self._nota_modo = tk.Label(
            c, text="Desactivado: LPA nuevo, montado a partir del PES.",
            bg=PALETA["cartao"], fg=PALETA["apagado"], font=(FONTE, 7),
            wraplength=340, justify="left")
        self._nota_modo.pack(anchor="w", pady=(3, 10))

        c = self._secao(pai, "Entradas")
        self._linha_caminho(c, "pes", "Informe PES", ".docx",
                            lambda: filedialog.askopenfilename(
                                title="Informe PES",
                                filetypes=[("Word", "*.docx"), ("Todos", "*.*")]))
        self._linha_caminho(c, "lpa_existente", "LPA anterior", ".xlsm",
                            lambda: filedialog.askopenfilename(
                                title="LPA ya emitido (para arrancar la revisión)",
                                filetypes=[("Excel con macros", "*.xlsm"), ("Todos", "*.*")]))
        self._linha_caminho(c, "recibida", "Documentos recibidos", "carpeta",
                            lambda: filedialog.askdirectory(title="Doc Recibida"))
        self._linha_caminho(c, "base", "Base de hallazgos", ".csv",
                            lambda: filedialog.askopenfilename(
                                title="Base de hallazgos",
                                filetypes=[("CSV", "*.csv"), ("Todos", "*.*")]))
        # Vive dentro do aplicativo: não se procura toda vez, só se muda quem
        # quiser apontar a outra. O botão ao lado é quem a faz crescer.
        self._campos["base"].set(str(_pasta_app() / BASE_PADRAO))
        fila_base = tk.Frame(c, bg=PALETA["cartao"])
        fila_base.pack(fill="x", pady=(0, 11))
        ttk.Button(fila_base, text="+ Añadir LPA a la base", style="Procurar.TButton",
                   command=self._adicionar_a_base).pack(side="left")
        self._contagem_base = tk.Label(fila_base, text="", bg=PALETA["cartao"],
                                       fg=PALETA["apagado"], font=(FONTE, 7))
        self._contagem_base.pack(side="left", padx=(10, 0))
        self._linha_caminho(c, "template", "Plantilla LPA", ".xlsm",
                            lambda: filedialog.askopenfilename(
                                title="Plantilla LPA",
                                filetypes=[("Excel con macros", "*.xlsm"), ("Todos", "*.*")]))
        self._linha_caminho(c, "trabalho", "Carpeta de trabajo", "carpeta",
                            lambda: filedialog.askdirectory(title="Carpeta de trabajo"))

        self._regua(pai)
        c = self._secao(pai, "Contexto de la obra")
        self._linha_texto(c, "solicitante", "Solicitante", "Quién hace los envíos. Ej.: ADIF")
        self._linha_texto(c, "scope", "Anclas de esta obra",
                          "Separadas por coma. Ej.: Sant Vicenç de Calders, TRAMO 2")
        self._linha_texto(c, "excluir_obra", "Código de esta obra",
                          "Ej.: EXC2026-18042. Evita sugerir a partir de la propia respuesta.")

        self._regua(pai)
        c = self._secao(pai, "Exigencia de las sugerencias")
        fila = tk.Frame(c, bg=PALETA["cartao"])
        fila.pack(fill="x")
        self._min_score = tk.DoubleVar(value=12.0)
        valor = tk.Label(fila, text="12", bg=PALETA["cartao"], fg=PALETA["texto"],
                         font=(FONTE, 10, "bold"), width=4, relief="solid", bd=1)
        valor.pack(side="right", padx=(10, 0))
        tk.Scale(fila, from_=0, to=60, resolution=2, orient="horizontal",
                 variable=self._min_score, showvalue=False, bg=PALETA["cartao"],
                 troughcolor=PALETA["fundo"], activebackground=PALETA["marca"],
                 highlightthickness=0, bd=0, sliderrelief="flat",
                 command=lambda v: valor.configure(text=str(int(float(v))))
                 ).pack(side="left", fill="x", expand=True)
        tk.Label(c, text="Más alto = menos sugerencias, pero más parecidas. 12 es un buen punto de partida.",
                 bg=PALETA["cartao"], fg=PALETA["apagado"], font=(FONTE, 7),
                 wraplength=340, justify="left").pack(anchor="w", pady=(6, 10))

        # Desligada por omissão: o normal é querer os puntos na folha. Ligada por
        # omissão, cada LPA saía com a aba vazia e só se dava por isso ao abrir o
        # Excel — as sugestões estavam no projeto e no Anejo, mas não no LPA.
        self._skip_lpa = tk.BooleanVar(value=False)
        ttk.Checkbutton(c, text="Dejar la pestaña LPA vacía para completar a mano",
                        variable=self._skip_lpa,
                        command=self._modo_mudou).pack(anchor="w")
        self._sugerir = tk.BooleanVar(value=True)
        ttk.Checkbutton(c, text="Proponer hallazgos del histórico (paso 3)",
                        variable=self._sugerir,
                        command=self._modo_mudou).pack(anchor="w", pady=(3, 0))
        self._substituir = tk.BooleanVar(value=False)
        ttk.Checkbutton(c, text="Al sugerir, sustituir las sugerencias anteriores",
                        variable=self._substituir).pack(anchor="w", pady=(3, 16))

    # ----------------------------------------------------------------- fluxo
    def _painel_fluxo(self, pai: tk.Widget) -> None:
        topo = tk.Frame(pai, bg=PALETA["cartao"])
        topo.pack(fill="x", padx=22, pady=(16, 0))
        tk.Label(topo, text="FLUJO", bg=PALETA["cartao"], fg=PALETA["apagado"],
                 font=(FONTE, 8, "bold")).pack(side="left")
        self._resumo = tk.Label(topo, text="0 de 5 pasos completados", bg=PALETA["cartao"],
                                fg=PALETA["apagado"], font=(FONTE, 8))
        self._resumo.pack(side="left", padx=(12, 0))

        cartoes = tk.Frame(pai, bg=PALETA["cartao"])
        cartoes.pack(fill="x", padx=22, pady=(10, 0))
        for i, p in enumerate(pipeline.PASSOS, start=1):
            cartoes.columnconfigure(i - 1, weight=1, uniform="passo")
            cartao = _CartaoPasso(cartoes, i, p, self._correr_indice)
            cartao.grid(row=0, column=i - 1, sticky="nsew", padx=(0 if i == 1 else 5, 0))
            self._cartoes[i] = cartao

        acoes = tk.Frame(pai, bg=PALETA["cartao"])
        acoes.pack(fill="x", padx=22, pady=(14, 0))
        self._botao = ttk.Button(acoes, text="EJECUTAR PASO 1", style="Marca.TButton",
                                 command=lambda: self._correr_indice(self._seguinte()))
        self._botao.pack(side="left")
        ttk.Button(acoes, text="ABRIR CARPETA", style="Contorno.TButton",
                   command=self._abrir_pasta).pack(side="left", padx=(8, 0))

        tk.Label(acoes, text="PROGRESO", bg=PALETA["cartao"], fg=PALETA["apagado"],
                 font=(FONTE, 7, "bold")).pack(side="left", padx=(24, 8))
        self._progresso = ttk.Progressbar(acoes, style="Marca.Horizontal.TProgressbar",
                                          length=180, maximum=len(pipeline.PASSOS))
        self._progresso.pack(side="left")
        self._percent = tk.Label(acoes, text="0%", bg=PALETA["cartao"], fg=PALETA["texto_2"],
                                 font=(FONTE, 8, "bold"))
        self._percent.pack(side="left", padx=(8, 0))

        tk.Frame(pai, bg=PALETA["linha"], height=1).pack(fill="x", pady=(16, 0))

    def _seguinte(self) -> int:
        """O passo a seguir — sempre o próximo, mesmo que esteja dispensável.

        Já saltou os dispensáveis automaticamente, e o resultado foi um LPA com
        0 puntos sem um único erro na consola: quem carregava no botão passava
        de 'analisar' para 'gerar' sem reparar que nunca chegou a sugerir nada.
        A etiqueta PRESCINDIBLE informa; quem decide saltar é quem carrega no
        cartão seguinte."""
        return min(self._feitos + 1, len(pipeline.PASSOS))

    def _marcar_passos(self) -> None:
        cfg = self._config()
        seguinte = self._seguinte()
        dispensaveis = 0
        for i, cartao in self._cartoes.items():
            opcional = pipeline.PASSOS[i - 1].opcional(cfg)
            if i <= self._feitos:
                cartao.estado("feito")
            elif i == seguinte:
                cartao.estado("correr" if self._a_correr else "seguinte")
            elif opcional:
                cartao.estado("dispensavel")
                dispensaveis += 1
            else:
                cartao.estado("espera")
        total = len(pipeline.PASSOS)
        resumo = f"{self._feitos} de {total} pasos completados"
        if dispensaveis:
            resumo += f" · {dispensaveis} prescindibles con la pestaña LPA vacía"
        self._resumo.configure(text=resumo)
        self._progresso.configure(value=self._feitos)
        self._percent.configure(text=f"{round(self._feitos / total * 100)}%")
        self._botao.configure(text=f"EJECUTAR PASO {seguinte}")

    def _modo_mudou(self) -> None:
        """Reage às caixas que mudam o fluxo (revisão, aba LPA vazia)."""
        if self._revisao.get():
            self._nota_modo.configure(
                text="Añade el envío nuevo al proyecto de esta carpeta y registra la "
                     "revisión, sin tocar los puntos. Si aún no hay projeto.yaml "
                     "aquí, indica el LPA anterior (.xlsm) para arrancar de él.")
        else:
            self._nota_modo.configure(
                text="Desactivado: LPA nuevo, montado a partir del PES.")
        self._marcar_passos()

    def _abrir_pasta(self) -> None:
        import subprocess

        pasta = self._campos["trabalho"].get().strip() or self._campos["pes"].get().strip()
        if not pasta:
            messagebox.showinfo("Sin carpeta", "Elige primero la carpeta de trabajo.")
            return
        caminho = Path(pasta)
        caminho = caminho if caminho.is_dir() else caminho.parent
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(caminho)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(caminho)])
            else:
                subprocess.Popen(["xdg-open", str(caminho)])
        except OSError as e:
            messagebox.showwarning("No se pudo", str(e))

    # -------------------------------------------------------------- consola
    def _painel_consola(self, pai: tk.Widget) -> None:
        fora = tk.Frame(pai, bg=PALETA["consola_fundo"])
        fora.pack(fill="both", expand=True)

        topo = tk.Frame(fora, bg=PALETA["consola_fundo"])
        topo.pack(fill="x", padx=22, pady=(12, 4))
        tk.Label(topo, text="QUÉ ESTÁ PASANDO", bg=PALETA["consola_fundo"],
                 fg="#7C8B99", font=(FONTE, 8, "bold")).pack(side="left")
        tk.Button(topo, text="Limpiar", command=self._limpar, relief="flat",
                  bg=PALETA["consola_fundo"], fg="#7C8B99",
                  activebackground=PALETA["consola_fundo"], activeforeground=PALETA["marca"],
                  font=(FONTE, 8), bd=0, cursor="hand2").pack(side="right")

        moldura = tk.Frame(fora, bg=PALETA["consola_fundo"])
        moldura.pack(fill="both", expand=True, padx=22, pady=(0, 16))
        barra = tk.Scrollbar(moldura)
        barra.pack(side="right", fill="y")
        self._consola = tk.Text(moldura, wrap="word", relief="flat",
                                bg=PALETA["consola_fundo"], fg=PALETA["consola_texto"],
                                insertbackground=PALETA["consola_texto"],
                                font=("Consolas", 9), yscrollcommand=barra.set,
                                padx=0, pady=4)
        self._consola.pack(fill="both", expand=True)
        barra.config(command=self._consola.yview)
        for etiqueta, cor in (("normal", PALETA["consola_texto"]), ("apagado", "#8A98A5"),
                              ("bom", "#6FD08C"), ("aviso", "#E8B457"), ("mau", "#F0796B")):
            self._consola.tag_config(etiqueta, foreground=cor)
        self._consola.tag_config("titulo", foreground="#FFFFFF", font=("Consolas", 9, "bold"))
        self._consola.config(state="disabled")

    def _escrever(self, texto: str, etiqueta: str = "normal") -> None:
        self._consola.config(state="normal")
        self._consola.insert("end", texto + "\n", etiqueta)
        self._consola.see("end")
        self._consola.config(state="disabled")

    def _limpar(self) -> None:
        self._consola.config(state="normal")
        self._consola.delete("1.0", "end")
        self._consola.config(state="disabled")

    # ---------------------------------------------------------------- correr
    def _config(self) -> Config:
        def caminho(chave: str) -> Path | None:
            valor = self._campos[chave].get().strip()
            return Path(valor) if valor else None

        trabalho = caminho("trabalho")
        if trabalho is None:
            pes = caminho("pes")
            trabalho = pes.parent if pes else Path.cwd()

        return Config(
            trabalho=trabalho,
            pes=caminho("pes"),
            recibida=caminho("recibida"),
            base=caminho("base"),
            template=caminho("template"),
            solicitante=self._campos["solicitante"].get().strip(),
            scope=self._campos["scope"].get().strip(),
            excluir_obra=self._campos["excluir_obra"].get().strip(),
            min_score=float(self._min_score.get()),
            skip_lpa=bool(self._skip_lpa.get()),
            sugerir=bool(self._sugerir.get()),
            substituir_sugestoes=bool(self._substituir.get()),
            revisao=bool(self._revisao.get()),
            lpa_existente=caminho("lpa_existente"),
        )

    def _correr_indice(self, indice: int) -> None:
        self._correr(pipeline.PASSOS[indice - 1].chave, indice)

    def _correr(self, chave: str, indice: int) -> None:
        if self._a_correr:
            return
        passo = pipeline.passo(chave)
        cfg = self._config()

        falta = passo.em_falta(cfg)
        if falta:
            messagebox.showwarning(
                "Falta completar",
                f"Para ejecutar «{passo.titulo}» falta:\n\n• " + "\n• ".join(falta),
            )
            return

        if chave == "preparar":
            # Numa revisão o 'update' preserva os puntos; só o 'merge' os apaga.
            n = pipeline.preparar_apaga_puntos(cfg)
            if n and not messagebox.askyesno(
                "Ya existe un proyecto",
                f"El projeto.yaml de esta carpeta ya tiene {n} punto(s).\n\n"
                "Volver a preparar los borra y empieza de cero.\n\n"
                "Si querías añadir un envío nuevo a este LPA, cancela y activa "
                "«Revisión de un LPA ya existente».\n\n¿Continuar?",
                icon="warning",
            ):
                return

        cfg.trabalho.mkdir(parents=True, exist_ok=True)
        self._lancar(passo.comandos(cfg), passo.titulo, indice)

    def _adicionar_a_base(self) -> None:
        """Lê um ou mais LPA .xlsm e acrescenta os hallazgos à base — sem passar
        pelo fluxo dos 5 passos: é manutenção da base, não parte de um projeto."""
        if self._a_correr:
            return
        caminhos = filedialog.askopenfilenames(
            title="Elegir uno o más LPA (.xlsm) para añadir a la base",
            filetypes=[("Excel con macros", "*.xlsm"), ("Todos", "*.*")],
        )
        if not caminhos:
            return
        base = self._campos["base"].get().strip() or str(_pasta_app() / BASE_PADRAO)
        self._campos["base"].set(base)
        Path(base).parent.mkdir(parents=True, exist_ok=True)
        argv = ["harvest", "-i", *caminhos, "-o", base]
        self._lancar([argv], f"Añadir {len(caminhos)} LPA a la base", None)

    def _lancar(self, comandos: list[list[str]], titulo: str, indice: int | None) -> None:
        self._a_indice = indice
        self._bloquear(True, titulo)
        self._escrever("", "normal")
        self._escrever(f"── {titulo} ──", "titulo")
        threading.Thread(target=self._trabalhar, args=(comandos,), daemon=True).start()

    def _trabalhar(self, comandos: list[list[str]]) -> None:
        from . import cli

        escritor = _Escritor(self._fila)
        codigo = 0
        try:
            for argv in comandos:
                self._fila.put(("linha", f"$ lpa_filler {' '.join(argv)}"))
                with redirect_stdout(escritor), redirect_stderr(escritor):
                    codigo = cli.main(argv) or 0
                escritor.flush()
                if codigo != 0:
                    break
        except SystemExit as e:
            codigo = int(e.code or 0)
        except Exception:
            escritor.flush()
            self._fila.put(("linha", traceback.format_exc().rstrip()))
            codigo = 1
        finally:
            escritor.flush()
            self._fila.put(("fim", codigo))

    def _drenar(self) -> None:
        try:
            while True:
                tipo, valor = self._fila.get_nowait()
                if tipo == "linha":
                    if str(valor).startswith("$ "):
                        self._escrever(str(valor), "apagado")
                    else:
                        self._escrever(str(valor), _classificar(str(valor)))
                else:
                    self._terminou(int(valor))
        except queue.Empty:
            pass
        self.after(60, self._drenar)

    def _terminou(self, codigo: int) -> None:
        if codigo == 0:
            self._escrever("Completado.", "bom")
            indice = getattr(self, "_a_indice", None)
            if indice:  # None nas ações fora do fluxo (ex. añadir a la base)
                self._feitos = max(self._feitos, indice)
            self._atualizar_contagem_base()
        else:
            self._escrever(f"Terminó con error (código {codigo}).", "mau")
        self._bloquear(False, "")

    def _atualizar_contagem_base(self) -> None:
        caminho = self._campos["base"].get().strip()
        if not caminho or not Path(caminho).exists():
            self._contagem_base.configure(text="Base vacía — añade un LPA para empezar.")
            return
        try:
            with open(caminho, encoding="utf-8-sig", newline="") as f:
                obras = set()
                n = 0
                for linha in csv.DictReader(f):
                    n += 1
                    if linha.get("obra"):
                        obras.add(linha["obra"])
        except OSError:
            return
        texto = f"{n} hallazgos en la base"
        if obras:
            texto += f", de {len(obras)} obras"
        self._contagem_base.configure(text=texto + ".")

    def _bloquear(self, ocupado: bool, titulo: str) -> None:
        self._a_correr = ocupado
        self._botao.state(["disabled"] if ocupado else ["!disabled"])
        if ocupado:
            self._estado.configure(text=f"● Corriendo: {titulo}…", fg=PALETA["marca"])
        else:
            self._estado.configure(text="● Listo", fg=PALETA["bom"])
        self.config(cursor="watch" if ocupado else "")
        self._marcar_passos()


def main() -> int:
    Janela().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
