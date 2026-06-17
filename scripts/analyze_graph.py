import argparse
import csv
import heapq
import json
import math
import platform
import random
import statistics
import sys
import time
from collections import Counter, deque
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # optional; SVG outputs remain the canonical graphics
    Image = None
    ImageDraw = None


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RESULTS = ROOT / "results"
sys.setrecursionlimit(100000)
STUDENT_ID = "224116475"


def draw_png(path: Path, width: int, height: int, draw_func) -> None:
    if Image is None or ImageDraw is None:
        return
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw_func(draw)
    image.save(path)


def svg_escape(value: object) -> str:
    text = str(value)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("use um inteiro positivo")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("use um inteiro nao negativo")
    return parsed


def fmt_tick(value: float) -> str:
    if not math.isfinite(value):
        return ""
    if abs(value) >= 1000:
        return f"{value:,.0f}".replace(",", ".")
    if 0 < abs(value) < 0.01:
        return f"{value:.1e}"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def linear_ticks(min_value: float, max_value: float, count: int = 6) -> list[float]:
    if not math.isfinite(min_value) or not math.isfinite(max_value):
        return []
    if abs(max_value - min_value) < 1e-12:
        return [min_value]
    return [min_value + (max_value - min_value) * i / (count - 1) for i in range(count)]


def fit_line(points: list[tuple[float, float]]) -> tuple[float, float, float] | None:
    if len(points) < 2:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    ss_x = sum((x - mean_x) ** 2 for x in xs)
    if ss_x == 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / ss_x
    intercept = mean_y - slope * mean_x
    fitted = [slope * x + intercept for x in xs]
    ss_res = sum((y - yhat) ** 2 for y, yhat in zip(ys, fitted))
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return slope, intercept, r2


def svg_axes(
    width: int,
    height: int,
    left: int,
    right: int,
    top: int,
    bottom: int,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
    x_ticks: list[tuple[float, str]],
    y_ticks: list[tuple[float, str]],
    sx,
    sy,
) -> list[str]:
    plot_left, plot_right = left, width - right
    plot_top, plot_bottom = top, height - bottom
    elements = [
        f'<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="34" font-size="22" font-family="Arial" font-weight="700" fill="#111827">{svg_escape(title)}</text>',
    ]
    if subtitle:
        elements.append(
            f'<text x="{left}" y="58" font-size="13" font-family="Arial" fill="#475569">{svg_escape(subtitle)}</text>'
        )
    for value, label in y_ticks:
        y = sy(value)
        elements.append(f'<line x1="{plot_left}" y1="{y:.1f}" x2="{plot_right}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        elements.append(
            f'<text x="{plot_left-10}" y="{y+4:.1f}" font-size="11" font-family="Arial" text-anchor="end" fill="#475569">{svg_escape(label)}</text>'
        )
    for value, label in x_ticks:
        x = sx(value)
        elements.append(f'<line x1="{x:.1f}" y1="{plot_top}" x2="{x:.1f}" y2="{plot_bottom}" stroke="#f1f5f9"/>')
        elements.append(f'<line x1="{x:.1f}" y1="{plot_bottom}" x2="{x:.1f}" y2="{plot_bottom+5}" stroke="#334155"/>')
        elements.append(
            f'<text x="{x:.1f}" y="{plot_bottom+21}" font-size="11" font-family="Arial" text-anchor="middle" fill="#475569">{svg_escape(label)}</text>'
        )
    elements.extend(
        [
            f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#111827" stroke-width="1.2"/>',
            f'<line x1="{plot_left}" y1="{plot_top}" x2="{plot_left}" y2="{plot_bottom}" stroke="#111827" stroke-width="1.2"/>',
            f'<text x="{(plot_left+plot_right)/2:.1f}" y="{height-18}" font-size="13" font-family="Arial" text-anchor="middle" fill="#111827">{svg_escape(x_label)}</text>',
            f'<text x="18" y="{(plot_top+plot_bottom)/2:.1f}" font-size="13" font-family="Arial" text-anchor="middle" fill="#111827" transform="rotate(-90 18,{(plot_top+plot_bottom)/2:.1f})">{svg_escape(y_label)}</text>',
        ]
    )
    return elements


