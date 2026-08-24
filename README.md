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

A janela tem duas abas e faz o caminho inteiro de uma vez:

- **1. Juntar arquivos** — escolha a pasta de origem e a de destino, marque copiar ou
  mover e clique em *Juntar arquivos*. O botao *Simular* mostra o que vai acontecer sem
  mexer em nada. Com a opcao "Ao terminar, gerar a planilha" marcada (padrao), ele ja
  emenda na aba 2 sozinho.
- **2. Planilha de documentos** — escolha a pasta e onde salvar o `.xlsx`.

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

## listar_documentos.py

Monta um Excel com a lista dos documentos: nome, titulo, versao, conteudo e mais.
Serve como passo seguinte do `extrair_arquivos.py`.

```bash
pip install openpyxl pypdf python-docx

python listar_documentos.py "Tarragona A-extract"
python listar_documentos.py "Tarragona A-extract" lista.xlsx --limite-conteudo 5000
python listar_documentos.py pasta/ lista.xlsx --ext .pdf --sem-conteudo
```

A planilha sai com duas abas:

- **Documentos** — uma linha por arquivo, com filtro automatico e link para abrir o arquivo:
  `#`, `Arquivo`, `Titulo`, `Versao`, `Versoes`, `Mais recente`, `Documento base`, `Tipo`,
  `Tamanho (KB)`, `Paginas`, `Palavras`, `Modificado em`, `Pasta`, `Conteudo`.
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
| `--ext .pdf .docx` | filtra por extensao |
| `--limite-conteudo N` | caracteres de conteudo por linha (padrao: 2000) |
| `--sem-conteudo` | so os dados dos arquivos, bem mais rapido |
| `--incluir-ocultos` | tambem lista arquivos e pastas com ponto |
