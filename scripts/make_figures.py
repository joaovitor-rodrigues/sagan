"""Gera as figuras (SVG) das páginas Teoria e Sobre.

Uso:  python scripts/make_figures.py

Saída: templates/app/figures/*.svg — incluídas inline nos templates com
{% include %}, o que permite hover (static/app/charts.js) e herda as fontes
e cores do site.

Dados:
  scripts/data/wasp18_s2_bin002.json   curva de luz de WASP-18 (TIC 100100827),
                                       TESS Setor 2, pipeline SPOC, obtida pelo
                                       próprio SAGAN (remove_outliers σ=5, bin 0,02 d)
  scripts/data/wasp18_s2_fold.json     mesma curva dobrada (P=0,9414445 d,
                                       T0=1354,46 BTJD) e agrupada em 0,004 d
  scripts/data/toi_dispositions_*.json contagem do catálogo TOI (ExoFOP)
O modelo de trânsito é calculado aqui mesmo (integração numérica do disco
estelar com escurecimento de limbo quadrático; ver Mandel & Agol 2002).
"""
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scripts" / "data"
OUT = ROOT / "templates" / "app" / "figures"

PURPLE = "#5B3FBF"
SERIES = ["#2a78d6", "#eb6834"]          # slots 1–2 da paleta validada (dataviz)
INK, INK2, MUTED = "#1A1625", "#52496B", "#7A7196"
GRID, AXIS = "#ECE9F5", "#CFC9E3"


def fmt(v, d=0):
    """Número em formato pt-BR (vírgula decimal, ponto de milhar)."""
    # separador de milhar só a partir de 5 dígitos (evita ler 1.360 BTJD como 1,36)
    s = f"{v:,.{d}f}" if abs(v) >= 10000 else f"{v:.{d}f}"
    s = s.replace(",", "§").replace(".", ",").replace("§", ".")
    return s.replace("-", "\u2212")         # sinal de menos tipográfico


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


class Chart:
    def __init__(self, cid, title, desc, w=720, h=330, m=(18, 24, 52, 70)):
        self.id, self.title, self.desc = cid, title, desc
        self.w, self.h = w, h
        self.mt, self.mr, self.mb, self.ml = m
        self.parts = []
        self.hover = None

    # escalas -------------------------------------------------------------
    def scales(self, x0, x1, y0, y1):
        self.x0, self.x1, self.y0, self.y1 = x0, x1, y0, y1
        self.px0, self.px1 = self.ml, self.w - self.mr
        self.py0, self.py1 = self.h - self.mb, self.mt

    def X(self, v):
        return self.px0 + (v - self.x0) / (self.x1 - self.x0) * (self.px1 - self.px0)

    def Y(self, v):
        return self.py0 + (v - self.y0) / (self.y1 - self.y0) * (self.py1 - self.py0)

    def add(self, s):
        self.parts.append(s)

    # eixos ---------------------------------------------------------------
    def axes(self, xticks, yticks, xlabel, ylabel, xd=0, yd=0, xfmt=None, yfmt=None):
        xfmt = xfmt or (lambda v: fmt(v, xd))
        yfmt = yfmt or (lambda v: fmt(v, yd))
        for v in yticks:
            y = self.Y(v)
            self.add(f'<line class="sg-grid" x1="{self.px0}" x2="{self.px1}" y1="{y:.1f}" y2="{y:.1f}"/>')
            self.add(f'<text class="sg-tick" x="{self.px0 - 8}" y="{y + 4:.1f}" text-anchor="end">{yfmt(v)}</text>')
        for v in xticks:
            x = self.X(v)
            self.add(f'<line class="sg-tickmark" x1="{x:.1f}" x2="{x:.1f}" y1="{self.py0}" y2="{self.py0 + 5}"/>')
            self.add(f'<text class="sg-tick" x="{x:.1f}" y="{self.py0 + 20}" text-anchor="middle">{xfmt(v)}</text>')
        self.add(f'<line class="sg-axis" x1="{self.px0}" x2="{self.px1}" y1="{self.py0}" y2="{self.py0}"/>')
        self.add(f'<text class="sg-label" x="{(self.px0 + self.px1) / 2:.1f}" y="{self.h - 10}" text-anchor="middle">{esc(xlabel)}</text>')
        cy = (self.py0 + self.py1) / 2
        self.add(f'<text class="sg-label" transform="translate(16 {cy:.1f}) rotate(-90)" text-anchor="middle">{esc(ylabel)}</text>')

    def set_hover(self, xs, ys, xl, yl, xd, yd, color, series=None):
        self.hover = {"x": [round(float(v), 6) for v in xs], "y": [None if v is None else round(float(v), 6) for v in ys],
                      "xl": xl, "yl": yl, "xd": xd, "yd": yd, "color": color,
                      "sx": [self.x0, self.x1, self.px0, self.px1],
                      "sy": [self.y0, self.y1, self.py0, self.py1]}
        if series:
            self.hover["series"] = series

    def svg(self):
        hov = ""
        if self.hover:
            hov = f" data-hover='{json.dumps(self.hover, separators=(',', ':'), ensure_ascii=False)}'"
        body = "\n".join(self.parts)
        return (f'<svg class="sg-chart" id="{self.id}" viewBox="0 0 {self.w} {self.h}" role="img" '
                f'aria-labelledby="{self.id}-t {self.id}-d" preserveAspectRatio="xMidYMid meet"{hov}>\n'
                f'<title id="{self.id}-t">{esc(self.title)}</title>\n<desc id="{self.id}-d">{esc(self.desc)}</desc>\n'
                f'{body}\n</svg>\n')


