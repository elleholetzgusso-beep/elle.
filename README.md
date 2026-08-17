# Organizador de Carpetas y Proyectos — Exceltic

Ferramenta interna para criar pastas de projeto, registar envios de cliente
e organizar documentos. Distribuída ao Roberto (e à equipa) sem precisar de
Python instalado, linha de comandos ou permissões de administrador.

## Arquitetura

- **`organizador/`** — motor real (biblioteca Python pura, testada). Contém
  toda a lógica de criação de pastas, organização de ficheiros, histórico e
  desfazer. Tem também um CLI de desenvolvimento (`organizador/cli.py`,
  `python -m organizador --help`) usado só por mim para testar — mensagens
  aí continuam em português, porque o Roberto nunca o usa diretamente.
- **`interfaz.py`** — a janela (Tkinter), a versão que o Roberto usa hoje.
  Mesmo motor, sem linha de comandos: pede os dados, mostra **sempre** uma
  pré-visualização (`simular=True`) antes de aplicar seja o que for, e
  traduz qualquer falha para uma mensagem em espanhol. Não altera nenhuma
  lógica de criação, organização, histórico ou desfazer.
- **`lanzador.py`** — o mesmo programa em menu de consola, mantido como
  alternativa (é o que abre se o equipamento não conseguir mostrar a
  janela). Importa as funções do `organizador/` diretamente (não passa pelo
  `cli.py`). Todas as mensagens que podem chegar ao ecrã dele estão em
  espanhol — incluindo as lançadas pelas exceções do motor
  (`ErroDeCriacao`, `ErroDeOrganizacao`, `ErroDeProjeto`), que foram
  traduzidas na origem.
- **`Organizador_Exceltic_Ventana.bat`** — o que o Roberto abre (duplo
  clique ou arrastar uma pasta em cima). Abre a janela; se faltar Tkinter no
  Python portátil, cai sozinho para o menu de consola.
- **`Organizador_Exceltic.bat`** — a mesma ferramenta, sempre em consola.
  Chama `lanzador.py` com um Python portátil (embeddable), sem precisar
  instalar nada nem ter permissões de admin.
- **`Preparar_Tkinter.bat`** — corre-se **uma única vez**, a partir de um PC
  com Python instalado, para completar o `python-embed` com o Tkinter que o
  pacote *embeddable* não traz. Detalhes em `docs/INSTALACION_VENTANA.md`.
- **`assets/`** — `logo-mark.png` e `logo-lockup.png`. Se existirem, a janela
  mostra o logótipo; se não, mostra o nome em texto.
- **`LEEME.txt`** — instruções em espanhol para o Roberto (o único ficheiro
  de texto que ele deve ler).
