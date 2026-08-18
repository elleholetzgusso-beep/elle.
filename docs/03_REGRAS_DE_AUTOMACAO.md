# Regras de automação — o que o programa pode e não pode decidir

Este documento é para quem desenvolve ou audita o `lpa_filler`. Diz o que está
automatizado, o que está deliberadamente **não** automatizado, e a justificação de
cada recusa. Uma recusa sem justificação escrita acaba por ser removida por alguém que
a toma por uma lacuna.

---

## A moldura: três níveis

```text
NÍVEL 1 — DETEÇÃO      🤖  "Encontrei uma pista."
              ↓            leer, radar, harvest, guide
NÍVEL 2 — AVALIAÇÃO    👩‍💻  "Analisei, e isto é um hallazgo."
              ↓            suggest, verify, draft — assistem; quem escreve é o avaliador
NÍVEL 3 — DECISÃO      ⚖️  "Está Abierto / Resuelto / Cerrado."
                           nenhum comando. Só o avaliador.
```

**Nenhum comando do `lpa_filler` altera o `estado` de um punto.** Não é um acaso da
implementação: é a fronteira do nível 3, e a responsabilidade é do avaliador
(ISO/IEC 17020). Qualquer proposta que implique um comando a fechar, reabrir ou
promover um punto está a atravessar esta linha, e a resposta por omissão é não.

---

## O que está automatizado

| Recurso | Procedimento | Onde | Comportamento |
|---|---|---|---|
| **Triagem de documentos não avaliativos** | PE/01 | `scan` | Ofertas, acuses, cartas, comunicações → `desviado` (ficam em Doc Evaluados, sem gerar puntos). Sinais fracos (acta, correo) → `incerto` (seguem no fluxo, listados para revisão). Actas de *pruebas* FAT/SAT são exceção técnica: contam como avaliáveis. Todo desvio regista o motivo. |
| **Validação de nomenclatura** | PE/05 | `scan`, `fill` | Verifica `EXCaaaa-nnnnn-ddd-TIPO-vv` (ficheiros) e `EXCaaaa-nnnnn/ddd/TIPO/vv` (referências). Desvio = **aviso**, nunca erro (documentos de terceiros não seguem o padrão). |
| **Veredicto esperado do IES** | PE/03 | `fill` | `NO_FAVORABLE` se houver Crítico Abierto; senão `FAVORABLE`. Punto sem estado conta como Abierto. Vai à consola, às propriedades do `.xlsm` e, opcionalmente, a uma célula. Não bloqueia a geração. |
| **Estados legados** | PE/03 §8.4 | `harvest`, `model` | Enum oficial: `Abierto`/`Resuelto`/`Cerrado`. Estados antigos (`Controlado`→`Resuelto`, `Conforme`→`Cerrado`) são mapeados e o original preservado em `estado_legado`. `Cancelado` passa intacto (não tem equivalente PE/03 — decisão pendente do RE). |
| **Regra de ouro** | PE/03 | `model.lint` | Nenhum Crítico pode ficar Abierto num informe favorável — gera aviso. |
| **ID estável do hallazgo** | PE/03, ISO 17020 | `model.assign_ids` | Cada punto recebe um `id` (`H-001`, …) na primeira escrita do projeto e nunca o perde. É o `id` — não o `n`, que renumera — que liga o mesmo hallazgo entre revisões. IDs não são reutilizados: apagar o H-007 não faz o seguinte passar a H-007. |
| **Transições de estado** | PE/03 §8.4 | `fill --strict`, `model.lint` | `Resuelto` exige resposta do cliente **e** aceitação da ação pelo avaliador; `Cerrado` exige além disso evidência documental citada. Verifica a **presença** da prova, nunca o mérito. Avisa por omissão; bloqueia com `--strict`. |
| **Coerência entre entregáveis** | PE/03, PE/05 | `model.preparar_emissao` | O `fill` e o `anejo` passam pelo mesmo funil de descartes e renumeração. Qualquer comando novo que produza um entregável tem de chamar esta função. |
| **Anejo A.2** | PE/05 | `anejo` | Base de No Conformidades derivada dos puntos, indexada pelo `id`. Campos não deriváveis ficam `(a completar)`. |
| **Deteção de contaminação de outra obra** | — | `suggest --scope` | Hallazgos que nomeiam outra obra e nenhuma âncora desta ficam `_fora_escopo` e afundados na ordenação. **Não são apagados** — o avaliador confirma ou remove a chave. |
| **Sugestões numa revisão** | — | `suggest` | Os puntos já no projeto são excluídos da base **antes** do corte aos `-n` melhores, para não gastarem as vagas. |
| **Classificação temática RAMS** | EN 50126/8/9 | `harvest`, `tema.py` | Etiqueta cada hallazgo com as áreas que menciona. Sem palavra-chave, fica sem etiqueta — não força. |
| **Leitura estrutural** | PE/02 | `leer` | Verifica se as partes esperadas do tipo estão presentes. Ausência de palavra-chave **nunca** é não conformidade. |
| **Extração insuficiente** | — | `leer`, `radar` | Documento cujo texto extraído fica abaixo de `lector.MIN_TEXTO_UTIL` é assinalado como provável digitalização a precisar de OCR. Sem isto passava por lido: o checklist dava tudo por ausente (como se faltassem partes ao documento, e não a leitura) e o radar dava-o "sem pistas", igual a um documento limpo. |
| **Revisão disfarçada de projeto novo** | PE/05 | `merge` | Se entre os documentos recebidos vier um LPA da própria obra com revisão superior à da portada, avisa. É o sinal de que o `merge` está a montar de raiz um projeto que já tem histórico — e os puntos das revisões anteriores desapareceriam sem nada o dizer. |
| **Radar dirigido** | PE/02–03 | `radar` | Cruza conteúdo real com a base histórica; instrui onde procurar. Só aponta. |
| **Verificação da resposta** | PE/03 | `verify` | Localiza o apartado citado e mostra o trecho real + diff. Traz a evidência; **nunca fecha**. |
| **Rascunho da réplica** | PE/03 | `draft` | Scaffold factual, termina em "pendiente de verificación", não altera estado, marca `[RASCUNHO]`. |

