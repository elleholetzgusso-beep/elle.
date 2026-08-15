# Entregar o programa a quem não tem Python

Até aqui a ferramenta corre na linha de comandos, o que pressupõe Python
instalado e à-vontade com o terminal. Este documento é sobre a outra via: uma
janela com botões, embrulhada num `.exe` que se copia e se abre.

---

## A janela

```bash
python -m lpa_filler gui
```

Cinco botões pela ordem do fluxo, à esquerda as entradas, à direita uma consola
que mostra exatamente o que está a acontecer:

```text
ENTRADAS                          O QUE ESTÁ A ACONTECER
  Relatório PES (.docx)             $ lpa_filler scan -r ... -o documentos.yaml
  Pasta dos documentos recebidos    # 72 documentos encontrados
  Base de hallazgos (.csv)          # 1 incertos (rever manualmente)
  Template LPA (.xlsm)              Escrito: documentos.yaml
  Pasta onde gravar                 Concluído.

PASSOS
  1 · Preparar o projeto
  2 · Analisar os documentos
  3 · Sugerir hallazgos
  4 · Gerar o LPA
  5 · Gerar o Anejo A.2
```

A janela **não sabe fazer nada** que a linha de comandos não faça: monta os
mesmos comandos e chama-os. Um teste garante que todos os comandos que a janela
oferece existem mesmo e aceitam os argumentos que ela lhes passa, para não se
repetir o caso do `--scope` no `radar` — uma opção que parecia existir e não
existia.

Isso também quer dizer que os limites do `03_REGRAS_DE_AUTOMACAO.md` continuam
todos de pé. **Não há botão que feche um punto.** O nível 3 continua a ser do
avaliador.

### Duas proteções próprias da janela

| Situação | O que acontece |
|---|---|
| Falta uma entrada | Diz o que falta, por nome, e não corre nada. |
| O passo 1 sobre um projeto que já tem puntos | Pergunta antes, dizendo quantos puntos vai apagar. |

---

## O executável

```bat
empacotar\construir.bat
```

Instala o que falta, corre os testes, empacota, e escreve
`dist\LPA-Exceltic.exe` — cerca de 22 MB, ficheiro único, sem consola por trás.
**Se os testes falharem, não empacota.**

Corre-se na máquina de quem desenvolve, não na de quem vai usar. O resultado é
um ficheiro para copiar; do outro lado não é preciso instalar nada.

### O que fica dentro

O Python, o `openpyxl`, o `PyYAML`, o leitor de `.docx` e o de `.pdf`. Fora
ficam o `matplotlib`, o `numpy`, o `pandas` e companhia, que não se usam e
valeriam dezenas de MB.

---

## O antivírus

Vale a pena saber isto antes de prometer uma data de entrega.

Um `.exe` do PyInstaller descomprime-se para uma pasta temporária e executa-se a
si próprio a partir de lá. É também o que faz um vírus embrulhado, e os
antivírus reconhecem a forma, não a intenção. Junta-se a isto o ficheiro não
estar assinado digitalmente, e o resultado é que **um bloqueio é plausível, não
é azar**.

O que já está feito para reduzir a probabilidade:

| Medida | Porquê |
|---|---|
| Identificação nas Propriedades do Windows | Um `.exe` anónimo é o primeiro a ser travado. Nome, empresa, versão e descrição estão preenchidos. |
| Sem compressão UPX | Comprimir é dos gatilhos mais fortes. Poupava alguns MB e não compensa. |

O que **não** está feito, porque não é uma decisão técnica:

- **Assinatura digital.** É o que resolve a sério. Exige um certificado de
  assinatura de código comprado em nome da empresa — decisão de quem gere o IT,
  não deste repositório.

Se for bloqueado, por ordem de preferência:

1. **Pedir ao IT que autorize o ficheiro** pela sua impressão digital (hash).
   É o caminho normal para ferramentas internas e não abre exceções largas.
2. **Entregar a pasta em vez do ficheiro único.** Trocar `--onefile` por
   `--onedir` na receita: deixa de haver auto-extração, que é metade do que
   levanta suspeita. Fica uma pasta com muitos ficheiros em vez de um só.
3. **Voltar ao `.bat`.** Nenhum antivírus desconfia de um ficheiro de texto de
   duas linhas. Exige Python instalado do outro lado — uma vez só, e é uma
   instalação normal de python.org.

Testar o `.exe` numa máquina com o mesmo antivírus da casa **antes** de o
anunciar. Descobrir o bloqueio na máquina de quem ia usar é a pior altura.

---

## Mudar o aspeto

Duas coisas, e nada mais no programa depende delas:

- **Cores** — o dicionário `PALETA`, no topo de `lpa_filler/gui.py`.
- **Logótipo** — `assets/logo.png` (janela) e `assets/logo.ico` (ícone do
  `.exe`). Ver `assets/LEIA-ME.md` para os tamanhos.

Ambos são opcionais: sem eles a janela mostra o nome em texto e o executável
fica com o ícone genérico. Depois de mudar, voltar a correr `construir.bat`.

---

## Se a janela não abrir

| Sintoma | Causa provável |
|---|---|
| `A janela gráfica precisa do tkinter` | Python instalado sem o tcl/tk. Reinstalar de python.org com a opção *tcl/tk and IDLE* ligada. |
| O `.exe` abre e fecha logo | Empacotado com um erro. Pôr `console=True` na receita, voltar a construir e correr pela linha de comandos para ver a mensagem. |
| Demora a abrir da primeira vez | Normal em ficheiro único: descomprime para uma pasta temporária. As vezes seguintes são mais rápidas. |
