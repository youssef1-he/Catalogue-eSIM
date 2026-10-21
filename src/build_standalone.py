"""
Génère docs/index.html : une page 100 % statique (aucune installation, aucun serveur).

La page du dashboard (dashboard/page.html) est écrite pour l'API `dash` de l'éditeur où elle
est publiée. Ce script l'enveloppe avec :
  - un mini-runtime `dash` (data / calc / onData / colors) qui exécute exactement les mêmes calculs,
  - les jeux de données du pipeline (catalogue.json, fichiers.json) intégrés dans la page,
  - D3 intégré (vendor/d3.min.js), donc la page fonctionne même hors ligne,
  - les variables de thème clair/sombre.

Usage : python src/build_standalone.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

THEME = """
:root {
  color-scheme: light;
  --font-anthropic-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-anthropic-serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  --color-bg: #f6f5f2; --color-panel: #ffffff; --color-fg: #1d1c1a; --color-fg-muted: #66635c;
  --color-border-line: #e4e1da; --color-bad: #b3261e;
  --cds-radius: 10px;
  --cds-pad-xs: .375rem; --cds-pad-sm: .625rem; --cds-pad-md: 1rem; --cds-pad-lg: 1.25rem; --cds-pad-xl: 1.75rem;
  --cds-gap-xs: .375rem; --cds-gap-sm: .625rem; --cds-gap-md: 1rem; --cds-gap-lg: 1.5rem; --cds-gap-xl: 2rem;
  --cds-font-size-caption: .78rem; --cds-font-size-body: .9rem; --cds-font-size-heading: 1.05rem; --cds-font-size-title: 1.4rem;
  --cds-font-weight-medium: 600;
  --cds-chart-muted: #c9c5bb; --cds-chart-grid: #ebe8e1; --cds-chart-axis: #b9b5aa; --cds-chart-reference: #7d796f;
  --cds-chart-status-critical: #c2412d;
  --cds-surface-popover: #ffffff; --cds-border: #d8d4ca; --cds-text-secondary: #66635c;
  --cds-shadow-popover: 0 6px 20px rgba(29, 28, 26, .14);
  --cds-dur-slow: 180ms;
  --dash-c0: #2f6690; --dash-c1: #d9822b; --dash-c2: #4f9d7a; --dash-c3: #8a6bb5; --dash-c4: #c25b7b; --dash-c5: #6f8f3b; --dash-c6: #b8a02e; --dash-c7: #5f6b78;
}
@media (prefers-color-scheme: dark) {
  :root { color-scheme: dark;
    --color-bg: #151412; --color-panel: #1e1d1a; --color-fg: #efede8; --color-fg-muted: #a09c92;
    --color-border-line: #33312c; --color-bad: #ef6b60;
    --cds-chart-muted: #4a473f; --cds-chart-grid: #2c2a26; --cds-chart-axis: #55524a; --cds-chart-reference: #a09c92;
    --cds-chart-status-critical: #ef7a63;
    --cds-surface-popover: #26241f; --cds-border: #3d3a34; --cds-text-secondary: #a09c92;
    --cds-shadow-popover: 0 6px 20px rgba(0, 0, 0, .5);
    --dash-c0: #6aa6d6; --dash-c1: #e8a254; --dash-c2: #74c19c; --dash-c3: #b79ae0; --dash-c4: #e387a3; --dash-c5: #a1c262; --dash-c6: #d8c457; --dash-c7: #93a0ad; }
}
html { background: var(--color-bg); }
body { margin: 0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-anthropic-sans); font-size: 14px; }
#dash-root { padding: clamp(1rem, 4vw, 3rem) max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px)); }
[hidden] { display: none !important; }
.dash-skeleton { display: inline-block; min-width: 3ch; min-height: 1em; border-radius: 4px; background: var(--cds-chart-grid); color: transparent; }
div.dash-skeleton { display: block; }
"""

RUNTIME = """
window.dash = (() => {
  const raw = {
    catalogue: JSON.parse(document.getElementById('data-catalogue').textContent),
    fichiers: JSON.parse(document.getElementById('data-fichiers').textContent),
  };
  const calcs = {}, cache = {}, callbacks = [];
  const get = (id) => {
    if (id in raw) return raw[id];
    if (id in cache) return cache[id];
    if (!(id in calcs)) return undefined;
    const c = calcs[id];
    return (cache[id] = c.fn(...c.inputs.map(get)));
  };
  return {
    colors: Array.from({ length: 8 }, (_, i) => `var(--dash-c${i})`),
    data(id) {
      try {
        const d = get(id);
        if (d === undefined) return { status: 'missing', data: [], columns: [], message: 'source inconnue', refreshing: false, meta: [] };
        return { status: 'ok', data: d, columns: d[0] ? Object.keys(d[0]) : [], message: '', refreshing: false, meta: [] };
      } catch (e) {
        console.error(id, e);
        return { status: 'error', data: [], columns: [], message: String(e), refreshing: false, meta: [] };
      }
    },
    calc(id, spec) { calcs[id] = spec; },
    onData(fn) { callbacks.push(fn); fn(); },
    params: () => ({}), setParams() {}, resetParams() {}, setLink() {}, refresh() {}, loader() {},
    _redraw() { callbacks.forEach((f) => f()); },
  };
})();
(() => {
  let t = 0, w = 0;
  const root = document.getElementById('dash-root');
  new ResizeObserver(() => {
    if (root.clientWidth === w) return;
    w = root.clientWidth; cancelAnimationFrame(t); t = requestAnimationFrame(() => dash._redraw());
  }).observe(root);
})();
"""


def main() -> None:
    page = (ROOT / "dashboard" / "page.html").read_text(encoding="utf-8")
    catalogue = (ROOT / "out" / "catalogue.json").read_text(encoding="utf-8")
    fichiers = (ROOT / "out" / "fichiers.json").read_text(encoding="utf-8")
    d3 = (ROOT / "vendor" / "d3.min.js").read_text(encoding="utf-8")
    # Les données sont dans des balises <script type="application/json"> : on neutralise "</".
    safe = lambda s: s.replace("</", "<\\/")
    html = f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Catalogue eSIM 18 fournisseurs</title>
<meta name="description" content="Dashboard des cartes eSIM importées depuis 18 fichiers fournisseurs : prix, data, répartition, comparaisons.">
<style>{THEME}</style>
</head>
<body>
<div id="dash-root">
{page.split("<script>")[0]}
</div>
<script type="application/json" id="data-catalogue">{safe(catalogue)}</script>
<script type="application/json" id="data-fichiers">{safe(fichiers)}</script>
<script>{safe(d3)}</script>
<script>{RUNTIME}</script>
<script>{page.split("<script>", 1)[1].rsplit("</script>", 1)[0]}</script>
</body>
</html>
"""
    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"{out.relative_to(ROOT)} : {len(html) / 1024:.0f} Ko")


if __name__ == "__main__":
    main()
