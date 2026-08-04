# Documentação do `lpa_filler`

A documentação está em três documentos, porque são três públicos diferentes e
misturá-los tornava difícil encontrar qualquer coisa.

### [`01_GUIA_LPA.md`](01_GUIA_LPA.md) — o processo
Para quem nunca trabalhou com um LPA. O que é, como se escreve um hallazgo, o ciclo
ABIERTO → RESUELTO → CERRADO, e o que tem de existir para um punto fechar. Exemplos
reais do EXC2026-16883-002-LPA-03.

**Começa por aqui**, mesmo que só queiras correr os comandos.

### [`02_MANUAL_LPA_FILLER.md`](02_MANUAL_LPA_FILLER.md) — a ferramenta
Referência dos comandos: instalação, `scan`, `leer`, `harvest`, `guide`, `radar`,
`suggest`, `verify`, `draft`, `merge`/`update`/`rev`, `fill`, `anejo`, `extract`, e a
estrutura do `projeto.yaml`.

### [`03_REGRAS_DE_AUTOMACAO.md`](03_REGRAS_DE_AUTOMACAO.md) — os limites
Para quem desenvolve ou audita o programa. O que está automatizado, o que está
deliberadamente **não** automatizado e porquê, os bloqueios, os módulos internos e as
invariantes.

---

A ideia que atravessa os três:

```text
NÍVEL 1 — DETEÇÃO      🤖  "Encontrei uma pista."
NÍVEL 2 — AVALIAÇÃO    👩‍💻  "Analisei, e isto é um hallazgo."
NÍVEL 3 — DECISÃO      ⚖️  "Está Abierto / Resuelto / Cerrado."  ← só o avaliador
```
