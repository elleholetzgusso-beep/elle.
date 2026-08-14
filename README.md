# Organizador de Pastas

Programa de linha de comando para **criar** estruturas de pastas e **organizar**
arquivos automaticamente. Feito em Python puro (sem bibliotecas externas),
funciona no Windows, Linux e macOS.

Tudo o que o programa faz pode ser testado antes com `--simular` e revertido
depois com `desfazer`. Nenhum arquivo e sobrescrito ou apagado.

---

## Instalacao

Basta ter o Python 3.9 ou superior:

```bash
python -m organizador --help
```

Para instalar o comando `organizador` no sistema:

```bash
pip install .
organizador --help
```

---

## Estrutura de projeto suportada

O modelo `proyecto` reproduz o padrao usado nos projetos de obra:

```
7.- Proyectos/
└── 1.- En curso/
    └── 2026-16883-ESTACIÓN DE TORRE PACHECO (APEADERO)/
        ├── 1_Oferta
        ├── 2_Doc Recebida
        │   ├── Envío 1 20260702
        │   ├── Envío 2 20260708
        │   ├── Envío 3 20260807 sin revisar
        │   └── mails
        ├── 3_Doc Trabajo
        └── 4_Doc Generada
            └── Doc
```

### Criar um projeto novo

```bash
python -m organizador novo-projeto "Estación de Torre Pacheco (Apeadero)" \
    --ano 2026 --codigo 16883 --destino "7.- Proyectos/1.- En curso"
```

Cria a pasta `2026-16883-ESTACIÓN DE TORRE PACHECO (APEADERO)` com todas as
subpastas. O nome e montado no padrao `AAAA-CODIGO-NOME` e os caracteres que o
Windows nao aceita (`\ / : * ? " < > |`) sao trocados por espaco.

### Registrar um envio do cliente

```bash
python -m organizador envio "2026-16883-ESTACIÓN DE TORRE PACHECO (APEADERO)" \
    --data 20260807 --obs "sin revisar"
```

Cria `2_Doc Recebida/Envío 4 20260807 sin revisar`. O numero e calculado
sozinho (o proximo livre) e a data aceita `AAAAMMDD`, `AAAA-MM-DD` ou
`DD/MM/AAAA` — sem `--data`, usa a data de hoje.

---

## Organizar arquivos

```bash
python -m organizador organizar "3_Doc Trabajo" --por documento --ignorar "*.tmp" "~$*"
```

Criterios disponiveis (`--por`):

| Criterio     | Agrupa por                        | Exemplo de pasta criada        |
|--------------|-----------------------------------|--------------------------------|
| `tipo`       | categoria do arquivo (padrao)     | `Documentos`, `Planilhas`      |
| `documento`  | codigo do documento               | `001-PES`, `002-LPA`           |
| `extensao`   | extensao                          | `PDF`, `XLSX`                  |
| `data`       | data de modificacao               | `2026/07-Julho`                |
| `alfabetico` | primeira letra do nome            | `A`, `B`, `0-9`                |

O criterio `documento` entende a nomenclatura usada nos projetos —
`EXC2026-16883-001-PES-01_R`, `EXC2026-16883-002-LPA-03`,
`EXC2026-16883-003-IES-01_borrador` — e junta todas as revisoes (`_R`, `_RR`,
`_RRA`, `_borrador`) do mesmo documento na mesma pasta. Arquivos fora do padrao
vao para `Sin codigo`.

Outras opcoes uteis:

- `-r, --recursivo` — inclui os arquivos das subpastas
- `-i, --ignorar "*.tmp"` — pula arquivos por padrao de nome
- `--incluir-ocultos` — inclui arquivos que comecam com ponto
- `--categorias meu.json` — usa suas proprias categorias
- `-d, --detalhado` — mostra tambem o que foi ignorado

Se ja existir um arquivo com o mesmo nome no destino, o novo entra como
`nome (1).pdf` — nada e sobrescrito.

---

## Todos os comandos

| Comando                | O que faz                                              |
|------------------------|--------------------------------------------------------|
| `criar <destino>`      | Cria uma estrutura de pastas                            |
| `novo-projeto <nome>`  | Cria a pasta do projeto no padrao `AAAA-CODIGO-NOME`    |
| `envio <projeto>`      | Cria a proxima pasta `Envío N AAAAMMDD`                 |
| `organizar <pasta>`    | Move os arquivos para subpastas                         |
| `limpar <pasta>`       | Remove as subpastas vazias                              |
| `arvore [pasta]`       | Mostra a estrutura em forma de arvore                   |
| `modelos`              | Lista os modelos prontos                                |
| `categorias`           | Lista as categorias de arquivos                         |
| `historico`            | Mostra as operacoes feitas                              |
| `desfazer [id]`        | Reverte a ultima operacao (ou a informada)              |

Todos os comandos que alteram o disco aceitam `-s, --simular`.

### Criar estruturas a partir de modelos ou arquivos

```bash
python -m organizador modelos                          # ver os modelos
python -m organizador criar "C:\Obras" --modelo proyecto
python -m organizador criar . --pastas Contratos Faturas "Fotos/2026"
python -m organizador criar . --arquivo minha-estrutura.txt
```

O arquivo de estrutura pode ser um `.txt` com indentacao:

```
Cliente A
    Contratos
    Faturas
Cliente B
```

ou um `.json` (lista de caminhos ou objeto aninhado):

```json
{ "Cliente A": ["Contratos", "Faturas"], "Cliente B": {} }
```

---

## Desfazer

Toda operacao que muda o disco fica registrada em
`~/.organizador-pastas/historico.json` (mude com `--historico caminho.json` ou
com a variavel de ambiente `ORGANIZADOR_HISTORICO`).

```bash
python -m organizador historico            # lista o que foi feito
python -m organizador desfazer             # reverte a ultima operacao
python -m organizador desfazer 20260814-091514-005 --simular
```

Desfazer devolve os arquivos ao lugar de origem e remove as pastas que a
operacao tinha criado (somente se estiverem vazias). Use `--sem-registro` para
executar sem gravar no historico.

---

## Testes

```bash
python -m unittest discover -s tests -v
```

---

## Organizacao do codigo

| Arquivo                     | Responsabilidade                                   |
|-----------------------------|----------------------------------------------------|
| `organizador/cli.py`        | Interface de linha de comando                      |
| `organizador/criador.py`    | Criacao de estruturas de pastas                    |
| `organizador/arrumador.py`  | Organizacao de arquivos e limpeza de pastas vazias |
| `organizador/projetos.py`   | Projetos `AAAA-CODIGO-NOME` e envios               |
| `organizador/modelos.py`    | Modelos prontos e leitura de `.txt` / `.json`      |
| `organizador/categorias.py` | Mapa de extensoes por categoria                    |
| `organizador/historico.py`  | Registro das operacoes                             |
| `organizador/desfazer.py`   | Reversao das operacoes                             |
