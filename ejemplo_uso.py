"""Ejemplos de uso del módulo word_com.

Herramienta de línea de órdenes para la evaluación independiente de seguridad
(AsBo/ISA) de documentación técnica ferroviaria.

Ejemplos::

    # 0. Comprobar que el entorno funciona (ejecutar esto lo primero)
    python ejemplo_uso.py diagnostico

    # 1. Comparar dos versiones de un documento
    python ejemplo_uso.py comparar ^
        "Y:\\Proyectos\\LAV\\PROY_Senalizacion_v03.docx" ^
        "Y:\\Proyectos\\LAV\\PROY_Senalizacion_v04.docx" ^
        --salida "C:\\Trabajo\\Comparativas"

    # 2. Extraer los comentarios de un documento a Excel
    python ejemplo_uso.py comentarios "Y:\\...\\PROY_Senalizacion_v04.docx" ^
        --salida "C:\\Trabajo\\Comparativas"

    # 3. Extraer los cambios registrados
    python ejemplo_uso.py cambios "Y:\\...\\PROY_Senalizacion_v04.docx"

    # 4. Actualizar campos, índices y referencias cruzadas
    python ejemplo_uso.py campos "Y:\\...\\PROY_Senalizacion_v04.docx"

    # 5. Exportar a PDF (con las marcas de revisión visibles)
    python ejemplo_uso.py pdf "Y:\\...\\PROY_Senalizacion_v04.docx" --con-marcas

    # 6a. Comparar en lote todos los pares de versiones de una carpeta
    python ejemplo_uso.py lote-comparar "Y:\\Proyectos\\LAV" ^
        --salida "C:\\Trabajo\\Comparativas"

    # 6b. Extraer los comentarios de todos los documentos de una carpeta
    python ejemplo_uso.py lote-comentarios "Y:\\Proyectos\\LAV" ^
        --salida "C:\\Trabajo\\Comparativas" --con-cambios

Nota sobre las rutas: se recomienda usar rutas UNC (\\\\servidor\\recurso\\...)
en lugar de la letra de unidad Y:, porque las unidades asignadas sólo existen
en la sesión del usuario que las asignó. El módulo convierte en todo caso las
rutas a absolutas antes de pasárselas a Word.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import word_com
from word_com import (
    ErrorDocumento,
    SesionWord,
    actualizar_campos,
    comparar_documentos,
    comparar_lote,
    configurar_registro,
    diagnostico,
    emparejar_versiones,
    exportar_a_pdf,
    exportar_tabla,
    extraer_comentarios,
    extraer_comentarios_lote,
    extraer_revisiones,
)

#: Carpeta de salida por defecto. Local a propósito: escribir en la unidad de
#: red en cada ejecución es más lento y más propenso a errores de permisos.
CARPETA_SALIDA_POR_DEFECTO = Path.home() / "Documentos" / "Evaluacion_AsBo"


# ---------------------------------------------------------------------------
# 1. Comparación de dos versiones
# ---------------------------------------------------------------------------


def orden_comparar(argumentos: argparse.Namespace) -> int:
    """Compara dos versiones y genera el documento marcado y el Excel."""
    anterior = Path(argumentos.anterior)
    nueva = Path(argumentos.nueva)
    salida = Path(argumentos.salida)
    salida.mkdir(parents=True, exist_ok=True)

    nombre = f"COMPARATIVA_{anterior.stem}_vs_{nueva.stem}"

    with SesionWord() as sesion:
        documento = comparar_documentos(
            sesion,
            ruta_original=anterior,
            ruta_revisado=nueva,
            ruta_salida=salida / f"{nombre}.docx",
            autor_revision=argumentos.autor,
        )
        print(f"\nDocumento comparado: {documento}")

        # El documento comparado lleva cada diferencia como un cambio
        # registrado, de modo que la tabla de hallazgos se obtiene leyendo
        # sus revisiones.
        diferencias = extraer_revisiones(sesion, documento)
        fichero = exportar_tabla(
            diferencias, salida / f"{nombre}_DIFERENCIAS.xlsx", "Diferencias"
        )
        print(f"Relación de diferencias: {fichero}")
        print(f"Total de diferencias detectadas: {len(diferencias)}")
    return 0


# ---------------------------------------------------------------------------
# 2 y 3. Comentarios y cambios registrados
# ---------------------------------------------------------------------------


def orden_comentarios(argumentos: argparse.Namespace) -> int:
    """Extrae los comentarios de un documento a Excel."""
    documento = Path(argumentos.documento)
    salida = Path(argumentos.salida)

    with SesionWord() as sesion:
        comentarios = extraer_comentarios(sesion, documento)

    fichero = exportar_tabla(
        comentarios, salida / f"COMENTARIOS_{documento.stem}.xlsx", "Comentarios"
    )
    print(f"\nComentarios extraídos: {len(comentarios)}")
    print(f"Fichero generado: {fichero}")
    _mostrar_primeros(comentarios)
    return 0


def orden_cambios(argumentos: argparse.Namespace) -> int:
    """Extrae los cambios registrados de un documento a Excel."""
    documento = Path(argumentos.documento)
    salida = Path(argumentos.salida)

    with SesionWord() as sesion:
        revisiones = extraer_revisiones(sesion, documento)

    fichero = exportar_tabla(
        revisiones, salida / f"CAMBIOS_{documento.stem}.xlsx", "Cambios registrados"
    )
    print(f"\nCambios registrados: {len(revisiones)}")
    print(f"Fichero generado: {fichero}")
    _mostrar_primeros(revisiones)
    return 0


def _mostrar_primeros(elementos: list, cuantos: int = 5) -> None:
    """Muestra por consola una vista previa de los primeros elementos."""
    if not elementos:
        print("No se ha localizado ningún elemento.")
        return
    print(f"\nVista previa (primeros {min(cuantos, len(elementos))}):")
    for elemento in elementos[:cuantos]:
        pagina = getattr(elemento, "pagina", 0)
        autor = getattr(elemento, "autor", "")
        texto = getattr(elemento, "texto_comentario", None) or getattr(
            elemento, "texto", ""
        )
        print(f"  [pág. {pagina:>3}] {autor:<20} {texto[:70]}")


# ---------------------------------------------------------------------------
# 4 y 5. Actualización de campos y exportación a PDF
# ---------------------------------------------------------------------------


def orden_campos(argumentos: argparse.Namespace) -> int:
    """Actualiza campos, índices y referencias cruzadas."""
    documento = Path(argumentos.documento)
    salida = Path(argumentos.salida)

    with SesionWord() as sesion:
        generado = actualizar_campos(
            sesion, documento, salida / f"{documento.stem}_ACTUALIZADO.docx"
        )
    print(f"\nDocumento actualizado: {generado}")
    print("El documento original no se ha modificado.")
    return 0


def orden_pdf(argumentos: argparse.Namespace) -> int:
    """Exporta un documento a PDF con la paginación real."""
    documento = Path(argumentos.documento)
    salida = Path(argumentos.salida)
    sufijo = "_CON_MARCAS" if argumentos.con_marcas else ""

    with SesionWord() as sesion:
        generado = exportar_a_pdf(
            sesion,
            documento,
            salida / f"{documento.stem}{sufijo}.pdf",
            con_marcas_de_revision=argumentos.con_marcas,
        )
    print(f"\nPDF generado: {generado}")
    return 0


# ---------------------------------------------------------------------------
# 6. Procesos en lote
# ---------------------------------------------------------------------------


def orden_lote_comparar(argumentos: argparse.Namespace) -> int:
    """Compara en lote todos los pares de versiones de una carpeta."""
    carpeta = Path(argumentos.carpeta)
    pares = emparejar_versiones(carpeta, solo_ultimo_par=not argumentos.todos_los_pares)
    if not pares:
        print("No se ha detectado ningún par de versiones (sufijo _vNN).")
        return 1

    print("\nPares de versiones detectados:")
    for anterior, nueva in pares:
        print(f"  {anterior.name}  ->  {nueva.name}")

    resultado = comparar_lote(
        carpeta_entrada=carpeta,
        carpeta_salida=Path(argumentos.salida),
        solo_ultimo_par=not argumentos.todos_los_pares,
        exportar_hallazgos=True,
        autor_revision=argumentos.autor,
    )
    print("\n" + resultado.resumen())
    return 0 if not resultado.fallidos else 2


def orden_lote_comentarios(argumentos: argparse.Namespace) -> int:
    """Extrae los comentarios de todos los documentos de una carpeta."""
    resultado = extraer_comentarios_lote(
        carpeta_entrada=Path(argumentos.carpeta),
        carpeta_salida=Path(argumentos.salida),
        fichero_unificado=not argumentos.fichero_por_documento,
        incluir_revisiones=argumentos.con_cambios,
    )
    print("\n" + resultado.resumen())
    print("\nFicheros generados:")
    for fichero in resultado.salidas:
        print(f"  {fichero}")
    return 0 if not resultado.fallidos else 2


def orden_diagnostico(_argumentos: argparse.Namespace) -> int:
    """Comprueba que Word y pywin32 están operativos."""
    return 0 if diagnostico() else 1


# ---------------------------------------------------------------------------
# Línea de órdenes
# ---------------------------------------------------------------------------


def construir_analizador() -> argparse.ArgumentParser:
    """Define las órdenes disponibles."""
    analizador = argparse.ArgumentParser(
        prog="ejemplo_uso.py",
        description="Automatización de Word para la evaluación independiente "
                    "de seguridad de proyectos ferroviarios.",
    )
    analizador.add_argument(
        "--salida",
        default=str(CARPETA_SALIDA_POR_DEFECTO),
        help="Carpeta donde se depositan los ficheros generados.",
    )
    ordenes = analizador.add_subparsers(dest="orden", required=True)

    comparar = ordenes.add_parser("comparar", help="Comparar dos versiones.")
    comparar.add_argument("anterior", help="Versión anterior (p. ej. _v03).")
    comparar.add_argument("nueva", help="Versión nueva (p. ej. _v04).")
    comparar.add_argument("--autor", default="Comparación automática",
                          help="Autor que figurará en las marcas de revisión.")
    comparar.set_defaults(funcion=orden_comparar)

    comentarios = ordenes.add_parser("comentarios", help="Extraer comentarios.")
    comentarios.add_argument("documento")
    comentarios.set_defaults(funcion=orden_comentarios)

    cambios = ordenes.add_parser("cambios", help="Extraer cambios registrados.")
    cambios.add_argument("documento")
    cambios.set_defaults(funcion=orden_cambios)

    campos = ordenes.add_parser("campos", help="Actualizar campos e índices.")
    campos.add_argument("documento")
    campos.set_defaults(funcion=orden_campos)

    pdf = ordenes.add_parser("pdf", help="Exportar a PDF.")
    pdf.add_argument("documento")
    pdf.add_argument("--con-marcas", action="store_true", dest="con_marcas",
                     help="Mostrar el control de cambios en el PDF.")
    pdf.set_defaults(funcion=orden_pdf, con_marcas=False)

    lote_comparar = ordenes.add_parser("lote-comparar",
                                       help="Comparar en lote una carpeta.")
    lote_comparar.add_argument("carpeta")
    lote_comparar.add_argument("--todos-los-pares", action="store_true",
                               dest="todos_los_pares",
                               help="Comparar todas las versiones consecutivas, "
                                    "no sólo las dos últimas.")
    lote_comparar.add_argument("--autor", default="Comparación automática")
    lote_comparar.set_defaults(funcion=orden_lote_comparar, todos_los_pares=False)

    lote_comentarios = ordenes.add_parser("lote-comentarios",
                                          help="Extraer comentarios de una carpeta.")
    lote_comentarios.add_argument("carpeta")
    lote_comentarios.add_argument("--con-cambios", action="store_true",
                                  dest="con_cambios",
                                  help="Extraer también los cambios registrados.")
    lote_comentarios.add_argument("--fichero-por-documento", action="store_true",
                                  dest="fichero_por_documento",
                                  help="Un Excel por documento en lugar de uno "
                                       "consolidado.")
    lote_comentarios.set_defaults(funcion=orden_lote_comentarios,
                                  con_cambios=False,
                                  fichero_por_documento=False)

    comprobacion = ordenes.add_parser("diagnostico",
                                      help="Comprobar el entorno (Word + pywin32).")
    comprobacion.set_defaults(funcion=orden_diagnostico)

    return analizador


def main(argumentos_linea: list[str] | None = None) -> int:
    """Punto de entrada."""
    configurar_registro()
    analizador = construir_analizador()
    argumentos = analizador.parse_args(argumentos_linea)

    Path(argumentos.salida).mkdir(parents=True, exist_ok=True)

    try:
        return int(argumentos.funcion(argumentos))
    except ErrorDocumento as exc:
        print(f"\nINCIDENCIA: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        # La sesión de Word se cierra igualmente: el bloque `finally` del
        # gestor de contexto se ejecuta también ante una interrupción.
        print("\nProceso interrumpido por el usuario.", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        word_com.registro.exception("Error no controlado")
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
