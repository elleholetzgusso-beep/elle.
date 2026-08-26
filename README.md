# Gerador de FSP — Exceltic

Gera automaticamente a **Ficha de Seguimiento del Proyecto (FSP)** a partir do
último LPA e das pastas do projeto (`1_ Doc Recibida`, `4_ Doc Generada`).

Agora tem **interface gráfica** (uma janela com botões) — já não é preciso a
linha de comandos.

---

## Como usar (o dia-a-dia)

1. Abre o programa (duplo-clique no `.exe` ou no `GerarFSP.bat`).
2. Clica em **Escolher pasta…** e seleciona a pasta do projeto.
3. Clica em **⚙ Gerar FSP**.
4. Quando aparecer *"✔ FSP gerado com sucesso"*, clica em **Abrir ficheiro
   gerado**. O ficheiro fica dentro da pasta do projeto, com o nome baseado na
   referência do projeto (ex.: `EXC2026-04019-000-FSP-01.xlsx`).

---

## Duas formas de o entregar ao Roberto

Como analogia: o script Python é uma *receita*. Podes dar a receita crua (`.bat`,
precisa da "cozinha" = Python instalado) ou uma *caixa fechada* pronta a usar
(`.exe`, não precisa de nada — mas às vezes o antivírus desconfia de caixas
fechadas desconhecidas).

### Opção A — `.exe` (recomendada para quem não tem Python)

O Roberto **não instala nada**. Recebe um único ficheiro `GerarFSP.exe` e clica.

**Tu** (uma vez, numa máquina Windows com Python) corres:

```
build_exe.bat
```

Isso cria `dist\GerarFSP.exe`. Copia esse ficheiro para o Roberto.
O template `FSP_template.xlsx` fica **dentro** do `.exe`; se quiseres poder
trocá-lo sem reconstruir, põe um `FSP_template.xlsx` ao lado do `.exe`.

> ⚠️ **Antivírus:** `.exe` criados com PyInstaller às vezes dão falso alarme.
> Se acontecer, usa a Opção B, ou assina o `.exe`, ou adiciona uma exceção no
> antivírus.

### Opção B — `.bat` (mais simples, mas precisa de Python)

O Roberto instala o **Python** uma vez
(<https://www.python.org/downloads/> — marcar **"Add Python to PATH"**).
Depois dá duplo-clique em **`GerarFSP.bat`**, que instala sozinho a
dependência (`openpyxl`) e abre a janela.

---

## Ficheiros

| Ficheiro            | Para quê                                                        |
|---------------------|-----------------------------------------------------------------|
| `app_fsp.py`        | A aplicação com a janela (interface gráfica).                    |
| `gerar_fsp.py`      | A lógica que lê o LPA e as pastas e escreve o FSP.               |
| `GerarFSP.bat`      | Atalho para abrir a app com Python (Opção B).                   |
| `build_exe.bat`     | Constrói o `GerarFSP.exe` (Opção A). Só o executas tu, uma vez.  |
| `FSP_template.xlsx` | Modelo do FSP (tem de estar presente para gerar).               |

---

## Requisitos para desenvolver

```
pip install openpyxl          # para correr
pip install pyinstaller       # só para construir o .exe
```

## A estética

A janela usa a **identidade Exceltic**: laranja `#F15722` sobre branco, tipo
Arial, régua laranja sob o cabeçalho e passos numerados. As cores estão em tokens
`COR_*` no topo de `app_fsp.py` — muda aí para ajustar a paleta. Os logótipos
estão em `assets/` (o `build_exe.bat` já os embute no `.exe`).