---

## O que está deliberadamente **não** automatizado

Cada linha aqui é uma recusa com razão. Antes de remover uma, é preciso responder à
razão — não basta achar que era conveniente ter.

### 1. Fechar, promover ou reabrir um punto

Nenhum comando escreve `estado`. O `verify` localiza a evidência e o `draft` redige o
rascunho, mas ambos param antes da decisão. Um programa que fechasse um punto por ter
encontrado texto no sítio citado estaria a confundir *"o documento mudou"* com *"a não
conformidade foi resolvida"* — que são coisas diferentes, e a diferença é o trabalho
do avaliador.

### 2. Julgar se uma evidência é suficiente

O `check_transiciones` verifica que existe **alguma** evidência citada antes de aceitar
um `Cerrado`. Não avalia se chega. A verificação é sobre a presença da prova, nunca
sobre o mérito.

### 3. Inventar um limiar para "demasiados Importantes"

O veredicto conta os Importantes abertos em bruto e não dispara nada a partir de um
número. O PE/03 não quantifica "número significativo", por isso qualquer limiar seria
inventado — e um número inventado num contexto de compliance é informação fabricada,
que é pior do que não ter número nenhum. A regra do Crítico existe porque está escrita;
esta não existe porque não está.

### 4. Preencher campos não deriváveis

O Anejo A.2 deixa `(a completar)` no que não sai do diálogo — a `fecha_deteccion`, por
exemplo, não existe em lado nenhum e sai sempre por preencher. Um valor plausível seria
indistinguível de um verdadeiro para quem lesse o registo depois.

### 5. Decidir a cláusula normativa violada

O `radar` e o `tema.py` apontam frentes e áreas temáticas. Não mapeiam
automaticamente cláusula ↔ documento nem preenchem o campo `punto`. Escolher o
requisito contra o qual algo é não conforme é o núcleo do juízo técnico — se quiseres
mais força de sugestão aqui, o caminho é mais sondas no `radar` e mais palavras-chave
no `tema.py`, não um motor que decide.

### 6. Desmarcar um `_fora_escopo`

O programa avisa quando um descarte por código de obra coincide com `portada.referencia`
por preencher (falso positivo provável), mas não inverte a marcação. Reclassificar é
correr o `suggest` de novo com a referência preenchida — e isso é decisão de quem
avalia.

### 7. Adaptar o texto de um hallazgo histórico

O `suggest` copia o texto da base tal e qual. Não o reescreve para a obra atual, e o
`estado` sai sempre `Abierto`. Um texto reescrito automaticamente pareceria redigido
pelo avaliador sem o ter sido.

