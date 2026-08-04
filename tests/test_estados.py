"""Testes do ID estável e da máquina de estados do PE/Inspección/03 §8.4.

Duas garantias, ambas de rastreabilidade (ISO 17020):

  * o ``id`` de um hallazgo é atribuído uma vez e nunca muda — é ele que liga
    o mesmo punto entre a revisão 01 e a 05 do LPA, ao contrário do ``n``, que
    renumera sempre que se insere ou descarta um punto;
  * um estado só é válido se o diálogo contiver a prova que o justifica —
    verifica-se a PRESENÇA da prova, nunca o seu mérito (esse é do avaliador).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import model  # noqa: E402


def _dialogo(cliente: str = "", exceltic: str = "") -> list[dict]:
    d = [{"tipo": "Hallazgo", "texto": "Falta la columna de evidencias."}]
    if cliente:
        d.append({"tipo": "Respuesta UTE (02/02/2026)", "texto": cliente})
    if exceltic:
        d.append({"tipo": "Respuesta Exceltic (10/02/2026)", "texto": exceltic})
    return d


def _punto(estado="Cerrado", **kw):
    pt = {"n": 1, "valoracion": "Crítico", "estado": estado, "dialogo": _dialogo()}
    pt.update(kw)
    return pt


# --- ID estável -------------------------------------------------------------

def test_assign_ids_atribui_por_ordem_e_nao_reatribui():
    data = {"puntos": [{"n": 1}, {"n": 2}]}
    assert model.assign_ids(data) == ["H-001", "H-002"]
    # Segunda passagem: nada de novo, e os IDs existentes ficam intactos.
    assert model.assign_ids(data) == []
    assert [pt["id"] for pt in data["puntos"]] == ["H-001", "H-002"]


def test_id_nao_e_reutilizado_depois_de_apagar_um_punto():
    """Apagar o H-002 não faz o punto seguinte herdar o número: num registo de
    não conformidades auditável, um ID queimado não volta."""
    data = {"puntos": [{"n": 1}, {"n": 2}, {"n": 3}]}
    model.assign_ids(data)
    del data["puntos"][1]                       # sai o H-002
    data["puntos"].append({"n": 3})             # entra um punto novo
    assert model.assign_ids(data) == ["H-004"]
    assert [pt["id"] for pt in data["puntos"]] == ["H-001", "H-003", "H-004"]


def test_id_sobrevive_a_renumeracao_do_n():
    """O 'n' é apresentação: o drop_fora_de_escopo renumera-o, o 'id' não."""
    data = {"puntos": [
        {"n": 1, "dialogo": [{"tipo": "Hallazgo", "texto": "a"}], "_fora_escopo": True},
        {"n": 2, "dialogo": [{"tipo": "Hallazgo", "texto": "b"}]},
    ]}
    model.assign_ids(data)
    model.drop_fora_de_escopo(data)
    sobrevivente = data["puntos"][0]
    assert sobrevivente["n"] == 1 and sobrevivente["id"] == "H-002"


def test_veredicto_refere_os_criticos_pelo_id_estavel():
    data = {"puntos": [{"n": 7, "id": "H-003", "valoracion": "Crítico", "estado": "Abierto"}]}
    assert model.veredicto(data)["criticos_abiertos"] == ["H-003"]


# --- transições de estado (PE/03 §8.4) --------------------------------------

def test_abierto_nao_exige_nada_alem_do_hallazgo():
    assert model.check_transiciones({"puntos": [_punto(estado="Abierto")]}) == []


def test_resuelto_sem_resposta_do_cliente_e_sinalizado():
    probs = model.check_transiciones({"puntos": [_punto(estado="Resuelto")]})
    assert any("sem resposta do cliente" in p for p in probs)


def test_resuelto_sem_aceitacao_do_avaliador_e_sinalizado():
    pt = _punto(estado="Resuelto", dialogo=_dialogo(cliente="Se corrige en la v0.6."))
    probs = model.check_transiciones({"puntos": [pt]})
    assert any("sem aceitação da ação" in p for p in probs)
    assert not any("sem resposta do cliente" in p for p in probs)


def test_resuelto_com_resposta_e_aceitacao_passa():
    pt = _punto(estado="Resuelto",
                dialogo=_dialogo(cliente="Se corregirá.", exceltic="Se acepta la acción."))
    assert model.check_transiciones({"puntos": [pt]}) == []


def test_cerrado_exige_evidencia_alem_da_aceitacao():
    """A aceitação da ação basta para 'Resuelto'; o fecho precisa da prova de
    execução — senão o veredito do IES assenta num estado sem suporte."""
    sem_prova = _punto(dialogo=_dialogo(cliente="Se corregirá.", exceltic="Se acepta la acción."))
    assert any("sem evidência documental" in p
               for p in model.check_transiciones({"puntos": [sem_prova]}))

    com_prova = _punto(dialogo=_dialogo(cliente="Corregido en la v0.6, apartado 4.2.",
                                        exceltic="Verificado. Se cierra."))
    assert model.check_transiciones({"puntos": [com_prova]}) == []


def test_rascunho_do_draft_nao_conta_como_aceitacao():
    """A réplica automática do 'draft' é um scaffold, não um parecer confirmado."""
    pt = _punto(estado="Resuelto",
                dialogo=_dialogo(cliente="Se corregirá.", exceltic="[RASCUNHO] rever isto"))
    assert any("sem aceitação da ação" in p for p in model.check_transiciones({"puntos": [pt]}))


def test_problemas_de_transicao_aparecem_no_lint():
    avisos = model.lint({"puntos": [_punto(estado="Resuelto", id="H-009")]})
    assert any("H-009" in a and "sem resposta do cliente" in a for a in avisos)
