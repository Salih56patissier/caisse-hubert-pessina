# Logiciel de caisse Hubert & Pessina : document de passation

Version transmise : `V2 - 2026-10-01.26` (constante `VERSION_APP` dans `main.py`),
avec les modifications du panneau ticket du 2026-10-23 (voir section 8).

Pâtisserie Hubert & Pessina (Témara, Maroc), monnaie : dirham (DH).
La caisse tourne en magasin sur un PC Windows tactile, avec une imprimante
thermique et un tiroir-caisse.

---

## 1. Lancer la caisse

Prérequis : Windows, Python 3 (la caisse tourne actuellement en 3.14) et Tkinter (fourni avec Python).

```
pip install -r requirements.txt     (pywin32, Pillow)
python main.py                      (ou double-clic sur lancer_caisse.bat)
```

- Au premier lancement, `caisse.db` (SQLite) est créé à côté des fichiers,
  avec un **catalogue de test** (`database.seed_test_data`).
- **Code admin par défaut** : constante `PIN_ADMIN_PAR_DEFAUT` dans `database.py`.
  Tapé sur l'écran de connexion, il ouvre le Mode Admin. Il faut d'abord
  y créer un vendeur pour pouvoir vendre.
- **Sans imprimante** : les fonctions d'impression lèvent une exception.
  La caisse l'attrape et affiche un message, sans planter.
- **Synchro Google** : elle est inactive tant qu'aucune adresse de script
  n'est réglée dans le Mode Admin. Elle fonctionne donc hors ligne sans rien configurer.

## 2. Ce qui n'est PAS dans ce dossier (volontairement)

| Élément | Raison |
|---|---|
| `caisse.db` réel | Ventes réelles du magasin, vendeurs et codes PIN |
| `google_sheets.json` | Identifiants de la synchro Google |
| Code secret et URL du script Google | Remplacés par `A_REMPLACER` dans `google_apps_script.txt` et `tableau_de_bord/index.html` |
| Journaux (`*.log`), `sauvegardes/` | Données du poste et anciennes versions |

Ne jamais travailler sur la base réelle du magasin. Une base de test se
recrée toute seule : il suffit de supprimer `caisse.db`.

## 3. Architecture

Application de bureau **Python / Tkinter**, base **SQLite** locale, sans
serveur. Chaque module crée ses propres tables (`creer_tables`) au démarrage.

| Fichier | Rôle |
|---|---|
| `main.py` | Fenêtre principale `CaisseApp` : catégories, tuiles produits, panneau ticket, encaissement, menus |
| `styles.py` | Palette, polices, composants dessinés (`Carte`, `Segments`, `ScrollableFrame`…), grille adaptative, DPI |
| `database.py` | Tables catalogue / ventes / config, catalogue de test, réglages (TVA, imprimante, logo) |
| `ventes.py` | **Point d'entrée unique** pour enregistrer une vente (détaillée ou vente rapide) |
| `vente_rapide.py` | Vente au montant (rush du matin), ou ligne « Vente rapide » ajoutée au ticket |
| `annulations.py` / `gestion_ventes.py` | Annulation d'une vente : règles + écran |
| `caisse.py` | Fond de caisse, relevés (comptage du tiroir), sorties d'espèces, coffre, calcul attendu / écart |
| `comptage.py` / `ecran_comptage.py` | Comptage du tiroir façon « feuille de caisse » (pièces pesées, billets comptés) |
| `fenetre_comptages.py` | Écarts par vendeur (admin) |
| `vendeurs.py` / `connexion.py` | Vendeurs, code PIN à 4 chiffres, écran de connexion |
| `tiroir.py` | Ouverture du tiroir + journal |
| `impression.py` | Tickets ESC/POS en RAW via `win32print` (Gprinter GP-C80250, 80 mm) |
| `historique.py` | Historique des ventes + Récap (protégés par le code admin) |
| `rapport.py` | Rapport de fin de journée imprimable (admin) |
| `ticket_z.py` | Ticket Z : clôture + effacement des données de vente |
| `remise_a_zero.py` | Remise à zéro ponctuelle, déclenchée par un fichier `remise_a_zero.flag` |
| `sync.py` + `google_apps_script.txt` | Envoi en arrière-plan des nouvelles lignes vers Google Sheets toutes les 60 s |
| `tableau_de_bord/index.html` | Tableau de bord web (téléphone) qui lit le Google Sheet |
| `admin.py` | Mode Admin : catalogue, vendeurs, TVA, imprimante, Google, export/import JSON |
| `dialogues.py`, `pave_numerique.py` | Fenêtres et pavé numérique tactiles réutilisables |

