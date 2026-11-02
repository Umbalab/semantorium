#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Semantorium — Analisador Textual Inteligente
Ponto de entrada da aplicação.
"""

import os
import sys
import traceback
from pathlib import Path

# Garante que o diretório do executável esteja no sys.path
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core import __version__ as APP_VERSION  # noqa: E402


def _install_excepthook() -> None:
    """Mostra erros inesperados em uma caixa de diálogo em vez de sumir."""
    def handler(exc_type, exc_value, exc_tb):
        message = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            log = APP_DIR / "semantorium_error.log"
            log.write_text(message, encoding="utf-8")
        except Exception:
            pass
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance():
                QMessageBox.critical(
                    None, "Erro inesperado",
                    f"Ocorreu um erro inesperado:\n\n{exc_value}\n\n"
                    f"Detalhes salvos em:\n{APP_DIR / 'semantorium_error.log'}"
                )
            else:
                print(message, file=sys.stderr)
        except Exception:
            print(message, file=sys.stderr)
    sys.excepthook = handler


def _run_selftest() -> int:
    """Verifica o pacote inteiro (análise + exportação) sem abrir a interface."""
    import json
    import tempfile

    log_lines = []
    errors = []

    def log(message: str) -> None:
        log_lines.append(str(message))

    try:
        from core.analysis import AnalysisConfig, AnalysisRunner
        from core.extractor import extract_text
        from reports import exporters

        out_dir = Path(tempfile.mkdtemp(prefix="semantorium_selftest_"))
        # Preferências, histórico e modelos do teste não tocam os do usuário.
        os.environ["LEXIMA_DATA_DIR"] = str(out_dir / "dados")
        sample = ROOT / "samples" / "texto_demo.md"

        if sample.exists():
            data = extract_text(str(sample))
            text, meta = data["text"], data["meta"]
            log(f"amostra: {sample.name} ({meta.get('words')} palavras)")
        else:
            text = (
                "A inteligência artificial transforma a educação digital. "
                "A ética dos algoritmos é central. Silva (2020) defende a "
                "transparência algorítmica. Costa (2018) aponta riscos de viés. "
            ) * 20
            meta = {"filename": "inline.txt", "extension": ".txt",
                    "method": "direct", "pages": 1}
            log("amostra: texto sintético (samples/ ausente)")

        result = AnalysisRunner(AnalysisConfig(), lambda p, m: None).run(text, meta)

        checks = {
            "idioma": result.get("language"),
            "motor": result.get("engine"),
            "resumo_chars": len(result.get("summary") or ""),
            "palavras_chave": len(result.get("keywords") or []),
            "citacoes": len(result.get("citations", {}).get("items") or []),
            "onomastico": len(result.get("onomastic") or []),
            "conceitos": len(result.get("concepts") or []),
            "topicos": len(result.get("topics") or []),
            "clusters": len(result.get("clusters") or []),
            "nos_rede": result.get("graphs", {}).get("cooccurrence", {})
                            .get("stats", {}).get("nodes", 0),
            "nuvem": bool(result.get("wordcloud")
                          and Path(result["wordcloud"]).exists()),
            "referencias": len((result.get("references") or {}).get("items") or []),
            "citacoes_diretas": len(
                (result.get("quotes") or {}).get("items") or []
            ),
            "sentimentos": len(
                (result.get("sentiment") or {}).get("sentences") or []
            ),
            "argumentos": len(
                (result.get("argument_map") or {}).get("nodes") or []
            ),
            "definicoes": len(
                (result.get("definitions") or {}).get("items") or []
            ),
            "linha_do_tempo": len(
                (result.get("timeline") or {}).get("events") or []
            ),
            "mapa_mental": bool(
                (result.get("mindmap") or {}).get("svg")
            ),
            "grafo_citacoes": bool(
                (result.get("citation_graph") or {}).get("summary")
            ),
            "resumo_tamanho": (result.get("summary_detail") or {}).get("size"),
            "sentimento_dominio": (result.get("sentiment") or {}).get(
                "domain_applied"
            ) or "geral",
            "ner_motor": (result.get("ner_status") or {}).get("engine", ""),
            "evidencias_onomasticas": sum(
                1 for item in (result.get("onomastic") or [])
                if item.get("evidence")
            ),
        }
        legibility = result.get("readability") or {}
        readability_ok = bool(legibility) and not legibility.get("error")
        checks["legibilidade"] = len(legibility) if readability_ok else 0
        log("análise: " + json.dumps(checks, ensure_ascii=False))

        for warning in result.get("warnings") or []:
            log(f"AVISO: {warning}")

        for key, minimum in (("resumo_chars", 100), ("palavras_chave", 5),
                             ("conceitos", 3), ("topicos", 1), ("clusters", 1),
                             ("referencias", 1), ("citacoes_diretas", 1),
                             ("sentimentos", 1), ("argumentos", 1),
                             ("definicoes", 1), ("linha_do_tempo", 1)):
            if checks.get(key, 0) < minimum:
                errors.append(f"{key} abaixo do esperado ({checks.get(key)})")
        if not checks["mapa_mental"]:
            errors.append("mapa mental não gerado")
        if not checks["grafo_citacoes"]:
            errors.append("grafo de citações não gerado")
        if not checks["nuvem"]:
            errors.append("nuvem de palavras não gerada")
        if checks["nos_rede"] < 2:
            errors.append("rede de coocorrência vazia")
        if not readability_ok:
            errors.append(
                "legibilidade indisponível: "
                + str(legibility.get("error", "sem dados"))
            )

        exports = {
            "html": exporters.export_html,
            "pdf": exporters.export_pdf,
            "json": exporters.export_json,
            "csv": exporters.export_csv,
            "xlsx": exporters.export_xlsx,
        }
        for kind, function in exports.items():
            path = out_dir / f"relatorio.{kind}"
            try:
                function(result, str(path))
                size = path.stat().st_size
                log(f"export {kind}: {size} bytes")
                if size < 200:
                    errors.append(f"export {kind} muito pequeno")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"export {kind}: {exc}")
                log(f"export {kind}: FALHOU {exc}")

        # a nuvem e o grafo precisam estar embutidos no HTML
        html_path = out_dir / "relatorio.html"
        if checks["nuvem"] and html_path.exists():
            content = html_path.read_text(encoding="utf-8", errors="ignore")
            if "data:image/png;base64" not in content:
                errors.append("HTML sem a nuvem de palavras embutida")
            if checks["nos_rede"] >= 2 and "data:text/html;base64" not in content:
                errors.append("HTML sem o grafo de coocorrência embutido")
            required = [
                "Palavras menos frequentes", "Legibilidade",
                "Concordância (KWIC)", "Árvore de palavras",
                "Rede semântica", "Similaridade entre trechos",
                "Referências bibliográficas", "Citações diretas",
                "Sentimentos", "Mapa de argumentos", "Definições",
                "Linha do tempo", "Mapa mental", "Grafo de citações",
            ]
            missing = [name for name in required if name not in content]
            if missing:
                errors.append("HTML sem as seções: " + ", ".join(missing))

        # CSV consolidado: todas as seções principais precisam existir
        csv_path = out_dir / "relatorio.csv"
        if csv_path.exists():
            lines = csv_path.read_text(encoding="utf-8-sig",
                                       errors="ignore").splitlines()[1:]
            present = {line.split(",", 1)[0] for line in lines if line}
            for section in ("estatisticas", "resumo", "palavras_chave",
                            "topicos", "kwic", "similaridade", "legibilidade",
                            "referencias", "citacoes_diretas", "sentimentos",
                            "argumentos", "definicoes", "linha_do_tempo"):
                if section not in present:
                    errors.append(f"CSV sem a seção {section}")

        # XLSX: abas essenciais
        xlsx_path = out_dir / "relatorio.xlsx"
        if xlsx_path.exists():
            from openpyxl import load_workbook
            workbook = load_workbook(xlsx_path, read_only=True)
            sheets = set(workbook.sheetnames)
            workbook.close()
            for name in ("Resumo", "Palavras-chave", "Tópicos", "Grupos",
                         "Concordância", "Rede semântica", "Similaridade",
                         "Referências", "Sentimentos", "Argumentos",
                         "Definições", "Linha do tempo", "Mapa mental",
                         "Grafo de citações"):
                if name not in sheets:
                    errors.append(f"XLSX sem a aba {name}")

        # PDF: todas as seções em várias páginas
        pdf_path = out_dir / "relatorio.pdf"
        if pdf_path.exists():
            import pymupdf
            with pymupdf.open(str(pdf_path)) as document:
                pages = document.page_count
            log(f"pdf: {pages} páginas")
            if pages < 6:
                errors.append(f"PDF com poucas páginas ({pages})")

        # Corpus (0.7.0): matriz N×N e exportações próprias
        from core import corpus, userdata

        documents = [
            {"name": "amostra",
             "path": str(sample) if sample.exists() else "",
             "text": text},
            {"name": "segundo_texto",
             "text": text + "\n\nO mercado financeiro cresceu com "
                             "investimentos e emprego no período."},
        ]
        corpus_result = corpus.analyze_corpus(documents, clusters=2)
        corpus_totals = corpus_result.get("totals") or {}
        log("corpus: " + json.dumps(corpus_totals, ensure_ascii=False))
        if corpus_totals.get("documents") != 2:
            errors.append("corpus não analisou os dois documentos")
        if len(corpus_result.get("matrix") or []) != 2:
            errors.append("matriz de similaridade do corpus incompleta")
        if not corpus_result.get("clusters"):
            errors.append("corpus sem agrupamentos")
        for kind, function in (
            ("html", exporters.export_corpus_html),
            ("csv", exporters.export_corpus_csv),
        ):
            path = out_dir / f"corpus.{kind}"
            try:
                function(corpus_result, str(path))
                size = path.stat().st_size
                log(f"export corpus {kind}: {size} bytes")
                if size < 200:
                    errors.append(f"export corpus {kind} muito pequeno")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"export corpus {kind}: {exc}")
                log(f"export corpus {kind}: FALHOU {exc}")
        corpus_html = out_dir / "corpus.html"
        if corpus_html.exists():
            content = corpus_html.read_text(encoding="utf-8", errors="ignore")
            if "Matriz de similaridade" not in content:
                errors.append("HTML do corpus sem a matriz N×N")

        # Preferências e modelos nomeados
        try:
            userdata.save_template("selftest", {"summary_size": "curto"}, "html")
            if "selftest" not in userdata.list_templates():
                errors.append("modelo de análise não foi salvo")
            userdata.delete_template("selftest")
            if "selftest" in userdata.list_templates():
                errors.append("modelo de análise não foi excluído")
            log("preferencias: modelos salvos e removidos")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"preferências/modelos: {exc}")

        log(f"saida: {out_dir}")

        # OCR: valida o caminho completo de imagem -> texto
        scan = ROOT / "samples" / "scan_demo.pdf"
        if scan.exists():
            try:
                scan_data = extract_text(str(scan))
                method = scan_data["meta"].get("method")
                words = scan_data["meta"].get("words", 0)
                available = scan_data["meta"].get("ocr_available", True)
                log(f"ocr: disponível={available} método={method} "
                    f"palavras={words}")
                if not available:
                    log("ocr: indisponível neste build (teste ignorado)")
                elif method != "ocr" or words < 10:
                    errors.append(
                        f"OCR não funcionou (método={method}, palavras={words})"
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"OCR falhou: {exc}")
                log(f"OCR falhou: {exc}")
        else:
            log("ocr: amostra ausente (ignorado)")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"falha geral: {exc}")
        log(traceback.format_exc())

    status = "OK" if not errors else "FALHOU"
    log_lines.insert(0, f"Semantorium SELFTEST: {status}")
    if errors:
        log_lines.extend(f"ERRO: {e}" for e in errors)
    report = "\n".join(log_lines)

    try:
        (APP_DIR / "semantorium_selftest.log").write_text(report, encoding="utf-8")
    except Exception:
        pass
    print(report)
    return 0 if not errors else 2


def main() -> int:
    argv = [a for a in sys.argv[1:]]
    if "--selftest" in argv:
        return _run_selftest()
    if "--version" in argv:
        print(f"Semantorium {APP_VERSION}")
        return 0

    _install_excepthook()

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    # Importar QtWebEngine antes de criar o QApplication (quando disponível)
    try:
        from PySide6 import QtWebEngineWidgets  # noqa: F401
    except Exception:
        pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Semantorium")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("Semantorium")

    try:
        from core import userdata, i18n
        settings = userdata.load_settings()
        ui_lang = settings.get("ui_language") or "pt-BR"
        i18n.set_locale(ui_lang)
    except Exception:
        pass

    icon_path = ROOT / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
