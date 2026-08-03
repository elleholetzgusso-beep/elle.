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
pip install -e '.[pdf]'     # + leitura de .pdf nos comandos leer/verify (pypdf)
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
                      │
              (a UTE responde e reenvia documentos)
                      │
                verify │  (abre os ficheiros novos, localiza o que a
                      ▼   resposta cita, faz diff entre versões)
              relatório de verificação  →  avaliador fecha/mantém
```

`leer` (opcional, no arranque) lê os documentos recebidos e corre um checklist
estrutural por tipo — um radar para o avaliador antes de redigir os hallazgos.

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
(migração reversível — ver §4). Cada hallazgo recebe também uma coluna `tema`
com as áreas RAMS/CENELEC que menciona (Hazard Log, Safety Case, SRAC, ...) —
ver §4.

### `guide` — base organizada (por onde começar numa obra nova)
Exporta a base de hallazgos num `.xlsx` de trabalho com duas vistas: uma aba
**"Por onde começar"** com as contagens por tipo de documento e por tema RAMS,
ordenadas por gravidade (Críticos primeiro), e uma aba **"Hallazgos"** filtrável
(ordenada por tipo → valoración → tema, colorida por valoración).

```bash
python -m lpa_filler guide -b base_hallazgos.csv -o base_organizada.xlsx
```

Serve para, ao arrancar uma obra nova, ver onde historicamente aparecem os
achados graves (ex.: REP/Hazard Log e V&V costumam concentrar Críticos) e por
onde começar a avaliar. O tipo de documento é derivado do nome por regras
(generaliza entre obras); o tema vem da coluna `tema` da base (ou é classificado
na hora se faltar).

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

### `merge` — montar o projeto.yaml (projeto NOVO)
Junta a saída do `scan` e do `from-docx` num `projeto.yaml` pronto a editar
(secção `puntos` vazia — preenche-se à mão ou com o `suggest`).

```bash
python -m lpa_filler merge -m meta.yaml -d documentos.yaml -o projeto.yaml \
    --solicitante "UTE ESTEYCO-ARDANUY"
```

⚠️ O `merge` cria um projeto **novo** (zera os `puntos`). Se o `-o` já existir e
tiver puntos (ex. saiu de um `extract` numa revisão), recusa sobrescrever — para
não apagar os hallazgos em silêncio. Numa revisão usa-se o `update` (ver abaixo);
`--force` ignora a trava.

### `update` — acrescentar documentos a um projeto (REVISÃO)
Numa revisão (já existe LPA anterior), o `extract` recupera os puntos + versiones
+ documentos do LPA anterior. O `update` acrescenta os documentos do novo envío
(saída do `scan`) **sem tocar nos puntos**: documento já existente ganha só os
envíos novos (dedup por referência); documento novo é adicionado ao fim.

```bash
python -m lpa_filler extract -i EXC..-LPA-01.xlsm -o projeto.yaml   # 1. recupera o anterior
python -m lpa_filler scan -r "Envío novo" -o docs_novos.yaml        # 2. cataloga o envío novo
python -m lpa_filler update -p projeto.yaml -d docs_novos.yaml      # 3. mescla (puntos intactos)
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

### `leer` — ler os documentos recebidos (1º LPA)
Abre cada documento recebido (`.docx`/`.pdf`/`.txt`), extrai o texto e corre um
checklist estrutural por tipo (Safety Case → 6 partes; REP → perigo/medida/estado;
Plan de Seguridad → gestión/ciclo de vida...). Assinala as normas CENELEC citadas.

```bash
python -m lpa_filler leer -r "1_Doc Recibida" -o leitura.txt
```

Uma parte "não encontrada" (`✗`) é **pista para o avaliador olhar**, nunca uma não
conformidade: pode estar escrita com outras palavras, num anexo, ou o ficheiro ser
uma digitalização sem texto (precisa de OCR). O programa não julga conformidade.

### `verify` — verificar a resposta da UTE (ciclo de resposta)
Para cada punto ainda aberto, lê a última *Respuesta* do diálogo, localiza o
ficheiro do documento na pasta da resposta (a versão mais nova), abre-o e extrai o
trecho real de cada apartado citado. Se houver duas versões, resume o que mudou.

```bash
python -m lpa_filler verify -p projeto.yaml -r "Envío 3 20260601" -o verificacao.txt
```

