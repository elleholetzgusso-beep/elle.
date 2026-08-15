"""Interfaz gráfica (Tkinter) del Organizador de carpetas y proyectos — Exceltic.

Sustituye el menú de consola de ``lanzador.py`` por una ventana. El motor real
(``organizador/``) no se toca: esta capa solo pide datos, muestra siempre una
previsualización (``simular=True``) antes de aplicar nada, y traduce cualquier
fallo a un mensaje comprensible en español.

Colocar este archivo junto a ``lanzador.py`` (misma carpeta que ``organizador/``).
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, date
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, ttk

_RAIZ = Path(__file__).resolve().parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from organizador.arrumador import ErroDeOrganizacao, organizar
from organizador.criador import ErroDeCriacao
from organizador.desfazer import desfazer_operacao
from organizador.historico import Historico, resumir
from organizador.modelos import ErroDeModelo
from organizador.projetos import ErroDeProjeto, criar_envio, criar_projeto

# --------------------------------------------------------------------- identidad
NARANJA = "#f15722"
NARANJA_OSCURO = "#d94e14"
NARANJA_CLARO = "#f47d31"
NARANJA_SUAVE = "#fde7d9"
PETROLEO = "#0a2c3b"
PETROLEO_CLARO = "#125d72"
NEGRO = "#1a1a1a"
GRIS_TEXTO = "#4a4a4a"
GRIS_SUAVE = "#7a7a7a"
GRIS_LINEA = "#c1c2c4"
GRIS_FONDO = "#f2f2f2"
BLANCO = "#ffffff"
VERDE = "#2e7d4f"
VERDE_FONDO = "#eef6f1"
ROJO = "#c62828"
ROJO_FONDO = "#fbeeee"
AMBAR = "#c98a1c"

F = "Arial"

AVISO = ("Revisa el resultado antes de darlo por bueno. "
         "Esta herramienta no sustituye la comprobación humana.")

ERRORES_CONOCIDOS = (
    ErroDeCriacao, ErroDeOrganizacao, ErroDeProjeto, ErroDeModelo,
    ValueError, FileNotFoundError, PermissionError, OSError,
)

CRITERIOS = [
    ("tipo", "Tipo de archivo", "Documentos, Imágenes, Hojas de cálculo…"),
    ("documento", "Código de documento", "EXC2026-16883-001-PES-01 → 001-PES"),
    ("extensao", "Extensión", "PDF, XLSX, DWG…"),
    ("data", "Fecha de modificación", "2026-05 Mayo, 2026-06 Junio…"),
    ("alfabetico", "Letra inicial", "A, B, E, M, P…"),
]

OPERACIONES = [
    ("organizar", "1", "Organizar documentos", "Mueve archivos a subcarpetas"),
    ("proyecto", "2", "Crear proyecto nuevo", "AAAA-CÓDIGO-NOMBRE con su estructura"),
    ("envio", "3", "Registrar envío", "Siguiente carpeta Envío N AAAAMMDD"),
    ("historial", "4", "Historial y deshacer", "Revertir lo que hizo el programa"),
]


def limpiar_ruta(texto: str) -> str:
    return texto.strip().strip('"').strip("'").strip()


def validar_carpeta(ruta: Path, *, exigir_archivos: bool = False) -> None:
    if not ruta.exists():
        raise ErroDeOrganizacao(
            f"La carpeta '{ruta}' no existe. Comprueba la ruta (o que la unidad "
            "de red esté conectada) e inténtalo de nuevo."
        )
    if not ruta.is_dir():
        raise ErroDeOrganizacao(f"'{ruta}' no es una carpeta.")
    if not os.access(ruta, os.W_OK):
        raise ErroDeOrganizacao(
            f"No hay permiso de escritura en '{ruta}'. Comprueba el acceso a la "
            "carpeta o a la unidad de red."
        )
    if exigir_archivos and not any(p.is_file() for p in ruta.iterdir()):
        raise ErroDeOrganizacao(
            f"La carpeta '{ruta}' no contiene ningún archivo para organizar."
        )


def escribir_log_error(carpeta_destino: Path, contexto: str) -> Path:
    momento = datetime.now().strftime("%Y%m%d-%H%M%S")
    nombre = f"ERROR_organizador_{momento}.txt"
    contenido = (
        f"Fecha: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Operación: {contexto}\n\n" + traceback.format_exc()
    )
    try:
        log = carpeta_destino / nombre
        log.write_text(contenido, encoding="utf-8")
        return log
    except OSError:
        log = Path.home() / nombre
        try:
            log.write_text(contenido, encoding="utf-8")
        except OSError:
            pass
        return log


# ------------------------------------------------------------------ componentes
class BotonPlano(tk.Label):
    """Botón rectangular plano (sin bordes de sistema), en la línea de la marca."""

    def __init__(self, padre, texto, comando, *, tipo="primario", ancho_pad=22):
        colores = {
            "primario": (NARANJA, BLANCO, NARANJA_OSCURO),
            "secundario": (BLANCO, NARANJA, NARANJA_SUAVE),
            "neutro": (BLANCO, NEGRO, GRIS_FONDO),
        }[tipo]
        self._fondo, self._texto_color, self._hover = colores
        super().__init__(
            padre, text=texto, bg=self._fondo, fg=self._texto_color,
            font=(F, 10, "bold"), padx=ancho_pad, pady=10, cursor="hand2",
        )
        if tipo == "secundario":
            self.configure(highlightbackground=NARANJA, highlightthickness=2, bd=0)
        self._comando = comando
        self.bind("<Button-1>", lambda _e: self._comando())
        self.bind("<Enter>", lambda _e: self.configure(bg=self._hover))
        self.bind("<Leave>", lambda _e: self.configure(bg=self._fondo))


class Campo(tk.Frame):
    """Etiqueta + entrada de texto, opcionalmente con botón Examinar."""

    def __init__(self, padre, etiqueta, variable, *, examinar=None, ancho=40, pista=None):
        super().__init__(padre, bg=BLANCO)
        tk.Label(self, text=etiqueta.upper(), bg=BLANCO, fg=GRIS_TEXTO,
                 font=(F, 9, "bold")).pack(anchor="w", pady=(0, 5))
        fila = tk.Frame(self, bg=BLANCO)
        fila.pack(fill="x")
        self.var = variable
        self.entrada = tk.Entry(
            fila, textvariable=self.var, font=(F, 10), bg=BLANCO, fg=NEGRO,
            relief="solid", bd=1, highlightthickness=0, insertbackground=NEGRO,
            width=ancho,
        )
        self.entrada.pack(side="left", fill="x", expand=True, ipady=6)
        if examinar:
            BotonPlano(fila, "Examinar…", examinar, tipo="neutro", ancho_pad=14).pack(
                side="left", padx=(6, 0), fill="y")
        if pista:
            tk.Label(self, text=pista, bg=BLANCO, fg=GRIS_SUAVE,
                     font=(F, 8)).pack(anchor="w", pady=(4, 0))

    def get(self) -> str:
        return self.var.get()


# ------------------------------------------------------------------- aplicación
class App(tk.Tk):
    def __init__(self, carpeta_inicial: str | None = None):
        super().__init__()
        self.title("Organizador de carpetas y proyectos — Exceltic")
        self.geometry("1180x780")
        self.minsize(1000, 660)
        self.configure(bg=GRIS_FONDO)

        self.hist = Historico()
        self.operacion = "organizar"
        self.etapa = "form"
        self.ruta = tk.StringVar(value=carpeta_inicial or "")
        self.criterio = tk.StringVar(value="tipo")
        self.recursivo = tk.BooleanVar(value=False)
        self.v_nombre = tk.StringVar()
        self.v_codigo = tk.StringVar()
        self.v_ano = tk.StringVar(value=str(date.today().year))
        self.v_fecha = tk.StringVar()
        self.v_obs = tk.StringVar()
        self.previa = None          # datos calculados en la simulación
        self.ultimo_id = None
        self.error = None
        self._logo = None

        self._construir_marca()
        self._construir_cuerpo()
        self._pintar()

    # ------------------------------------------------------------------ marca
    def _construir_marca(self):
        barra = tk.Frame(self, bg=PETROLEO, height=40)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        marca = _cargar_logo(_RAIZ / "assets" / "logo-mark.png", 20)
        if marca:
            self._logo_mark = marca
            tk.Label(barra, image=marca, bg=PETROLEO).pack(side="left", padx=(14, 10))
        tk.Label(barra, text="Organizador de carpetas y proyectos — Exceltic",
                 bg=PETROLEO, fg=BLANCO, font=(F, 9)).pack(side="left")

        cabecera = tk.Frame(self, bg=BLANCO)
        cabecera.pack(fill="x")
        interior = tk.Frame(cabecera, bg=BLANCO)
        interior.pack(fill="x", padx=26, pady=(16, 12))

        lockup = _cargar_logo(_RAIZ / "assets" / "logo-lockup.png", 44)
        if lockup:
            self._logo = lockup
            tk.Label(interior, image=lockup, bg=BLANCO).pack(side="left", padx=(0, 18))
        else:
            tk.Label(interior, text="EXCELTIC", bg=BLANCO, fg=NEGRO,
                     font=(F, 18, "bold")).pack(side="left", padx=(0, 18))

        textos = tk.Frame(interior, bg=BLANCO)
        textos.pack(side="left", fill="x", expand=True)
        self.lbl_titulo = tk.Label(textos, text="", bg=BLANCO, fg=NEGRO,
                                   font=(F, 15, "bold"), anchor="w")
        self.lbl_titulo.pack(fill="x")
        self.lbl_subtitulo = tk.Label(textos, text="", bg=BLANCO, fg=GRIS_SUAVE,
                                      font=(F, 10), anchor="w")
        self.lbl_subtitulo.pack(fill="x", pady=(2, 0))

        tk.Frame(cabecera, bg=NARANJA, height=3).pack(fill="x")

    # ----------------------------------------------------------------- cuerpo
    def _construir_cuerpo(self):
        cuerpo = tk.Frame(self, bg=BLANCO)
        cuerpo.pack(fill="both", expand=True)

        lateral = tk.Frame(cuerpo, bg=PETROLEO, width=268)
        lateral.pack(side="left", fill="y")
        lateral.pack_propagate(False)
        tk.Label(lateral, text="OPERACIONES", bg=PETROLEO, fg="#9fb6c0",
                 font=(F, 8, "bold")).pack(anchor="w", padx=18, pady=(16, 10))

        self.items_lateral = {}
        for clave, num, titulo, desc in OPERACIONES:
            self.items_lateral[clave] = self._item_lateral(lateral, clave, num, titulo, desc)

        tarjeta = tk.Frame(lateral, bg="#123c4c")
        tarjeta.pack(side="bottom", fill="x", padx=16, pady=16)
        tk.Frame(tarjeta, bg=NARANJA, height=3).pack(fill="x")
        tk.Label(tarjeta, text="ÚLTIMA OPERACIÓN", bg="#123c4c", fg="#9fb6c0",
                 font=(F, 8, "bold")).pack(anchor="w", padx=14, pady=(12, 6))
        self.lbl_ultima = tk.Label(tarjeta, text="", bg="#123c4c", fg=BLANCO,
                                   font=(F, 9), wraplength=210, justify="left")
        self.lbl_ultima.pack(anchor="w", padx=14)
        enlace = tk.Label(tarjeta, text="Ver historial y deshacer →", bg="#123c4c",
                          fg=NARANJA_CLARO, font=(F, 9, "bold"), cursor="hand2")
        enlace.pack(anchor="w", padx=14, pady=(8, 14))
        enlace.bind("<Button-1>", lambda _e: self.abrir("historial"))

        derecha = tk.Frame(cuerpo, bg=BLANCO)
        derecha.pack(side="left", fill="both", expand=True)

        self.barra_pasos = tk.Frame(derecha, bg=BLANCO)
        self.barra_pasos.pack(fill="x", padx=26, pady=(16, 0))
        self.pasos = []
        for i, nombre in enumerate(("Datos", "Previsualización", "Resultado")):
            celda = tk.Frame(self.barra_pasos, bg=BLANCO)
            celda.pack(side="left", fill="x", expand=(i < 2))
            punto = tk.Label(celda, text=str(i + 1), width=2, font=(F, 9, "bold"))
            punto.pack(side="left")
            etiqueta = tk.Label(celda, text=nombre, bg=BLANCO, font=(F, 9, "bold"))
            etiqueta.pack(side="left", padx=(8, 10))
            linea = tk.Frame(celda, bg=GRIS_LINEA, height=2)
            if i < 2:
                linea.pack(side="left", fill="x", expand=True, padx=(0, 10))
            self.pasos.append((punto, etiqueta, linea))

        self.contenido = tk.Frame(derecha, bg=BLANCO)
        self.contenido.pack(fill="both", expand=True, padx=26, pady=(18, 8))

        pie = tk.Frame(derecha, bg=GRIS_FONDO)
        pie.pack(fill="x")
        tk.Frame(pie, bg=GRIS_LINEA, height=1).pack(fill="x")
        interior_pie = tk.Frame(pie, bg=GRIS_FONDO)
        interior_pie.pack(fill="x", padx=26, pady=12)
        tk.Label(interior_pie, text=AVISO, bg=GRIS_FONDO, fg=GRIS_SUAVE,
                 font=(F, 8), wraplength=440, justify="left").pack(side="left")
        self.btn_primario = BotonPlano(interior_pie, "", self._avanzar, tipo="primario")
        self.btn_primario.pack(side="right")
        self.btn_secundario = BotonPlano(interior_pie, "", self._retroceder,
                                         tipo="secundario", ancho_pad=16)

    def _item_lateral(self, padre, clave, num, titulo, desc):
        fila = tk.Frame(padre, bg=PETROLEO, cursor="hand2")
        fila.pack(fill="x")
        marca = tk.Frame(fila, bg=PETROLEO, width=4)
        marca.pack(side="left", fill="y")
        cuerpo = tk.Frame(fila, bg=PETROLEO)
        cuerpo.pack(side="left", fill="x", expand=True, padx=(14, 14), pady=12)
        numero = tk.Label(cuerpo, text=num, bg="#1d4a5c", fg=BLANCO,
                          font=(F, 9, "bold"), width=2, height=1)
        numero.pack(side="left", padx=(0, 12), anchor="n")
        textos = tk.Frame(cuerpo, bg=PETROLEO)
        textos.pack(side="left", fill="x", expand=True)
        lt = tk.Label(textos, text=titulo, bg=PETROLEO, fg=BLANCO,
                      font=(F, 10, "bold"), anchor="w")
        lt.pack(fill="x")
        ld = tk.Label(textos, text=desc, bg=PETROLEO, fg="#9fb6c0", font=(F, 8),
                      anchor="w", wraplength=180, justify="left")
        ld.pack(fill="x")
        for w in (fila, cuerpo, textos, numero, lt, ld):
            w.bind("<Button-1>", lambda _e, c=clave: self.abrir(c))
        return {"fila": fila, "marca": marca, "cuerpo": cuerpo, "textos": textos,
                "numero": numero, "titulo": lt, "desc": ld}

    # ------------------------------------------------------------ navegación
    def abrir(self, clave):
        self.operacion = clave
        self.etapa = "historial" if clave == "historial" else "form"
        self.previa = None
        self.error = None
        self._pintar()

    def _avanzar(self):
        if self.operacion == "historial":
            self.abrir("organizar")
            return
        if self.etapa in ("resultado", "error"):
            self.etapa = "form"
            self.previa = None
            self.error = None
            self._pintar()
            return
        if self.etapa == "form":
            self._ejecutar(simular=True)
        else:
            self._ejecutar(simular=False)

    def _retroceder(self):
        if self.etapa == "previa":
            self.etapa = "form"
            self._pintar()
        elif self.etapa == "resultado":
            self.abrir("historial")
        elif self.etapa == "error":
            self.abrir("organizar")

    def _examinar(self):
        elegida = filedialog.askdirectory(title="Elige la carpeta")
        if elegida:
            self.ruta.set(str(Path(elegida)))

    # -------------------------------------------------------------- ejecución
    def _ejecutar(self, *, simular: bool):
        carpeta = Path(limpiar_ruta(self.ruta.get())).expanduser() if self.ruta.get() else None
        try:
            if self.operacion == "organizar":
                self._ejecutar_organizar(carpeta, simular)
            elif self.operacion == "proyecto":
                self._ejecutar_proyecto(carpeta, simular)
            else:
                self._ejecutar_envio(carpeta, simular)
        except ERRORES_CONOCIDOS as erro:
            self.error = {"titulo": "No se ha podido continuar", "texto": str(erro), "log": None}
            self.etapa = "error"
        except Exception:
            log = escribir_log_error(carpeta or Path.home(), contexto=self.operacion)
            self.error = {
                "titulo": "Ha ocurrido un problema inesperado",
                "texto": ("La operación no se ha podido completar. No se ha cambiado "
                          "nada más en la carpeta."),
                "log": str(log),
            }
            self.etapa = "error"
        self._pintar()

    def _ejecutar_organizar(self, carpeta, simular):
        if carpeta is None:
            raise ErroDeOrganizacao("Indica la carpeta que quieres organizar.")
        validar_carpeta(carpeta, exigir_archivos=True)
        resultado = organizar(carpeta, self.criterio.get(),
                              recursivo=self.recursivo.get(), simular=simular)
        filas = [(m.origem.name, str(m.destino.relative_to(carpeta))) for m in resultado.movimentos]
        self.previa = {
            "filas": filas,
            "ignorados": [(a.name, motivo) for a, motivo in resultado.ignorados],
            "carpetas": len({d.split(os.sep)[0] for _o, d in filas}),
            "base": carpeta,
            "titulo": f"{len(filas)} archivo(s) movido(s) correctamente",
        }
        if simular:
            self.etapa = "previa"
            return
        if resultado.movimentos:
            self.ultimo_id = self.hist.registrar(
                "organizar", carpeta,
                movimentos=[{"de": str(m.origem), "para": str(m.destino)}
                            for m in resultado.movimentos],
                pastas_criadas=[str(p) for p in resultado.pastas_criadas],
                detalhes={"criterio": self.criterio.get()},
            )
        self.etapa = "resultado"

    def _ejecutar_proyecto(self, carpeta, simular):
        if carpeta is None:
            raise ErroDeProjeto("Indica la carpeta donde se creará el proyecto.")
        validar_carpeta(carpeta)
        nombre = self.v_nombre.get().strip()
        codigo = self.v_codigo.get().strip()
        ano = self.v_ano.get().strip()
        if not (nombre and codigo and ano):
            raise ErroDeProjeto("Rellena nombre, código y año del proyecto.")
        resultado = criar_projeto(carpeta, ano, codigo, nombre, simular=simular)
        base = resultado.pasta
        filas = []
        for creada in resultado.criacao.criadas:
            etiqueta = str(creada.relative_to(base.parent))
            filas.append((base.name, etiqueta))
        self.previa = {
            "filas": filas, "ignorados": [], "carpetas": len(filas), "base": base,
            "titulo": f"Proyecto {base.name} creado",
        }
        if simular:
            self.etapa = "previa"
            return
        if resultado.criacao.criadas:
            self.ultimo_id = self.hist.registrar(
                "criar", base,
                pastas_criadas=[str(p) for p in resultado.criacao.criadas],
                detalhes={"proyecto": base.name},
            )
        self.etapa = "resultado"

    def _ejecutar_envio(self, carpeta, simular):
        if carpeta is None:
            raise ErroDeProjeto("Indica la carpeta del proyecto.")
        validar_carpeta(carpeta)
        fecha = self.v_fecha.get().strip() or None
        obs = self.v_obs.get().strip() or None
        pasta = criar_envio(carpeta, data_envio=fecha, observacao=obs, simular=simular)
        self.previa = {
            "filas": [("2_Doc Recebida", pasta.name)], "ignorados": [], "carpetas": 1,
            "base": pasta.parent, "titulo": f"Carpeta {pasta.name} creada",
        }
        if simular:
            self.etapa = "previa"
            return
        self.ultimo_id = self.hist.registrar("criar", pasta.parent,
                                             pastas_criadas=[str(pasta)])
        self.etapa = "resultado"

    def _deshacer(self, operacao):
        try:
            resultado = desfazer_operacao(operacao)
        except ERRORES_CONOCIDOS as erro:
            self.error = {"titulo": "No se ha podido deshacer", "texto": str(erro), "log": None}
            self.etapa = "error"
            self._pintar()
            return
        self.hist.remover(operacao["id"])
        self.previa = {
            "filas": [(str(a), str(b)) for a, b in resultado.restaurados]
                     + [("", f"- {p}") for p in resultado.pastas_removidas],
            "ignorados": [("", p) for p in resultado.problemas],
            "carpetas": len(resultado.pastas_removidas),
            "total": len(resultado.restaurados),
            "base": Path(operacao.get("base", ".")),
            "titulo": f"{len(resultado.restaurados)} archivo(s) restaurado(s)",
            "modo": "deshacer",
        }
        # La operación deshecha sale del historial: ya no se puede volver a
        # deshacer, así que tampoco debe anunciarse como tal en el resultado.
        self.ultimo_id = None
        self.operacion = "historial"
        self.etapa = "resultado"
        self._pintar()

    # ----------------------------------------------------------------- pintar
    def _pintar(self):
        titulos = {
            "organizar": ("Organizar documentos",
                          "Mueve los archivos de una carpeta a subcarpetas. Nunca sobrescribe nada."),
            "proyecto": ("Crear proyecto nuevo",
                         "Carpeta AAAA-CÓDIGO-NOMBRE con la estructura de obra completa."),
            "envio": ("Registrar envío de cliente",
                      "Crea la siguiente carpeta de envío dentro de 2_Doc Recebida."),
            "historial": ("Historial y deshacer",
                          "Todas las operaciones registradas por el programa."),
        }
        titulo, subtitulo = titulos[self.operacion]
        self.lbl_titulo.configure(text=titulo)
        self.lbl_subtitulo.configure(text=subtitulo)

        for clave, item in self.items_lateral.items():
            activo = clave == self.operacion
            fondo = "#123c4c" if activo else PETROLEO
            item["marca"].configure(bg=NARANJA if activo else PETROLEO)
            for k in ("fila", "cuerpo", "textos"):
                item[k].configure(bg=fondo)
            item["titulo"].configure(bg=fondo)
            item["desc"].configure(bg=fondo)
            item["numero"].configure(bg=NARANJA if activo else "#1d4a5c")

        ultima = self.hist.ultima()
        self.lbl_ultima.configure(text=resumir(ultima) if ultima else "Ninguna todavía")

        self._pintar_pasos()

        for hijo in self.contenido.winfo_children():
            hijo.destroy()

        if self.etapa == "historial":
            self._vista_historial()
        elif self.etapa == "error":
            self._vista_error()
        elif self.etapa == "previa":
            self._vista_lista(simulacion=True)
        elif self.etapa == "resultado":
            self._vista_lista(simulacion=False)
        elif self.operacion == "organizar":
            self._form_organizar()
        elif self.operacion == "proyecto":
            self._form_proyecto()
        else:
            self._form_envio()

        self._pintar_pie()

    def _pintar_pasos(self):
        if self.operacion == "historial":
            self.barra_pasos.pack_forget()
            return
        self.barra_pasos.pack(fill="x", padx=26, pady=(16, 0), before=self.contenido)
        indice = {"form": 0, "error": 0, "previa": 1, "resultado": 2}[self.etapa]
        for i, (punto, etiqueta, linea) in enumerate(self.pasos):
            if i == indice:
                punto.configure(bg=NARANJA, fg=BLANCO)
            elif i < indice:
                punto.configure(bg=NARANJA_SUAVE, fg=NARANJA_OSCURO)
            else:
                punto.configure(bg=GRIS_FONDO, fg=GRIS_SUAVE)
            etiqueta.configure(fg=NEGRO if i <= indice else GRIS_SUAVE)
            linea.configure(bg=NARANJA if i < indice else GRIS_LINEA)

    def _pintar_pie(self):
        if self.operacion == "historial":
            primario, secundario = "Volver a las operaciones", None
        elif self.etapa == "form":
            primario, secundario = "Ver previsualización", None
        elif self.etapa == "previa":
            primario = ("Aplicar y mover archivos" if self.operacion == "organizar"
                        else "Aplicar y crear carpetas")
            secundario = "Cambiar datos"
        elif self.etapa == "resultado":
            primario, secundario = "Nueva operación", "Ir al historial"
        else:
            primario, secundario = "Volver a intentarlo", "Volver al inicio"
        self.btn_primario.configure(text=primario)
        if secundario:
            self.btn_secundario.configure(text=secundario)
            self.btn_secundario.pack(side="right", padx=(0, 12))
        else:
            self.btn_secundario.pack_forget()

    # ------------------------------------------------------------ formularios
    def _form_organizar(self):
        zona = tk.Frame(self.contenido, bg=GRIS_FONDO, highlightbackground=GRIS_LINEA,
                        highlightthickness=1, cursor="hand2")
        zona.pack(fill="x")
        interior = tk.Frame(zona, bg=GRIS_FONDO)
        interior.pack(fill="x", padx=20, pady=16)
        tk.Label(interior, text="Elige la carpeta a organizar", bg=GRIS_FONDO, fg=NEGRO,
                 font=(F, 10, "bold")).pack(anchor="w")
        tk.Label(interior, text="Pega la ruta abajo o pulsa Examinar. Ej.: "
                                r"Y:\1.- En curso\2026-16883-…\2_Doc Recebida",
                 bg=GRIS_FONDO, fg=GRIS_SUAVE, font=(F, 9)).pack(anchor="w", pady=(4, 0))
        for w in (zona, interior):
            w.bind("<Button-1>", lambda _e: self._examinar())

        campo = tk.Frame(self.contenido, bg=BLANCO)
        campo.pack(fill="x", pady=(12, 18))
        fila = tk.Frame(campo, bg=BLANCO)
        fila.pack(fill="x")
        tk.Entry(fila, textvariable=self.ruta, font=(F, 10), bg=BLANCO, fg=NEGRO,
                 relief="solid", bd=1, insertbackground=NEGRO).pack(
            side="left", fill="x", expand=True, ipady=6)
        BotonPlano(fila, "Examinar…", self._examinar, tipo="neutro",
                   ancho_pad=14).pack(side="left", padx=(6, 0), fill="y")

        tk.Label(self.contenido, text="CRITERIO DE ORGANIZACIÓN", bg=BLANCO,
                 fg=GRIS_TEXTO, font=(F, 9, "bold")).pack(anchor="w")
        rejilla = tk.Frame(self.contenido, bg=BLANCO)
        rejilla.pack(fill="x", pady=(8, 16))
        rejilla.columnconfigure(0, weight=1, uniform="c")
        rejilla.columnconfigure(1, weight=1, uniform="c")
        for i, (clave, titulo, ejemplo) in enumerate(CRITERIOS):
            self._tarjeta_criterio(rejilla, clave, titulo, ejemplo, i)

        casilla = tk.Checkbutton(
            self.contenido, text="Incluir también los archivos de las subcarpetas",
            variable=self.recursivo, bg=BLANCO, fg=GRIS_TEXTO, font=(F, 10),
            activebackground=BLANCO, selectcolor=BLANCO, cursor="hand2",
            highlightthickness=0, bd=0,
        )
        casilla.pack(anchor="w")

    def _tarjeta_criterio(self, padre, clave, titulo, ejemplo, indice):
        activo = self.criterio.get() == clave
        marco = tk.Frame(padre, bg=NARANJA_SUAVE if activo else BLANCO,
                         highlightbackground=NARANJA if activo else GRIS_LINEA,
                         highlightthickness=1, cursor="hand2")
        marco.grid(row=indice // 2, column=indice % 2, sticky="ew", padx=(0, 8), pady=4)
        interior = tk.Frame(marco, bg=marco["bg"])
        interior.pack(fill="x", padx=12, pady=10)
        radio = tk.Radiobutton(interior, variable=self.criterio, value=clave,
                               bg=marco["bg"], activebackground=marco["bg"],
                               selectcolor=BLANCO, highlightthickness=0, bd=0,
                               cursor="hand2", command=self._pintar)
        radio.pack(side="left", anchor="n")
        textos = tk.Frame(interior, bg=marco["bg"])
        textos.pack(side="left", fill="x", expand=True)
        lt = tk.Label(textos, text=titulo, bg=marco["bg"], fg=NEGRO,
                      font=(F, 10, "bold"), anchor="w")
        lt.pack(fill="x")
        le = tk.Label(textos, text=ejemplo, bg=marco["bg"], fg=GRIS_SUAVE,
                      font=(F, 8), anchor="w", wraplength=260, justify="left")
        le.pack(fill="x")

        def elegir(_e=None):
            self.criterio.set(clave)
            self._pintar()

        for w in (marco, interior, textos, lt, le):
            w.bind("<Button-1>", elegir)

    def _form_proyecto(self):
        fila = tk.Frame(self.contenido, bg=BLANCO)
        fila.pack(fill="x")
        Campo(fila, "Nombre del proyecto", self.v_nombre).pack(
            side="left", fill="x", expand=True)
        Campo(fila, "Código", self.v_codigo, ancho=10).pack(side="left", padx=(12, 0))
        Campo(fila, "Año", self.v_ano, ancho=8).pack(side="left", padx=(12, 0))

        destino = tk.Frame(self.contenido, bg=BLANCO)
        destino.pack(fill="x", pady=(16, 0))
        tk.Label(destino, text="SE CREARÁ DENTRO DE", bg=BLANCO, fg=GRIS_TEXTO,
                 font=(F, 9, "bold")).pack(anchor="w", pady=(0, 5))
        linea = tk.Frame(destino, bg=BLANCO)
        linea.pack(fill="x")
        tk.Entry(linea, textvariable=self.ruta, font=(F, 10), bg=BLANCO, fg=NEGRO,
                 relief="solid", bd=1, insertbackground=NEGRO).pack(
            side="left", fill="x", expand=True, ipady=6)
        BotonPlano(linea, "Examinar…", self._examinar, tipo="neutro",
                   ancho_pad=14).pack(side="left", padx=(6, 0), fill="y")

        nota = tk.Frame(self.contenido, bg=GRIS_FONDO)
        nota.pack(fill="x", pady=(18, 0))
        tk.Label(nota, text="ESTRUCTURA QUE SE CREARÁ", bg=GRIS_FONDO, fg=GRIS_SUAVE,
                 font=(F, 8, "bold")).pack(anchor="w", padx=16, pady=(14, 6))
        tk.Label(nota, text="1_Oferta · 2_Doc Recebida (+ mails) · 3_Doc Trabajo · "
                            r"4_Doc Generada\Doc",
                 bg=GRIS_FONDO, fg=GRIS_TEXTO, font=(F, 9)).pack(anchor="w", padx=16,
                                                                 pady=(0, 14))

    def _form_envio(self):
        destino = tk.Frame(self.contenido, bg=BLANCO)
        destino.pack(fill="x")
        tk.Label(destino, text="CARPETA DEL PROYECTO", bg=BLANCO, fg=GRIS_TEXTO,
                 font=(F, 9, "bold")).pack(anchor="w", pady=(0, 5))
        linea = tk.Frame(destino, bg=BLANCO)
        linea.pack(fill="x")
        tk.Entry(linea, textvariable=self.ruta, font=(F, 10), bg=BLANCO, fg=NEGRO,
                 relief="solid", bd=1, insertbackground=NEGRO).pack(
            side="left", fill="x", expand=True, ipady=6)
        BotonPlano(linea, "Examinar…", self._examinar, tipo="neutro",
                   ancho_pad=14).pack(side="left", padx=(6, 0), fill="y")
        tk.Label(destino, text="También vale la propia carpeta 2_Doc Recebida.",
                 bg=BLANCO, fg=GRIS_SUAVE, font=(F, 8)).pack(anchor="w", pady=(4, 0))

        fila = tk.Frame(self.contenido, bg=BLANCO)
        fila.pack(fill="x", pady=(16, 0))
        Campo(fila, "Fecha del envío", self.v_fecha, ancho=16,
              pista="AAAAMMDD, AAAA-MM-DD o DD/MM/AAAA · vacío = hoy").pack(side="left")
        Campo(fila, "Observación (opcional)", self.v_obs, ancho=30,
              pista="ej.: sin revisar").pack(side="left", fill="x", expand=True, padx=(12, 0))

    # ----------------------------------------------------------------- listas
    def _vista_lista(self, *, simulacion: bool):
        datos = self.previa or {"filas": [], "ignorados": [], "carpetas": 0, "titulo": ""}
        deshecho = datos.get("modo") == "deshacer"

        if simulacion:
            aviso = tk.Frame(self.contenido, bg=NARANJA_SUAVE)
            aviso.pack(fill="x")
            tk.Frame(aviso, bg=NARANJA, width=4).pack(side="left", fill="y")
            tk.Label(aviso, text="SIMULACIÓN", bg=NARANJA_SUAVE, fg=NARANJA_OSCURO,
                     font=(F, 9, "bold")).pack(side="left", padx=(14, 10), pady=12)
            tk.Label(aviso, text="Todavía no se ha movido ni creado nada. Revisa la lista "
                                "y pulsa Aplicar.", bg=NARANJA_SUAVE, fg=GRIS_TEXTO,
                     font=(F, 9)).pack(side="left")
        else:
            aviso = tk.Frame(self.contenido, bg=VERDE_FONDO)
            aviso.pack(fill="x")
            tk.Frame(aviso, bg=VERDE, width=4).pack(side="left", fill="y")
            textos = tk.Frame(aviso, bg=VERDE_FONDO)
            textos.pack(side="left", padx=14, pady=12)
            tk.Label(textos, text=datos["titulo"], bg=VERDE_FONDO, fg=NEGRO,
                     font=(F, 10, "bold")).pack(anchor="w")
            if deshecho:
                detalle = ("Todo ha vuelto a como estaba. La operación ya no aparece "
                           "en el historial.")
            elif self.ultimo_id:
                detalle = f"Registrado en el historial como {self.ultimo_id} — se puede deshacer."
            else:
                detalle = "Operación completada."
            tk.Label(textos, text=detalle, bg=VERDE_FONDO, fg=GRIS_TEXTO,
                     font=(F, 9)).pack(anchor="w")

        contadores = tk.Frame(self.contenido, bg=BLANCO)
        contadores.pack(fill="x", pady=(12, 12))
        if deshecho:
            rotulos = ("RESTAURADOS", "CARPETAS ELIMINADAS", "NO SE HAN PODIDO DESHACER")
        else:
            principal = ("SE MOVERÁN" if simulacion else "MOVIDOS") \
                if self.operacion == "organizar" else ("SE CREARÁN" if simulacion else "CREADAS")
            rotulos = (principal, "SUBCARPETAS", "IGNORADOS")
        for i, (valor, rotulo, fuerte) in enumerate((
            (datos.get("total", len(datos["filas"])), rotulos[0], True),
            (datos["carpetas"], rotulos[1], False),
            (len(datos["ignorados"]), rotulos[2], False),
        )):
            caja = tk.Frame(contadores, bg=NARANJA if fuerte else PETROLEO)
            caja.pack(side="left", fill="x", expand=True, padx=(0 if i == 0 else 8, 0))
            tk.Label(caja, text=str(valor), bg=caja["bg"], fg=BLANCO,
                     font=(F, 17, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(caja, text=rotulo, bg=caja["bg"], fg=BLANCO,
                     font=(F, 8, "bold")).pack(anchor="w", padx=16, pady=(2, 12))

        tabla = ttk.Treeview(self.contenido, columns=("origen", "destino"),
                             show="headings", height=10)
        tabla.heading("origen", text="ORIGEN")
        tabla.heading("destino", text="DESTINO")
        tabla.column("origen", width=340, anchor="w")
        tabla.column("destino", width=340, anchor="w")
        estilo = ttk.Style(self)
        estilo.configure("Treeview", font=(F, 9), rowheight=24, borderwidth=1,
                         fieldbackground=BLANCO, background=BLANCO)
        estilo.configure("Treeview.Heading", font=(F, 8, "bold"), foreground=GRIS_SUAVE)
        for origen, destino in datos["filas"]:
            tabla.insert("", "end", values=(origen, destino))
        tabla.pack(fill="both", expand=True)

        if datos["ignorados"]:
            tk.Label(self.contenido, text="PROBLEMAS AL DESHACER" if deshecho else "NO SE MOVERÁN",
                     bg=BLANCO, fg=GRIS_SUAVE,
                     font=(F, 8, "bold")).pack(anchor="w", pady=(12, 4))
            for nombre, motivo in datos["ignorados"][:6]:
                tk.Label(self.contenido, text=f"·  {nombre} — {motivo}", bg=BLANCO,
                         fg=AMBAR if not nombre else GRIS_SUAVE,
                         font=(F, 9)).pack(anchor="w")

    def _vista_historial(self):
        tk.Label(self.contenido,
                 text="Deshacer devuelve los archivos a donde estaban y elimina las carpetas "
                      "que el programa creó. Solo actúa sobre lo que hizo esta herramienta.",
                 bg=BLANCO, fg=GRIS_TEXTO, font=(F, 10), wraplength=760,
                 justify="left").pack(anchor="w", pady=(0, 14))

        operaciones = self.hist.listar(20)
        if not operaciones:
            tk.Label(self.contenido, text="No hay ninguna operación registrada todavía.",
                     bg=BLANCO, fg=GRIS_SUAVE, font=(F, 10)).pack(anchor="w")
            return

        for operacao in operaciones:
            fila = tk.Frame(self.contenido, bg=BLANCO, highlightbackground=GRIS_LINEA,
                            highlightthickness=1)
            fila.pack(fill="x", pady=(0, 8))
            tk.Frame(fila, bg=NARANJA, width=4).pack(side="left", fill="y")
            icono = "⇄" if operacao.get("tipo") == "organizar" else "+"
            tk.Label(fila, text=icono, bg=NARANJA, fg=BLANCO, font=(F, 12, "bold"),
                     width=2).pack(side="left", padx=14, pady=14)
            textos = tk.Frame(fila, bg=BLANCO)
            textos.pack(side="left", fill="x", expand=True, pady=12)
            tk.Label(textos, text=resumir(operacao), bg=BLANCO, fg=NEGRO,
                     font=(F, 10, "bold"), anchor="w", wraplength=520,
                     justify="left").pack(fill="x")
            tk.Label(textos, text=operacao.get("base", ""), bg=BLANCO, fg=GRIS_SUAVE,
                     font=(F, 8), anchor="w").pack(fill="x")
            BotonPlano(fila, "Deshacer", lambda o=operacao: self._deshacer(o),
                       tipo="secundario", ancho_pad=14).pack(side="right", padx=14)

    def _vista_error(self):
        error = self.error or {}
        caja = tk.Frame(self.contenido, bg=ROJO_FONDO)
        caja.pack(fill="x")
        tk.Frame(caja, bg=ROJO, width=4).pack(side="left", fill="y")
        tk.Label(caja, text="!", bg=ROJO, fg=BLANCO, font=(F, 12, "bold"),
                 width=2).pack(side="left", padx=14, pady=16, anchor="n")
        textos = tk.Frame(caja, bg=ROJO_FONDO)
        textos.pack(side="left", fill="x", expand=True, pady=16, padx=(0, 16))
        tk.Label(textos, text=error.get("titulo", ""), bg=ROJO_FONDO, fg=NEGRO,
                 font=(F, 10, "bold"), anchor="w").pack(fill="x")
        tk.Label(textos, text=error.get("texto", ""), bg=ROJO_FONDO, fg=GRIS_TEXTO,
                 font=(F, 10), wraplength=620, justify="left",
                 anchor="w").pack(fill="x", pady=(6, 0))

        if error.get("log"):
            detalle = tk.Frame(self.contenido, bg=GRIS_FONDO)
            detalle.pack(fill="x", pady=(14, 0))
            tk.Label(detalle, text="DETALLE TÉCNICO GUARDADO EN", bg=GRIS_FONDO,
                     fg=GRIS_SUAVE, font=(F, 8, "bold")).pack(anchor="w", padx=16,
                                                              pady=(14, 6))
            tk.Label(detalle, text=error["log"], bg=GRIS_FONDO, fg=NEGRO, font=(F, 9),
                     wraplength=700, justify="left").pack(anchor="w", padx=16)
            acciones = tk.Frame(detalle, bg=GRIS_FONDO)
            acciones.pack(anchor="w", padx=16, pady=12)
            BotonPlano(acciones, "Abrir carpeta del archivo",
                       lambda: _abrir_en_explorador(Path(error["log"]).parent),
                       tipo="neutro", ancho_pad=14).pack(side="left")
            BotonPlano(acciones, "Copiar ruta",
                       lambda: self._copiar(error["log"]), tipo="neutro",
                       ancho_pad=14).pack(side="left", padx=(8, 0))
            tk.Label(detalle, text="Envía ese archivo a elleholetzgusso@gmail.com para "
                                   "que lo revise.", bg=GRIS_FONDO, fg=GRIS_SUAVE,
                     font=(F, 9)).pack(anchor="w", padx=16, pady=(0, 14))

    def _copiar(self, texto):
        self.clipboard_clear()
        self.clipboard_append(texto)


def _abrir_en_explorador(carpeta: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(carpeta))  # noqa: S606
        elif sys.platform == "darwin":
            os.system(f'open "{carpeta}"')
        else:
            os.system(f'xdg-open "{carpeta}"')
    except OSError:
        pass


def _cargar_logo(ruta: Path, alto: int):
    """Carga un PNG y lo reduce a ``alto`` px con subsample (sin dependencias)."""
    if not ruta.exists():
        return None
    try:
        imagen = tk.PhotoImage(file=str(ruta))
    except tk.TclError:
        return None
    factor = max(1, round(imagen.height() / alto))
    return imagen.subsample(factor, factor) if factor > 1 else imagen


def main() -> int:
    inicial = limpiar_ruta(sys.argv[1]) if len(sys.argv) > 1 else None
    app = App(inicial)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
