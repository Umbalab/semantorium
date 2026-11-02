import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.textproc import TextProcessor
from core import definitions, timeline, onomastic
from core.bibliography import build_references
from core.citations import detect_citations
from core.citation_graph import build_citation_graph_rendered
from core import compare

text = Path('samples/texto_demo.md').read_text(encoding='utf-8')
p = TextProcessor('PT-BR')
processed = p.process(text)
print('entities', len(processed.entities))
idx = onomastic.generate_onomastic_index(processed.entities, text, {'Silva': 3, 'Costa': 2})
print('onomastic', [(e['name'], e['type'], e['count'], e['confidence']) for e in idx[:15]])
print('types', onomastic.type_counts(idx))
d = definitions.extract_definitions(text)
print('defs', d['count'], d['by_pattern'], [i['term'] for i in d['items'][:8]])
t = timeline.build_timeline(text)
print('timeline', t['summary'], t['years'][:8])
cits = detect_citations(text)
refs = build_references(text, cits)
print('refs', refs['count'], refs['by_type'], len(cits))
g = build_citation_graph_rendered(refs, {'items': cits}, 'Demo')
print('graph', g['summary'], len(g['svg']), len(g['html']))

other = text.replace('ética', 'moral').replace('algoritmos', 'sistemas')
cmp = compare.compare_texts(text, other, 'A', 'B')
print('compare', cmp['similarity'], cmp['verdict'])
print('sentences', cmp['sentences']['matched'], cmp['sentences']['only_a_count'])
