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

`radar` (opcional, no arranque) vai além do `leer`: cruza o **conteúdo real** de
cada documento recebido com a `base_hallazgos.csv`, instruindo *onde* procurar
erros naquele tipo de documento (frentes históricas + sondas no texto). É a ponte
que o `suggest` — que só casa nomes — não faz:

```
  Doc Recibida/  +  base_hallazgos.csv
        └──────────┬──────────┘
               radar │  (lê o texto, cruza com o histórico por tipo)
                     ▼
              radar.txt  →  o avaliador vê onde olhar e por quê, e redige
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
    --scope "Torre Pacheco, L352, Balsicas" --min-score 12

# Modo consulta: imprime correspondências para um texto
python -m lpa_filler suggest -b base_hallazgos.csv -q "perfilado de banqueta" -n 5
```

`--scope` ativa a deteção de contaminação entre obras: sugestões cujo texto
nomeia outra obra ficam marcadas `_fora_escopo` e afundadas na ordenação
(nunca apagadas). `--debug` mostra o melhor score por documento para calibrar
`--min-score`.

**Calibrar o `--min-score` é obrigatório, não opcional.** O score é
`3×(palavras em comum no nome do documento) + 2×(no punto) + 1×(no hallazgo)`.
Com um limiar baixo, basta uma palavra genérica ("informe", "plan") para colar
um hallazgo de outra obra a um documento desta — e uma LPA com dezenas de
Críticos sugeridos produz um veredito `NO_FAVORABLE` que é artefacto do ruído,
não da avaliação. O default é 8; o comando imprime a distribuição dos scores e
avisa quando demasiadas sugestões ficam perto do limiar. Sobe até só sobrar o
que reconheces como pertinente a esta obra.

### `radar` — onde procurar erros em cada documento (a ponte base ↔ conteúdo)
Enquanto o `suggest` só casa *nomes* de documento com a base, o `radar` **abre e
lê o conteúdo real** de cada documento recebido e cruza-o com o que a *sua* base
histórica diz que costuma falhar naquele tipo de documento. Para cada documento
emite:

- **Frentes de atenção** (da base): os temas RAMS onde aquele tipo de documento
  concentra achados, ordenados por gravidade (Críticos primeiro), com contagens
  reais (nº de obras, nº de Cerrados). Saem **uma vez por tipo**, no preâmbulo:
  são iguais para todos os documentos do mesmo tipo, e repeti-las por documento
  afogava as pistas reais em ruído;
- **Pistas no texto real**: sondas determinísticas (referência cruzada de anexos
  incoerente, coluna de Evidencias ausente, perigos sem estado/ID, ...) que só
  disparam quando (a) o sinal existe no texto e (b) a base apoia aquele tipo de
  achado para aquele tipo de documento — cada pista traz o *porquê* (contagens +
  exemplo com fonte) e o *onde* (o sinal encontrado);
- **Estrutura esperada** e **normas CENELEC** citadas (reusa o `leer`).

```bash
python -m lpa_filler radar -r "1_Doc Recibida" -b base_hallazgos.csv -o radar.txt
python -m lpa_filler radar -r "1_Doc Recibida" -b base_hallazgos.csv \
    --excluir-obra EXC2026-16883      # ao reavaliar uma obra já na base
python -m lpa_filler radar -r "1_Doc Recibida" -b base_hallazgos.csv --so-pistas
```

O relatório abre com um **resumo**: quantas pistas e em que documentos, e quais
os documentos de que não se extraiu texto (PDF escaneado ou grande demais) — são
esses que ficam por rever à mão ou por passar por OCR. `--so-pistas` omite a
lista final dos documentos lidos sem sinal específico.

`--excluir-obra` remove os hallazgos da própria obra da base, para que, ao correr
o radar numa obra **já presente** na base, ele instrua a partir das *outras*
obras e não "cole da própria resposta".

Um documento que caia em `tipo: Otros` não recebe sondas específicas. Se muitos
documentos de um envío caírem em `Otros`, o dicionário de tipos
(`guide.TIPOS`) não conhece a nomenclatura daquele cliente — acrescentar lá o
padrão é o que faz as sondas passarem a correr nesses documentos.

Como o `leer`, é um **radar, não um veredito**: cada pista diz "olhe aqui,
porque…"; nunca redige o hallazgo nem decide conformidade. A leitura e a decisão
são do avaliador (ISO 17020). Tudo determinístico e rastreável — nada é inventado:
sem sinal no texto ou sem apoio na base, a sonda cala-se.

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

Com `--strict`, o `fill` recusa gerar se algum punto estiver `Resuelto`/`Cerrado` sem
o suporte que o PE/03 §8.4 exige no diálogo (§4). Sem a flag, os mesmos casos saem
como avisos e o ficheiro é gerado à mesma.

```bash
python -m lpa_filler fill -t template.xlsm -d projeto.yaml -o LPA.xlsm --strict
```

### `anejo` — Base de Datos de No Conformidades (Anejo A.2)
Gera o registo de não conformidades que o PE/05 exige, derivado dos puntos: a ação
e o responsável saem da primeira resposta do cliente, a fecha de cierre da última
data do diálogo (só se o punto estiver `Cerrado`), e o resultado da verificação
mapeia o estado PE/03.

É indexado pelo `id` estável — é a coluna Nº do registo. Por isso recusa correr se
algum punto não tiver `id`; `--asignar-ids` atribui-os e **grava-os no projeto.yaml**
(um ID que só existisse no CSV mudava na próxima passagem, e não seria estável).

```bash
python -m lpa_filler anejo -p projeto.yaml -o anejo_a2.csv
# só as não conformidades novas desta revisão (aceita 'H-007', 'h-7' ou '7'):
python -m lpa_filler anejo -p projeto.yaml -o anejo_rev05.csv --solo H-007 H-008 12
```

