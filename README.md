# Semantorium — Analisador Textual Inteligente

Aplicativo **local** para Windows que analisa textos longos e gera um relatório
completo: resumo com tamanho ajustável, palavras-chave, nuvem de palavras
personalizável, redes de coocorrência, grafo e citações bibliográficas, citações
diretas, índice onomástico editável com evidências, conceitos, concordância,
legibilidade, tópicos, agrupamentos semânticos, sentimentos por domínio, mapa de
argumentos, definições, linha do tempo com datas normalizadas, mapa mental
automático, comparação entre dois textos e **análise de corpus com matriz de
similaridade N×N**, além de **discurso**, **conhecimento documental**,
**consistência interna**, **exploração por evidências** com painel de pesquisa
local e **camada opcional de modelos locais** (spaCy/Stanza, embeddings,
correferência neural e Ollama opt-in).

**Versão 2.0.0.** **100% offline.** Nenhum dado sai do seu computador — o
assistente local opcional (Ollama) conversa apenas com um servidor na própria
máquina. A única exceção é o **download opcional do instalador do Ollama**,
iniciado por você no diálogo e cancelável; o texto analisado nunca é enviado
para a internet.

Licença **MIT** — uso, distribuição e modificação permitidos (veja `LICENSE`).

---

## Como usar (versão compilada)

