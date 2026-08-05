# Guia do LPA — para quem nunca trabalhou com um

Este documento explica **o processo**: o que é um Listado de Puntos Abiertos, como
se escreve um hallazgo, e o que tem de existir para um punto poder fechar. Não fala
de comandos — isso é o `02_MANUAL_LPA_FILLER.md`. O que o programa pode e não pode
decidir sozinho está no `03_REGRAS_DE_AUTOMACAO.md`.

Todos os exemplos aqui são reais, de dois LPAs em fases opostas do seu ciclo:

| | |
|---|---|
| **EXC2025-16126-1/002/LPA/01** | Estación de Posadas (Córdoba), revisão **01**. 14 puntos, todos `Abierto`, todos com uma única linha de diálogo. É assim que um LPA nasce. |
| **EXC2026-16883-002-LPA-03** | Estación de Torre Pacheco, revisão **03**. 21 puntos, 20 `Cerrado` e 1 `Resuelto`. É assim que um LPA acaba. |

Nenhum exemplo foi inventado — se um parecer estranho ou incompleto, é porque a
realidade é assim.

---

## 1. O que é um LPA

O LPA é o registo onde a Exceltic acompanha os pontos que ficaram **pendentes durante
a avaliação** de um projeto, desde que são detetados até ao fecho.

```text
problema encontrado
        ↓
     HALLAZGO
        ↓
  cliente responde
        ↓
 avaliador verifica
        ↓
ABIERTO → RESUELTO → CERRADO
```

Não é uma lista de erros. É uma lista **viva**: cada linha é um assunto que fica em
acompanhamento até alguém demonstrar que está resolvido. O LPA tem de responder, para
cada punto: *o que foi encontrado, porque é um problema, onde está, o que o cliente
respondeu, o que o avaliador verificou, e porque foi ou não fechado.*

---

## 2. A anatomia de um punto

Este é o punto Nº 1 do LPA-03 de Torre Pacheco, tal como está no ficheiro:

| Campo | Conteúdo |
|---|---|
| Nº | 1 |
| Eval | SM |
| Documento | F3. Definición del Sistema (DS-REP) |
| Versión | v0.5 |
| Pto. | Andén 1 (vallado provisional; Anexo 5 Desviaciones) |
| Valoración | Importante |
| Estado | Cerrado |

E o diálogo, que é onde vive a história do punto:

> **Hallazgo** — El F3 no detalla el vallado provisional que impide el acceso de
> viajeros al andén 1 (altura, cálculo estructural, Anexo Nº5 del Informe de
> Desviaciones), medida de seguridad relevante ligada al peligro ID 47 del REP.
> Incluir una breve referencia en el F3 al vallado provisional del andén 1 y a su
> justificación (Anexo Nº5).
>
> **Respuesta ADIF (13/07/2026)** — en el apartado b. Funciones y elementos del
> sistema, dentro de la descripción de "Estación de Torre Pacheco (Apeadero)"
> (página 17 del F3) se añade el siguiente párrafo: "Este cerramiento se compone […]"
>
> **Respuesta Exceltic (14/07/2026)** — Se comprueba en la pag 18 y se da por cerrado
> el hallazgo.

Três coisas a reter deste exemplo:

**O cliente não se chama "UTE".** Aqui é a **ADIF**. Noutros projetos é uma UTE, um
consórcio, uma empresa. A linha do diálogo é `Respuesta <SOLICITANTE> (dd/mm/aaaa)`,
e o solicitante é do projeto, não um campo fixo do sistema. Se vires "UTE" num
exemplo, é só isso — um exemplo.

**Cada punto traz mais duas linhas de diálogo por preencher**, literalmente
`Respuesta ADIF (dd/mm/aaaa)` e `Respuesta Exceltic (dd/mm/aaaa)`, vazias. São espaço
do modelo para uma segunda volta de diálogo, se for preciso. **Não significam que se
está à espera de resposta** — aparecem em todos os puntos, incluindo os já fechados,
como este.

**O `Pto.` não é o número da página.** É o requisito ou o elemento em causa — aqui,
"Andén 1 (vallado provisional; Anexo 5 Desviaciones)". É por ele que se sabe *contra o
quê* o documento foi avaliado.

