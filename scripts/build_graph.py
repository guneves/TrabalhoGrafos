import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None
    ImageDraw = None


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "web-redditEmbeddings-subreddits.csv"
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"


def svg_escape(value: object) -> str:
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("use um inteiro positivo")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Constroi o grafo de similaridade entre subreddits.")
    parser.add_argument(
        "--sample-size",
        type=positive_int,
        default=None,
        help="Numero de subreddits lidos do CSV. Por padrao, le todos os vertices do arquivo.",
    )
    parser.add_argument("--k", type=positive_int, default=10, help="Numero de vizinhos mais proximos por vertice.")
    parser.add_argument("--block-size", type=positive_int, default=256, help="Tamanho do bloco para produto matricial.")
    parser.add_argument("--visualization-n", type=positive_int, default=350, help="Vertices usados na visualizacao SVG.")
    parser.add_argument(
        "--visualization-only",
        action="store_true",
        help="Regenera apenas a visualizacao usando data/processed, sem reconstruir o kNN.",
    )
    return parser.parse_args()


def load_embeddings(sample_size: int | None) -> tuple[list[str], np.ndarray]:
    if not RAW.exists():
        raise FileNotFoundError(f"Arquivo nao encontrado: {RAW}. Execute scripts/download_data.py.")
    df = pd.read_csv(RAW, header=None, nrows=sample_size)
    if df.empty:
        raise ValueError(f"Nenhuma linha encontrada em {RAW}.")
    names = df.iloc[:, 0].astype(str).tolist()
    x = df.iloc[:, 1:].to_numpy(dtype=np.float32)
    if x.ndim != 2 or x.shape[1] == 0:
        raise ValueError("CSV de embeddings precisa ter uma coluna de nome e colunas numericas de vetor.")
    if len(names) < 2:
        raise ValueError("Sao necessarios pelo menos dois vertices para construir o grafo kNN.")
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return names, x / norms


def load_processed_for_visualization() -> tuple[list[str], list[tuple[int, int, float, float]], np.ndarray]:
    nodes_path = PROCESSED / "nodes.csv"
    edges_path = PROCESSED / "edges.csv"
    if not nodes_path.exists() or not edges_path.exists():
        raise FileNotFoundError("Arquivos processados nao encontrados. Execute a construcao completa antes.")
    with nodes_path.open(encoding="utf-8") as f:
        labels = [row["label"] for row in csv.DictReader(f)]
    raw_labels, x = load_embeddings(len(labels))
    if raw_labels != labels:
        all_labels, all_x = load_embeddings(None)
        index = {label: i for i, label in enumerate(all_labels)}
        missing = [label for label in labels if label not in index]
        if missing:
            raise ValueError(f"Labels processados ausentes no CSV bruto: {missing[:3]}")
        x = all_x[[index[label] for label in labels]]
    edges = []
    with edges_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            edges.append(
                (
                    int(row["source"]),
                    int(row["target"]),
                    float(row["cosine_similarity"]),
                    float(row["weight"]),
                )
            )
    return labels, edges, x


def build_knn_edges(x: np.ndarray, k: int, block_size: int) -> list[tuple[int, int, float, float]]:
    n = x.shape[0]
    if n < 2:
        raise ValueError("Sao necessarios pelo menos dois vertices para construir arestas.")
    if k <= 0:
        raise ValueError("k precisa ser positivo.")
    if block_size <= 0:
        raise ValueError("block-size precisa ser positivo.")
    edge_best: dict[tuple[int, int], float] = {}
    for start in range(0, n, block_size):
        end = min(start + block_size, n)
        sims = x[start:end] @ x.T
        rows = np.arange(end - start)
        sims[rows, start + rows] = -np.inf
        take = min(k, n - 1)
        idx = np.argpartition(-sims, take - 1, axis=1)[:, :take]
        for local_i, neighbors in enumerate(idx):
            i = start + local_i
            ordered = neighbors[np.argsort(-sims[local_i, neighbors])]
            for j in ordered:
                a, b = (i, int(j)) if i < int(j) else (int(j), i)
                sim = float(sims[local_i, j])
                if (a, b) not in edge_best or sim > edge_best[(a, b)]:
                    edge_best[(a, b)] = sim
    edges = [(a, b, sim, 1.0 - sim) for (a, b), sim in edge_best.items()]
    edges.sort()
    return edges