1. Baixe/extraia a pasta `dist\Semantorium\`.
2. Execute **`Semantorium.exe`**.
3. Clique em **Carregar arquivo** e escolha um `.pdf`, `.docx`, `.odt`, `.txt`,
   `.md` ou `.rtf`.
4. Confira o idioma (ou deixe em *Auto-detectar*).
5. Clique em **⚡ Gerar relatório**.
6. Navegue pelas abas e exporte em HTML, PDF, JSON, TXT, CSV, XLSX, **DOCX** ou
   **ODT** (com tabelas e imagens).

Não é necessário instalar Python.

### Verificar a instalação

O executável tem um autoteste embutido que roda a análise completa, **testa o
OCR** em um PDF escaneado e exporta todos os formatos, sem abrir a interface:

```powershell
.\dist\Semantorium\Semantorium.exe --selftest
```

O resultado é gravado em `dist\Semantorium\Semantorium_selftest.log` (deve terminar com
`Semantorium SELFTEST: OK`).

---

## Formatos suportados

| Formato | Extração |
|---|---|
| `.pdf` | Texto nativo (PyMuPDF) + figuras e tabelas quando habilitado |
| `.pdf` escaneado | **OCR automático** (RapidOCR + ONNX), quando habilitado |
| `.docx` | Texto, **tabelas**, **cabeçalhos/rodapés** e notas de rodapé |
| `.odt` | Texto + **tabelas** |
| `.rtf` | Texto |
| `.txt` | Texto direto (detecção de encoding) |
| `.md` | Texto + front matter, **tabelas**, notas e links |

Se um PDF tiver pouco texto por página, o Semantorium tenta OCR automaticamente.
O OCR é opcional: a interface avisa quando não está disponível.

A extração respeita a estrutura do documento: DOCX preserva a ordem do corpo
e registra cabeçalhos/rodapés/notas, ODT preserva tabelas, Markdown preserva
front matter, tabelas, notas e links, e o PDF extrai figuras e tabelas quando a
leitura nativa não traz texto suficiente.

---

## O que o relatório contém

| Aba | Conteúdo |
|---|---|
| **Carregar** | Seleção de arquivo, idioma e pré-visualização |
| **Visão geral** | KPIs, resumo automático, palavras-chave, **resultados e evidências** (natureza, limitações e trechos localizados) e detalhes da análise |
| **Palavras** | Ranking de frequência com formas completas, stoplist editável, paletas, fundo transparente, máscara PNG/JPG/SVG e botão **Salvar nuvem (PNG)** |
| **Redes** | Grafo de coocorrência interativo, árvore de palavras, rede semântica, **similaridade** (com toggle *Usar embeddings locais* — TF-IDF ou `sentence-transformers` com cache por hash), **mapa mental** (SVG/HTML/Mermaid/Markdown, com editor visual e exportação PNG/PDF) e **grafo de citações** |
| **Citações & índices** | Referências bibliográficas com extração determinística, **12 estilos** (ABNT, APA 7, Chicago autor-data e notas, MLA 9, Harvard, IEEE, Vancouver, AMA, ACS, Turabian e ISO 690), pré-visualização, confiança por campo, detalhes da extração, importação **e exportação** BibTeX/RIS e deduplicação exata/possível; citações, citações diretas, índice onomástico editável, conceitos e concordância (KWIC) |
| **Análise avançada** | Legibilidade, riqueza lexical, tópicos (LDA), agrupamentos, sentimentos com domínio e explicações, argumentos, definições, linha do tempo com datas normalizadas, **linha do tempo temporal** e **Modelos (opcional)** com capacidades, resultados, comparação determinístico × modelo e relatório de divergências |
| **Lexicometria** | Métricas, termos e dispersão, n-gramas, colocações, variação e períodos, com gráfico SVG/PNG |
| **Linguística** | POS, sintaxe, campos semânticos, marcadores discursivos e correferência, com filtro por seção e indicador de motor |
| **Estilo** | Estilometria, pontuação, palavras funcionais, repetição e perfil por seção |
| **Pesquisa** | Mapa IMRaD, função das citações, metodologia declarada, lacunas observadas e matriz de estudos |
| **Discurso** | Ethos/pathos/logos, Toulmin, CDA sem juízo de poder, posicionamento por alvo e enquadramento — tudo interpretativo |
| **Conhecimento** | Relações, ontologia editável, terminologia, eventos e afirmações, sem fact-checking automático |
| **Consistência** | Achados para revisão humana, comparação de paráfrase e comparação de versões |
| **Comparar** | Comparação com um segundo arquivo: volume, riqueza lexical, legibilidade, similaridade, vocabulário, palavras-chave e trechos equivalentes |
| **Corpus** | Vários documentos: panorama, documentos, matriz de similaridade N×N, pares mais e menos parecidos, agrupamentos, duplicatas, **matriz de extração**, **PRISMA 2020**, checklist e vocabulário compartilhado/exclusivo |
| **Explorar** | Investigação por evidências em até dois cliques: busca contextual (booleana, frases, `NEAR/n`, lemma, variantes e regex seguro), catálogo filtrável de trechos com página/seção/método/confiança, navegação por conceitos, filtros cruzados persistentes, perfil de documento por seção e **painel de pesquisa** com notas, perguntas e exportação Markdown/CSV/JSON |
| **Relatórios de IA** | Textos gerados pelo assistente local (Ollama), com pré-visualização, cópia, salvamento individual e **inclusão automática no relatório final** |
| **Exportar** | HTML, PDF, JSON, TXT, CSV, XLSX, sessão (`.Semantorium.json`), modelos de análise/exportação, formato preferido e **DOCX/ODT com tabelas e imagens** |

O HTML exportado é **autocontido**: a nuvem de palavras, o grafo interativo, o
mapa mental e o grafo de citações vão embutidos no próprio arquivo (não é
preciso enviar arquivos auxiliares). O relatório atual inclui **mais de 30 seções
no HTML**, **40+ abas no XLSX**, **50+ categorias no CSV** e **15+ páginas no
PDF**: frequência, legibilidade, riqueza lexical, **lexicometria e n-gramas**,
**linguística estrutural**, **estilo e estilometria**, **pesquisa acadêmica**,
**discurso, retórica e argumentação**, citações, referências,
citações diretas, onomástico, conceitos, tópicos, concordância (KWIC), redes,
árvore de palavras, similaridade, sentimentos, argumentos, definições, linha do
tempo, mapa mental, grafo de citações, temporalidade, **resultados e
evidências**, matriz de extração, relatórios gerados por IA e avisos da análise.
Os avisos também aparecem na Visão geral e na barra de status.

Cada aba e sub-aba tem um painel **“o que esta aba faz e como ler os índices”**,
com explicações detalhadas sobre o propósito da análise, o significado de cada
métrica e como interpretar valores baixos, médios e altos. O mesmo **guia de
leitura** e o **glossário** (62 guias e 40 termos) são incluídos no relatório
exportado: seção própria em HTML/PDF/DOCX/ODT, linhas `guia_leitura` no CSV,
aba **Guia e glossário** no XLSX e os campos `reading_guide`/`glossary` no JSON.

### Análise de corpus

A aba **Corpus** compara vários arquivos ao mesmo tempo, sem depender de um
documento carregado:

- panorama por documento (volume, sentenças, riqueza lexical, legibilidade,
  idioma e sentimento);
- **matriz de similaridade N×N** (cosseno sobre TF-IDF), com todos os pares;
- pares mais e menos parecidos, agrupamentos por similaridade média e detecção
  de **duplicatas/quase-duplicatas**;
- vocabulário compartilhado por todos, frequência documental e termos
  exclusivos de cada documento;
- **matriz de extração** de metadados (autor, afiliação, método, idioma, ano) com
  sugestões de perguntas de investigação;
- **PRISMA 2020** com checklist de 37 itens e **checklist de registro** exportável
  em HTML/Markdown/CSV;
- exportação própria em **HTML** (com a matriz visual) e **CSV**.

Tudo é calculado localmente, em Python puro quando o scikit-learn não está
disponível.

### Exploração por evidências

A aba **Explorar** transforma o relatório em investigação, sem criar novas
classificações: ela reorganiza as evidências já calculadas e permite chegar a
qualquer trecho em **até dois cliques**.

- **Busca** contextual com AND implícito, `AND`/`OR`/`NOT`, frases,
  parênteses, `NEAR/n`, `lemma:`/`lema:`, `variante:`/`variant:`, `regex:` e
  `/.../flags`, com destaque dos trechos encontrados. `AND`/`OR` operam no
  documento inteiro; para exigir proximidade, use `NEAR/n`.
- **Evidências** em painel reutilizável: trecho exato, página (quando
  extraída), seção, contexto, natureza, confiança, método e limitações.
- **Conceitos** com ocorrências, relações, documentos e evolução; **Documento**
  com perfil e análise por seção.
- **Filtros** cruzados por autor, ano, conceito, sentimento, documento, seção e
  natureza (OU dentro da faceta, E entre facetas), persistidos em
  `settings.json`.
- **Pesquisa**: painel local com evidências, perguntas, conceitos e notas do
  pesquisador, salvo em `%APPDATA%\Semantorium\research_panel.json` e exportável em
  Markdown, CSV e JSON.

As perguntas investigativas são geradas por **templates determinísticos**
(`review_required = True`, `fact_checked = False`, `automatic_verdict = False`):
elas indicam o que revisar, mas nunca respondem nem emitem veredito.

### Referências bibliográficas

O pipeline de referências é **determinístico, local e sem IA**: cada etapa é
independente e auditável.

- **Segmentação** de referências numeradas (`[1]`, `1.`), alfabéticas, separadas
  por linha em branco ou por início de linha, reunindo linhas quebradas pelo PDF
  sem cortar títulos ou sobrenomes.
- **Modelo intermediário** independente de norma: autores (inclusive
  institucionais e sobrenomes compostos), título e subtítulo, periódico, livro,
  editora, local, ano, edição, volume, número, páginas, instituição, tipo de
  trabalho, DOI, ISBN, ISSN, URL, data de acesso, evento, série e idioma.
- **Classificação de tipo** por evidências (artigo, livro, capítulo, tese,
  dissertação, TCC, anais, relatório, norma, legislação, patente, verbete,
  página web, documento eletrônico etc.), com categoria genérica quando não há
  evidência suficiente.
- **Confiança por campo** e sinalização de **revisão humana**; campos ausentes
  usam marcadores normativos (`[s. d.]`, `n.d.`, `no date`) e **nunca são
  inventados**. O texto original de cada entrada fica preservado para auditoria.
- **12 estilos de formatação** aplicados sobre o mesmo registro: ABNT NBR 6023,
  APA 7, Chicago (autor-data e notas), MLA 9, Harvard, IEEE, Vancouver, AMA, ACS,
  Turabian e ISO 690 — com ordenação alfabética ou numérica e citação no corpo.
- **Citações no corpo** relacionadas às referências por autores, coautores, ano
  e identificadores (não apenas pelo sobrenome), com relatório de cobertura e
  lacunas.
- **Duplicatas** classificadas como **exatas** ou **possíveis** por DOI, ISBN,
  ISSN, título, autores, ano, periódico, volume e páginas; nada é excluído sem
  confirmação explícita.
- **Importação e exportação** BibTeX e RIS preservando todos os metadados, além
  de TXT, CSV, JSON, XLSX, HTML, DOCX e PDF no relatório final. O JSON traz as
  referências formatadas nos 12 estilos.

### Modelos, preferências e atalhos

- **Modelos de análise/exportação**: salve a configuração atual com um nome e
  reaplique-a depois. O modelo guarda os parâmetros da análise e o formato
  preferido.
- **Preferências persistentes** em `%APPDATA%\Semantorium\settings.json` (a variável
  `Semantorium_DATA_DIR` troca a pasta): configuração, formato preferido, idioma da
  interface, tema claro/escuro, documentos recentes, favoritos, histórico de
  análises, modelo de embeddings, cache de embeddings e checklist PRISMA.
- **Idioma da interface**: 13 idiomas suportados (pt-BR, pt-PT, en, es, fr, de, it,
  ja, zh, ru, pl, el, tr). Menus, abas, botões principais, títulos de diálogos e
  textos de status são traduzidos por catálogos em `data/i18n/*.json`; o idioma
  escolhido é aplicado ao iniciar e reaplicado ao salvar as configurações.
- **Tema**: claro (padrão) ou escuro.
- **Embeddings**: similaridade semântica via `sentence-transformers` com fallback
  automático para TF-IDF; cache em disco por hash SHA-256 em
  `<dados>/cache/embeddings/*.npy`; modelo configurável.
- **Checklist PRISMA 2020**: estado (37 itens + subitens) persistido em
  `settings.json` e exportável em HTML/Markdown/CSV.
- **Histórico** registra apenas metadados (caminho, idioma, volume, resumo curto
  e avisos); o texto não é armazenado.
- **Atalhos**: `Ctrl+O` abrir, `F5` gerar relatório, `Ctrl+,` configurações,
  `Ctrl+K` stoplist, `Ctrl+D` favoritar, `Ctrl+H` histórico, `Ctrl+E` exportar,
  `Ctrl+F` busca global no relatório, `Ctrl+Shift+A` assistente local (Ollama),
  `F1` ajuda e `Alt+1`…`Alt+9` trocar de aba.

### Stoplist e personalização

A stoplist combina a lista padrão de cada idioma com as palavras que você
adicionar ou remover. Ela vale para **todas** as análises de conteúdo
(frequência, nuvem, palavras-chave, conceitos, tópicos, agrupamentos,
similaridade e redes), é salva automaticamente em
`%APPDATA%\Semantorium\stoplist.json` e pode ser importada/exportada. O caminho pode
ser trocado pela variável de ambiente `Semantorium_STOPLIST`.

---

## Idiomas

13 idiomas suportados: **pt-BR**, **pt-PT**, en, es, fr, de, it, ja, zh, ru, pl, el e tr.

A interface (menus, abas, botões, diálogos e status) e a detecção/lematização do
texto usam esses idiomas. O idioma é **auto-detectado** e pode ser forçado
manualmente.

> Se os modelos do spaCy estiverem instalados, o processamento usa lematização e
> NER completos. Modelos também podem ser colocados na pasta `models/` ao lado
> do executável ou indicados em `Semantorium_MODELS` (pastas separadas por `;`).
> Caso contrário, o Semantorium usa um motor interno de tokenização, stemming leve e
> heurísticas de nomes próprios — **o aplicativo funciona nos dois casos** e
> mostra qual motor foi usado.

---

## Assistente local (Ollama) — opcional

O Semantorium pode incluir um **assistente de IA** que roda 100% local em
**Ollama** (`http://localhost:11434`), sem nuvem e sem telemetria.

- **Desativado por padrão** — nenhuma tarefa é executada sem você habilitar.
- Ative em **Configurações → Assistente local (Ollama)** ou via menu
  **Análise → Assistente local (Ollama)…** (`Ctrl+Shift+A`).
- O assistente oferece **resumo do documento**, **perguntas sobre o texto** e
  **sugestões de análise**, usando um modelo local (Ollama empurra modelos como
  `llama3.2`, `qwen2.5`, `mistral`, etc.).
- Requer o Ollama **instalado e em execução** local (`https://ollama.com/download`).
  Ativar a opção nas preferências apenas autoriza o uso; não instala o serviço.
- O diálogo faz um **diagnóstico instantâneo**: se o Ollama não estiver
  instalado, mostra o botão **«Baixar e instalar»**; se estiver instalado mas
  parado, oferece **«Iniciar Ollama»** (executa `ollama serve` em segundo plano).
- **«Baixar e instalar»** pede confirmação, baixa o instalador oficial
  (~1,7 GB) mostrando o progresso e permite **cancelar** o download. O
  instalador é executado em modo silencioso; nenhum documento é enviado.
- Depois de instalar, baixe um modelo (`ollama pull llama3.2`) e clique em
  **«Verificar»** para listar os modelos disponíveis.
- **Modelos recomendados** (testados nesta máquina, CPU sem GPU): `llama3.2:3b`
  (2,0 GB) como padrão — mais rápido e melhor em raciocínio crítico — e
  `qwen2.5:3b` (1,9 GB) para resumos mais fluentes. Ambos rodam a ~6–7 tokens/s
  em um Core i5 de 4 núcleos; respostas longas podem levar de 1 a 2 minutos.
- O tempo limite padrão é **300 s**, ajustável em `ollama_timeout` nas
  preferências, para não interromper análises longas em máquinas sem GPU.
- Cada resposta é adicionada automaticamente à aba **Relatórios de IA**, onde
  pode ser revisada, copiada, salva em Markdown ou removida. Os textos dessa
  aba entram no relatório final exportado em HTML, PDF, DOCX, ODT, JSON, TXT,
  CSV e XLSX, com a identificação da tarefa, do modelo e da data de geração.
- Sem o servidor, o diálogo explica o que fazer e nenhuma chamada sai da máquina.

---

## Instalação para desenvolvimento

Requer **Python 3.11–3.13** (recomendado 3.13).

```powershell
cd C:\OpenCode\Semantorium
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

### Dependências opcionais (melhoram a precisão)

```powershell
# Lematização/NER de alta qualidade
python -m spacy download pt_core_news_lg
python -m spacy download en_core_web_lg

# OCR para PDFs escaneados
pip install rapidocr-onnxruntime onnxruntime

# Similaridade semântica por embeddings (mais pesado, ~2 GB)
pip install sentence-transformers
```

Sem essas dependências o app continua funcional (com fallback interno).

---

## Gerar o executável

Build completo (com OCR e grafo interativo embutido):

```powershell
.\build.ps1            # testes + PyInstaller + autoteste + instalador
.\build.ps1 -NoInstaller
```

Build **Lite** (sem OCR e sem QtWebEngine, ~64% menor):

```powershell
.\build_lite.ps1       # gera dist\SemantoriumLite\SemantoriumLite.exe
```

Saída: `dist\Semantorium\Semantorium.exe` (modo pasta, inicia rápido).

> O pacote completo ocupa cerca de **982 MB** porque inclui OCR (ONNX/OpenCV),
> aprendizado de máquina (scikit-learn) e o motor de navegador para os grafos
> interativos. O **Lite** ocupa **357 MB** (sem OCR e sem QtWebEngine). O
> instalador tem **270 MB**. Copie a pasta inteira — o `.exe` depende dela.
>
> O Lite não faz OCR de PDFs escaneados e mostra a rede como tabela estática;
> o HTML exportado continua autocontido e interativo.

### Instalador

```powershell
.\build_installer.ps1              # usa o build existente
.\build_installer.ps1 -SkipBuild   # só recompila o instalador
```

Requer o [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install
JRSoftware.InnoSetup`). Saída: `dist\installer\SemantoriumSetup-<versão>.exe`
(instalação por usuário, sem exigir administrador, com atalhos e desinstalador).

---

## Testes

```powershell
.\.venv\Scripts\python.exe -m pytest -q     # núcleo + UI (pytest-qt) + exportação
.\.venv\Scripts\python.exe tests\test_core.py
```

A suíte atual é **416 testes**, todos passando (núcleo, UI com `QT_QPA_PLATFORM=offscreen`
e exportação). `tests/test_ui.py` cobre os fluxos que já quebraram e os recursos
novos: preenchimento/ordenação das tabelas, conclusão da análise habilitando as
dezoito abas, pré-visualização do texto completo, exportação da nuvem em PNG, exibição
de avisos, abas de referências/citações/personalização, sentimentos por domínio,
argumentos, definições, linha do tempo normalizada, mapa mental, grafo de citações,
comparação, análise de corpus, relatórios de IA, matriz de extração, PRISMA 2020 e
checklist, modelos de exportação, histórico, editor de stoplist e a sub-aba
**Modelos (opcional)**. Os testes
`tests/test_academic.py` e `tests/test_academic_integration.py` cobrem IMRaD,
função das citações, metodologia, lacunas, matriz de estudos, PT/EN, seções
combinadas, documento sem seção e os sete formatos de exportação. Os testes
`tests/test_discourse.py` e `tests/test_discourse_integration.py` cobrem
retórica, Toulmin (inclusive claims de reserva), CDA sem juízo de poder,
posicionamento agregado, enquadramento, comparação entre documentos, a fachada
que isola falhas e os sete formatos de exportação. Os testes
`tests/test_knowledge.py` e `tests/test_knowledge_integration.py` cobrem relações,
ontologia editável e exportações RDF/JSON-LD/OWL/CSV, terminologia, eventos,
afirmações sem fact-checking, consistência determinística, paráfrase, versões,
offsets exatos e os sete formatos de exportação. Os testes
`tests/test_exploration.py` e `tests/test_exploration_integration.py` cobrem a
busca contextual (booleana, proximidade, lemma, variante e regex), os spans e o
destaque, o catálogo e os filtros cruzados, o painel de pesquisa com persistência
e exportação Markdown/CSV/JSON, as perguntas investigativas e o desligamento da
fase. Os testes
`tests/test_models.py` cobrem capacidades, motores fake, contrato de evidência,
opt-in do Ollama, comparação descritiva, relatório Markdown, round-trip de
configuração, integração e ausência do bloco por padrão. Os testes usam
uma pasta de dados temporária (`Semantorium_DATA_DIR`) para não alterar as preferências
da máquina.

Análise headless (sem interface):

```powershell
.\.venv\Scripts\python.exe -m tools.cli_analyze documento.pdf
```

Amostras incluídas:

- `samples/texto_demo.md` — texto em português com citações e autores;
- `samples/scan_demo.pdf` — PDF **sem camada de texto** (imagem), usado para
  validar o OCR. Pode ser regenerado com `tools\make_scan_sample.py`.

---

## Estrutura do projeto

```
Semantorium/
├── agents/           # Agentes de desenvolvimento (escopo por área)
├── core/             # Lógica pura, sem UI
│   ├── extractor.py      extração multi-formato + OCR
│   ├── language.py       detecção e configuração de idioma
│   ├── textproc.py       tokenização/lematização com fallback
│   ├── analysis.py       orquestrador do relatório
│   ├── summary.py        resumo (TF-IDF + posição + MMR; LSA/LexRank opcionais)
│   ├── keywords.py       palavras-chave (YAKE)
│   ├── citations.py      detecção de citações
│   ├── bibliography.py   extração de referências e pareamento com citações
│   ├── reference_model.py    modelo intermediário, tipos, confiança e dedup
│   ├── reference_extract.py  segmentação e extração determinística
│   ├── reference_format.py   formatação em 12 estilos + citações no corpo
│   ├── bibliography_dedup.py  deduplicação exata/possível
│   ├── reference_import.py     importação BibTeX/RIS
│   ├── citation_graph.py grafo de citações (SVG/HTML)
│   ├── quotes.py         citações diretas com atribuição
│   ├── onomastic.py      índice onomástico editável
│   ├── concepts.py       conceitos principais (n-gramas)
│   ├── coocurrence.py    rede de coocorrência + árvore + PyVis
│   ├── semantic.py       tópicos, similaridade, agrupamentos
│   ├── sentiment.py      análise de sentimentos offline (domínios e explicações)
│   ├── argument.py       mapa de argumentos
│   ├── definitions.py    definições explícitas
│   ├── timeline.py       linha do tempo (datas numéricas, séculos, décadas)
│   ├── temporal_chart.py linha do tempo temporal (eventos normalizados)
│   ├── mindmap.py        mapa mental (SVG/HTML/Mermaid/Markdown)
│   ├── export_mindmap.py exportação do mapa mental (SVG/PNG/PDF)
│   ├── compare.py        comparação entre dois textos
│   ├── corpus.py         corpus: perfis, matriz N×N, pares, clusters, duplicatas
│   ├── extraction_matrix.py  matriz de extração de metadados + perguntas
│   ├── prisma.py         checklist PRISMA 2020 + critérios
│   ├── prisma_checklist.py  itens e subitens do checklist PRISMA 2020
│   ├── coauthorship.py  mapa de coautoria (autores × citadores)
│   ├── pdf_assets.py     figuras e tabelas extraídas de PDFs
│   ├── embeddings.py    embeddings locais (sentence-transformers) + cache + TF-IDF
│   ├── ollama.py         assistente local opcional (Ollama, stdlib)
│   ├── i18n.py           internacionalização (13 idiomas, data/i18n)
│   ├── ner.py            NER opcional via spaCy e modelos locais
│   ├── userdata.py       preferências, recentes, favoritos, histórico, modelos
│   ├── sections.py       separação corpo/referências
│   ├── stopwords.py      stoplist por idioma, persistente
│   ├── kwic.py           concordância
│   ├── readability.py    legibilidade e riqueza lexical
│   ├── lexicometry.py    frequência, diversidade, entropia, dispersão, Zipf e Heaps
│   ├── ngrams.py         n-gramas e comparação entre documentos
│   ├── collocations.py   PMI, G², t-score, Dice e associação diferencial
│   ├── lexical_variation.py  variação por seção, janela e ganho/perda de peso
│   ├── topic_temporal.py temas agrupados por marcos temporais citados
│   ├── pos.py            POS e dependências (spaCy opcional + fallback declarado)
│   ├── syntax.py         passiva, coordenação/subordinação e período
│   ├── stylometry.py     frases, pontuação, palavras funcionais, repetição e Delta
│   ├── semantic_fields.py campos semânticos por léxico curado PT/EN
│   ├── discourse_markers.py marcadores discursivos com contexto e ambiguidade
│   ├── coreference.py    correferência heurística conservadora
│   ├── section_analysis.py análise por seção e agregação por offset
│   ├── linguistics.py    fachada dos analisadores linguísticos
│   ├── imrad.py          mapa IMRaD por títulos, heurística e ambivalência
│   ├── citation_function.py função provável e polaridade das citações
│   ├── methodology.py    metodologia declarada, sem nota de qualidade
│   ├── research_gaps.py  lacunas observadas × hipóteses sugeridas
│   ├── lit_review.py     matriz de estudos com coluna de lacunas
│   ├── academic.py       fachada da análise acadêmica
│   ├── rhetoric.py       ethos, pathos e logos com trecho e confiança
│   ├── toulmin.py        claim, grounds, warrant, backing, qualifier e rebuttal
│   ├── cda.py            agência, nomeação, modalização e pressuposição (sem juízo de poder)
│   ├── stance.py         posicionamento por alvo declarado, com ambivalência
│   ├── framing.py        eixos de enquadramento e comparação entre documentos
│   ├── discourse_compare.py afirmações alinhadas/contraditórias e agentes
│   ├── discourse.py      fachada interpretativa da análise do discurso
│   └── wordcloud_gen.py  nuvem de palavras (paletas, fundo, máscaras)
├── ui/               # Interface PySide6
│   ├── views/            abas de análise (load, overview, words, graphs, citations, advanced, compare, corpus, ai_reports, export)
│   ├── dialogs/          stoplist, histórico, assistente, PRISMA, PDF assets, busca global
│   ├── mindmap_editor.py editor visual do mapa mental
│   ├── theme.py          tema claro/escuro (QSS)
│   └── worker.py         workers (QtConcurrent): análise, carregar, exportar, Ollama
├── reports/          # Exportadores HTML/PDF/JSON/TXT/CSV/XLSX + corpus + checklist/office
├── tests/            # Núcleo, UI (pytest-qt) e exportação
├── installer/        # Script do Inno Setup
├── tools/            # CLI headless e utilitários (ícone, PDF de teste)
├── data/  assets/    # Recursos (i18n em data/i18n/*.json)
├── samples/          # Amostras de texto/PDF
├── main.py           # Ponto de entrada
├── Semantorium.spec       # Empacotamento PyInstaller (completo e Lite)
├── build.ps1         # Build completo + instalador
├── build_lite.ps1    # Build Lite (sem OCR/WebEngine)
├── build_installer.ps1  # Gera o instalador Inno Setup
├── ROADMAP.md        # Fases do projeto
├── docs/             # Contratos e avaliações (evidências, viabilidade, assinatura)
└── SPEC.md           # Especificação funcional
```

---

## Planejamento (v1.0+)

O ciclo seguinte está descrito no [`ROADMAP.md`](ROADMAP.md) e parte de uma
camada transversal de resultados e evidências:

- **Fase 14** — camada de resultados/evidências concluída: `AnalysisResult`, offsets, página/seção e retrocompatibilidade
- **Fase 15** — lexicometria, n-gramas, colocações e variação lexical concluídos (métricas, UI, exportações e testes)
- **Fase 16** — POS/sintaxe, estilometria, campos semânticos, marcadores e correferência concluídos (fallback sem spaCy, UI, exportações e testes)
- **Fase 17** — IMRaD, função das citações, metodologia declarada, lacunas observadas/hipóteses e matriz de estudos concluídos (aba **Pesquisa**, sete formatos de exportação e testes PT/EN)
- **Fase 18** — retórica, Toulmin, CDA, stance e framing concluídos (aba **Discurso**, natureza interpretativa, comparação entre documentos e testes próprios)
- **Fase 19** — relações, ontologia editável, terminologia, eventos, afirmações sem fact-checking, consistência determinística, paráfrase e versões concluídos (abas **Conhecimento** e **Consistência**, sete formatos de exportação e testes próprios)
- **Fase 20** — busca contextual, painel de evidências e painel de pesquisa concluídos (aba **Explorar**, filtros persistentes e exportações)
- **Fase 21** — camada opcional de modelos locais concluída (spaCy/Stanza, embeddings, correferência neural, Ollama opt-in e comparação descritiva), fora do build padrão

A avaliação de viabilidade das 28 sugestões está em
[`docs/AVALIACAO_SUGESTOES.md`](docs/AVALIACAO_SUGESTOES.md) e o contrato técnico
em [`docs/EVIDENCE_MODEL.md`](docs/EVIDENCE_MODEL.md).

---

## Privacidade

Nenhuma requisição de rede é feita em tempo de execução. Não há telemetria.
Todos os modelos e arquivos ficam locais.

O assistente local **Ollama** (opcional, desativado por padrão) conversa apenas
com um servidor Ollama na própria máquina (`http://localhost:11434`), quando
habilitado pelo usuário e com o servidor em execução. Nenhuma outra rede é
utilizada.

---

## Licença

Distribuído sob a licença **MIT**. Copyright © 2026 Mateus Filipe de Lima
Pelanda (Umbalab). Consulte [`LICENSE`](LICENSE) para o texto completo.

O programa usa bibliotecas de terceiros com suas próprias licenças (PySide6/Qt,
spaCy, scikit-learn, NumPy, NetworkX, matplotlib, wordcloud, Pillow, PyVis,
ReportLab, openpyxl, PyMuPDF, python-docx, YAKE e sumy).
