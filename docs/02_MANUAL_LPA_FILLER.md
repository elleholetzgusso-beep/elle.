# Manual do `lpa_filler`

Referência dos comandos. Pressupõe que já leste o `01_GUIA_LPA.md` — sobretudo a
parte dos três níveis, porque é ela que explica porque é que alguns destes comandos
se recusam a concluir o que parecem estar prestes a concluir.

O que o programa pode e não pode decidir sozinho está no `03_REGRAS_DE_AUTOMACAO.md`.

---

## 1. Instalação

```bash
pip install -e .
python -m pytest tests/          # confirmar que está tudo de pé
```

---

## 2. O fluxo

```text
PROJETO NOVO                          REVISÃO (ciclo de resposta)
────────────                          ──────────────────────────
scan      documentos recebidos        extract   LPA anterior → YAML
from-docx portada, do PES             scan      documentos do novo envío
merge     → projeto.yaml              update    acrescenta docs, preserva puntos
                                      verify    localiza a evidência citada
harvest   base histórica (1ª vez)     draft     rascunha a réplica  (opcional)
guide     ver a base organizada       ─── rever à mão: parecer + estado ───
leer      o que falta a cada doc      rev       nova linha de versões
radar     onde procurar
suggest   candidatos do histórico
─── rever à mão: escrever os puntos ───
fill      → LPA.xlsm
anejo     → Anejo A.2 (CSV)
```

---

## 3. Preparar a mesa

### `scan` — o que o cliente entregou

```bash
python -m lpa_filler scan -r "1_Doc Recibida" -o documentos.yaml
```

Percorre as pastas de envíos e monta a secção `documentos`. Triagem PE/01: ofertas,
acuses, cartas e comunicações são marcadas `desviado` (ficam em Doc Evaluados mas não
geram puntos); sinais fracos (acta, correo) ficam `incerto` e seguem no fluxo,
listados para revisão. Actas de *pruebas* FAT/SAT contam como avaliáveis.

| Opção | Para quê |
|---|---|
| `--group-by {file,folder}` | Agrupar por ficheiro ou por pasta |
| `--autor` | Autor por omissão dos envíos |
| `--estado` | Estado por omissão dos documentos |
| `--no-triage` | Desligar a triagem PE/01 |

### `from-docx` — a portada, a partir do PES

```bash
python -m lpa_filler from-docx -i EXC2026-16883-001-PES-01.docx -o meta.yaml
```

Extrai portada, avaliadores e documentos do relatório PES.

### `merge` — montar o projeto (projeto NOVO)

```bash
python -m lpa_filler merge -m meta.yaml -d documentos.yaml -o projeto.yaml \
    --solicitante "ADIF"
```

Recusa-se a correr se o ficheiro de saída já tiver puntos — apagá-los-ia. Para uma
revisão é o `update` que serve. `--force` passa por cima, se for mesmo isso que
queres.

O `--solicitante` é quem faz os envíos, e entra na descrição da versão. Varia por
projeto: ADIF, uma UTE, um consórcio.

### `update` — acrescentar documentos (REVISÃO)

```bash
python -m lpa_filler update -p projeto.yaml -d documentos.yaml
```

Acrescenta os documentos do novo envío **sem tocar nos puntos**.

### `rev` — a próxima linha do Control de Versiones

```bash
python -m lpa_filler rev -p projeto.yaml --solicitante "ADIF"
```

Deteta os envíos ainda não mencionados e compõe a descrição da revisão nova.

---

## 4. Perceber os documentos

### `harvest` — a memória histórica

```bash
python -m lpa_filler harvest -r "LPAs antigos" -o base_hallazgos.csv
python -m lpa_filler harvest -i LPA_A.xlsm LPA_B.xlsm -o base_hallazgos.csv
```

Extrai os hallazgos de LPAs já emitidos para um CSV — uma linha por hallazgo, com
documento, punto, valoración, estado, texto e proveniência. Acrescenta por omissão;
`--overwrite` reescreve. Estados legados são mapeados para o enum PE/03 preservando
o original em `estado_legado`.

