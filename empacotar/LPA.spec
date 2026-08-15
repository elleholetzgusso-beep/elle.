# Receita do PyInstaller para o executável da janela gráfica.
#
#   pyinstaller empacotar/LPA.spec --noconfirm --workpath build
#
# Sai um único ficheiro em dist/LPA-Exceltic.exe, sem consola por trás.
import os

from PyInstaller.utils.hooks import collect_submodules

AQUI = os.path.dirname(os.path.abspath(SPEC))
RAIZ = os.path.dirname(AQUI)


def _se_existir(caminho):
    """O logótipo e o ícone são opcionais: sem eles a janela usa o nome em texto."""
    return caminho if os.path.exists(caminho) else None

# Quase todos os módulos do lpa_filler são importados tarde, dentro das funções
# dos comandos, para o arranque ser rápido. O PyInstaller encontra-os na mesma,
# mas isto torna-o explícito e imune a uma reorganização dos imports.
ocultos = collect_submodules("lpa_filler") + [
    "openpyxl",
    "yaml",
    "docx",   # python-docx: ler o PES
    "pypdf",  # ler os .pdf recebidos
]

# Se puseres um logótipo em assets/, vai dentro do .exe e a janela usa-o.
_assets = os.path.join(RAIZ, "assets")
recursos = [(_assets, "assets")] if os.path.isdir(_assets) else []

a = Analysis(
    [os.path.join(AQUI, "arranque.py")],
    pathex=[RAIZ],
    binaries=[],
    datas=recursos,
    hiddenimports=ocultos,
    hookspath=[],
    runtime_hooks=[],
    # Fora o que não se usa: só isto poupa dezenas de MB.
    excludes=["matplotlib", "numpy", "pandas", "scipy", "PIL", "pytest", "PyQt5", "PySide2"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LPA-Exceltic",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX comprime, mas é o que mais dispara antivírus. Não vale a pena.
    runtime_tmpdir=None,
    console=False,  # sem janela preta atrás
    icon=_se_existir(os.path.join(RAIZ, "assets", "logo.ico")),
    # Identifica o ficheiro nas Propriedades do Windows; reduz a desconfiança
    # do antivírus e do SmartScreen perante um .exe anónimo.
    version=_se_existir(os.path.join(AQUI, "version.txt")),
)
