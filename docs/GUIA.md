# Guia do lpa_filler

Ferramenta de automatização de LPAs (Listado de Puntos Abiertos) para avaliações
independentes de segurança (ISA) ferroviárias, alinhada com os procedimentos
PE/Inspección/01–05 e a norma UNE-EN ISO/IEC 17020.

Índice:
1. [Instalação](#1-instalação)
2. [O fluxo em uma passagem](#2-o-fluxo-em-uma-passagem)
3. [Comandos](#3-comandos)
4. [Recursos normativos](#4-recursos-normativos)
5. [Estrutura do projeto.yaml](#5-estrutura-do-projetoyaml)
6. [Módulos internos](#6-módulos-internos)
7. [Testes](#7-testes)

---

## 1. Instalação

```bash
pip install -e .            # instala o pacote e o comando 'lpa-filler'
pip install -e '.[docx]'    # + suporte a from-docx (python-docx)
pip install -e '.[dev]'     # + pytest
```

Requer Python ≥ 3.10. Dependências base: `openpyxl`, `PyYAML`.

Todos os comandos correm também via `python -m lpa_filler <comando>`.

---

## 2. O fluxo em uma passagem

```
                     LPAs históricos (.xlsm)
                              │
                       harvest │  (uma vez / periódico)
                              ▼
                     base_hallazgos.csv ──────────────┐
                                                       │
  Doc Recibida/          relatório PES (.docx)         │
        │                        │                     │
   scan │                from-docx │                   │
        ▼                        ▼                     │
  documentos.yaml           meta.yaml                  │
        └───────────┬───────────┘                      │
                merge │                                │
                      ▼                                │
                projeto.yaml ◄─── suggest ─────────────┘
                      │        (candidatos da base)
             (editar à mão)
                      │
                  rev │  (descrição da próxima revisão)
                      ▼
                  fill │
                      ▼
                  LPA.xlsm  +  veredicto esperado do IES
```

`extract` faz o caminho inverso (reconstrói `projeto.yaml` a partir de um
`.xlsm` já preenchido) para arrancar de um LPA existente.

---

## 3. Comandos

### `harvest` — construir a base de hallazgos
Extrai todos os puntos de LPAs `.xlsm` para um CSV reutilizável (uma linha por
hallazgo). Serve de "base de erros" para o `suggest`.

```bash
python -m lpa_filler harvest -r "pasta/com/LPAs" -o base_hallazgos.csv
python -m lpa_filler harvest -i LPA_A.xlsm LPA_B.xlsm -o base_hallazgos.csv
python -m lpa_filler harvest -i novo.xlsm -o base_hallazgos.csv          # acrescenta
python -m lpa_filler harvest -i novo.xlsm -o base_hallazgos.csv --overwrite
```

Estados legados fora do PE/03 (`Controlado`, `Conforme`, ...) são mapeados para o
equivalente PE/03 e o valor original preservado na coluna `estado_legado`
(migração reversível — ver §4).

### `scan` — catalogar documentos recebidos
Percorre `1_Doc Recibida/Envío N AAAAMMDD/...`, agrupa por documento e deteta
versões (`_v06`). Faz a triagem de documentos não avaliativos (PE/01).

```bash
python -m lpa_filler scan -r "1_Doc Recibida" -o documentos.yaml --autor "UTE"
python -m lpa_filler scan -r "1_Doc Recibida" --group-by folder
python -m lpa_filler scan -r "1_Doc Recibida" --no-triage      # desliga a triagem PE/01
```

A consola (stderr) lista os `desviados` (não avaliativos) e os `incertos`
(a rever), com o motivo citável de cada um.

### `from-docx` — metadados do PES
Extrai título, código, referência e evaluadores do relatório de origem `.docx`.

```bash
python -m lpa_filler from-docx -i EXC2025-16126-1-001-PES-02.docx -o meta.yaml
```

### `merge` — montar o projeto.yaml
Junta a saída do `scan` e do `from-docx` num `projeto.yaml` pronto a editar
(secção `puntos` vazia — preenche-se à mão ou com o `suggest`).

```bash
python -m lpa_filler merge -m meta.yaml -d documentos.yaml -o projeto.yaml \
    --solicitante "UTE ESTEYCO-ARDANUY"
```

### `suggest` — propor hallazgos da base
Matching determinístico (sem IA) entre os documentos do projeto e a base
histórica. Dois modos:

```bash
# Modo projeto: pré-preenche 'puntos' com candidatos (rever sempre!)
python -m lpa_filler suggest -b base_hallazgos.csv -p projeto.yaml -o projeto.yaml \
    --scope "Torre Pacheco, L352, Balsicas" --min-score 2

# Modo consulta: imprime correspondências para um texto
python -m lpa_filler suggest -b base_hallazgos.csv -q "perfilado de banqueta" -n 5
```

`--scope` ativa a deteção de contaminação entre obras: sugestões cujo texto
nomeia outra obra ficam marcadas `_fora_escopo` e afundadas na ordenação
(nunca apagadas). `--debug` mostra o melhor score por documento para calibrar
`--min-score`.

### `rev` — próxima revisão do Control de Versiones
Deteta os envíos ainda não mencionados e compõe a descrição da revisão nova.

```bash
python -m lpa_filler rev -p projeto.yaml --solicitante "UTE ESTEYCO-ARDANUY"
```

### `fill` — gerar o .xlsm final
Preenche o template preservando macros, fórmulas, dropdowns e pivot tables.
Calcula e reporta o veredicto esperado do IES (§4).

```bash
python -m lpa_filler fill -t examples/template_exemplo.xlsm -d projeto.yaml -o LPA.xlsm
python -m lpa_filler fill -t template.xlsm -d projeto.yaml -o LPA.xlsm \
    --veredicto-cell "Portada!B30"
```

### `extract` — reconstruir o YAML (bootstrap)
```bash
python -m lpa_filler extract -i LPA_existente.xlsm -o projeto.yaml
```

---

## 4. Recursos normativos

| Recurso | Procedimento | Onde | Comportamento |
|---|---|---|---|
| **Triagem de documentos não avaliativos** | PE/01 | `scan` | Ofertas, acuses, cartas, comunicações → `desviado` (ficam em Doc Evaluados, sem gerar puntos). Sinais fracos (acta, correo) → `incerto` (seguem no fluxo, listados para revisão). Actas de *pruebas* FAT/SAT são exceção técnica: contam como avaliáveis. Todo desvio regista o motivo. |
| **Validação de nomenclatura** | PE/05 | `scan`, `fill` | Verifica `EXCaaaa-nnnnn-ddd-TIPO-vv` (ficheiros) e `EXCaaaa-nnnnn/ddd/TIPO/vv` (referências). Desvio = **aviso**, nunca erro (documentos de terceiros não seguem o padrão). |
| **Veredicto esperado do IES** | PE/03 | `fill` | `NO_FAVORABLE` se houver Crítico Abierto; senão `FAVORABLE`. Importantes abertos contam-se em bruto (sem limiar arbitrário — o PE/03 não quantifica "número significativo"). Punto sem estado conta como Abierto. Vai à consola, às propriedades do `.xlsm` e, opcionalmente, a uma célula. Não bloqueia a geração. |
| **Estados legados** | PE/03 §8.4 | `harvest`, `model` | Enum oficial: `Abierto`/`Resuelto`/`Cerrado`. Estados antigos (`Controlado`→`Resuelto`, `Conforme`→`Cerrado`) são mapeados e o original preservado em `estado_legado`. `Cancelado` passa intacto (não tem equivalente PE/03 — decisão pendente do RE). |
| **Regra de ouro** | PE/03 | `model.lint` | Nenhum Crítico pode ficar Abierto num informe favorável — gera aviso. |
| **Anejo A.2** (módulo) | PE/05 | `anejo.py` | Gera a Base de No Conformidades a partir dos puntos, derivando datas/responsável dos diálogos. Campos não deriváveis ficam `(a preencher)` — nunca fabricados. Ainda não ligado a um comando do CLI. |

---

## 5. Estrutura do projeto.yaml

Ver `config/projeto_exemplo.yaml` para um exemplo completo comentado. Resumo:

```yaml
portada:
  titulo: "PROYECTO DE ..."
  referencia: "EXC2025-16126-1/002/LPA/05"   # padrão PE/05
  normativa: "Anexo I del Reglamento ..."
  evaluadores:
    - {nombre: "Miriam Romera (MRG)", rol: "Evaluador técnico (supervisada)"}

scope: "Torre Pacheco, L352, Balsicas"        # âncoras da obra (para o suggest)

versiones:
  - {rev: 1, fecha: 2026-01-12, descripcion: "Primera versión ..."}

documentos:
  - nombre: "Anejo 27. Estudio Previo Seguridad"
    firmado: "Si"
    estado: auto                              # "auto" => fórmula; ou "Cerrado"
    envios:
      - {referencia: "...", version: 6, fecha: 2026-02-03, autor: "UTE",
         envio: 2, fecha_envio: 2026-02-16}

puntos:
  - n: 1
    eval: "SM"
    documento: "Anejo 27. Estudio Previo Seguridad"
    ref_documento: "auto"                     # "auto" => VLOOKUP a Doc Evaluados
    punto: "Anexo I, 2.4.2"                    # requisito normativo
    valoracion: "Crítico"                      # Crítico/Importante/Informativo/Formal
    estado: "Abierto"                          # Abierto/Resuelto/Cerrado
    dialogo:
      - {tipo: "Hallazgo", texto: "..."}
      - {tipo: "Respuesta UTE (02/02/2026)", texto: "..."}
```

Chaves com prefixo `_` (`_triage`, `_fora_escopo`, `_score`, `_sugerido_de`) são
metadados de triagem — ignoradas pelo `fill`.

---

## 6. Módulos internos

| Módulo | Responsabilidade |
|---|---|
| `cli.py` | Interface de linha de comandos (argparse). |
| `model.py` | Carregar/validar o `projeto.yaml`, veredicto, lint, contagens. |
| `scan.py` | Catalogar documentos recebidos + triagem. |
| `filtro.py` | Classificar documentos avaliar/desviado/incerto (PE/01). |
| `nomenclatura.py` | Validar o padrão documental Exceltic (PE/05). |
| `docx_source.py` | Extrair metadados do PES `.docx`. |
| `harvest.py` | Construir a base CSV de hallazgos. |
| `suggest.py` | Matching determinístico de hallazgos. |
| `scope.py` | Deteção de contaminação entre obras (gazetteer + códigos). |
| `versiones.py` | Descrição das revisões (Control de Versiones). |
| `anejo.py` | Gerar a estrutura do Anejo A.2 (PE/05). |
| `filler.py` | Escrever o `.xlsm` final. |
| `styles.py`, `extensions.py` | Clonar estilos e preservar o que o openpyxl descarta. |
| `extract.py` | Reconstruir o YAML a partir do `.xlsm`. |

---

## 7. Testes

```bash
python -m pytest tests/
# ou, sem pytest, cada ficheiro corre isolado:
python tests/test_filtro.py
```

O teste de roundtrip do `fill` usa `examples/template_exemplo.xlsm`; se o
template não estiver presente, é ignorado (SKIP) em vez de falhar.
