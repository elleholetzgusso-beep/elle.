#!/usr/bin/env python3
"""App de janela para extrair arquivos de subpastas e montar a planilha de documentos.

Roda com duplo clique (ou "python app.py") e usa os mesmos motores dos scripts
extrair_arquivos.py e listar_documentos.py.

Para ler o conteudo dos documentos na aba 2:
    pip install openpyxl pypdf python-docx
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import extrair_arquivos as extrator
import listar_documentos as listador

CONFIG = Path.home() / ".extrator_documentos.json"
TITULO = "Extrator de Documentos"
EXTENSOES_DOCUMENTOS = "pdf, doc, docx, xls, xlsx, ppt, pptx, txt, csv, rtf, odt"


def abrir_no_sistema(caminho: Path) -> None:
    """Abre a pasta ou o arquivo no programa padrao do sistema."""
    try:
        if sys.platform == "win32":
            os.startfile(str(caminho))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.run(["open", str(caminho)], check=False)
        else:
            subprocess.run(["xdg-open", str(caminho)], check=False)
    except Exception as erro:
        messagebox.showerror(TITULO, f"Nao foi possivel abrir:\n{caminho}\n\n{erro}")


def separar_extensoes(texto: str) -> set[str] | None:
    """Transforma "pdf, .docx" em {".pdf", ".docx"}."""
    itens = [p.strip().lower() for p in texto.replace(";", ",").replace(" ", ",").split(",")]
    itens = [p if p.startswith(".") else f".{p}" for p in itens if p and p != "."]
    return set(itens) or None


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(TITULO)
        self.minsize(760, 620)
        self.fila: queue.Queue = queue.Queue()
        self.ocupado = False
        self.ultima_saida: Path | None = None
        self.encadear = False

        self._montar_estilo()
        self._montar_widgets()
        self._carregar_config()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        self.after(100, self._drenar_fila)

    # ------------------------------------------------------------------ layout

    def _montar_estilo(self) -> None:
        estilo = ttk.Style(self)
        if "vista" in estilo.theme_names():
            estilo.theme_use("vista")
        elif "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure("Titulo.TLabel", font=("Segoe UI", 11, "bold"))
        estilo.configure("Acao.TButton", font=("Segoe UI", 10, "bold"))

    def _montar_widgets(self) -> None:
        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="x", padx=12, pady=(12, 6))
        self.abas.add(self._aba_extrair(), text="  1. Juntar arquivos  ")
        self.abas.add(self._aba_planilha(), text="  2. Planilha de documentos  ")

        painel = ttk.LabelFrame(self, text="Andamento")
        painel.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        self.barra = ttk.Progressbar(painel, mode="determinate")
        self.barra.pack(fill="x", padx=10, pady=(10, 4))

        self.status = ttk.Label(painel, text="Pronto.")
        self.status.pack(anchor="w", padx=10)

        moldura = ttk.Frame(painel)
        moldura.pack(fill="both", expand=True, padx=10, pady=8)
        self.log = tk.Text(moldura, height=12, wrap="none", state="disabled",
                           font=("Consolas", 9), background="#1e1e1e", foreground="#d4d4d4")
        barra_v = ttk.Scrollbar(moldura, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=barra_v.set)
        self.log.pack(side="left", fill="both", expand=True)
        barra_v.pack(side="right", fill="y")
        self.log.tag_configure("erro", foreground="#f48771")
        self.log.tag_configure("ok", foreground="#89d185")

        rodape = ttk.Frame(painel)
        rodape.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(rodape, text="Limpar", command=self._limpar_log).pack(side="left")
        self.botao_abrir = ttk.Button(rodape, text="Abrir resultado", state="disabled",
                                      command=self._abrir_resultado)
        self.botao_abrir.pack(side="right")

    def _aba_extrair(self) -> ttk.Frame:
        aba = ttk.Frame(self, padding=14)

        ttk.Label(aba, text="Junta os arquivos de todas as subpastas em uma pasta so.",
                  style="Titulo.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(aba, foreground="#505050",
                  text="Nao importa quantos niveis de subpasta existam: tudo termina "
                       "solto em uma pasta unica.").grid(row=1, column=0, columnspan=3,
                                                         sticky="w", pady=(2, 6))

        self.origem = tk.StringVar()
        self.destino = tk.StringVar()
        self._linha_pasta(aba, 2, "Pasta de origem:", self.origem, self._escolher_origem)
        self._linha_pasta(aba, 3, "Pasta de destino:", self.destino,
                          lambda: self._escolher_pasta(self.destino))

        opcoes = ttk.LabelFrame(aba, text="Opcoes", padding=10)
        opcoes.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 8))
        opcoes.columnconfigure(3, weight=1)

        self.modo = tk.StringVar(value="copiar")
        ttk.Radiobutton(opcoes, text="Copiar (mantem o original)", variable=self.modo,
                        value="copiar").grid(row=0, column=0, sticky="w", padx=(0, 16))
        ttk.Radiobutton(opcoes, text="Mover", variable=self.modo,
                        value="mover").grid(row=0, column=1, sticky="w")

        ttk.Label(opcoes, text="Nomes repetidos:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.conflito = tk.StringVar(value="renomear")
        ttk.Combobox(opcoes, textvariable=self.conflito, state="readonly", width=14,
                     values=["renomear", "pular", "sobrescrever"]).grid(
            row=1, column=1, sticky="w", pady=(8, 0))

        ttk.Label(opcoes, text="So estas extensoes:").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.ext_extrair = tk.StringVar()
        ttk.Entry(opcoes, textvariable=self.ext_extrair, width=28).grid(
            row=2, column=1, columnspan=2, sticky="w", pady=(8, 0))
        atalhos = ttk.Frame(opcoes)
        atalhos.grid(row=2, column=3, sticky="w", padx=8, pady=(8, 0))
        ttk.Button(atalhos, text="so documentos", width=15,
                   command=lambda: self.ext_extrair.set(EXTENSOES_DOCUMENTOS)).pack(side="left")
        ttk.Button(atalhos, text="tudo", width=7,
                   command=lambda: self.ext_extrair.set("")).pack(side="left", padx=4)

        self.prefixo = tk.BooleanVar()
        self.limpar_vazias = tk.BooleanVar()
        self.ocultos_extrair = tk.BooleanVar()
        ttk.Checkbutton(opcoes, text="Guardar o caminho no nome (sub_pasta_foto.jpg)",
                        variable=self.prefixo).grid(row=3, column=0, columnspan=3,
                                                    sticky="w", pady=(10, 0))
        ttk.Checkbutton(opcoes, text="Apagar as subpastas vazias (so ao mover)",
                        variable=self.limpar_vazias).grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Checkbutton(opcoes, text="Incluir arquivos ocultos",
                        variable=self.ocultos_extrair).grid(row=5, column=0, columnspan=3,
                                                            sticky="w")

        depois = ttk.LabelFrame(aba, text="Quando terminar de juntar", padding=10)
        depois.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.depois = tk.StringVar(value="parar")
        ttk.Radiobutton(depois, text="Parar por aqui  -  so juntar os arquivos, "
                                     "sem listar nem analisar nada",
                        variable=self.depois, value="parar").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(depois, text="Gerar tambem a planilha da pasta de destino",
                        variable=self.depois, value="listar").grid(row=1, column=0,
                                                                   sticky="w", pady=(4, 0))

        extras = ttk.Frame(aba)
        extras.grid(row=6, column=0, columnspan=3, sticky="ew")
        ttk.Button(extras, text="So quero a planilha, sem organizar  >",
                   command=lambda: self.abas.select(1)).pack(side="right")

        botoes = ttk.Frame(aba)
        botoes.grid(row=7, column=0, columnspan=3, sticky="e", pady=(12, 0))
        self.botao_simular = ttk.Button(botoes, text="Simular", command=lambda: self._extrair(True))
        self.botao_simular.pack(side="left", padx=(0, 8))
        self.botao_extrair = ttk.Button(botoes, text="Juntar arquivos", style="Acao.TButton",
                                        command=lambda: self._extrair(False))
        self.botao_extrair.pack(side="left")

        aba.columnconfigure(1, weight=1)
        return aba

    def _aba_planilha(self) -> ttk.Frame:
        aba = ttk.Frame(self, padding=14)

        ttk.Label(aba, text="Monta um Excel com a lista dos documentos.",
                  style="Titulo.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(aba, foreground="#505050",
                  text="Pode usar sozinho, sem passar pela aba 1: nada e movido nem copiado, "
                       "so a planilha e criada.").grid(row=1, column=0, columnspan=3,
                                                       sticky="w", pady=(2, 6))

        self.pasta_docs = tk.StringVar()
        self.arquivo_saida = tk.StringVar()
        self._linha_pasta(aba, 2, "Pasta dos documentos:", self.pasta_docs,
                          self._escolher_pasta_docs)

        ttk.Label(aba, text="Salvar planilha em:").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(aba, textvariable=self.arquivo_saida).grid(row=3, column=1, sticky="ew", padx=6)
        ttk.Button(aba, text="Procurar...", command=self._escolher_saida).grid(row=3, column=2)

        conteudo = ttk.LabelFrame(aba, text="O que a planilha vai trazer", padding=10)
        conteudo.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 8))

        self.modo_lista = tk.StringVar(value="completo")
        ttk.Radiobutton(conteudo, text="Lista completa  -  titulo, versao, paginas e o conteudo "
                                       "de cada documento",
                        variable=self.modo_lista, value="completo",
                        command=self._atualizar_modo_lista).grid(row=0, column=0, columnspan=4,
                                                                 sticky="w")
        ttk.Radiobutton(conteudo, text="So nomes e caminhos  -  nao abre os arquivos, "
                                       "termina em segundos",
                        variable=self.modo_lista, value="nomes",
                        command=self._atualizar_modo_lista).grid(row=1, column=0, columnspan=4,
                                                                 sticky="w", pady=(4, 0))

        self.rotulo_limite = ttk.Label(conteudo, text="Conteudo por linha:")
        self.rotulo_limite.grid(row=2, column=0, sticky="w", padx=(22, 0), pady=(8, 0))
        self.limite = tk.IntVar(value=2000)
        self.campo_limite = ttk.Spinbox(conteudo, from_=0, to=32000, increment=500, width=10,
                                        textvariable=self.limite)
        self.campo_limite.grid(row=2, column=1, sticky="w", pady=(8, 0))
        self.rotulo_caracteres = ttk.Label(conteudo, text="caracteres")
        self.rotulo_caracteres.grid(row=2, column=2, sticky="w", pady=(8, 0))
        conteudo.columnconfigure(3, weight=1)

        opcoes = ttk.LabelFrame(aba, text="Quais arquivos entram", padding=10)
        opcoes.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        opcoes.columnconfigure(3, weight=1)

        ttk.Label(opcoes, text="So estas extensoes:").grid(row=0, column=0, sticky="w")
        self.ext_planilha = tk.StringVar()
        ttk.Entry(opcoes, textvariable=self.ext_planilha, width=28).grid(
            row=0, column=1, columnspan=2, sticky="w")
        ttk.Label(opcoes, text="ex: pdf, docx   (vazio = tudo)").grid(
            row=0, column=3, sticky="w", padx=8)

        self.ocultos_planilha = tk.BooleanVar()
        ttk.Checkbutton(opcoes, text="Incluir arquivos ocultos",
                        variable=self.ocultos_planilha).grid(row=1, column=0, columnspan=3,
                                                             sticky="w", pady=(8, 0))

        if listador.openpyxl is None:
            ttk.Label(aba, foreground="#b03030",
                      text="Falta a biblioteca openpyxl. No Prompt de Comando rode:\n"
                           "    pip install openpyxl pypdf python-docx").grid(
                row=6, column=0, columnspan=3, sticky="w", pady=(4, 0))

        botoes = ttk.Frame(aba)
        botoes.grid(row=7, column=0, columnspan=3, sticky="e", pady=(12, 0))
        self.botao_planilha = ttk.Button(botoes, text="Gerar planilha", style="Acao.TButton",
                                         command=self._gerar_planilha)
        self.botao_planilha.pack(side="left")

        aba.columnconfigure(1, weight=1)
        return aba

    def _atualizar_modo_lista(self) -> None:
        """O limite de caracteres so vale quando o conteudo e lido."""
        estado = "disabled" if self.modo_lista.get() == "nomes" else "normal"
        self.campo_limite.configure(state=estado)
        cor = "#909090" if estado == "disabled" else ""
        for rotulo in (self.rotulo_limite, self.rotulo_caracteres):
            rotulo.configure(foreground=cor)

    def _linha_pasta(self, aba, linha, rotulo, variavel, comando) -> None:
        ttk.Label(aba, text=rotulo).grid(row=linha, column=0, sticky="w", pady=6)
        ttk.Entry(aba, textvariable=variavel).grid(row=linha, column=1, sticky="ew", padx=6)
        ttk.Button(aba, text="Procurar...", command=comando).grid(row=linha, column=2)

    # ----------------------------------------------------------------- escolhas

    def _escolher_pasta(self, variavel: tk.StringVar) -> None:
        inicial = variavel.get() or str(Path.home())
        escolhida = filedialog.askdirectory(title="Escolha a pasta", initialdir=inicial)
        if escolhida:
            variavel.set(os.path.normpath(escolhida))

    def _escolher_origem(self) -> None:
        self._escolher_pasta(self.origem)
        origem = self.origem.get()
        if origem and not self.destino.get():
            self.destino.set(os.path.normpath(f"{origem}-extract"))

    def _escolher_pasta_docs(self) -> None:
        self._escolher_pasta(self.pasta_docs)
        self._sugerir_saida()

    def _sugerir_saida(self) -> None:
        pasta = self.pasta_docs.get()
        if pasta and not self.arquivo_saida.get():
            alvo = Path(pasta)
            self.arquivo_saida.set(str(alvo.parent / f"{alvo.name} - lista.xlsx"))

    def _escolher_saida(self) -> None:
        atual = Path(self.arquivo_saida.get() or Path.home() / "lista_documentos.xlsx")
        escolhido = filedialog.asksaveasfilename(
            title="Salvar planilha como", defaultextension=".xlsx",
            initialdir=str(atual.parent), initialfile=atual.name,
            filetypes=[("Planilha do Excel", "*.xlsx")])
        if escolhido:
            self.arquivo_saida.set(os.path.normpath(escolhido))

    # ------------------------------------------------------------------ tarefas

    def _extrair(self, simular: bool) -> None:
        if self.ocupado:
            return
        origem = self.origem.get().strip()
        destino = self.destino.get().strip()
        if not origem or not Path(origem).is_dir():
            messagebox.showwarning(TITULO, "Escolha uma pasta de origem valida.")
            return
        if not destino:
            messagebox.showwarning(TITULO, "Escolha a pasta de destino.")
            return
        if self.modo.get() == "mover" and not simular:
            if not messagebox.askyesno(
                    TITULO, "Mover tira os arquivos das pastas originais.\n\nContinuar?"):
                return

        self.encadear = self.depois.get() == "listar" and not simular
        alvo = Path(destino)
        self.ultima_saida = alvo
        if self.encadear:
            self.pasta_docs.set(str(alvo))
            self._sugerir_saida()

        # As variaveis do Tkinter so podem ser lidas na thread principal, entao
        # o valor de cada opcao e capturado aqui, antes de a tarefa comecar.
        parametros = dict(
            origem=Path(origem).expanduser().resolve(),
            destino=alvo.expanduser().resolve(),
            mover=self.modo.get() == "mover",
            conflito=self.conflito.get(),
            extensoes=separar_extensoes(self.ext_extrair.get()),
            incluir_ocultos=self.ocultos_extrair.get(),
            usar_prefixo=self.prefixo.get(),
            separador="_",
            simular=simular,
            limpar_vazias=self.limpar_vazias.get(),
        )
        self._iniciar(
            "Simulando..." if simular else "Juntando arquivos...",
            lambda log, progresso: extrator.extrair(log=log, progresso=progresso, **parametros))

    def _gerar_planilha(self) -> None:
        if self.ocupado:
            return
        if listador.openpyxl is None:
            messagebox.showerror(TITULO, listador.AVISO_INSTALACAO)
            return
        pasta = self.pasta_docs.get().strip()
        if not pasta or not Path(pasta).is_dir():
            messagebox.showwarning(TITULO, "Escolha a pasta dos documentos.")
            return
        self._sugerir_saida()
        saida = Path(self.arquivo_saida.get().strip())
        if saida.suffix.lower() not in {".xlsx", ".xlsm"}:
            saida = saida.with_suffix(".xlsx")
            self.arquivo_saida.set(str(saida))

        self.ultima_saida = saida
        self.abas.select(1)
        try:
            limite = max(0, int(self.limite.get() or 0))
        except (tk.TclError, ValueError):
            limite = 2000
        parametros = dict(
            pasta=Path(pasta).expanduser().resolve(),
            saida=saida.expanduser().resolve(),
            extensoes=separar_extensoes(self.ext_planilha.get()),
            limite_conteudo=limite,
            sem_conteudo=self.modo_lista.get() == "nomes",
            incluir_ocultos=self.ocultos_planilha.get(),
        )
        self._iniciar(
            "Lendo os documentos...",
            lambda log, progresso: listador.montar_planilha(
                log=log, progresso=progresso, **parametros))

    def _iniciar(self, mensagem: str, tarefa) -> None:
        self.ocupado = True
        self.barra.configure(value=0, maximum=100)
        self.status.configure(text=mensagem)
        self.botao_abrir.configure(state="disabled")
        for botao in (self.botao_extrair, self.botao_simular, self.botao_planilha):
            botao.configure(state="disabled")
        self._escrever(f"--- {mensagem}", "ok")

        def trabalhar() -> None:
            log = lambda texto: self.fila.put(("log", texto))  # noqa: E731
            progresso = lambda feitos, total: self.fila.put(("prog", (feitos, total)))  # noqa: E731
            try:
                codigo = tarefa(log, progresso)
            except Exception:
                self.fila.put(("log", traceback.format_exc()))
                codigo = 1
            self.fila.put(("fim", codigo))

        threading.Thread(target=trabalhar, daemon=True).start()

    # --------------------------------------------------------------------- fila

    def _drenar_fila(self) -> None:
        try:
            while True:
                tipo, dado = self.fila.get_nowait()
                if tipo == "log":
                    self._escrever(dado, "erro" if str(dado).startswith("erro") else None)
                elif tipo == "prog":
                    feitos, total = dado
                    self.barra.configure(maximum=max(total, 1), value=feitos)
                    self.status.configure(text=f"{feitos} de {total}...")
                elif tipo == "fim":
                    self._terminar(dado)
        except queue.Empty:
            pass
        self.after(100, self._drenar_fila)

    def _terminar(self, codigo: int) -> None:
        self.ocupado = False
        for botao in (self.botao_extrair, self.botao_simular, self.botao_planilha):
            botao.configure(state="normal")
        if codigo == 0:
            self.status.configure(text="Concluido.")
            self._escrever("--- concluido", "ok")
            if self.ultima_saida and self.ultima_saida.exists():
                self.botao_abrir.configure(state="normal")
            if self.encadear:
                self.encadear = False
                self.abas.select(1)
                self.after(300, self._gerar_planilha)
        else:
            self.barra.configure(value=0)
            self.status.configure(text="Terminou com erro. Veja as mensagens acima.")

    def _escrever(self, texto: str, marca: str | None = None) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{texto}\n", marca or ())
        self.log.see("end")
        self.log.configure(state="disabled")

    def _limpar_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.barra.configure(value=0)
        self.status.configure(text="Pronto.")

    def _abrir_resultado(self) -> None:
        if self.ultima_saida and self.ultima_saida.exists():
            abrir_no_sistema(self.ultima_saida)

    # ------------------------------------------------------------------ config

    def _carregar_config(self) -> None:
        """Recupera as escolhas da ultima vez; qualquer defeito no arquivo e ignorado."""
        try:
            dados = json.loads(CONFIG.read_text(encoding="utf-8"))
            self.origem.set(dados.get("origem", ""))
            self.destino.set(dados.get("destino", ""))
            self.pasta_docs.set(dados.get("pasta_docs", ""))
            self.arquivo_saida.set(dados.get("saida", ""))
            self.ext_extrair.set(dados.get("ext_extrair", ""))
            self.ext_planilha.set(dados.get("ext_planilha", ""))
            self.limite.set(int(dados.get("limite", 2000)))
            if dados.get("modo_lista") in {"completo", "nomes"}:
                self.modo_lista.set(dados["modo_lista"])
            if dados.get("depois") in {"parar", "listar"}:
                self.depois.set(dados["depois"])
        except Exception:
            pass
        self._atualizar_modo_lista()

    def _ao_fechar(self) -> None:
        if self.ocupado and not messagebox.askyesno(
                TITULO, "Ainda esta processando. Fechar mesmo assim?"):
            return
        try:
            CONFIG.write_text(json.dumps({
                "origem": self.origem.get(),
                "destino": self.destino.get(),
                "pasta_docs": self.pasta_docs.get(),
                "saida": self.arquivo_saida.get(),
                "ext_extrair": self.ext_extrair.get(),
                "ext_planilha": self.ext_planilha.get(),
                "limite": int(self.limite.get() or 2000),
                "modo_lista": self.modo_lista.get(),
                "depois": self.depois.get(),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
        self.destroy()


def main() -> int:
    if sys.platform == "win32":  # deixa o texto nitido em telas com escala
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    App().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
