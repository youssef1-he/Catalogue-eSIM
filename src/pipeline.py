"""
Pipeline MyBestSim : lecture des CSV fournisseurs -> normalisation -> KPI.

Usage :
    python src/pipeline.py data/ out/stats.json

Le script est volontairement tolérant : un nouveau fournisseur peut arriver avec
un autre séparateur, un autre encodage, des noms de colonnes différents, un prix
avec virgule ou une data en Mo, sans qu'il faille modifier le code.
Tout ce qui est écarté ou ambigu est compté et remonté dans `quality`.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# 1. Lecture et normalisation
# --------------------------------------------------------------------------- #

# Alias de colonnes acceptés -> nom canonique.
COLUMN_ALIASES = {
    "sku": ["sku", "id", "product_id", "reference", "ref"],
    "provider": ["provider", "fournisseur", "supplier", "vendor"],
    "product_name": ["product_name", "name", "nom", "produit", "title"],
    "country_code": ["country_code", "iso", "pays_code", "country_iso"],
    "country_name": ["country_name", "country", "pays", "zone"],
    "data_gb": ["data_gb", "data_go", "data"],
    "data_display": ["data_display", "data_label", "data_text"],
    "validity_days": ["validity_days", "validity", "duree", "durée", "days"],
    "price": ["price", "prix", "price_eur", "amount"],
    "currency": ["currency", "devise", "cur"],
    "network": ["network", "reseau", "réseau"],
    "top_up": ["top_up", "topup", "recharge"],
}
REQUIRED = ["price"]
UNLIMITED_RE = re.compile(r"illimit|unlimit", re.I)


def read_csv_tolerant(path: Path) -> pd.DataFrame:
    """Essaie plusieurs encodages ; le séparateur est détecté automatiquement."""
    last_err = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(
                path, sep=None, engine="python", dtype=str,
                keep_default_na=False, encoding=enc,
            )
        except (UnicodeDecodeError, pd.errors.ParserError) as err:
            last_err = err
    raise RuntimeError(f"Impossible de lire {path.name}: {last_err}")


def canonicalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    lookup = {a.lower(): canon for canon, aliases in COLUMN_ALIASES.items() for a in aliases}
    renamed = {}
    for col in df.columns:
        key = col.strip().lower()
        if key in lookup and lookup[key] not in renamed.values():
            renamed[col] = lookup[key]
    return df.rename(columns=renamed)


def parse_price(s: pd.Series) -> pd.Series:
    cleaned = (
        s.astype(str)
        .str.replace(r"[€\s]|EUR", "", regex=True)
        .str.replace(",", ".", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def parse_data(row_gb: pd.Series, row_display: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Retourne (data en Go, est_illimité). Priorité à data_gb, repli sur le libellé."""
    display = row_display.astype(str)
    unlimited = display.str.contains(UNLIMITED_RE)
    gb = pd.to_numeric(row_gb.astype(str).str.replace(",", ".", regex=False), errors="coerce")

    # Repli : "500 Mo", "5 Go", "2.5GB"
    m = display.str.extract(r"(?P<n>\d+(?:[.,]\d+)?)\s*(?P<u>[A-Za-z]+)")
    n = pd.to_numeric(m["n"].str.replace(",", ".", regex=False), errors="coerce")
    factor = m["u"].str.lower().map({"go": 1, "gb": 1, "mo": 1 / 1024, "mb": 1 / 1024})
    fallback = n * factor
    gb = gb.fillna(fallback)
    gb = gb.where(~unlimited)  # un illimité n'a pas de volume en Go
    return gb, unlimited


