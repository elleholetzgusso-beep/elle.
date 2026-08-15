"""Janela gráfica do lpa_filler.

Corre os mesmos comandos da linha de comandos, sem terminal à vista. Os comandos
são chamados dentro do próprio processo (``cli.main``), e não por subprocesso,
porque dentro de um ``.exe`` não há interpretador de Python para invocar.

Para mudar o aspeto, ver PALETA e ``assets/logo.png`` — nada mais depende delas.
"""
from __future__ import annotations

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
# Aspeto. Trocar aqui pelas cores da casa; o resto do ficheiro não as conhece.

PALETA = {
    "tinta": "#12263A",       # barra de topo
    "destaque": "#2E7DA8",    # botões e realces
    "fundo": "#F4F6F8",
    "cartao": "#FFFFFF",
    "texto": "#1A1A1A",
    "apagado": "#6B7280",
    "linha": "#D9DEE5",
    "bom": "#1B7A4B",
    "aviso": "#A85B00",
    "mau": "#B3261E",
    "consola_fundo": "#12181F",
    "consola_texto": "#E4E8EC",
}

MARCA = "EXCELTIC"
SUBTITULO = "Automatização de LPA · Listado de Puntos Abiertos"


def _recurso(nome: str) -> Path:
    """Caminho de um recurso, dentro do .exe (``sys._MEIPASS``) ou no repositório."""
    base = getattr(sys, "_MEIPASS", None)
    raiz = Path(base) if base else Path(__file__).resolve().parent.parent
    return raiz / nome


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


def _classificar(linha: str) -> str:
    """Etiqueta de cor a partir do conteúdo — os comandos escrevem nos dois canais."""
    t = linha.strip()
    if not t:
        return "normal"
    if t.startswith(("✗", "Erro", "erro:", "Traceback")):
        return "mau"
    if t.startswith(("!", "?")) or "ATENÇÃO" in t or t.startswith("# ATENÇÃO"):
        return "aviso"
    if t.startswith(("Escrito:", "Gerado:", "==", "✓")):
        return "bom"
    if t.startswith("#"):
        return "apagado"
    return "normal"


