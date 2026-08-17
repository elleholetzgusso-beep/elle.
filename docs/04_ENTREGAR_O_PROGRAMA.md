# Entregar o programa a quem não tem Python

Até aqui a ferramenta corre na linha de comandos, o que pressupõe Python
instalado e à-vontade com o terminal. Este documento é sobre a outra via: uma
janela com botões, embrulhada num `.exe` que se copia e se abre.

---

## A janela

```bash
python -m lpa_filler gui
```

À esquerda as entradas, em cima os cinco passos do fluxo, em baixo uma consola
que mostra exatamente o que está a acontecer:

```text
ENTRADAS               FLUXO   2 de 5 passos concluídos
 ✓ Relatório PES        ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
 ✓ Documentos recebidos │ ✓ FEITO││ ✓ FEITO││3 SEGUIN││4 ESPERA││5 ESPERA│
 ✓ Base de hallazgos    │Preparar││Analisar││Sugerir ││Gerar o ││Gerar o │
 ! Template LPA         │o proje…││os docu…││hallaz… ││LPA     ││Anejo   │
 ✓ Pasta de trabalho    └────────┘└────────┘└────────┘└────────┘└────────┘

CONTEXTO DA OBRA        [ CORRER PASSO 3 ]  [ ABRIR PASTA ]   ▓▓▓▓░░░░ 40%
  Solicitante
  Âncoras desta obra    O QUE ESTÁ A ACONTECER
  Código desta obra       $ lpa_filler scan -r ... -o documentos.yaml
                          # 72 documentos encontrados
EXIGÊNCIA               # 1 incertos (rever manualmente)
  ──────●─────  12       Escrito: documentos.yaml
                         Concluído.
```

Três coisas que a janela diz sem ser preciso perguntar:

- **O que falta preencher.** Cada entrada tem um `!` âmbar por preencher e um
  `✓` verde quando está — vê-se antes de tentar correr.
- **Por onde se vai.** Os passos mostram-se `FEITO` / `SEGUINTE` / `EM ESPERA`,
  e o botão principal aponta sempre ao seguinte. Também se pode clicar num
  cartão para repetir um passo anterior.
- **O que correu.** A consola imprime o comando exato antes de cada saída, por
  isso o que se vê na janela é reproduzível no terminal.

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

**Cores** — o dicionário `PALETA`, no topo de `lpa_filler/gui.py`. O laranja é a
única cor de marca; trocar os três tons de `marca` muda a janela toda.

**Logótipo** — a marca real da Exceltic já está em `assets/` (`logo-lockup.png`
e `simbolo.png`, ver `assets/LEIA-ME.md`). Trocar por outra versão é largar os
ficheiros novos nesses nomes e correr:

```bash
python assets/gerar_marca.py
```

Escreve o `logo.png` da barra (o lockup completo, 44 px sobre branco) e o
`logo.ico` do executável (só o escudo, 16→256 px — o lockup completo não se lê
a 16 px). Diz na consola qual dos dois usou de verdade e qual caiu no
provisório, para nunca se entregar um `.exe` com a marca errada sem dar por
isso.

Ambos são opcionais: sem eles a janela mostra o nome em texto e o executável
fica com o ícone genérico. Depois de mudar, voltar a correr `construir.bat`.

---

## Se a janela não abrir

| Sintoma | Causa provável |
|---|---|
| `A janela gráfica precisa do tkinter` | Python instalado sem o tcl/tk. Reinstalar de python.org com a opção *tcl/tk and IDLE* ligada. |
| O `.exe` abre e fecha logo | Empacotado com um erro. Pôr `console=True` na receita, voltar a construir e correr pela linha de comandos para ver a mensagem. |
| Demora a abrir da primeira vez | Normal em ficheiro único: descomprime para uma pasta temporária. As vezes seguintes são mais rápidas. |
