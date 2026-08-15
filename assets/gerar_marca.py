"""Gera o `logo.png` da janela e o `logo.ico` do executável, a partir do símbolo.

Põe o símbolo da Exceltic em `assets/simbolo.png` (PNG com fundo transparente,
256 px ou mais) e corre:

    pip install Pillow
    python assets/gerar_marca.py

Sem esse ficheiro, desenha um símbolo PROVISÓRIO — um quadrado laranja com um E.
Não é a marca da Exceltic: serve só para o executável não sair com o ícone
genérico do PyInstaller, que é dos sinais que mais depressa fazem um antivírus
desconfiar. O aviso aparece na consola sempre que isso acontece.

Na barra de topo entra só o símbolo: a palavra «EXCELTIC» não vai aqui porque já
lá está «AUTOMATIZAÇÃO DE LPA» em texto, ao lado.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
ORIGEM = AQUI / "simbolo.png"

LARANJA = (241, 87, 34)
BRANCO = (255, 255, 255)

ALTURA_PNG = 44                              # a barra da janela; o tkinter não redimensiona
TAMANHOS_ICO = [16, 32, 48, 64, 128, 256]

FONTES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    for caminho in FONTES:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    raise SystemExit("Não encontrei nenhuma fonte bold. Edita a lista FONTES.")


def _provisorio(lado: int) -> Image.Image:
    """Quadrado laranja de cantos redondos com um E branco. Legível a 16 px."""
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, lado - 1, lado - 1], radius=int(lado * 0.22), fill=LARANJA)

    fonte = _fonte(int(lado * 0.62))
    caixa = d.textbbox((0, 0), "E", font=fonte)
    d.text(
        ((lado - (caixa[2] - caixa[0])) / 2 - caixa[0],
         (lado - (caixa[3] - caixa[1])) / 2 - caixa[1]),
        "E", font=fonte, fill=BRANCO,
    )
    return img


def simbolo() -> tuple[Image.Image, bool]:
    """O símbolo em RGBA, e se é o verdadeiro ou o provisório."""
    if ORIGEM.exists():
        img = Image.open(ORIGEM).convert("RGBA")
        if min(img.size) < 128:
            print(f"! {ORIGEM.name} tem só {img.size[0]}x{img.size[1]} px — "
                  "o ícone a 256 px vai sair esborratado. Convém 256 px ou mais.")
        return img, True
    return _provisorio(256 * 2), False


def gerar_png(marca: Image.Image) -> Path:
    """Símbolo à altura da barra, achatado sobre branco — a barra é branca."""
    escala = ALTURA_PNG / marca.height
    tamanho = (max(1, round(marca.width * escala)), ALTURA_PNG)
    reduzido = marca.resize(tamanho, Image.LANCZOS)

    fundo = Image.new("RGB", tamanho, BRANCO)
    fundo.paste(reduzido, (0, 0), reduzido)

    destino = AQUI / "logo.png"
    fundo.save(destino, "PNG")
    return destino


def gerar_ico(marca: Image.Image) -> Path:
    """Só o símbolo, com transparência. A 16 px uma palavra não se leria."""
    lado = max(marca.size)
    quadrado = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    quadrado.paste(marca, ((lado - marca.width) // 2, (lado - marca.height) // 2), marca)

    destino = AQUI / "logo.ico"
    quadrado.resize((256, 256), Image.LANCZOS).save(
        destino, format="ICO", sizes=[(t, t) for t in TAMANHOS_ICO]
    )
    return destino


def main() -> int:
    marca, verdadeiro = simbolo()
    for caminho in (gerar_png(marca), gerar_ico(marca)):
        print(f"Escrito: {caminho}")

    if verdadeiro:
        print(f"\nA partir de {ORIGEM.name}.")
    else:
        print("\nPROVISÓRIOS — não são a marca da Exceltic.")
        print(f"Põe o símbolo em {ORIGEM} e volta a correr isto.")
    print("Depois: empacotar\\construir.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
