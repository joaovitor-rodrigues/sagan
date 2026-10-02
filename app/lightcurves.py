"""Download e processamento de curvas de luz do TESS (via lightkurve).

O processamento é *stateless*: o navegador envia a lista de operações
(o "pipeline") e o servidor sempre recalcula a partir da curva base.
Assim nenhuma sessão ou banco de dados é necessário, o que permite rodar
em ambiente serverless (Vercel) com várias instâncias.
"""
import math
import os
from functools import lru_cache

import numpy as np
import pandas as pd

MAX_PIPELINE_STEPS = 20

X_LABEL_DEFAULT = "Dias — Barycentric Julian Date (BJD)"
X_LABEL_PHASE = "Fase (unidades do período)"
Y_LABEL_DEFAULT = "Fluxo normalizado"

# ── Registro das operações disponíveis na interface ─────────────────────────

LC_FUNCTIONS = {
    "flatten": {
        "label": "Achatar (Flatten)",
        "desc": "Remove tendências de longo prazo usando filtro Savitzky-Golay. Útil para isolar trânsitos do brilho de fundo da estrela.",
        "params": [
            {"name": "window_length", "label": "Janela (pontos, ímpar)", "type": "number", "default": 101, "min": 3, "step": 2},
            {"name": "polyorder",     "label": "Grau polinomial",        "type": "number", "default": 2,   "min": 1, "max": 5, "step": 1},
        ],
    },
    "fold": {
        "label": "Dobrar (Fold)",
        "desc": "Dobra a curva de luz pelo período orbital, empilhando todos os trânsitos. Revela o padrão periódico com mais clareza.",
        "params": [
            {"name": "period",     "label": "Período (dias)",           "type": "number", "default": "", "min": 0.001, "step": 0.001, "placeholder": "Ex: 3.141", "required": True},
            {"name": "epoch_time", "label": "Época T₀ (BJD, opcional)", "type": "number", "default": "", "step": 0.0001, "placeholder": "Deixe vazio para auto"},
        ],
    },
    "bin": {
        "label": "Agrupar (Bin)",
        "desc": "Agrupa pontos próximos no tempo, reduzindo ruído aleatório. O tamanho do bin é em dias.",
        "params": [
            {"name": "time_bin_size", "label": "Tamanho do bin (dias)", "type": "number", "default": 0.02, "min": 0.0001, "step": 0.001},
        ],
    },
    "remove_outliers": {
        "label": "Remover Outliers",
        "desc": "Remove pontos que desviam além de N desvios-padrão da mediana. Limpa artefatos e falhas de medição.",
        "params": [
            {"name": "sigma", "label": "Sigma (desvios-padrão)", "type": "number", "default": 5.0, "min": 1.0, "max": 20.0, "step": 0.5},
        ],
    },
    "smooth": {
        "label": "Suavizar (Smooth)",
        "desc": "Aplica média móvel (box kernel) para suavizar ruído de alta frequência.",
        "params": [
            {"name": "filter_width", "label": "Largura do filtro (pontos)", "type": "number", "default": 11, "min": 1, "step": 2},
        ],
    },
    "normalize": {
        "label": "Normalizar",
        "desc": "Normaliza o fluxo dividindo pela mediana. Permite escolher a unidade resultante.",
        "params": [
            {"name": "unit", "label": "Unidade", "type": "select",
             "options": [("unscaled", "Adimensional (padrão)"), ("percent", "Porcentagem (%)"), ("ppm", "Partes por milhão (ppm)")]},
        ],
    },
    "truncate": {
        "label": "Truncar (intervalo)",
        "desc": "Recorta a curva de luz para um intervalo de tempo específico. Útil para focar em um trânsito ou setor.",
        "params": [
            {"name": "before", "label": "Início (BJD, opcional)", "type": "number", "default": "", "step": 0.01, "placeholder": "Deixe vazio para usar o início"},
            {"name": "after",  "label": "Fim (BJD, opcional)",    "type": "number", "default": "", "step": 0.01, "placeholder": "Deixe vazio para usar o fim"},
        ],
    },
}


class PipelineError(ValueError):
    """Pipeline inválido enviado pelo cliente."""


# ── Download (com cache) ────────────────────────────────────────────────────

def _download_dir():
    return os.environ.get("SAGAN_CACHE_DIR") or None


@lru_cache(maxsize=32)
def search(tic_id: int):
    import lightkurve as lk
    return lk.search_lightcurve(f"TIC {tic_id}", mission="TESS")


@lru_cache(maxsize=16)
def get_base_lightcurve(tic_id: int, ind: int):
    """Curva de luz normalizada da observação `ind` do alvo, como arrays numpy."""
    result = search(tic_id)
    if ind < 0 or ind >= len(result):
        raise IndexError("Observação inexistente para este alvo.")
    lc = result[ind].download(download_dir=_download_dir()).normalize()
    time = np.asarray(lc.time.value, dtype=float)
    flux = np.asarray(lc.flux.value, dtype=float)
    return time, flux


