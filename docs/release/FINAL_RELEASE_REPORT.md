# BOUSSLA final release — integration evidence

## État démonstration du 28 septembre 2026

Le compte rendu actuel, la matrice des phases et le protocole de test manuel se trouvent dans [DEMO_READINESS_2026-09-28.md](DEMO_READINESS_2026-09-28.md). Sur `feat/progressive-review`, le dernier contrôle complet donne 619 tests backend, 34 tests React et 11 parcours Playwright passés, avec build et formatage valides. Les phases 6, 19 et 20 restent partielles aux limites documentées. Les sections ci-dessous décrivent des livraisons antérieures et leurs chiffres ne sont pas le résultat actuel.

## Mise à jour du 27 septembre 2026 — livraison 2 : historique et confiance

La branche `feat/progressive-review` ajoute un indicateur historique séparé de la revue documentaire, calculé sur l'historique couvert propre à l'entreprise, et une confiance opérationnelle réversible. Leurs facteurs, références, versions de méthode et statuts sont renvoyés par le backend au seul agent. L'historique sans base couverte reste `null` / `INSUFFICIENT_DATA`. La confiance demande au moins deux observations attribuables (demandes publiées et propositions) ; elle tient compte des délais de réponse, demandes échues, propositions acceptées/rejetées, cohérence ou contradiction d'une pièce et signaux historiques couverts. Le score documentaire ne consomme aucun de ces deux indices. L'interface affiche les facteurs et jusqu'à douze mois de contexte fournis par l'API, sans calculer les indicateurs.

Vérifications exécutées pour cette livraison :

- `python -m pytest -q -x -o addopts='' -p no:cacheprovider` : **522 tests passés**, un avertissement de dépréciation Starlette.
- `npm --prefix frontend run test` : **22/22 tests passés** ; `typecheck`, `format:check` et `build` : passés.
- `npm --prefix frontend run test:e2e -- demo.spec.ts` : **1/1 parcours passé**, serveur local isolé et fournisseurs externes désactivés malgré la présence de `.env`.
- Contrats vérifiés : confiance réversible sur réponse tardive, acceptation et rejet, contradiction de pièce, données insuffisantes ; isolation de la vue entreprise ; historique sans effet sur le score documentaire.

Limites : l'indice de confiance est un indicateur opérationnel de démonstration, pas une conclusion fiscale ni une probabilité de fraude. Les données de portefeuille et l'historique sont synthétiques. La classification et la vérification exhaustive à chaque dépôt, le nouveau parcours dossier/entreprise et le graphe 3D relèvent des lots suivants. Les chiffres de la livraison 1 et de l'ancienne intégration ci-dessous sont conservés comme historique, pas comme état actuel de cette branche.

## Mise à jour du 27 septembre 2026 — livraison 1 du parcours progressif

La branche `feat/progressive-review` apporte un moteur de revue documentaire **par cause**, sans toucher au calcul des constats ni convertir l'indice en probabilité de fraude. Les états sont `UNRESOLVED`, `EXPLANATION_RECEIVED`, `EVIDENCE_RECEIVED`, `EVIDENCE_COHERENT` et `RESOLVED` (facteurs 100/75/50/25/0 %). Une cause de poids 40 suit donc 40 → 30 → 20 → 10 → 0. Les trois baisses avant décision humaine sont provisoires ; une preuve contradictoire ou rejetée revient au poids brut. Une pièce jointe sans lien explicite avec la réponse et la cause ne réduit rien. Les réponses et dépôts conservent leur score dans les révisions versionnées ; le frontend n'en déduit aucun palier.

Le dossier agent expose score courant, contribution brute et courante par cause, couverture des preuves, urgence de triage, et des emplacements distincts pour signal historique et confiance opérationnelle. Ces deux derniers sont renvoyés `null` / `INSUFFICIENT_DATA` par l'API et affichés comme tels ; leur calcul est prévu après cette livraison. Le triage garde la contribution documentaire brute comme base tant qu'une baisse est provisoire, et affiche cette composante. La vue entreprise ne reçoit ni score ni ces indicateurs internes.

