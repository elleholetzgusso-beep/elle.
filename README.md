# lpa_filler — Automatização de LPAs (Listado de Puntos Abiertos)

Ferramenta Python que automatiza a criação e gestão de documentos LPA — relatórios
de conformidade e segurança usados em avaliações ISA de projetos de infraestruturas
ferroviárias em Espanha (marco PE/Inspección/01–05, UNE-EN ISO/IEC 17020).

## Fluxo

| Comando | O que faz |
|---|---|
| `harvest` | Extrai hallazgos de LPAs históricos para uma base CSV reutilizável |
| `scan` | Cataloga documentos recebidos, agrupando por envío e detectando versionamento; filtra documentos não avaliativos (PE/01) |
| `from-docx` | Extrai metadados (título, código, evaluadores) do relatório PES |
| `merge` | Junta documentos + metadados num `projeto.yaml` pronto para editar |
| `suggest` | Propõe hallazgos históricos similares via matching determinístico (calibrar `--min-score`: um limiar baixo enche a LPA de achados de outras obras) |
| `radar` | Lê o conteúdo real de cada documento recebido e, cruzando-o com a base, instrui onde procurar erros (frentes históricas + sondas no texto, com procedência e localização) |
| `rev` | Gera automaticamente a descrição da próxima revisão (envíos novos) |
| `fill` | Gera o Excel final (`.xlsm`) com macros, fórmulas e pivot tables, e calcula o veredito esperado do IES |
| `extract` | Reconstrói `projeto.yaml` a partir de um LPA existente (bootstrap) |

## Uso

```bash
pip install -e .
python -m lpa_filler scan -r "1_Doc Recibida" -o documentos.yaml
python -m lpa_filler from-docx -i origem_PES.docx -o meta.yaml
python -m lpa_filler merge -m meta.yaml -d documentos.yaml -o projeto.yaml
python -m lpa_filler suggest -b base_hallazgos.csv -p projeto.yaml -o projeto.yaml --scope "Torre Pacheco, L352" --min-score 12
python -m lpa_filler radar -r "1_Doc Recibida" -b base_hallazgos.csv -o radar.txt --excluir-obra EXC2026-16883
python -m lpa_filler fill -t template.xlsm -d projeto.yaml -o LPA.xlsm
python -m lpa_filler anejo -p projeto.yaml -o anejo_a2.csv
```

## Convenções normativas

- Estados de hallazgo (PE/Inspección/03 §8.4): `Abierto` / `Resuelto` / `Cerrado`.
  Cada degrau exige que a prova exista no diálogo: `Resuelto` pede resposta do cliente
  e aceitação da ação pelo avaliador; `Cerrado` pede ainda evidência documental citada.
  O `fill` avisa; com `--strict` recusa gerar. Verifica-se a presença da prova, não o
  seu mérito — esse continua a ser juízo do avaliador.
- Cada punto tem um `id` estável (`H-001`, …) atribuído uma vez e nunca reutilizado:
  é ele que segue o mesmo hallazgo entre revisões, ao contrário do `n`, que renumera.
- Valoración: `Crítico` / `Importante` / `Informativo` / `Formal`.
- Regra de ouro: nenhum `Crítico` pode permanecer `Abierto` num informe favorable —
  o `fill` calcula e regista o veredito esperado (`FAVORABLE` / `NO_FAVORABLE`)
  sem bloquear a geração do ficheiro.
- Nomenclatura de documentos Exceltic (PE/05): `EXCaaaa-nnnnn-ddd-TIPO-vv`;
  desvios geram aviso, não erro (documentos de terceiros podem não seguir o padrão).

## Testes

```bash
python -m pytest tests/
```