> É um **CSV linha-a-linha**, não uma árvore agrupada por tema. Se vires diagramas em
> árvore num material de formação, são ilustração.

### `guide` — a base organizada

```bash
python -m lpa_filler guide -b base_hallazgos.csv -o base_organizada.xlsx
```

Por onde começar numa obra nova: a base agrupada e ordenada, para leitura humana.

### `leer` — o documento tem o que devia ter?

```bash
python -m lpa_filler leer -r "1_Doc Recibida" -o leitura.txt
```

Abre cada documento (`.docx`/`.pdf`/`.txt`), extrai o texto e corre um checklist
estrutural por tipo (Safety Case → 6 partes; REP → perigo/medida/estado; Plan de
Seguridad → gestión/ciclo de vida…). Assinala as normas CENELEC citadas.

**Ausência de uma palavra-chave nunca é uma não conformidade.** É nível 1: "olha aqui".

### `radar` — onde exatamente procurar

```bash
python -m lpa_filler radar -r "1_Doc Recibida" -b base_hallazgos.csv -o radar.txt \
    --excluir-obra EXC2026-16883
```

Cruza o conteúdo real de cada documento com a base histórica e diz onde procurar
erros: frentes por tipo de documento, mais sondas no texto, com proveniência e
localização. `--excluir-obra` evita colar da própria resposta. `--so-pistas` reduz a
saída ao que encontrou.

**Só aponta.** Não redige nem decide conformidade.

---

## 5. Propor candidatos

### `suggest`

```bash
# Modo projeto: pré-preenche 'puntos' com candidatos
python -m lpa_filler suggest -b base_hallazgos.csv -p projeto.yaml -o projeto.yaml \
    --scope "Torre Pacheco, L352" --min-score 12

# Modo consulta: imprime correspondências para um texto
python -m lpa_filler suggest -b base_hallazgos.csv -q "peligro sin estado de tratamiento"
```

| Opção | Para quê |
|---|---|
| `-n N` | Candidatos por documento (default 5) |
| `--min-score` | Limiar de força do match (default 8) |
| `--scope` | Âncoras da obra, para detetar contaminação de outras |
| `--valoracion` | Filtrar a base por valoración |
| `--replace` | Substituir os puntos em vez de acrescentar |
| `--debug` | Melhor score por documento — para calibrar o limiar |

Os hallazgos sugeridos são **texto histórico copiado**, não adaptado a esta obra. O
`suggest` não abre os documentos do projeto: casa nomes de documento com a base.
Rever e reescrever cada punto — e o seu `estado`, que sai sempre `Abierto` — é do
avaliador. Para ler o *conteúdo* dos ficheiros, `leer` e `radar`.

**Se der zero sugestões**, o comando diz porquê: ou a base já está toda no projeto,
ou nada chega ao limiar. `--debug` mostra o score de cada documento.

**Preenche `portada.referencia` antes de confiar no `--scope`.** É de lá que sai o
código desta obra; sem ele, um hallazgo que cite o relatório desta obra é marcado
`_fora_escopo` como se fosse de outra. O comando avisa quando isso acontece.

---

## 6. Ciclo de resposta

### `verify` — o que a resposta diz vs. o que o documento mostra

```bash
python -m lpa_filler verify -p projeto.yaml -r "Envío 3 20260601" -o verificacao.txt
```

Para cada punto aberto, lê a última *Respuesta* do diálogo, localiza o ficheiro (a
versão mais nova), abre-o e extrai o trecho real de cada apartado citado. Se houver
duas versões, resume o que mudou. Sinaliza citações a apartados que não existem.

**Traz a evidência. Não fecha hallazgos nem altera estados.**

### `draft` — rascunhar a Respuesta Exceltic

```bash
python -m lpa_filler draft -p projeto.yaml -r "Envío 3 20260601" -o projeto.yaml
```

Reutiliza o `verify` e escreve um rascunho factual da réplica: "localizei o apartado
X, diz Y; mudaram N linhas". Termina sempre em *pendiente de verificación y cierre por
el evaluador*, **não altera o estado**, e marca `[RASCUNHO]` + `_rascunho: true`.