def best_period(time, flux) -> float:
    """Período mais provável de trânsito, via Box Least Squares (BLS).

    O BLS procura quedas periódicas em forma de "caixa", que é o formato de
    um trânsito; o Lomb-Scargle (senoidal) tende a escolher harmônicos.
    """
    lc = _make_lc(time, flux).remove_nans()
    baseline = float(lc.time.value.max() - lc.time.value.min())
    max_period = max(baseline / 2, 1.0)
    periods = np.exp(np.linspace(np.log(0.5), np.log(max_period), 5000))
    pg = lc.to_periodogram(
        method="bls",
        period=periods,
        duration=[0.04, 0.08, 0.12, 0.2],
        frequency_factor=500,
    )
    return float(pg.period_at_max_power.value)


# ── Pipeline ────────────────────────────────────────────────────────────────

def _make_lc(time, flux):
    from lightkurve import LightCurve
    return LightCurve(time=np.array(time, dtype=float), flux=np.array(flux, dtype=float))


def _to_number(value, spec):
    try:
        num = float(value)
    except (TypeError, ValueError):
        raise PipelineError(f"Valor inválido para {spec['label']}.")
    if not math.isfinite(num):
        raise PipelineError(f"Valor inválido para {spec['label']}.")
    if "min" in spec and num < spec["min"]:
        raise PipelineError(f"{spec['label']}: mínimo {spec['min']}.")
    if "max" in spec and num > spec["max"]:
        raise PipelineError(f"{spec['label']}: máximo {spec['max']}.")
    return num


def validate_pipeline(raw):
    """Valida a lista enviada pelo cliente e devolve uma versão limpa.

    Só aceita operações e parâmetros conhecidos; números são convertidos e
    checados contra os limites do registro.
    """
    if not isinstance(raw, list):
        raise PipelineError("Pipeline deve ser uma lista.")
    if len(raw) > MAX_PIPELINE_STEPS:
        raise PipelineError(f"Máximo de {MAX_PIPELINE_STEPS} operações.")

    clean = []
    for step in raw:
        if not isinstance(step, dict) or step.get("name") not in LC_FUNCTIONS:
            raise PipelineError("Função inválida.")
        name = step["name"]
        given = step.get("params") or {}
        if not isinstance(given, dict):
            raise PipelineError("Parâmetros inválidos.")

        params = {}
        for spec in LC_FUNCTIONS[name]["params"]:
            value = given.get(spec["name"])
            if value is None or str(value).strip() == "":
                if spec.get("required"):
                    raise PipelineError(f"O parâmetro {spec['label']} é obrigatório.")
                continue
            if spec["type"] == "select":
                allowed = [opt for opt, _ in spec["options"]]
                if value not in allowed:
                    raise PipelineError(f"Valor inválido para {spec['label']}.")
                params[spec["name"]] = value
            else:
                params[spec["name"]] = _to_number(value, spec)

        clean.append({"name": name, "label": LC_FUNCTIONS[name]["label"], "params": params})
    return clean


def apply_pipeline(time, flux, pipeline):
    """Aplica as operações em sequência sobre a curva base."""
    lc = _make_lc(time, flux)
    x_label, y_label = X_LABEL_DEFAULT, Y_LABEL_DEFAULT

    for step in pipeline:
        name, p = step["name"], step["params"]

        if name == "flatten":
            wl = int(p.get("window_length", 101))
            if wl % 2 == 0:
                wl += 1
            lc = lc.flatten(window_length=wl, polyorder=int(p.get("polyorder", 2)))

        elif name == "fold":
            kwargs = {"period": p["period"]}
            if "epoch_time" in p:
                kwargs["epoch_time"] = p["epoch_time"]
            lc = lc.fold(**kwargs)
            x_label = X_LABEL_PHASE

        elif name == "bin":
            lc = lc.bin(time_bin_size=p.get("time_bin_size", 0.02))

        elif name == "remove_outliers":
            lc = lc.remove_outliers(sigma=p.get("sigma", 5.0))

        elif name == "smooth":
            # LightCurve não tem .smooth(); média móvel centrada (box kernel)
            fw = max(int(p.get("filter_width", 11)), 1)
            lc = lc.copy()
            smoothed = (
                pd.Series(lc.flux.value)
                .rolling(fw, center=True, min_periods=1)
                .mean()
                .to_numpy()
            )
            lc.flux = smoothed * lc.flux.unit

        elif name == "normalize":
            unit = p.get("unit", "unscaled")
            lc = lc.normalize(unit=unit)
            y_label = {
                "percent": "Fluxo relativo (%)",
                "ppm": "Fluxo relativo (ppm)",
            }.get(unit, Y_LABEL_DEFAULT)

        elif name == "truncate":
            kw = {k: p[k] for k in ("before", "after") if k in p}
            if kw:
                lc = lc.truncate(**kw)

    return lc.time.value, lc.flux.value, x_label, y_label


def to_json_list(values):
    """Floats prontos para JSON: NaN/inf viram None e o tamanho do payload é
    reduzido para 9 algarismos significativos (bem abaixo do ruído do TESS)."""
    out = []
    for v in np.asarray(values, dtype=float).tolist():
        out.append(float(f"{v:.9g}") if math.isfinite(v) else None)
    return out