Tables : `categories`, `produits`, `sous_produits`, `ventes`, `vente_lignes`,
`journal_tiroir`, `vendeurs`, `connexions`, `releves`, `releve_details`,
`sorties_especes`, `releves_coffre`, `annulations`, `config` (clé / valeur).

## 4. Règles métier à respecter absolument

Ce sont les garde-fous anti-erreur et anti-fraude de la caisse. Le
propriétaire y tient. Ne pas les affaiblir sans son accord.

1. **Une vente enregistrée n'est jamais modifiée ni supprimée.** Seul le
   drapeau `ventes.annulee` peut être posé, par `annulations.annuler()`.
   Chaque annulation est tracée (qui, quand, motif, montant).
2. **Annulation totale uniquement.** Un vendeur annule seul ses ventes du
   poste en cours, pendant quelques minutes et avec un motif. Au-delà, il faut le code admin.
3. **Comptage à l'aveugle.** Le montant attendu et l'écart ne sont **jamais**
   montrés au vendeur, seulement dans l'Historique (code admin).
   `attendu = base + ventes espèces - sorties`. Les périodes sont délimitées
   par les **id**, pas par l'heure.
4. **Le tiroir** ne s'ouvre qu'après une vente en espèces, ou via
   « Ouvrir tiroir » avec un motif obligatoire. **Chaque** ouverture est journalisée.
5. **Ticket Z** : les id ne repartent pas à 1 (AUTOINCREMENT). Le Google Sheet
   garde tout l'historique, sans doublon.
6. **La synchro ne bloque jamais la caisse** : tout est d'abord écrit en local,
   et l'envoi est retenté plus tard.
7. **Le ticket en cours** (`CaisseApp.ticket`) reste en mémoire uniquement.
   Rien n'est écrit en base avant l'encaissement.

## 5. Contraintes d'interface

- **Écran tactile** : grosses zones de touche (environ 32 à 40 px minimum).
  Utiliser `dialogues.py` plutôt que `messagebox` et `pave_numerique.py` pour
  toute saisie de chiffres. Ne jamais exiger le clavier.
- **Petit écran du magasin** : la fenêtre est limitée à 950 × 680
  (`LARGEUR_FENETRE_MAX` / `HAUTEUR_FENETRE_MAX`, voir `diagnostic_ecran.log`
  créé au lancement). Toujours tester à cette taille.
- Panneau ticket à droite : 300 px (`LARGEUR_ZONE_TICKET`). Seule la liste des
  articles est élastique (avec défilement). Le haut est de taille fixe et le
  bas (Total TTC + ENCAISSER) n'est jamais compressé.
- Style : palette bruns / crème / framboise définie dans `styles.py`. Ne pas
  coder de couleurs en dur ailleurs.

## 6. Conventions de code

- Noms, commentaires et docstrings **en français, sans accents** dans le code.
- Chaque module commence par une docstring qui explique ses règles. Les
  commentaires expliquent le **pourquoi** (cas réel du magasin).
- Dates et heures en heure locale. Montants en DH, affichés en `{:.2f}` pour
  les totaux et en `{:g}` pour les prix unitaires.
- Toute nouvelle action sur une vente passe par `ventes.py` ou `annulations.py`,
  jamais par un `UPDATE` / `DELETE` direct depuis un écran.

