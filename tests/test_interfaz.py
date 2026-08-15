"""Testes da janela (``interfaz.py``) com cliques reais.

Os botoes da interface sao ``tk.Label`` com um binding ``<Button-1>`` proprio,
nao ``tk.Button``. Chamar os metodos da aplicacao diretamente nao provaria que
esses bindings estao ligados, por isso aqui entrega-se um evento de rato de
verdade (``event_generate``) e verifica-se o efeito no ecra e no disco.

Se faltar Tkinter ou um ecra (servidor X, Wayland, sessao Windows), os testes
saltam sozinhos em vez de falhar: o motor em ``organizador/`` continua a ser
testado por ``test_organizador.py``, que nao precisa de nada disto.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

try:
    import tkinter as tk
except ImportError:  # pragma: no cover - depende da instalacao de Python
    tk = None


def _ha_ecra() -> bool:
    """Ha um ecra utilizavel? (nao ha em CI sem X, nem em SSH sem display)."""
    if tk is None:
        return False
    try:
        raiz = tk.Tk()
    except tk.TclError:
        return False
    raiz.destroy()
    return True


PRECISA_DE_ECRA = unittest.skipUnless(
    _ha_ecra(), "sem Tkinter ou sem ecra: a janela nao pode ser aberta aqui"
)


def descendentes(widget):
    """Todos os widgets abaixo de ``widget``, em profundidade."""
    for filho in widget.winfo_children():
        yield filho
        yield from descendentes(filho)


@PRECISA_DE_ECRA
class TestJanela(unittest.TestCase):
    ORIGINAIS = ("EXC2026-16883-001-PES-01.pdf", "EXC2026-16883-002-LPA-01.pdf",
                 "mediciones.xlsx", "foto obra.jpg")

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.base = Path(self._temp.name)
        self.pasta = self.base / "3_Doc Trabajo"
        self.pasta.mkdir()
        for nome in self.ORIGINAIS:
            (self.pasta / nome).write_text("x", encoding="utf-8")

        # Historico proprio deste teste: nunca tocar no do utilizador.
        anterior = os.environ.get("ORGANIZADOR_HISTORICO")
        os.environ["ORGANIZADOR_HISTORICO"] = str(self.base / "historico.json")
        self.addCleanup(self._repor_ambiente, anterior)

        import interfaz  # importado aqui: so existe se houver Tkinter

        self.interfaz = interfaz
        self.app = interfaz.App(str(self.pasta))
        self.addCleanup(self.app.destroy)
        self.app.update()

    @staticmethod
    def _repor_ambiente(anterior: str | None) -> None:
        if anterior is None:
            os.environ.pop("ORGANIZADOR_HISTORICO", None)
        else:
            os.environ["ORGANIZADOR_HISTORICO"] = anterior

    # ------------------------------------------------------------- utilidades
    def clicar(self, widget) -> None:
        """Entrega um clique de rato ao widget e deixa o Tk processa-lo."""
        widget.event_generate("<Button-1>", x=5, y=5)
        self.app.update_idletasks()
        self.app.update()

    def por_texto(self, raiz, texto, tipo=None):
        tipo = tipo or tk.Label
        for widget in descendentes(raiz):
            if isinstance(widget, tipo) and str(widget.cget("text")) == texto:
                return widget
        self.fail(f"nao ha nenhum {tipo.__name__} com o texto {texto!r} no ecra")

    def conteudo(self) -> list[str]:
        return sorted(p.name for p in self.pasta.iterdir())

    # ----------------------------------------------------------------- testes
    def test_clicar_numa_tarjeta_muda_o_criterio(self):
        self.assertEqual(self.app.criterio.get(), "tipo")
        self.clicar(self.por_texto(self.app.contenido, "Código de documento"))
        self.assertEqual(self.app.criterio.get(), "documento")

    def test_previsualizacao_nao_toca_no_disco(self):
        self.clicar(self.app.btn_primario)
        self.assertEqual(self.app.etapa, "previa")
        self.assertEqual(self.conteudo(), sorted(self.ORIGINAIS))

    def test_botao_secundario_volta_ao_formulario(self):
        self.clicar(self.app.btn_primario)
        self.clicar(self.app.btn_secundario)
        self.assertEqual(self.app.etapa, "form")

    def test_aplicar_move_e_desfazer_restaura(self):
        self.clicar(self.por_texto(self.app.contenido, "Código de documento"))
        self.clicar(self.app.btn_primario)   # previsualizar
        self.clicar(self.app.btn_primario)   # aplicar

        self.assertEqual(self.app.etapa, "resultado")
        self.assertEqual(self.conteudo(), ["001-PES", "002-LPA", "Sin código"])
        self.assertIsNotNone(self.app.ultimo_id)

        self.clicar(self.por_texto(self.app, "Ver historial y deshacer →"))
        self.assertEqual(self.app.operacion, "historial")

        self.clicar(self.por_texto(self.app.contenido, "Deshacer",
                                   self.interfaz.BotonPlano))
        self.assertEqual(self.conteudo(), sorted(self.ORIGINAIS))
        self.assertEqual(self.app.hist.listar(), [])
        # A operacao saiu do historico: o resultado nao pode dizer que ainda
        # se pode desfazer.
        self.assertIsNone(self.app.ultimo_id)

    def test_barra_lateral_abre_as_quatro_operacoes(self):
        for chave, _num, titulo, _desc in self.interfaz.OPERACIONES:
            with self.subTest(operacao=titulo):
                self.clicar(self.app.items_lateral[chave]["titulo"])
                self.assertEqual(self.app.operacion, chave)

    def test_pasta_inexistente_da_mensagem_em_espanhol(self):
        self.app.ruta.set(str(self.base / "no-existe"))
        self.clicar(self.app.btn_primario)

        self.assertEqual(self.app.etapa, "error")
        self.assertEqual(self.app.error["titulo"], "No se ha podido continuar")
        self.assertIn("no existe", self.app.error["texto"])
        # Erro esperado: nao se grava ficheiro de log nenhum.
        self.assertIsNone(self.app.error["log"])
        self.assertEqual(list(self.base.glob("ERROR_organizador_*.txt")), [])

    def test_criar_projeto_previsualiza_a_estrutura(self):
        self.clicar(self.app.items_lateral["proyecto"]["titulo"])
        self.app.ruta.set(str(self.base))
        self.app.v_nombre.set("Estación de Torre Pacheco (Apeadero)")
        self.app.v_codigo.set("16883")
        self.app.v_ano.set("2026")

        self.clicar(self.app.btn_primario)

        self.assertEqual(self.app.etapa, "previa")
        criadas = [destino for _origem, destino in self.app.previa["filas"]]
        self.assertIn("1_Oferta", criadas)
        self.assertIn(str(Path("2_Doc Recebida") / "mails"), criadas)
        self.assertIn(str(Path("4_Doc Generada") / "Doc"), criadas)
        # A carpeta do projeto nao conta como subpasta dela propria.
        self.assertEqual(self.app.previa["carpetas"], len(criadas) - 1)
        # E continua a ser so uma simulacao.
        self.assertFalse(any(p.name.startswith("2026-16883") for p in self.base.iterdir()))


if __name__ == "__main__":
    unittest.main()
