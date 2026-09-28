# Audit de préparation à la démonstration — 28 septembre 2026

Branche vérifiée : `feat/progressive-review`. Données synthétiques uniquement. La démo locale hors ligne est **prête pour le parcours principal** ; les limites ci-dessous empêchent de présenter le prototype comme un système documentaire ou fiscal exhaustif.

## État réel des phases 0–21

| Phases | État | Preuve et limite principale |
|---|---|---|
| 0 | TERMINÉ pour la démo locale | Suites complètes et parcours navigateur relancés ; périmètre et incident de base de test documentés ici. |
| 1 | TERMINÉ | Cause versionnée ; 40 → 30 → 20 → 10 → 0, retour, rejet, contradiction et résolution partielle couverts par les tests. Une pièce non liée n'abaisse pas une autre cause. |
| 2–3 | TERMINÉ | Cinq indicateurs distincts, avec facteurs, échantillon et données insuffisantes ; confiance opérationnelle sur quatre dimensions. |
| 4–5 | TERMINÉ sur données couvertes | Baseline propre à l'entreprise et rapprochement explicite ; absence de contrepartie ≠ anomalie. Les périodes et méthodes de paiement inconnues restent inconnues. |
| 6 | PARTIEL | Pipeline de dix étapes pour PDF à texte natif. Pas d'OCR de scans, de registre externe ni d'analyse visuelle fiable des altérations. Ces vérifications restent `UNKNOWN` et demandent une revue humaine. |
| 7–18 | TERMINÉ pour le prototype | Confiance documentaire, questionnaire contrôlé, actions, parcours agent/entreprise, timeline, notifications internes, simulation, historique, réseau sourcé et graphe 3D. Les notifications ne sont ni email ni SMS. |
| 19 | PARTIEL | Trois motifs descriptifs sourcés : concentration fournisseur, montant répété et échanges réciproques. Pas de couverture suffisante pour conclure à de nouveaux liens anormaux, croissance de relation, centralité robuste ou motifs temporels ; aucun signal n'agit sur l'indice documentaire. |
| 20 | PARTIEL | Assistant d'investigation déterministe, cité et limité au dossier autorisé. Pas d'index sémantique complet des documents ni de recherche dans les scans sans OCR. |
| 21 | TERMINÉ pour les nouvelles révisions | Acteur, date, raison, anciennes/nouvelles valeurs, pièces, règle et moteur. Les événements anciens incomplets ne sont pas reconstruits artificiellement ; SQLite n'est pas un journal légal infalsifiable. |

Les spécifications détaillées, preuves de développement et anciens résultats restent dans `ROADMAP_AUDIT_2026-09-27.md`. Cette page est l'état vérifié pour la démo d'aujourd'hui et remplace sa mention ancienne d'un report de la phase 19.

## Vérifications exécutées sur ce code

- `python -m pytest tests -o addopts= -q --tb=short` : **624/624 passés**.
- `npm --prefix frontend test -- --reporter=dot` : **34/34 passés**.
- `npm --prefix frontend run build` : **réussi** ; vérification TypeScript incluse.
- `npm --prefix frontend run format:check` : **réussi** après correction du seul écart Prettier existant.
- `npm --prefix frontend run test:e2e -- --reporter=list` : **14/14 passés** sur un nouveau serveur et une base SQLite synthétique isolée, fournisseurs externes désactivés. Les scénarios couvrent le parcours entreprise/agent, l'historique, l'assistant, le réseau, l'administration démo et le conflit de version.
- Signaux réseau : **61/61 tests backend ciblés**, dont quatre nouveaux tests de source, seuil, double perspective et conflit de montants.
- Quatre défauts du navigateur corrigés et publiés : pertinence de la preuve, rattachement tardif, motif humain, adaptation 320/390/768 px. Détails et reproductions dans `BROWSER_AUDIT_2026-09-28.md`. Un contrôle navigateur complémentaire a confirmé **30 → 30 → 20** pour une pièce d'affectation déposée puis liée après la réponse.

Un premier rerun navigateur a obtenu **9/11** car son lanceur utilisait à tort `BOUSSLA_CASE_DB_PATH` au lieu de `CASE_DB_PATH` (et des noms analogues pour les autres chemins). Le serveur a alors repris `runtime/` : les deux scénarios dépendant d'un dossier initial à 40 ont commencé sur un état déjà modifié. Ce n'était pas une régression du code applicatif. Le passage suivant avec les vrais noms de variables et une base vierge a obtenu **11/11**. Le dossier synthétique `runtime/` par défaut a été touché par ce passage fautif ; son état antérieur n'a pas de sauvegarde créée par cet audit. Il a été conservé, sans suppression ni réinitialisation. Utiliser le lanceur isolé ci-dessous pour la démo.

Ces tests ne valident pas les fournisseurs en mode LIVE, une authentification de production, une vraie donnée fiscale, l'OCR, un registre externe, ni une livraison email/SMS.

## Démarrer la démo d'aujourd'hui

Depuis la racine du dépôt, dans PowerShell :

