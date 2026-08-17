# Marca

A marca verdadeira da Exceltic já está aqui, em dois ficheiros de origem:

| Ficheiro | O que é | Origem |
|---|---|---|
| `logo-lockup.png` | Escudo + wordmark "Exceltic" + "DELIVERING EXCELLENCE" | Extraído do material de formação da Exceltic |
| `simbolo.png` | Só o escudo, recortado do lockup | Recorte do ficheiro acima |

`logo.png` e `logo.ico` (os que o programa usa de facto) são **gerados** a
partir destes dois — não se editam à mão:

```bash
pip install Pillow
python assets/gerar_marca.py
```

seguido de `empacotar\construir.bat` para o executável apanhar o resultado.

## Porque são dois ficheiros de origem, e não um só a dois tamanhos

O lockup completo, com o wordmark em serifa e a legenda por baixo, deixa de se
ler a 16 px — que é o tamanho mais pequeno do ícone do `.exe`, na barra de
tarefas. O escudo sozinho, sem letras finas, ainda se reconhece a esse
tamanho. Por isso:

| Ficheiro gerado | Onde aparece | Vem de |
|---|---|---|
| `logo.png` | Barra de topo da janela | `logo-lockup.png`, à altura da barra (44 px), sobre branco |
| `logo.ico` | Ícone do `.exe` e da barra de tarefas | `simbolo.png`, com transparência, em 16/32/48/64/128/256 px |

Se algum dos dois ficheiros de origem faltar, o gerador cai num provisório —
um quadrado laranja com um E — e diz isso mesmo na consola, para nunca se
confundir um com o outro nem entregar um `.exe` com a marca errada sem dar por
isso.

> `simbolo.png` tem 78×104 px, recortado do lockup original (313×221 px) — não
> há um ficheiro vetorial ou de maior resolução disponível. O ícone gerado fica
> ligeiramente suave a 256 px por causa disso. Se a Exceltic tiver o escudo em
> SVG ou PNG de maior resolução, substituir `simbolo.png` melhora o resultado
> sem tocar em mais nada.

Ambos os gerados são opcionais: sem eles a janela mostra `EXCELTIC` em texto e
o executável fica com o ícone genérico do PyInstaller — funciona à mesma, só
sem identificação.

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
