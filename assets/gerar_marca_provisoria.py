"""Gera um logótipo e um ícone PROVISÓRIOS para a janela e para o .exe.

Isto não é a marca da Exceltic — é um substituto tipográfico para o programa não
ficar anónimo enquanto os ficheiros verdadeiros não chegam. Um .exe sem ícone é,
aliás, dos sinais que mais depressa fazem um antivírus desconfiar.

Assim que houver o logótipo a sério, apagar este ficheiro e pôr em assets/ o
`logo.png` (sobre fundo branco, ~44 px de altura) e o `logo.ico`.

    pip install Pillow
    python assets/gerar_marca_provisoria.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent

LARANJA = (241, 87, 34)
TINTA = (26, 26, 26)
BRANCO = (255, 255, 255)

ALTURA_PNG = 44          # a barra de topo da janela; o tkinter não redimensiona
ESCALA = 4               # desenha-se grande e reduz-se, para as curvas ficarem limpas

# Liberation Sans tem as mesmas medidas do Arial, que é a fonte da janela.
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


def _texto_largura(desenho: ImageDraw.ImageDraw, texto: str, fonte, espaco: int) -> int:
    largura = sum(desenho.textlength(c, font=fonte) for c in texto)
    return int(largura + espaco * (len(texto) - 1))


def _escrever_espacado(desenho, xy, texto: str, fonte, cor, espaco: int) -> None:
    """O PIL não faz espaçamento entre letras; desenha-se letra a letra."""
    x, y = xy
    for c in texto:
        desenho.text((x, y), c, font=fonte, fill=cor)
        x += desenho.textlength(c, font=fonte) + espaco


def _marca(lado: int, raio_rel: float = 0.22) -> Image.Image:
    """Quadrado laranja de cantos redondos com um E branco. Legível a 16 px."""
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, lado - 1, lado - 1], radius=int(lado * raio_rel), fill=LARANJA)

    fonte = _fonte(int(lado * 0.62))
    caixa = d.textbbox((0, 0), "E", font=fonte)
    d.text(
        ((lado - (caixa[2] - caixa[0])) / 2 - caixa[0],
         (lado - (caixa[3] - caixa[1])) / 2 - caixa[1]),
        "E", font=fonte, fill=BRANCO,
    )
    return img


def gerar_png() -> Path:
    """Marca + palavra EXCELTIC, sobre branco — a barra de topo é branca."""
    alt = ALTURA_PNG * ESCALA
    lado = int(alt * 0.80)
    folga = int(alt * 0.28)
    espaco = max(1, int(alt * 0.03))

    fonte = _fonte(int(alt * 0.46))
    medida = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    largura_texto = _texto_largura(medida, "EXCELTIC", fonte, espaco)
    largura = lado + folga + largura_texto

    img = Image.new("RGB", (largura, alt), BRANCO)
    img.paste(_marca(lado), (0, (alt - lado) // 2), _marca(lado))

    d = ImageDraw.Draw(img)
    caixa = d.textbbox((0, 0), "EXCELTIC", font=fonte)
    _escrever_espacado(
        d, (lado + folga, (alt - (caixa[3] - caixa[1])) / 2 - caixa[1]),
        "EXCELTIC", fonte, TINTA, espaco,
    )

    img = img.resize((largura // ESCALA, ALTURA_PNG), Image.LANCZOS)
    destino = AQUI / "logo.png"
    img.save(destino, "PNG")
    return destino


def gerar_ico() -> Path:
    """Só a marca: a 16 px uma palavra inteira não se lê."""
    destino = AQUI / "logo.ico"
    tamanhos = [16, 32, 48, 64, 128, 256]
    grande = _marca(256 * 2)
    imagens = [grande.resize((t, t), Image.LANCZOS) for t in tamanhos]
    imagens[-1].save(destino, format="ICO", sizes=[(t, t) for t in tamanhos])
    return destino


if __name__ == "__main__":
    for caminho in (gerar_png(), gerar_ico()):
        print(f"Escrito: {caminho}")
    print("\nProvisórios. Substituir pelos ficheiros de marca verdadeiros.")
