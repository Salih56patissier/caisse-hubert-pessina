# -*- coding: utf-8 -*-
"""
Etape 1 : structure de la base SQLite + donnees de test
pour le logiciel de caisse "Hubert & Pessina".

Ce module ne fait que :
- creer le fichier caisse.db et ses tables si elles n'existent pas
- inserer un catalogue de test (categories / produits / sous-produits)
  si la base est vide, pour pouvoir valider la structure
- fournir une fonction d'affichage du catalogue pour verification manuelle

Aucune interface graphique ici : ce sera l'etape 2.
"""

import os
import sys
import sqlite3

if getattr(sys, "frozen", False):
    # Empaquete par PyInstaller (--onefile) : sys.executable pointe vers le
    # .exe lui-meme. __file__ pointerait vers le dossier temporaire
    # d'extraction (_MEIPASS), efface a chaque lancement : la base de
    # donnees doit vivre a cote du .exe, pas la-dedans.
    _DOSSIER_BASE = os.path.dirname(sys.executable)
else:
    _DOSSIER_BASE = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(_DOSSIER_BASE, "caisse.db")

PIN_ADMIN_PAR_DEFAUT = "1234"
TVA_SUR_PLACE_PAR_DEFAUT = 10
TVA_A_EMPORTER_PAR_DEFAUT = 20
IMPRIMANTE_NOM_PAR_DEFAUT = "GP-C80250 Series"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            nom    TEXT NOT NULL UNIQUE,
            ordre  INTEGER
        )
    """)
    # migration : les bases creees avant l'ajout du glisser-deposer n'ont pas
    # encore la colonne "ordre"
    colonnes_categories = [row["name"] for row in cur.execute("PRAGMA table_info(categories)").fetchall()]
    if "ordre" not in colonnes_categories:
        cur.execute("ALTER TABLE categories ADD COLUMN ordre INTEGER")
    cur.execute("UPDATE categories SET ordre = id WHERE ordre IS NULL")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS produits (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            nom                  TEXT NOT NULL,
            prix                 REAL,
            categorie_id         INTEGER NOT NULL,
            a_des_sous_produits  INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (categorie_id) REFERENCES categories(id)
        )
    """)
    # migration : TVA fixe par produit (ex: 0% pour le pain), independante
    # du choix Sur place / A emporter. NULL = suit le taux dynamique.
    colonnes_produits = [row["name"] for row in cur.execute("PRAGMA table_info(produits)").fetchall()]
    if "tva_fixe" not in colonnes_produits:
        cur.execute("ALTER TABLE produits ADD COLUMN tva_fixe REAL")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sous_produits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            produit_id  INTEGER NOT NULL,
            nom         TEXT NOT NULL,
            prix        REAL NOT NULL,
            FOREIGN KEY (produit_id) REFERENCES produits(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS ventes (
            id     INTEGER PRIMARY KEY AUTOINCREMENT,
            date   TEXT NOT NULL,
            heure  TEXT NOT NULL,
            total  REAL NOT NULL,
            note   TEXT
        )
    """)
    # migration : mode de vente (Sur place / A emporter) et decomposition
    # HT/TVA du total, conserves tels qu'appliques au moment de la vente.
    colonnes_ventes = [row["name"] for row in cur.execute("PRAGMA table_info(ventes)").fetchall()]
    if "mode_vente" not in colonnes_ventes:
        cur.execute("ALTER TABLE ventes ADD COLUMN mode_vente TEXT")
    if "total_ht" not in colonnes_ventes:
        cur.execute("ALTER TABLE ventes ADD COLUMN total_ht REAL")
    if "total_tva" not in colonnes_ventes:
        cur.execute("ALTER TABLE ventes ADD COLUMN total_tva REAL")
    # migration : mode de paiement (especes / carte), imprime sur le ticket
    if "mode_paiement" not in colonnes_ventes:
        cur.execute("ALTER TABLE ventes ADD COLUMN mode_paiement TEXT")
    # migration : remise globale (%) appliquee sur le ticket avant encaissement
    # (ex: prix de gros pour un client). Les lignes vente_lignes gardent le
    # prix nominal ; seuls les totaux de la vente sont deja remises.
    if "remise_pourcentage" not in colonnes_ventes:
        cur.execute("ALTER TABLE ventes ADD COLUMN remise_pourcentage REAL")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS vente_lignes (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            vente_id       INTEGER NOT NULL,
            nom_produit    TEXT NOT NULL,
            quantite       INTEGER NOT NULL,
            prix_unitaire  REAL NOT NULL,
            FOREIGN KEY (vente_id) REFERENCES ventes(id)
        )
    """)
    # migration : taux de TVA reellement applique a cette ligne au moment de
    # la vente (independant d'un eventuel changement de taux ulterieur -
    # l'historique ne doit jamais etre recalcule retroactivement).
    colonnes_lignes = [row["name"] for row in cur.execute("PRAGMA table_info(vente_lignes)").fetchall()]
    if "taux_tva" not in colonnes_lignes:
        cur.execute("ALTER TABLE vente_lignes ADD COLUMN taux_tva REAL")

    # Table technique (absente du cahier des charges initial) pour stocker le
    # PIN admin et d'autres reglages simples sous forme cle/valeur.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS config (
            cle    TEXT PRIMARY KEY,
            valeur TEXT
        )
    """)
    cur.execute(
        "INSERT OR IGNORE INTO config (cle, valeur) VALUES ('pin_admin', ?)",
        (PIN_ADMIN_PAR_DEFAUT,),
    )
    cur.execute(
        "INSERT OR IGNORE INTO config (cle, valeur) VALUES ('tva_sur_place', ?)",
        (str(TVA_SUR_PLACE_PAR_DEFAUT),),
    )
    cur.execute(
        "INSERT OR IGNORE INTO config (cle, valeur) VALUES ('tva_a_emporter', ?)",
        (str(TVA_A_EMPORTER_PAR_DEFAUT),),
    )
    cur.execute(
        "INSERT OR IGNORE INTO config (cle, valeur) VALUES ('imprimante_nom', ?)",
        (IMPRIMANTE_NOM_PAR_DEFAUT,),
    )
    cur.execute(
        "INSERT OR IGNORE INTO config (cle, valeur) VALUES ('logo_chemin', '')",
    )

    conn.commit()


def obtenir_taux_tva(conn):
    """Renvoie les taux de TVA (%) configures pour Sur place / A emporter,
    sous forme de dict {"sur_place": .., "a_emporter": ..}. Lus depuis la
    table config (pas codes en dur) pour pouvoir etre changes si la loi
    evolue, sans toucher au code."""
    lignes = conn.execute(
        "SELECT cle, valeur FROM config WHERE cle IN ('tva_sur_place', 'tva_a_emporter')"
    ).fetchall()
    valeurs = {row["cle"]: float(row["valeur"]) for row in lignes}
    return {
        "sur_place": valeurs.get("tva_sur_place", TVA_SUR_PLACE_PAR_DEFAUT),
        "a_emporter": valeurs.get("tva_a_emporter", TVA_A_EMPORTER_PAR_DEFAUT),
    }


def definir_taux_tva(conn, cle_config, valeur):
    """cle_config : 'tva_sur_place' ou 'tva_a_emporter'."""
    conn.execute(
        "INSERT OR REPLACE INTO config (cle, valeur) VALUES (?, ?)",
        (cle_config, str(valeur)),
    )
    conn.commit()


def obtenir_config_texte(conn, cle, defaut=""):
    """Lecture generique d'un reglage texte simple stocke dans la table
    config (nom d'imprimante, chemin du logo, ...)."""
    ligne = conn.execute("SELECT valeur FROM config WHERE cle = ?", (cle,)).fetchone()
    if ligne is None or ligne["valeur"] is None or ligne["valeur"] == "":
        return defaut
    return ligne["valeur"]


def definir_config_texte(conn, cle, valeur):
    conn.execute(
        "INSERT OR REPLACE INTO config (cle, valeur) VALUES (?, ?)",
        (cle, valeur),
    )
    conn.commit()


def obtenir_nom_imprimante(conn):
    return obtenir_config_texte(conn, "imprimante_nom", IMPRIMANTE_NOM_PAR_DEFAUT)


def definir_nom_imprimante(conn, nom):
    definir_config_texte(conn, "imprimante_nom", nom)


def obtenir_chemin_logo(conn):
    return obtenir_config_texte(conn, "logo_chemin", "")


def definir_chemin_logo(conn, chemin):
    definir_config_texte(conn, "logo_chemin", chemin)


def ajouter_categorie(conn, nom):
    ordre_max = conn.execute("SELECT COALESCE(MAX(ordre), 0) AS m FROM categories").fetchone()["m"]
    conn.execute("INSERT INTO categories (nom, ordre) VALUES (?, ?)", (nom, ordre_max + 1))
    conn.commit()
    return conn.execute("SELECT id FROM categories WHERE nom = ?", (nom,)).fetchone()["id"]


def definir_ordre_categories(conn, ids_categories_ordonnes):
    """ids_categories_ordonnes : liste des id de categories dans le nouvel
    ordre voulu (glisser-deposer dans le Mode Admin)."""
    for position, categorie_id in enumerate(ids_categories_ordonnes):
        conn.execute("UPDATE categories SET ordre = ? WHERE id = ?", (position, categorie_id))
    conn.commit()


def modifier_categorie(conn, categorie_id, nom):
    conn.execute("UPDATE categories SET nom = ? WHERE id = ?", (nom, categorie_id))
    conn.commit()


def supprimer_categorie(conn, categorie_id):
    """Supprime la categorie ainsi que tous ses produits et leurs
    sous-produits (parfums)."""
    ids_produits = [
        row["id"] for row in
        conn.execute("SELECT id FROM produits WHERE categorie_id = ?", (categorie_id,)).fetchall()
    ]
    for produit_id in ids_produits:
        conn.execute("DELETE FROM sous_produits WHERE produit_id = ?", (produit_id,))
    conn.execute("DELETE FROM produits WHERE categorie_id = ?", (categorie_id,))
    conn.execute("DELETE FROM categories WHERE id = ?", (categorie_id,))
    conn.commit()


def ajouter_produit_simple(conn, nom, prix, categorie_id, tva_fixe=None):
    conn.execute(
        "INSERT INTO produits (nom, prix, categorie_id, a_des_sous_produits, tva_fixe) VALUES (?, ?, ?, 0, ?)",
        (nom, prix, categorie_id, tva_fixe),
    )
    conn.commit()


def ajouter_produit_sous_menu(conn, nom, categorie_id, parfums, tva_fixe=None):
    """parfums : liste de tuples (nom_parfum, prix)"""
    cur = conn.execute(
        "INSERT INTO produits (nom, prix, categorie_id, a_des_sous_produits, tva_fixe) VALUES (?, NULL, ?, 1, ?)",
        (nom, categorie_id, tva_fixe),
    )
    produit_id = cur.lastrowid
    for nom_parfum, prix in parfums:
        conn.execute(
            "INSERT INTO sous_produits (produit_id, nom, prix) VALUES (?, ?, ?)",
            (produit_id, nom_parfum, prix),
        )
    conn.commit()
    return produit_id


def modifier_produit(conn, produit_id, nom, prix, categorie_id, tva_fixe=None):
    conn.execute(
        "UPDATE produits SET nom = ?, prix = ?, categorie_id = ?, tva_fixe = ? WHERE id = ?",
        (nom, prix, categorie_id, tva_fixe, produit_id),
    )
    conn.commit()


def supprimer_produit(conn, produit_id):
    conn.execute("DELETE FROM sous_produits WHERE produit_id = ?", (produit_id,))
    conn.execute("DELETE FROM produits WHERE id = ?", (produit_id,))
    conn.commit()


def ajouter_sous_produit(conn, produit_id, nom, prix):
    conn.execute(
        "INSERT INTO sous_produits (produit_id, nom, prix) VALUES (?, ?, ?)",
        (produit_id, nom, prix),
    )
    conn.commit()


def modifier_sous_produit(conn, sous_produit_id, nom, prix):
    conn.execute(
        "UPDATE sous_produits SET nom = ?, prix = ? WHERE id = ?",
        (nom, prix, sous_produit_id),
    )
    conn.commit()


def supprimer_sous_produit(conn, sous_produit_id):
    conn.execute("DELETE FROM sous_produits WHERE id = ?", (sous_produit_id,))
    conn.commit()


def exporter_catalogue(conn):
    """Renvoie le catalogue complet (categories/produits/sous-produits) sous
    forme de dict pret a etre serialise en JSON."""
    categories_export = []
    categories = conn.execute("SELECT * FROM categories ORDER BY ordre, id").fetchall()
    for cat in categories:
        produits_export = []
        produits = conn.execute(
            "SELECT * FROM produits WHERE categorie_id = ? ORDER BY id", (cat["id"],)
        ).fetchall()
        for prod in produits:
            if prod["a_des_sous_produits"]:
                sous_produits = conn.execute(
                    "SELECT * FROM sous_produits WHERE produit_id = ? ORDER BY id",
                    (prod["id"],),
                ).fetchall()
                produits_export.append({
                    "nom": prod["nom"],
                    "a_des_sous_produits": True,
                    "tva_fixe": prod["tva_fixe"],
                    "sous_produits": [{"nom": sp["nom"], "prix": sp["prix"]} for sp in sous_produits],
                })
            else:
                produits_export.append({
                    "nom": prod["nom"],
                    "a_des_sous_produits": False,
                    "prix": prod["prix"],
                    "tva_fixe": prod["tva_fixe"],
                })
        categories_export.append({"nom": cat["nom"], "produits": produits_export})

    return {"categories": categories_export}


def vider_catalogue(conn):
    conn.execute("DELETE FROM sous_produits")
    conn.execute("DELETE FROM produits")
    conn.execute("DELETE FROM categories")
    conn.commit()


def importer_catalogue(conn, catalogue):
    """Remplace tout le catalogue actuel par celui fourni (meme structure
    que exporter_catalogue). Ne touche pas a l'historique des ventes."""
    vider_catalogue(conn)
    for cat in catalogue.get("categories", []):
        categorie_id = ajouter_categorie(conn, cat["nom"])
        for prod in cat.get("produits", []):
            tva_fixe = prod.get("tva_fixe")
            if prod.get("a_des_sous_produits"):
                parfums = [(sp["nom"], sp["prix"]) for sp in prod.get("sous_produits", [])]
                ajouter_produit_sous_menu(conn, prod["nom"], categorie_id, parfums, tva_fixe=tva_fixe)
            else:
                ajouter_produit_simple(conn, prod["nom"], prod["prix"], categorie_id, tva_fixe=tva_fixe)


def seed_test_data(conn):
    """Insere un catalogue de test, uniquement si la base est vide."""
    nb_categories = conn.execute("SELECT COUNT(*) AS n FROM categories").fetchone()["n"]
    if nb_categories > 0:
        return False  # deja des donnees, on ne touche a rien

    cat_patisserie = ajouter_categorie(conn, "Patisserie")
    cat_tartes = ajouter_categorie(conn, "Tartes")
    cat_sables = ajouter_categorie(conn, "Sables")
    cat_evenement = ajouter_categorie(conn, "Evenement")
    cat_sale = ajouter_categorie(conn, "Sale")

    # --- Patisserie ---
    ajouter_produit_simple(conn, "Mille-feuilles", 15, cat_patisserie)
    ajouter_produit_simple(conn, "Paris-Brest", 18, cat_patisserie)
    ajouter_produit_sous_menu(conn, "Eclairs", cat_patisserie, [
        ("Chocolat", 12),
        ("Cafe", 12),
        ("Vanille", 12),
        ("Fraise", 13),
    ])

    # --- Tartes ---
    ajouter_produit_simple(conn, "Tarte aux fraises", 25, cat_tartes)
    ajouter_produit_simple(conn, "Tarte au citron", 22, cat_tartes)
    ajouter_produit_simple(conn, "Tarte Tatin", 20, cat_tartes)

    # --- Sables ---
    ajouter_produit_simple(conn, "Sable nature", 5, cat_sables)
    ajouter_produit_simple(conn, "Sable chocolat", 6, cat_sables)
    ajouter_produit_simple(conn, "Sable amande", 6, cat_sables)

    # --- Evenement (avec sous-produits de tailles/formules) ---
    ajouter_produit_sous_menu(conn, "Piece montee", cat_evenement, [
        ("Petite (20 pers)", 800),
        ("Moyenne (40 pers)", 1500),
        ("Grande (60 pers)", 2200),
    ])
    ajouter_produit_sous_menu(conn, "Gateau anniversaire", cat_evenement, [
        ("6 parts", 150),
        ("10 parts", 220),
        ("15 parts", 300),
    ])

    # --- Sale ---
    ajouter_produit_simple(conn, "Quiche lorraine (part)", 18, cat_sale)
    ajouter_produit_simple(conn, "Croissant sale", 10, cat_sale)
    ajouter_produit_simple(conn, "Sandwich traiteur", 25, cat_sale)

    conn.commit()
    return True


def afficher_catalogue(conn):
    """Affiche tout le catalogue dans la console, pour verification."""
    categories = conn.execute("SELECT * FROM categories ORDER BY ordre, id").fetchall()
    for cat in categories:
        print("[CATEGORIE] {}".format(cat["nom"]))
        produits = conn.execute(
            "SELECT * FROM produits WHERE categorie_id = ? ORDER BY id", (cat["id"],)
        ).fetchall()
        for prod in produits:
            if prod["a_des_sous_produits"]:
                print("    {} (sous-menu)".format(prod["nom"]))
                sous_produits = conn.execute(
                    "SELECT * FROM sous_produits WHERE produit_id = ? ORDER BY id",
                    (prod["id"],),
                ).fetchall()
                for sp in sous_produits:
                    print("        - {} : {} DH".format(sp["nom"], sp["prix"]))
            else:
                print("    {} : {} DH".format(prod["nom"], prod["prix"]))
        print()


if __name__ == "__main__":
    conn = get_connection()
    init_db(conn)
    a_insere = seed_test_data(conn)

    print("Base de donnees : {}".format(DB_PATH))
    print("Donnees de test inserees : {}".format("oui" if a_insere else "non (deja presentes)"))
    print("PIN admin par defaut : {}".format(PIN_ADMIN_PAR_DEFAUT))
    print()
    print("=== Catalogue actuel ===")
    print()
    afficher_catalogue(conn)

    conn.close()
