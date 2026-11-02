# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec do Semantorium.

Build completo (padrão):
    .\\.venv\\Scripts\\python.exe -m PyInstaller Semantorium.spec --noconfirm

Build Lite (sem OCR e sem QtWebEngine, instalação menor):
    $env:Semantorium_LITE = "1"
    .\\.venv\\Scripts\\python.exe -m PyInstaller Semantorium.spec --noconfirm
"""

import os

from PyInstaller.utils.hooks import (collect_data_files, collect_dynamic_libs,
                                     collect_submodules)

LITE = os.environ.get("Semantorium_LITE", "").strip().lower() in ("1", "true", "yes")
APP_NAME = "SemantoriumLite" if LITE else "Semantorium"

hiddenimports = [
    # Módulos da aplicação (importados dinamicamente em alguns pontos)
    "core", "core.analysis", "core.extractor", "core.textproc",
    "core.keywords", "core.summary", "core.citations", "core.onomastic",
    "core.concepts", "core.kwic", "core.coocurrence", "core.semantic",
    "core.readability", "core.wordcloud_gen", "core.language",
    "core.argument", "core.bibliography", "core.citation_graph",
    "core.reference_model", "core.reference_extract", "core.reference_format",
    "core.reference_import", "core.bibliography_dedup", "core.explanations",
    "core.compare", "core.definitions", "core.mindmap", "core.quotes",
    "core.sections", "core.sentiment", "core.stopwords", "core.timeline",
    "core.corpus", "core.ner", "core.userdata",
    "reports", "reports.exporters",
    "ui", "ui.main_window", "ui.worker", "ui.views", "ui.widgets",
    "ui.views.load_view", "ui.views.overview_view", "ui.views.words_view",
    "ui.views.graphs_view", "ui.views.citations_view",
    "ui.views.advanced_view", "ui.views.export_view",
    "ui.views.corpus_view", "ui.views.compare_view", "ui.dialogs",
    "ui.dialogs.stoplist_dialog", "ui.dialogs.history_dialog",
    "ui.widgets.common", "ui.widgets.graph_view",
    # Qt usado na rasterização de máscaras SVG da nuvem
    "PySide6.QtSvg",
    # Bibliotecas com import dinâmico
    "yake", "sumy", "pyvis", "wordcloud", "textstat",
    "reportlab.pdfbase._fontdata", "openpyxl.cell._writer",
    "charset_normalizer.md__mypyc",
]

if not LITE:
    # OCR (importado dinamicamente por rapidocr)
    hiddenimports += ["cv2", "onnxruntime"]

datas = [
    ("data", "data"),
    ("assets", "assets"),
    ("samples", "samples"),
    ("LICENSE", "."),
    ("README.md", "."),
]

binaries = []

if not LITE:
    # OCR: bibliotecas nativas e modelos ONNX
    for package in ("onnxruntime", "cv2", "shapely"):
        try:
            datas += collect_data_files(package)
            binaries += collect_dynamic_libs(package)
        except Exception:
            pass

# Pacotes que precisam dos próprios arquivos de dados em runtime
packages_with_data = [
    "pyvis",            # templates + biblioteca vis.js
    "wordcloud",        # fonte DroidSansMono
    "langdetect",       # perfis de idioma
    "textstat",
    "sumy",
]
if not LITE:
    packages_with_data.append("rapidocr_onnxruntime")  # modelos ONNX de OCR

for package in packages_with_data:
    try:
        datas += collect_data_files(package)
    except Exception:
        pass

# Submódulos que o PyInstaller não enxerga por análise estática
packages_with_submodules = ["yake", "sumy", "pyvis"]
if not LITE:
    packages_with_submodules.append("rapidocr_onnxruntime")

for package in packages_with_submodules:
    try:
        hiddenimports += collect_submodules(package)
    except Exception:
        pass

# PyMuPDF: o subsistema "pymupdf.layout" (analise de layout por modelos ONNX)
# nao e usado pelo Semantorium. Ele e importado automaticamente por "import pymupdf"
# e, no bundle, falhava ao procurar os modelos (PermissionError/FileNotFound).
# Excluir o pacote mantem a extracao de texto/OCR do PyMuPDF intacta e evita
# ~50 MB de modelos no instalador.
excludes = [
    "tkinter", "pydoc_data", "test",
    "notebook", "jupyter", "IPython", "pytest", "pytestqt",
    # dependências instaladas indiretamente que não são usadas
    "pymupdf4llm", "pymupdf_layout", "pymupdf.layout",
    "jedi", "prompt_toolkit", "stack_data", "matplotlib_inline",
    "pygments", "asttokens", "executing", "pure_eval", "traitlets",
    "wcwidth", "parso", "tensorflow", "torch", "transformers",
    "sentence_transformers", "spacy", "tk",
]

if LITE:
    excludes += [
        "rapidocr_onnxruntime", "onnxruntime", "cv2", "shapely",
        "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
        "PySide6.QtWebSockets",
    ]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

if LITE:
    # No build Lite não há navegador embutido: remove DLLs/pacotes do
    # QtWebEngine, traduções do Qt e QML (economia de ~400 MB).
    LITE_DROP_TOKENS = (
        "qt6webengine", "qtwebengine", "qtwebchannel", "qtwebsockets",
        "pyside6/translations", "pyside6/qml", "icudtl.dat",
        "v8_context_snapshot",
    )

    def _keep_for_lite(entries):
        kept = []
        for entry in entries:
            destination = str(entry[0]).replace("\\", "/").lower()
            if any(token in destination for token in LITE_DROP_TOKENS):
                continue
            kept.append(entry)
        return kept

    a.binaries = _keep_for_lite(a.binaries)
    a.datas = _keep_for_lite(a.datas)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
