# Boussla · Interface d'instruction et de clarification

> **« Boussla ne demande pas seulement si une facture est bien calculée : il aide à comprendre à quoi elle correspond et quelles pièces expliquent un écart. »**

Boussla est une application d'aide à l'instruction et à la clarification contextuelle des opérations commerciales, séparant rigoureusement les montants facturés, réglés et déclarés, et orchestrant une boucle de dialogue contradictoire entre l'entreprise et l'agent vérificateur.

---

## 1. Vue d'ensemble et garanties de conception

- **Données synthétiques & service réel** : L'application s'exécute sur le service réel (`boussla.services.build_service()`) : base locale SQLite (`runtime/cases.sqlite`), contrôles déterministes de la voie B (`ChecksEngineV4`) et orchestration LangGraph. Les données sont synthétiques ; les constats et indices n'ont aucune portée juridique ni administrative. Le service en mémoire `MOCK` reste disponible pour le développement (`BOUSSLA_SERVICE=mock`).
- **Simulation de rôles locale** : Sélecteur de rôle démonstratif (« Entreprise » / « Agent ») sans authentification de production.
- **Intégrité comptable et fiscale** :
  - Les flux facturés, réglés observés et déclarés sont présentés dans des colonnes séparées ; ils ne sont jamais fusionnés en un total de chiffre d'affaires inventé.
  - La concordance de contenu et la provenance des fichiers sont distinguées : une pièce non signée ou d'origine inconnue n'est pas qualifiée de « fausse ».
  - L'indice de revue reflète une priorité de traitement documentaire, et en aucun cas une probabilité de fraude ou une notation de culpabilité.
  - Les calculs de sensibilité (+10 % de marge) sont purement arithmétiques et hypothétiques : ils ne modifient pas l'état canonique du dossier.
  - Seul le service backend autorise les révisions via contrôle de version et clé d'idempotence.

---

## 2. Installation et prérequis

- **Environnement** : Python 3.12 recommandé.
- **Dépendances** : Verrouillées dans `requirements.txt`.

```bash
# Création et activation de l'environnement virtuel
python -m venv .venv

# Windows (PowerShell) :
.\.venv\Scripts\Activate.ps1

# Linux / macOS :
source .venv/bin/activate

# Installation des dépendances
pip install -r requirements.txt
```

---

## 3. Lancement de l'application

```bash
streamlit run app.py
```

L'application s'ouvre sur `http://localhost:8501`.

- **Configuration optionnelle** : copier `.env.example` vers `.env` (jamais commité). Sans `OPENAI_API_KEY`, le planificateur de questions utilise le repli déterministe (mode `TEMPLATE`) ; sans `LANGSMITH_API_KEY`, seule la trace locale `runtime/events.jsonl` est écrite. Aucune panne de fournisseur ne bloque le dossier.
- **Réinitialiser la démo** : arrêter l'application et supprimer le dossier `runtime/` ; le dossier synthétique `CASE-BRICKS-001` est recréé en version 1 au démarrage suivant.
- **Service MOCK (développement UI uniquement)** : `BOUSSLA_SERVICE=mock streamlit run app.py` (PowerShell : `$env:BOUSSLA_SERVICE="mock"; streamlit run app.py`). Le bandeau indique alors explicitement « service MOCK ».

---

## 4. Validation des tests

La suite de tests automatisée valide les contrats, le service réel, les contrôles déterministes, le graphe LangGraph et les parcours UI Streamlit (hors ligne, sans clé API) :

```bash
python -m pytest -p no:cacheprovider
```

Le décompte exact des tests est indiqué dans le message de chaque commit d'intégration de la branche `integration/release`.

- `tests/integration/test_release_e2e.py` : moteur de la voie B actif, pièce d'une autre entreprise rejetée, fournisseur de modèle indisponible (repli `TEMPLATE`), traçage indisponible sans blocage, reprise après redémarrage sans double application.
- `tests/ui/test_app_real.py` : parcours complet cliqué sur le service réel (contexte, dépôt de facture, dossier agent, demande, réponse avec pièce et répartition, acceptation 40 → 0, version précédente conservée), déclaration seule non acceptable, clic sur une page périmée sans effet, persistance après redémarrage.

- `tests/backend/test_contracts.py` : Typage strict V4, sérialisation Pydantic, gestion des erreurs canoniques (`ErrorCode`).
- `tests/backend/test_mock_service.py` : Isolation des vues par rôle, immutabilité des versions, boucle de clarification, acceptation de pièces justificatives, recalcul du score, export de brouillons.
- `tests/ui/test_app.py` : Test de bout en bout avec `streamlit.testing.v1.AppTest` :
  - Ségrégation stricte des vues entreprise vs agent.
  - Protection contre la traversée de répertoire et vérification SHA-256 des pièces téléchargeables.
  - Neutralité des demandes de précision et exigence d'une pièce justificative pour accepter une réaffectation.
  - Transition de version atomique (v1 → v2) et ajustement de l'indice de revue (40 → 0).
  - Affichage de la matrice des hypothèses, de la table de sensibilité et des boutons d'export Markdown.

---

## 5. Parcours de démonstration guidé (5 minutes)

Le scénario de référence s'appuie sur le dossier de briques `CASE-BRICKS-001` :

