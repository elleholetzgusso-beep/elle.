"""
patrones.py
============

Biblioteca de patrones de expresiones regulares (regex) reutilizables para
el trabajo de revisión y elaboración de documentación técnica ferroviaria
(AsBo/ISA, Exceltic).

Incluye:
    1. Extracción de la versión a partir de un nombre de archivo.
    2. Detección de placeholders (campos sin rellenar) en un texto.
    3. Linter de "lusismos" (errores típicos de un hablante de portugués
       al escribir español técnico).
    4. Análisis (parseo) del nombre de un archivo para separar sus partes.

Solo se usa la librería estándar (`re`). No hay dependencias externas.

Convención de este módulo: todos los patrones se compilan una única vez,
al principio del archivo, con el nombre en MAYÚSCULAS. Las funciones que
los usan están más abajo.
"""

from __future__ import annotations

import os
import re
from typing import List, NamedTuple, Optional, Tuple, Union


# ---------------------------------------------------------------------------
# 1. EXTRACCIÓN DE VERSIÓN A PARTIR DE UN NOMBRE DE ARCHIVO
# ---------------------------------------------------------------------------
#
# Antes de leer el patrón, dos conceptos de regex que se usan mucho aquí:
#
# - `(?:...)` es un "grupo no capturante": agrupa varias piezas para poder
#   aplicarles cosas como `|` (alternancia) o `?` (opcional), pero sin que
#   Python lo guarde como un grupo al que luego podamos acceder por índice.
# - `(?P<nombre>...)` es un "grupo con nombre": SÍ se guarda, y se puede
#   leer después con `match.group("nombre")`. Lo usamos para saber, tras el
#   match, qué variante (v/rev/ed, número/letra) fue la que encajó.
#
# Un detalle importante que descubrimos con los nombres reales: `\b` (límite
# de palabra) NO sirve para separar "v03" de un "_" delante, porque para
# Python el guion bajo `_` cuenta como "carácter de palabra" igual que una
# letra o un dígito. Es decir, en "_v03" no hay ningún "límite de palabra"
# entre "_" y "v", así que `\bv03` NO matchearía ahí. Por eso usamos en su
# lugar `(?<![A-Za-z0-9])`, un "lookbehind negativo": una comprobación (que
# no consume caracteres) de que justo antes de la posición actual NO hay
# una letra ni un dígito. El guion bajo, el guion, el punto, el espacio o
# el propio inicio del texto sí lo dejan pasar.
PATRON_VERSION = re.compile(
    r"""
    (?<![A-Za-z0-9])                        # no debe venir precedido de letra/dígito (pero SÍ puede venir precedido de "_", "-", ".", espacio o el inicio del texto)
    (?:
        v [\s.]? (?P<num_v>\d+(?:\.\d+)?)   # "v" + separador opcional (espacio o punto) + número entero o decimal
      | rev \.? \s? (?P<num_rev>\d+)        # "rev" + punto opcional + espacio opcional + número entero
      | rev \.? \s? (?P<letra_rev>[A-Z]) \b # "rev" + separadores opcionales + UNA letra (revisión con letra en vez de número)
      | ed [\s_.]? (?P<num_ed>\d+)          # "ed" + separador opcional (espacio, "_" o punto) + número entero
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Coincide con:
#   "_v03"        -> num_v="03"
#   "-V3"         -> num_v="3"
#   "v0.5"        -> num_v="0.5"   (versión con decimal)
#   "_ED04"       -> num_ed="04"
#   "_Ed_11"      -> num_ed="11"
#   "_Rev.2"      -> num_rev="2"
#   "_rev 2"      -> num_rev="2"
#   "Rev06"       -> num_rev="06"
#   "Rev. D"      -> letra_rev="D"
# NO coincide con:
#   "Revision"       (no hay ni punto/espacio/nada + dígito o letra sueltos después de "rev" que cumplan el patrón)
#   "avanzado04"     (la "v" está pegada a otra letra antes: "a" es letra, así que el lookbehind lo bloquea)
#   "EV. INFRA-119"  (no hay "v"/"rev"/"ed" como prefijo válido de versión; "119" no lleva delante ninguno de los tres)


class InfoVersion(NamedTuple):
    """Resultado de `extraer_version`: qué se encontró y cómo interpretarlo."""

    texto: str  # texto tal cual aparece en el nombre, p. ej. "Rev06", "v0.5", "Rev. D"
    valor: Optional[Union[int, float]]  # número (int o float); None si la revisión es una letra
    letra: Optional[str]  # letra de revisión (p. ej. "D"); None si la versión es numérica


def extraer_version(nombre_archivo: str) -> Optional[InfoVersion]:
    """Extrae la versión/revisión de un nombre de archivo.

    Soporta variantes "v", "V", "rev"/"Rev"/"REV" (numérica o con letra) y
    "ed"/"Ed"/"ED". Si aparecen varias coincidencias en el mismo nombre, se
    devuelve la ÚLTIMA (se asume que es la más reciente/definitiva).

    No todo marcador de revisión de terceros sigue este esquema: formatos
    propios de un contratista como "01RL" o "01P02" no se reconocen aquí
    a propósito, para no arriesgarnos a interpretar mal algo que no es una
    versión. Ver `analizar_nombre_archivo` para el tratamiento de esos casos.

    :param nombre_archivo: nombre de archivo (con o sin extensión).
    :return: un `InfoVersion`, o `None` si no se encuentra ningún marcador.
    """
    coincidencias = list(PATRON_VERSION.finditer(nombre_archivo))
    if not coincidencias:
        return None

    m = coincidencias[-1]  # nos quedamos con la última ocurrencia
    texto = m.group(0)

    if m.group("num_v") is not None:
        crudo = m.group("num_v")
        valor: Union[int, float] = float(crudo) if "." in crudo else int(crudo)
        return InfoVersion(texto=texto, valor=valor, letra=None)
    if m.group("num_rev") is not None:
        return InfoVersion(texto=texto, valor=int(m.group("num_rev")), letra=None)
    if m.group("letra_rev") is not None:
        return InfoVersion(texto=texto, valor=None, letra=m.group("letra_rev").upper())
    return InfoVersion(texto=texto, valor=int(m.group("num_ed")), letra=None)


# ---------------------------------------------------------------------------
# 2. DETECCIÓN DE PLACEHOLDERS (CAMPOS SIN RELLENAR)
# ---------------------------------------------------------------------------
#
# `\b` sí funciona bien aquí porque estos placeholders van rodeados de
# espacios, puntuación o el borde del texto -no de guiones bajos-, así que
# no tenemos el problema explicado arriba.

PATRON_XXX = re.compile(r"\bX{3,}\b")
# "X" repetida 3 o más veces, como palabra completa.
# Coincide con: "XXX", "XXXXXX", "Estación XXX"
# NO coincide con: "TAXI" (solo 1 "X"), "MAXXXIMO" (las "X" no son una palabra suelta, van pegadas a otras letras)

PATRON_CORCHETES_VACIOS = re.compile(r"\[\s*\]")
# Corchete de apertura, cero o más espacios (\s*), corchete de cierre.
# Coincide con: "[ ]", "[]", "[   ]"
# NO coincide con: "[completo]", "[TBD]" (este último lo captura otro patrón, ver más abajo)

PATRON_CORCHETE_POR_CONFIRMAR = re.compile(r"\[\s*por\s+confirmar\s*\]", re.IGNORECASE)
# Literal "por confirmar" dentro de corchetes, tolerando espacios extra y mayúsculas/minúsculas.
# Coincide con: "[por confirmar]", "[POR CONFIRMAR]", "[ Por Confirmar ]"
# NO coincide con: "[confirmado]", "(por confirmar)" (paréntesis, no corchetes)

PATRON_GUIONES_BAJOS = re.compile(r"_{3,}")
# "_" repetido 3 o más veces (típico hueco para rellenar a mano en una plantilla).
# Coincide con: "___", "Firma: ______"
# NO coincide con: "campo_nombre" (un solo "_"), "a__b" (solo 2)

PATRON_TBD = re.compile(r"\bTBD\b", re.IGNORECASE)
# Coincide con: "TBD", "tbd", "Tbd"
# NO coincide con: "TBDX" (no hay límite de palabra tras "TBD", va pegado a otra letra)

PATRON_PENDIENTE = re.compile(r"\bPENDIENTE\b", re.IGNORECASE)
# Coincide con: "PENDIENTE", "pendiente"
# NO coincide con: "pendientes" (plural: no hay límite de palabra justo tras "pendiente")

PATRON_POR_DEFINIR = re.compile(r"\bPOR\s+DEFINIR\b", re.IGNORECASE)
# "por" + uno o más espacios (\s+, admite varios) + "definir".
# Coincide con: "POR DEFINIR", "por  definir" (con doble espacio)
# NO coincide con: "por determinar" (otra palabra distinta)

PATRON_FECHA_DDMMAAAA = re.compile(r"\bDD\s*/\s*MM\s*/\s*AAAA\b", re.IGNORECASE)
# Plantilla de fecha sin rellenar: "DD" + "/" + "MM" + "/" + "AAAA", con espacios opcionales alrededor de cada "/".
# Coincide con: "DD/MM/AAAA", "dd / mm / aaaa"
# NO coincide con: "15/03/2026" (fecha ya rellenada, con dígitos reales)

PATRON_AAAA = re.compile(r"\bAAAA\b", re.IGNORECASE)
# El propio "AAAA" (placeholder de año) también puede aparecer suelto, no solo dentro de una fecha completa.
# Coincide con: "Revisión AAAA", "aaaa"
# NO coincide con: "2026" (año real), "AAAAA" (5 letras, no forma la palabra exacta "AAAA" con límites de palabra)

PATRON_ND = re.compile(r"\bN\s*/\s*D\b", re.IGNORECASE)
# Coincide con: "N/D", "n/d", "N / D"
# NO coincide con: "ND" (sin barra)

PATRON_NA = re.compile(r"\bN\s*/\s*A\b", re.IGNORECASE)
# Coincide con: "N/A", "n/a"
# NO coincide con: "NA" (sin barra), "N/AA"

PATRON_NO_DISPONIBLE = re.compile(r"\bNO\s+DISPONIBLE\b", re.IGNORECASE)
# Coincide con: "NO DISPONIBLE", "no disponible"
# NO coincide con: "no disponibles" (plural)

# Lista de (tipo, patrón) usada por `detectar_placeholders`. Está pensada
# para poder añadir nuevas entradas sin tocar la lógica de la función.
PATRONES_PLACEHOLDER: List[Tuple[str, "re.Pattern[str]"]] = [
    ("XXX", PATRON_XXX),
    ("CORCHETES_VACIOS", PATRON_CORCHETES_VACIOS),
    ("CORCHETE_POR_CONFIRMAR", PATRON_CORCHETE_POR_CONFIRMAR),
    ("GUIONES_BAJOS", PATRON_GUIONES_BAJOS),
    ("TBD", PATRON_TBD),
    ("PENDIENTE", PATRON_PENDIENTE),
    ("POR_DEFINIR", PATRON_POR_DEFINIR),
    ("FECHA_DD_MM_AAAA", PATRON_FECHA_DDMMAAAA),
    ("AAAA", PATRON_AAAA),
    ("ND", PATRON_ND),
    ("NA", PATRON_NA),
    ("NO_DISPONIBLE", PATRON_NO_DISPONIBLE),
]


class Placeholder(NamedTuple):
    """Una ocurrencia de placeholder encontrada en un texto."""

    tipo: str
    texto: str
    inicio: int
    fin: int


def detectar_placeholders(texto: str) -> List[Placeholder]:
    """Busca placeholders (campos sin rellenar) en `texto`.

    Un ejemplo típico es que "DD/MM/AAAA" también contiene "AAAA" suelto:
    para no duplicar el aviso, si una coincidencia queda totalmente dentro
    de otra coincidencia más larga, se descarta la más corta.

    :param texto: texto donde buscar.
    :return: lista de `Placeholder`, ordenada por posición de aparición.
    """
    encontrados: List[Placeholder] = []
    for tipo, patron in PATRONES_PLACEHOLDER:
        for m in patron.finditer(texto):
            encontrados.append(Placeholder(tipo, m.group(0), m.start(), m.end()))
    encontrados.sort(key=lambda p: p.inicio)

    resultado: List[Placeholder] = []
    for p in encontrados:
        contenido_en_otro = any(
            otro is not p and otro.inicio <= p.inicio and p.fin <= otro.fin
            for otro in encontrados
        )
        if not contenido_en_otro:
            resultado.append(p)
    return resultado


# ---------------------------------------------------------------------------
# 3. LINTER DE LUSISMOS
# ---------------------------------------------------------------------------
#
# Cada regla es simplemente `\bpalabra\b` (la palabra portuguesa, con
# límites de palabra para no matchear dentro de otra palabra más larga),
# más una sugerencia en español. NO se hace ninguna sustitución automática:
# la idea es avisar y dejar que decidas tú, porque hay palabras muy
# parecidas entre portugués y español donde el contexto importa.
#
# Estructura pensada para crecer: `REGLAS_LUSISMOS` es una simple lista de
# tuplas (id, patrón, sugerencia). Añadir una regla nueva es añadir una
# línea más, sin tocar `lint_lusismos`.

PATRON_LUSISMO_INFORMACAO = re.compile(r"\binformação\b", re.IGNORECASE)
PATRON_LUSISMO_DOCUMENTACAO = re.compile(r"\bdocumentação\b", re.IGNORECASE)
PATRON_LUSISMO_EXECUCAO = re.compile(r"\bexecução\b", re.IGNORECASE)
PATRON_LUSISMO_AVALIACAO = re.compile(r"\bavaliação\b", re.IGNORECASE)
PATRON_LUSISMO_VERIFICACAO = re.compile(r"\bverificação\b", re.IGNORECASE)
PATRON_LUSISMO_EVIDENCIA = re.compile(r"\bevidência\b", re.IGNORECASE)
PATRON_LUSISMO_PENDENTE = re.compile(r"\bpendente\b", re.IGNORECASE)
PATRON_LUSISMO_ATUALIZACAO = re.compile(r"\batualização\b", re.IGNORECASE)
PATRON_LUSISMO_ATRAVES = re.compile(r"\batravés\b", re.IGNORECASE)
PATRON_LUSISMO_PORTANTO = re.compile(r"\bportanto\b", re.IGNORECASE)
PATRON_LUSISMO_A_MEDIDA_QUE = re.compile(r"\bà\s+medida\s+que\b", re.IGNORECASE)
PATRON_LUSISMO_EMBORA = re.compile(r"\bembora\b", re.IGNORECASE)
# Ejemplo de cada patrón (todos siguen el mismo esquema \bpalabra\b, así que
# no se repite la explicación pieza a pieza en cada uno):
#   PATRON_LUSISMO_INFORMACAO coincide con "informação" / "Informação" y NO con "información" (ya está en español) ni "informal"

REGLAS_LUSISMOS: List[Tuple[str, "re.Pattern[str]", str]] = [
    ("informacao", PATRON_LUSISMO_INFORMACAO, 'En español es "información" (con tilde en la "o", no "ão").'),
    ("documentacao", PATRON_LUSISMO_DOCUMENTACAO, 'En español es "documentación".'),
    ("execucao", PATRON_LUSISMO_EXECUCAO, 'En español es "ejecución" (con "j", no "x").'),
    ("avaliacao", PATRON_LUSISMO_AVALIACAO, 'En español es "evaluación" (con "e-va-lu", no "a-va-li").'),
    ("verificacao", PATRON_LUSISMO_VERIFICACAO, 'En español es "verificación".'),
    ("evidencia_pt", PATRON_LUSISMO_EVIDENCIA, 'En español es "evidencia" (sin acento en la "e").'),
    ("pendente", PATRON_LUSISMO_PENDENTE, 'En español es "pendiente".'),
    ("atualizacao", PATRON_LUSISMO_ATUALIZACAO, 'En español es "actualización" (con "c": "actualizaci-ón").'),
    ("atraves", PATRON_LUSISMO_ATRAVES, 'En español se escribe en dos palabras: "a través".'),
    ("portanto", PATRON_LUSISMO_PORTANTO, 'En español es "por tanto" o "por lo tanto" (dos palabras, no "portanto").'),
    ("a_medida_que", PATRON_LUSISMO_A_MEDIDA_QUE, 'En español es "a medida que" (sin tilde en la "a").'),
    ("embora", PATRON_LUSISMO_EMBORA, 'En español es "aunque".'),
]


class Lusismo(NamedTuple):
    """Una posible interferencia del portugués detectada en un texto."""

    regla: str
    texto: str
    inicio: int
    fin: int
    contexto: str
    sugerencia: str


def lint_lusismos(texto: str, radio_contexto: int = 20) -> List[Lusismo]:
    """Busca posibles lusismos en `texto` y propone una corrección.

    No modifica el texto: solo informa. Es responsabilidad de quien revisa
    decidir si aplicar o no la sugerencia, porque el contexto puede importar.

    :param texto: texto a revisar.
    :param radio_contexto: nº de caracteres de contexto a mostrar a cada lado.
    :return: lista de `Lusismo`, ordenada por posición de aparición.
    """
    resultados: List[Lusismo] = []
    for id_regla, patron, sugerencia in REGLAS_LUSISMOS:
        for m in patron.finditer(texto):
            inicio_ctx = max(0, m.start() - radio_contexto)
            fin_ctx = min(len(texto), m.end() + radio_contexto)
            contexto = texto[inicio_ctx:fin_ctx]
            resultados.append(Lusismo(id_regla, m.group(0), m.start(), m.end(), contexto, sugerencia))
    resultados.sort(key=lambda l: l.inicio)
    return resultados


# ---------------------------------------------------------------------------
# 4. PARSER DE NOMBRE DE ARCHIVO
# ---------------------------------------------------------------------------
#
# La documentación real que manejas mezcla dos mundos:
#   (a) Los archivos propios de Exceltic, que siguen un patrón fijo:
#       EXC<año>-<código>-<nº proyecto>-<tipo>-<nº documento>
#       p. ej. "EXC2026-XXXXXX-001-PES-01"
#   (b) Archivos recibidos de terceros (ADIF/INECO/contratistas), con
#       nomenclaturas muy variadas: "SAG1-AP2-F3 DS-REP", "Secciones_Galibos_Rev06"...
#
# En vez de forzar un único patrón "universal" (que fallaría todo el rato
# con los archivos de terceros, o sería tan permisivo que aceptaría
# cualquier cosa), el parser hace dos intentos:
#   1. Intenta el patrón EXCELTIC estricto -> si encaja, confianza "alta".
#   2. Si no encaja, hace una extracción parcial (versión + tipo de
#      documento conocido, si aparece) -> confianza "baja", con avisos
#      explicando qué no se ha podido determinar y por qué.
# Esto es a propósito: es mejor decir "no lo sé, revísalo tú" que
# adivinar mal el código de proyecto de un archivo de un contratista.

EXTENSIONES_CONOCIDAS = {
    ".docx", ".doc", ".xlsx", ".xlsm", ".xls",
    ".pdf", ".pptx", ".ppt", ".dwg", ".dxf",
}

PATRON_EXTENSION = re.compile(
    r"\.(?P<ext>docx|doc|xlsx|xlsm|xls|pdf|pptx|ppt|dwg|dxf)$",
    re.IGNORECASE,
)
# Punto + una extensión de la lista conocida, anclado al final del texto ($).
# Coincide con: "informe.docx", "plano.DWG"
# NO coincide con: "260603_Acta reunión.v04" (".v04" no es una extensión conocida:
#   aquí ".v04" es en realidad una versión, no hay que confundirla con la extensión de archivo)

TIPOS_DOCUMENTO_CONOCIDOS = {
    "LPA", "PES", "F03", "F3", "F5", "F5-REP", "REP",
    "PPI", "ISA", "EV", "CIE",
}

PATRON_EXCELTIC = re.compile(
    r"""
    ^EXC                                    # prefijo fijo de los proyectos Exceltic
    (?P<anio>\d{4})                         # año, 4 dígitos: "2026"
    -(?P<codigo>[A-Za-z0-9]+)               # código de proyecto (letras y/o dígitos, incluye placeholders tipo "XXXXXX")
    -(?P<numero_proyecto>\d+)               # nº de proyecto: "001"
    -(?P<tipo>[A-Za-z]+\d*(?:(?:\.\d+)|(?:-[A-Za-z0-9]+))?) # tipo de documento: letras + dígitos + opcionalmente (punto + dígitos) o (guion + caracteres alfanuméricos) ("PES", "F03", "F3.2", "F5-REP")
    -(?P<numero_doc>\d+)                    # nº de documento: "01"
    (?P<sufijo>.*)                          # lo que sobre al final (p. ej. "(2)", "_atualizado"), se guarda tal cual
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)
# Coincide con (ya sin la extensión, ver `_separar_extension`):
#   "EXC2026-XXXXXX-001-PES-01"              -> codigo=XXXXXX, numero_proyecto=001, tipo=PES, numero_doc=01, sufijo=""
#   "EXC2026-XXXXXX-001-PES-01(2)"           -> igual, sufijo="(2)"
#   "EXC2026-XXXX-002-LPA-01_atualizado"     -> codigo=XXXX, numero_proyecto=002, tipo=LPA, numero_doc=01, sufijo="_atualizado"
# NO coincide con:
#   "SAG1-AP2-F3 DS-REP"     (no empieza por "EXC")
#   "Secciones_Galibos_Rev06" (no empieza por "EXC")