- **`docs/`** — documentação que não vai para o `Y:\`:
  `INSTALACION_VENTANA.md` (como completar o `python-embed` com Tkinter) e
  `USO_CLI.md` (o CLI de desenvolvimento, `python -m organizador`).

### O que foi traduzido para espanhol e o que ficou intacto

Nomes de pasta que o programa **cria de raiz** (categorias em
`organizar --por tipo`: `Imágenes`, `Documentos`, `Hojas de cálculo`,
`Presentaciones`, `Vídeos`, `Comprimidos`, `Código`, `Fuentes`, `Diseño`,
`Otros`, `Sin extensión`; e os nomes dos meses em `--por data`) foram
traduzidos — confirmaste que não é convenção fixa.

A estrutura de projeto (`1_Oferta`, `2_Doc Recebida`, `2_Doc Recebida/mails`,
`3_Doc Trabajo`, `4_Doc Generada/Doc`, `Envío N AAAAMMDD`) **não foi tocada**
— é a convenção real usada nas pastas de obra existentes no `Y:\`.

## Distribuição

1. Copia esta pasta inteira (com `organizador/`, `interfaz.py`,
   `lanzador.py`, os três `.bat`, `assets/` e `LEEME.txt`) para uma pasta de
   rede, ex.: `Y:\Herramientas\OrganizadorExceltic\`.
2. Dentro dela, coloca uma pasta `python-embed\` com o
   [Python embeddable package](https://www.python.org/downloads/windows/)
   (ex.: `python-3.12.x-embed-amd64`, descompactado, renomeado para
   `python-embed`). Isto dá um Python portátil, sem instalação, sem admin.
   Não precisa de `pip` nem de bibliotecas externas — o programa só usa a
   biblioteca padrão. **Esta pasta não está no repositório** (são binários
   de Windows, ~22 MB); descarrega-se de python.org em cada preparação.
3. Corre `Preparar_Tkinter.bat` **uma vez**, a partir de um PC com Python
   instalado: copia o Tkinter que falta ao `python-embed`. Sem este passo o
   `.bat` da janela abre o menu de consola em vez da janela
   (ver `docs/INSTALACION_VENTANA.md`).
4. O Roberto acede pela unidade mapeada `Y:\` e corre
   `Organizador_Exceltic_Ventana.bat`.

Nunca distribuir por anexo de e-mail/Teams — além do peso, ficheiros `.bat`
e `.exe` vindos de anexo são bloqueados/quarentenados por padrão pela
maioria dos antivírus corporativos. A pasta de rede é o canal correto.

### Opção de reserva: `.exe` com PyInstaller

Se a pasta de rede não puder ter uma subpasta `python-embed\` (política de
TI, por exemplo), gera um executável autónomo:

```bash
pyinstaller --onedir --console --noupx --clean --name OrganizadorExceltic lanzador.py
```

- `--onedir` — gera uma **pasta** com o `.exe` + dependências, em vez de um
  único ficheiro. Um `.exe` "onefile" extrai-se para uma pasta temporária
  em cada execução, o que é exatamente o padrão que heurísticas de
  antivírus associam a droppers/trojans — `--onedir` reduz bastante os
  falsos positivos.
- `--console` — mantém a janela de consola aberta (o programa é interativo,
  com menu e `input()`; `--windowed` esconderia a janela e quebraria isso).
- `--noupx` — desativa a compressão UPX. Executáveis comprimidos com UPX são
  outro gatilho clássico de deteção heurística; sem UPX o `.exe` fica maior
  mas muito menos suspeito.
- `--clean` — limpa cache do PyInstaller antes de gerar (evita builds
  "sujos" com resíduos de uma versão anterior).
- `--name OrganizadorExceltic` — nome da pasta/executável final.

Resultado em `dist/OrganizadorExceltic/`. Distribui **a pasta inteira**
(não só o `.exe`) pela mesma unidade de rede, nunca por e-mail/Teams.

**Mesmo assim pode dar falso positivo.** Mitigação:
- Assinar o executável digitalmente, se a Exceltic tiver certificado
  (elimina a maioria dos avisos do Windows SmartScreen/Defender).
- Submeter o `.exe` ao [VirusTotal](https://www.virustotal.com) antes de
  distribuir; se algum motor acusar, pedir ao TI para o colocar em
  allowlist (hash do ficheiro) em vez de desativar o antivírus.
- Preferir sempre a opção `.bat` + `python-embed` — não é compilado, não
  soa a "executável desconhecido" para o antivírus, e é mais fácil de o TI
  inspecionar (é código Python legível, não um binário).

## Checklist antes de entregar ao Roberto

- [ ] `python -m unittest discover -s tests -v` — todos os testes a passar
      (62 testes: 48 do motor `organizador/` e 14 da
      janela — estes saltam se o PC não tiver Tkinter ou ecrã, confirma que
      dizem `ok` e não `skipped`).
- [ ] Correr `interfaz.py` no meu PC: as 4 operações da janela (organizar,
      novo projeto, envio, histórico/desfazer), sempre passando pela
      pré-visualização antes de aplicar.
- [ ] Correr `lanzador.py` no meu PC: as 4 operações do menu (organizar,
      novo projeto, envio, desfazer) e a opção "Salir".
- [ ] `Preparar_Tkinter.bat` corrido uma vez, e depois
      `Organizador_Exceltic_Ventana.bat` abre a janela (sem consola atrás).
      Sem esse passo, confirmar que o mesmo `.bat` cai no menu de consola em
      vez de dar erro.
- [ ] Testar arrastar uma pasta para cima de cada `.bat` (não só `python
      lanzador.py`) — confirma que o caminho chega limpo (sem aspas), que
      aparece já preenchido na janela e que o `chcp 65001` mostra acentos/ç
      corretamente na consola do Windows.
- [ ] Testar um erro esperado (pasta inexistente, pasta sem permissão de
      escrita) — mensagem em espanhol, sem traceback, janela não fecha
      sozinha.
- [ ] Forçar um erro inesperado (ex.: renomear temporariamente uma função
      interna) — confirma que grava o `.txt` de log junto ao resultado e
      que a mensagem pede para enviar o ficheiro.
- [ ] Confirmar que "Organizar" nunca sobrescreve — testar com um ficheiro
      já existente no destino e ver que fica `nome (1)`.
- [ ] Testar o critério **"Crear envíos por fecha"** numa `2_Doc Recebida`
      real: deve criar uma pasta `Envío N AAAAMMDD` por cada data distinta,
      numeradas por ordem cronológica e a continuar da maior já existente.
      **Atenção às datas**: usa a data de modificação. Se a cópia para o
      `Y:\` as tiver reposto para o dia da cópia, todos os documentos caem
      num único envio — a pré-visualização mostra isso antes de aplicar, mas
      convém olhar com atenção da primeira vez.
- [ ] Testar "Deshacer" logo a seguir a organizar/criar — confirma que
      volta ao estado anterior.
- [ ] **Testar numa máquina que não a minha** (idealmente a do Roberto ou
      outro colega): sem Python instalado, sem permissões de admin, a
      aceder por `Y:\`. Confirmar que o antivírus corporativo não bloqueia
      o `.bat` nem o `python-embed\python.exe`.
- [ ] Confirmar que o histórico (`~/.organizador-pastas/historico.json` no
      perfil do Windows do Roberto) persiste entre execuções, para o
      "Deshacer" funcionar mesmo depois de fechar e reabrir.
- [ ] Ler o `LEEME.txt` como se fosse o Roberto a abri-lo pela primeira vez
      — confirmar que chega para ele perceber o que fazer sem te perguntar.

## Testes automatizados

```bash
python -m unittest discover -s tests -v
```

São 62, em dois ficheiros:

- **`tests/test_organizador.py`** (48) — o motor. Não abre janela nenhuma,
  corre em qualquer sítio.
- **`tests/test_interfaz.py`** (14) — a janela, com **cliques reais**. Os
  botões da interface são `tk.Label` com um binding `<Button-1>` próprio (não
  `tk.Button`), por isso os testes entregam um evento de rato de verdade
  (`event_generate`) em vez de chamar os métodos por dentro: assim um binding
  mal ligado é apanhado. Verificam também o disco — aplicar move mesmo os
  ficheiros, desfazer põe-nos de volta, e a pré-visualização não toca em nada —
  e cobrem a rede de segurança global (`report_callback_exception`) e a
  separação entre ficheiros que falharam ao mover e os que já estavam no
  sítio.

Os testes da janela **saltam sozinhos** (`skipped`) se faltar Tkinter ou um
ecrã, em vez de falhar. Se quiseres corrê-los numa máquina sem ecrã (CI,
SSH), com um servidor X virtual:

```bash
xvfb-run -a python -m unittest discover -s tests -v
```
