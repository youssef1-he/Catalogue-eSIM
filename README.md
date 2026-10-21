# Dashboard catalogue eSIM

Test de recrutement MyBestSim, partie 1 : lire 18 fichiers CSV fournisseurs, en sortir les statistiques clés et les présenter dans un dashboard accessible par un simple lien.

- **Dashboard en ligne** : _à compléter avec le lien_ (la page `docs/index.html` est 100 % statique, elle s'ouvre sans rien installer).
- **Données** : 18 fichiers, 5 056 lignes, un fichier par fournisseur (`data/`).

## Résultats

| Indicateur demandé | Valeur |
|---|---|
| Cartes eSIM (produits) | **5 056** |
| Produits à plus de 100 € | **56** (1,1 %), tous des « Illimité 30 jours » |
| Prix le plus bas / le plus haut | **5,36 €** / **154,63 €** |
| Data moyenne par carte | **14,49 Go** (sur 4 403 cartes avec un volume, les 653 illimitées sont exclues) |
| Prix moyen global | **29,30 €** (médiane 20,70 €) |
| Répartition par fournisseur | Airalo 722, Ubigi 562, eSIMX 432, Saily 382, GigSky 342, Nomad 312, Instabridge 282, aloSIM 262, Holafly 242, Yesim 222, Jetpac 212, Truphone 202, JamboSIM 182, Flexiroam 172, Yatelo 162, Maya Mobile 152, Roamic 122, 4S eSIM 92 |

### Ce que le dashboard ajoute (bonus)

- **Le prix dépend de l'offre, pas du fournisseur.** Le prix moyen varie de 24,26 € (4S eSIM) à 32,10 € (Yesim), mais cet écart suit le mix de produits (corrélation de 0,95 avec la data moyenne). Avec un indice qui compare chaque carte à la médiane de la même offre (pays, volume, durée), tous les fournisseurs sont entre 99,1 et 100,5.
- **Les offres multi-pays coûtent 40 % de plus** (Europe, Asie, Amérique du Nord, Monde) à volume et durée égaux. Le pays, lui, change le prix de moins de 3 %.
- **L'illimité se paie sur la durée** : +27 % face à 50 Go sur 30 jours, −33 % sur 7 jours.
- **Prix au Go** divisé par 5,8 entre 1 Go et 50 Go. Pas de prime 5G visible.
- Distribution des prix, prix par volume et par durée, meilleures et moins bonnes offres au Go, tableau fournisseurs triable, encart qualité des données.

## Choix assumés

| Question | Choix | Pourquoi |
|---|---|---|
| Qu'est-ce qu'un « produit » ? | Une ligne de CSV = une carte, identifiée par son SKU | Aucun SKU n'apparaît deux fois. |
| 1 351 lignes partagent fournisseur + pays + volume + durée avec une autre ligne (620 offres) | **Conservées** | Elles ont un SKU, un prix et parfois un réseau ou une option de recharge différents : ce sont des lignes de catalogue distinctes. Le dashboard indique l'effet d'un dédoublonnage (4 325 cartes, prix moyen 29,16 €). |
| « Illimité » dans la moyenne de data | **Exclu**, compté à part (653 cartes) | Pas de volume en Go. Le compter à 0 donnerait 12,62 Go, ce qui n'a pas de sens. |
| Seuil « plus de 100 € » | **Strict** (> 100) | Aucun produit n'est à exactement 100 €, le résultat est identique avec ≥. |
| Prix manquants, nuls, autre devise | Écartés **et comptés** | Ici : 0 ligne écartée, tout est en EUR. Le contrôle reste actif pour les imports suivants. |
| Comparaison des fournisseurs | Indice de prix à offre comparable | Le prix moyen seul trompe : un fournisseur avec plus d'illimité ou de gros volumes paraît plus cher sans l'être. |

## Pièges rencontrés

- **Le code pays `NA` (Amérique du Nord)** est lu comme une valeur manquante par pandas. Le pipeline lit tout en texte avec `keep_default_na=False`.
- **Un bug attrapé par recoupement** : mon histogramme Python s'arrêtait à 150 € et excluait la carte à 154,63 €. Le calcul indépendant fait dans le navigateur a révélé l'écart (5 055 cartes comptées au lieu de 5 056).

## Fonctionnement

```
data/*.csv ──> src/pipeline.py ──> out/catalogue.json, out/fichiers.json, out/stats.json
                                              │
dashboard/page.html + out/*.json ──> src/build_standalone.py ──> docs/index.html
```

1. `src/pipeline.py` lit les CSV de façon tolérante (encodage utf-8 / cp1252, séparateur détecté, prix avec virgule, data en Mo ou Go, alias de colonnes), rejette et compte ce qui est invalide, puis calcule `out/stats.json` (valeurs de référence) et exporte le catalogue nettoyé.
2. `dashboard/page.html` recalcule tous les chiffres dans le navigateur à partir du catalogue nettoyé. `out/stats.json` sert de référence : plus de 230 valeurs comparées (KPI, fournisseurs, histogramme, volumes, durées, qualité) sont identiques.
3. `src/build_standalone.py` assemble une page unique `docs/index.html` (données et D3 intégrés), thème clair et sombre, utilisable sur mobile.

## Lancer

```bash
pip install -r requirements.txt
python src/pipeline.py data out/stats.json     # nettoie, calcule, exporte
python src/build_standalone.py                 # génère docs/index.html
```

Puis ouvrir `docs/index.html`. Pour le mettre en ligne : GitHub Pages (Settings, Pages, branche `main`, dossier `/docs`), ou glisser le dossier `docs` sur Netlify Drop.