class ResultadoParseo(NamedTuple):
    """Resultado de `analizar_nombre_archivo`."""

    nombre_original: str
    extension: Optional[str]
    codigo_proyecto: Optional[str]
    numero_proyecto: Optional[str]
    tipo_documento: Optional[str]
    numero_documento: Optional[str]
    tipo_referencia: Optional[str]
    numero_referencia: Optional[str]
    version: Optional[InfoVersion]
    confianza: str  # "alta" | "baja" | "no_reconocido"
    avisos: List[str]


def _separar_extension(nombre_archivo: str) -> Tuple[str, Optional[str]]:
    """Separa la extensión (solo si es una extensión conocida) del resto del nombre."""
    m = PATRON_EXTENSION.search(nombre_archivo)
    if m:
        return nombre_archivo[: m.start()], m.group(0)
    return nombre_archivo, None


def analizar_nombre_archivo(nombre_archivo: str) -> ResultadoParseo:
    """Analiza el nombre de un archivo de documentación técnica.

    Primero prueba el patrón estricto de Exceltic (confianza "alta"). Si no
    encaja, hace una extracción parcial de lo que se pueda identificar con
    seguridad -tipo de documento conocido y versión-, marcando el resultado
    como confianza "baja" y explicando en `avisos` qué falta por revisar
    a mano.

    :param nombre_archivo: nombre del archivo, con o sin extensión.
    :return: un `ResultadoParseo`.
    """
    base, extension = _separar_extension(nombre_archivo)
    version = extraer_version(base)

    m = PATRON_EXCELTIC.match(base)
    if m:
        avisos: List[str] = []
        sufijo = m.group("sufijo").strip()
        if sufijo:
            avisos.append(f'Se ha detectado texto adicional no estándar al final: "{sufijo}".')
        return ResultadoParseo(
            nombre_original=nombre_archivo,
            extension=extension,
            codigo_proyecto=m.group("codigo"),
            numero_proyecto=m.group("numero_proyecto"),
            tipo_documento=m.group("tipo").upper(),
            numero_documento=m.group("numero_doc"),
            tipo_referencia=None,
            numero_referencia=None,
            version=version,
            confianza="alta",
            avisos=avisos,
        )

    # Modo alternativo: el nombre no sigue el patrón Exceltic (típico de
    # documentación recibida de terceros). Se trocea por separadores
    # habituales y se busca, entre los trozos, algún tipo de documento
    # conocido.
    tokens = [t for t in re.split(r"[-_.\s]+", base) if t]
    candidatos_tipo = [t.upper() for t in tokens if t.upper() in TIPOS_DOCUMENTO_CONOCIDOS]

    avisos = [
        "El nombre no sigue el patrón estándar de Exceltic "
        "(EXC<año>-<código>-<nº proyecto>-<tipo>-<nº documento>); "
        "se ha hecho una extracción parcial, revisar manualmente."
    ]
    tipo_documento: Optional[str] = None
    if len(candidatos_tipo) == 1:
        tipo_documento = candidatos_tipo[0]
    elif len(candidatos_tipo) > 1:
        avisos.append(
            "Se han encontrado varios tipos de documento candidatos: "
            f"{', '.join(candidatos_tipo)}. No se puede determinar cuál es el correcto."
        )
    else:
        avisos.append("No se ha reconocido ningún tipo de documento conocido en el nombre.")

    tuvo_alguna_pista = bool(tipo_documento) or bool(version) or bool(candidatos_tipo)
    confianza = "baja" if tuvo_alguna_pista else "no_reconocido"

    return ResultadoParseo(
        nombre_original=nombre_archivo,
        extension=extension,
        codigo_proyecto=None,
        numero_proyecto=None,
        tipo_documento=tipo_documento,
        numero_documento=None,
        tipo_referencia=None,
        numero_referencia=None,
        version=version,
        confianza=confianza,
        avisos=avisos,
    )


