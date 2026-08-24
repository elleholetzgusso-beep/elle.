ddd

# Extrator de Documentos

Junta os arquivos espalhados em varias subpastas em uma pasta so e monta um Excel
com a lista dos documentos (nome, titulo, versao e conteudo).

Da para usar de duas formas: pelo **app de janela** ou pela **linha de comando**.

## App (recomendado)

```cmd
pip install openpyxl pypdf python-docx
python app.py
```

No Windows, depois de instalar as bibliotecas basta dar duplo clique em
**`abrir app.bat`**.

A janela tem duas abas, e cada uma funciona sozinha:

- **1. Juntar arquivos** — **so extrair, sem listar nem analisar nada**: escolha a pasta
  de origem e a de destino, marque copiar ou mover e clique em *Juntar arquivos*. Nao
  importa quantos niveis de subpasta existam, tudo termina solto em uma pasta unica.
  O botao *Simular* mostra o que vai acontecer sem mexer em nada.
  Em *Quando terminar de juntar* da para escolher entre parar por aqui (padrao) ou
  emendar direto na planilha da pasta de destino.
  Os botoes *so documentos* / *tudo*, ao lado do filtro de extensoes, servem para pegar
  so os arquivos de documento (pdf, doc, docx, xls, ppt, txt...) ou tudo o que houver.
- **2. Planilha de documentos** — **so a planilha, sem organizar nada**: aponte para
  qualquer pasta (com ou sem subpastas) e ela e lida onde esta, sem mover nem copiar
  arquivo nenhum. Quem quiser pular direto para ca tem o botao
  *"So quero a planilha, sem organizar"* na aba 1.

Antes de gerar, a aba 2 pergunta o que voce quer na planilha:

- **Lista completa** — abre cada documento e traz titulo, versao, paginas, contagem de
  palavras e o conteudo do texto.
- **So nomes e caminhos** — nao abre os arquivos: traz nome, caminho completo, tipo,
  tamanho, data e a versao (que sai do proprio nome do arquivo). Termina em segundos,
  mesmo com muitos documentos, e a planilha vem sem as colunas de conteudo.

Embaixo ficam a barra de andamento, o registro do que esta sendo feito e o botao
*Abrir resultado*, que abre a pasta ou a planilha pronta. As pastas usadas ficam
guardadas para a proxima vez.

### Gerar o .exe (opcional)

Para rodar em um computador sem Python instalado, de duplo clique em
**`criar_exe.bat`**. Ele instala o PyInstaller e cria
`dist\Extrator de Documentos.exe`, um arquivo unico que pode ser copiado para
outra maquina.

## Linha de comando

## extrair_arquivos.py

Junta todos os arquivos que estao espalhados em subpastas dentro de uma unica pasta.

```bash
# copia tudo de fotos/ (e subpastas) para tudo_junto/
python extrair_arquivos.py fotos/ tudo_junto/

# ve o que aconteceria, sem mexer em nada
python extrair_arquivos.py fotos/ tudo_junto/ --simular

# move em vez de copiar e apaga as subpastas que ficarem vazias
python extrair_arquivos.py fotos/ tudo_junto/ --mover --limpar-vazias

# so alguns tipos de arquivo
python extrair_arquivos.py docs/ so_pdfs/ --ext .pdf .docx

# mantem o caminho no nome: sub/pasta/foto.jpg vira sub_pasta_foto.jpg
python extrair_arquivos.py fotos/ tudo_junto/ --prefixo-pasta
```

Opcoes:

| Opcao | O que faz |
| --- | --- |
| `--mover` | move os arquivos em vez de copiar |
| `--conflito renomear\|pular\|sobrescrever` | o que fazer com nomes repetidos (padrao: `renomear`, que gera `foto_1.jpg`) |
| `--ext .jpg .png` | filtra por extensao |
| `--incluir-ocultos` | tambem pega arquivos e pastas que comecam com ponto |
| `--prefixo-pasta` | usa o caminho no nome final |
| `--separador` | separador do `--prefixo-pasta` (padrao: `_`) |
| `--simular` | mostra o plano sem alterar o disco |
| `--limpar-vazias` | remove as subpastas vazias depois de mover |

So precisa do Python 3 instalado, sem bibliotecas extras.

Nomes de pasta com espaco precisam de aspas:

```cmd
python extrair_arquivos.py "Tarragona A" "Tarragona A-extract"
```

Para achatar a propria pasta, sem criar outra, e so repetir o caminho. Os arquivos
das subpastas sobem para a raiz e o que ja estava solto la fica onde esta:

```cmd
python extrair_arquivos.py "Tarragona A" "Tarragona A" --mover --limpar-vazias
```

## listar_documentos.py

Monta um Excel com a lista dos documentos: nome, caminho, titulo, versao, conteudo e mais.
Nao mexe em nada — le a pasta onde ela esta, com todas as subpastas. Pode ser usado
depois do `extrair_arquivos.py` ou sozinho, em qualquer pasta.

```bash
pip install openpyxl pypdf python-docx

# lista completa (le o conteudo dos documentos)
python listar_documentos.py "Tarragona A"

# so nomes e caminhos, sem abrir os arquivos
python listar_documentos.py "Tarragona A" lista.xlsx --so-nomes

python listar_documentos.py pasta/ lista.xlsx --limite-conteudo 5000 --ext .pdf
```

A planilha sai com duas abas:

- **Documentos** — uma linha por arquivo, com filtro automatico e link para abrir o arquivo:
  `#`, `Arquivo`, `Titulo`, `Versao`, `Versoes`, `Mais recente`, `Documento base`, `Tipo`,
  `Tamanho (KB)`, `Paginas`, `Palavras`, `Modificado em`, `Pasta`, `Caminho completo`,
  `Conteudo`. Com `--so-nomes` saem as quatro colunas que dependem de abrir o arquivo
  (`Titulo`, `Paginas`, `Palavras` e `Conteudo`) e ficam as outras onze.
- **Resumo** — quantidade por tipo, total, quantos documentos distintos existem e
  a lista dos que tem mais de uma versao.

Sobre as versoes: o script le o nome do arquivo e reconhece `Rev00`, `Rev. A`, `v2.1`,
`versao 3`, `Edicao 2` e copias do Windows como `relatorio (2).pdf`. Tirando esse trecho
do nome ele monta o `Documento base` e agrupa: `Versoes` mostra quantos arquivos sao do
mesmo documento e `Mais recente` marca `Sim` na versao mais alta de cada grupo (as linhas
com mais de uma versao ficam destacadas em amarelo). Se o nome nao trouxer versao, ele
ainda procura um `Rev X` nas primeiras linhas do texto.

Titulo: vem das propriedades do arquivo (PDF, Word, Excel); se estiver vazio ou generico
(`untitled`, `Microsoft Word - ...`), usa o primeiro titulo/linha do conteudo.

Formatos com leitura de conteudo: `.pdf`, `.docx`, `.xlsx`, `.txt`, `.md`, `.csv` e outros
textos. Os demais (`.doc`, `.ppt`, imagens) entram na lista so com os dados do arquivo.

Opcoes:

| Opcao | O que faz |
| --- | --- |
| `--so-nomes` | so nomes, caminhos e dados dos arquivos, bem mais rapido (tambem aceita `--sem-conteudo`) |
| `--ext .pdf .docx` | filtra por extensao |
| `--limite-conteudo N` | caracteres de conteudo por linha (padrao: 2000) |
| `--incluir-ocultos` | tambem lista arquivos e pastas com ponto |

A deteccao de versao funciona nos dois modos, porque sai do nome do arquivo.
