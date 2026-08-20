# Entregar o programa a quem não tem Python

Até aqui a ferramenta corre na linha de comandos, o que pressupõe Python
instalado e à-vontade com o terminal. Este documento é sobre a outra via: uma
janela com botões.

Há **duas formas** de a abrir, e a diferença entre elas é se a máquina de
destino tem Python instalado ou não:

| | Precisa de Python instalado? | Como se abre |
|---|---|---|
| `Abrir_LPA.bat` (raiz do repositório) | **Sim** — a máquina tem de ter Python, tal como para correr `python -m lpa_filler ...` | Clique duplo. Instala o pacote sozinho na primeira vez; das seguintes abre logo, sem terminal visível. |
| `dist\LPA-Exceltic.exe` (via `empacotar\construir.bat`) | **Não** — o Python vai lá dentro, empacotado | Clique duplo, copiado para qualquer máquina Windows. |

Para uso próprio (com Python já instalado, como neste computador), `Abrir_LPA.bat`
é o caminho direto. Correr `Crear_Acceso_Directo.bat` uma vez põe um ícone
"LPA Exceltic" no Ambiente de Trabalho, para nunca mais ser preciso encontrar
esta pasta. Para dar a ferramenta a alguém **sem** Python — o Roberto — é o
`.exe` que serve, mais abaixo neste documento.

---

## A janela

```bash
python -m lpa_filler gui
```

(ou, mais simples: clique duplo em `Abrir_LPA.bat`.)

À esquerda as entradas, em cima os cinco passos do fluxo, em baixo uma consola
que mostra exatamente o que está a acontecer:

```text
O QUE VAIS FAZER       FLUXO  1 de 5 concluídos · 2 dispensáveis
 ☐ Revisão de um LPA    ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
   já existente         │ ✓ FEITO││2 DISPEN││3 DISPEN││4 SEGUIN││5 ESPERA│
                        │Preparar││Analisar││Sugerir ││Gerar o ││Gerar o │
ENTRADAS                │o proje…││os docu…││hallaz… ││LPA     ││Anejo   │
 ✓ Relatório PES        └────────┘└────────┘└────────┘└────────┘└────────┘
 ! LPA anterior
 ✓ Documentos recebidos [ CORRER PASSO 4 ]  [ ABRIR PASTA ]   ▓▓░░░░░░ 20%
 ✓ Base de hallazgos
 ! Template LPA         O QUE ESTÁ A ACONTECER
 ✓ Pasta de trabalho      $ lpa_filler scan -r ... -o documentos.yaml
                          # 72 documentos encontrados
CONTEXTO DA OBRA          # 1 incertos (rever manualmente)
  Solicitante             Escrito: documentos.yaml
  Âncoras desta obra      Concluído.
  Código desta obra
```

Três coisas que a janela diz sem ser preciso perguntar:

- **O que falta preencher.** Cada entrada tem um `!` âmbar por preencher e um
  `✓` verde quando está — vê-se antes de tentar correr.
- **Por onde se vai.** Os passos mostram-se `FEITO` / `SEGUINTE` / `EM ESPERA` /
  `DISPENSÁVEL`, e o botão principal aponta sempre ao seguinte que interessa.
  Também se pode clicar num cartão para repetir um passo anterior.
- **O que correu.** A consola imprime o comando exato antes de cada saída, por
  isso o que se vê na janela é reproduzível no terminal.

### Os dois modos

A caixa **«Revisão de um LPA já existente»**, no topo da coluna esquerda, decide
o que o passo 1 faz:

| | Desligada — LPA novo | Ligada — revisão |
|---|---|---|
| Passo 1 corre | `from-docx` → `scan` → `merge` | `scan` → `update` → `rev` |
| Os puntos | monta de raiz (**apaga** os que houver) | **preserva**, acrescenta o envío novo e regista a versão |
| Precisa de | Relatório PES | `projeto.yaml` desta obra — ou, se ainda não existir, o **LPA anterior** (`.xlsm`), de onde arranca com o `extract` |

