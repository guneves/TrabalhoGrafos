import csv
import html
import json
import math
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage
from reportlab.platypus import Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
REPORT_MD = ROOT / "relatorio_web_reddit_embeddings.md"
REPORT_PDF = ROOT / "relatorio_web_reddit_embeddings.pdf"


def fmt(value, digits=4):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def load_results():
    return json.loads((RESULTS / "analysis_results.json").read_text(encoding="utf-8"))


def load_degree_rows():
    with (RESULTS / "degree_distribution.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def student_rule(result):
    return result.get(
        "student_graph_rule",
        {
            "student_id": "224116475",
            "digit_sum": 32,
            "last_two_digits": 75,
            "last_two_plus_one": 76,
            "product": 2432,
            "modulo_129": 110,
            "graph_number": 110,
            "graph_label": "G110",
            "assigned_dataset": "web-RedditEmbeddings",
        },
    )


def complexity_for(result, algorithm):
    key = algorithm.replace(" (subgrafo)", "")
    return result["complexities"].get(key, result["complexities"].get(algorithm, "O(?)"))


def benchmark_interpretation(algorithm):
    if algorithm == "BFS":
        return "alcancou a componente da origem"
    if algorithm == "DFS":
        return "confirma percorribilidade da componente da origem"
    if algorithm == "Verificacao de Eulerianidade":
        return "resultado falso por haver vertices de grau impar"
    if algorithm == "Dijkstra":
        return "menores caminhos ponderados aplicaveis com pesos nao negativos"
    if "Bellman-Ford" in algorithm:
        return "executado em subgrafo; redundante frente ao Dijkstra, mas valido"
    if "Floyd-Warshall" in algorithm:
        return "limitado a subgrafo por custo cubico no grafo completo"
    if algorithm == "Tarjan":
        return "identificou pontos de articulacao e pontes"
    if algorithm == "Kruskal/MST":
        return "gera MST se conectado; caso contrario, floresta geradora minima"
    return "resultado interpretado no texto"


def degree_table_rows(rows):
    shown = rows[:10]
    if rows and rows[-1] not in shown:
        shown.append(rows[-1])
    out = []
    for row in shown:
        ln_k = float(row["ln_k"]) if row["ln_k"] else math.nan
        ln_p = float(row["ln_p_k"]) if row["ln_p_k"] else math.nan
        out.append(
            f"| {int(row['degree'])} | {int(row['frequency'])} | {fmt(float(row['p_k']), 6)} | "
            f"{fmt(ln_k, 4)} | {fmt(ln_p, 4)} |"
        )
    return "\n".join(out)


def benchmark_rows(result):
    rows = []
    for b in result["benchmarks"]:
        applicable = "Sim, em subgrafo" if "subgrafo" in b["algorithm"] else "Sim"
        rows.append(
            f"| {b['algorithm']} | {applicable} | {complexity_for(result, b['algorithm'])} | "
            f"{fmt(b['mean_seconds'], 6)} | {fmt(b['sd_seconds'], 6)} | +/- {fmt(b['ci95_seconds'], 6)} | "
            f"{b['last_result']} | {benchmark_interpretation(b['algorithm'])} |"
        )
    return "\n".join(rows)


def markdown_report(result):
    s = result["structural"]
    sw = result["small_world"]
    power = result["power_law"]
    rob = result["robustness"]["summary"]
    rule = student_rule(result)
    degree_rows = load_degree_rows()
    component_sizes = ", ".join(map(str, s["component_sizes"][:10]))
    if len(s["component_sizes"]) > 10:
        component_sizes += ", ..."
    cluster_ratio = sw["graph_clustering"] / sw["random_clustering"] if sw["random_clustering"] else math.inf
    meta = result.get("metadata", {})
    is_connected = s["components"] == 1
    component_interpretation = (
        "todos os vertices pertencem a mesma componente"
        if is_connected
        else f"ha uma componente gigante com {s['largest_component_size']} vertices e {s['components'] - 1} componentes pequenas"
    )
    component_size_interpretation = (
        "a maior componente contem todo o grafo"
        if is_connected
        else "a maior componente concentra quase todos os vertices, mas o grafo nao e totalmente conectado"
    )
    connectivity_phrase = "conectada" if is_connected else "dominada por uma componente gigante"
    mst_label = "arvore geradora minima" if s["mst"]["is_spanning_tree"] else "floresta geradora minima"
    benchmark_by_name = {b["algorithm"]: b for b in result["benchmarks"]}
    bfs_reached = benchmark_by_name.get("BFS", {}).get("last_result", s["largest_component_size"])
    dfs_reached = benchmark_by_name.get("DFS", {}).get("last_result", s["largest_component_size"])
    dijkstra_reached = benchmark_by_name.get("Dijkstra", {}).get("last_result", s["largest_component_size"])
    uses_all_vertices = bool(meta.get("uses_all_subreddit_vertices"))
    graph_scope = (
        "grafo tratado com todos os subreddits"
        if uses_all_vertices
        else f"grafo tratado amostrado com {s['vertices']} subreddits"
    )
    scope_sentence = (
        f"As conclusoes se referem ao **grafo tratado com todos os {s['vertices']} subreddits carregados do arquivo oficial do SNAP**."
        if uses_all_vertices
        else f"As conclusoes se referem ao **grafo tratado/amostrado com {s['vertices']} subreddits**, extraido dos 51.278 subreddits informados pelo SNAP."
    )
    selection_row = (
        f"| Uso de vertices | Todos os subreddits do CSV oficial | 51.278 candidatos | {s['vertices']} vertices | atender a exigencia de usar todos os vertices disponiveis | elimina a amostragem de vertices |\n"
        if uses_all_vertices
        else f"| Amostragem | primeiros {s['vertices']} subreddits | 51.278 candidatos | {s['vertices']} vertices | reduzir custo de kNN e caminhos exatos | conclusoes limitadas a amostra |\n"
    )
    vertex_interpretation = (
        "quantidade de subreddits usados do arquivo oficial"
        if uses_all_vertices
        else "quantidade de subreddits na amostra tratada"
    )
    path_description = (
        "calculados por amostragem de fontes devido ao tamanho do grafo"
        if s["path_calculation_mode"] == "sampled"
        else "calculados exatamente"
    )
    path_ci = s.get("average_path_length_ci95", 0.0) or 0.0
    path_uncertainty = (
        f" media das fontes amostradas com IC 95% +/- {fmt(path_ci)}"
        if s.get("path_calculation_mode") == "sampled"
        else " valor exato na componente analisada"
    )
    diameter_note = "limite inferior observado por amostragem" if s.get("diameter_is_lower_bound") else "valor exato"
    radius_note = "limite superior observado por amostragem" if s.get("radius_is_upper_bound") else "valor exato"
    random_baseline = sw.get("random_baseline", {})
    random_path_stats = random_baseline.get("average_path_length", {})
    random_clustering_stats = random_baseline.get("clustering", {})
    random_path_text = (
        f"{fmt(random_path_stats.get('mean'))} +/- {fmt(random_path_stats.get('ci95', 0.0))}"
        if random_path_stats
        else fmt(sw["random_average_path_length"])
    )
    random_clustering_text = (
        f"{fmt(random_clustering_stats.get('mean'))} +/- {fmt(random_clustering_stats.get('ci95', 0.0))}"
        if random_clustering_stats
        else fmt(sw["random_clustering"])
    )
    random_runs = random_path_stats.get("runs", 1) if random_path_stats else 1
    power_mle_text = (
        f"MLE discreto: alpha = {fmt(power.get('alpha_mle'))}, xmin = {fmt(power.get('xmin'))}, "
        f"cauda com {fmt(power.get('tail_count'))} vertices ({fmt((power.get('tail_fraction') or 0) * 100, 2)}%), "
        f"KS = {fmt(power.get('ks_distance'))}."
        if power.get("alpha_mle") is not None
        else "MLE discreto indisponivel para esta distribuicao."
    )
    discussion_scope = (
        "O resultado depende da escolha de `k`. Como todos os subreddits disponiveis sao usados, nao ha amostragem de vertices; ainda assim, como o dataset original e embedding, qualquer grafo derivado exige uma regra metodologica de criacao de arestas."
        if uses_all_vertices
        else "O resultado depende da escolha de `k` e do tamanho da amostra. Valores maiores de `k` aumentariam densidade e poderiam reduzir diametro; valores menores poderiam fragmentar a rede. Como o dataset original e embedding, qualquer grafo derivado exige uma regra metodologica de criacao de arestas."
    )
    build_command = "python scripts/build_graph.py --k 10" if uses_all_vertices else f"python scripts/build_graph.py --sample-size {s['vertices']} --k 10"

    return f"""# Analise de Grafos: web-RedditEmbeddings ({graph_scope})

## Resumo

Este relatorio analisa o dataset **web-RedditEmbeddings** do SNAP como uma rede de similaridade entre subreddits. Como o arquivo original contem embeddings e nao uma lista explicita de arestas, o grafo foi construido por k-vizinhos mais proximos usando similaridade de cosseno. {scope_sentence} A rede tratada tem **{s['vertices']} vertices**, **{s['edges']} arestas**, densidade **{fmt(s['density'], 6)}**, comprimento medio **{fmt(s['average_path_length'])}** ({path_uncertainty.strip()}), clusterizacao media **{fmt(s['average_clustering'])}** e **{s['triangles']} triangulos**.

## 1. Introducao

O objetivo do trabalho e aplicar conceitos de Teoria dos Grafos e Redes Complexas a um grafo real: tratamento de dados, analise estrutural, execucao de algoritmos classicos, small-world, lei de potencia, robustez e comparacao com modelos classicos. Todos os valores numericos foram extraidos dos artefatos do projeto, principalmente `results/analysis_results.json`, `results/benchmark_times.csv`, `results/benchmark_raw_times.csv` e `results/degree_distribution.csv`.

## 2. Descricao do grafo original

O dataset oficial e **web-RedditEmbeddings**, da categoria **Online communities**, com tipo **Reddit Embeddings**. A pagina do SNAP informa **118.381 usuarios**, **51.278 subreddits**, embeddings de **300 dimensoes** e dados extraidos de **janeiro de 2014 a abril de 2017**.

Fonte oficial: <https://snap.stanford.edu/data/web-RedditEmbeddings.html>

Arquivos brutos preservados:

- `data/raw/web-redditEmbeddings-subreddits.csv`
- `data/raw/web-redditEmbeddings-users.csv`

## 3. Determinacao do grafo pela matricula

A matricula informada no enunciado e **{rule['student_id']}**. A regra usada para determinar o grafo e:

```text
f(M) = ((soma dos digitos de M) x (ultimos dois digitos de M + 1)) mod 129
```

Calculo passo a passo:

1. Matricula usada: **{rule['student_id']}**.
2. Soma dos digitos: **{rule['digit_sum']}**.
3. Ultimos dois digitos: **{rule['last_two_digits']}**.
4. Ultimos dois digitos + 1: **{rule['last_two_plus_one']}**.
5. Multiplicacao: **{rule['digit_sum']} x {rule['last_two_plus_one']} = {rule['product']}**.
6. Resultado do modulo 129: **{rule['product']} mod 129 = {rule['modulo_129']}**.
7. Grafo final escolhido: **{rule['graph_label']}**.

Assim, a matricula determina a posicao do grafo em uma lista de 129 possibilidades. Para esta entrega, o grafo **{rule['graph_label']}** corresponde ao dataset recebido no enunciado: **{rule['assigned_dataset']}**.

## 4. Tratamento dos dados

O SNAP disponibiliza embeddings, nao uma lista pronta de arestas. Por isso, o tratamento necessario foi transformar vetores em uma rede de similaridade entre comunidades.

| Etapa | Tratamento aplicado | Antes | Depois | Justificativa | Impacto |
|---|---|---:|---:|---|---|
| Fonte bruta | Download e preservacao dos CSVs oficiais | 2 arquivos remotos | 2 arquivos em `data/raw` | garantir reproducibilidade | nao altera metricas |
| Escolha de vertices | Subreddits como vertices | 118.381 usuarios e 51.278 subreddits | 51.278 subreddits candidatos | foco em comunidades online | usuarios nao entram como vertices |
{selection_row.rstrip()}
| Normalizacao | vetores com norma 1 | embeddings de 300 dimensoes | embeddings normalizados | calcular similaridade de cosseno por produto interno | nao muda n; prepara arestas |
| Construcao de arestas | kNN por similaridade de cosseno | sem arestas explicitas | {s['edges']} arestas | transformar embeddings em grafo analisavel | define topologia |
| Simplificacao | uniao de pares kNN em grafo simples | vizinhancas direcionais possiveis | grafo simples nao direcionado | metricas exigidas assumem grafo simples | remove duplicidade de pares |
| Pesos | `1 - similaridade` | similaridade de cosseno | pesos nao negativos | menor peso indica maior semelhanca | permite Dijkstra/MST |
| Componentes | verificacao de conectividade | grafo tratado | {s['components']} componentes; maior com {s['largest_component_size']} vertices | identificar a estrutura conexa usada nos caminhos | caminhos {path_description} |

**Descricao do grafo tratado.** A versao analisada e uma rede simples, nao direcionada e ponderada de similaridade entre comunidades do Reddit. Cada vertice representa um subreddit; duas comunidades sao conectadas quando uma aparece entre os vizinhos semanticamente mais proximos da outra. Para metricas estruturais classicas, o grafo foi considerado sem peso; para algoritmos de caminho ponderado e MST, foi usado `1 - similaridade`.

## 5. Metodologia

As metricas estruturais foram calculadas sobre a versao nao ponderada quando a definicao classica depende do numero de arestas. Dijkstra, Bellman-Ford, Floyd-Warshall e Kruskal usaram pesos. Diametro, raio e comprimento medio dos caminhos foram estimados por **{s['path_sample_size']} fontes** na maior componente por causa do tamanho do grafo; nessa situacao, diametro e raio sao valores observados na amostra, e o comprimento medio tem IC 95% **+/- {fmt(path_ci)}**. Cada algoritmo foi executado **{result['benchmarks'][0]['runs']}** vezes. Conforme o enunciado, os intervalos de confianca de 95% usam **Normal/Z quando n >= 30** e **t-Student quando n < 30**; nesta execucao, os benchmarks usaram **{result['benchmarks'][0].get('ci95_method', 'Normal/Z')}**. Os tempos individuais de cada repeticao foram exportados em `results/benchmark_raw_times.csv`, enquanto `results/benchmark_times.csv` contem media, desvio padrao e IC 95%.

## 6. Analise estrutural obrigatoria

| Medida | Valor | Computada? | Interpretacao | Justificativa, se nao computada |
|---|---:|---|---|---|
| Numero de vertices | {s['vertices']} | Sim | {vertex_interpretation} | N/A |
| Numero de arestas | {s['edges']} | Sim | pares de comunidades semanticamente proximas | N/A |
| Grau minimo | {s['degree_min']} | Sim | efeito esperado do kNN com k=10 | N/A |
| Grau maximo | {s['degree_max']} | Sim | existe ao menos um hub semantico muito conectado | N/A |
| Grau medio | {fmt(s['degree_mean'])} | Sim | rede esparsa, mas com conexoes suficientes para formar uma componente gigante | N/A |
| Distribuicao de graus | `results/degree_distribution.csv` | Sim | cauda pesada e hubs aparecem na frequencia dos graus | N/A |
| Densidade | {fmt(s['density'], 6)} | Sim | apenas pequena fracao dos pares possiveis esta conectada | N/A |
| Numero de componentes conexas | {s['components']} | Sim | {component_interpretation} | N/A |
| Tamanho de cada componente | {component_sizes} | Sim | {component_size_interpretation} | N/A |
| Diametro | {s['diameter']} | Sim | {diameter_note} no modo {s['path_calculation_mode']} | N/A |
| Raio | {s['radius']} | Sim | {radius_note} no modo {s['path_calculation_mode']} | N/A |
| Comprimento medio dos caminhos | {fmt(s['average_path_length'])} +/- {fmt(path_ci)} | Sim, modo {s['path_calculation_mode']} | poucos intermediarios separam comunidades | N/A |
| Clusterizacao media | {fmt(s['average_clustering'])} | Sim | ha forte agrupamento local | N/A |
| Numero de triangulos | {s['triangles']} | Sim | muitas triplas de subreddits semanticamente proximos | N/A |
| Visualizacao do grafo | `results/graph_visualization.svg` | Sim, reduzida | amostra visual para evitar sobreposicao excessiva | N/A |

![Visualizacao do grafo](results/graph_visualization.svg)

![Histograma de graus](results/degree_histogram.svg)

![CCDF da distribuicao de graus](results/degree_ccdf.svg)

## 7. Algoritmos da disciplina

| Algoritmo | Objetivo, funcionamento e condicoes | Complexidade teorica |
|---|---|---|
| BFS | visita a origem, depois seus vizinhos, depois os vizinhos dos vizinhos; aplicavel para medir alcancabilidade em grafos ponderados ou nao ponderados quando o peso nao importa | O(V + E) |
| DFS | explora um ramo ate o fim antes de retroceder; aplicavel para percorrimento e base de analises de conectividade | O(V + E) |
| Eulerianidade | checa se o grafo nao direcionado e conectado e se todos os graus sao pares | O(V + E) |
| Dijkstra | relaxa arestas em ordem de distancia minima por fila de prioridade; aplicavel porque `1 - similaridade` e nao negativo | O((V + E) log V) |
| Bellman-Ford | relaxa todas as arestas repetidamente e tolera pesos negativos; aqui e aplicavel, mas redundante, pois nao ha pesos negativos | O(VE) |
| Floyd-Warshall | atualiza uma matriz de distancias considerando cada vertice como intermediario; aplicavel conceitualmente, mas caro no grafo completo | O(V^3) |
| Tarjan | usa tempos de descoberta e valores `low-link` para identificar pontos de articulacao e pontes na versao nao direcionada | O(V + E) |
| Kruskal/MST | ordena arestas por peso e une componentes com union-find ate formar a MST; se o grafo for desconexo, o resultado e uma floresta geradora minima | O(E log E) |

| Algoritmo | Aplicavel? | Complexidade teorica | Tempo medio (s) | Desvio padrao (s) | IC 95% (s) | Resultado principal | Interpretacao |
|---|---|---|---:|---:|---:|---|---|
{benchmark_rows(result)}

![Tempos por algoritmo](results/algorithm_times.svg)

Interpretacao dos resultados:

- BFS alcancou {bfs_reached} vertices e DFS alcancou {dfs_reached}, isto e, a componente da origem usada nos testes.
- O grafo nao e euleriano, pois nem todos os vertices tem grau par.
- Dijkstra alcancou {dijkstra_reached} vertices com pesos nao negativos, correspondentes a componente da origem.
- Bellman-Ford foi executado em subgrafo de 120 vertices e Floyd-Warshall em subgrafo de 70 vertices, com justificativa tecnica de custo.
- Tarjan encontrou **{s['articulation_points']}** pontos de articulacao e **{s['bridges']}** ponte(s).
- Kruskal gerou uma **{mst_label}** com **{s['mst']['forest_edges']}** arestas e peso total **{fmt(s['mst']['total_weight'])}**.

## 8. Analise de small-world

Pergunta obrigatoria: **o grafo apresenta indicios de propriedade small-world? Faz sentido para seu grafo? Qual e a implicacao pratica?**

| Metrica | Grafo real | Grafos aleatorios equivalentes ({random_runs} execucoes) | Comparacao |
|---|---:|---:|---|
| Comprimento medio dos caminhos | {fmt(sw['graph_average_path_length'])} | {random_path_text} | mesma ordem de grandeza, embora o real seja maior |
| Clusterizacao media | {fmt(sw['graph_clustering'])} | {random_clustering_text} | grafo real tem clustering {fmt(cluster_ratio, 2)} vezes maior |

Conclusao: ha **indicios relevantes, de moderados a fortes, de small-world**. O comprimento medio dos caminhos permanece pequeno em termos praticos e da mesma ordem do aleatorio, embora seja maior que o do grafo aleatorio equivalente; ao mesmo tempo, a clusterizacao real e muito maior. Isso faz sentido para subreddits, pois comunidades tematicas formam grupos locais densos, mas ainda se conectam por caminhos curtos via interesses intermediarios. A implicacao pratica e comunicacao/propagacao eficiente entre comunidades com forte agrupamento local.

## 9. Analise de lei de potencia

Pergunta obrigatoria: **a distribuicao de graus sugere uma lei de potencia?**

A distribuicao de graus sugere cauda pesada e presenca de hubs, mas nao permite afirmar rigorosamente uma lei de potencia sem teste estatistico completo. A CCDF em escala log-log teve inclinacao estimada **{fmt(power['gamma_ccdf_slope'])}** e **R2 = {fmt(power['r2_loglog'])}**. Como melhoria, tambem foi aplicado um ajuste discreto exploratorio por maxima verossimilhanca: {power_mle_text} Tambem foi gerado o grafico pedido de `log(P(k))` versus `log(k)`, separado da CCDF.

| Grau k | Frequencia | P(k) | log(k) | log(P(k)) |
|---:|---:|---:|---:|---:|
{degree_table_rows(degree_rows)}

![Grafico log(P(k)) versus log(k)](results/degree_log_pk.svg)

![Comparacao de P(k) com Poisson e normal](results/degree_model_comparison.svg)

Como contraponto visual, o grafico compara a distribuicao observada com uma Poisson de media igual ao grau medio e uma normal com a mesma media e desvio padrao dos graus observados. Como o eixo Y esta em log10, probabilidades visualmente nulas usam um piso numerico apenas para renderizacao. As distribuicoes homogeneas concentram a massa ao redor da media, enquanto o grafo observado preserva uma cauda mais longa, com hubs de grau elevado.

Interpretacao: ha muitos vertices em graus baixos ou moderados, e poucos vertices de grau muito alto, como o grau maximo **{s['degree_max']}**, muito acima do grau medio **{fmt(s['degree_mean'])}**. Portanto, ha indicios compativeis com lei de potencia e rede parcialmente livre de escala, mas a evidencia e sugestiva, nao conclusiva.

## 10. Analise de robustez

Pergunta obrigatoria: **o grafo e robusto a remocao aleatoria de 5% dos vertices? E a remocao dos 5% mais centrais?**

Foram removidos **{result['robustness']['remove_count']}** vertices, equivalentes a 5% da rede tratada. A remocao aleatoria foi repetida **{len(result['robustness']['random_runs'])}** vezes; o ataque direcionado removeu os 5% de maior grau. Como a remocao pode fragmentar a rede, o comprimento medio dos caminhos foi calculado **na maior componente conexa remanescente** e, por custo computacional, estimado por amostragem de fontes nessa componente.

| Metrica | Grafo original | Remocao aleatoria 5% | Remocao dos 5% mais centrais | Interpretacao |
|---|---:|---:|---:|---|
| Tamanho da maior componente | {s['vertices']} | {fmt(rob['largest_component_size']['mean'])} +/- {fmt(rob['largest_component_size'].get('ci95', 0.0))} | {fmt(rob['largest_component_size']['central_attack'])} | ataque central reduz mais a maior componente |
| Numero de componentes | {s['components']} | {fmt(rob['components']['mean'])} +/- {fmt(rob['components'].get('ci95', 0.0))} | {fmt(rob['components']['central_attack'])} | ataque central fragmenta a rede |
| Comprimento medio dos caminhos | {fmt(s['average_path_length'])} | {fmt(rob['average_path_length_lcc']['mean'])} +/- {fmt(rob['average_path_length_lcc'].get('ci95', 0.0))} | {fmt(rob['average_path_length_lcc']['central_attack'])} | caminhos crescem mais no ataque central |
| Fracao de nos isolados | 0 | {fmt(rob['isolated_fraction']['mean'])} +/- {fmt(rob['isolated_fraction'].get('ci95', 0.0))} | {fmt(rob['isolated_fraction']['central_attack'])} | ataque central gera isolados |

![Boxplots de robustez](results/robustness.svg)

Resposta: o grafo e muito robusto a falhas aleatorias, pois a maior componente reteve em media **{fmt(rob['largest_component_fraction']['mean'] * 100, 2)}%** dos vertices restantes. A remocao dos 5% vertices de maior grau e mais danosa: fragmenta a rede em **{fmt(rob['components']['central_attack'])}** componentes, gera nos isolados e aumenta o comprimento medio dos caminhos. Portanto, ha vulnerabilidade maior a ataques direcionados do que a falhas aleatorias.

## 11. Descoberta mais interessante

A descoberta mais interessante foi que a rede de subreddits e altamente agrupada e ao mesmo tempo redundante. Isso aparece no clustering medio **{fmt(s['average_clustering'])}**, nos **{s['triangles']} triangulos** e no resultado de Tarjan: **{s['articulation_points']} pontos de articulacao** e **{s['bridges']} pontes**. Em termos praticos, comunidades semanticamente proximas nao dependem de uma unica rota: mesmo quando hubs sao removidos, a maior componente ainda retem **{fmt(rob['largest_component_fraction']['central_attack'] * 100, 2)}%** dos vertices restantes.

## 12. Comparacao com modelos classicos

Pergunta obrigatoria: **o grafo se aproxima de Erdos-Renyi, Barabasi-Albert ou Watts-Strogatz?**

| Modelo | Evidencias a favor | Evidencias contra | Grau de aproximacao |
|---|---|---|---|
| Erdos-Renyi | rede esparsa com componente gigante | clusterizacao real muito maior que a aleatoria; grau maximo alto | fraca |
| Barabasi-Albert | hubs, cauda pesada e vulnerabilidade maior a ataque central | clustering local muito alto e arestas derivadas de embeddings, nao crescimento preferencial observado | parcial |
| Watts-Strogatz | alto clustering, caminhos curtos e indicios de small-world | mecanismo de construcao e similaridade semantica, nao religacao aleatoria | mais proximo |

Conclusao: a aproximacao mais forte e com **Watts-Strogatz/small-world**, com tracos parciais de Barabasi-Albert por causa dos hubs. A aproximacao com Erdos-Renyi e fraca.

## 13. Discussao critica

{discussion_scope} Valores maiores de `k` aumentariam densidade e poderiam reduzir diametro; valores menores poderiam fragmentar a rede. Bellman-Ford e Floyd-Warshall foram executados em subgrafos por custo computacional, portanto seus tempos medem a implementacao e a aplicabilidade conceitual, nao o custo do grafo completo. A analise de lei de potencia agora combina diagnostico visual e ajuste MLE discreto exploratorio, mas ainda nao substitui um estudo estatistico completo com bootstrap de p-valor e comparacoes formais adicionais.

## 14. Conclusao

O projeto aplicou tratamento de dados, construcao de grafo, analise estrutural, algoritmos classicos, small-world, lei de potencia e robustez ao dataset web-RedditEmbeddings. A rede tratada e {connectivity_phrase}, pouco densa, altamente clusterizada, robusta a falhas aleatorias e mais sensivel a remocao de hubs semanticos.

## 15. Referencias

- SNAP. Reddit User and Subreddit Embeddings. <https://snap.stanford.edu/data/web-RedditEmbeddings.html>
- Kumar, S.; Zhang, X.; Leskovec, J. Predicting Dynamic Embedding Trajectory in Temporal Interaction Networks. KDD, 2019.
- Kumar, S.; Hamilton, W. L.; Leskovec, J.; Jurafsky, D. Community Interaction and Conflict on the Web. WWW, 2018.

## 16. Apendice: codigo principal

O codigo completo esta organizado em scripts reprodutiveis:

- `scripts/download_data.py`: baixa os CSVs oficiais.
- `scripts/build_graph.py`: le embeddings, normaliza vetores, constroi kNN, salva vertices/arestas e visualizacao.
- `scripts/analyze_graph.py`: calcula metricas, algoritmos, tempos, small-world com grafos aleatorios, lei de potencia com MLE exploratorio e robustez.
- `scripts/generate_report.py`: gera este Markdown e PDF.

Funcoes principais implementadas: `load_embeddings`, `build_knn_edges`, `load_graph`, `bfs_order`, `dfs_order`, `dijkstra`, `bellman_ford`, `floyd_warshall`, `tarjan_articulation_bridges`, `mst_kruskal`, `benchmark_algorithms`, `power_law_fit`, `robustness` e `markdown_report`.

## 17. Como reproduzir

Pipeline detalhado:

```powershell
pip install -r requirements.txt
{build_command}
python scripts/analyze_graph.py --benchmark-runs 30 --robustness-runs 30 --path-samples 16 --random-graphs 5
python scripts/generate_report.py
```

Atalho equivalente:

```powershell
python main.py
```

## 18. Checklist final obrigatorio

| Item obrigatorio | Atendido? | Onde aparece no relatorio |
|---|---|---|
| Calculo do grafo pela matricula | Sim | Secao 3 |
| Tratamento dos dados informado | Sim | Secao 4 |
| Numero de vertices | Sim | Secao 6 |
| Numero de arestas | Sim | Secao 6 |
| Grau minimo, maximo e medio | Sim | Secao 6 |
| Distribuicao de graus | Sim | Secoes 6 e 9; `results/degree_log_pk.svg` |
| Densidade | Sim | Secao 6 |
| Componentes conexas | Sim | Secao 6 |
| Tamanho das componentes | Sim | Secao 6 |
| Diametro | Sim | Secao 6 |
| Raio | Sim | Secao 6 |
| Comprimento medio dos caminhos | Sim | Secoes 6 e 8 |
| Clusterizacao media | Sim | Secoes 6 e 8 |
| Numero de triangulos | Sim | Secao 6 |
| Visualizacao do grafo | Sim | Secao 6 |
| BFS | Sim | Secao 7 |
| DFS | Sim | Secao 7 |
| Eulerianidade | Sim | Secao 7 |
| Dijkstra | Sim | Secao 7 |
| Bellman-Ford | Sim | Secao 7 |
| Floyd-Warshall | Sim | Secao 7 |
| Tarjan | Sim | Secao 7 |
| Prim ou Kruskal | Sim | Secao 7 |
| Complexidade teorica | Sim | Secao 7 |
| Tempo real observado | Sim | Secao 7 |
| Media, desvio padrao e IC | Sim | Secoes 7 e 10 |
| Small-world | Sim | Secao 8 |
| Lei de potencia | Sim | Secao 9 |
| Robustez aleatoria | Sim | Secao 10 |
| Robustez por centralidade | Sim | Secao 10 |
| Descoberta mais interessante | Sim | Secao 11 |
| Comparacao com modelos classicos | Sim | Secao 12 |
| Comparacao visual com Poisson/normal | Sim | Secao 9 |
| Codigo disponibilizado | Sim | Secao 16 e `scripts/` |
| README ou instrucao de execucao | Sim | Secao 17 e `README.md` |
"""


def add_image(story, path, width):
    image_path = Path(path)
    if not image_path.is_absolute():
        image_path = ROOT / image_path
    if image_path.suffix.lower() == ".svg" and image_path.with_suffix(".png").exists():
        image_path = image_path.with_suffix(".png")
    if image_path.exists():
        story.append(RLImage(str(image_path), width=width, height=width * 0.62, kind="proportional"))
        story.append(Spacer(1, 0.25 * cm))


def inline_markup(text):
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", escaped)
    return escaped


def markdown_table(story, lines, styles):
    rows = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.append([Paragraph(inline_markup(cell), styles["TableCell"]) for cell in cells])
    if not rows:
        return
    max_cols = max(len(row) for row in rows)
    for row in rows:
        while len(row) < max_cols:
            row.append(Paragraph("", styles["TableCell"]))
    usable_width = A4[0] - 2.4 * cm
    table = Table(rows, colWidths=[usable_width / max_cols] * max_cols, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#9ca3af")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.18 * cm))


def pdf_report_from_markdown(markdown_text):
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CodeBlock", fontName="Courier", fontSize=7, leading=9, leftIndent=0.2 * cm))
    styles.add(ParagraphStyle(name="TableCell", fontName="Helvetica", fontSize=5.8, leading=7))
    doc = SimpleDocTemplate(
        str(REPORT_PDF),
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.1 * cm,
        bottomMargin=1.1 * cm,
    )
    story = []
    lines = markdown_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            story.append(Spacer(1, 0.12 * cm))
            i += 1
            continue
        if line.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            story.append(Preformatted("\n".join(code), styles["CodeBlock"], maxLineLength=96))
            story.append(Spacer(1, 0.16 * cm))
            i += 1
            continue
        image_match = re.match(r"!\[(.*?)\]\((.*?)\)", line)
        if image_match:
            add_image(story, image_match.group(2), 15.5 * cm)
            i += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            markdown_table(story, table_lines, styles)
            continue
        if line.startswith("# "):
            story.append(Paragraph(inline_markup(line[2:]), styles["Title"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline_markup(line[3:]), styles["Heading2"]))
        elif line.startswith("- "):
            story.append(Paragraph("&bull; " + inline_markup(line[2:]), styles["BodyText"]))
        elif re.match(r"\d+\. ", line):
            story.append(Paragraph(inline_markup(line), styles["BodyText"]))
        else:
            story.append(Paragraph(inline_markup(line), styles["BodyText"]))
        i += 1
    doc.build(story)


def main():
    result = load_results()
    markdown_text = markdown_report(result)
    REPORT_MD.write_text(markdown_text, encoding="utf-8")
    pdf_report_from_markdown(markdown_text)
    print(f"Relatorio Markdown: {REPORT_MD}")
    print(f"Relatorio PDF: {REPORT_PDF}")


if __name__ == "__main__":
    main()