def load_catalog(data_dir: Path) -> tuple[pd.DataFrame, dict]:
    files = sorted(data_dir.glob("*.csv"))
    if not files:
        raise SystemExit(f"Aucun CSV dans {data_dir}")

    frames, per_file = [], []
    for f in files:
        raw = canonicalize_columns(read_csv_tolerant(f))
        missing = [c for c in REQUIRED if c not in raw.columns]
        if missing:
            raise SystemExit(f"{f.name}: colonnes obligatoires absentes {missing}")
        raw["source_file"] = f.name
        if "provider" not in raw.columns:  # repli : nom du fichier
            raw["provider"] = f.stem
        per_file.append({"file": f.name, "rows": len(raw)})
        frames.append(raw)

    df = pd.concat(frames, ignore_index=True)
    for c in COLUMN_ALIASES:
        if c not in df.columns:
            df[c] = ""
    for c in COLUMN_ALIASES:
        df[c] = df[c].astype(str).str.strip()

    n_raw = len(df)
    df["price"] = parse_price(df["price"])
    df["data_gb"], df["unlimited"] = parse_data(df["data_gb"], df["data_display"])
    df["validity_days"] = pd.to_numeric(df["validity_days"], errors="coerce")
    df["currency"] = df["currency"].str.upper().replace("", "EUR")

    # --- règles de rejet (comptées, jamais silencieuses) ---------------------
    bad_price = df["price"].isna() | (df["price"] <= 0)
    non_eur = df["currency"] != "EUR"  # pas de taux de change : on écarte et on le dit
    no_volume = ~df["unlimited"] & df["data_gb"].isna()
    dup_sku = df["sku"].ne("") & df.duplicated("sku", keep="first")

    rejected = bad_price | non_eur | dup_sku
    quality = {
        "files": len(files),
        "rows_read": int(n_raw),
        "rejected_bad_price": int(bad_price.sum()),
        "rejected_non_eur": int((non_eur & ~bad_price).sum()),
        "rejected_duplicate_sku": int((dup_sku & ~bad_price & ~non_eur).sum()),
        "data_unreadable": int(no_volume[~rejected].sum()),
        "rows_kept": int((~rejected).sum()),
        "per_file": per_file,
    }
    df = df[~rejected].copy()

    # --- "quasi-doublons" : même offre affichée, SKU/prix différents ---------
    # On ne les supprime PAS : SKU distincts = lignes de catalogue distinctes
    # (prix, réseau ou recharge différents). On mesure l'effet pour être transparent.
    key = ["provider", "country_code", "data_display", "validity_days"]
    grp = df.groupby(key, dropna=False)["price"]
    size = grp.transform("size")
    quality["same_offer_rows"] = int((size > 1).sum())
    quality["same_offer_groups"] = int(df[size > 1].groupby(key, dropna=False).ngroups)
    quality["rows_if_deduped_by_offer"] = int(df.groupby(key, dropna=False).ngroups)
    cheapest = df.loc[df.groupby(key, dropna=False)["price"].idxmin()]
    quality["avg_price_if_deduped_cheapest"] = round(float(cheapest["price"].mean()), 2)
    return df.reset_index(drop=True), quality


# --------------------------------------------------------------------------- #
# 2. Statistiques
# --------------------------------------------------------------------------- #

REGION_CODES = {"EU", "AS", "NA", "WW"}  # offres multi-pays dans le catalogue


def r2(x) -> float:
    return round(float(x), 2)