def polyline(c, xs, ys, cls, color):
    pts = " ".join(f"{c.X(x):.1f},{c.Y(y):.1f}" for x, y in zip(xs, ys))
    c.add(f'<polyline class="{cls}" points="{pts}" style="stroke:{color}"/>')


def dots(c, xs, ys, r, color, cls="sg-dot"):
    out = [f'<g class="{cls}" style="fill:{color}">']
    for x, y in zip(xs, ys):
        out.append(f'<circle cx="{c.X(x):.1f}" cy="{c.Y(y):.1f}" r="{r}"/>')
    out.append("</g>")
    c.add("".join(out))


def save(name, svg):
    (OUT / f"{name}.svg").write_text(svg, encoding="utf-8")
    print("ok", name, f"{len(svg) / 1024:.0f} KB")


# ── Modelo de trânsito (escurecimento de limbo quadrático) ───────────────────

def transit_model(t_hours, k, a_rs, b, period_days, u1, u2, n=220):
    """Fluxo relativo integrando numericamente a área ocultada do disco."""
    inc = math.acos(b / a_rs)
    phase = 2 * math.pi * (np.asarray(t_hours) / 24.0) / period_days
    xc = a_rs * np.sin(phase)
    yc = a_rs * np.cos(phase) * math.cos(inc)

    g = np.linspace(-1, 1, n)
    gx, gy = np.meshgrid(g, g)
    inside_p = gx**2 + gy**2 <= 1
    px, py = gx[inside_p] * k, gy[inside_p] * k          # amostras no disco do planeta
    dA = (2 / n) ** 2 * k * k

    def intensity(r2):
        mu = np.sqrt(np.clip(1 - r2, 0, 1))
        return np.where(r2 <= 1, 1 - u1 * (1 - mu) - u2 * (1 - mu) ** 2, 0.0)

    total = math.pi * (1 - u1 / 3 - u2 / 6)              # fluxo do disco inteiro
    out = []
    for x, y in zip(xc, yc):
        if math.hypot(x, y) > 1 + k + 1e-9:
            out.append(1.0)
            continue
        r2 = (px + x) ** 2 + (py + y) ** 2
        out.append(1 - intensity(r2).sum() * dA / total)
    return np.array(out)


