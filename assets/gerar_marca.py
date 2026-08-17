"""Gera o `logo.png` da janela e o `logo.ico` do executável, a partir da marca.

Dois ficheiros de origem, cada um para o seu uso — não são o mesmo ficheiro a
dois tamanhos, porque o lockup completo (escudo + "Exceltic" + "DELIVERING
EXCELLENCE") deixa de se ler a 16 px, e um ícone só com o escudo perde a marca
na barra da janela, onde há espaço de sobra.

    assets/logo-lockup.png   escudo + wordmark + tagline → barra da janela
    assets/simbolo.png       só o escudo, recortado      → ícone do .exe

    pip install Pillow
    python assets/gerar_marca.py

Falta algum dos dois? Cai no provisório correspondente — um quadrado laranja
com um E — e diz-se na consola qual ficheiro entrou de verdade e qual não.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

AQUI = Path(__file__).resolve().parent
ORIGEM_LOCKUP = AQUI / "logo-lockup.png"
ORIGEM_SIMBOLO = AQUI / "simbolo.png"

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


def _abrir(origem: Path) -> tuple[Image.Image, bool]:
    """A imagem em RGBA, e se veio do ficheiro real ou do provisório."""
    if origem.exists():
        img = Image.open(origem).convert("RGBA")
        if min(img.size) < 128:
            print(f"! {origem.name} tem só {img.size[0]}x{img.size[1]} px — "
                  "convém 256 px ou mais para não sair esborratado.")
        return img, True
    return _provisorio(256 * 2), False


def gerar_png(lockup: Image.Image) -> Path:
    """O lockup completo à altura da barra, sobre branco — a barra é branca."""
    escala = ALTURA_PNG / lockup.height
    tamanho = (max(1, round(lockup.width * escala)), ALTURA_PNG)
    reduzido = lockup.resize(tamanho, Image.LANCZOS)

    fundo = Image.new("RGB", tamanho, BRANCO)
    fundo.paste(reduzido, (0, 0), reduzido)

    destino = AQUI / "logo.png"
    fundo.save(destino, "PNG")
    return destino


def gerar_ico(simbolo: Image.Image) -> Path:
    """Só o escudo, com transparência. A 16 px o lockup completo não se leria."""
    lado = max(simbolo.size)
    quadrado = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    quadrado.paste(simbolo, ((lado - simbolo.width) // 2, (lado - simbolo.height) // 2), simbolo)

    destino = AQUI / "logo.ico"
    quadrado.resize((256, 256), Image.LANCZOS).save(
        destino, format="ICO", sizes=[(t, t) for t in TAMANHOS_ICO]
    )
    return destino


def main() -> int:
    lockup, lockup_real = _abrir(ORIGEM_LOCKUP)
    simb, simb_real = _abrir(ORIGEM_SIMBOLO)

    for caminho in (gerar_png(lockup), gerar_ico(simb)):
        print(f"Escrito: {caminho}")

    print()
    print(f"logo.png: {'a partir de ' + ORIGEM_LOCKUP.name if lockup_real else 'PROVISÓRIO — não é a marca da Exceltic'}")
    print(f"logo.ico: {'a partir de ' + ORIGEM_SIMBOLO.name if simb_real else 'PROVISÓRIO — não é a marca da Exceltic'}")
    if not (lockup_real and simb_real):
        faltam = [o.name for o, ok in ((ORIGEM_LOCKUP, lockup_real), (ORIGEM_SIMBOLO, simb_real)) if not ok]
        print(f"\nPõe em assets/: {', '.join(faltam)} — e volta a correr isto.")
    print("Depois: empacotar\\construir.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