def compute_stats(df: pd.DataFrame, quality: dict) -> dict:
    limited = df[~df["unlimited"]]
    stats: dict = {"quality": quality}

    # ---- les 6 KPI demandés -------------------------------------------------
    pmin, pmax = df.loc[df["price"].idxmin()], df.loc[df["price"].idxmax()]
    stats["kpi"] = {
        "total_products": int(len(df)),
        "over_100": int((df["price"] > 100).sum()),  # strict : > 100 €
        "price_min": r2(pmin["price"]),
        "price_min_label": f'{pmin["provider"]} · {pmin["product_name"]}',
        "price_max": r2(pmax["price"]),
        "price_max_label": f'{pmax["provider"]} · {pmax["product_name"]}',
        "avg_data_gb": r2(limited["data_gb"].mean()),
        "avg_data_n": int(len(limited)),
        "unlimited_count": int(df["unlimited"].sum()),
        "avg_price": r2(df["price"].mean()),
        "median_price": r2(df["price"].median()),
        "providers_count": int(df["provider"].nunique()),
    }

    # ---- répartition par fournisseur ---------------------------------------
    g = df.groupby("provider")
    prov = pd.DataFrame({
        "count": g.size(),
        "avg_price": g["price"].mean(),
        "median_price": g["price"].median(),
        "over_100": g["price"].apply(lambda s: (s > 100).sum()),
        "unlimited_share": g["unlimited"].mean(),
    })
    lim = limited.groupby("provider")
    prov["avg_data_gb"] = lim["data_gb"].mean()
    # prix par Go sur les offres limitées uniquement (l'illimité n'a pas de Go)
    prov["price_per_gb"] = lim["price"].sum() / lim["data_gb"].sum()

    # Indice de prix à offre comparable : prix / médiane du segment
    # (même pays, même volume, même durée), moyenné par fournisseur.
    seg = ["country_code", "data_display", "validity_days"]
    seg_n_prov = df.groupby(seg)["provider"].transform("nunique")
    seg_med = df.groupby(seg)["price"].transform("median")
    comparable = seg_n_prov >= 3  # au moins 3 fournisseurs sur le segment
    ratio = (df["price"] / seg_med).where(comparable)
    df = df.assign(price_ratio=ratio, comparable=comparable)
    prov["price_index"] = df.groupby("provider")["price_ratio"].mean() * 100
    stats["index_basis"] = {
        "comparable_rows": int(comparable.sum()),
        "segments": int(df[comparable].groupby(seg).ngroups),
    }

    prov = prov.sort_values("count", ascending=False)
    stats["providers"] = [
        {
            "name": name,
            "count": int(r["count"]),
            "share": round(r["count"] / len(df) * 100, 1),
            "avg_price": r2(r["avg_price"]),
            "median_price": r2(r["median_price"]),
            "over_100": int(r["over_100"]),
            "unlimited_share": round(float(r["unlimited_share"]) * 100, 1),
            "avg_data_gb": r2(r["avg_data_gb"]),
            "price_per_gb": r2(r["price_per_gb"]),
            "price_index": round(float(r["price_index"]), 1),
        }
        for name, r in prov.iterrows()
    ]

    # ---- distribution des prix ---------------------------------------------
    top = int(np.floor(df["price"].max() / 10) * 10) + 10  # dernière tranche incluse
    bins = list(range(0, top + 10, 10))
    cut = pd.cut(df["price"], bins=bins, right=False)
    hist = cut.value_counts(sort=False)
    stats["price_hist"] = [
        {"from": int(i.left), "to": int(i.right), "count": int(c)} for i, c in hist.items()
    ]

    # ---- par volume de data, par durée ------------------------------------
    order = [1, 3, 5, 10, 20, 50]
    by_data = []
    for gb in order:
        s = limited[limited["data_gb"] == gb]["price"]
        by_data.append({
            "label": f"{gb} Go", "count": int(len(s)),
            "avg_price": r2(s.mean()), "median_price": r2(s.median()),
            "price_per_gb": r2(s.mean() / gb),
        })
    u = df[df["unlimited"]]["price"]
    by_data.append({
        "label": "Illimité", "count": int(len(u)),
        "avg_price": r2(u.mean()), "median_price": r2(u.median()), "price_per_gb": None,
    })
    stats["by_data"] = by_data

    by_val = []
    for d in sorted(df["validity_days"].dropna().unique()):
        sub = df[df["validity_days"] == d]
        sub_l = sub[~sub["unlimited"]]
        by_val.append({
            "label": f"{int(d)} jours", "count": int(len(sub)),
            "avg_price": r2(sub["price"].mean()),
            "median_price": r2(sub["price"].median()),
            "price_per_gb": r2(sub_l["price"].sum() / sub_l["data_gb"].sum()),
        })
    stats["by_validity"] = by_val

    # ---- réseau, recharge, zones -----------------------------------------
    net = df.groupby("network")["price_ratio"].mean() * 100
    stats["network"] = [
        {"label": k, "count": int((df["network"] == k).sum()),
         "share": round((df["network"] == k).mean() * 100, 1),
         "price_index": round(float(net[k]), 1)}
        for k in sorted(df["network"].unique())
    ]
    topup_yes = df["top_up"].str.lower().isin(["oui", "yes", "true", "1"])
    stats["topup"] = {"yes": int(topup_yes.sum()), "share": round(float(topup_yes.mean()) * 100, 1)}

    region = df["country_code"].isin(REGION_CODES)
    stats["scope"] = {
        "regional_products": int(region.sum()),
        "regional_share": round(float(region.mean()) * 100, 1),
        "single_country_products": int((~region).sum()),
        "countries": int(df.loc[~region, "country_code"].nunique()),
        "avg_price_regional": r2(df.loc[region, "price"].mean()),
        "avg_price_single": r2(df.loc[~region, "price"].mean()),
    }
    cc = (
        df.groupby(["country_code", "country_name"]).agg(
            count=("price", "size"), avg_price=("price", "mean"),
            providers=("provider", "nunique"),
        ).reset_index().sort_values("count", ascending=False)
    )
    stats["top_destinations"] = [
        {"code": r.country_code, "name": r.country_name, "count": int(r["count"]),
         "avg_price": r2(r.avg_price), "providers": int(r.providers),
         "regional": r.country_code in REGION_CODES}
        for _, r in cc.head(12).iterrows()
    ]

    # ---- meilleures offres (€/Go sur offres limitées) ----------------------
    lim_df = df[~df["unlimited"]].copy()
    lim_df["eur_per_gb"] = lim_df["price"] / lim_df["data_gb"]
    best = lim_df.nsmallest(10, "eur_per_gb")
    stats["best_value"] = [
        {"provider": r.provider, "name": r.product_name, "price": r2(r.price),
         "eur_per_gb": round(float(r.eur_per_gb), 3)}
        for r in best.itertuples()
    ]
    worst = lim_df.nlargest(5, "eur_per_gb")
    stats["worst_value"] = [
        {"provider": r.provider, "name": r.product_name, "price": r2(r.price),
         "eur_per_gb": round(float(r.eur_per_gb), 3)}
        for r in worst.itertuples()
    ]
    top_over = df[df["price"] > 100]
    stats["over_100_detail"] = {
        "all_unlimited_30d": bool(top_over["unlimited"].all() and (top_over["validity_days"] == 30).all()),
        "by_provider": top_over.groupby("provider").size().sort_values(ascending=False).to_dict(),
    }

    # ---- prime des offres multi-pays, à volume et durée égaux ---------------
    tier = df["unlimited"].map({True: "U", False: ""}) + df["data_gb"].fillna(0).astype(int).astype(str)
    tier = tier.where(~df["unlimited"], "U")
    seg2_med = df.groupby([tier, "validity_days"])["price"].transform("median")
    r2_ = df["price"] / seg2_med
    stats["scope"]["premium_regional_controlled_pct"] = round(
        (r2_[region].mean() / r2_[~region].mean() - 1) * 100, 1)
    stats["scope"]["premium_regional_raw_pct"] = round(
        (df.loc[region, "price"].mean() / df.loc[~region, "price"].mean() - 1) * 100, 1)

    # ---- illimité vs 50 Go selon la durée ----------------------------------
    cmp_rows = []
    for d in sorted(df["validity_days"].unique()):
        sub = df[df["validity_days"] == d]
        cmp_rows.append({
            "days": int(d),
            "unlimited": r2(sub[sub["unlimited"]]["price"].mean()),
            "gb50": r2(sub[sub["data_gb"] == 50]["price"].mean()),
        })
    stats["unlimited_vs_50gb"] = cmp_rows

    # ---- corrélation prix moyen / data moyenne par fournisseur --------------
    stats["provider_price_vs_data_corr"] = round(float(prov["avg_price"].corr(prov["avg_data_gb"])), 3)
    idx = prov["price_index"]
    stats["price_index_range"] = [round(float(idx.min()), 1), round(float(idx.max()), 1)]
    stats["price_index_max_dev_pct"] = round(float((idx - 100).abs().max()), 1)
    return stats


