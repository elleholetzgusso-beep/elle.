"""Testes do programa de criar e organizar pastas."""

from __future__ import annotations

import io
import contextlib
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from organizador import arrumador, criador, desfazer, historico, modelos, projetos
from organizador.cli import main


class BaseTemporaria(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.base = Path(self._temp.name)
        self.addCleanup(self._temp.cleanup)

    def criar_arquivo(self, caminho: str, conteudo: str = "x") -> Path:
        arquivo = self.base / caminho
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(conteudo, encoding="utf-8")
        return arquivo


class TestModelos(BaseTemporaria):
    def test_modelo_pronto_existe(self):
        pastas = modelos.obter_modelo("proyecto")
        self.assertIn("2_Doc Recebida/mails", pastas)
        self.assertIn("4_Doc Generada/Doc", pastas)

    def test_modelo_inexistente(self):
        with self.assertRaises(modelos.ErroDeModelo):
            modelos.obter_modelo("nao-existe")

    def test_texto_com_indentacao(self):
        texto = "Projeto\n    Documentos\n        2026\n    Imagens\nOutra\n"
        self.assertEqual(
            modelos.analisar_texto(texto),
            [
                "Projeto",
                "Projeto/Documentos",
                "Projeto/Documentos/2026",
                "Projeto/Imagens",
                "Outra",
            ],
        )

    def test_texto_ignora_comentarios(self):
        self.assertEqual(modelos.analisar_texto("# nada\nA\n\n  B # fim\n"), ["A", "A/B"])

    def test_json_aninhado(self):
        dados = {"A": {"B": {}, "C": ["D"]}}
        self.assertEqual(modelos.analisar_json(dados), ["A", "A/B", "A/C", "A/C/D"])

    def test_caminho_invalido(self):
        for ruim in ("../fora", "/absoluto", "  "):
            with self.assertRaises(modelos.ErroDeModelo):
                modelos.validar_caminho(ruim)

    def test_carregar_arquivo_json(self):
        arquivo = self.base / "estrutura.json"
        arquivo.write_text(json.dumps(["a", "a/b"]), encoding="utf-8")
        self.assertEqual(modelos.carregar_arquivo(arquivo), ["a", "a/b"])


class TestCriador(BaseTemporaria):
    def test_cria_estrutura_e_e_idempotente(self):
        destino = self.base / "novo"
        primeiro = criador.criar_estrutura(destino, ["a/b", "c"])
        self.assertTrue((destino / "a" / "b").is_dir())
        self.assertTrue((destino / "c").is_dir())
        self.assertEqual(len(primeiro.criadas), 4)  # novo, a, a/b, c

        segundo = criador.criar_estrutura(destino, ["a/b", "c"])
        self.assertEqual(segundo.criadas, [])
        self.assertEqual(len(segundo.existentes), 2)

    def test_simulacao_nao_toca_no_disco(self):
        destino = self.base / "simulado"
        resultado = criador.criar_estrutura(destino, ["x/y"], simular=True)
        self.assertFalse(destino.exists())
        self.assertEqual([p.name for p in resultado.criadas], ["simulado", "x", "y"])

    def test_conflito_com_arquivo(self):
        (self.base / "a").write_text("sou arquivo", encoding="utf-8")
        with self.assertRaises(criador.ErroDeCriacao):
            criador.criar_estrutura(self.base, ["a"])


class TestArrumador(BaseTemporaria):
    def test_organiza_por_tipo(self):
        self.criar_arquivo("foto.JPG")
        self.criar_arquivo("relatorio.pdf")
        self.criar_arquivo("planilha.xlsx")
        self.criar_arquivo("desconhecido.zzz")
        self.criar_arquivo("semextensao")

        resultado = arrumador.organizar(self.base, "tipo")

        self.assertTrue((self.base / "Imágenes" / "foto.JPG").is_file())
        self.assertTrue((self.base / "Documentos" / "relatorio.pdf").is_file())
        self.assertTrue((self.base / "Hojas de cálculo" / "planilha.xlsx").is_file())
        self.assertTrue((self.base / "Otros" / "desconhecido.zzz").is_file())
        self.assertTrue((self.base / "Sin extensión" / "semextensao").is_file())
        self.assertEqual(len(resultado.movimentos), 5)

    def test_nao_sobrescreve_arquivo_existente(self):
        self.criar_arquivo("Documentos/nota.pdf", "antigo")
        self.criar_arquivo("nota.pdf", "novo")

        arrumador.organizar(self.base, "tipo")

        self.assertEqual((self.base / "Documentos" / "nota.pdf").read_text(), "antigo")
        self.assertEqual((self.base / "Documentos" / "nota (1).pdf").read_text(), "novo")

    def test_ja_organizado_e_ignorado(self):
        self.criar_arquivo("Documentos/nota.pdf")
        resultado = arrumador.organizar(self.base, "tipo", recursivo=True)
        self.assertEqual(resultado.movimentos, [])
        self.assertEqual(len(resultado.ignorados), 1)

    def test_simulacao_nao_move(self):
        arquivo = self.criar_arquivo("foto.png")
        resultado = arrumador.organizar(self.base, "tipo", simular=True)
        self.assertTrue(arquivo.is_file())
        self.assertFalse((self.base / "Imágenes").exists())
        self.assertEqual(len(resultado.movimentos), 1)

    def test_padroes_ignorados_e_ocultos(self):
        self.criar_arquivo("temp.tmp")
        self.criar_arquivo(".oculto.pdf")
        self.criar_arquivo("bom.pdf")

        resultado = arrumador.organizar(self.base, "tipo", ignorar=("*.tmp",))

        self.assertEqual([m.origem.name for m in resultado.movimentos], ["bom.pdf"])
        self.assertTrue((self.base / "temp.tmp").is_file())
        self.assertTrue((self.base / ".oculto.pdf").is_file())

    def test_organiza_por_extensao_e_alfabetico(self):
        self.criar_arquivo("a.pdf")
        arrumador.organizar(self.base, "extensao")
        self.assertTrue((self.base / "PDF" / "a.pdf").is_file())

        self.criar_arquivo("zebra.txt")
        arrumador.organizar(self.base, "alfabetico")
        self.assertTrue((self.base / "Z" / "zebra.txt").is_file())

    def test_organiza_por_documento(self):
        self.criar_arquivo("EXC2026-16883-001-PES-01_R.docx")
        self.criar_arquivo("EXC2026-16883-001-PES-01_RRA.docx")
        self.criar_arquivo("EXC2026-16883-002-LPA-01.xlsx")
        self.criar_arquivo("qualquer coisa.txt")

        arrumador.organizar(self.base, "documento")

        pasta_pes = self.base / "001-PES"
        self.assertTrue((pasta_pes / "EXC2026-16883-001-PES-01_R.docx").is_file())
        self.assertTrue((pasta_pes / "EXC2026-16883-001-PES-01_RRA.docx").is_file())
        self.assertTrue((self.base / "002-LPA" / "EXC2026-16883-002-LPA-01.xlsx").is_file())
        self.assertTrue((self.base / "Sin código" / "qualquer coisa.txt").is_file())

    def test_codigo_documento(self):
        self.assertEqual(
            arrumador.codigo_documento("EXC2026-16883-003-IES-01_borrador.pdf"), "003-IES"
        )
        self.assertEqual(
            arrumador.codigo_documento("EXC2026-XXXXXX-001-PES-01_borrador.docx"), "001-PES"
        )
        self.assertIsNone(arrumador.codigo_documento("mails.msg"))

    def test_criterio_invalido(self):
        with self.assertRaises(arrumador.ErroDeOrganizacao):
            arrumador.organizar(self.base, "cor")

    def test_limpar_vazias(self):
        (self.base / "vazia" / "dentro").mkdir(parents=True)
        self.criar_arquivo("cheia/arquivo.txt")

        removidas = arrumador.limpar_vazias(self.base)

        self.assertEqual({p.name for p in removidas}, {"vazia", "dentro"})
        self.assertFalse((self.base / "vazia").exists())
        self.assertTrue((self.base / "cheia").is_dir())


class TestProjetos(BaseTemporaria):
    def test_nome_do_projeto(self):
        self.assertEqual(
            projetos.nome_projeto(2026, "16883", "Estación de Torre Pacheco (Apeadero)"),
            "2026-16883-ESTACIÓN DE TORRE PACHECO (APEADERO)",
        )

    def test_nome_com_caracteres_proibidos(self):
        self.assertEqual(projetos.nome_projeto("2026", "1", "a/b:c"), "2026-1-A B C")

    def test_ano_invalido(self):
        with self.assertRaises(projetos.ErroDeProjeto):
            projetos.nome_projeto("26", "1", "obra")

    def test_cria_projeto_completo(self):
        resultado = projetos.criar_projeto(self.base, 2026, "16883", "Torre Pacheco")
        pasta = resultado.pasta
        self.assertEqual(pasta.name, "2026-16883-TORRE PACHECO")
        for sub in projetos.ESTRUTURA_PROJETO:
            self.assertTrue((pasta / sub).is_dir(), sub)

    def test_envios_numerados_em_sequencia(self):
        pasta = projetos.criar_projeto(self.base, 2026, "16883", "Obra").pasta

        primeiro = projetos.criar_envio(pasta, data_envio="20260702")
        segundo = projetos.criar_envio(pasta, data_envio="2026-07-08")
        terceiro = projetos.criar_envio(pasta, data_envio="10/07/2026", observacao="sin revisar")

        self.assertEqual(primeiro.name, "Envío 1 20260702")
        self.assertEqual(segundo.name, "Envío 2 20260708")
        self.assertEqual(terceiro.name, "Envío 3 20260710 sin revisar")
        self.assertEqual(primeiro.parent.name, projetos.PASTA_RECEBIDA)
        self.assertEqual(projetos.proximo_numero_envio(primeiro.parent), 4)

    def test_envio_com_data_padrao_de_hoje(self):
        pasta = projetos.criar_projeto(self.base, 2026, "1", "Obra").pasta
        envio = projetos.criar_envio(pasta)
        self.assertTrue(envio.name.endswith(date.today().strftime("%Y%m%d")))

    def test_envio_data_invalida(self):
        pasta = projetos.criar_projeto(self.base, 2026, "1", "Obra").pasta
        with self.assertRaises(projetos.ErroDeProjeto):
            projetos.criar_envio(pasta, data_envio="ontem")


class TestHistoricoEDesfazer(BaseTemporaria):
    def setUp(self) -> None:
        super().setUp()
        self.arquivo_historico = self.base / "historico.json"
        self.hist = historico.Historico(self.arquivo_historico)
        self.trabalho = self.base / "trabalho"
        self.trabalho.mkdir()

    def test_registra_e_lista(self):
        identificador = self.hist.registrar("criar", self.trabalho, pastas_criadas=["a"])
        self.assertTrue(self.arquivo_historico.is_file())
        self.assertEqual(self.hist.ultima()["id"], identificador)
        self.assertEqual(len(self.hist.listar()), 1)
        self.assertTrue(self.hist.remover(identificador))
        self.assertEqual(self.hist.listar(), [])

    def test_desfaz_organizacao(self):
        (self.trabalho / "foto.png").write_text("i", encoding="utf-8")
        (self.trabalho / "nota.pdf").write_text("d", encoding="utf-8")

        resultado = arrumador.organizar(self.trabalho, "tipo")
        identificador = self.hist.registrar(
            "organizar",
            self.trabalho,
            movimentos=[{"de": str(m.origem), "para": str(m.destino)} for m in resultado.movimentos],
            pastas_criadas=[str(p) for p in resultado.pastas_criadas],
        )

        reversao = desfazer.desfazer_operacao(self.hist.obter(identificador))

        self.assertTrue((self.trabalho / "foto.png").is_file())
        self.assertTrue((self.trabalho / "nota.pdf").is_file())
        self.assertFalse((self.trabalho / "Imágenes").exists())
        self.assertFalse((self.trabalho / "Documentos").exists())
        self.assertEqual(len(reversao.restaurados), 2)
        self.assertEqual(len(reversao.pastas_removidas), 2)

    def test_desfaz_criacao_de_pastas(self):
        resultado = criador.criar_estrutura(self.trabalho / "proj", ["a/b"])
        identificador = self.hist.registrar(
            "criar", self.trabalho, pastas_criadas=[str(p) for p in resultado.criadas]
        )

        desfazer.desfazer_operacao(self.hist.obter(identificador))

        self.assertFalse((self.trabalho / "proj").exists())

    def test_desfazer_em_simulacao_nao_altera(self):
        (self.trabalho / "foto.png").write_text("i", encoding="utf-8")
        resultado = arrumador.organizar(self.trabalho, "tipo")
        operacao = {
            "id": "x",
            "movimentos": [{"de": str(m.origem), "para": str(m.destino)} for m in resultado.movimentos],
            "pastas_criadas": [str(p) for p in resultado.pastas_criadas],
        }

        desfazer.desfazer_operacao(operacao, simular=True)

        self.assertTrue((self.trabalho / "Imágenes" / "foto.png").is_file())


class TestCLI(BaseTemporaria):
    def executar(self, *argumentos: str) -> tuple[int, str]:
        saida = io.StringIO()
        with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
            codigo = main(["--historico", str(self.base / "h.json"), *argumentos])
        return codigo, saida.getvalue()

    def test_fluxo_completo(self):
        destino = self.base / "obras"

        codigo, saida = self.executar(
            "novo-projeto", "Estacion de Torre Pacheco (Apeadero)",
            "--codigo", "16883", "--ano", "2026", "--destino", str(destino),
        )
        self.assertEqual(codigo, 0)
        projeto = destino / "2026-16883-ESTACION DE TORRE PACHECO (APEADERO)"
        self.assertTrue((projeto / "4_Doc Generada" / "Doc").is_dir())

        codigo, _ = self.executar("envio", str(projeto), "--data", "20260702")
        self.assertEqual(codigo, 0)
        self.assertTrue((projeto / "2_Doc Recebida" / "Envío 1 20260702").is_dir())

        trabalho = projeto / "3_Doc Trabajo"
        (trabalho / "EXC2026-16883-001-PES-01_R.docx").write_text("a", encoding="utf-8")
        (trabalho / "EXC2026-16883-001-PES-01_RR.docx").write_text("b", encoding="utf-8")

        codigo, _ = self.executar("organizar", str(trabalho), "--por", "documento")
        self.assertEqual(codigo, 0)
        self.assertTrue((trabalho / "001-PES" / "EXC2026-16883-001-PES-01_R.docx").is_file())

        codigo, _ = self.executar("desfazer")
        self.assertEqual(codigo, 0)
        self.assertTrue((trabalho / "EXC2026-16883-001-PES-01_R.docx").is_file())
        self.assertFalse((trabalho / "001-PES").exists())

    def test_criar_exige_uma_origem(self):
        codigo, saida = self.executar("criar", str(self.base / "x"))
        self.assertEqual(codigo, 2)
        self.assertIn("--modelo", saida)

    def test_modelos_e_categorias(self):
        codigo, saida = self.executar("modelos")
        self.assertEqual(codigo, 0)
        self.assertIn("proyecto", saida)

        codigo, saida = self.executar("categorias")
        self.assertEqual(codigo, 0)
        self.assertIn("Imágenes", saida)

    def test_criar_com_modelo_e_arvore(self):
        destino = self.base / "estudos"
        codigo, _ = self.executar("criar", str(destino), "--modelo", "estudos")
        self.assertEqual(codigo, 0)
        self.assertTrue((destino / "Provas" / "Gabaritos").is_dir())

        codigo, saida = self.executar("arvore", str(destino), "--nivel", "1")
        self.assertEqual(codigo, 0)
        self.assertIn("Aulas", saida)

    def test_pasta_inexistente_retorna_erro(self):
        codigo, saida = self.executar("organizar", str(self.base / "nao-existe"))
        self.assertEqual(codigo, 1)
        self.assertIn("Erro:", saida)


if __name__ == "__main__":
    unittest.main()
