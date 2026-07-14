# lpa_filler — preenchimento automático do Excel padrão de LPA

Ferramenta reutilizável (Python) para automatizar o preenchimento do **Excel
padrão de projeto** — o *Listado de Puntos Abiertos* (LPA) da avaliação
independente de segurança (ISA) ferroviária.

A partir de um ficheiro de dados em YAML (e/ou das pastas de documentos
recebidos e do relatório PES de origem), gera o `.xlsm` final **preservando**:

- macros (VBA),
- fórmulas (`VLOOKUP`, `COUNTIFS`, propagação de estado),
- estilos, mesclas e formatação condicional por cor,
- *dropdowns* (validações de dados x14: Valoración / Estado),
- imagens (logótipo), PivotTable e gráfico de `Resumen Resultados`.

> O openpyxl, sozinho, descarta dropdowns, imagens e gráficos ao gravar. O
> módulo `extensions.preserve` repõe tudo isso a partir do template original.

## Instalação

```bash
pip install -r requirements.txt   # openpyxl, PyYAML
pip install python-docx           # só necessário para o comando from-docx
```

## Estrutura do projeto típico

```
2025-4263-1-PC POSADAS/
├── 1_Doc Recibida/
│   ├── Envío 1 20251126/.../   ← documentos recebidos (→ aba "Doc Evaluados")
│   ├── Envío 2 20260216/...
│   └── ...
├── 3_Doc Generada/Doc/
│   └── EXC...-PES-02.docx       ← relatório de origem (→ Portada/evaluadores)
└── FSP_GERADO.xlsm              ← Excel gerado
```

## Fluxo de trabalho

```bash
# 1) Gerar a lista de documentos avaliados a partir das pastas de envíos
#    --group-by folder: nombre = nome da pasta, referencia = nome do ficheiro
python -m lpa_filler scan -r "2025-4263-1-PC POSADAS/1_Doc Recibida" -o documentos.yaml
#    (use --group-by folder quando os ficheiros têm códigos longos dentro de pastas com nome)

# 2) (opcional) Extrair portada/evaluadores do relatório PES
python -m lpa_filler from-docx -i ".../EXC...-PES-02.docx" -o meta.yaml

# 3) Juntar scan + from-docx num projeto.yaml pronto a editar
python -m lpa_filler merge -m meta.yaml -d documentos.yaml -o projeto.yaml

# 4) Editar projeto.yaml e completar à mão os "puntos" (hallazgos),
#    que são juízo do avaliador (ver config/projeto_exemplo.yaml).

# 5) Gerar o Excel final
python -m lpa_filler fill -t template.xlsm -d projeto.yaml -o LPA_gerado.xlsm
```

Para arrancar de um LPA já existente (engenharia inversa para YAML):

```bash
python -m lpa_filler extract -i LPA_existente.xlsm -o projeto.yaml
```

## Comandos

| Comando     | O que faz                                                            |
|-------------|----------------------------------------------------------------------|
| `fill`      | Preenche o template `.xlsm` a partir do YAML de dados.               |
| `scan`      | Percorre `1_Doc Recibida/Envío N <AAAAMMDD>/` e gera `documentos`.   |
| `from-docx` | Extrai portada/evaluadores/documentos do relatório PES (`.docx`).    |
| `merge`     | Junta o `scan` + `from-docx` num `projeto.yaml` pronto a editar.     |
| `extract`   | Lê um `.xlsm` preenchido e reconstrói o YAML (bootstrap).            |
| `harvest`   | Extrai hallazgos de LPAs existentes para uma base de dados (CSV).    |
| `suggest`   | Sugere hallazgos da base para um novo LPA (documento/requisito/texto).|

## Formato do ficheiro de dados

Ver [`config/projeto_exemplo.yaml`](config/projeto_exemplo.yaml) para um exemplo
completo e comentado. Secções: `portada`, `versiones`, `documentos`, `puntos`.

Convenções úteis:

- `ref_documento: auto` num punto → gera a fórmula `VLOOKUP` à aba *Doc Evaluados*.
- `estado: auto` num documento → gera a fórmula `COUNTIFS` que lê o estado do LPA.
- `categoria: Planos` num documento → agrupa vários documentos sob o mesmo nome
  na coluna A (ex.: a categoria "Planos" com vários planos por baixo).
- `dialogo` de um punto → primeira linha é o *Hallazgo*; as seguintes são as
  respostas (UTE / Exceltic), cada uma numa linha do bloco.

## Notas

- A aba **Resumen Resultados** (PivotTable) atualiza-se automaticamente ao abrir
  o ficheiro no Excel (marcada com `refreshOnLoad`).
- Os *hallazgos* dependem do critério do avaliador; a ferramenta automatiza toda
  a parte mecânica (numeração, mesclas, fórmulas, estilos e contagens).
- Os documentos reais (template `.xlsm` e relatórios `.docx`) **não** são
  versionados no repositório (ver `.gitignore`); indica-os via `--template` /
  `--input`.