---

## 3. O que faz um hallazgo ser bom

Um hallazgo tem de permitir que outra pessoa perceba o problema **sem perguntar nada
ao avaliador** — meses depois, numa auditoria, com o avaliador noutro projeto.

❌ *Falta información en el F3.*

Genérico. Falta o quê? Onde? Porque é que isso é um problema?

✅ O hallazgo real do Nº 1, desmontado:

| Pergunta | O que o texto responde |
|---|---|
| **Onde?** | El F3 *(e o Pto. remete para o Anexo Nº5 do Informe de Desviaciones)* |
| **O quê?** | el vallado provisional que impide el acceso de viajeros al andén 1 |
| **Que falta?** | altura, cálculo estructural, Anexo Nº5 |
| **Porque importa?** | medida de seguridad relevante ligada al peligro ID 47 del REP |
| **O que fazer?** | Incluir una breve referencia en el F3 […] y a su justificación |

O "porque importa" é a parte que mais se esquece e a que mais falta faz. Sem ela, o
hallazgo parece uma questão de forma; com ela, vê-se que é uma medida de segurança
ligada a um perigo identificado.

---

## 4. O ciclo de vida

### 🔴 ABIERTO

O problema foi detetado e comunicado. É o estado inicial de todo o punto, e é onde
fica enquanto a resposta não chegar **ou** enquanto a resposta que chegou não for
suficiente.

Um LPA acabado de emitir é inteiramente assim. O de Posadas, revisão 01, tem 14
puntos, **todos** `Abierto`, e cada um com uma só linha de diálogo — o hallazgo. Ainda
não há nada mais para haver.

O punto Nº 1 desse LPA:

| Campo | Conteúdo |
|---|---|
| Documento | Firmas documentación evaluada |
| Pto. | pestaña "Doc Evaluados" de este documento |
| Valoración | **Crítico** |
| Estado | **Abierto** |

> **Hallazgo** — Todos los documentos evaluados deben estar debidamente firmados (ver
> aquellos que figuran sin firmar en la pestaña "Doc Evaluados").

É um hallazgo curto porque o problema é simples de enunciar e a prova está no próprio
LPA — a aba "Doc Evaluados" mostra quais faltam. Curto não é o mesmo que vago: sabe-se
o que falta, onde ver, e é Crítico porque avaliar documentação não assinada põe em
causa tudo o resto.

> **ABIERTO não quer dizer "o cliente ainda não respondeu".** Pode haver resposta e o
> punto continuar aberto, se a resposta não resolver o problema. Em Posadas rev. 01
> ainda não houve resposta nenhuma; em revisões seguintes, um punto pode continuar
> aberto já com duas ou três voltas de diálogo em cima.

**Um problema transversal dá vários puntos, não um.** Ainda em Posadas, os puntos
Nº 4, 6, 8, 9 e 10 são todos Críticos sobre a mesma coisa — evidências do REP que não
correspondem ao perigo que dizem sustentar (planos de eletrificação citados em perigos
de drenagem, e por aí). Cada perigo é um punto próprio, porque cada um se resolve e
fecha por si. O Nº 9 é o que generaliza:

> De forma general, se incluye como evidencia los planos 8.1 y 8.2 en la mayoría de
> peligros, siendo estos planos referentes a electrificación. Revisar las evidencias
> de los peligros de forma general.

### 🟡 RESUELTO

O cliente respondeu **e** o avaliador aceitou a ação proposta — mas a execução ainda
não está comprovada.

Exemplo real, o Nº 20 de Torre Pacheco (o único em RESUELTO dos 21 puntos):

> **Hallazgo** — Queda pendiente de recepción las evidencias que son consideradas
> como Punto Pendiente y condición para la puesta en servicio. Se mantendrá abierta
> esta observación no bloqueante para el AsBo previo.
>
> **Respuesta ADIF (13/07/2026)** — Se enviarán
>
> **Respuesta Exceltic (14/07/2026)** — Las evidencias pendientes quedan gestionadas
> en el F6.1 como CPIT/CPE y el cierre depende de su entrega y validación antes de la
> puesta en explotación. Se mantiene abierto hallazgo no bloqueante para el AsBo previo.