---

## Bloqueios

Só há um bloqueio efetivo, e é opcional:

| Bloqueio | Como | Porquê opcional |
|---|---|---|
| `fill --strict` | Não gera o `.xlsm` se algum punto estiver `Resuelto`/`Cerrado` sem suporte no diálogo | A decisão de emitir assim mesmo é do avaliador. Sem a flag, sai como aviso. |

Tudo o resto avisa. A razão é a mesma em todos os casos: o programa não tem
informação para distinguir um erro de uma exceção legítima, e um bloqueio que se
contorna com uma flag ensina a usar a flag.

Dois erros **param** o comando, mas não são juízos técnicos — são proteções contra
perda de trabalho ou registo incompleto:

- `merge` sobre um projeto que já tem puntos (apagá-los-ia). `--force` passa.
- `anejo --solo` com um ID inexistente, ou sem `id` nos puntos. Nada é escrito.

---

## Módulos internos

| Módulo | Responsabilidade |
|---|---|
| `cli.py` | Interface de linha de comandos (argparse). |
| `pipeline.py` | Passos do fluxo para a janela: que comandos correr, e o que exigir antes de correr. |
| `gui.py` | Janela gráfica (tkinter). Monta e chama os comandos do `cli.py` — não sabe fazer mais nada. |
| `model.py` | Carregar/validar o `projeto.yaml`, IDs, veredicto, lint, transições, contagens. |
| `scan.py` | Catalogar documentos recebidos + triagem. |
| `filtro.py` | Classificar documentos avaliar/desviado/incerto (PE/01). |
| `nomenclatura.py` | Validar o padrão documental Exceltic (PE/05). |
| `docx_source.py` | Extrair metadados do PES `.docx`. |
| `harvest.py` | Construir a base CSV de hallazgos. |
| `suggest.py` | Matching determinístico de hallazgos (por nome de documento). |
| `radar.py` | Cruza o conteúdo real de cada documento com a base: frentes históricas por tipo + sondas no texto. |
| `scope.py` | Deteção de contaminação entre obras (gazetteer + códigos). |
| `tema.py` | Classificação temática RAMS/CENELEC dos hallazgos. |
| `updater.py` | Mesclar documentos novos num projeto existente (revisão). |
| `lector.py` | Ler texto de `.docx`/`.pdf`/`.txt`; localizar apartados; diff de versões. |
| `leer.py` | Checklist estrutural dos documentos recebidos (1º LPA). |
| `verify.py` | Verificar a resposta do cliente contra os ficheiros novos. |
| `draft.py` | Rascunhar a réplica do avaliador com a evidência. |
| `guide.py` | Exportar a base num `.xlsx` organizado. |
| `versiones.py` | Descrição das revisões (Control de Versiones). |
| `anejo.py` | Gerar o Anejo A.2 — Base de No Conformidades (PE/05), indexado por ID. |
| `gerar_fsp.py` | Ficha de Seguimiento de Proyecto. Ainda não ligado a um comando do CLI. |
| `filler.py` | Escrever o `.xlsm` final. |
| `styles.py`, `extensions.py` | Clonar estilos e preservar o que o openpyxl descarta. |
| `extract.py` | Reconstruir o YAML a partir do `.xlsm`. |

---

## Invariantes para quem desenvolve

1. **Todo o entregável passa por `model.preparar_emissao`.** Dois emissores com
   filtros diferentes descrevem obras diferentes. Já aconteceu: o Anejo saía com os
   hallazgos que o LPA descarta por serem de outra obra.
2. **Todo o punto escrito tem `id`.** A atribuição está em `_dump_yaml`, ponto único
   de escrita, e não em cada comando.
3. **O `n` é apresentação, o `id` é identidade.** Qualquer coisa que refira um punto
   entre revisões — veredicto, Anejo, mensagens — usa o `id`.
4. **O que não é derivável não é fabricado.** Fica por preencher, visivelmente.
5. **Nenhum comando escreve `estado`.**
6. **A janela não pode fazer o que a linha de comandos não faz.** O `gui.py`
   monta argumentos e chama o `cli.py`; não tem lógica própria. Um teste passa
   tudo o que a janela oferece pelo analisador de argumentos do CLI, para não se
   repetir o caso de uma opção que parecia existir e não existia.
