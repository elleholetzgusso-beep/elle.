#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GERADOR DE FSP — Aplicacao com interface grafica
------------------------------------------------------------
Janela simples para o utilizador:
  1. Escolher a pasta do projeto (botao "Escolher pasta...")
  2. Clicar em "Gerar FSP"
  3. Ver o progresso e abrir o ficheiro gerado

Nao precisa de linha de comandos. Corre com:  py app_fsp.py
Ou empacotado como GerarFSP.exe (ver build_exe.bat).
"""
from __future__ import annotations

import os
import sys
import queue
import threading
import subprocess
from pathlib import Path

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import gerar_fsp

APP_TITULO = "Gerador de FSP — Exceltic"

# ---------------------------------------------------------------------------
# Paleta (tema escuro). Para refinar a estetica no Claude Design, troca aqui.
# ---------------------------------------------------------------------------
COR_FUNDO    = "#0b1220"   # fundo geral
COR_CARD     = "#151f31"   # cartoes / paineis
COR_CARD_2   = "#1c2942"   # campos dentro dos cartoes
COR_BORDA    = "#243350"
COR_TEXTO    = "#e6edf6"
COR_SUAVE    = "#8ea0bd"   # texto secundario
COR_ACENTO   = "#38bdf8"   # azul-claro (accao principal)
COR_ACENTO_H = "#7dd3fc"   # hover do acento
COR_ACENTO_D = "#082f49"   # texto sobre acento
COR_OK       = "#22c55e"
COR_ERRO     = "#ef4444"
COR_LOG_BG   = "#070c16"

FONTE       = "Segoe UI"
FONTE_MONO  = "Consolas"


class HoverButton(tk.Button):
    """Botao plano com efeito de hover (o tk.Button normal nao tem)."""
    def __init__(self, master, bg, fg, bg_hover, **kw):
        super().__init__(master, bg=bg, fg=fg, activebackground=bg_hover,
                         activeforeground=fg, relief="flat", bd=0,
                         cursor="hand2", **kw)
        self._bg, self._bg_hover = bg, bg_hover
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, on):
        if str(self["state"]) != "disabled":
            self.config(bg=self._bg_hover if on else self._bg)

    def set_base(self, bg, bg_hover):
        self._bg, self._bg_hover = bg, bg_hover
        self.config(bg=bg)


class AppFSP(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITULO)
        self.geometry("760x620")
        self.minsize(680, 540)
        self.configure(bg=COR_FUNDO)

        self.pasta_projeto: str | None = None
        self.output_path: Path | None = None
        self._fila: queue.Queue[tuple[str, object]] = queue.Queue()
        self._a_correr = False

        self._configurar_estilo()
        self._construir_ui()
        self.after(80, self._processar_fila)

    # ---------------- estilo ttk ----------------
    def _configurar_estilo(self):
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure("Barra.Horizontal.TProgressbar",
                     troughcolor=COR_CARD_2, background=COR_ACENTO,
                     bordercolor=COR_CARD_2, lightcolor=COR_ACENTO,
                     darkcolor=COR_ACENTO, thickness=6)

    # ---------------- UI ----------------
    def _card(self, parent, **pack):
        """Cria um 'cartao' com borda subtil."""
        outer = tk.Frame(parent, bg=COR_BORDA)
        outer.pack(**pack)
        inner = tk.Frame(outer, bg=COR_CARD)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        return inner

    def _construir_ui(self):
        PADX = 22

        # ---- Cabecalho ----
        cab = tk.Frame(self, bg=COR_FUNDO)
        cab.pack(fill="x", padx=PADX, pady=(20, 6))
        titulo = tk.Frame(cab, bg=COR_FUNDO)
        titulo.pack(anchor="w")
        tk.Label(titulo, text="📄", bg=COR_FUNDO, font=(FONTE, 22)).pack(side="left", padx=(0, 10))
        col = tk.Frame(titulo, bg=COR_FUNDO)
        col.pack(side="left")
        tk.Label(col, text="Gerador de FSP", bg=COR_FUNDO, fg=COR_TEXTO,
                 font=(FONTE, 21, "bold")).pack(anchor="w")
        tk.Label(col, text="Ficha de Seguimiento del Proyecto — a partir do LPA e das pastas do projeto.",
                 bg=COR_FUNDO, fg=COR_SUAVE, font=(FONTE, 10)).pack(anchor="w")

        # ---- Cartao: escolher pasta ----
        card = self._card(self, fill="x", padx=PADX, pady=12)
        pad = tk.Frame(card, bg=COR_CARD)
        pad.pack(fill="x", padx=16, pady=16)

        tk.Label(pad, text="PASSO 1 · PASTA DO PROJETO", bg=COR_CARD, fg=COR_SUAVE,
                 font=(FONTE, 8, "bold")).pack(anchor="w")

        linha = tk.Frame(pad, bg=COR_CARD)
        linha.pack(fill="x", pady=(8, 0))
        campo = tk.Frame(linha, bg=COR_CARD_2)
        campo.pack(side="left", fill="x", expand=True)
        self.var_pasta = tk.StringVar(value="(nenhuma pasta escolhida)")
        tk.Label(campo, textvariable=self.var_pasta, bg=COR_CARD_2, fg=COR_TEXTO,
                 font=(FONTE_MONO, 9), anchor="w", padx=12, pady=9).pack(fill="x")
        HoverButton(linha, bg=COR_CARD_2, fg=COR_TEXTO, bg_hover=COR_BORDA,
                    text="Escolher pasta…", command=self._escolher_pasta,
                    padx=14, pady=9, font=(FONTE, 9, "bold")).pack(side="left", padx=(8, 0))

        # ---- Accoes ----
        acoes = tk.Frame(self, bg=COR_FUNDO)
        acoes.pack(fill="x", padx=PADX, pady=(0, 6))
        self.btn_gerar = HoverButton(acoes, bg=COR_ACENTO, fg=COR_ACENTO_D,
                                     bg_hover=COR_ACENTO_H, text="⚙  Gerar FSP",
                                     command=self._on_gerar, padx=22, pady=11,
                                     font=(FONTE, 11, "bold"))
        self.btn_gerar.pack(side="left")
        self.btn_gerar.config(state="disabled")
        self.btn_abrir = HoverButton(acoes, bg=COR_CARD, fg=COR_TEXTO,
                                     bg_hover=COR_BORDA, text="Abrir ficheiro gerado",
                                     command=self._abrir_output, padx=16, pady=11,
                                     font=(FONTE, 10))
        self.btn_abrir.pack(side="left", padx=8)
        self.btn_abrir.config(state="disabled")

        # ---- Estado (pill) + barra de progresso ----
        estado_fr = tk.Frame(self, bg=COR_FUNDO)
        estado_fr.pack(fill="x", padx=PADX, pady=(6, 0))
        self.var_estado = tk.StringVar(value="Pronto.")
        self.lbl_estado = tk.Label(estado_fr, textvariable=self.var_estado, bg=COR_FUNDO,
                                   fg=COR_SUAVE, font=(FONTE, 10, "bold"), anchor="w")
        self.lbl_estado.pack(side="left")
        self.barra = ttk.Progressbar(self, mode="indeterminate",
                                     style="Barra.Horizontal.TProgressbar")
        # so aparece durante a geracao

        # ---- Log ----
        tk.Label(self, text="PROGRESSO", bg=COR_FUNDO, fg=COR_SUAVE,
                 font=(FONTE, 8, "bold")).pack(anchor="w", padx=PADX, pady=(14, 4))
        logcard = self._card(self, fill="both", expand=True, padx=PADX, pady=(0, 8))
        self.txt = scrolledtext.ScrolledText(logcard, bg=COR_LOG_BG, fg=COR_TEXTO,
                                             font=(FONTE_MONO, 9), relief="flat", bd=0,
                                             insertbackground=COR_TEXTO, wrap="word",
                                             state="disabled", padx=12, pady=10)
        self.txt.pack(fill="both", expand=True, padx=1, pady=1)
        self.txt.tag_config("erro", foreground=COR_ERRO)
        self.txt.tag_config("ok", foreground=COR_OK)

        # ---- Rodape ----
        tk.Label(self, text="Exceltic · o ficheiro gerado fica em FSP_GERADO.xlsx dentro da pasta do projeto.",
                 bg=COR_FUNDO, fg=COR_SUAVE, font=(FONTE, 8)).pack(anchor="w", padx=PADX, pady=(0, 12))

    # ---------------- accoes ----------------
    def _escolher_pasta(self):
        pasta = filedialog.askdirectory(title="Escolhe a pasta do projeto")
        if pasta:
            self.pasta_projeto = pasta
            self.var_pasta.set(pasta)
            self.btn_gerar.config(state="normal")
            self.btn_abrir.config(state="disabled")
            self.var_estado.set("Pronto para gerar.")
            self.lbl_estado.config(fg=COR_SUAVE)

    def _on_gerar(self):
        if self._a_correr or not self.pasta_projeto:
            return
        self._a_correr = True
        self.output_path = None
        self.btn_gerar.config(state="disabled")
        self.btn_abrir.config(state="disabled")
        self.var_estado.set("A gerar…  aguarda um momento.")
        self.lbl_estado.config(fg=COR_ACENTO)
        self.barra.pack(fill="x", padx=22, pady=(6, 0))
        self.barra.start(12)
        self._limpar_log()
        threading.Thread(target=self._worker, args=(self.pasta_projeto,), daemon=True).start()

    def _worker(self, pasta):
        def log(msg):
            self._fila.put(("log", str(msg)))
        try:
            out = gerar_fsp.gerar_fsp(pasta, log=log)
            self._fila.put(("done", out))
        except SystemExit as e:  # erros "esperados" do script
            self._fila.put(("erro", str(e)))
        except Exception as e:
            import traceback
            self._fila.put(("log", traceback.format_exc()))
            self._fila.put(("erro", f"Erro inesperado: {e}"))

    def _parar_barra(self):
        self.barra.stop()
        self.barra.pack_forget()

    def _processar_fila(self):
        try:
            while True:
                tipo, payload = self._fila.get_nowait()
                if tipo == "log":
                    self._escrever(payload)
                elif tipo == "done":
                    self.output_path = payload
                    self._a_correr = False
                    self._parar_barra()
                    self.var_estado.set("✔  FSP gerado com sucesso.")
                    self.lbl_estado.config(fg=COR_OK)
                    self.btn_gerar.config(state="normal")
                    self.btn_abrir.config(state="normal")
                elif tipo == "erro":
                    self._a_correr = False
                    self._parar_barra()
                    self._escrever(str(payload), tag="erro")
                    self.var_estado.set("✖  Ocorreu um erro (ver detalhes acima).")
                    self.lbl_estado.config(fg=COR_ERRO)
                    self.btn_gerar.config(state="normal")
                    messagebox.showerror(APP_TITULO, str(payload))
        except queue.Empty:
            pass
        self.after(80, self._processar_fila)

    def _abrir_output(self):
        if not self.output_path or not Path(self.output_path).exists():
            messagebox.showwarning(APP_TITULO, "O ficheiro gerado ainda nao existe.")
            return
        p = str(Path(self.output_path).resolve())
        try:
            if sys.platform.startswith("win"):
                os.startfile(p)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", p])
            else:
                subprocess.run(["xdg-open", p])
        except Exception as e:
            messagebox.showerror(APP_TITULO, f"Nao consegui abrir o ficheiro:\n{e}")

    # ---------------- log helpers ----------------
    def _limpar_log(self):
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.config(state="disabled")

    def _escrever(self, msg, tag=None):
        self.txt.config(state="normal")
        self.txt.insert("end", msg + "\n", tag or ())
        self.txt.see("end")
        self.txt.config(state="disabled")


def main():
    app = AppFSP()
    app.mainloop()


if __name__ == "__main__":
    main()