def pca_2d(x: np.ndarray) -> np.ndarray:
    centered = x - x.mean(axis=0, keepdims=True)
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    coords = centered @ vt[:2].T
    return coords.astype(float)


def write_visualization(names: list[str], edges: list[tuple[int, int, float, float]], x: np.ndarray, limit: int) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    total_nodes = len(names)
    n = min(limit, total_nodes)
    full_degree = np.zeros(total_nodes, dtype=int)
    neighbors: list[list[int]] = [[] for _ in range(total_nodes)]
    for a, b, _, _ in edges:
        full_degree[a] += 1
        full_degree[b] += 1
        neighbors[a].append(b)
        neighbors[b].append(a)

    ranked = np.argsort(-full_degree).tolist()
    selected: list[int] = []
    selected_set: set[int] = set()

    def add_node(node: int) -> None:
        if node not in selected_set and len(selected) < n:
            selected.append(node)
            selected_set.add(node)

    for node in ranked[: min(40, n)]:
        add_node(node)
    for node in list(selected):
        for neighbor in sorted(neighbors[node], key=lambda item: full_degree[item], reverse=True):
            add_node(neighbor)
            if len(selected) >= n:
                break
        if len(selected) >= n:
            break
    for node in ranked:
        add_node(node)
        if len(selected) >= n:
            break

    local_index = {old: new for new, old in enumerate(selected)}
    coords = pca_2d(x[selected])
    min_xy = coords.min(axis=0)
    max_xy = coords.max(axis=0)
    span = np.maximum(max_xy - min_xy, 1e-9)
    pts = (coords - min_xy) / span
    width, height, pad = 1200, 840, 58
    pts[:, 0] = pad + pts[:, 0] * (width - 2 * pad)
    pts[:, 1] = pad + 34 + pts[:, 1] * (height - 2 * pad - 52)
    edge_lines = []
    for a, b, sim, _ in edges:
        if a in local_index and b in local_index:
            la = local_index[a]
            lb = local_index[b]
            opacity = max(0.04, min(0.32, (sim + 1.0) / 4.3))
            edge_lines.append(
                f'<line x1="{pts[la,0]:.1f}" y1="{pts[la,1]:.1f}" x2="{pts[lb,0]:.1f}" y2="{pts[lb,1]:.1f}" '
                f'stroke="#64748b" stroke-width="0.65" opacity="{opacity:.3f}" />'
            )
    local_degrees = full_degree[selected]
    top = set(np.argsort(-local_degrees)[:10].tolist())
    node_lines = []
    label_lines = []
    for i in range(n):
        r = 2.4 + min(10.5, np.sqrt(local_degrees[i]) * 0.82)
        fill = "#2563eb" if i in top else "#0f766e"
        stroke = "#0f172a" if i in top else "#ffffff"
        node_lines.append(
            f'<circle cx="{pts[i,0]:.1f}" cy="{pts[i,1]:.1f}" r="{r:.1f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="0.8" opacity="0.90"><title>{svg_escape(names[selected[i]])}: grau {int(local_degrees[i])}</title></circle>'
        )
        if i in top:
            safe = svg_escape(names[selected[i]][:28])
            label_lines.append(
                f'<text x="{pts[i,0]+8:.1f}" y="{pts[i,1]-8:.1f}" font-size="11" fill="#111827" '
                f'stroke="#ffffff" stroke-width="3" paint-order="stroke">{safe}</text>'
            )
    subtitle = f"Amostra visual de {n} vertices: hubs por grau e vizinhos semanticos; tamanho do no proporcional ao grau no grafo completo."
    svg = "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
            '<rect width="100%" height="100%" fill="#f8fafc"/>',
            '<text x="58" y="34" font-size="23" font-family="Arial" font-weight="700" fill="#111827">web-RedditEmbeddings: rede de similaridade entre subreddits</text>',
            f'<text x="58" y="58" font-size="13" font-family="Arial" fill="#475569">{svg_escape(subtitle)}</text>',
            '<line x1="808" y1="34" x2="848" y2="34" stroke="#64748b" stroke-width="1" opacity="0.45"/><text x="858" y="39" font-size="12" font-family="Arial" fill="#475569">arestas kNN</text>',
            '<circle cx="814" cy="58" r="7" fill="#2563eb" stroke="#0f172a"/><text x="858" y="63" font-size="12" font-family="Arial" fill="#475569">maiores graus</text>',
            '<circle cx="814" cy="82" r="5" fill="#0f766e" stroke="#ffffff"/><text x="858" y="87" font-size="12" font-family="Arial" fill="#475569">vizinhos amostrados</text>',
            '<g>',
            *edge_lines,
            "</g>",
            '<g>',
            *node_lines,
            "</g>",
            '<g font-family="Arial">',
            *label_lines,
            "</g>",
            "</svg>",
        ]
    )
    (RESULTS / "graph_visualization.svg").write_text(svg, encoding="utf-8")

    if Image is not None and ImageDraw is not None:
        image = Image.new("RGB", (width, height), "#f8fafc")
        draw = ImageDraw.Draw(image)
        draw.text((58, 18), "web-RedditEmbeddings: rede de similaridade entre subreddits", fill="#111827")
        draw.text((58, 44), subtitle, fill="#475569")
        draw.line((808, 34, 848, 34), fill="#94a3b8", width=1)
        draw.text((858, 28), "arestas kNN", fill="#475569")
        draw.ellipse((807, 51, 821, 65), fill="#2563eb", outline="#0f172a")
        draw.text((858, 51), "maiores graus", fill="#475569")
        draw.ellipse((809, 77, 819, 87), fill="#0f766e", outline="#ffffff")
        draw.text((858, 75), "vizinhos amostrados", fill="#475569")
        for a, b, sim, _ in edges:
            if a in local_index and b in local_index:
                la = local_index[a]
                lb = local_index[b]
                shade = int(180 - max(0, min(80, (sim + 1.0) * 25)))
                draw.line((pts[la, 0], pts[la, 1], pts[lb, 0], pts[lb, 1]), fill=(shade, shade, shade), width=1)
        for i in range(n):
            r = 2.4 + min(10.5, np.sqrt(local_degrees[i]) * 0.82)
            fill = "#2563eb" if i in top else "#0f766e"
            draw.ellipse((pts[i, 0] - r, pts[i, 1] - r, pts[i, 0] + r, pts[i, 1] + r), fill=fill)
        for i in top:
            draw.text((pts[i, 0] + 8, pts[i, 1] - 8), names[selected[i]][:28], fill="#111827")
        image.save(RESULTS / "graph_visualization.png")