Numa revisão o PES não é pedido outra vez: é do primeiro LPA. E o aviso de
"isto apaga os puntos" desaparece, porque nesse modo não apaga nada.

Em modo revisão, se o campo **«LPA anterior»** estiver preenchido, o passo 4
compara-se contra esse ficheiro e pinta a azul (`#0070C0`) o que for novo desde
ele — puntos inteiros, diálogo acrescentado a puntos que já existiam,
documentos e envíos novos, a linha da versão nova. Sem esse campo preenchido,
nada se destaca (o `extract` já corre à mesma se o `projeto.yaml` não existir;
o campo serve aqui só para a comparação, mesmo quando não é preciso para
arrancar).

### Passos dispensáveis

Com **«Deixar a aba LPA vazia»** ligada, os passos 2 (analisar) e 3 (sugerir)
ficam marcados `DISPENSÁVEL` e o botão salta-os. A razão é simples: ambos
existem para propor conteúdo para a aba LPA, e essa aba vai ficar vazia para se
escrever à mão. O passo 2 é também o mais lento — abre todos os `.pdf`
recebidos.

**Dispensável não é bloqueado.** Os cartões continuam clicáveis: o `radar.txt` é
útil mesmo quando se escreve tudo à mão, só deixa de ser obrigatório passar por
ele para chegar ao fim.

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
| O passo 1 sobre um projeto que já tem puntos, **em modo LPA novo** | Pergunta antes, dizendo quantos puntos vai apagar — e lembra que era a caixa «Revisão» que evitava isso. Em modo revisão não pergunta, porque não apaga. |

### Porque é que o passo 2 era lento

O `leer` e o `radar` percorrem a mesma pasta de documentos recebidos, um a
seguir ao outro. Cada um abria os ficheiros por sua conta, por isso **todos os
`.pdf` eram lidos duas vezes** — e um `.pdf` mal formado pode ocupar até 25
segundos (`PDF_TIMEOUT_S`) antes de se desistir dele. Numa pasta com 80
documentos isso é muito tempo a dobrar.

O `lector` passou a guardar o texto já extraído, por `(caminho, data de
modificação, tamanho)`. Um documento substituído por uma versão nova entre dois
comandos é relido; o mesmo ficheiro inalterado não. É uma cache dentro da
execução, não em disco — não há estado a ficar desatualizado entre sessões.

### O nome do ficheiro final, sem escrever nada

O passo 4 (Gerar o LPA) e o passo 5 (Anejo A.2) já não saem como `LPA.xlsm` e
`anejo_a2.csv`. Assim que o `projeto.yaml` tem uma `portada.referencia` válida
(ex. `EXC2025-16126-1/002/LPA/05`), o nome do ficheiro sai dela — `LPA.xlsm`
passa a `EXC2025-16126-1-002-LPA-05.xlsm`, seguindo o PE/05. O Anejo fica preso
ao mesmo nome (`..._Anejo-A2.csv`), para os dois ficheiros de uma revisão se
reconhecerem como o par que são.

Sem uma referência válida (placeholder por preencher, ou projeto ainda vazio),
cai no nome genérico — não se inventa um código.

### A base dentro do aplicativo

O campo "Base de hallazgos" já vem preenchido, sempre com o mesmo caminho: ao
lado do `Abrir_LPA.bat` a correr da fonte, ao lado do `.exe` quando empacotado.
Não é preciso ir à procura dela a cada obra nova.

Para a fazer crescer há o botão **"+ Añadir LPA a la base"**, ao lado do campo:
escolhe um ou mais `.xlsm` de LPAs já emitidos e acrescenta os hallazgos —
mesmo comando `harvest` de sempre, só que sem passar pelo terminal. Por baixo
do botão vê-se sempre quantos hallazgos e de quantas obras a base já tem.

> Ao empacotar num `.exe`, a base **não** vai lá dentro presa: fica ao lado
> do executável, na pasta onde ele foi copiado — nunca em `sys._MEIPASS`
> (a pasta temporária onde o PyInstaller descomprime a cada arranque, só de
> leitura, apagada ao fechar). Uma base que só existisse lá dentro perdia-se
> a cada fecho do programa.

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
