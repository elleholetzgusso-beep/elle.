# Marca

> **O `logo.png` e o `logo.ico` que aqui estão são provisórios** — um quadrado
> laranja com um E. Não são a marca da Exceltic. Estão cá porque um `.exe` sem
> ícone é dos sinais que mais depressa fazem um antivírus desconfiar.

## Pôr a marca verdadeira

Um ficheiro e um comando:

1. Guardar o símbolo em **`assets/simbolo.png`** — PNG com fundo transparente,
   256 px ou mais.
2. ```bash
   pip install Pillow
   python assets/gerar_marca.py
   ```
3. `empacotar\construir.bat`

O gerador escreve o `logo.png` e o `logo.ico` a partir dele, e diz na consola se
usou o símbolo verdadeiro ou o provisório. Não é preciso mexer no `LPA.spec`:
já apanha o que estiver em `assets/`.

## Os dois ficheiros gerados

| Ficheiro | Onde aparece | O que é |
|---|---|---|
| `logo.png` | Barra de topo da janela | O símbolo a 44 px, achatado sobre branco — a barra é branca. O tkinter não redimensiona, por isso o tamanho tem de vir certo do gerador. |
| `logo.ico` | Ícone do `.exe` e da barra de tarefas | O símbolo com transparência, em 16/32/48/64/128/256 px. |

Na barra vai **só o símbolo**, sem a palavra: já lá está «AUTOMATIZAÇÃO DE LPA»
em texto, ao lado, e a palavra duas vezes na mesma barra não acrescenta nada.

Ambos são opcionais. Sem eles a janela mostra `EXCELTIC` em texto e o executável
fica com o ícone genérico — funciona à mesma.

## Cores

Estão no dicionário `PALETA`, no topo de `lpa_filler/gui.py`. É o único sítio
onde vivem — mudar lá muda a janela toda.

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
