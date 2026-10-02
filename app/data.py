import io
import time

import pandas as pd
import requests

EXOFOP_URL = (
    "https://exofop.ipac.caltech.edu/tess/download_toi.php"
    "?sort=toi&output=csv"
)

# Mapeamento das colunas do ExoFOP para nomes usáveis em templates Django
COLUMN_MAP = {
    "TIC ID": "tic_id",
    "TOI": "toi",
    "TESS Disposition": "disposition",
    "Source": "source",
    "Period (days)": "period",
    "Stellar Radius (R_Sun)": "stellar_radius",
    "Stellar Mass (M_Sun)": "stellar_mass",
    "Date TOI Alerted (UTC)": "alerted",
    "Date TOI Updated (UTC)": "updated",
    "Date Modified": "modified",
    "Comments": "comments",
}

_cache: dict = {"df": None, "fetched_at": 0.0}
_TTL = 3600  # 1 hora


def get_toi_dataframe() -> pd.DataFrame:
    """Retorna o catálogo TOI do ExoFOP, com cache de 1 hora em memória."""
    now = time.time()
    if _cache["df"] is not None and (now - _cache["fetched_at"]) < _TTL:
        return _cache["df"]

    resp = requests.get(EXOFOP_URL, timeout=30)
    resp.raise_for_status()

    df = pd.read_csv(io.StringIO(resp.text))

    # Renomeia apenas as colunas que existem na resposta atual da API
    rename = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df = df[list(rename.keys())].rename(columns=rename).fillna("")

    _cache["df"] = df
    _cache["fetched_at"] = now
    return df


def cached_toi_count() -> int | None:
    """Total de TOIs já em cache (não dispara download)."""
    df = _cache["df"]
    return len(df) if df is not None else None