def main() -> None:
    args = parse_args()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    if args.visualization_only:
        names, edges, x = load_processed_for_visualization()
        write_visualization(names, edges, x, args.visualization_n)
        print(json.dumps({"visualization": str(RESULTS / "graph_visualization.svg"), "vertices_used": min(args.visualization_n, len(names))}, indent=2))
        return

    names, x = load_embeddings(args.sample_size)
    edges = build_knn_edges(x, args.k, args.block_size)

    with (PROCESSED / "nodes.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "label"])
        for i, name in enumerate(names):
            writer.writerow([i, name])

    with (PROCESSED / "edges.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "cosine_similarity", "weight"])
        writer.writerows(edges)

    meta = {
        "source_dataset": "web-RedditEmbeddings",
        "source_url": "https://snap.stanford.edu/data/web-RedditEmbeddings.html",
        "raw_files": [
            str(RAW.relative_to(ROOT)),
            "data/raw/web-redditEmbeddings-users.csv",
        ],
        "analysis_raw_file": str(RAW.relative_to(ROOT)),
        "graph_interpretation": "Subreddits as vertices; undirected cosine-similarity kNN edges.",
        "construction_algorithm": "exact blocked cosine kNN",
        "construction_cost": "O(n^2 * d) time, O(block_size * n) memory for similarities",
        "uses_all_subreddit_vertices": args.sample_size is None,
        "requested_sample_size": args.sample_size,
        "sample_size": len(names),
        "k": args.k,
        "embedding_dimensions": int(x.shape[1]),
        "nodes": len(names),
        "edges": len(edges),
        "weight": "1 - cosine_similarity",
    }
    (PROCESSED / "graph_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_visualization(names, edges, x, args.visualization_n)
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