### Étape 1 : Rôle Entreprise — « Mes opérations »
1. Sélectionner **Entreprise** dans le sélecteur de rôle.
2. Examiner le tableau « Facturé et réglé observé » : les montants facturés, réglés et déclarés sont visibles séparément.
3. Constater la possibilité de déposer une facture ou pièce justificative (PDF) avec option d'indiquer explicitement l'indisponibilité de la deuxième pièce (pas de blocage utilisateur).

### Étape 2 : Rôle Entreprise — « Contexte et réponses »
1. Consulter les projets enregistrés et déclarer le contexte d'utilisation (bénéficiaire, dates de début et fin prévues, phase du chantier).
2. Vérifier la boîte de réception des demandes de précision.

### Étape 3 : Rôle Agent — « File de revue »
1. Basculer sur **Agent**.
2. Dans l'onglet **File de revue**, observer la liste des dossiers avec l'indice de priorité (40), la couverture des preuves et le statut de clarification.
3. Noter l'absence totale de mention accusatoire ou de score de fraude.

### Étape 4 : Rôle Agent — « Dossier »
1. Dans l'onglet **Dossier**, consulter les métriques de synthèse et le rapprochement des observations (vues acheteur et vendeur d'une même opération).
2. **Références de quantité et constats** : observer l'écart de 1 000 unités entre l'achat (2 000 unités) et la référence documentée du lot P1 (1 000 unités).
3. **Pièces et provenance** : consulter l'origine et l'empreinte SHA-256 de chaque pièce (le téléchargement des pièces synthétiques n'est proposé qu'en mode MOCK).
4. **Passages de référence candidats** : affichés uniquement lorsque la recherche documentaire (voie C) est active ; sinon le nœud `retrieval` est marqué `NOT_RUN` dans Diagnostics.
5. **Matrice des hypothèses et sensibilité** : examiner les hypothèses ouvertes et la simulation de sensibilité (+10 % marge fictive) clairement marquée comme non-mutante.
6. **Brouillons exportables** : choisir l'audience puis cliquer sur **« Générer le brouillon »** (action journalisée, liée à la version courante) pour prévisualiser et télécharger la synthèse Markdown interne (Agent) ou destinataire (Entreprise).

### Étape 5 : Boucle de clarification contradictoire et révision
1. Cliquer sur **« Préparer une demande neutre »** : un brouillon neutre et sans accusation est généré par le service.
2. Cliquer sur **« Publier dans la boîte de démo »**.
3. Revenir sur **Entreprise** > **Contexte et réponses** : la demande apparaît dans la boîte.
4. *Test de déclaration seule* : Rédiger une réponse, cocher la proposition de répartition (1 000 pour chaque lot) sans joindre de fichier, et envoyer. Côté Agent, la proposition est marquée en attente avec l'avertissement qu'une déclaration seule ne suffit pas (bouton d'acceptation inactif).
5. *Test avec pièce justificative* : Avec une pièce jointe validant le second lot, le bouton **« Accepter dans ce dossier »** s'active côté Agent.
6. Cliquer sur **« Accepter dans ce dossier »** :
   - Le dossier passe atomiquement à une **nouvelle version** (N → N+1) ; la version précédente reste consultable (répartition P1 = 2 000 conservée dans l'historique).
   - Le constat de quantité est résolu.
   - L'indice de priorité passe de **40 à 0**.
   - Le comparatif **Avant / après la décision** s'affiche immédiatement.
   - L'historique complet des révisions est consigné.
   - Un double clic ou une page restée ouverte sur une ancienne version ne produit aucune seconde application.

### Étape 6 : Rôle Agent — « Diagnostics »
1. Ouvrir l'onglet **Diagnostics** pour visualiser le mode réel de chaque nœud (`LIVE`, `TEMPLATE`, `NOT_RUN`).
2. Noter la transparence sur l'état des intégrations : les benchmarks non exécutés sont étiquetés en toute honnêteté `NOT_RUN`.

---

## 6. Structure du projet

```
Boussla/
├── app.py                      # Point d'entrée Streamlit (simulation de rôles)
├── ui/
│   ├── __init__.py
│   ├── common.py               # Formatage monétaire TND et gestion des erreurs de service
│   ├── company.py              # Écrans Entreprise (Mes opérations, Contexte et réponses)
│   └── officer.py              # Écrans Agent (File de revue, Dossier, Diagnostics, Exports)
├── boussla/
│   ├── __init__.py
│   ├── contracts.py            # Types de données partagés V4, contrats et protocoles (voie A)
│   ├── services.py             # Service réel : seul point d'entrée des écritures (voie A)
│   ├── store.py                # Base SQLite append-only, versions et reçus d'actions (voie A)
│   ├── workflow.py             # Graphes LangGraph analyse/décision avec reprise (voie A)
│   ├── checks/ scenarios/      # Contrôles déterministes et scénarios (voie B)
│   └── mock_service.py         # Service en mémoire étiqueté MOCK (développement)
├── tests/
│   ├── backend/
│   │   ├── test_contracts.py   # Tests unitaires des contrats
│   │   └── test_mock_service.py# Tests du service mock et de la logique de révision
│   ├── checks/                 # Tests des contrôles (voie B)
│   ├── integration/            # Tests de publication de bout en bout
│   └── ui/
│       ├── test_app.py         # Parcours UI sur le service MOCK
│       └── test_app_real.py    # Parcours UI cliqués sur le service réel
├── docs/
│   └── build_lock/             # Spécifications V4-GIT-1, contrats et fixtures de référence
├── requirements.txt            # Verrou de dépendances
└── README.md                   # Guide d'exécution et de démonstration
```