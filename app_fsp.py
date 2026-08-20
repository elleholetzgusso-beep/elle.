#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GERADOR DE FSP - interface no estilo Exceltic
------------------------------------------------------------
Mesma logica de app_fsp.py; muda a estetica para a identidade Exceltic:
fundo branco, Arial, laranja #F15722 como unica cor de marca, formas
planas e rectangulares (sem sombras nem cantos redondos), regua laranja
sob o cabecalho.

Substitui app_fsp.py (mesmo ponto de entrada: gerar_fsp.gerar_fsp).
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
# Paleta Exceltic (tokens do design system)
# ---------------------------------------------------------------------------
COR_LARANJA    = "#f15722"   # marca (accao principal)
COR_LARANJA_D  = "#d94e14"   # hover / pressionado
COR_LARANJA_CL = "#fde7d9"   # fundo suave laranja
COR_FUNDO      = "#ffffff"   # pagina
COR_SUNKEN     = "#f2f2f2"   # barras, campos inactivos
COR_BORDA      = "#c1c2c4"
COR_BORDA_F    = "#1a1a1a"   # regua "documento legal" (log, tabelas)
COR_TEXTO      = "#1a1a1a"
COR_TEXTO_2    = "#4a4a4a"
COR_SUAVE      = "#7a7a7a"
COR_BRANCO     = "#ffffff"
COR_OK         = "#2e7d4f"
COR_ERRO       = "#c62828"
COR_DESACTIVO  = "#c1c2c4"

FONTE      = "Arial"
FONTE_MONO = "Courier New"


class HoverButton(tk.Button):
    """Botao plano (sem relevo) com hover — o tk.Button normal nao tem."""
    def __init__(self, master, bg, fg, bg_hover, **kw):
        super().__init__(master, bg=bg, fg=fg, activebackground=bg_hover,
                         activeforeground=fg, relief="flat", bd=0,
                         highlightthickness=0, cursor="hand2", **kw)
        self._bg, self._bg_hover = bg, bg_hover
        self.bind("<Enter>", lambda e: self._hover(True))
        self.bind("<Leave>", lambda e: self._hover(False))

    def _hover(self, on):
        if str(self["state"]) != "disabled":
            self.config(bg=self._bg_hover if on else self._bg)

    def set_base(self, bg, bg_hover, fg=None):
        self._bg, self._bg_hover = bg, bg_hover
        self.config(bg=bg)
        if fg:
            self.config(fg=fg)


def moldura(parent, cor_borda=COR_BORDA, cor_fundo=COR_FUNDO, espessura=1):
    """Rectangulo plano com regua de 1px (o motivo de borda da marca)."""
    outer = tk.Frame(parent, bg=cor_borda)
    inner = tk.Frame(outer, bg=cor_fundo)
    inner.pack(fill="both", expand=True, padx=espessura, pady=espessura)
    return outer, inner


