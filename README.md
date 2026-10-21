# Dashboard catalogue eSIM

Projet réalisé dans le cadre du test de recrutement MyBestSim.

L'objectif était de récupérer les données de 18 fournisseurs eSIM au format CSV, de les nettoyer, d'en tirer les principales statistiques et de les présenter dans un dashboard accessible directement depuis un navigateur.

**Dashboard :** (https://catalogue-e-sim.vercel.app/)

Le dashboard est entièrement statique : il n'y a rien à installer pour le consulter.

## Quelques chiffres

| Indicateur | Résultat |
|---|---:|
| Nombre de produits | **5 056** |
| Produits à plus de 100 € | **56** |
| Prix minimum | **5,36 €** |
| Prix maximum | **154,63 €** |
| Data moyenne | **14,49 Go** |
| Prix moyen | **29,30 €** |
| Prix médian | **20,70 €** |

La moyenne de data est calculée sur les 4 403 produits ayant un volume indiqué. Les offres illimitées sont donc exclues de ce calcul.

### Produits par fournisseur

- Airalo : 722
- Ubigi : 562
- eSIMX : 432
- Saily : 382
- GigSky : 342
- Nomad : 312
- Instabridge : 282
- aloSIM : 262
- Holafly : 242
- Yesim : 222
- Jetpac : 212
- Truphone : 202
- JamboSIM : 182
- Flexiroam : 172
- Yatelo : 162
- Maya Mobile : 152
- Roamic : 122
- 4S eSIM : 92

## Ce que j'ai ajouté au dashboard

En plus des statistiques demandées, j'ai ajouté quelques comparaisons pour essayer de mieux comprendre les données :

- comparaison des prix entre fournisseurs ;
- distribution des prix ;
- prix en fonction du volume de data ;
- prix en fonction de la durée ;
- prix au Go ;
- comparaison des offres illimitées ;
- classement des meilleures offres au Go ;
- tableau des fournisseurs avec tri ;
- quelques indicateurs sur la qualité des données.

Quelques observations ressortent notamment :

- le prix moyen varie selon les fournisseurs, mais cela dépend beaucoup du type d'offres présentes dans leur catalogue ;
- les offres multi-pays sont globalement plus chères que les offres pour un seul pays ;
- les offres illimitées sont surtout plus chères lorsque la durée augmente ;
- le prix par Go diminue fortement lorsque le volume de data augmente ;
- je n'ai pas trouvé de différence suffisamment claire pour conclure à une vraie différence de prix liée à la 5G.

## Comment j'ai traité les données

J'ai considéré qu'une ligne du CSV correspondait à un produit, avec son SKU comme identifiant.

Certaines lignes ont des caractéristiques très proches (même fournisseur, pays, volume et durée), mais je les ai gardées lorsqu'elles avaient un SKU différent. Elles peuvent notamment avoir un réseau ou une option différente.

Pour les offres illimitées, je ne les ai pas comptées comme `0 Go` dans la moyenne. Elles sont comptées séparément car elles n'ont pas réellement de volume de data comparable aux autres offres.

Pour le calcul des produits à plus de 100 €, j'ai utilisé le seuil strict `> 100 €`.

Les prix manquants ou invalides sont également contrôlés par le pipeline. Dans les données fournies
