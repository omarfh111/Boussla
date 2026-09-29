# Nouveaux PDF synthétiques pour BOUSSLA

Importer uniquement les fichiers `cas_*.pdf` dans l'application. `evaluation_only/manifest.json` est une grille de référence pour le testeur : ne pas le transmettre au modèle ni à l'application.

Les fichiers 01 et 02 décrivent une seule transaction. Une importation par le même utilisateur ne crée pas deux origines indépendantes. Les fichiers 23 et 24 nécessitent respectivement une revue manuelle (scan sans texte natif) et un traitement de PDF chiffré ; mot de passe du fichier 24 : `synthetic-test-only`. Aucune pièce ne prouve un paiement réel, une identité ou une authenticité juridique.

La classe prévue par le scénario et celle du routeur natif peuvent différer. Le cas 14 documente une limite connue : il est routé comme une réponse d'affectation, pas comme une référence.

| PDF | Classe visée | Objectif de test |
|---|---|---|
| cas_01_facture_acheteur.pdf | INVOICE | Facture de base, avec montants et ligne cohérents. |
| cas_02_facture_vendeur.pdf | INVOICE | Même opération vue par le vendeur ; l'origine dépend du canal d'import. |
| cas_03_facture_vue_divergente.pdf | INVOICE | Même référence que 01/02, mais TTC divergent. |
| cas_04_facture_total_incoherent.pdf | INVOICE | HT + TVA différent du TTC. |
| cas_05_facture_ligne_incoherente.pdf | INVOICE | Quantité multipliée par prix unitaire différente du HT de ligne. |
| cas_06_facture_date_future.pdf | INVOICE | Date documentaire postérieure au 2026-09-29. |
| cas_07_facture_champs_manquants.pdf | INVOICE | TTC, devise et identifiant acheteur manquants. |
| cas_08_facture_champs_contradictoires.pdf | INVOICE | Deux valeurs TTC incompatibles dans le même document. |
| cas_09_facture_deux_pages.pdf | INVOICE | Champs répartis sur deux pages avec texte natif. |
| cas_10_facture_autre_entreprise.pdf | INVOICE | Acheteur différent du dossier Horizon ; vérifier la portée humaine. |
| cas_11_paiement_solde.pdf | PAYMENT_RECORD | Règlement déclaré complet ; PDF seul insuffisant pour prouver la banque. |
| cas_12_paiement_partiel.pdf | PAYMENT_RECORD | Règlement déclaré partiel ; ne pas assimiler à une anomalie. |
| cas_13_paiement_initie.pdf | PAYMENT_RECORD | Ordre initié ; ne pas traiter comme règlement effectué. |
| cas_14_reference_affectation.pdf | ALLOCATION_REFERENCE | Référence quantitative ; le routeur natif actuel la confond avec une réponse. |
| cas_15_reponse_affectation.pdf | ALLOCATION_RESPONSE | Réponse d'affectation de 125 unités, sans acceptation automatique. |
| cas_16_reponse_quantite_excessive.pdf | ALLOCATION_RESPONSE | Réponse de 400 unités pour une facture de 345 ; tester le refus de dépassement. |
| cas_17_bon_livraison.pdf | DELIVERY_RECORD | Bon de livraison, sans preuve indépendante de réception. |
| cas_18_avoir.pdf | CREDIT_NOTE | Avoir rattaché à la facture, à traiter comme ajustement distinct. |
| cas_19_contrat.pdf | CONTRACT | Contrat ; texte lisible sans champs de facture complets. |
| cas_20_declaration.pdf | DECLARATION | Déclaration de contexte ; une affirmation n'est pas une preuve. |
| cas_21_document_autre.pdf | OTHER_OR_UNKNOWN | Bon de commande hors classes reconnues par le routeur natif. |
| cas_22_texte_adversarial.pdf | INVOICE | Instruction hostile dans la pièce ; contenu non fiable. |
| cas_23_scan_sans_texte.pdf | INVOICE | PDF image sans texte natif ; revue manuelle attendue. |
| cas_24_pdf_chiffre.pdf | INVOICE | PDF chiffré ; extraction native non prise en charge. |
