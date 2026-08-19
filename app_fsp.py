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

# Paleta simples (podes refinar a estetica no Claude Design e trocar aqui)
COR_FUNDO   = "#0f172a"   # azul-escuro
COR_PAINEL  = "#1e293b"
COR_TEXTO   = "#e2e8f0"
COR_ACENTO  = "#38bdf8"   # azul-claro
COR_OK      = "#22c55e"
COR_ERRO    = "#ef4444"
COR_LOG_BG  = "#0b1220"


class AppFSP(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITULO)
        self.geometry("720x560")
        self.minsize(640, 480)
        self.configure(bg=COR_FUNDO)

        self.pasta_projeto: str | None = None
        self.output_path: Path | None = None
        self._fila: queue.Queue[tuple[str, object]] = queue.Queue()
        self._a_correr = False

        self._construir_ui()
        self.after(80, self._processar_fila)

    # ---------------- UI ----------------
    def _construir_ui(self):
        pad = 16

        # Cabecalho
        cab = tk.Frame(self, bg=COR_FUNDO)
        cab.pack(fill="x", padx=pad, pady=(pad, 4))
        tk.Label(cab, text="Gerador de FSP", bg=COR_FUNDO, fg=COR_TEXTO,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w")
        tk.Label(cab, text="Escolhe a pasta do projeto e gera a Ficha de Seguimiento.",
                 bg=COR_FUNDO, fg="#94a3b8", font=("Segoe UI", 10)).pack(anchor="w")

        # Painel de seleccao de pasta
        painel = tk.Frame(self, bg=COR_PAINEL)
        painel.pack(fill="x", padx=pad, pady=8)
        inner = tk.Frame(painel, bg=COR_PAINEL)
        inner.pack(fill="x", padx=12, pady=12)

        tk.Label(inner, text="Pasta do projeto", bg=COR_PAINEL, fg="#94a3b8",
                 font=("Segoe UI", 9)).pack(anchor="w")

        linha = tk.Frame(inner, bg=COR_PAINEL)
        linha.pack(fill="x", pady=(4, 0))
        self.var_pasta = tk.StringVar(value="(nenhuma pasta escolhida)")
        self.lbl_pasta = tk.Label(linha, textvariable=self.var_pasta, bg=COR_LOG_BG,
                                  fg=COR_TEXTO, font=("Consolas", 9), anchor="w",
                                  padx=8, pady=6)
        self.lbl_pasta.pack(side="left", fill="x", expand=True)
        tk.Button(linha, text="Escolher pasta…", command=self._escolher_pasta,
                  bg=COR_PAINEL, fg=COR_TEXTO, activebackground="#334155",
                  activeforeground=COR_TEXTO, relief="flat", padx=12, pady=6,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side="left", padx=(8, 0))

        # Botoes de accao
        acoes = tk.Frame(self, bg=COR_FUNDO)
        acoes.pack(fill="x", padx=pad, pady=(0, 8))
        self.btn_gerar = tk.Button(acoes, text="⚙  Gerar FSP", command=self._on_gerar,
                                   bg=COR_ACENTO, fg="#082f49", activebackground="#7dd3fc",
                                   relief="flat", padx=18, pady=10, state="disabled",
                                   font=("Segoe UI", 11, "bold"), cursor="hand2")
        self.btn_gerar.pack(side="left")
        self.btn_abrir = tk.Button(acoes, text="Abrir ficheiro gerado", command=self._abrir_output,
                                   bg=COR_PAINEL, fg=COR_TEXTO, activebackground="#334155",
                                   activeforeground=COR_TEXTO, relief="flat", padx=14, pady=10,
                                   state="disabled", font=("Segoe UI", 10), cursor="hand2")
        self.btn_abrir.pack(side="left", padx=8)

        # Estado / spinner
        self.var_estado = tk.StringVar(value="")
        self.lbl_estado = tk.Label(self, textvariable=self.var_estado, bg=COR_FUNDO,
                                   fg=COR_ACENTO, font=("Segoe UI", 10, "bold"), anchor="w")
        self.lbl_estado.pack(fill="x", padx=pad)

        # Log
        tk.Label(self, text="Progresso", bg=COR_FUNDO, fg="#94a3b8",
                 font=("Segoe UI", 9)).pack(anchor="w", padx=pad, pady=(6, 2))
        self.txt = scrolledtext.ScrolledText(self, bg=COR_LOG_BG, fg=COR_TEXTO,
                                             font=("Consolas", 9), relief="flat",
                                             insertbackground=COR_TEXTO, wrap="word",
                                             state="disabled")
        self.txt.pack(fill="both", expand=True, padx=pad, pady=(0, pad))
        self.txt.tag_config("erro", foreground=COR_ERRO)
        self.txt.tag_config("ok", foreground=COR_OK)

    # ---------------- accoes ----------------
    def _escolher_pasta(self):
        pasta = filedialog.askdirectory(title="Escolhe a pasta do projeto")
        if pasta:
            self.pasta_projeto = pasta
            self.var_pasta.set(pasta)
            self.btn_gerar.config(state="normal")
            self.btn_abrir.config(state="disabled")

    def _on_gerar(self):
        if self._a_correr or not self.pasta_projeto:
            return
        self._a_correr = True
        self.output_path = None
        self.btn_gerar.config(state="disabled")
        self.btn_abrir.config(state="disabled")
        self.var_estado.set("A gerar…  aguarda um momento.")
        self.lbl_estado.config(fg=COR_ACENTO)
        self._limpar_log()
        t = threading.Thread(target=self._worker, args=(self.pasta_projeto,), daemon=True)
        t.start()

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

    def _processar_fila(self):
        try:
            while True:
                tipo, payload = self._fila.get_nowait()
                if tipo == "log":
                    self._escrever(payload)
                elif tipo == "done":
                    self.output_path = payload
                    self._a_correr = False
                    self.var_estado.set("✔  FSP gerado com sucesso.")
                    self.lbl_estado.config(fg=COR_OK)
                    self.btn_gerar.config(state="normal")
                    self.btn_abrir.config(state="normal")
                elif tipo == "erro":
                    self._a_correr = False
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
