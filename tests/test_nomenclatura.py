"""Testes da validação de nomenclatura Exceltic (PE/05)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lpa_filler import nomenclatura  # noqa: E402


def test_filenames_validos():
    for s in [
        "EXC2025-00001-001-LPA-01",
        "EXC2024-03868-001-PES-01",
        "EXC2025-16126-1-001-PES-02",
        "EXC2026-16883-12-003-IES-01",
    ]:
        assert nomenclatura.check_filename(s) is None, s


def test_filenames_invalidos_geram_aviso():
    for s in [
        "EXC2025-00001-001-LPA-1",      # versão com 1 dígito
        "EXC2025-00001-LPA-01",          # falta nº do documento
        "EXC25-00001-001-LPA-01",        # ano com 2 dígitos
        "EXC2025-00001-001-lpa-01",      # tipo em minúsculas
    ]:
        motivo = nomenclatura.check_filename(s)
        assert motivo and "PE/05" in motivo, s


def test_terceiros_nao_geram_aviso():
    assert nomenclatura.check_filename("Anejo 27. Estudio Previo Seguridad_v06") is None
    assert nomenclatura.check_referencia("UTE-DOC-0001") is None


def test_referencias_validas_e_invalidas():
    assert nomenclatura.check_referencia("EXC2025-16126-1/002/LPA/05") is None
    assert nomenclatura.check_referencia("EXC2025-16126/002/LPA/05") is None
    assert nomenclatura.check_referencia("EXC2025-16126-1/002/LPA/5") is not None
    assert nomenclatura.check_referencia("EXC2025-16126-1-002-LPA-05") is not None  # separador errado


def test_avisos_documentos_deduplicados():
    docs = [
        {"nombre": "A", "envios": [
            {"referencia": "EXC2025-1-001-LPA-01"},   # nº de projeto curto demais
            {"referencia": "EXC2025-1-001-LPA-01"},   # repetido -> 1 aviso só
            {"referencia": "Anejo 3_v02"},            # terceiro -> sem aviso
        ]},
    ]
    avisos = nomenclatura.avisos_documentos(docs)
    assert len(avisos) == 1


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    sys.exit(1 if failed else 0)


def test_lpa_mais_recente_entre_os_recebidos_denuncia_uma_revisao():
    """Portada em LPA/01 com um LPA-18 desta obra nos documentos recebidos.

    É uma revisão disfarçada de projeto novo. O merge monta o projeto de raiz e
    os puntos das 17 revisões anteriores desaparecem sem que nada o diga.
    """
    docs = [
        {"nombre": "EXC2025-02703-6-002-LPA-18", "envios": [
            {"referencia": "EXC2025-02703-6-002-LPA-18"}]},
        {"nombre": "F09A REP", "envios": [{"referencia": "24-30-V-F09A-REP-VLC-SUD-V1.0"}]},
    ]
    aviso = nomenclatura.aviso_revisao_anterior("EXC2025-02703-6/002/LPA/01", docs)
    assert aviso and "LPA-18" in aviso
    assert "Revisión de un LPA ya existente" in aviso


def test_sem_lpa_anterior_nao_ha_aviso():
    docs = [{"nombre": "F09A REP", "envios": [{"referencia": "24-30-V-F09A-REP-VLC-SUD-V1.0"}]}]
    assert nomenclatura.aviso_revisao_anterior("EXC2025-02703-6/002/LPA/01", docs) is None


def test_o_proprio_lpa_da_mesma_revisao_nao_dispara():
    # Receber de volta a revisão que se está a emitir não é sinal de nada.
    docs = [{"nombre": "EXC2025-02703-6-002-LPA-01", "envios": []}]
    assert nomenclatura.aviso_revisao_anterior("EXC2025-02703-6/002/LPA/01", docs) is None


def test_lpa_de_outra_obra_nao_dispara():
    docs = [{"nombre": "EXC2026-16883-002-LPA-09", "envios": []}]
    assert nomenclatura.aviso_revisao_anterior("EXC2025-02703-6/002/LPA/01", docs) is None


def test_nome_ficheiro_a_partir_da_referencia():
    assert (nomenclatura.nome_ficheiro("EXC2025-16126-1/002/LPA/05", ".xlsm")
            == "EXC2025-16126-1-002-LPA-05.xlsm")


def test_nome_ficheiro_none_quando_referencia_nao_segue_o_padrao():
    assert nomenclatura.nome_ficheiro("PREENCHER: ex. EXC.../002/LPA/01", ".xlsm") is None
    assert nomenclatura.nome_ficheiro("", ".xlsm") is None
