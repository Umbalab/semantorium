#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Teste CLI headless do núcleo do Semantorium.

Uso:
    python -m tools.cli_analyze arquivo.txt
    python -m tools.cli_analyze arquivo.pdf --lang PT-BR --json saida.json
"""

import argparse
import json
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "tools"

from core.analysis import AnalysisConfig, AnalysisRunner  # noqa: E402
from core.extractor import extract_text  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Semantorium - análise headless")
    parser.add_argument("file", help="Arquivo a analisar")
    parser.add_argument("--lang", default="Auto-detectar")
    parser.add_argument("--json", dest="json_out", help="Salvar resultado em JSON")
    parser.add_argument("--no-graphs", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    def progress(pct, msg):
        if not args.quiet:
            print(f"[{pct:3d}%] {msg}")

    print(f"Lendo {args.file} ...")
    extracted = extract_text(args.file)
    meta = extracted["meta"]
    print(f"  {meta['words']} palavras · método {meta['method']} · "
          f"páginas {meta.get('pages')}")

    config = AnalysisConfig(language=args.lang,
                            generate_graphs=not args.no_graphs)
    runner = AnalysisRunner(config, progress)
    result = runner.run(extracted["text"], meta)

    print()
    print("=" * 70)
    print(f"Idioma: {result['language_label']} | motor: {result['engine']}")
    print(f"Palavras: {result['stats']['words']} | "
          f"únicas: {result['stats']['unique_words']} | "
          f"sentenças: {result['stats']['sentences']}")
    print("-" * 70)
    print("RESUMO:")
    print(result["summary"][:900])
    print("-" * 70)
    print("PALAVRAS-CHAVE:")
    print(", ".join(k["keyword"] for k in result["keywords"][:15]))
    print("-" * 70)
    print(f"CITAÇÕES: {len(result['citations']['items'])}")
    print(f"ONOMÁSTICO: {len(result['onomastic'])} nomes")
    print(f"CONCEITOS: {', '.join(c['term'] for c in result['concepts'][:10])}")
    print(f"TÓPICOS: {len(result['topics'])}")
    print(f"CLUSTERS: {len(result['clusters'])}")
    graphs = result.get("graphs", {}).get("cooccurrence", {})
    print(f"REDE: {graphs.get('stats', {}).get('nodes', 0)} nós, "
          f"{graphs.get('stats', {}).get('edges', 0)} conexões")
    print(f"NUVEM: {result.get('wordcloud')}")
    print("=" * 70)

    if args.json_out:
        payload = {k: v for k, v in result.items()}
        Path(args.json_out).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"JSON salvo em {args.json_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