def fig_model():
    k, a_rs, b, P = 0.10, 8.0, 0.3, 3.0
    t = np.linspace(-2.6, 2.6, 261)
    uni = transit_model(t, k, a_rs, b, P, 0.0, 0.0)
    ld = transit_model(t, k, a_rs, b, P, 0.40, 0.26)
    c = Chart("fig-modelo", "Modelo de trânsito: disco uniforme e com escurecimento de limbo",
              "Duas curvas de luz teóricas para um planeta com 10% do raio da estrela. A curva do disco uniforme "
              "tem fundo plano com profundidade de 1%; com escurecimento de limbo o fundo é arredondado e mais "
              "profundo no centro.", h=370, m=(54, 24, 52, 70))
    c.scales(-2.6, 2.6, 0.9862, 1.0016)
    c.axes([-2, -1, 0, 1, 2], [0.988, 0.990, 0.992, 0.994, 0.996, 0.998, 1.000],
           "Tempo desde o centro do trânsito (horas)", "Fluxo relativo", yd=3)
    # δ = k²
    yk = c.Y(1 - k * k)
    c.add(f'<line class="sg-ref" x1="{c.px0}" x2="{c.px1}" y1="{yk:.1f}" y2="{yk:.1f}"/>')
    c.add(f'<text class="sg-note" x="{c.px1 - 4}" y="{yk - 6:.1f}" text-anchor="end">δ = k² = 1%</text>')
    polyline(c, t, uni, "sg-line", SERIES[0])
    polyline(c, t, ld, "sg-line", SERIES[1])
    # rótulos diretos + legenda
    i = 200
    c.add(f'<text class="sg-direct" x="{c.X(t[i]) + 8:.1f}" y="{c.Y(uni[i]) + 18:.1f}">disco uniforme</text>')
    j = 130
    c.add(f'<text class="sg-direct" x="{c.X(t[j]):.1f}" y="{c.Y(ld[j]) + 20:.1f}" text-anchor="middle">com escurecimento de limbo</text>')
    lx = c.px0 + 12
    for n, (lab, col) in enumerate([("Disco uniforme", SERIES[0]), ("Escurecimento de limbo (u₁=0,40; u₂=0,26)", SERIES[1])]):
        y = 16 + n * 18
        c.add(f'<line x1="{lx}" x2="{lx + 18}" y1="{y}" y2="{y}" style="stroke:{col}" class="sg-key"/>')
        c.add(f'<text class="sg-legend" x="{lx + 24}" y="{y + 4}">{lab}</text>')
    c.set_hover(t, ld, "Tempo (h)", "Fluxo (limbo)", 2, 4, SERIES[1],
                series=[{"name": "Uniforme", "y": [round(float(v), 6) for v in uni], "color": SERIES[0], "d": 4}])
    save("fig-modelo", c.svg())


def fig_wasp18_series():
    d = json.loads((DATA / "wasp18_s2_bin002.json").read_text())
    t, f = np.array(d["time_btjd"]), np.array(d["flux"])
    c = Chart("fig-wasp18-serie", "WASP-18: curva de luz do TESS, Setor 2",
              "Fluxo normalizado de WASP-18 ao longo de 27 dias. Há 28 quedas de cerca de 1% espaçadas de "
              "0,94 dia, uma lacuna no meio do setor durante a transmissão de dados, e variações menores entre os trânsitos.",
              h=300)
    c.scales(1353.5, 1382.2, 0.9875, 1.0020)
    c.axes(list(range(1355, 1382, 5)), [0.988, 0.992, 0.996, 1.000],
           "Tempo (BTJD = BJD − 2.457.000)", "Fluxo normalizado", yd=3)
    gap = (t > 1367.2) & (t < 1368.5)
    if not gap.any():
        g0 = c.X(1367.25); g1 = c.X(1368.55)
        c.add(f'<rect class="sg-gap" x="{g0:.1f}" y="{c.py1}" width="{g1 - g0:.1f}" height="{c.py0 - c.py1}"/>')
        c.add(f'<text class="sg-note" x="{(g0 + g1) / 2:.1f}" y="{c.py0 - 8}" text-anchor="middle">downlink</text>')
    dots(c, t, f, 1.9, PURPLE)
    c.set_hover(t, f, "Tempo (BTJD)", "Fluxo", 3, 5, PURPLE)
    save("fig-wasp18-serie", c.svg())
    return t, f