# ---------------------------------------------------------------------------
# BATERÍA DE PRUEBAS
# ---------------------------------------------------------------------------

def _informar(descripcion: str, esperado: object, obtenido: object) -> bool:
    """Imprime un caso de prueba (esperado vs. obtenido) y devuelve si ha pasado."""
    ok = esperado == obtenido
    estado = "OK" if ok else "FALLO"
    print(f"[{estado}] {descripcion}")
    print(f"        esperado : {esperado!r}")
    print(f"        obtenido : {obtenido!r}")
    return ok


if __name__ == "__main__":
    total = 0
    aciertos = 0

    print("=" * 70)
    print("1. EXTRACCIÓN DE VERSIÓN")
    print("=" * 70)
    casos_version = [
        ("informe_v03.docx", InfoVersion("v03", 3, None)),
        ("informe_V3.docx", InfoVersion("V3", 3, None)),
        ("informe-v03.docx", InfoVersion("v03", 3, None)),
        ("informe_ED04.docx", InfoVersion("ED04", 4, None)),
        ("informe_Rev.2.docx", InfoVersion("Rev.2", 2, None)),
        ("informe_rev 2.docx", InfoVersion("rev 2", 2, None)),
        ("informe_Ed_11.docx", InfoVersion("Ed_11", 11, None)),
        ("informe_v01_v02.docx", InfoVersion("v02", 2, None)),  # se queda con la ÚLTIMA
        ("informe_sin_version.docx", None),
        ("plano_v0.5.dwg", InfoVersion("v0.5", 0.5, None)),
        ("Secciones_Galibos_Rev06.pdf", InfoVersion("Rev06", 6, None)),
        ("R.T.Pacheco-Rev. D.docx", InfoVersion("Rev. D", None, "D")),
        ("01RL-04RL.pdf", None),  # formato propio de un contratista, fuera de alcance a propósito
    ]
    for nombre, esperado in casos_version:
        total += 1
        obtenido = extraer_version(nombre)
        if _informar(f'extraer_version("{nombre}")', esperado, obtenido):
            aciertos += 1

    print()
    print("=" * 70)
    print("2. DETECCIÓN DE PLACEHOLDERS")
    print("=" * 70)
    texto_prueba = (
        "Estación XXXXXX, fecha DD/MM/AAAA, longitud ____ m. "
        "Responsable: TBD. Estado: PENDIENTE. Anden: [por confirmar]. "
        "Cota: N/D."
    )
    total += 1
    tipos_encontrados = sorted({p.tipo for p in detectar_placeholders(texto_prueba)})
    esperado_tipos = sorted([
        "XXX", "FECHA_DD_MM_AAAA", "GUIONES_BAJOS", "TBD",
        "PENDIENTE", "CORCHETE_POR_CONFIRMAR", "ND",
    ])
    if _informar("tipos de placeholder detectados", esperado_tipos, tipos_encontrados):
        aciertos += 1

    total += 1
    sin_placeholders = detectar_placeholders("Estación de Atocha, andén 3, cota 620.50 m.")
    if _informar("texto sin placeholders", [], sin_placeholders):
        aciertos += 1

    print()
    print("=" * 70)
    print("3. LINTER DE LUSISMOS")
    print("=" * 70)
    texto_lusismos = (
        "A informação do documento está pendente de verificação. "
        "Através deste relatório, portanto, confirmamos a avaliação."
    )
    total += 1
    reglas_encontradas = sorted({l.regla for l in lint_lusismos(texto_lusismos)})
    esperado_reglas = sorted([
        "informacao", "pendente", "verificacao", "atraves", "portanto", "avaliacao",
    ])
    if _informar("lusismos detectados", esperado_reglas, reglas_encontradas):
        aciertos += 1

    total += 1
    sin_lusismos = lint_lusismos("La información del documento está pendiente de verificación.")
    if _informar("texto ya en español, sin lusismos", [], sin_lusismos):
        aciertos += 1

    print()
    print("=" * 70)
    print("4. PARSER DE NOMBRE DE ARCHIVO")
    print("=" * 70)

    total += 1
    r = analizar_nombre_archivo("EXC2026-XXXXXX-001-PES-01.docx")
    obtenido = (r.confianza, r.codigo_proyecto, r.numero_proyecto, r.tipo_documento, r.numero_documento, r.extension)
    esperado = ("alta", "XXXXXX", "001", "PES", "01", ".docx")
    if _informar("nombre Exceltic estándar", esperado, obtenido):
        aciertos += 1

    total += 1
    r = analizar_nombre_archivo("EXC2026-XXXXXX-001-PES-01(2).docx")
    obtenido = (r.confianza, r.tipo_documento, r.avisos != [])
    esperado = ("alta", "PES", True)  # debe avisar del sufijo "(2)"
    if _informar("nombre Exceltic con sufijo de copia", esperado, obtenido):
        aciertos += 1

    total += 1
    r = analizar_nombre_archivo("EXC2026-XXXX-002-LPA-01_atualizado.xlsm")
    obtenido = (r.confianza, r.codigo_proyecto, r.tipo_documento, r.extension)
    esperado = ("alta", "XXXX", "LPA", ".xlsm")
    if _informar("nombre Exceltic con sufijo de texto", esperado, obtenido):
        aciertos += 1

    total += 1
    r = analizar_nombre_archivo("Secciones_Galibos_Rev06.pdf")
    obtenido = (r.confianza, r.tipo_documento, r.version.valor if r.version else None)
    esperado = ("baja", None, 6)
    if _informar("nombre de terceros sin tipo reconocido", esperado, obtenido):
        aciertos += 1

    total += 1
    r = analizar_nombre_archivo("SAG1-AP2-F5 REP-L352 Y ANDEN 3 TP.pdf")
    obtenido = (r.confianza, r.tipo_documento, "varios tipos de documento candidatos" in " ".join(r.avisos))
    esperado = ("baja", None, True)  # F5 y REP son ambos candidatos: ambiguo a propósito
    if _informar("nombre de terceros con tipo ambiguo (F5 y REP)", esperado, obtenido):
        aciertos += 1

    total += 1
    r = analizar_nombre_archivo("[119.4] R.T.Pacheco-v03.docx")
    obtenido = (r.confianza, r.version.valor if r.version else None)
    esperado = ("baja", 3)
    if _informar("nombre de terceros solo con versión reconocible", esperado, obtenido):
        aciertos += 1

    print()
    print("=" * 70)
    print(f"RESUMEN: {aciertos}/{total} casos correctos")
    print("=" * 70)