É um scaffold, não um parecer. O `fill` avisa enquanto houver rascunho por rever.

---

## 7. Gerar os entregáveis

### `fill` — o LPA final

```bash
python -m lpa_filler fill -t template.xlsm -d projeto.yaml -o LPA.xlsm
python -m lpa_filler fill -t template.xlsm -d projeto.yaml -o LPA.xlsm \
    --veredicto-cell "Portada!B30" --strict
```

Preenche o template preservando macros, fórmulas, dropdowns e pivot tables. Calcula e
regista o veredicto esperado do IES.

`--strict` recusa gerar se algum punto estiver `Resuelto`/`Cerrado` sem o suporte que
o PE/03 §8.4 exige no diálogo. Sem a flag, os mesmos casos saem como avisos.

### `anejo` — a Base de No Conformidades (Anejo A.2)

```bash
python -m lpa_filler anejo -p projeto.yaml -o anejo_a2.csv
python -m lpa_filler anejo -p projeto.yaml -o anejo_rev05.csv --solo H-007 H-008 12
```

Indexado pelo `id` estável. `--asignar-ids` atribui os que faltem e grava-os no
projeto. `--solo` restringe a certos IDs (aceita `H-007`, `h-7` ou `7`); um ID
inexistente é erro e nada é escrito.

Aplica os mesmos descartes que o `fill`, para as duas vistas descreverem o mesmo
registo.

### `extract` — reconstruir o YAML

```bash
python -m lpa_filler extract -i LPA_existente.xlsm -o projeto.yaml
```

Para arrancar de um LPA legado. O `.xlsm` não tem coluna de `id`, por isso atribui
IDs novos por ordem — não serve para recuperar um projeto cujo YAML se perdeu com os
IDs lá dentro.

---

## 8. O `projeto.yaml`

É a fonte de verdade. O Excel é o que o programa monta a partir dele.

```yaml
portada:
  titulo: "PROYECTO DE ..."
  referencia: "EXC2026-16883/002/LPA/03"    # padrão PE/05 — preencher!
  normativa: "Anexo I del Reglamento ..."
  evaluadores:
    - {nombre: "Miriam Romera (MRG)", rol: "Evaluador técnico (supervisada)"}

scope: "Torre Pacheco, L352, Balsicas"       # âncoras da obra (para o suggest)

versiones:
  - {rev: 1, fecha: 2026-01-12, descripcion: "Primera versión ..."}

documentos:
  - nombre: "F3. Definición del Sistema (DS-REP)"
    firmado: "Si"
    estado: auto                             # "auto" => fórmula; ou "Cerrado"
    envios:
      - {referencia: "...", version: 6, fecha: 2026-02-03, autor: "ADIF",
         envio: 2, fecha_envio: 2026-02-16}

puntos:
  - id: "H-001"                              # identidade estável, atribuída uma vez
    n: 1                                     # nº de apresentação, renumera-se
    eval: "SM"
    documento: "F3. Definición del Sistema (DS-REP)"
    ref_documento: "auto"                    # "auto" => VLOOKUP a Doc Evaluados
    punto: "Andén 1 (vallado provisional)"   # o requisito ou elemento avaliado
    valoracion: "Importante"                 # Crítico/Importante/Informativo/Formal
    estado: "Abierto"                        # Abierto/Resuelto/Cerrado
    dialogo:
      - {tipo: "Hallazgo", texto: "..."}
      - {tipo: "Respuesta ADIF (13/07/2026)", texto: "..."}
      - {tipo: "Respuesta Exceltic (14/07/2026)", texto: "..."}
```

Chaves com prefixo `_` (`_triage`, `_fora_escopo`, `_score`, `_sugerido_de`,
`_rascunho`) são metadados de triagem, ignorados pelo `fill`.

O `id` é atribuído automaticamente por qualquer comando que escreva o projeto e não
se edita à mão.

---

## 9. Testes

```bash
python -m pytest tests/
```