class Janela(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{MARCA} · LPA")
        self.geometry("1120x720")
        self.minsize(940, 600)
        self.configure(bg=PALETA["fundo"])

        icone = _recurso("assets/logo.ico")
        if icone.exists():
            try:
                self.iconbitmap(str(icone))
            except tk.TclError:
                pass

        self._fila: queue.Queue = queue.Queue()
        self._a_correr = False
        self._botoes: list[ttk.Button] = []
        self._campos: dict[str, tk.StringVar] = {}

        self._estilos()
        self._cabecalho()

        corpo = tk.Frame(self, bg=PALETA["fundo"])
        corpo.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        corpo.columnconfigure(0, minsize=430)
        corpo.columnconfigure(1, weight=1)
        corpo.rowconfigure(0, weight=1)

        esquerda = tk.Frame(corpo, bg=PALETA["fundo"])
        esquerda.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self._painel_entradas(esquerda)
        self._painel_opcoes(esquerda)
        self._painel_passos(esquerda)

        self._painel_consola(corpo)

        self._escrever(f"{MARCA} · pronto.", "bom")
        self._escrever("Escolhe as entradas à esquerda e corre os passos por ordem.", "apagado")
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
        e.configure("Apagado.TLabel", foreground=PALETA["apagado"])
        e.configure("TCheckbutton", background=PALETA["cartao"], foreground=PALETA["texto"])
        e.configure(
            "Passo.TButton",
            background=PALETA["destaque"],
            foreground="#FFFFFF",
            padding=(10, 9),
            borderwidth=0,
            font=("Segoe UI", 10, "bold"),
        )
        e.map("Passo.TButton",
              background=[("active", PALETA["tinta"]), ("disabled", PALETA["linha"])],
              foreground=[("disabled", PALETA["apagado"])])
        e.configure("Procurar.TButton", padding=(8, 4))

    def _cabecalho(self) -> None:
        barra = tk.Frame(self, bg=PALETA["tinta"], height=76)
        barra.pack(fill="x")
        barra.pack_propagate(False)

        caixa = tk.Frame(barra, bg=PALETA["tinta"])
        caixa.pack(side="left", padx=20)

        logo = _recurso("assets/logo.png")
        posto = False
        if logo.exists():
            try:
                self._logo = tk.PhotoImage(file=str(logo))
                tk.Label(caixa, image=self._logo, bg=PALETA["tinta"]).pack(side="left")
                posto = True
            except tk.TclError:
                posto = False
        if not posto:
            tk.Label(caixa, text=MARCA, bg=PALETA["tinta"], fg="#FFFFFF",
                     font=("Segoe UI", 19, "bold")).pack(side="left")

        tk.Label(barra, text=SUBTITULO, bg=PALETA["tinta"], fg="#9FB3C4",
                 font=("Segoe UI", 10)).pack(side="left", padx=(14, 0))

        self._estado = tk.Label(barra, text="", bg=PALETA["tinta"], fg="#9FB3C4",
                                font=("Segoe UI", 10))
        self._estado.pack(side="right", padx=20)

    def _cartao(self, pai: tk.Widget, titulo: str) -> tk.Frame:
        fora = tk.Frame(pai, bg=PALETA["linha"])
        fora.pack(fill="x", pady=(0, 12))
        dentro = tk.Frame(fora, bg=PALETA["cartao"])
        dentro.pack(fill="both", padx=1, pady=1)
        tk.Label(dentro, text=titulo, bg=PALETA["cartao"], fg=PALETA["apagado"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=14, pady=(11, 6))
        corpo = tk.Frame(dentro, bg=PALETA["cartao"])
        corpo.pack(fill="both", padx=14, pady=(0, 12))
        return corpo

    # -------------------------------------------------------------- entradas
    def _linha_caminho(self, pai: tk.Widget, chave: str, rotulo: str, escolher) -> None:
        tk.Label(pai, text=rotulo, bg=PALETA["cartao"], fg=PALETA["texto"],
                 font=("Segoe UI", 9)).pack(anchor="w")
        fila = tk.Frame(pai, bg=PALETA["cartao"])
        fila.pack(fill="x", pady=(2, 9))
        var = tk.StringVar()
        self._campos[chave] = var
        tk.Entry(fila, textvariable=var, relief="solid", bd=1,
                 font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True, ipady=3)
        ttk.Button(fila, text="Procurar", style="Procurar.TButton",
                   command=lambda: self._escolher(var, escolher)).pack(side="left", padx=(6, 0))

    def _escolher(self, var: tk.StringVar, escolher) -> None:
        caminho = escolher()
        if caminho:
            var.set(caminho)

    def _painel_entradas(self, pai: tk.Widget) -> None:
        c = self._cartao(pai, "ENTRADAS")
        self._linha_caminho(c, "pes", "Relatório PES (.docx)",
                            lambda: filedialog.askopenfilename(
                                title="Relatório PES",
                                filetypes=[("Word", "*.docx"), ("Todos", "*.*")]))
        self._linha_caminho(c, "recibida", "Pasta dos documentos recebidos",
                            lambda: filedialog.askdirectory(title="Doc Recibida"))
        self._linha_caminho(c, "base", "Base de hallazgos (.csv)",
                            lambda: filedialog.askopenfilename(
                                title="Base de hallazgos",
                                filetypes=[("CSV", "*.csv"), ("Todos", "*.*")]))
        self._linha_caminho(c, "template", "Template LPA (.xlsm)",
                            lambda: filedialog.askopenfilename(
                                title="Template LPA",
                                filetypes=[("Excel com macros", "*.xlsm"), ("Todos", "*.*")]))
        self._linha_caminho(c, "trabalho", "Pasta onde gravar os resultados",
                            lambda: filedialog.askdirectory(title="Pasta de trabalho"))

    def _linha_texto(self, pai: tk.Widget, chave: str, rotulo: str, dica: str) -> None:
        tk.Label(pai, text=rotulo, bg=PALETA["cartao"], fg=PALETA["texto"],
                 font=("Segoe UI", 9)).pack(anchor="w")
        var = tk.StringVar()
        self._campos[chave] = var
        tk.Entry(pai, textvariable=var, relief="solid", bd=1,
                 font=("Segoe UI", 9)).pack(fill="x", ipady=3, pady=(2, 1))
        tk.Label(pai, text=dica, bg=PALETA["cartao"], fg=PALETA["apagado"],
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 8))

    def _painel_opcoes(self, pai: tk.Widget) -> None:
        c = self._cartao(pai, "OPÇÕES")
        self._linha_texto(c, "solicitante", "Solicitante", "Quem faz os envíos. Ex.: ADIF")
        self._linha_texto(c, "scope", "Âncoras desta obra",
                          "Separadas por vírgula. Ex.: Sant Vicenç de Calders, TRAMO 2")
        self._linha_texto(c, "excluir_obra", "Código desta obra",
                          "Ex.: EXC2026-18042. Evita sugerir a partir da própria resposta.")

        fila = tk.Frame(c, bg=PALETA["cartao"])
        fila.pack(fill="x", pady=(2, 6))
        tk.Label(fila, text="Exigência das sugestões", bg=PALETA["cartao"],
                 fg=PALETA["texto"], font=("Segoe UI", 9)).pack(side="left")
        self._min_score = tk.DoubleVar(value=12.0)
        tk.Spinbox(fila, from_=0, to=60, increment=2, width=6,
                   textvariable=self._min_score, relief="solid", bd=1,
                   font=("Segoe UI", 9)).pack(side="right")
        tk.Label(c, text="Mais alto = menos sugestões, mas mais parecidas. 12 é um começo razoável.",
                 bg=PALETA["cartao"], fg=PALETA["apagado"], font=("Segoe UI", 8),
                 wraplength=380, justify="left").pack(anchor="w", pady=(0, 8))

        self._skip_lpa = tk.BooleanVar(value=True)
        ttk.Checkbutton(c, text="Deixar a aba LPA vazia para preencher à mão",
                        variable=self._skip_lpa).pack(anchor="w")
        self._substituir = tk.BooleanVar(value=False)
        ttk.Checkbutton(c, text="Ao sugerir, substituir as sugestões anteriores",
                        variable=self._substituir).pack(anchor="w", pady=(2, 0))

    def _painel_passos(self, pai: tk.Widget) -> None:
        c = self._cartao(pai, "PASSOS")
        for p in pipeline.PASSOS:
            b = ttk.Button(c, text=p.titulo, style="Passo.TButton",
                           command=lambda chave=p.chave: self._correr(chave))
            b.pack(fill="x", pady=(0, 4))
            self._botoes.append(b)
            tk.Label(c, text=p.descricao, bg=PALETA["cartao"], fg=PALETA["apagado"],
                     font=("Segoe UI", 8), wraplength=380,
                     justify="left").pack(anchor="w", pady=(0, 9))

    # -------------------------------------------------------------- consola
    def _painel_consola(self, pai: tk.Widget) -> None:
        fora = tk.Frame(pai, bg=PALETA["linha"])
        fora.grid(row=0, column=1, sticky="nsew")
        dentro = tk.Frame(fora, bg=PALETA["consola_fundo"])
        dentro.pack(fill="both", expand=True, padx=1, pady=1)

        topo = tk.Frame(dentro, bg=PALETA["consola_fundo"])
        topo.pack(fill="x", padx=12, pady=(9, 4))
        tk.Label(topo, text="O QUE ESTÁ A ACONTECER", bg=PALETA["consola_fundo"],
                 fg="#7C8B99", font=("Segoe UI", 9, "bold")).pack(side="left")
        tk.Button(topo, text="Limpar", command=self._limpar, relief="flat",
                  bg=PALETA["consola_fundo"], fg="#7C8B99", activebackground=PALETA["consola_fundo"],
                  activeforeground="#FFFFFF", font=("Segoe UI", 8), bd=0,
                  cursor="hand2").pack(side="right")

        moldura = tk.Frame(dentro, bg=PALETA["consola_fundo"])
        moldura.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        barra = tk.Scrollbar(moldura)
        barra.pack(side="right", fill="y")
        self._consola = tk.Text(moldura, wrap="word", relief="flat",
                                bg=PALETA["consola_fundo"], fg=PALETA["consola_texto"],
                                insertbackground=PALETA["consola_texto"],
                                font=("Consolas", 9), yscrollcommand=barra.set,
                                padx=8, pady=8)
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
            substituir_sugestoes=bool(self._substituir.get()),
        )

    def _correr(self, chave: str) -> None:
        if self._a_correr:
            return
        passo = pipeline.passo(chave)
        cfg = self._config()

        falta = passo.em_falta(cfg)
        if falta:
            messagebox.showwarning(
                "Falta preencher",
                f"Para correr «{passo.titulo}» falta:\n\n• " + "\n• ".join(falta),
            )
            return

        if chave == "preparar":
            n = pipeline.projeto_tem_puntos(cfg)
            if n and not messagebox.askyesno(
                "Já existe um projeto",
                f"O projeto.yaml desta pasta já tem {n} punto(s).\n\n"
                "Voltar a preparar apaga-os e recomeça do zero.\n\nContinuar?",
                icon="warning",
            ):
                return

        cfg.trabalho.mkdir(parents=True, exist_ok=True)
        self._bloquear(True, passo.titulo)
        self._escrever("", "normal")
        self._escrever(f"── {passo.titulo} ──", "titulo")
        threading.Thread(target=self._trabalhar, args=(passo, cfg), daemon=True).start()

    def _trabalhar(self, passo: pipeline.Passo, cfg: Config) -> None:
        from . import cli

        escritor = _Escritor(self._fila)
        codigo = 0
        try:
            for argv in passo.comandos(cfg):
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
            self._escrever("Concluído.", "bom")
        else:
            self._escrever(f"Terminou com erro (código {codigo}).", "mau")
        self._bloquear(False, "")

    def _bloquear(self, ocupado: bool, titulo: str) -> None:
        self._a_correr = ocupado
        for b in self._botoes:
            b.state(["disabled"] if ocupado else ["!disabled"])
        self._estado.config(text=f"A correr: {titulo}…" if ocupado else "")
        self.config(cursor="watch" if ocupado else "")


def main() -> int:
    Janela().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