class AppFSP(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITULO)
        self.geometry("860x700")
        self.minsize(760, 600)
        self.configure(bg=COR_FUNDO)

        self.pasta_projeto: str | None = None
        self.output_path: Path | None = None
        self._fila: queue.Queue[tuple[str, object]] = queue.Queue()
        self._a_correr = False
        self._n_linha = 0

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
                     troughcolor=COR_SUNKEN, background=COR_LARANJA,
                     bordercolor=COR_SUNKEN, lightcolor=COR_LARANJA,
                     darkcolor=COR_LARANJA, thickness=4)

    # ---------------- logo ----------------
    def _carregar_logo(self, nome, altura_alvo=34):
        """Carrega assets/<nome> como PhotoImage, reduzido para ~altura_alvo px.
        Devolve None se o ficheiro nao existir ou o Tk nao suportar o PNG."""
        try:
            caminho = gerar_fsp.resource_path(str(Path("assets") / nome))
            if not Path(caminho).exists():
                return None
            img = tk.PhotoImage(file=str(caminho))
            fator = max(1, round(img.height() / altura_alvo))
            if fator > 1:
                img = img.subsample(fator, fator)
            return img
        except Exception:
            return None

    # ---------------- UI ----------------
    def _construir_ui(self):
        PADX = 30

        # ---- Cabecalho ----
        cab = tk.Frame(self, bg=COR_FUNDO)
        cab.pack(fill="x", padx=PADX, pady=(26, 0))

        linha_tit = tk.Frame(cab, bg=COR_FUNDO)
        linha_tit.pack(fill="x")
        # Logo real (assets/logo-lockup.png); se nao carregar, cai para o texto "FSP."
        self._logo = self._carregar_logo("logo-lockup.png", altura_alvo=34)
        if self._logo is not None:
            tk.Label(linha_tit, image=self._logo, bg=COR_FUNDO).pack(side="left")
            tk.Label(linha_tit, text="  Gerador de Ficha de Seguimiento", bg=COR_FUNDO,
                     fg=COR_TEXTO, font=(FONTE, 20, "bold")).pack(side="left")
        else:
            tk.Label(linha_tit, text="FSP.", bg=COR_FUNDO, fg=COR_LARANJA,
                     font=(FONTE, 20, "bold")).pack(side="left")
            tk.Label(linha_tit, text="  Gerador de Ficha de Seguimiento", bg=COR_FUNDO,
                     fg=COR_TEXTO, font=(FONTE, 20, "bold")).pack(side="left")
        tk.Label(linha_tit, text="VERSÃO 1.0", bg=COR_FUNDO, fg=COR_SUAVE,
                 font=(FONTE, 8, "bold")).pack(side="right", pady=(8, 0))

        tk.Label(cab, text="Gera a Ficha de Seguimiento del Proyecto a partir do último LPA e das "
                           "pastas 1_ Doc Recibida e 3_ Doc Generada.",
                 bg=COR_FUNDO, fg=COR_TEXTO_2, font=(FONTE, 9), justify="left",
                 anchor="w").pack(fill="x", pady=(6, 0))

        # regua laranja — o divisor da marca
        tk.Frame(self, bg=COR_LARANJA, height=3).pack(fill="x", padx=PADX, pady=(16, 0))

        # ---- Passo 1: pasta ----
        p1 = tk.Frame(self, bg=COR_FUNDO)
        p1.pack(fill="x", padx=PADX, pady=(22, 0))
        cabecalho_passo(p1, "1.", "PASTA DO PROJETO")

        linha = tk.Frame(p1, bg=COR_FUNDO)
        linha.pack(fill="x", pady=(10, 0))
        campo_out, campo = moldura(linha)
        campo_out.pack(side="left", fill="x", expand=True)
        self.var_pasta = tk.StringVar(value="(nenhuma pasta escolhida)")
        self.lbl_pasta = tk.Label(campo, textvariable=self.var_pasta, bg=COR_FUNDO,
                                  fg=COR_SUAVE, font=(FONTE_MONO, 9), anchor="w",
                                  padx=12, pady=10)
        self.lbl_pasta.pack(fill="x")

        btn_out, btn_in = moldura(linha, cor_borda=COR_LARANJA)
        btn_out.pack(side="left")
        HoverButton(btn_in, bg=COR_FUNDO, fg=COR_LARANJA, bg_hover=COR_LARANJA_CL,
                    text="Escolher pasta…", command=self._escolher_pasta,
                    padx=20, pady=10, font=(FONTE, 9, "bold")).pack()

        # ---- Passo 2: accoes ----
        p2 = tk.Frame(self, bg=COR_FUNDO)
        p2.pack(fill="x", padx=PADX, pady=(22, 0))
        cabecalho_passo(p2, "2.", "GERAR O FICHEIRO")

        acoes = tk.Frame(p2, bg=COR_FUNDO)
        acoes.pack(fill="x", pady=(12, 0))
        self.btn_gerar = HoverButton(acoes, bg=COR_DESACTIVO, fg=COR_BRANCO,
                                     bg_hover=COR_LARANJA_D, text="GERAR FSP",
                                     command=self._on_gerar, padx=28, pady=12,
                                     font=(FONTE, 11, "bold"), state="disabled")
        self.btn_gerar.pack(side="left")

        abrir_out, abrir_in = moldura(acoes, cor_borda=COR_DESACTIVO)
        abrir_out.pack(side="left", padx=12)
        self.btn_abrir = HoverButton(abrir_in, bg=COR_FUNDO, fg=COR_DESACTIVO,
                                     bg_hover=COR_SUNKEN, text="Abrir ficheiro gerado",
                                     command=self._abrir_output, padx=18, pady=11,
                                     font=(FONTE, 9, "bold"), state="disabled")
        self.btn_abrir.pack()
        self._abrir_out = abrir_out

        # ---- Estado + barra ----
        estado_fr = tk.Frame(self, bg=COR_FUNDO)
        estado_fr.pack(fill="x", padx=PADX, pady=(16, 0))
        self._estado_barra = tk.Frame(estado_fr, bg=COR_SUAVE, width=3)
        self._estado_barra.pack(side="left", fill="y")
        self._estado_cx = tk.Frame(estado_fr, bg=COR_SUNKEN)
        self._estado_cx.pack(side="left")
        self.var_estado = tk.StringVar(value="Aguarda seleção da pasta")
        self.lbl_estado = tk.Label(self._estado_cx, textvariable=self.var_estado,
                                   bg=COR_SUNKEN, fg=COR_SUAVE,
                                   font=(FONTE, 9, "bold"), padx=14, pady=7)
        self.lbl_estado.pack()
        self.barra = ttk.Progressbar(estado_fr, mode="indeterminate",
                                     style="Barra.Horizontal.TProgressbar")

        # ---- Log ----
        cab_log = tk.Frame(self, bg=COR_FUNDO)
        cab_log.pack(fill="x", padx=PADX, pady=(22, 6))
        tk.Label(cab_log, text="PROGRESSO", bg=COR_FUNDO, fg=COR_SUAVE,
                 font=(FONTE, 8, "bold")).pack(side="left")
        self.var_contagem = tk.StringVar(value="—")
        tk.Label(cab_log, textvariable=self.var_contagem, bg=COR_FUNDO, fg=COR_SUAVE,
                 font=(FONTE_MONO, 8)).pack(side="right")

        log_out, log_in = moldura(self, cor_borda=COR_BORDA_F)
        log_out.pack(fill="both", expand=True, padx=PADX)
        self.txt = scrolledtext.ScrolledText(log_in, bg=COR_FUNDO, fg=COR_TEXTO,
                                             font=(FONTE_MONO, 9), relief="flat", bd=0,
                                             insertbackground=COR_TEXTO, wrap="word",
                                             state="disabled", padx=12, pady=10)
        self.txt.pack(fill="both", expand=True)
        self.txt.tag_config("erro", foreground=COR_ERRO)
        self.txt.tag_config("ok", foreground=COR_OK)
        self.txt.tag_config("num", foreground=COR_BORDA)
        self._escrever_placeholder()

        # ---- Rodape ----
        rod = tk.Frame(self, bg=COR_FUNDO)
        rod.pack(fill="x", padx=PADX, pady=(10, 16))
        tk.Label(rod, text="O ficheiro é escrito em FSP_GERADO.xlsx dentro da pasta do projeto.",
                 bg=COR_FUNDO, fg=COR_SUAVE, font=(FONTE, 8)).pack(side="left")
        tk.Label(rod, text="DELIVERING EXCELLENCE", bg=COR_FUNDO, fg=COR_LARANJA,
                 font=(FONTE, 8, "bold")).pack(side="right")

    # ---------------- accoes ----------------
    def _escolher_pasta(self):
        pasta = filedialog.askdirectory(title="Escolhe a pasta do projeto")
        if pasta:
            self.pasta_projeto = pasta
            self.var_pasta.set(pasta)
            self.lbl_pasta.config(fg=COR_TEXTO)
            self.btn_gerar.set_base(COR_LARANJA, COR_LARANJA_D)
            self.btn_gerar.config(state="normal")
            self._desactivar_abrir()
            self._estado("Pronto para gerar", COR_TEXTO_2, COR_SUNKEN)

    def _estado(self, texto, cor, fundo=COR_SUNKEN):
        self.var_estado.set(texto)
        self.lbl_estado.config(fg=cor, bg=fundo)
        self._estado_cx.config(bg=fundo)
        self._estado_barra.config(bg=cor)

    def _activar_abrir(self):
        self._abrir_out.config(bg=COR_BORDA_F)
        self.btn_abrir.set_base(COR_FUNDO, COR_SUNKEN, fg=COR_TEXTO)
        self.btn_abrir.config(state="normal")

    def _desactivar_abrir(self):
        self._abrir_out.config(bg=COR_DESACTIVO)
        self.btn_abrir.set_base(COR_FUNDO, COR_FUNDO, fg=COR_DESACTIVO)
        self.btn_abrir.config(state="disabled")

    def _on_gerar(self):
        if self._a_correr or not self.pasta_projeto:
            return
        self._a_correr = True
        self.output_path = None
        self.btn_gerar.config(state="disabled")
        self.btn_gerar.set_base(COR_DESACTIVO, COR_DESACTIVO)
        self._desactivar_abrir()
        self._estado("A gerar — aguarda um momento", COR_LARANJA, COR_LARANJA_CL)
        self.barra.pack(side="left", fill="x", expand=True, padx=(14, 0))
        self.barra.start(12)
        self._limpar_log()
        threading.Thread(target=self._worker, args=(self.pasta_projeto,), daemon=True).start()

    def _worker(self, pasta):
        def log(msg):
            self._fila.put(("log", str(msg)))
        try:
            out = gerar_fsp.gerar_fsp(pasta, log=log)
            self._fila.put(("done", out))
        except SystemExit as e:
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
                    self._escrever("FSP_GERADO.xlsx escrito com sucesso.", tag="ok")
                    self._estado("FSP gerado com sucesso", COR_OK)
                    self.btn_gerar.set_base(COR_LARANJA, COR_LARANJA_D)
                    self.btn_gerar.config(state="normal")
                    self._activar_abrir()
                elif tipo == "erro":
                    self._a_correr = False
                    self._parar_barra()
                    self._escrever(str(payload), tag="erro")
                    self._estado("Ocorreu um erro — ver progresso", COR_ERRO)
                    self.btn_gerar.set_base(COR_LARANJA, COR_LARANJA_D)
                    self.btn_gerar.config(state="normal")
                    messagebox.showerror(APP_TITULO, str(payload))
        except queue.Empty:
            pass
        self.after(80, self._processar_fila)

    def _abrir_output(self):
        if not self.output_path or not Path(self.output_path).exists():
            messagebox.showwarning(APP_TITULO, "O ficheiro gerado ainda não existe.")
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
            messagebox.showerror(APP_TITULO, f"Não consegui abrir o ficheiro:\n{e}")

    # ---------------- log ----------------
    def _escrever_placeholder(self):
        self.txt.config(state="normal")
        self.txt.insert("end", "Sem operações registadas. Escolhe a pasta do projeto "
                               "e clica em GERAR FSP.\n", "num")
        self.txt.config(state="disabled")

    def _limpar_log(self):
        self._n_linha = 0
        self.var_contagem.set("—")
        self.txt.config(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.config(state="disabled")

    def _escrever(self, msg, tag=None):
        self._n_linha += 1
        self.var_contagem.set(f"{self._n_linha} linhas")
        self.txt.config(state="normal")
        self.txt.insert("end", f"{self._n_linha:02d}  ", "num")
        self.txt.insert("end", str(msg) + "\n", tag or ())
        self.txt.see("end")
        self.txt.config(state="disabled")


def cabecalho_passo(parent, numero, titulo):
    fr = tk.Frame(parent, bg=COR_FUNDO)
    fr.pack(fill="x")
    tk.Label(fr, text=numero, bg=COR_FUNDO, fg=COR_LARANJA,
             font=(FONTE, 10, "bold")).pack(side="left")
    tk.Label(fr, text="  " + titulo, bg=COR_FUNDO, fg=COR_TEXTO,
             font=(FONTE, 10, "bold")).pack(side="left")
    return fr


def main():
    AppFSP().mainloop()


if __name__ == "__main__":
    main()