Um ID pedido no `--solo` que não exista no projeto é **erro**, e nada é escrito: num
registo de compliance, um Anejo incompleto por engano de escrita é pior do que um
comando que se recusa a correr. O que não é derivável do diálogo sai `(a preencher)`,
nunca um valor plausível inventado — o comando conta quantas faltam **por campo**.

O `anejo` aplica os mesmos descartes que o `fill` (`model.preparar_emissao`): puntos
`_fora_escopo` e placeholders não entram, e o `n` é o da folha emitida. Correr os dois
a partir do mesmo `projeto.yaml` dá duas vistas coerentes do mesmo registo — se um
descartasse e o outro não, o Anejo descreveria uma obra diferente do LPA.

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
| **ID estável do hallazgo** | PE/03, ISO 17020 | `model.assign_ids` | Cada punto recebe um `id` (`H-001`, `H-002`, …) na primeira vez que o projeto é escrito, e nunca mais o perde. É o `id` — não o `n`, que renumera a cada inserção ou descarte — que liga o mesmo hallazgo entre a revisão 01 e a 05, e o que o veredicto cita. IDs não são reutilizados: apagar o H-007 não faz o seguinte passar a H-007. |
| **Transições de estado** | PE/03 §8.4 | `fill --strict`, `model.lint` | Um estado só vale se o diálogo contiver a prova que o justifica: `Resuelto` exige resposta do cliente **e** aceitação da ação pelo avaliador; `Cerrado` exige além disso evidência documental citada (versão, apartado, anexo, documento aportado). Verifica-se a **presença** da prova, nunca o seu mérito — esse é juízo do avaliador. Por omissão avisa; com `--strict` não gera o ficheiro. |
| **Anejo A.2** | PE/05 | `anejo`, `anejo.py` | Gera a Base de No Conformidades a partir dos puntos, derivando datas/responsável dos diálogos. Indexado pelo `id` estável (a coluna Nº do PE/05), com o `n` ao lado como referência cruzada para a folha do LPA. Campos não deriváveis ficam `(a preencher)` — nunca fabricados. |
| **Sugestões numa revisão** | — | `suggest` | Os puntos já no projeto são excluídos da base **antes** do corte aos `-n` melhores por documento, para não gastarem as vagas. Sem isto, uma revisão (onde o projeto já tem os melhores matches da passagem anterior) devolvia sempre zero sugestões. |
| **Coerência entre entregáveis** | PE/03, PE/05 | `model.preparar_emissao` | O `fill` e o `anejo` são duas vistas do mesmo registo, por isso passam pelo mesmo funil de descartes (`_fora_escopo`, placeholders) e pela mesma renumeração. Qualquer comando novo que produza um entregável a partir dos puntos tem de chamar esta função — se dois emissores filtrarem de maneira diferente, passam a descrever obras diferentes. |
| **Classificação temática RAMS** | EN 50126/8/9 | `harvest`, `tema.py` | Etiqueta cada hallazgo com as áreas de segurança que menciona (Hazard Log/REP, Safety Case, SRAC, Análisis RAM, Software/SIL, V&V, Ciclo de vida, Interfaces). Coluna `tema` na base; sem palavra-chave, fica sem etiqueta (não força). Palavras-chave calibradas contra os 625 hallazgos reais. Glossário em `config/referencias_rams.yaml`. |
| **Leitura estrutural** | PE/02 | `leer`, `leer.py` | Extrai o texto dos documentos recebidos e verifica se as partes esperadas do tipo estão presentes (radar, não veredito). Ausência de palavra-chave nunca é não conformidade. |
| **Radar dirigido** | PE/02–03 | `radar`, `radar.py` | Cruza o conteúdo real de cada documento com a base histórica: instrui onde procurar erros (frentes por tipo de documento + sondas no texto, com procedência e localização). Só aponta; nunca redige nem decide conformidade. `--excluir-obra` evita colar da própria resposta. |
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
  - id: "H-001"                               # identidade estável, atribuída uma vez
    n: 1                                      # nº de apresentação, renumera-se
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

> **Nota sobre o `id`:** é atribuído automaticamente por qualquer comando que escreva
> o projeto (`merge`, `update`, `suggest`, `extract`, …) e não deve ser editado à mão.
> Vive no `projeto.yaml`, que é a fonte de verdade: o `.xlsm` gerado não tem coluna de
> `id`, por isso um `extract` a partir de um Excel atribui IDs novos por ordem — usa-o
> para arrancar de um LPA legado, não para recuperar o projeto.

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
| `suggest.py` | Matching determinístico de hallazgos (por nome de documento). |
| `radar.py` | Cruza o conteúdo real de cada documento com a base: frentes históricas por tipo + sondas no texto (a ponte que o `suggest` não faz). |
| `scope.py` | Deteção de contaminação entre obras (gazetteer + códigos). |
| `tema.py` | Classificação temática RAMS/CENELEC dos hallazgos. |
| `updater.py` | Mesclar documentos novos num projeto existente (revisão). |
| `lector.py` | Ler texto de `.docx`/`.pdf`/`.txt`; localizar apartados; diff de versões. |
| `leer.py` | Checklist estrutural dos documentos recebidos (1º LPA). |
| `verify.py` | Verificar a resposta da UTE contra os ficheiros novos. |
| `draft.py` | Rascunhar a réplica do avaliador (Respuesta Exceltic) com a evidência. |
| `guide.py` | Exportar a base num .xlsx organizado (por onde começar numa obra nova). |
| `versiones.py` | Descrição das revisões (Control de Versiones). |
| `anejo.py` | Gerar o Anejo A.2 — Base de No Conformidades (PE/05), indexado por ID. |
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
