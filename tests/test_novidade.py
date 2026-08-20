"""Testes do que conta como 'novo' entre o LPA anterior e o projeto atual."""
from lpa_filler import novidade


def test_sem_anterior_nada_e_novo():
    # LPA-01: não há com que comparar, por isso nada se destaca.
    data = {"puntos": [{"id": "H-001", "dialogo": [{"tipo": "Hallazgo", "texto": "X"}]}]}
    assert novidade.calcular(data, None) == novidade.vazio()


def test_punto_inteiro_novo():
    anterior = {"puntos": [{"id": "H-001", "dialogo": []}]}
    data = {"puntos": [
        {"id": "H-001", "dialogo": []},
        {"id": "H-002", "dialogo": [{"tipo": "Hallazgo", "texto": "Novo"}]},
    ]}
    n = novidade.calcular(data, anterior)
    assert n["puntos_novos"] == {"H-002"}
    # Um punto inteiramente novo não precisa de granularidade no diálogo.
    assert "H-002" not in n["dialogos_novos"]


def test_resposta_nova_num_punto_que_ja_existia():
    anterior = {"puntos": [{"id": "H-001", "dialogo": [
        {"tipo": "Hallazgo", "texto": "Falta X"},
        {"tipo": "Respuesta ADIF", "texto": "Corregido"},
    ]}]}
    data = {"puntos": [{"id": "H-001", "dialogo": [
        {"tipo": "Hallazgo", "texto": "Falta X"},
        {"tipo": "Respuesta ADIF", "texto": "Corregido"},
        {"tipo": "Respuesta Exceltic", "texto": "Verificado, se cierra"},
    ]}]}
    n = novidade.calcular(data, anterior)
    assert n["puntos_novos"] == set()
    assert n["dialogos_novos"] == {"H-001": {2}}   # só a linha índice 2 (a nova)


def test_dialogo_sem_alteracoes_nao_marca_nada():
    igual = {"puntos": [{"id": "H-001", "dialogo": [{"tipo": "Hallazgo", "texto": "X"}]}]}
    n = novidade.calcular(igual, igual)
    assert n["puntos_novos"] == set()
    assert n["dialogos_novos"] == {}


def test_documento_novo_e_envio_novo_em_documento_antigo():
    anterior = {"documentos": [
        {"nombre": "F3", "envios": [{"envio": 1, "referencia": "F3-v1", "version": 1}]},
    ]}
    data = {"documentos": [
        {"nombre": "F3", "envios": [
            {"envio": 1, "referencia": "F3-v1", "version": 1},
            {"envio": 2, "referencia": "F3-v2", "version": 2},
        ]},
        {"nombre": "F7", "envios": [{"envio": 2, "referencia": "F7-v1", "version": 1}]},
    ]}
    n = novidade.calcular(data, anterior)
    assert n["documentos_novos"] == {"F7"}
    assert n["envios_novos"] == {"F3": {1}}         # só o segundo envío (índice 1)


def test_versao_nova_no_control_de_versiones():
    anterior = {"versiones": [{"rev": 1, "descripcion": "Primera"}]}
    data = {"versiones": [
        {"rev": 1, "descripcion": "Primera"},
        {"rev": 2, "descripcion": "Segunda, con el envío 44"},
    ]}
    n = novidade.calcular(data, anterior)
    assert n["versiones_novas"] == {2}


def test_projeto_vazio_nao_rebenta():
    assert novidade.calcular({}, {}) == novidade.vazio()
    assert novidade.calcular({"puntos": []}, {"puntos": []}) == novidade.vazio()