```powershell
npm --prefix frontend run build
powershell -ExecutionPolicy Bypass -File scripts/start_demo_today.ps1
```

Ouvrir `http://127.0.0.1:8060`. Le lanceur conserve les données dans `runtime/manual-demo-2026-09-28/`, séparées du `runtime/` par défaut et des tests automatisés. Il désactive les fournisseurs externes ; les décisions et calculs restent déterministes. `Ctrl+C` arrête le serveur sans effacer le dossier. Pour un nouveau jeu de démonstration, passer un **nouveau** `-DataDir` absolu et éventuellement `-Port` ; ne pas supprimer le dossier existant pour « remettre à zéro » une session utile. Le rôle *Opérateur démo* permet de réinitialiser volontairement les données synthétiques de ce seul jeu.

Les boutons *Entreprise*, *Agent* et *Opérateur démo* simulent des rôles locaux. Le bandeau de données synthétiques doit rester visible dans la présentation.

## Test manuel conseillé, dans l'ordre

1. **Agent → Dashboard puis Dossiers** : ouvrir `CASE-BRICKS-001`. Vérifier l'indice de revue initial **40**, les cinq indicateurs séparés, la cause `+40`, ses sources, l'urgence indépendante, les actions et l'impact hypothétique `40 → 0` sans changement effectif.
2. **Agent → Réseau / Historique / Notifications** : voir les relations sourcées, tourner/zoomer/filtrer le graphe, ouvrir un nœud et une relation ; vérifier que les signaux réseau sont descriptifs et peuvent être absents si l'échantillon est mince. Dans Historique, distinguer périodes couvertes et données inconnues. Dans Notifications, marquer un événement enregistré comme lu ; les signaux courants ne sont pas des messages livrés.
3. **Entreprise → Messages** : déclarer le contexte du dossier vitrine (matériaux pour P1 et P2). Dans *Actions requises*, ouvrir la demande automatique. Pour observer le palier 30, répondre par une explication pertinente sans pièce sur un **jeu isolé réservé à cet essai** : l'agent doit voir **40 → 30 provisoire**. Une réponse vide ou hors cause doit laisser **40**.
4. **Sur un deuxième jeu isolé neuf, pour le parcours principal**, déclarer le même contexte, ouvrir la demande dans *Actions requises*, joindre la pièce synthétique `docs/build_lock/fixtures/documents/06_second_project_allocation.pdf` à la demande, proposer `P1=1000`, `P2=1000`, puis transmettre. L'agent doit voir **20 provisoire** quand réponse et pièce sont réellement liées. Un dépôt isolé, sans ce lien, ne doit pas réduire une autre cause.
5. **Entreprise → Documents** : confirmer les champs sourcés de cette pièce. L'agent doit voir **10 provisoire**, avec « validation agent requise ». Inspecter classification, vérifications et confiance documentaire ; aucune « authenticité prouvée » n'est annoncée.
6. **Agent → Dossiers** : examiner la proposition, saisir un motif précis d’au moins 10 caractères, puis accepter dans ce dossier. L'indice passe à **0** pour cette cause ; l'historique et l'audit gardent le 10 précédent, l'acteur, la pièce, la raison et les versions. Vérifier qu'une cause indépendante ou une autre transaction ne disparaît pas par cet acte.
7. **Sur un autre jeu isolé** : au stade 20, rejeter la proposition avec un motif précis ; attendre **20 → 40** et une notification entreprise neutre. Tester une confirmation documentaire contradictoire : la cause remonte au lieu d'être automatiquement résolue. Les retours intermédiaires **10 → 20/30/40** et la résolution partielle multi-cause sont couverts par les tests backend ; leur manipulation visuelle dépend des pièces et champs préparés pour le scénario.
8. **Assistant et rôles** : demander « Pourquoi ce dossier est prioritaire ? » et inspecter les citations. Passer au rôle Entreprise : aucun indice agent, audit interne ou réseau agent ne doit apparaître. Le rôle Opérateur démo ne doit gérer que les entreprises synthétiques.

Avant la présentation, répéter au moins les étapes 1, 3–6 et 8 sur le **même** `DataDir` prévu pour la démo ; garder un autre `DataDir` neuf pour la prestation si un départ à 40 est nécessaire.

## Interfaces et limites à annoncer

- **Agent** : Dashboard, Dossiers en six zones, Réseau 3D et signaux descriptifs, Historique comparé à l'habitude de l'entreprise, Notifications internes, détails avancés et assistant cité.
- **Entreprise** : Mes dossiers, Actions requises, Documents, Messages. L'entreprise ne voit pas les scores/causes internes de l'agent.
- **Document** : PDF à texte natif analysé avec lien aux causes proposé, puis validation humaine. Un scan sans texte demande une inspection manuelle ; il n'est pas rejeté automatiquement.
- **Règles** : `calculated_at`, version de règle/moteur et causes sont conservés pour les nouveaux calculs. Les baisses avant décision de l'agent sont provisoires. Aucun indice n'est une probabilité de fraude.
