# Projeto de Grafos - web-RedditEmbeddings

Este projeto analisa o dataset **web-RedditEmbeddings** do SNAP como uma rede de similaridade entre comunidades do Reddit. Cada subreddit e representado por um vetor de 300 dimensoes; o grafo tratado liga comunidades com embeddings parecidos por similaridade de cosseno.

Repositorio da entrega: https://github.com/guneves/TrabalhoGrafos

## Determinacao pela matricula

Matricula usada: `224116475`.

```text
soma dos digitos = 32
ultimos dois digitos = 75
ultimos dois digitos + 1 = 76
32 x 76 = 2432
2432 mod 129 = 110
grafo final = G110
```

Nesta entrega, o `G110` corresponde ao dataset recebido **web-RedditEmbeddings**.

## Dataset

- Fonte: https://snap.stanford.edu/data/web-RedditEmbeddings.html
- Nome: web-RedditEmbeddings
- Tipo: Reddit Embeddings
- Dominio: Online communities
- Tamanho informado pelo SNAP: 118.381 usuarios e 51.278 subreddits
- Vetores: 300 dimensoes
- Periodo dos dados: Jan/2014 a Abr/2017

Arquivos brutos oficiais usados localmente em `data/raw`:

```text
data/raw/web-redditEmbeddings-subreddits.csv
data/raw/web-redditEmbeddings-users.csv
```

O grafo analisado usa diretamente o arquivo de subreddits, pois os vertices foram definidos como comunidades online. O arquivo de usuarios fica preservado em `raw` como parte do dataset original do SNAP.

## Dados grandes e GitHub

Os CSVs brutos do SNAP nao devem ser enviados para o GitHub comum, pois passam do limite recomendado de tamanho de arquivo:

- `data/raw/web-redditEmbeddings-subreddits.csv`: cerca de 145 MB
- `data/raw/web-redditEmbeddings-users.csv`: cerca de 335 MB

Por isso, `.gitignore` ignora `data/raw/*.csv`. A pasta `data/raw` fica no repositorio apenas com `.gitkeep`, e os CSVs devem ser baixados localmente com:

```powershell
python scripts/download_data.py
```

Os arquivos tratados em `data/processed`, os graficos em `results` e o relatorio final em `LaTeX` permanecem no projeto para consulta e reproducibilidade da entrega.

## Como executar

Use Python 3.11+ com as dependencias de `requirements.txt`.

```powershell
pip install -r requirements.txt
python scripts/download_data.py
python scripts/build_graph.py --k 10
python scripts/analyze_graph.py --benchmark-runs 30 --robustness-runs 30 --path-samples 16 --random-graphs 5
```

Atalho equivalente para executar o pipeline completo:

```powershell
python main.py
```

Para refazer o download dos CSVs oficiais de subreddits e usuarios:

```powershell
python scripts/download_data.py
```

Para refazer apenas a visualizacao do grafo a partir dos CSVs ja processados, sem recalcular o kNN completo:

```powershell
python scripts/build_graph.py --visualization-only --visualization-n 420
```

## Saidas principais

- `data/processed/nodes.csv`: vertices tratados
- `data/processed/edges.csv`: arestas do grafo de similaridade
- `data/processed/graph_metadata.json`: parametros de construcao
- `results/analysis_results.json`: metricas e respostas numericas
- `results/*.svg` e `results/*.png`: graficos, histograma, CCDF, boxplots e visualizacao
- `results/degree_log_pk.svg` e `.png`: grafico log(P(k)) versus log(k)
- `results/degree_model_comparison.svg` e `.png`: comparacao visual com Poisson e normal
- `results/benchmark_raw_times.csv`: tempos individuais das 30 execucoes de cada algoritmo
- `results/robustness_runs.csv`: metricas das 30 repeticoes de robustez aleatoria e do ataque por centralidade
- `LaTeX/main.tex`: relatorio final em formato WebMedia/Overleaf
- `LaTeX/224116475.pdf`: PDF final para envio no Moodle
- `LaTeX/artigo_webmedia_referencias.bib`: referencias BibTeX para compilar a versao WebMedia

## Como compilar a versao WebMedia

A versao em artigo cientifico foi escrita para o template oficial WebMedia
do Overleaf. A pasta `LaTeX` reune os arquivos prontos para upload:
`main.tex`, `artigo_webmedia_referencias.bib` e a subpasta `results`
com todas as imagens usadas no artigo.

Para compilar no Overleaf, crie um projeto a partir do template
`webmedia-template`, envie o conteudo da pasta `LaTeX` e deixe
`main.tex` como arquivo principal. As imagens usadas sao:

```text
artigo_webmedia_referencias.bib
results/graph_visualization.png
results/degree_histogram.png
results/degree_ccdf.png
results/algorithm_times.png
results/degree_log_pk.png
results/degree_model_comparison.png
results/robustness.png
```

O arquivo final para envio no Moodle fica em `LaTeX/224116475.pdf`.

## Observacao metodologica

O SNAP fornece embeddings, nao uma lista explicita de arestas. Portanto, o tratamento dos dados transforma vetores em uma rede nao direcionada e ponderada: para cada subreddit, conectamos seus `k` vizinhos mais proximos por similaridade de cosseno. As metricas estruturais sao calculadas sobre a versao nao ponderada desse grafo quando a definicao classica exige distancias por numero de arestas; os algoritmos de menor caminho ponderado usam peso `1 - similaridade`.

Por padrao, o pipeline usa todos os subreddits do arquivo `web-redditEmbeddings-subreddits.csv`. A opcao `--sample-size` continua disponivel apenas para testes rapidos de desenvolvimento. Bellman-Ford e Floyd-Warshall sao medidos em subgrafos por custo computacional, e diametro, raio e comprimento medio dos caminhos sao estimados na maior componente por amostragem de fontes quando o grafo completo torna o calculo exato custoso. Nessas metricas amostradas, o relatorio agora explicita o IC 95% do comprimento medio e marca diametro/raio como limites observados na amostra.
