# Audit navigateur sans correction — 28 septembre 2026

Branche examinée : `feat/progressive-review` au commit `22eb0dd`. L'application a été lancée hors ligne avec des bases SQLite synthétiques distinctes sur les ports 8063, 8064, 8070, 8071 et 8072. Le serveur préexistant de l'utilisateur sur 8000 n'a pas été utilisé. Aucun code produit n'a été modifié pendant cette campagne.

Le navigateur @Navigateur n'a pas pu démarrer : son moteur local a quitté avant l'ouverture d'un onglet (`windows sandbox failed: helper_unknown_error: apply deny-read ACLs`). Les interactions ont donc été exécutées dans Microsoft Edge/Chromium par Playwright, avec de vraies pages et requêtes locales. Ce changement d'outil est une limite de la campagne, pas un défaut de BOUSSLA.

## Résultats

| Contrôle | Résultat |
|---|---:|
| Parcours Playwright existants sur base neuve : contexte, dossier, historique, assistant, réseau, résilience, administration | 11/11 passés |
| Suite backend complète | 619/619 passés |
| Tests React | 34/34 passés |
| Build de production et TypeScript | réussi |
| Exploration de 25 contrôles UI/API supplémentaires | 24 passés, 1 défaut visuel confirmé après correction d'un appel de test mal formé |
| Parcours de progression supplémentaires | 40 → 30, 30 → 20 via API liée, 20 → 40 après rejet et 20 → 0 après acceptation observés |
| Rôles et écrans | 11 écrans principaux des trois rôles chargés sans alerte ni erreur JavaScript |

Les contrôles supplémentaires comprenaient recherche, tri et filtre de portefeuille ; six zones du dossier ; simulation sans mutation ; références, timeline, audit, diagnostics ; graphe et liste accessible ; historique à données insuffisantes ; écran Entreprise sans indices internes ; écran Opérateur ; affichage mobile ; refus de rôles/identités forgés ; isolation interentreprises ; routes 404/405 ; clé d'idempotence/version manquantes ; score injecté ; fichier non PDF ; motif de décision vide ; notification inconnue. Le test d'accès à l'assistant a d'abord envoyé un champ `expected_version` non accepté et reçu 400. Rejoué avec le schéma exact `{question}`, il a reçu 403 pour le rôle Entreprise : **pas un bug produit**.

## Problèmes à corriger, par priorité

### BROWSER-01 — Critique : une preuve non pertinente peut résoudre la cause quantité

Sur un dossier neuf `CASE-BRICKS-001` à 40, l'Entreprise répond à la demande de répartition P1/P2 en proposant 1000/1000 et choisit comme « pièce justificative existante » le **relevé de paiement** `03_payment_record.pdf` (`DOC-PAY-001`). L'API attribue `DOC-PAY-001` comme `source_document_id` de la proposition et passe à `EVIDENCE_RECEIVED`, **40 → 20**. Le bouton Agent « Accepter dans ce dossier » est actif ; un clic résout la cause et passe **20 → 0**. Une reproduction distincte avec la facture acheteur initiale `DOC-BUY-001` donne aussi 20 → 0. Ces pièces documentent paiement ou facture initiale, pas l'affectation P2 proposée.

Attendu : la pertinence de la pièce pour la cause et la modification proposées doit être vérifiée explicitement ; une pièce de paiement ou la facture source ne doit pas suffire à valider une nouvelle affectation. À défaut, la proposition doit rester à examiner sans résolution. Gravité : **bloquant pour toute démonstration qui prétend valider automatiquement la pertinence des preuves**. Les suites vertes ne couvrent pas ce choix de document préexistant via le formulaire.

### BROWSER-02 — Moyen : impossible de rattacher depuis l'UI une pièce déposée après une réponse

Sur une autre base neuve, une réponse explicative sans pièce donne **40 → 30**. La demande devient « Réponse reçue » et le bouton « Répondre à la demande » disparaît. Depuis l'écran Documents, l'Entreprise dépose ensuite le vrai justificatif `06_second_project_allocation.pdf` : la version passe de 3 à 4, mais la cause reste à 30, sans action UI pour lier ce dépôt à la réponse existante. L'API sait le faire lorsque l'upload porte `response_id` : une copie synthétique distincte du même PDF a fait **30 → 20**. Reposter les mêmes octets après dépôt isolé a reçu 409 « Pièce identique déjà déposée » ; l'UI n'offre pas de rattachement rétroactif de cette pièce déjà stockée.

