# CLI de desenvolvimento (`python -m organizador`)

Interface de linha de comandos do motor, usada só para testar. O Roberto
nunca chega aqui: ele usa a janela (`interfaz.py`) ou o menu de consola
(`lanzador.py`). Por isso as mensagens deste CLI continuam em português.

## Requisitos

Python 3.9 ou superior. Sem dependências externas.

```cmd
python -m organizador --help
```

## Instalar (opcional)

```cmd
pip install .
organizador --help
```

## Criar projeto

```cmd
python -m organizador novo-projeto "Estación de Torre Pacheco (Apeadero)" --ano 2026 --codigo 16883 --destino "7.- Proyectos/1.- En curso"
```

Cria:

```text
2026-16883-ESTACIÓN DE TORRE PACHECO (APEADERO)
├── 1_Oferta
├── 2_Doc Recebida
│   └── mails
├── 3_Doc Trabajo
└── 4_Doc Generada
    └── Doc
```

## Registar envio

```cmd
python -m organizador envio "PROYECTOS\2026-16883-ESTACIÓN DE TORRE PACHECO (APEADERO)" --data 20260807 --obs "sin revisar"
```

Cria automaticamente o próximo `Envío N`. A data aceita `AAAAMMDD`,
`AAAA-MM-DD` ou `DD/MM/AAAA`; sem `--data`, usa hoje.

## Organizar arquivos

```cmd
python -m organizador organizar "PROYECTOS\2026-16883-ESTACIÓN DE TORRE PACHECO (APEADERO)\3_Doc Trabajo" --por documento
```

Opções de `--por`:

```text
tipo        → Documentos, Imágenes, Hojas de cálculo, etc.
documento   → 001-PES, 002-LPA, etc.
envio       → Envío 29 20260107 (pastas de envio que já existem)
extensao    → PDF, XLSX, etc.
data        → 2026/07-Julio
alfabetico  → A, B, C, 0-9
```

Os nomes das pastas criadas estão em espanhol (categorias e meses), como no
resto do programa. `python -m organizador categorias` lista as categorias e
as extensões de cada uma.

### `--por envio`

Distribui os ficheiros soltos pelas pastas `Envío N AAAAMMDD` que **já
existem**, pela data de modificação de cada ficheiro. Corre-se sobre a
`2_Doc Recebida` do projeto:

```cmd
python -m organizador organizar "...\2026-16883-…\2_Doc Recebida" --por envio --simular
```

A regra é uma só: **cada ficheiro vai para o último envio cuja data seja
igual ou anterior à sua** — o envio que estava aberto quando o ficheiro
chegou. Um ficheiro de 16/12 entra no `Envío 28 20251215`, não no
`Envío 29 20260107`.

Ao contrário dos outros critérios, este **não cria pastas**: usa só os envios
já registados (com `python -m organizador envio`, ou pela janela). Dois casos
não movem nada e são listados como ignorados:

- ficheiros anteriores ao primeiro envio — ficam onde estão;
- se não houver nenhuma pasta de envio na pasta indicada, o comando falha com
  uma mensagem a pedir que se registe o envio primeiro.

Outras opções:

```cmd
-r, --recursivo
-i, --ignorar "*.tmp"
--incluir-ocultos
--categorias meu.json
--formato-data %Y-%m
-d, --detalhado
```

Não sobrescreve arquivos existentes. Cria automaticamente `arquivo (1).pdf`.

## Comandos

```cmd
python -m organizador criar <destino>
python -m organizador novo-projeto <nome>
python -m organizador envio <projeto>
python -m organizador organizar <pasta>
python -m organizador limpar <pasta>
python -m organizador arvore [pasta]
python -m organizador modelos
python -m organizador categorias
python -m organizador historico
python -m organizador desfazer [id]
```

## Criar estruturas

```cmd
python -m organizador modelos
python -m organizador criar "C:\Obras" --modelo proyecto
python -m organizador criar . --pastas Contratos Faturas "Fotos/2026"
python -m organizador criar . --arquivo minha-estrutura.txt
```

## Simular sem alterar arquivos

Todos os comandos que escrevem em disco aceitam `--simular`:

```cmd
python -m organizador organizar "3_Doc Trabajo" --por documento --simular
```

## Desfazer

```cmd
python -m organizador historico
python -m organizador desfazer
python -m organizador desfazer 20260814-091514-005 --simular
```

## Testes

```cmd
python -m unittest discover -s tests -v
```