Repara no que a resposta da Exceltic faz: **aceita o encaminhamento** (as evidências
ficam geridas no F6.1 como CPIT/CPE) e ao mesmo tempo **diz explicitamente de que
depende o fecho** (entrega e validação antes da entrada em exploração). É isso que
distingue RESUELTO de CERRADO — a ação está aceite, a prova ainda não chegou.

### 🟢 CERRADO

Além da aceitação, existe **evidência documental verificada pelo avaliador**.

No Nº 1 de Torre Pacheco (§2), a evidência é curta e localizável: *"Se comprueba en la
pag 18"*. Não é "o cliente diz que corrigiu" — é o avaliador a dizer onde foi ver.

Um exemplo mais difícil, o Nº 2 do mesmo LPA (Crítico, ciclo completo):

> **Hallazgo** — Peligro ID-299: falta de validación funcional de campo del pedal
> (traslado del pedal de Balsicas). La documentación disponible […] no acredita la
> validación.
>
> **Respuesta ADIF (13/07/2026)** — El traslado del pedal se realizará durante la TBA.
> En fase previa se ha aportado el protocolo de pruebas de concordancia
> "3AA-09599-AAAA-QHZZD-01P02_PPC__Pedal Balsicas SDC-LCP" y una vez realizado el
> traslado del pedal, se aportarán los resultados de las pruebas […]
>
> **Respuesta Exceltic (14/07/2026)** — Las evidencias EV.CMS-311.0, 312.0 y 316.0
> constan como disponibles solo en fase previa; se cierra el hallazgo, se queda
> pendiente de recepción de las evidencias de cierre tras el traslado.

Este fecho é uma decisão de avaliação, não uma dedução automática: fecha-se com as
evidências da fase prévia identificadas pelo código, deixando registado o que fica
pendente para depois do traslado. **A decisão é do avaliador e o registo explica-a** —
que é exatamente o que se exige a um fecho auditável.

---

## 5. Os três níveis

Esta é a moldura que atravessa tudo o resto, e a razão pela qual o programa se recusa
a fazer certas coisas:

```text
NÍVEL 1 — DETEÇÃO      🤖  "Encontrei uma pista."
              ↓            (o programa é forte aqui)
NÍVEL 2 — AVALIAÇÃO    👩‍💻  "Analisei, e isto é um hallazgo."
              ↓            (o programa ajuda; quem escreve é o avaliador)
NÍVEL 3 — DECISÃO      ⚖️  "Está Abierto / Resuelto / Cerrado."
                           (só o avaliador)
```

Um documento sem uma palavra-chave esperada **não é** uma não conformidade. Um
hallazgo histórico parecido **não é** um hallazgo desta obra. Um texto encontrado no
sítio que o cliente citou **não é** um fecho. São todos nível 1: pistas.

---

## 6. As dez regras

1. **Um hallazgo tem de ser rastreável.** Documento → apartado → requisito → problema.
2. **"Falta información" não é um hallazgo.** Qual informação, e porque é que falta importa.
3. **ABIERTO não significa que o cliente não respondeu.** Pode ter respondido e não chegar.
4. **Resposta do cliente ≠ CERRADO.** A resposta é uma promessa; o fecho precisa de prova.
5. **RESUELTO ≠ CERRADO.** RESUELTO é a ação aceite; CERRADO é a execução comprovada.
6. **Nunca fechar pelo que o cliente diz.** Fechar pelo que o avaliador verificou.
7. **Uma sugestão histórica não é uma não conformidade.** É um candidato a rever.
8. **Um radar não dá veredito.** Diz onde procurar.
9. **A evidência tem de ser localizável.** Documento + versão + apartado.
10. **A decisão final é do avaliador.** Sempre, e sem exceção prevista.

---

## 7. Onde entra o programa

O `lpa_filler` automatiza o trabalho à volta do LPA — organizar o que o cliente
entregou, dizer onde procurar, propor candidatos do histórico, localizar a evidência
que a resposta cita, montar o Excel final. Não avalia e não decide estados.

Os comandos estão no `02_MANUAL_LPA_FILLER.md`. Os limites — o que ele bloqueia, o
que se recusa a inventar, e porquê — no `03_REGRAS_DE_AUTOMACAO.md`.