def fig_bls(t, f):
    from astropy.timeseries import BoxLeastSquares
    periods = np.exp(np.linspace(np.log(0.3), np.log(5.0), 24000))
    res = BoxLeastSquares(t, f).power(periods, [0.04, 0.06, 0.08, 0.10])
    p = res.power / res.power.max()
    ibest = int(np.argmax(p))
    pbest = periods[ibest]
    c = Chart("fig-bls", "Periodograma BLS de WASP-18",
              f"Potência BLS normalizada em função do período de teste. O pico mais alto está em "
              f"{fmt(pbest, 4)} dia; picos menores aparecem em múltiplos e frações desse período.", h=300)
    lp = np.log10(periods)
    c.scales(math.log10(0.3), math.log10(5.0), 0, 1.08)
    xt = [0.3, 0.5, 1, 2, 3, 5]
    c.axes([math.log10(v) for v in xt], [0, 0.25, 0.5, 0.75, 1.0],
           "Período de teste (dias, escala logarítmica)", "Potência BLS (normalizada)",
           xfmt=lambda v: fmt(10 ** v, 1 if 10 ** v < 1 else 0), yd=2)
    # reduz pontos para o traço (máximo por pixel)
    cols = {}
    for x, y in zip(lp, p):
        px = int(c.X(x))
        cols[px] = max(cols.get(px, 0), y)
    xs = sorted(cols)
    pts = " ".join(f"{x},{c.Y(cols[x]):.1f}" for x in xs)
    c.add(f'<polyline class="sg-line" points="{pts}" style="stroke:{PURPLE}"/>')
    bx, by = c.X(math.log10(pbest)), c.Y(1)
    c.add(f'<circle class="sg-mark" cx="{bx:.1f}" cy="{by:.1f}" r="4.5" style="fill:{PURPLE}"/>')
    c.add(f'<text class="sg-direct" x="{bx + 10:.1f}" y="{by + 4:.1f}">P = {fmt(pbest, 4)} d</text>')
    for mult, lab in [(0.5, "P/2"), (2, "2P"), (3, "3P")]:
        pm = pbest * mult
        if 0.3 < pm < 5:
            i = int(np.argmin(abs(periods - pm)))
            win = slice(max(i - 25, 0), i + 25)
            j = win.start + int(np.argmax(p[win]))
            c.add(f'<text class="sg-note" x="{c.X(lp[j]):.1f}" y="{c.Y(p[j]) - 8:.1f}" text-anchor="middle">{lab}</text>')
    step = max(1, len(periods) // 1200)
    c.set_hover(periods[::step], p[::step], "Período (d)", "Potência", 4, 3, PURPLE)
    c.hover["logx"] = True
    save("fig-bls", c.svg())
    return pbest


def fig_fold():
    d = json.loads((DATA / "wasp18_s2_fold.json").read_text())
    ph, fl = np.array(d["phase_days"]) * 24, np.array(d["flux_ppm"])
    # painel A: trânsito
    c = Chart("fig-fold-transito", "WASP-18b: trânsito dobrado e agrupado",
              "Os 28 trânsitos do Setor 2 sobrepostos. A queda chega a cerca de 10.900 ppm (1,1%) e dura "
              "pouco mais de 2 horas.", w=350, h=300, m=(16, 12, 52, 66))
    sel = abs(ph) < 3.2
    c.scales(-3.2, 3.2, -11800, 900)
    c.axes([-3, -2, -1, 0, 1, 2, 3], [-10000, -7500, -5000, -2500, 0],
           "Horas desde o centro do trânsito", "Variação de fluxo (ppm)")
    dots(c, ph[sel], fl[sel], 3.2, PURPLE)
    c.set_hover(ph[sel], fl[sel], "Horas", "ppm", 2, 0, PURPLE)
    save("fig-fold-transito", c.svg())
    # painel B: fora do trânsito (curva de fase + eclipse secundário)
    c = Chart("fig-fold-fase", "WASP-18b: curva de fase fora do trânsito",
              "Mesmo conjunto, com o eixo vertical ampliado e o trânsito fora da escala. O brilho sobe "
              "e desce duas vezes por órbita e cai de novo perto de ±11 horas, quando o planeta passa atrás da estrela.",
              w=350, h=300, m=(16, 12, 52, 56))
    c.scales(-11.6, 11.6, -650, 650)
    c.axes([-10, -5, 0, 5, 10], [-600, -300, 0, 300, 600], "Horas desde o centro do trânsito", "ppm")
    keep = (abs(ph) > 1.3) & (abs(fl) < 650)
    xa, ya = c.X(-1.3), c.X(1.3)
    c.add(f'<rect class="sg-gap" x="{xa:.1f}" y="{c.py1}" width="{ya - xa:.1f}" height="{c.py0 - c.py1}"/>')
    c.add(f'<text class="sg-note" x="{(xa + ya) / 2:.1f}" y="{c.py1 + 12}" text-anchor="middle">trânsito</text>')
    dots(c, ph[keep], fl[keep], 3.2, PURPLE)
    for xe in (-11.2, 11.2):
        c.add(f'<text class="sg-note" x="{c.X(xe):.1f}" y="{c.Y(-560):.1f}" text-anchor="{"start" if xe < 0 else "end"}">eclipse secundário</text>')
    c.set_hover(ph[keep], fl[keep], "Horas", "ppm", 2, 0, PURPLE)
    save("fig-fold-fase", c.svg())


def fig_toi():
    d = json.loads(sorted(DATA.glob("toi_dispositions_*.json"))[-1].read_text())
    names = {"PC": "PC — candidato planetário", "EB": "EB — binária eclipsante", "KP": "KP — planeta já conhecido",
             "CP": "CP — planeta confirmado", "O": "O — outro", "IS": "IS — ruído instrumental",
             "V": "V — variabilidade estelar", "FP": "FP — falso positivo"}
    items = sorted(d["counts"].items(), key=lambda kv: -kv[1])
    w, row, top, left = 720, 34, 14, 210
    h = top + row * len(items) + 30
    vmax = 7000
    parts = []
    tips = []
    px1 = w - 70
    def X(v): return left + v / vmax * (px1 - left)
    for v in range(0, vmax + 1, 1000):
        x = X(v)
        parts.append(f'<line class="sg-grid" x1="{x:.1f}" x2="{x:.1f}" y1="{top - 4}" y2="{h - 26}"/>')
        parts.append(f'<text class="sg-tick" x="{x:.1f}" y="{h - 8}" text-anchor="middle">{fmt(v)}</text>')
    for n, (code, val) in enumerate(items):
        y = top + n * row
        bw = max(X(val) - left, 2)
        pct = val / d["total"] * 100
        tip = f"{names[code]}: {fmt(val)} ({fmt(pct, 1)}%)"
        tips.append(tip)
        parts.append(f'<text class="sg-cat" x="{left - 10}" y="{y + 17}" text-anchor="end">{esc(names[code])}</text>')
        r = min(4, bw / 2)
        x0 = left
        parts.append(f'<path class="sg-bar" data-tip="{esc(tip)}" style="fill:{PURPLE}" '
                     f'd="M{x0},{y + 4} h{bw - r:.1f} a{r},{r} 0 0 1 {r},{r} v{22 - 2 * r} a{r},{r} 0 0 1 -{r},{r} h-{bw - r:.1f} z">'
                     f'<title>{esc(tip)}</title></path>')
        parts.append(f'<text class="sg-value" x="{x0 + bw + 6:.1f}" y="{y + 20}">{fmt(val)}</text>')
    svg = (f'<svg class="sg-chart" id="fig-toi" viewBox="0 0 {w} {h}" role="img" aria-labelledby="fig-toi-t fig-toi-d">\n'
           f'<title id="fig-toi-t">Disposições do catálogo TOI</title>\n'
           f'<desc id="fig-toi-d">{esc("; ".join(tips))}. Total: {fmt(d["total"])} TOIs em {d["retrieved"]}.</desc>\n'
           + "\n".join(parts) + "\n</svg>\n")
    save("fig-toi", svg)
    return d


# ── Diagramas ────────────────────────────────────────────────────────────────

def fig_geometry():
    """Geometria do trânsito alinhada à curva de luz (contatos I–IV)."""
    W, H = 720, 400
    cx, cy, R = 360, 120, 92
    k, b = 0.16, 0.35
    r = k * R
    yp = cy + b * R
    def cx_at(s): return cx + s * R
    xI, xII = -math.sqrt((1 + k) ** 2 - b ** 2), -math.sqrt((1 - k) ** 2 - b ** 2)
    xs = [xI, xII, -xII, -xI]
    P = []
    P.append('<defs><radialGradient id="ld" cx="50%" cy="50%" r="50%">'
             '<stop offset="0%" stop-color="#FFF4C9"/><stop offset="70%" stop-color="#FBD37A"/>'
             '<stop offset="100%" stop-color="#E9963A"/></radialGradient>'
             '<marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path d="M0,0 L8,4 L0,8 z" fill="#7A7196"/></marker></defs>')
    P.append(f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#ld)"/>')
    P.append(f'<text class="sg-note" x="{cx - R - 14}" y="{cy - R + 18}" text-anchor="end">estrela (R★)</text>')
    P.append(f'<text class="sg-note" x="{cx - R - 14}" y="{cy - R + 33}" text-anchor="end">borda mais escura:</text>')
    P.append(f'<text class="sg-note" x="{cx - R - 14}" y="{cy - R + 48}" text-anchor="end">escurecimento de limbo</text>')
    # trajetória e parâmetro de impacto
    P.append(f'<line class="sg-path" x1="{cx_at(xI) - 60:.1f}" x2="{cx_at(-xI) + 60:.1f}" y1="{yp:.1f}" y2="{yp:.1f}" marker-end="url(#arr)"/>')
    P.append(f'<line class="sg-dim" x1="{cx}" x2="{cx}" y1="{cy}" y2="{yp:.1f}" marker-end="url(#arr)"/>')
    P.append(f'<circle cx="{cx}" cy="{cy}" r="2.5" fill="#7A7196"/>')
    P.append(f'<text class="sg-note" x="{cx + 6}" y="{(cy + yp) / 2 + 4:.1f}">b·R★</text>')
    for n, (s_, lab) in enumerate(zip(xs, ["I", "II", "III", "IV"])):
        x = cx_at(s_)
        P.append(f'<circle cx="{x:.1f}" cy="{yp:.1f}" r="{r:.1f}" fill="#1A1625" fill-opacity="{0.55 if n in (0, 3) else 0.85}"/>')
        P.append(f'<text class="sg-cat" x="{x:.1f}" y="{yp + r + 18:.1f}" text-anchor="middle">{lab}</text>')
    P.append(f'<text class="sg-note" x="{cx_at(-xI) + 20:.1f}" y="{yp - 10:.1f}">planeta (Rp)</text>')
    # curva de luz alinhada
    y1, y0 = 270, 350        # fluxo 1 e fundo
    t = np.linspace(-1.55, 1.55, 400)
    # aproximação visual: área ocultada de disco uniforme + leve curvatura (limbo)
    def frac(x):
        d = math.hypot(x, b)
        if d >= 1 + k: return 0.0
        if d <= 1 - k: return 1.0
        # sobreposição de dois círculos (raio 1 e k), normalizada por k²
        a1 = math.acos((d * d + 1 - k * k) / (2 * d))
        a2 = math.acos((d * d + k * k - 1) / (2 * d * k))
        area = a1 + k * k * a2 - 0.5 * math.sqrt(max((-d + 1 + k) * (d + 1 - k) * (d - 1 + k) * (d + 1 + k), 0))
        return area / (math.pi * k * k)
    pts = []
    for x in t:
        mu = math.sqrt(max(1 - x * x - b * b, 0))
        depth = frac(x) * (0.80 + 0.20 * mu / math.sqrt(1 - b * b))
        pts.append(f"{cx_at(x):.1f},{y1 + depth * (y0 - y1):.1f}")
    P.append(f'<line class="sg-grid" x1="{cx_at(-1.55):.1f}" x2="{cx_at(1.55):.1f}" y1="{y1}" y2="{y1}"/>')
    P.append(f'<polyline class="sg-line" points="{" ".join(pts)}" style="stroke:{PURPLE}"/>')
    P.append(f'<text class="sg-note" x="{cx_at(-1.55):.1f}" y="{y1 - 8}">fluxo observado</text>')
    for s_ in xs:
        x = cx_at(s_)
        P.append(f'<line class="sg-guide" x1="{x:.1f}" x2="{x:.1f}" y1="{yp + r + 24:.1f}" y2="{y0 + 8}"/>')
    # δ
    xd = cx_at(1.42)
    P.append(f'<line class="sg-dim" x1="{xd:.1f}" x2="{xd:.1f}" y1="{y1}" y2="{y0 - 6}" marker-start="url(#arr)" marker-end="url(#arr)"/>')
    P.append(f'<text class="sg-direct" x="{xd + 8:.1f}" y="{(y1 + y0) / 2 + 4:.1f}">δ ≈ (Rp/R★)²</text>')
    # durações
    def bracket(xa, xb, y, lab):
        P.append(f'<line class="sg-dim" x1="{xa:.1f}" x2="{xb:.1f}" y1="{y}" y2="{y}" marker-start="url(#arr)" marker-end="url(#arr)"/>')
        P.append(f'<text class="sg-note" x="{(xa + xb) / 2:.1f}" y="{y + 15}" text-anchor="middle">{lab}</text>')
    bracket(cx_at(xs[1]), cx_at(xs[2]), y0 + 2, "")
    P.append(f'<text class="sg-note" x="{cx:.1f}" y="{y0 - 10}" text-anchor="middle">T₂₃ (fundo)</text>')
    bracket(cx_at(xs[0]), cx_at(xs[3]), y0 + 24, "T₁₄ — duração total")
    bracket(cx_at(xs[0]), cx_at(xs[1]), y0 + 2, "")
    P.append(f'<text class="sg-note" x="{cx_at((xs[0] + xs[1]) / 2) - 8:.1f}" y="{y0 - 10}" text-anchor="end">τ (entrada)</text>')
    svg = (f'<svg class="sg-chart sg-diagram" id="fig-geometria" viewBox="0 0 {W} {H}" role="img" '
           f'aria-labelledby="fig-geometria-t fig-geometria-d">\n<title id="fig-geometria-t">Geometria de um trânsito</title>\n'
           f'<desc id="fig-geometria-d">O planeta cruza o disco da estrela a uma distância b do centro. Os contatos I a IV '
           f'marcam o início e o fim da entrada e da saída. Abaixo, a curva de luz alinhada: a queda δ, a duração total T14, '
           f'o fundo T23 e a entrada τ.</desc>\n' + "\n".join(P) + "\n</svg>\n")
    save("fig-geometria", svg)


def _box(P, x, y, w, h, title, sub="", cls="sg-node"):
    P.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{w}" height="{h}" rx="10"/>')
    if sub:
        P.append(f'<text class="sg-node-t" x="{x + w / 2}" y="{y + h / 2 - 3}" text-anchor="middle">{esc(title)}</text>')
        P.append(f'<text class="sg-node-s" x="{x + w / 2}" y="{y + h / 2 + 13}" text-anchor="middle">{esc(sub)}</text>')
    else:
        P.append(f'<text class="sg-node-t" x="{x + w / 2}" y="{y + h / 2 + 4}" text-anchor="middle">{esc(title)}</text>')


def _arrow(P, x1, y1, x2, y2, label="", dy=-6):
    P.append(f'<line class="sg-flow" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#arr2)"/>')
    if label:
        P.append(f'<text class="sg-note" x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 + dy}" text-anchor="middle">{esc(label)}</text>')


ARR2 = ('<defs><marker id="arr2" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto">'
        '<path d="M0,0 L8,4 L0,8 z" class="sg-arrowhead"/></marker></defs>')


def fig_pipeline():
    """Do pixel ao TOI (Guerrero et al. 2021)."""
    W, H = 720, 250
    P = [ARR2]
    w, h, y = 120, 58, 30
    xs = [10, 152, 294, 436, 578]
    steps = [("Câmeras TESS", "2 min / 30 min"), ("Curvas de luz", "SPOC · QLP"),
             ("Busca de sinais", "TCEs (TPS · BLS)"), ("Triagem e vetting", "humanos + IA"),
             ("TOI", "catálogo público")]
    for x, (a, b_) in zip(xs, steps):
        _box(P, x, y, w, h, a, b_, "sg-node sg-node-accent" if a == "TOI" else "sg-node")
    for i in range(4):
        _arrow(P, xs[i] + w, y + h / 2, xs[i + 1] - 4, y + h / 2)
    # follow-up e desfechos
    _box(P, 578, 150, 120, 58, "Follow-up (TFOP)", "imagem · espectro · VR")
    _arrow(P, 638, y + h, 638, 146)
    _box(P, 404, 128, 150, 42, "CP", "planeta confirmado", "sg-node sg-node-good")
    _box(P, 404, 184, 150, 42, "FP / FA", "falso positivo ou alarme", "sg-node sg-node-bad")
    _arrow(P, 578, 166, 558, 152)
    _arrow(P, 578, 192, 558, 204)
    for n, line in enumerate(["Sinais descartados no vetting (EB, V, IS)",
                              "não viram TOIs. Os que viram podem ser",
                              "reclassificados pelo follow-up.",
                              "Fluxo resumido de Guerrero et al. (2021)."]):
        P.append(f'<text class="sg-note" x="10" y="{150 + n * 16}">{line}</text>')
    svg = (f'<svg class="sg-chart sg-diagram" id="fig-pipeline" viewBox="0 0 {W} {H}" role="img" '
           f'aria-labelledby="fig-pipeline-t fig-pipeline-d">\n<title id="fig-pipeline-t">Do pixel ao TOI</title>\n'
           f'<desc id="fig-pipeline-d">As câmeras do TESS geram imagens; os pipelines SPOC e QLP produzem curvas de luz e '
           f'procuram eventos periódicos (TCEs); triagem automática e vetting humano promovem os melhores a TOI; o '
           f'follow-up da comunidade confirma o planeta ou o marca como falso positivo.</desc>\n'
           + "\n".join(P) + "\n</svg>\n")
    save("fig-pipeline", svg)


def fig_arquitetura():
    """Arquitetura do SAGAN (página Sobre)."""
    W, H = 720, 300
    P = [ARR2]
    _box(P, 10, 110, 130, 70, "Navegador", "gráficos + pipeline")
    _box(P, 230, 95, 170, 100, "Django (Vercel)", "função Python stateless", "sg-node sg-node-accent")
    _box(P, 500, 20, 200, 70, "ExoFOP-TESS (IPAC)", "catálogo TOI · CSV")
    _box(P, 500, 200, 200, 70, "MAST (STScI)", "curvas de luz · FITS")
    _arrow(P, 140, 135, 226, 135, "páginas", -8)
    _arrow(P, 226, 160, 144, 160, "JSON", 16)
    _arrow(P, 400, 120, 496, 60)
    P.append('<text class="sg-note" x="430" y="70" text-anchor="middle">cache 1 h</text>')
    _arrow(P, 400, 170, 496, 232)
    P.append('<text class="sg-note" x="470" y="186" text-anchor="middle">lightkurve</text>')
    P.append('<text class="sg-note" x="10" y="232">O navegador guarda a lista de</text>')
    P.append('<text class="sg-note" x="10" y="248">funções aplicadas e a reenvia</text>')
    P.append('<text class="sg-note" x="10" y="264">a cada mudança; o servidor valida</text>')
    P.append('<text class="sg-note" x="10" y="280">e recalcula a partir da curva base.</text>')
    svg = (f'<svg class="sg-chart sg-diagram" id="fig-arquitetura" viewBox="0 0 {W} {H}" role="img" '
           f'aria-labelledby="fig-arquitetura-t fig-arquitetura-d">\n<title id="fig-arquitetura-t">Arquitetura do SAGAN</title>\n'
           f'<desc id="fig-arquitetura-d">O navegador conversa com uma função Django na Vercel. A função busca o catálogo '
           f'TOI no ExoFOP (com cache de uma hora) e as curvas de luz no MAST pelo lightkurve.</desc>\n'
           + "\n".join(P) + "\n</svg>\n")
    save("fig-arquitetura", svg)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fig_model()
    t, f = fig_wasp18_series()
    p = fig_bls(t, f)
    print("BLS P =", p)
    fig_fold()
    fig_toi()
    fig_geometry()
    fig_pipeline()
    fig_arquitetura()