Traz a evidência lado a lado com o que a resposta alega (trecho real, diff, e o que
não encontrou). **Não fecha hallazgos nem altera estados** — a decisão é do avaliador
(ISO 17020). Sinaliza quando a resposta cita um apartado que não existe no ficheiro.

### `draft` — rascunhar a réplica do avaliador (Respuesta Exceltic)
Para cada punto aberto com resposta do contratista, localiza nos ficheiros do novo
envío o apartado citado, extrai o trecho real + diff (reutiliza o `verify`) e escreve
um **rascunho** da Respuesta Exceltic com essa evidência.

```bash
python -m lpa_filler draft -p projeto.yaml -r "Envío 3 20260601" -o projeto.yaml
```

É um **scaffold, não um parecer**: o texto é factual ("localizei o apartado X, diz Y;
mudaram N linhas"), termina sempre em "pendiente de verificación y cierre por el
evaluador", **não altera o estado** e é marcado `[RASCUNHO]` + `_rascunho: true`. O
avaliador reescreve o parecer e define o estado à mão; o `fill` avisa enquanto houver
rascunho por rever. Nunca fecha um hallazgo — a responsabilidade ISO 17020 é do avaliador.

### Fluxo de revisão (ciclo de resposta), em resumo
```
extract  (do LPA-01_respuestas.xlsm — já traz Hallazgo + Respuesta do contratista)
   │
update   (acrescenta os documentos do novo envío; preserva puntos)
   │
draft    (rascunha a Respuesta Exceltic com a evidência dos ficheiros)   ← opcional
   │
(rever à mão: parecer + estado de cada punto)
   │
rev → fill   (LPA-02)
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
| **Classificação temática RAMS** | EN 50126/8/9 | `harvest`, `tema.py` | Etiqueta cada hallazgo com as áreas de segurança que menciona (Hazard Log/REP, Safety Case, SRAC, Análisis RAM, Software/SIL, V&V, Ciclo de vida, Interfaces). Coluna `tema` na base; sem palavra-chave, fica sem etiqueta (não força). Palavras-chave calibradas contra os 625 hallazgos reais. Glossário em `config/referencias_rams.yaml`. |
| **Leitura estrutural** | PE/02 | `leer`, `leer.py` | Extrai o texto dos documentos recebidos e verifica se as partes esperadas do tipo estão presentes (radar, não veredito). Ausência de palavra-chave nunca é não conformidade. |
| **Verificação da resposta** | PE/03 | `verify`, `verify.py` | Localiza nos ficheiros novos o apartado que a resposta cita e mostra o trecho real + diff entre versões. Traz a evidência; nunca fecha o hallazgo — decisão do avaliador. Sinaliza citações a apartados inexistentes. |
| **Rascunho da réplica** | PE/03 | `draft`, `draft.py` | Pré-preenche a Respuesta Exceltic com a evidência localizada (scaffold factual, não parecer). Termina em "pendiente de verificación", não altera estado, marca `[RASCUNHO]`. O `fill` avisa enquanto o rascunho não for revisto. O avaliador confirma — nunca o programa. |

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

> **Nota sobre o `suggest`:** os hallazgos sugeridos são **texto histórico copiado**
> da base (campo `hallazgo` do LPA de origem), não adaptado a esta obra. O `suggest`
> não abre os documentos do projeto — casa só nomes de documento com a base. Rever e
> reescrever cada punto (e o seu `estado`, que sai sempre `Abierto` por omissão) é do
> avaliador. Para ler o *conteúdo* dos ficheiros, usar `leer` e `verify`.

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
| `tema.py` | Classificação temática RAMS/CENELEC dos hallazgos. |
| `updater.py` | Mesclar documentos novos num projeto existente (revisão). |
| `lector.py` | Ler texto de `.docx`/`.pdf`/`.txt`; localizar apartados; diff de versões. |
| `leer.py` | Checklist estrutural dos documentos recebidos (1º LPA). |
| `verify.py` | Verificar a resposta da UTE contra os ficheiros novos. |
| `draft.py` | Rascunhar a réplica do avaliador (Respuesta Exceltic) com a evidência. |
| `guide.py` | Exportar a base num .xlsx organizado (por onde começar numa obra nova). |
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