Vérifications exécutées sur cette branche :

- `python -m pytest -q -x -p no:cacheprovider` : 506 tests collectés, suite passée sans échec.
- `npm --prefix frontend run test` : 21/21 tests ; `typecheck`, `format:check` et `build` : passés.
- `npm --prefix frontend run test:e2e -- demo.spec.ts` : 1/1 parcours Playwright sur un serveur hors ligne et une base de test vierge, montrant 40 → 20 provisoire → 0 après décision agent.
- Tests d'intégration : 40 → 30 → 20 → 10 → 0, contradiction 10 → 40, rejet 20 → 40, idempotence, historique versionné et isolation entreprise.

Limite explicite : le palier 10 repose ici sur des champs d'extraction confirmés, complets et sourcés dans le test ; le traitement automatique exhaustif des documents et les moteurs de confiance/historique sont des lots ultérieurs. Les chiffres de la section historique ci-dessous correspondent à la livraison précédente, pas à cette branche.

Branch `integration/final-release` from main `b33ae94`, merging lanes A (`874c718`), B (`07fdd00`), C (`2083312`) and D (`4559a7a`) with `--no-ff`. Synthetic data only.

## Judge gauntlet — round 2 (harness `test/live-judge-gauntlet` @ `159ef7b`, run against this branch)

| Outcome | Count |
|---|---:|
| PASS | 42 |
| SAFE_REJECTION | 6 |
| SAFE_FALLBACK | 2 |
| MANUAL_REQUIRED | 4 |
| BUG | 0 |
| NOT_RUN | 0 |

- 47 scenarios through the unmodified harness in live mode (providers configured privately): 36 PASS, 5 SAFE_REJECTION, 2 SAFE_FALLBACK, 4 MANUAL_REQUIRED, 0 BUG. Offline mode: 0 BUG as well.
- JUDGE-040…045 were `pending_context` stubs in the round-1 harness; a round-2 driver executed them against the integrated service (offline with an injected model disagreement, and live): 5 PASS, 1 SAFE_REJECTION (end before start). With a live model that agrees with the dates, JUDGE-045 correctly stays CONSISTENT; the disagreement path is proven with the injected run.
- JUDGE-046 (React/API/browser) is covered by the Playwright journeys: 8/8 offline and 8/8 live.
- Critical 0, High 0, Medium 0. Round-1 defects: LJG-001, LJG-002, LJG-003, LJG-004 and JUDGE-054 all pass (harness regressions and repository tests).

## Tests

- `python -m pytest -p no:cacheprovider`: 488 passed; with every non-loopback socket blocked: 0 external connection attempts.
- Frontend: typecheck, Prettier, 20 unit tests, production build; Playwright journeys 1–6 + boot + resilience, offline and live, each on a fresh disposable runtime.
- Public references: 29 reviewed passages, 4 official sources, hashes match. Qdrant `boussla_public_references_v2`: 29 points, 384 dimensions, Cosine, public payload only. Retrieval evaluation (21 fixed cases): top-1 16/21, top-3 19/21.

## Providers (live, synthetic data)

OpenAI extraction, context interpretation, investigator selection and grounded reference generation: LIVE. Jev routing: LIVE. Qdrant retrieval: LIVE. LangSmith: traces for `boussla.auto_clarification` and `boussla.investigator` (and the workflow nodes) with hidden inputs/outputs; no company names, tax IDs, invoice or purpose text, payment data or secrets found in metadata, tags or errors.

## Security

Company scope, operator-only administration, forged identity/score/triage/investigator fields (403), strict payloads (INVALID_INPUT), no `dangerouslySetInnerHTML`, no local paths in API responses, secret scan of tracked files, build output, screenshots and branch history: 0 matches.