Attendu : une action Entreprise ou Agent, soumise à contrôle de périmètre, doit lier une pièce tardive déjà déposée à la réponse/cause appropriée, sans exiger un doublon de fichier ni abaisser une autre cause.

### BROWSER-03 — Moyen : motif humain de validation/rejet non saisissable

Les boutons Agent « Accepter dans ce dossier » et « Rejeter » de la proposition n'offrent pas de champ de justification. L'audit d'une acceptation enregistre seulement « Acceptée dans ce dossier par l'agent (pas une authentification) » ; celui d'un rejet enregistre « Pièce non retenue dans ce dossier ». Le rejet a bien produit **20 → 40** et une notification Entreprise neutre, mais le *pourquoi* de la décision n'est pas capturé. Le formulaire distinct de décision de revue interne a un motif obligatoire ; celui des propositions n'en a pas.

Attendu : collecter et conserver la raison propre à chaque acceptation/rejet de preuve, avec l'acteur, la pièce et la version déjà tracés.

### BROWSER-04 — Moyen : débordement horizontal sur petits écrans

À 390 px, l'écran Agent « Dossiers » mesure **423 px** de largeur de document ; `cause-row` et les sections de synthèse assistée dépassent le viewport. À 320 px, tous les onglets Agent dépassent au moins **349 px**, le dossier atteint **423 px**. À 768 px, les onglets Agent mesurent **802 px** à cause notamment de `top-actions`. Les onglets Entreprise/Opérateur à 390 px n'ont pas montré de débordement de document. La navigation demeure cliquable, mais la lecture et les commandes demandent un défilement latéral ; certaines sections internes d'Avancé dépassent aussi leur colonne.

Attendu : contenu lisible et commandes accessibles sans débordement du document aux largeurs mobiles/tablette annoncées. Capture locale : `.tmp/browser_explore_2026-09-28/failure-11.png`.

## Vérifications réussies utiles pour le triage

- Un fichier texte et un PDF de plus de 10 Mo sont refusés par l'interface Entreprise ; le bouton de dépôt reste désactivé et la version du dossier ne change pas.
- Un fichier non PDF envoyé directement à l'API est refusé sans révision. Les routes Agent/Réseau/Audit restent interdites au rôle Entreprise ; l'Opérateur ne reçoit pas le Réseau Agent. Les champs de score et d'identité forgés sont refusés.
- Une correction manuelle de la quantité P2 de 1000 à 900 dans les champs extraits **n'a pas** accordé le palier cohérent 10 ; la cause est restée à 20, car la correction n'était pas soutenue par une nouvelle plage source du PDF. Ce cas n'est pas une contradiction documentaire sourcée et ne démontre pas le retour 10 → 40 dans l'interface.
- Le rejet d'une proposition avec pièce liée restaure 20 → 40 ; une notification « Justificatif non retenu » apparaît pour l'Entreprise. Une notification Agent peut être marquée lue sans faire disparaître les éléments non lus de l'Entreprise.
- La simulation « Impact si résolu » n'a pas changé la version du dossier. Les données historiques insuffisantes restent affichées comme telles. Aucun des 11 écrans principaux explorés n'a émis d'erreur JavaScript.

## Limites de couverture

Cette campagne n'établit pas que *toutes* les combinaisons possibles fonctionnent : elle utilise des données synthétiques et des scénarios finis. Elle ne teste pas les fournisseurs LIVE, les services publics, l'OCR d'un scan, les notifications email/SMS, une authentification réelle ou un déploiement multiutilisateur. Les retours 10 → 20/30/40, la résolution partielle multi-cause et les états de rapprochement rares ont des tests backend, mais n'ont pas tous été reproduits par manipulation visuelle dans cette campagne. Les bases, sorties et captures d'audit locales ont été conservées sous `.tmp/` et n'ont pas été publiées avec le rapport.
