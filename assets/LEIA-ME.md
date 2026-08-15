# Marca

Dois ficheiros, ambos opcionais. Sem eles a janela mostra o nome em texto e o
executável fica com o ícone genérico — funciona à mesma.

| Ficheiro | Onde aparece | Formato |
|---|---|---|
| `logo.png` | Barra de topo da janela | PNG. Cerca de 40 px de altura; o tkinter não redimensiona, por isso convém já vir no tamanho certo. |
| `logo.ico` | Ícone do `.exe` e da barra de tarefas | ICO com vários tamanhos (16, 32, 48, 256). |

As cores estão no dicionário `PALETA`, no topo de `lpa_filler/gui.py`. É o único
sítio onde vivem — mudar lá muda a janela toda.

```python
PALETA = {
    "tinta": "#12263A",     # barra de topo
    "destaque": "#2E7DA8",  # botões
    ...
}
```

Depois de trocar os ficheiros ou as cores, voltar a correr `build\construir.bat`.
