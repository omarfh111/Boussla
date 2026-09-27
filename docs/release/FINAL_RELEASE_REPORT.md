# BOUSSLA final release — integration evidence

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
