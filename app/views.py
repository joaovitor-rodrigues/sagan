import json
from urllib.parse import urlencode

import pandas as pd
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from . import lightcurves as lcs
from .data import cached_toi_count, get_toi_dataframe

PAGE_SIZE = 50

ORDERABLE_COLS = {
    "tic_id", "toi", "disposition", "source",
    "period", "stellar_radius", "stellar_mass",
    "alerted", "updated", "modified",
}
NUMERIC_COLS = {"tic_id", "toi", "period", "stellar_radius", "stellar_mass"}

# Mantido para compatibilidade com os templates e testes
LC_FUNCTIONS = lcs.LC_FUNCTIONS


# ── Páginas estáticas ──────────────────────────────────────────────────────────

def index(request):
    count = cached_toi_count()
    toi_count = f"{count:,}".replace(",", ".") if count else None
    return render(request, "app/home.html", {"toi_count": toi_count})


def about(request):
    return render(request, "app/about.html")


def tutorial(request):
    return render(request, "app/tutorial.html")


def theory(request):
    return render(request, "app/theory.html")


# ── Catálogo TOI ───────────────────────────────────────────────────────────────

def objectList(request):
    try:
        df = get_toi_dataframe()
    except Exception as e:
        return HttpResponse(f"Erro ao carregar catálogo TOI: {e}", status=502)

    all_df = df
    q           = request.GET.get("q", "").strip()
    disposition = request.GET.get("disposition", "").strip()
    source      = request.GET.get("source", "").strip()
    order_by    = request.GET.get("order_by", "").strip()
    order_dir   = request.GET.get("order_dir", "asc").strip()

    if q:
        mask = (
            df["tic_id"].astype(str).str.contains(q, case=False, na=False, regex=False)
            | df["toi"].astype(str).str.contains(q, case=False, na=False, regex=False)
            | df["comments"].astype(str).str.contains(q, case=False, na=False, regex=False)
            | df["source"].astype(str).str.contains(q, case=False, na=False, regex=False)
        )
        df = df[mask]

    if disposition:
        df = df[df["disposition"] == disposition]

    if source:
        df = df[df["source"].astype(str).str.contains(source, case=False, na=False, regex=False)]

    if order_by in ORDERABLE_COLS:
        ascending = order_dir != "desc"
        if order_by in NUMERIC_COLS:
            sort_series = pd.to_numeric(df[order_by], errors="coerce")
            df = df.iloc[sort_series.argsort(kind="stable")]
            if not ascending:
                df = df.iloc[::-1]
        else:
            df = df.sort_values(order_by, ascending=ascending, kind="stable")

    dispositions = sorted(all_df["disposition"].dropna().unique().tolist())
    sources      = sorted(all_df["source"].dropna().unique().tolist())

    filter_params = {k: v for k, v in [
        ("q", q), ("disposition", disposition), ("source", source),
    ] if v}
    filter_qs = urlencode(filter_params)

    paginator = Paginator(df.to_dict("records"), PAGE_SIZE)
    page_obj  = paginator.get_page(request.GET.get("page", 1))

    return render(request, "app/objectlist.html", {
        "page_obj": page_obj, "q": q,
        "disposition": disposition, "source": source,
        "order_by": order_by, "order_dir": order_dir,
        "total_count": paginator.count,
        "filter_qs": filter_qs,
        "dispositions": dispositions, "sources": sources,
    })


def modal(request):
    tic_id = request.POST.get("id", "").strip()
    if not tic_id.isdigit():
        return HttpResponseBadRequest("TIC ID inválido")
    try:
        df = lcs.search(int(tic_id)).table.to_pandas()
        records = (
            df[["mission", "year", "author"]]
            .copy()
            .assign(tic_id=int(tic_id))
            .to_dict("records")
        )
        return render(request, "app/modal.html", {"d": records})
    except Exception as e:
        return HttpResponse(f"Erro ao buscar observações: {e}", status=502)


# ── Curvas de luz ──────────────────────────────────────────────────────────────

def _render_object(request, ticID, ind, pipeline):
    time, flux = lcs.get_base_lightcurve(ticID, ind)
    x, y, x_label, y_label = lcs.apply_pipeline(time, flux, pipeline)
    return render(request, "app/object.html", {
        "id": ticID, "index": ind,
        "base_x": lcs.to_json_list(time), "base_y": lcs.to_json_list(flux),
        "x": lcs.to_json_list(x), "y": lcs.to_json_list(y),
        "x_label": x_label, "y_label": y_label,
        "pipeline_json": json.dumps(pipeline).replace("<", "\\u003c"),
        "lc_functions": LC_FUNCTIONS,
    })


def tessObject(request, ticID, ind):
    try:
        return _render_object(request, ticID, ind, [])
    except IndexError as e:
        return HttpResponse(str(e), status=404)
    except Exception as e:
        return HttpResponse(f"Erro ao carregar curva de luz: {e}", status=502)


def foldLightCurve(request, ticID, ind):
    """Mesma página, já com uma etapa "fold" no período do periodograma."""
    try:
        time, flux = lcs.get_base_lightcurve(ticID, ind)
        period = round(lcs.best_period(time, flux), 6)
        pipeline = lcs.validate_pipeline([{"name": "fold", "params": {"period": period}}])
        return _render_object(request, ticID, ind, pipeline)
    except IndexError as e:
        return HttpResponse(str(e), status=404)
    except Exception as e:
        return HttpResponse(f"Erro ao calcular periodograma: {e}", status=502)


@require_POST
def process_lightcurve(request, ticID, ind):
    """Recalcula a curva a partir da base aplicando o pipeline enviado (JSON)."""
    try:
        raw = json.loads(request.POST.get("pipeline", "[]"))
        pipeline = lcs.validate_pipeline(raw)
    except (json.JSONDecodeError, lcs.PipelineError) as e:
        msg = str(e) if isinstance(e, lcs.PipelineError) else "Pipeline inválido."
        return JsonResponse({"error": msg}, status=400)

    try:
        time, flux = lcs.get_base_lightcurve(ticID, ind)
    except IndexError as e:
        return JsonResponse({"error": str(e)}, status=404)
    except Exception as e:
        return JsonResponse({"error": f"Erro ao carregar curva de luz: {e}"}, status=502)

    try:
        x, y, x_label, y_label = lcs.apply_pipeline(time, flux, pipeline)
    except Exception as e:
        return JsonResponse({"error": f"Erro ao aplicar função: {e}"}, status=400)

    return JsonResponse({
        "x": lcs.to_json_list(x), "y": lcs.to_json_list(y),
        "x_label": x_label, "y_label": y_label,
        "functions": pipeline,
    })