## 7. Matériel en magasin

- Imprimante : Gprinter GP-C80250I Plus, USB, vue par Windows comme
  « GP-C80250 Series » (nom modifiable dans l'Admin). 42 caractères par ligne.
- Tiroir-caisse branché sur l'imprimante (RJ11), commande `ESC p`.
- Les envois bloqués (imprimante éteinte) sont **purgés** de la file Windows
  après 3 s, pour éviter que des tickets ou des ouvertures de tiroir sortent plus tard.

## 8. Dernières modifications (2026-10-23)

Panneau ticket de l'écran principal (`main.py`, `_construire_ticket` et `_rafraichir_ticket`) :
- **Nombre d'articles** (somme des quantités) en gros chiffre framboise à côté
  de « Ticket en cours ». Il sert à vérifier la boîte du client d'un coup d'œil.
- En-tête plus compact : titre, Sur place / A emporter et Dernier ticket /
  Ouvrir tiroir en plus petit.
- Lignes d'articles en plus grand (`POLICE_LIGNE_NOM` / `POLICE_LIGNE_DETAIL`).
- En bas, il ne reste que : Remise, **Total TTC**, **ENCAISSER**. Total HT et
  TVA ne sont plus affichés à l'écran, mais restent sur le ticket imprimé.
- Le ticket imprimé est inchangé.

## 9. Pour rendre ton travail

1. Ne modifie pas ce document, sauf la section 10 ci-dessous.
2. Note dans la section 10 chaque changement : fichier, ce qui change et pourquoi.
3. Teste à 950 × 680, avec et sans imprimante.
4. Renvoie **le dossier complet** (sans `caisse.db`, `__pycache__` ni `*.log`).
   Il sera comparé fichier par fichier avec la version d'origine avant d'être
   installé sur la caisse du magasin.

## 10. Journal des modifications (à remplir)

| Date | Fichier(s) | Changement | Raison |
|---|---|---|---|
| 2026-10-24 | admin.py | Code secret Google et adresse du script masqués par défaut dans le Mode Admin ; affichage en clair uniquement après un second code PIN (« Afficher les codes »). | Ne pas exposer les identifiants de synchro en clair sur l’écran admin. |
| 2026-10-24 | main.py | Bouton de maintenance « Maint. » (activation par 5 clics sur le titre, protégé par PIN). Permet de retirer un pourcentage choisi des ventes espèces du jour. | Exercice de cours : interface conditionnelle, paramètre variable, algorithme de sélection, opérations sur la base. |
| 2026-10-24 | styles.py | Palette rafraichie, ombres plus douces, coins plus ronds. `BoutonArrondi` devient un bouton lisse (comme `Carte`, sans ombre). Nouveau `ajuster_texte` : le texte est reduit ou passe a la ligne aux espaces pour ne jamais depasser de son bouton. Georgia retiree des montants (chiffres a hauteur variable) et gardee pour le nom de la patisserie. | Rendre l'interface plus moderne et supprimer les textes rognes. |
| 2026-10-24 | main.py | En-tete : titre centre dans l'espace libre (il touchait les boutons). Ticket : panneau 330 px, montant de ligne dans sa propre colonne, nom coupe aux espaces, total ajuste. Tuiles produit : puce de prix, pastille d'accent. Fenetre de paiement et titres adaptes a leur contenu. Version `V2 - 2026-10-24.27`. | Chevauchements et coupures constates sur le ticket et l'en-tete. |
| 2026-10-24 | dialogues.py, pave_numerique.py, ecran_comptage.py, historique.py, connexion.py, admin.py, gestion_ventes.py, fenetre_comptages.py, vente_rapide.py | Fenetres dimensionnees d'apres leur contenu (plus de hauteur fixe qui rognait Annuler, le calendrier ou la barre de total du comptage). Ligne d'actions de categorie de l'Admin sur deux lignes. Pastilles pour le code vendeur. Titres en Segoe UI. | Debordements avec la mise a l'echelle Windows. |