def export_datasets(df: pd.DataFrame, quality: dict, out_dir: Path) -> None:
    """Jeux de données consommés par le dashboard (JSON typé, une ligne par carte)."""
    rows = [
        {
            "sku": r.sku, "provider": r.provider, "product": r.product_name,
            "country_code": r.country_code, "country": r.country_name,
            "data_gb": None if r.unlimited else float(r.data_gb),
            "unlimited": bool(r.unlimited), "days": int(r.validity_days),
            "price": float(r.price), "network": str(r.network),
            "top_up": str(r.top_up).lower() in ("oui", "yes", "true", "1"),
        }
        for r in df.itertuples()
    ]
    (out_dir / "catalogue.json").write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kept = df.groupby("source_file").size()
    files = [
        {"file": f["file"], "provider": df.loc[df["source_file"] == f["file"], "provider"].iloc[0],
         "rows_read": f["rows"], "rows_kept": int(kept.get(f["file"], 0)),
         "rows_rejected": f["rows"] - int(kept.get(f["file"], 0))}
        for f in quality["per_file"]
    ]
    (out_dir / "fichiers.json").write_text(
        json.dumps(files, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    data_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "data")
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "out/stats.json")
    df, quality = load_catalog(data_dir)
    stats = compute_stats(df, quality)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(stats, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    df.to_csv(out.with_name("catalogue_nettoye.csv"), index=False)
    export_datasets(df, quality, out.parent)
    k = stats["kpi"]
    print(f'{k["total_products"]} produits | >100€ : {k["over_100"]} | '
          f'prix {k["price_min"]}–{k["price_max"]} € | moy. data {k["avg_data_gb"]} Go | '
          f'prix moyen {k["avg_price"]} €')


if __name__ == "__main__":
    main()
