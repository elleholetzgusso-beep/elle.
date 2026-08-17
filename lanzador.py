"""Punto de entrada para el equipo de Exceltic — Organizador de carpetas.

No requiere conocer la linea de comandos: muestra un menu en espanol,
pide los datos que faltan y siempre deja una pausa al final para poder
leer el resultado antes de que se cierre la ventana.

El motor real (creacion de carpetas, organizacion de archivos, historial
y deshacer) esta en el paquete ``organizador``; este script solo se ocupa
de la interaccion con la persona que lo usa y de traducir cualquier fallo
a un mensaje comprensible.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from organizador.arrumador import ErroDeOrganizacao, organizar
from organizador.criador import ErroDeCriacao
from organizador.desfazer import desfazer_operacao
from organizador.historico import Historico, resumir
from organizador.modelos import ErroDeModelo
from organizador.projetos import ErroDeProjeto, criar_envio, criar_projeto

TITULO = "ORGANIZADOR DE CARPETAS Y PROYECTOS — EXCELTIC"

AVISO_VERIFICACION = (
    "IMPORTANTE: revisa el resultado antes de darlo por bueno.\n"
    "Esta herramienta no sustituye la comprobación humana."
)

# Errores esperables (datos mal introducidos, carpetas inexistentes, permisos...).
# Se muestran tal cual, sin el detalle tecnico interno (traceback).
ERRORES_CONOCIDOS = (
    ErroDeCriacao,
    ErroDeOrganizacao,
    ErroDeProjeto,
    ErroDeModelo,
    ValueError,
    FileNotFoundError,
    PermissionError,
    OSError,
)

# Orden y texto mostrados en el menu de "organizar"; las claves deben
# coincidir con organizador.arrumador.CRITERIOS.
CRITERIOS_MENU = [
    ("tipo", "Tipo de archivo (Documentos, Imágenes, Hojas de cálculo...)"),
    ("documento", "Código de documento (EXC2026-16883-001-PES-01...)"),
    ("envio", "Crear envíos por fecha (una carpeta Envío N AAAAMMDD por fecha)"),
    ("extensao", "Extensión (PDF, XLSX...)"),
    ("data", "Fecha de modificación"),
    ("alfabetico", "Letra inicial del nombre"),
]

HIST = Historico()


# --------------------------------------------------------------------- utilidades
def limpiar_ruta(texto: str) -> str:
    """Quita comillas y espacios sobrantes de una ruta pegada o arrastrada."""
    return texto.strip().strip('"').strip("'").strip()


def pedir_texto(mensaje: str, *, opcional: bool = False) -> str | None:
    valor = input(mensaje).strip()
    if not valor and opcional:
        return None
    return valor


def pedir_carpeta(mensaje: str, arrastrada: str | None) -> Path:
    if arrastrada:
        ruta = Path(limpiar_ruta(arrastrada)).expanduser()
        print(f"Carpeta recibida por arrastre: {ruta}")
        return ruta
    print(mensaje)
    bruta = input("Ruta de la carpeta: ")
    return Path(limpiar_ruta(bruta)).expanduser()


def validar_carpeta(ruta: Path, *, exigir_archivos: bool = False) -> None:
    if not ruta.exists():
        raise ErroDeOrganizacao(
            f"La carpeta '{ruta}' no existe. Comprueba la ruta "
            "(o que la unidad de red esté conectada) e inténtalo de nuevo."
        )
    if not ruta.is_dir():
        raise ErroDeOrganizacao(f"'{ruta}' no es una carpeta.")
    if not os.access(ruta, os.W_OK):
        raise ErroDeOrganizacao(
            f"No hay permiso de escritura en '{ruta}'. "
            "Comprueba el acceso a la carpeta o a la unidad de red."
        )
    if exigir_archivos and not any(p.is_file() for p in ruta.iterdir()):
        raise ErroDeOrganizacao(f"La carpeta '{ruta}' no contiene ningún archivo para organizar.")


def escribir_log_error(carpeta_destino: Path, contexto: str) -> Path:
    """Guarda el traceback en un .txt junto al resultado; nunca lanza excepción."""
    momento = datetime.now().strftime("%Y%m%d-%H%M%S")
    nombre = f"ERROR_organizador_{momento}.txt"
    contenido = (
        f"Fecha: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Operación: {contexto}\n\n"
        + traceback.format_exc()
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


# ------------------------------------------------------------------------ menus
def operacion_organizar(arrastrada: str | None, estado: dict) -> None:
    print("\n--- ORGANIZAR DOCUMENTOS ---")
    print("Mueve los archivos de la carpeta indicada a subcarpetas. No se sobrescribe nada:")
    print("si ya existe un archivo con el mismo nombre, el nuevo se guarda como 'nombre (1)'.\n")

    carpeta = pedir_carpeta(
        "Indica la carpeta a organizar (o arrastra la carpeta sobre el programa la próxima vez).",
        arrastrada,
    )
    validar_carpeta(carpeta, exigir_archivos=True)
    estado["carpeta"] = carpeta

    print("\n¿Por qué criterio quieres organizar?")
    for i, (_clave, etiqueta) in enumerate(CRITERIOS_MENU, start=1):
        print(f"  {i}) {etiqueta}")
    eleccion = pedir_texto(f"Opción [1-{len(CRITERIOS_MENU)}] (por defecto 1): ", opcional=True)
    indice = int(eleccion) - 1 if eleccion and eleccion.isdigit() else 0
    if not (0 <= indice < len(CRITERIOS_MENU)):
        indice = 0
    criterio = CRITERIOS_MENU[indice][0]

    respuesta = pedir_texto("¿Incluir también los archivos de las subcarpetas? (s/N): ", opcional=True)
    recursivo = (respuesta or "").strip().lower().startswith("s")

    resultado = organizar(carpeta, criterio, recursivo=recursivo)

    print()
    for movimiento in resultado.movimentos:
        print(f"  {movimiento.origem.name}  ->  {movimiento.destino.relative_to(carpeta)}")

    if resultado.ignorados:
        print("\nArchivos no movidos:")
        for archivo, motivo in resultado.ignorados:
            print(f"  . {archivo.name} ({motivo})")

    print(
        f"\n{len(resultado.movimentos)} archivo(s) movido(s), "
        f"{len(resultado.ignorados)} ignorado(s) de {len(resultado.movimentos) + len(resultado.ignorados)} "
        f"encontrado(s). Resultado en: {carpeta}"
    )

    if any(motivo.startswith("fallo al mover") for _archivo, motivo in resultado.ignorados):
        print(
            "\nATENCIÓN: algún archivo no se pudo mover; la carpeta puede haber quedado a medio "
            "organizar. Revisa la lista de arriba antes de seguir trabajando en ella."
        )

    if resultado.movimentos:
        identificador = HIST.registrar(
            "organizar",
            carpeta,
            movimentos=[
                {"de": str(m.origem), "para": str(m.destino)} for m in resultado.movimentos
            ],
            pastas_criadas=[str(p) for p in resultado.pastas_criadas],
            detalhes={"criterio": criterio},
        )
        print(f"Registrado en el historial como {identificador} (opción 4 del menú para deshacer).")


def operacion_nuevo_proyecto(arrastrada: str | None, estado: dict) -> None:
    print("\n--- CREAR PROYECTO NUEVO ---")
    nombre = pedir_texto("Nombre del proyecto (ej.: Estación de Torre Pacheco (Apeadero)): ")
    codigo = pedir_texto("Código del proyecto (ej.: 16883): ")
    ano = pedir_texto("Año del proyecto (ej.: 2026): ")
    destino = pedir_carpeta(
        "Indica la carpeta donde se creará el proyecto (ej.: la carpeta '1.- En curso').",
        arrastrada,
    )
    validar_carpeta(destino)
    estado["carpeta"] = destino

    resultado = criar_projeto(destino, ano, codigo, nombre)
    pasta = resultado.pasta
    estado["carpeta"] = pasta

    print(f"\nProyecto: {pasta.name}")
    for carpeta_creada in resultado.criacao.criadas:
        etiqueta = carpeta_creada.relative_to(pasta.parent)
        print(f"  + {pasta.name if str(etiqueta) == '.' else etiqueta}")
    print(f"\n{len(resultado.criacao.criadas)} carpeta(s) creada(s) en {pasta.parent}")

    if resultado.criacao.criadas:
        identificador = HIST.registrar(
            "criar",
            pasta,
            pastas_criadas=[str(p) for p in resultado.criacao.criadas],
            detalhes={"proyecto": pasta.name},
        )
        print(f"Registrado en el historial como {identificador} (opción 4 del menú para deshacer).")


def operacion_registrar_envio(arrastrada: str | None, estado: dict) -> None:
    print("\n--- REGISTRAR ENVÍO DE CLIENTE ---")
    proyecto = pedir_carpeta(
        "Indica la carpeta del proyecto (o directamente la carpeta '2_Doc Recebida').",
        arrastrada,
    )
    validar_carpeta(proyecto)
    estado["carpeta"] = proyecto

    fecha = pedir_texto(
        "Fecha del envío (AAAAMMDD, AAAA-MM-DD o DD/MM/AAAA; vacío = hoy): ", opcional=True
    )
    observacion = pedir_texto("Observación (opcional, ej.: 'sin revisar'): ", opcional=True)

    pasta = criar_envio(proyecto, data_envio=fecha, observacao=observacion)
    estado["carpeta"] = pasta.parent

    print(f"\n+ {pasta}")
    print(f"\nCarpeta de envío creada en: {pasta}")

    identificador = HIST.registrar("criar", pasta.parent, pastas_criadas=[str(pasta)])
    print(f"Registrado en el historial como {identificador} (opción 4 del menú para deshacer).")


def operacion_deshacer(estado: dict) -> None:
    print("\n--- DESHACER ÚLTIMA OPERACIÓN ---")
    operacao = HIST.ultima()
    if operacao is None:
        print("No hay ninguna operación registrada para deshacer.")
        return

    if operacao.get("base"):
        estado["carpeta"] = Path(operacao["base"])

    print("Se va a deshacer:")
    print(f"  {resumir(operacao)}")
    confirmacion = pedir_texto("¿Continuar? (s/N): ", opcional=True)
    if not (confirmacion or "").strip().lower().startswith("s"):
        print("Cancelado. No se ha deshecho nada.")
        return

    resultado = desfazer_operacao(operacao)

    for actual, destino in resultado.restaurados:
        print(f"  {actual}  ->  {destino}")
    for carpeta in resultado.pastas_removidas:
        print(f"  - {carpeta}")
    for carpeta in resultado.pastas_recriadas:
        print(f"  + {carpeta}")
    for problema in resultado.problemas:
        print(f"  ! {problema}")

    print(
        f"\n{len(resultado.restaurados)} archivo(s) restaurado(s), "
        f"{len(resultado.pastas_removidas)} carpeta(s) eliminada(s), "
        f"{len(resultado.pastas_recriadas)} carpeta(s) recreada(s)."
    )
    if resultado.problemas:
        print(
            "\nATENCIÓN: hubo algún problema al deshacer (ver líneas con '!' arriba). "
            "Revisa manualmente antes de continuar."
        )

    HIST.remover(operacao["id"])


# -------------------------------------------------------------------------- menu
def mostrar_menu() -> None:
    print("\n" + "=" * len(TITULO))
    print(TITULO)
    print("=" * len(TITULO))
    print(
        "\n"
        "  1) Organizar documentos de una carpeta\n"
        "  2) Crear proyecto nuevo (AAAA-CÓDIGO-NOMBRE)\n"
        "  3) Registrar envío de cliente\n"
        "  4) Deshacer la última operación\n"
        "  5) Salir\n"
    )


def ejecutar() -> int:
    print(TITULO)
    print(AVISO_VERIFICACION)

    arrastrada = limpiar_ruta(sys.argv[1]) if len(sys.argv) > 1 else None
    if arrastrada:
        print(f"\nCarpeta recibida por arrastre: {arrastrada}")

    while True:
        mostrar_menu()
        opcion = pedir_texto("Elige una opción [1-5]: ", opcional=True) or ""
        estado: dict = {}

        if opcion == "5" or not opcion:
            print("\nHasta luego.")
            return 0

        if opcion not in ("1", "2", "3", "4"):
            print("\nOpción no reconocida. Elige un número del 1 al 5.")
            continue

        try:
            if opcion == "1":
                operacion_organizar(arrastrada, estado)
            elif opcion == "2":
                operacion_nuevo_proyecto(arrastrada, estado)
            elif opcion == "3":
                operacion_registrar_envio(arrastrada, estado)
            elif opcion == "4":
                operacion_deshacer(estado)
            print(f"\n{AVISO_VERIFICACION}")
        except ERRORES_CONOCIDOS as erro:
            print(f"\nError: {erro}")
        except Exception:
            carpeta_log = estado.get("carpeta") or Path.home()
            log = escribir_log_error(carpeta_log, contexto=f"opción {opcion}")
            print(
                "\nHa ocurrido un problema inesperado y la operación no se ha podido completar.\n"
                f"Se ha guardado el detalle técnico en: {log}\n"
                "Envía ese archivo a Elle Holetzgusso (elleholetzgusso@gmail.com) para que lo revise."
            )

        arrastrada = None  # el arrastre solo se usa como atajo la primera vez
        otra = pedir_texto("\n¿Realizar otra operación? (S/n): ", opcional=True)
        if (otra or "s").strip().lower().startswith("n"):
            print("\nHasta luego.")
            return 0


def main() -> int:
    try:
        return ejecutar()
    except KeyboardInterrupt:
        print("\n\nInterrumpido por el usuario.")
        return 130


if __name__ == "__main__":
    _codigo = 1
    try:
        _codigo = main()
    finally:
        print()
        input("Pulsa Intro para cerrar esta ventana...")
    raise SystemExit(_codigo)