def draw_png_axes(
    draw,
    width: int,
    height: int,
    left: int,
    right: int,
    top: int,
    bottom: int,
    title: str,
    subtitle: str,
    x_label: str,
    y_label: str,
    x_ticks: list[tuple[float, str]],
    y_ticks: list[tuple[float, str]],
    sx,
    sy,
) -> None:
    plot_left, plot_right = left, width - right
    plot_top, plot_bottom = top, height - bottom
    draw.text((left, 18), title, fill="#111827")
    if subtitle:
        draw.text((left, 44), subtitle, fill="#475569")
    for value, label in y_ticks:
        y = sy(value)
        draw.line((plot_left, y, plot_right, y), fill="#e5e7eb", width=1)
        draw.text((plot_left - 58, y - 6), str(label), fill="#475569")
    for value, label in x_ticks:
        x = sx(value)
        draw.line((x, plot_top, x, plot_bottom), fill="#f1f5f9", width=1)
        draw.line((x, plot_bottom, x, plot_bottom + 5), fill="#334155", width=1)
        draw.text((x - 12, plot_bottom + 8), str(label), fill="#475569")
    draw.line((plot_left, plot_bottom, plot_right, plot_bottom), fill="#111827", width=2)
    draw.line((plot_left, plot_top, plot_left, plot_bottom), fill="#111827", width=2)
    draw.text(((plot_left + plot_right) / 2 - 32, height - 24), x_label, fill="#111827")
    draw.text((8, top - 18), y_label, fill="#111827")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analisa o grafo tratado do web-RedditEmbeddings.")
    parser.add_argument("--benchmark-runs", type=positive_int, default=30)
    parser.add_argument("--robustness-runs", type=positive_int, default=30)
    parser.add_argument("--exact-path-limit", type=nonnegative_int, default=4000)
    parser.add_argument("--path-samples", type=positive_int, default=16)
    parser.add_argument("--random-graphs", type=positive_int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def student_graph_rule(student_id: str = STUDENT_ID) -> dict:
    digits = [int(ch) for ch in student_id if ch.isdigit()]
    digit_sum = sum(digits)
    last_two = int(student_id[-2:])
    last_two_plus_one = last_two + 1
    product = digit_sum * last_two_plus_one
    modulo = product % 129
    graph_number = modulo if modulo != 0 else 129
    return {
        "student_id": student_id,
        "digit_sum": digit_sum,
        "last_two_digits": last_two,
        "last_two_plus_one": last_two_plus_one,
        "product": product,
        "modulo_129": modulo,
        "graph_number": graph_number,
        "graph_label": f"G{graph_number}",
        "assigned_dataset": "web-RedditEmbeddings",
    }


def load_graph() -> tuple[list[str], list[tuple[int, int, float]], list[set[int]], list[list[tuple[int, float]]], dict]:
    with (PROCESSED / "nodes.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"Nenhum vertice encontrado em {PROCESSED / 'nodes.csv'}.")
    ids = [int(r["id"]) for r in rows]
    expected_ids = list(range(len(rows)))
    if ids != expected_ids:
        raise ValueError("nodes.csv deve ter ids consecutivos iniciando em 0.")
    labels = [r["label"] for r in rows]
    n = len(labels)
    adj = [set() for _ in range(n)]
    wadj = [[] for _ in range(n)]
    edges = []
    with (PROCESSED / "edges.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            a = int(row["source"])
            b = int(row["target"])
            weight = float(row["weight"])
            if a == b:
                raise ValueError(f"Aresta com auto-laco encontrada: {a}.")
            if not (0 <= a < n and 0 <= b < n):
                raise ValueError(f"Aresta fora do intervalo de vertices: {a}, {b}.")
            adj[a].add(b)
            adj[b].add(a)
            wadj[a].append((b, weight))
            wadj[b].append((a, weight))
            edges.append((a, b, weight))
    meta = json.loads((PROCESSED / "graph_metadata.json").read_text(encoding="utf-8"))
    if int(meta.get("nodes", n)) != n:
        raise ValueError("graph_metadata.json nao bate com a contagem de vertices processados.")
    if int(meta.get("edges", len(edges))) != len(edges):
        raise ValueError("graph_metadata.json nao bate com a contagem de arestas processadas.")
    return labels, edges, adj, wadj, meta


def bfs_distances(adj: list[set[int]], start: int, allowed: set[int] | None = None) -> dict[int, int]:
    seen = {start: 0}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if allowed is not None and v not in allowed:
                continue
            if v not in seen:
                seen[v] = seen[u] + 1
                q.append(v)
    return seen


def bfs_order(adj: list[set[int]], start: int) -> list[int]:
    seen = {start}
    order = []
    q = deque([start])
    while q:
        u = q.popleft()
        order.append(u)
        for v in adj[u]:
            if v not in seen:
                seen.add(v)
                q.append(v)
    return order


def dfs_order(adj: list[set[int]], start: int) -> list[int]:
    seen = set()
    order = []
    stack = [start]
    while stack:
        u = stack.pop()
        if u in seen:
            continue
        seen.add(u)
        order.append(u)
        stack.extend(v for v in adj[u] if v not in seen)
    return order


def components(adj: list[set[int]], active: set[int] | None = None) -> list[list[int]]:
    nodes = list(range(len(adj))) if active is None else list(active)
    unseen = set(nodes)
    comps = []
    while unseen:
        start = unseen.pop()
        comp = []
        q = deque([start])
        while q:
            u = q.popleft()
            comp.append(u)
            for v in adj[u]:
                if active is not None and v not in active:
                    continue
                if v in unseen:
                    unseen.remove(v)
                    q.append(v)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps


def path_summary(adj: list[set[int]], nodes: list[int], exact_limit: int, samples: int, rng: random.Random) -> dict:
    allowed = set(nodes)
    n = len(nodes)
    if n <= 1:
        return {
            "mode": "trivial",
            "diameter": 0,
            "radius": 0,
            "average_path_length": 0.0,
            "average_path_length_source_sd": 0.0,
            "average_path_length_ci95": 0.0,
            "ci95_method": "N/A",
            "ci95_critical": 0.0,
            "sample_size": n,
            "component_size": n,
            "diameter_is_lower_bound": False,
            "radius_is_upper_bound": False,
        }
    sources = nodes if n <= exact_limit else rng.sample(nodes, min(samples, n))
    ecc = []
    source_means = []
    total = 0
    pairs = 0
    for src in sources:
        dist = bfs_distances(adj, src, allowed)
        values = [d for v, d in dist.items() if v != src]
        if values:
            source_total = sum(values)
            ecc.append(max(values))
            source_means.append(source_total / len(values))
            total += source_total
            pairs += len(values)
    mode = "exact" if n <= exact_limit else "sampled"
    sd = statistics.stdev(source_means) if len(source_means) > 1 else 0.0
    critical, method = confidence_critical_95(len(source_means))
    ci = critical * sd / math.sqrt(len(source_means)) if mode == "sampled" and len(source_means) > 1 else 0.0
    return {
        "mode": mode,
        "diameter": max(ecc) if ecc else None,
        "radius": min(ecc) if ecc else None,
        "average_path_length": total / pairs if pairs else None,
        "average_path_length_source_sd": sd,
        "average_path_length_ci95": ci,
        "ci95_method": method if mode == "sampled" else "N/A",
        "ci95_critical": critical if mode == "sampled" else 0.0,
        "sample_size": len(sources),
        "component_size": n,
        "diameter_is_lower_bound": mode == "sampled",
        "radius_is_upper_bound": mode == "sampled",
        "sampled_sources": sources if mode == "sampled" else [],
    }


def clustering_and_triangles(adj: list[set[int]]) -> tuple[float, int]:
    local = []
    triangle_contrib = 0
    for u, neigh in enumerate(adj):
        d = len(neigh)
        if d < 2:
            local.append(0.0)
            continue
        links = 0
        for v in neigh:
            links += len(neigh & adj[v])
        links //= 2
        triangle_contrib += links
        local.append((2 * links) / (d * (d - 1)))
    return sum(local) / len(local), triangle_contrib // 3


def degree_distribution_svg(degrees: list[int]) -> None:
    counts = Counter(degrees)
    total = len(degrees)
    xs = sorted(k for k in counts if k > 0)
    ccdf = []
    running = 0
    for k in sorted(counts, reverse=True):
        running += counts[k]
        if k > 0:
            ccdf.append((k, running / total))
    ccdf.sort()
    with (RESULTS / "degree_distribution.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["degree", "frequency", "p_k", "ln_k", "ln_p_k", "ccdf", "ln_ccdf"])
        ccdf_by_degree = dict(ccdf)
        for k in sorted(counts):
            p_k = counts[k] / total if total else 0.0
            w.writerow(
                [
                    k,
                    counts[k],
                    p_k,
                    math.log(k) if k > 0 else "",
                    math.log(p_k) if p_k > 0 else "",
                    ccdf_by_degree.get(k, ""),
                    math.log(ccdf_by_degree[k]) if k in ccdf_by_degree and ccdf_by_degree[k] > 0 else "",
                ]
            )
    if not xs:
        return

    write_degree_histogram(counts, total)
    write_degree_ccdf(ccdf)
    degree_log_pk_svg(counts, total)
    degree_model_comparison_svg(counts, total)


def write_degree_histogram(counts: Counter, total: int) -> None:
    xs = sorted(k for k in counts if k > 0)
    degree_min, degree_max = min(xs), max(xs)
    max_bins = 72
    bin_width = max(1, math.ceil((degree_max - degree_min + 1) / max_bins))
    bins = []
    for start in range(degree_min, degree_max + 1, bin_width):
        end = min(start + bin_width - 1, degree_max)
        value = sum(counts.get(k, 0) for k in range(start, end + 1))
        if value:
            bins.append((start, end, value))

    width, height = 1100, 660
    left, right, top, bottom = 92, 42, 86, 78
    plot_left, plot_right = left, width - right
    plot_bottom = height - bottom
    min_x, max_x = degree_min, degree_max + 1
    max_log = math.ceil(math.log10(max(v for _, _, v in bins)))
    y_min, y_max = 0.0, max(1.0, float(max_log))

    def sx(x: float) -> float:
        return plot_left + (x - min_x) / max(max_x - min_x, 1e-9) * (plot_right - plot_left)

    def sy(y: float) -> float:
        return plot_bottom - (y - y_min) / max(y_max - y_min, 1e-9) * (plot_bottom - top)

    x_ticks = [(v, fmt_tick(v)) for v in linear_ticks(degree_min, degree_max, 7)]
    y_ticks = [(float(i), f"10^{i}" if i else "1") for i in range(int(y_max) + 1)]
    subtitle = f"{total} vertices; grau minimo {degree_min}; grau maximo {degree_max}; barras agregadas a cada {bin_width} grau(s)"
    elements = svg_axes(
        width,
        height,
        left,
        right,
        top,
        bottom,
        "Histograma da distribuicao de graus",
        subtitle,
        "grau k",
        "frequencia em escala log10",
        x_ticks,
        y_ticks,
        sx,
        sy,
    )
    for start, end, value in bins:
        x0 = sx(start)
        x1 = sx(end + 1)
        y = sy(math.log10(max(value, 1)))
        label = f"grau {start}" if start == end else f"graus {start}-{end}"
        elements.append(
            f'<rect x="{x0:.1f}" y="{y:.1f}" width="{max(1.0, (x1-x0)*0.86):.1f}" height="{plot_bottom-y:.1f}" '
            f'fill="#0f766e" opacity="0.84"><title>{svg_escape(label)}: {value}</title></rect>'
        )
    elements.append(
        '<text x="760" y="106" font-size="12" font-family="Arial" fill="#475569">Eixo Y em log10 para revelar a cauda da distribuicao.</text>'
    )
    svg = "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', *elements, "</svg>"])
    (RESULTS / "degree_histogram.svg").write_text(svg, encoding="utf-8")

    def draw_hist_png(draw):
        draw_png_axes(
            draw,
            width,
            height,
            left,
            right,
            top,
            bottom,
            "Histograma da distribuicao de graus",
            subtitle,
            "grau k",
            "frequencia log10",
            x_ticks,
            y_ticks,
            sx,
            sy,
        )
        for start, end, value in bins:
            x0 = sx(start)
            x1 = sx(end + 1)
            y = sy(math.log10(max(value, 1)))
            draw.rectangle((x0, y, x0 + max(1.0, (x1 - x0) * 0.86), plot_bottom), fill="#0f766e")

    draw_png(RESULTS / "degree_histogram.png", width, height, draw_hist_png)


def write_degree_ccdf(ccdf: list[tuple[int, float]]) -> None:
    points = [(math.log10(k), math.log10(p)) for k, p in ccdf if k > 0 and p > 0]
    if not points:
        return
    width, height = 1100, 660
    left, right, top, bottom = 92, 42, 86, 78
    min_x, max_x = min(x for x, _ in points), max(x for x, _ in points)
    min_y, max_y = min(y for _, y in points), max(y for _, y in points)
    plot_left, plot_right = left, width - right
    plot_bottom = height - bottom

    def sx(x: float) -> float:
        return plot_left + (x - min_x) / max(max_x - min_x, 1e-9) * (plot_right - plot_left)

    def sy(y: float) -> float:
        return plot_bottom - (y - min_y) / max(max_y - min_y, 1e-9) * (plot_bottom - top)

    fit = fit_line(points)
    subtitle = "Cada ponto mostra log10(P(K >= k)); a linha tracejada e ajuste linear exploratorio."
    elements = svg_axes(
        width,
        height,
        left,
        right,
        top,
        bottom,
        "Distribuicao de graus - CCDF em log-log",
        subtitle,
        "log10(grau k)",
        "log10(P(K >= k))",
        [(v, fmt_tick(v)) for v in linear_ticks(min_x, max_x, 6)],
        [(v, fmt_tick(v)) for v in linear_ticks(min_y, max_y, 6)],
        sx,
        sy,
    )
    if fit:
        slope, intercept, r2 = fit
        y1 = slope * min_x + intercept
        y2 = slope * max_x + intercept
        elements.append(
            f'<line x1="{sx(min_x):.1f}" y1="{sy(y1):.1f}" x2="{sx(max_x):.1f}" y2="{sy(y2):.1f}" '
            f'stroke="#dc2626" stroke-width="2.4" stroke-dasharray="7 5"/>'
        )
        elements.append(
            f'<text x="760" y="106" font-size="12" font-family="Arial" fill="#334155">ajuste: inclinacao {slope:.3f}; R2 {r2:.3f}</text>'
        )
    for x, y in points:
        elements.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.1" fill="#2563eb" opacity="0.72"/>')
    svg = "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', *elements, "</svg>"])
    (RESULTS / "degree_ccdf.svg").write_text(svg, encoding="utf-8")
    (RESULTS / "degree_distribution.svg").write_text(svg, encoding="utf-8")

    def draw_ccdf_png(draw):
        draw_png_axes(
            draw,
            width,
            height,
            left,
            right,
            top,
            bottom,
            "Distribuicao de graus - CCDF em log-log",
            subtitle,
            "log10(grau k)",
            "log10(P(K >= k))",
            [(v, fmt_tick(v)) for v in linear_ticks(min_x, max_x, 6)],
            [(v, fmt_tick(v)) for v in linear_ticks(min_y, max_y, 6)],
            sx,
            sy,
        )
        if fit:
            slope, intercept, _ = fit
            draw.line((sx(min_x), sy(slope * min_x + intercept), sx(max_x), sy(slope * max_x + intercept)), fill="#dc2626", width=3)
        for x, y in points:
            cx, cy = sx(x), sy(y)
            draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill="#2563eb")

    draw_png(RESULTS / "degree_ccdf.png", width, height, draw_ccdf_png)
    draw_png(RESULTS / "degree_distribution.png", width, height, draw_ccdf_png)


def degree_log_pk_svg(counts: Counter, total: int) -> None:
    points = [(math.log10(k), math.log10(count / total)) for k, count in sorted(counts.items()) if k > 0 and count > 0]
    if not points:
        return
    width, height = 1100, 660
    left, right, top, bottom = 92, 42, 86, 78
    min_x, max_x = min(x for x, _ in points), max(x for x, _ in points)
    min_y, max_y = min(y for _, y in points), max(y for _, y in points)
    plot_left, plot_right = left, width - right
    plot_bottom = height - bottom

    def sx(x: float) -> float:
        return plot_left + (x - min_x) / max(max_x - min_x, 1e-9) * (plot_right - plot_left)

    def sy(y: float) -> float:
        return plot_bottom - (y - min_y) / max(max_y - min_y, 1e-9) * (plot_bottom - top)

    fit = fit_line(points)
    subtitle = "Frequencia pontual dos graus; usado como evidencia visual, nao como prova estatistica."
    elements = svg_axes(
        width,
        height,
        left,
        right,
        top,
        bottom,
        "Grafico log(P(k)) versus log(k)",
        subtitle,
        "log10(k)",
        "log10(P(k))",
        [(v, fmt_tick(v)) for v in linear_ticks(min_x, max_x, 6)],
        [(v, fmt_tick(v)) for v in linear_ticks(min_y, max_y, 6)],
        sx,
        sy,
    )
    if fit:
        slope, intercept, r2 = fit
        elements.append(
            f'<line x1="{sx(min_x):.1f}" y1="{sy(slope*min_x+intercept):.1f}" x2="{sx(max_x):.1f}" y2="{sy(slope*max_x+intercept):.1f}" '
            f'stroke="#dc2626" stroke-width="2.4" stroke-dasharray="7 5"/>'
        )
        elements.append(f'<text x="760" y="106" font-size="12" font-family="Arial" fill="#334155">ajuste: inclinacao {slope:.3f}; R2 {r2:.3f}</text>')
    for x, y in points:
        elements.append(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3.1" fill="#7c3aed" opacity="0.72"/>')
    svg = "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', *elements, "</svg>"])
    (RESULTS / "degree_log_pk.svg").write_text(svg, encoding="utf-8")

    def draw_log_pk_png(draw):
        draw_png_axes(
            draw,
            width,
            height,
            left,
            right,
            top,
            bottom,
            "Grafico log(P(k)) versus log(k)",
            subtitle,
            "log10(k)",
            "log10(P(k))",
            [(v, fmt_tick(v)) for v in linear_ticks(min_x, max_x, 6)],
            [(v, fmt_tick(v)) for v in linear_ticks(min_y, max_y, 6)],
            sx,
            sy,
        )
        if fit:
            slope, intercept, _ = fit
            draw.line((sx(min_x), sy(slope * min_x + intercept), sx(max_x), sy(slope * max_x + intercept)), fill="#dc2626", width=3)
        for x, y in points:
            cx, cy = sx(x), sy(y)
            draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill="#7c3aed")

    draw_png(RESULTS / "degree_log_pk.png", width, height, draw_log_pk_png)


def degree_model_comparison_svg(counts: Counter, total: int) -> None:
    if not counts or not total:
        return
    xs = sorted(k for k in counts if k > 0)
    mean = sum(k * c for k, c in counts.items()) / total
    variance = sum(c * (k - mean) ** 2 for k, c in counts.items()) / total
    sd = math.sqrt(max(variance, 1e-12))
    observed = {k: counts[k] / total for k in xs}
    poisson = {}
    p = math.exp(-mean)
    for k in range(0, max(xs) + 1):
        if k > 0:
            p *= mean / k
        poisson[k] = p
    normal = {k: math.exp(-0.5 * ((k - mean) / sd) ** 2) / (sd * math.sqrt(2 * math.pi)) for k in xs}
    floor = 1 / (total * 10)
    y_values = [max(v, floor) for v in observed.values()]
    y_values += [max(poisson.get(k, 0.0), floor) for k in xs]
    y_values += [max(normal.get(k, 0.0), floor) for k in xs]
    min_y, max_y = math.floor(math.log10(min(y_values))), math.ceil(math.log10(max(y_values)))
    min_x, max_x = min(xs), max(xs)
    width, height = 1100, 660
    left, right, top, bottom = 92, 42, 86, 78
    plot_left, plot_right = left, width - right
    plot_bottom = height - bottom

    def sx(x: float) -> float:
        return plot_left + (x - min_x) / max(max_x - min_x, 1e-9) * (plot_right - plot_left)

    def sy_log(y: float) -> float:
        ly = math.log10(max(y, floor))
        return plot_bottom - (ly - min_y) / max(max_y - min_y, 1e-9) * (plot_bottom - top)

    x_ticks = [(v, fmt_tick(v)) for v in linear_ticks(min_x, max_x, 7)]
    y_ticks = [(float(i), f"1e{i}") for i in range(int(min_y), int(max_y) + 1)]
    subtitle = f"Media observada {mean:.2f}; desvio padrao {sd:.2f}; eixo Y em log10"
    elements = svg_axes(
        width,
        height,
        left,
        right,
        top,
        bottom,
        "Comparacao de P(k) com Poisson e normal",
        subtitle,
        "grau k",
        "P(k) em escala log10",
        x_ticks,
        y_ticks,
        sx,
        lambda value: plot_bottom - (value - min_y) / max(max_y - min_y, 1e-9) * (plot_bottom - top),
    )

    def polyline(values: dict[int, float], color: str, dash: str = "") -> str:
        pts = " ".join(f"{sx(k):.1f},{sy_log(values.get(k, 0.0)):.1f}" for k in xs)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5" opacity="0.9"{dash_attr}/>'

    elements.extend(
        [
            '<circle cx="722" cy="104" r="5" fill="#0f766e"/><text x="737" y="109" font-size="12" font-family="Arial" fill="#334155">observado</text>',
            '<line x1="835" y1="104" x2="875" y2="104" stroke="#2563eb" stroke-width="2.5"/><text x="884" y="109" font-size="12" font-family="Arial" fill="#334155">Poisson</text>',
            '<line x1="970" y1="104" x2="1010" y2="104" stroke="#dc2626" stroke-width="2.5" stroke-dasharray="7 5"/><text x="1019" y="109" font-size="12" font-family="Arial" fill="#334155">normal</text>',
            polyline(poisson, "#2563eb"),
            polyline(normal, "#dc2626", "7 5"),
        ]
    )
    for k, p_k in observed.items():
        elements.append(f'<circle cx="{sx(k):.1f}" cy="{sy_log(p_k):.1f}" r="2.8" fill="#0f766e" opacity="0.72"/>')
    svg = "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', *elements, "</svg>"])
    (RESULTS / "degree_model_comparison.svg").write_text(svg, encoding="utf-8")

    def draw_model_png(draw):
        draw_png_axes(
            draw,
            width,
            height,
            left,
            right,
            top,
            bottom,
            "Comparacao de P(k) com Poisson e normal",
            subtitle,
            "grau k",
            "P(k) log10",
            x_ticks,
            y_ticks,
            sx,
            lambda value: plot_bottom - (value - min_y) / max(max_y - min_y, 1e-9) * (plot_bottom - top),
        )
        draw.ellipse((717, 99, 727, 109), fill="#0f766e")
        draw.text((737, 98), "observado", fill="#334155")
        draw.line((835, 104, 875, 104), fill="#2563eb", width=3)
        draw.text((884, 98), "Poisson", fill="#334155")
        draw.line((970, 104, 1010, 104), fill="#dc2626", width=3)
        draw.text((1019, 98), "normal", fill="#334155")
        for values, color in ((poisson, "#2563eb"), (normal, "#dc2626")):
            pts = [(sx(k), sy_log(values.get(k, 0.0))) for k in xs]
            if len(pts) > 1:
                draw.line(pts, fill=color, width=3)
        for k, p_k in observed.items():
            cx, cy = sx(k), sy_log(p_k)
            draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill="#0f766e")

    draw_png(RESULTS / "degree_model_comparison.png", width, height, draw_model_png)


def discrete_distribution(values: range, score_func) -> dict[int, float]:
    weights = {k: score_func(k) for k in values}
    total = sum(weights.values())
    if total <= 0:
        return {}
    return {k: w / total for k, w in weights.items()}


def ks_distance_discrete(sample: list[int], probabilities: dict[int, float]) -> float:
    if not sample or not probabilities:
        return math.inf
    sorted_sample = sorted(sample)
    n = len(sorted_sample)
    cumulative_model = 0.0
    seen = 0
    max_ks = 0.0
    for k in sorted(probabilities):
        cumulative_model += probabilities[k]
        while seen < n and sorted_sample[seen] <= k:
            seen += 1
        empirical = seen / n
        max_ks = max(max_ks, abs(empirical - cumulative_model))
    return max_ks


def log_likelihood(sample: list[int], probabilities: dict[int, float]) -> float:
    floor = 1e-300
    return sum(math.log(max(probabilities.get(k, 0.0), floor)) for k in sample)


def power_law_mle(degrees: list[int], min_tail: int = 30) -> dict:
    positive = sorted(d for d in degrees if d > 0)
    if len(positive) < min_tail:
        return {
            "alpha_mle": None,
            "xmin": None,
            "tail_count": len(positive),
            "tail_fraction": None,
            "ks_distance": None,
            "log_likelihood_ratio_power_vs_exponential": None,
            "mle_interpretation": "Amostra insuficiente para ajuste MLE da cauda.",
        }
    max_degree = max(positive)
    best = None
    for xmin in sorted(set(positive)):
        tail = [d for d in positive if d >= xmin]
        if len(tail) < min_tail or xmin >= max_degree:
            continue
        denom = sum(math.log(d / (xmin - 0.5)) for d in tail)
        if denom <= 0:
            continue
        alpha = 1.0 + len(tail) / denom
        values = range(xmin, max_degree + 1)
        power_probs = discrete_distribution(values, lambda k, a=alpha: k ** (-a))
        ks = ks_distance_discrete(tail, power_probs)
        if best is None or ks < best["ks_distance"]:
            shifted_mean = statistics.mean(d - xmin for d in tail)
            if shifted_mean > 0:
                rate = 1.0 / shifted_mean
                exp_probs = discrete_distribution(values, lambda k, r=rate, x=xmin: math.exp(-r * (k - x)))
                ll_exp = log_likelihood(tail, exp_probs)
            else:
                ll_exp = None
            ll_power = log_likelihood(tail, power_probs)
            best = {
                "alpha_mle": alpha,
                "xmin": xmin,
                "tail_count": len(tail),
                "tail_fraction": len(tail) / len(positive),
                "ks_distance": ks,
                "log_likelihood_power_law": ll_power,
                "log_likelihood_exponential": ll_exp,
                "log_likelihood_ratio_power_vs_exponential": None if ll_exp is None else ll_power - ll_exp,
            }
    if best is None:
        return {
            "alpha_mle": None,
            "xmin": None,
            "tail_count": len(positive),
            "tail_fraction": None,
            "ks_distance": None,
            "log_likelihood_ratio_power_vs_exponential": None,
            "mle_interpretation": "Nao foi possivel escolher uma cauda valida para MLE.",
        }
    llr = best["log_likelihood_ratio_power_vs_exponential"]
    if llr is None:
        comparison = "comparacao com exponencial indisponivel"
    elif llr > 0:
        comparison = "cauda ajustada favorece lei de potencia sobre exponencial no log-verossimilhanca exploratorio"
    else:
        comparison = "cauda ajustada nao favorece lei de potencia contra exponencial no log-verossimilhanca exploratorio"
    best["mle_interpretation"] = (
        f"MLE discreto exploratorio em k >= {best['xmin']} com {best['tail_count']} vertices na cauda; {comparison}."
    )
    return best


def power_law_fit(degrees: list[int]) -> dict:
    counts = Counter(d for d in degrees if d > 0)
    if len(counts) < 2:
        return {
            "gamma_ccdf_slope": None,
            "r2_loglog": None,
            "interpretation": "Distribuicao insuficiente.",
            **power_law_mle(degrees),
        }
    total = len(degrees)
    ccdf = []
    running = 0
    for k in sorted(counts, reverse=True):
        running += counts[k]
        ccdf.append((k, running / total))
    points = [(math.log(k), math.log(p)) for k, p in ccdf if k > 0 and p > 0]
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    ss_x = sum((x - mean_x) ** 2 for x in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / ss_x
    intercept = mean_y - slope * mean_x
    fitted = [slope * x + intercept for x in xs]
    ss_res = sum((y - yhat) ** 2 for y, yhat in zip(ys, fitted))
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    return {
        "gamma_ccdf_slope": -slope,
        "r2_loglog": r2,
        "interpretation": (
            "A regressao log-log da CCDF e apenas diagnostico visual; o MLE discreto e a checagem KS "
            "dao uma avaliacao mais robusta da cauda."
        ),
        **power_law_mle(degrees),
    }


def make_random_graph(n: int, m: int, rng: random.Random) -> list[set[int]]:
    max_edges = n * (n - 1) // 2
    if m > max_edges:
        raise ValueError("Numero de arestas maior que o maximo de um grafo simples.")
    adj = [set() for _ in range(n)]
    edges = set()
    while len(edges) < m:
        a = rng.randrange(n)
        b = rng.randrange(n)
        if a == b:
            continue
        if a > b:
            a, b = b, a
        if (a, b) in edges:
            continue
        edges.add((a, b))
        adj[a].add(b)
        adj[b].add(a)
    return adj


def summarize_measurements(values: list[float]) -> dict:
    clean = [v for v in values if v is not None and math.isfinite(v)]
    if not clean:
        return {"mean": None, "sd": None, "ci95": None, "ci95_method": "N/A", "ci95_critical": 0.0, "runs": 0}
    sd = statistics.stdev(clean) if len(clean) > 1 else 0.0
    critical, method = confidence_critical_95(len(clean))
    ci = critical * sd / math.sqrt(len(clean)) if len(clean) > 1 else 0.0
    return {
        "mean": statistics.mean(clean),
        "sd": sd,
        "ci95": ci,
        "ci95_method": method,
        "ci95_critical": critical,
        "runs": len(clean),
    }


def random_graph_baseline(n: int, m: int, exact_limit: int, samples: int, runs: int, rng: random.Random) -> dict:
    run_rows = []
    for i in range(runs):
        random_adj = make_random_graph(n, m, rng)
        random_comps = components(random_adj)
        random_lcc = random_comps[0] if random_comps else []
        random_clustering, _ = clustering_and_triangles(random_adj)
        random_path = path_summary(random_adj, random_lcc, exact_limit, samples, rng)
        run_rows.append(
            {
                "run": i + 1,
                "largest_component_size": len(random_lcc),
                "components": len(random_comps),
                "average_path_length": random_path["average_path_length"],
                "clustering": random_clustering,
            }
        )
    return {
        "runs": run_rows,
        "average_path_length": summarize_measurements([r["average_path_length"] for r in run_rows]),
        "clustering": summarize_measurements([r["clustering"] for r in run_rows]),
        "largest_component_size": summarize_measurements([float(r["largest_component_size"]) for r in run_rows]),
    }


def dijkstra(wadj: list[list[tuple[int, float]]], start: int) -> list[float]:
    dist = [math.inf] * len(wadj)
    dist[start] = 0.0
    heap = [(0.0, start)]
    while heap:
        du, u = heapq.heappop(heap)
        if du != dist[u]:
            continue
        for v, w in wadj[u]:
            nd = du + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(heap, (nd, v))
    return dist


def bellman_ford(n: int, edges: list[tuple[int, int, float]], start: int) -> list[float]:
    dist = [math.inf] * n
    dist[start] = 0.0
    directed = [(a, b, w) for a, b, w in edges] + [(b, a, w) for a, b, w in edges]
    for _ in range(n - 1):
        changed = False
        for a, b, w in directed:
            if dist[a] + w < dist[b]:
                dist[b] = dist[a] + w
                changed = True
        if not changed:
            break
    return dist


def floyd_warshall(n: int, edges: list[tuple[int, int, float]]) -> list[list[float]]:
    dist = [[math.inf] * n for _ in range(n)]
    for i in range(n):
        dist[i][i] = 0.0
    for a, b, w in edges:
        dist[a][b] = min(dist[a][b], w)
        dist[b][a] = min(dist[b][a], w)
    for k in range(n):
        dk = dist[k]
        for i in range(n):
            dik = dist[i][k]
            if dik == math.inf:
                continue
            row = dist[i]
            alt_base = dik
            for j in range(n):
                alt = alt_base + dk[j]
                if alt < row[j]:
                    row[j] = alt
    return dist


def tarjan_articulation_bridges(adj: list[set[int]]) -> tuple[set[int], list[tuple[int, int]]]:
    n = len(adj)
    timer = 0
    tin = [-1] * n
    low = [-1] * n
    arts = set()
    bridges = []

    def dfs(u: int, parent: int) -> None:
        nonlocal timer
        tin[u] = low[u] = timer
        timer += 1
        children = 0
        for v in adj[u]:
            if v == parent:
                continue
            if tin[v] != -1:
                low[u] = min(low[u], tin[v])
            else:
                dfs(v, u)
                low[u] = min(low[u], low[v])
                if low[v] > tin[u]:
                    bridges.append((min(u, v), max(u, v)))
                if low[v] >= tin[u] and parent != -1:
                    arts.add(u)
                children += 1
        if parent == -1 and children > 1:
            arts.add(u)

    for i in range(n):
        if tin[i] == -1:
            dfs(i, -1)
    return arts, bridges


def mst_kruskal(n: int, edges: list[tuple[int, int, float]]) -> dict:
    parent = list(range(n))
    rank = [0] * n

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> bool:
        ra, rb = find(a), find(b)
        if ra == rb:
            return False
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1
        return True

    total = 0.0
    used = 0
    for a, b, w in sorted(edges, key=lambda e: e[2]):
        if union(a, b):
            total += w
            used += 1
    return {"forest_edges": used, "total_weight": total, "is_spanning_tree": used == n - 1}


def t_critical_95(n: int) -> float:
    table = {
        1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
        8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160,
        14: 2.145, 15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093,
        20: 2.086, 21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
        26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
    }
    if n <= 1:
        return 0.0
    return table.get(n - 1, 1.96)


def confidence_critical_95(n: int) -> tuple[float, str]:
    if n <= 1:
        return 0.0, "N/A"
    if n >= 30:
        return 1.96, "Normal/Z"
    return t_critical_95(n), "t-Student"


def timed(name: str, func, runs: int) -> dict:
    samples = []
    result = None
    for _ in range(runs):
        start = time.perf_counter()
        result = func()
        samples.append(time.perf_counter() - start)
    mean = statistics.mean(samples)
    sd = statistics.stdev(samples) if len(samples) > 1 else 0.0
    critical, method = confidence_critical_95(len(samples))
    ci = critical * sd / math.sqrt(len(samples)) if len(samples) > 1 else 0.0
    return {
        "algorithm": name,
        "runs": runs,
        "mean_seconds": mean,
        "sd_seconds": sd,
        "ci95_seconds": ci,
        "ci95_method": method,
        "ci95_critical": critical,
        "last_result": result,
        "samples_seconds": samples,
    }


def subgraph_edges(edges: list[tuple[int, int, float]], nodes: list[int]) -> tuple[list[int], list[tuple[int, int, float]]]:
    mapping = {old: new for new, old in enumerate(nodes)}
    out = []
    for a, b, w in edges:
        if a in mapping and b in mapping:
            out.append((mapping[a], mapping[b], w))
    return nodes, out


def benchmark_algorithms(
    adj: list[set[int]],
    wadj: list[list[tuple[int, float]]],
    edges: list[tuple[int, int, float]],
    lcc: list[int],
    runs: int,
    rng: random.Random,
) -> list[dict]:
    start = lcc[0]
    small_size = min(120, len(lcc))
    fw_size = min(70, len(lcc))
    small_nodes = rng.sample(lcc, small_size) if len(lcc) > small_size else list(lcc)
    fw_nodes = rng.sample(lcc, fw_size) if len(lcc) > fw_size else list(lcc)
    _, small_edges = subgraph_edges(edges, small_nodes)
    _, fw_edges = subgraph_edges(edges, fw_nodes)
    small_wadj = [[] for _ in small_nodes]
    for a, b, w in small_edges:
        small_wadj[a].append((b, w))
        small_wadj[b].append((a, w))
    return [
        timed("BFS", lambda: len(bfs_order(adj, start)), runs),
        timed("DFS", lambda: len(dfs_order(adj, start)), runs),
        timed("Verificacao de Eulerianidade", lambda: len(lcc) == len(adj) and all(len(neigh) % 2 == 0 for neigh in adj), runs),
        timed("Dijkstra", lambda: sum(math.isfinite(x) for x in dijkstra(wadj, start)), runs),
        timed("Bellman-Ford (subgrafo)", lambda: sum(math.isfinite(x) for x in bellman_ford(len(small_nodes), small_edges, 0)), runs),
        timed("Floyd-Warshall (subgrafo)", lambda: len(floyd_warshall(len(fw_nodes), fw_edges)), runs),
        timed("Tarjan", lambda: tuple(len(x) for x in tarjan_articulation_bridges(adj)), runs),
        timed("Kruskal/MST", lambda: mst_kruskal(len(adj), edges)["forest_edges"], runs),
    ]


def robustness_metrics(adj: list[set[int]], active: set[int], rng: random.Random, samples: int) -> dict:
    comps = components(adj, active)
    lcc = comps[0] if comps else []
    path = path_summary(adj, lcc, exact_limit=0, samples=samples, rng=rng)
    isolates = sum(1 for u in active if not (adj[u] & active))
    return {
        "largest_component_size": len(lcc),
        "largest_component_fraction": len(lcc) / len(active) if active else 0.0,
        "components": len(comps),
        "isolated_fraction": isolates / len(active) if active else 0.0,
        "average_path_length_lcc": path["average_path_length"],
    }


def robustness(adj: list[set[int]], runs: int, rng: random.Random, path_samples: int) -> dict:
    n = len(adj)
    remove_count = max(1, math.ceil(0.05 * n))
    all_nodes = set(range(n))
    random_runs = []
    for _ in range(runs):
        removed = set(rng.sample(range(n), remove_count))
        random_runs.append(robustness_metrics(adj, all_nodes - removed, rng, path_samples))
    ranked = sorted(range(n), key=lambda u: len(adj[u]), reverse=True)
    central_removed = set(ranked[:remove_count])
    central = robustness_metrics(adj, all_nodes - central_removed, rng, path_samples)
    summary = {}
    for key in random_runs[0]:
        vals = [r[key] for r in random_runs if r[key] is not None]
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        critical, method = confidence_critical_95(len(vals))
        summary[key] = {
            "mean": statistics.mean(vals),
            "sd": sd,
            "ci95": critical * sd / math.sqrt(len(vals)) if len(vals) > 1 else 0.0,
            "ci95_method": method,
            "ci95_critical": critical,
            "central_attack": central[key],
        }
    return {"remove_count": remove_count, "path_samples": path_samples, "random_runs": random_runs, "summary": summary, "centrality_used": "degree"}


def quantile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    pos = (len(sorted_vals) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] * (hi - pos) + sorted_vals[hi] * (pos - lo)


def robustness_svg(rob: dict) -> None:
    metrics = [
        ("largest_component_size", "Maior componente"),
        ("components", "Componentes"),
        ("isolated_fraction", "Fracao isolada"),
        ("average_path_length_lcc", "Distancia media"),
    ]
    width, height = 1200, 680
    left, right, top, bottom = 76, 42, 118, 96
    panel_gap = 34
    panel_w = (width - left - right - panel_gap * (len(metrics) - 1)) / len(metrics)
    panel_h = height - top - bottom
    elements = [
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="76" y="34" font-size="22" font-family="Arial" font-weight="700" fill="#111827">Robustez apos remocao de 5% dos vertices</text>',
        '<text x="76" y="58" font-size="13" font-family="Arial" fill="#475569">Boxplots das remocoes aleatorias; ponto vermelho mostra ataque aos vertices de maior grau.</text>',
        '<rect x="770" y="82" width="18" height="18" fill="#bfdbfe" stroke="#1d4ed8"/><text x="796" y="96" font-size="13" font-family="Arial" fill="#334155">remocoes aleatorias</text>',
        '<circle cx="962" cy="91" r="7" fill="#dc2626"/><text x="978" y="96" font-size="13" font-family="Arial" fill="#334155">ataque por grau</text>',
    ]
    for i, (key, label) in enumerate(metrics):
        vals = sorted(float(r[key]) for r in rob["random_runs"] if r[key] is not None)
        central = float(rob["summary"][key]["central_attack"])
        low = min(vals + [central])
        high = max(vals + [central])
        if abs(high - low) < 1e-12:
            low -= 0.5
            high += 0.5
        pad_value = (high - low) * 0.08
        low = max(0.0, low - pad_value)
        high += pad_value
        span = high - low
        q1 = quantile(vals, 0.25)
        med = quantile(vals, 0.50)
        q3 = quantile(vals, 0.75)
        whisk_low = min(vals)
        whisk_high = max(vals)
        panel_left = left + i * (panel_w + panel_gap)
        panel_right = panel_left + panel_w
        panel_bottom = top + panel_h
        x_mid = panel_left + panel_w * 0.50
        box_w = min(82, panel_w * 0.36)

        def sy(value: float) -> float:
            return panel_bottom - (value - low) / span * panel_h

        y_q1, y_med, y_q3 = sy(q1), sy(med), sy(q3)
        y_low, y_high = sy(whisk_low), sy(whisk_high)
        y_central = sy(central)
        elements.append(f'<rect x="{panel_left:.1f}" y="{top}" width="{panel_w:.1f}" height="{panel_h}" fill="#f8fafc" stroke="#e2e8f0"/>')
        for tick in linear_ticks(low, high, 5):
            y = sy(tick)
            elements.append(f'<line x1="{panel_left:.1f}" y1="{y:.1f}" x2="{panel_right:.1f}" y2="{y:.1f}" stroke="#e5e7eb"/>')
            elements.append(f'<text x="{panel_left+5:.1f}" y="{y-4:.1f}" font-size="10" font-family="Arial" fill="#64748b">{fmt_tick(tick)}</text>')
        elements.extend(
            [
                f'<line x1="{x_mid:.1f}" y1="{y_high:.1f}" x2="{x_mid:.1f}" y2="{y_low:.1f}" stroke="#334155" stroke-width="2"/>',
                f'<line x1="{x_mid-box_w/3:.1f}" y1="{y_high:.1f}" x2="{x_mid+box_w/3:.1f}" y2="{y_high:.1f}" stroke="#334155" stroke-width="2"/>',
                f'<line x1="{x_mid-box_w/3:.1f}" y1="{y_low:.1f}" x2="{x_mid+box_w/3:.1f}" y2="{y_low:.1f}" stroke="#334155" stroke-width="2"/>',
                f'<rect x="{x_mid-box_w/2:.1f}" y="{min(y_q1,y_q3):.1f}" width="{box_w:.1f}" height="{max(3.0, abs(y_q3-y_q1)):.1f}" fill="#bfdbfe" stroke="#1d4ed8" stroke-width="2" opacity="0.92"><title>aleatoria: Q1={q1:.4f}; mediana={med:.4f}; Q3={q3:.4f}</title></rect>',
                f'<line x1="{x_mid-box_w/2:.1f}" y1="{y_med:.1f}" x2="{x_mid+box_w/2:.1f}" y2="{y_med:.1f}" stroke="#1e3a8a" stroke-width="3"/>',
                f'<circle cx="{x_mid+box_w*0.82:.1f}" cy="{y_central:.1f}" r="7" fill="#dc2626"><title>ataque por grau: {central:.4f}</title></circle>',
                f'<text x="{x_mid:.1f}" y="{height-52}" font-size="13" font-family="Arial" text-anchor="middle" fill="#111827">{svg_escape(label)}</text>',
                f'<text x="{x_mid:.1f}" y="{height-31}" font-size="11" font-family="Arial" text-anchor="middle" fill="#475569">mediana {fmt_tick(med)}; ataque {fmt_tick(central)}</text>',
            ]
        )
    svg = "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', *elements, "</svg>"])
    (RESULTS / "robustness.svg").write_text(svg, encoding="utf-8")

    def draw_robustness_png(draw):
        draw.text((76, 18), "Robustez apos remocao de 5% dos vertices", fill="#111827")
        draw.text((76, 44), "Boxplots das remocoes aleatorias; ponto vermelho mostra ataque por grau.", fill="#475569")
        draw.rectangle((770, 82, 788, 100), fill="#bfdbfe", outline="#1d4ed8")
        draw.text((796, 84), "remocoes aleatorias", fill="#334155")
        draw.ellipse((955, 84, 969, 98), fill="#dc2626")
        draw.text((978, 84), "ataque por grau", fill="#334155")
        for i, (key, label) in enumerate(metrics):
            vals = sorted(float(r[key]) for r in rob["random_runs"] if r[key] is not None)
            central = float(rob["summary"][key]["central_attack"])
            low = min(vals + [central])
            high = max(vals + [central])
            if abs(high - low) < 1e-12:
                low -= 0.5
                high += 0.5
            pad_value = (high - low) * 0.08
            low = max(0.0, low - pad_value)
            high += pad_value
            span = high - low
            q1 = quantile(vals, 0.25)
            med = quantile(vals, 0.50)
            q3 = quantile(vals, 0.75)
            whisk_low = min(vals)
            whisk_high = max(vals)
            panel_left = left + i * (panel_w + panel_gap)
            panel_right = panel_left + panel_w
            panel_bottom = top + panel_h
            x_mid = panel_left + panel_w * 0.50
            box_w = min(84, panel_w * 0.38)

            def sy_png(value: float) -> float:
                return panel_bottom - (value - low) / span * panel_h

            y_q1, y_med, y_q3 = sy_png(q1), sy_png(med), sy_png(q3)
            y_low, y_high = sy_png(whisk_low), sy_png(whisk_high)
            y_central = sy_png(central)
            draw.rectangle((panel_left, top, panel_right, panel_bottom), fill="#f8fafc", outline="#e2e8f0")
            for tick in linear_ticks(low, high, 5):
                y = sy_png(tick)
                draw.line((panel_left, y, panel_right, y), fill="#e5e7eb", width=1)
                draw.text((panel_left + 5, y - 11), fmt_tick(tick), fill="#64748b")
            draw.line((x_mid, y_high, x_mid, y_low), fill="#334155", width=2)
            draw.line((x_mid - box_w / 3, y_high, x_mid + box_w / 3, y_high), fill="#334155", width=2)
            draw.line((x_mid - box_w / 3, y_low, x_mid + box_w / 3, y_low), fill="#334155", width=2)
            draw.rectangle((x_mid - box_w / 2, min(y_q1, y_q3), x_mid + box_w / 2, max(y_q1, y_q3)), fill="#93c5fd", outline="#1d4ed8")
            draw.line((x_mid - box_w / 2, y_med, x_mid + box_w / 2, y_med), fill="#1e3a8a", width=3)
            draw.ellipse((x_mid + box_w * 0.82 - 7, y_central - 7, x_mid + box_w * 0.82 + 7, y_central + 7), fill="#dc2626")
            draw.text((x_mid - panel_w * 0.30, height - 54), label, fill="#111827")
            draw.text((x_mid - panel_w * 0.30, height - 34), f"med {fmt_tick(med)} / ataque {fmt_tick(central)}", fill="#475569")

    draw_png(RESULTS / "robustness.png", width, height, draw_robustness_png)


def benchmark_svg(benchmarks: list[dict]) -> None:
    width, height = 1200, 660
    left, right, top, bottom = 98, 42, 86, 132
    plot_left, plot_right = left, width - right
    plot_bottom = height - bottom
    values = [max(float(b["mean_seconds"]), 1e-12) for b in benchmarks]
    ci_values = [max(float(b.get("ci95_seconds", 0.0)), 0.0) for b in benchmarks]
    floor = min(values) / 5
    min_log = math.floor(math.log10(max(min(values) / 2, 1e-12)))
    max_log = math.ceil(math.log10(max(values) * 2))
    step = (plot_right - plot_left) / len(benchmarks)
    bar_w = step * 0.58

    def sx_index(i: int) -> float:
        return plot_left + i * step + step / 2

    def sy_log(value: float) -> float:
        log_value = math.log10(max(value, floor, 1e-12))
        return plot_bottom - (log_value - min_log) / max(max_log - min_log, 1e-9) * (plot_bottom - top)

    y_ticks = [(float(i), f"1e{i}s") for i in range(int(min_log), int(max_log) + 1)]
    elements = svg_axes(
        width,
        height,
        left,
        right,
        top,
        bottom,
        "Tempo medio observado por algoritmo",
        "Escala log10 em segundos; barras mostram media e hastes mostram IC 95%.",
        "algoritmo",
        "tempo medio em escala log10",
        [],
        y_ticks,
        lambda value: value,
        lambda value: plot_bottom - (value - min_log) / max(max_log - min_log, 1e-9) * (plot_bottom - top),
    )
    for i, b in enumerate(benchmarks):
        x_mid = sx_index(i)
        mean = max(float(b["mean_seconds"]), floor)
        ci = ci_values[i]
        y = sy_log(mean)
        lower = sy_log(max(mean - ci, floor))
        upper = sy_log(mean + ci)
        elements.append(
            f'<rect x="{x_mid-bar_w/2:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{plot_bottom-y:.1f}" '
            f'fill="#0f766e" opacity="0.86"><title>{svg_escape(b["algorithm"])}: {mean:.6g}s +/- {ci:.3g}s</title></rect>'
        )
        elements.append(f'<line x1="{x_mid:.1f}" y1="{upper:.1f}" x2="{x_mid:.1f}" y2="{lower:.1f}" stroke="#111827" stroke-width="1.6"/>')
        elements.append(f'<line x1="{x_mid-9:.1f}" y1="{upper:.1f}" x2="{x_mid+9:.1f}" y2="{upper:.1f}" stroke="#111827" stroke-width="1.6"/>')
        elements.append(f'<line x1="{x_mid-9:.1f}" y1="{lower:.1f}" x2="{x_mid+9:.1f}" y2="{lower:.1f}" stroke="#111827" stroke-width="1.6"/>')
        elements.append(f'<text x="{x_mid:.1f}" y="{y-7:.1f}" font-size="10" font-family="Arial" text-anchor="middle" fill="#334155">{mean:.2e}s</text>')
        name = b["algorithm"].replace("Verificacao de ", "").replace(" (subgrafo)", "")
        elements.append(
            f'<text x="{x_mid-8:.1f}" y="{height-58}" font-size="11" font-family="Arial" fill="#111827" transform="rotate(-35 {x_mid-8:.1f},{height-58})">{svg_escape(name)}</text>'
        )
    svg = "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', *elements, "</svg>"])
    (RESULTS / "algorithm_times.svg").write_text(svg, encoding="utf-8")

    def draw_algorithm_png(draw):
        draw_png_axes(
            draw,
            width,
            height,
            left,
            right,
            top,
            bottom,
            "Tempo medio observado por algoritmo",
            "Escala log10 em segundos; barras mostram media e hastes mostram IC 95%.",
            "algoritmo",
            "tempo log10",
            [],
            y_ticks,
            lambda value: value,
            lambda value: plot_bottom - (value - min_log) / max(max_log - min_log, 1e-9) * (plot_bottom - top),
        )
        for i, b in enumerate(benchmarks):
            x_mid = sx_index(i)
            mean = max(float(b["mean_seconds"]), floor)
            ci = ci_values[i]
            y = sy_log(mean)
            lower = sy_log(max(mean - ci, floor))
            upper = sy_log(mean + ci)
            draw.rectangle((x_mid - bar_w / 2, y, x_mid + bar_w / 2, plot_bottom), fill="#0f766e")
            draw.line((x_mid, upper, x_mid, lower), fill="#111827", width=2)
            draw.line((x_mid - 9, upper, x_mid + 9, upper), fill="#111827", width=2)
            draw.line((x_mid - 9, lower, x_mid + 9, lower), fill="#111827", width=2)
            name = b["algorithm"].replace("Verificacao de ", "").replace(" (subgrafo)", "")
            draw.text((x_mid - 34, height - 68), name[:14], fill="#111827")

    draw_png(RESULTS / "algorithm_times.png", width, height, draw_algorithm_png)


def main() -> None:
    args = parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    labels, edges, adj, wadj, meta = load_graph()
    n = len(adj)
    m = len(edges)
    degrees = [len(a) for a in adj]
    comps = components(adj)
    lcc = comps[0] if comps else []
    path = path_summary(adj, lcc, args.exact_path_limit, args.path_samples, rng)
    clustering, triangles = clustering_and_triangles(adj)
    random_baseline = random_graph_baseline(n, m, args.exact_path_limit, args.path_samples, args.random_graphs, rng)
    power = power_law_fit(degrees)
    benchmarks = benchmark_algorithms(adj, wadj, edges, lcc, args.benchmark_runs, rng)
    rob = robustness(adj, args.robustness_runs, rng, args.path_samples)
    arts, bridges = tarjan_articulation_bridges(adj)
    mst = mst_kruskal(n, edges)
    eulerian = len(comps) == 1 and all(d % 2 == 0 for d in degrees)

    degree_distribution_svg(degrees)
    robustness_svg(rob)
    benchmark_svg(benchmarks)

    with (RESULTS / "benchmark_times.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "algorithm",
            "runs",
            "mean_seconds",
            "sd_seconds",
            "ci95_seconds",
            "ci95_method",
            "ci95_critical",
            "last_result",
        ])
        for b in benchmarks:
            w.writerow([
                b["algorithm"],
                b["runs"],
                b["mean_seconds"],
                b["sd_seconds"],
                b["ci95_seconds"],
                b["ci95_method"],
                b["ci95_critical"],
                b["last_result"],
            ])

    with (RESULTS / "benchmark_raw_times.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["algorithm", "run", "seconds"])
        for b in benchmarks:
            for i, seconds in enumerate(b["samples_seconds"], start=1):
                w.writerow([b["algorithm"], i, seconds])

    with (RESULTS / "robustness_runs.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "scenario",
            "run",
            "largest_component_size",
            "largest_component_fraction",
            "components",
            "isolated_fraction",
            "average_path_length_lcc",
        ])
        for i, row in enumerate(rob["random_runs"], start=1):
            w.writerow([
                "random_5_percent",
                i,
                row["largest_component_size"],
                row["largest_component_fraction"],
                row["components"],
                row["isolated_fraction"],
                row["average_path_length_lcc"],
            ])
        central_row = {key: value["central_attack"] for key, value in rob["summary"].items()}
        w.writerow([
            "degree_centrality_5_percent",
            1,
            central_row["largest_component_size"],
            central_row["largest_component_fraction"],
            central_row["components"],
            central_row["isolated_fraction"],
            central_row["average_path_length_lcc"],
        ])

    result = {
        "student_graph_rule": student_graph_rule(),
        "metadata": meta,
        "structural": {
            "vertices": n,
            "edges": m,
            "degree_min": min(degrees) if degrees else 0,
            "degree_max": max(degrees) if degrees else 0,
            "degree_mean": sum(degrees) / n if n else 0,
            "density": (2 * m) / (n * (n - 1)) if n > 1 else 0,
            "components": len(comps),
            "component_sizes": [len(c) for c in comps],
            "largest_component_size": len(lcc),
            "diameter": path["diameter"],
            "radius": path["radius"],
            "average_path_length": path["average_path_length"],
            "average_path_length_source_sd": path["average_path_length_source_sd"],
            "average_path_length_ci95": path["average_path_length_ci95"],
            "average_path_length_ci95_method": path["ci95_method"],
            "diameter_is_lower_bound": path["diameter_is_lower_bound"],
            "radius_is_upper_bound": path["radius_is_upper_bound"],
            "path_calculation_mode": path["mode"],
            "path_sample_size": path["sample_size"],
            "path_component_size": path["component_size"],
            "average_clustering": clustering,
            "triangles": triangles,
            "eulerian": eulerian,
            "articulation_points": len(arts),
            "bridges": len(bridges),
            "mst": mst,
        },
        "small_world": {
            "graph_average_path_length": path["average_path_length"],
            "random_average_path_length": random_baseline["average_path_length"]["mean"],
            "graph_clustering": clustering,
            "random_clustering": random_baseline["clustering"]["mean"],
            "random_baseline": random_baseline,
            "interpretation": (
                "Ha indicio de small-world se a distancia media e proxima da aleatoria "
                "e o clustering e muito maior que o aleatorio."
            ),
        },
        "power_law": power,
        "robustness": rob,
        "benchmarks": benchmarks,
        "validation": {
            "metadata_nodes": int(meta.get("nodes", n)),
            "processed_nodes": n,
            "metadata_edges": int(meta.get("edges", m)),
            "processed_edges": m,
            "embedding_dimensions": int(meta.get("embedding_dimensions", 0)),
            "uses_all_subreddit_vertices": bool(meta.get("uses_all_subreddit_vertices")),
            "full_processed_graph_analyzed": int(meta.get("nodes", n)) == n and int(meta.get("edges", m)) == m,
        },
        "runtime_environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "seed": args.seed,
            "random_graph_runs": args.random_graphs,
        },
        "confidence_interval_policy": "Normal/Z quando n >= 30; t-Student quando n < 30.",
        "complexities": {
            "BFS": "O(V + E)",
            "DFS": "O(V + E)",
            "Verificacao de Eulerianidade": "O(V + E), considerando checagem de conexidade e graus pares",
            "Dijkstra": "O((V + E) log V) com heap binario",
            "Bellman-Ford": "O(VE)",
            "Floyd-Warshall": "O(V^3)",
            "Tarjan": "O(V + E)",
            "Kruskal/MST": "O(E log E)",
        },
    }
    (RESULTS / "analysis_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["structural"], indent=2))


if __name__ == "__main__":
    main()
