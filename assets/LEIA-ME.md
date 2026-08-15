# Marca

Dois ficheiros, ambos opcionais. Sem eles a janela mostra o nome em texto e o
executável fica com o ícone genérico — funciona à mesma.

| Ficheiro | Onde aparece | Formato |
|---|---|---|
| `logo.png` | Barra de topo da janela | PNG **sobre fundo branco** — a barra é branca. Cerca de 44 px de altura; o tkinter não redimensiona, por isso convém já vir no tamanho certo. |
| `logo.ico` | Ícone do `.exe` e da barra de tarefas | ICO com vários tamanhos (16, 32, 48, 256). |

As cores estão no dicionário `PALETA`, no topo de `lpa_filler/gui.py`. É o único
sítio onde vivem — mudar lá muda a janela toda.

```python
PALETA = {
    "marca": "#F15722",         # laranja: régua do topo, botão, passo ativo
    "marca_escura": "#D94E14",  # o mesmo laranja carregado (rato em cima)
    "marca_clara": "#FDE7D9",   # fundo do cartão do passo seguinte
    "cartao": "#FFFFFF",
    ...
}
```

O laranja é a única cor de marca. O resto são brancos, cinzas e as três cores de
estado da consola (verde/âmbar/vermelho), que não são decorativas — distinguem
"escrito" de "atenção" de "erro". Trocar os três tons de `marca` muda a
identidade toda sem lhes tocar.

Depois de trocar os ficheiros ou as cores, voltar a correr `empacotar\construir.bat`.
