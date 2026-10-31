# -*- coding: utf-8 -*-
"""
Vendeurs : chacun se connecte avec un code PIN a 4 chiffres. Chaque vente
et chaque ouverture du tiroir est rattachee au vendeur connecte.

Un vendeur n'est jamais supprime (son historique doit rester lisible) :
on le desactive. Un PIN est unique parmi les vendeurs actifs et ne peut
jamais etre egal au code admin.
"""

from datetime import datetime


def creer_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vendeurs (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            nom      TEXT NOT NULL,
            pin      TEXT NOT NULL,
            actif    INTEGER NOT NULL DEFAULT 1,
            cree_le  TEXT
        )
    """)
    # une ligne par connexion d'un vendeur (debut / fin) : sert a savoir
    # qui tenait la caisse a quel moment, et servira a la releve de caisse
    cur.execute("""
        CREATE TABLE IF NOT EXISTS connexions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            vendeur_id  INTEGER NOT NULL,
            debut       TEXT NOT NULL,
            fin         TEXT,
            FOREIGN KEY (vendeur_id) REFERENCES vendeurs(id)
        )
    """)
    # prise de poste SANS comptage (le patron) : le fond de caisse reprend
    # automatiquement le dernier comptage
    colonnes = [row[1] for row in cur.execute("PRAGMA table_info(vendeurs)").fetchall()]
    if "sans_comptage" not in colonnes:
        cur.execute("ALTER TABLE vendeurs ADD COLUMN sans_comptage INTEGER NOT NULL DEFAULT 0")
    for table in ("ventes", "journal_tiroir"):
        colonnes = [row[1] for row in cur.execute("PRAGMA table_info({})".format(table)).fetchall()]
        if "vendeur_id" not in colonnes:
            cur.execute("ALTER TABLE {} ADD COLUMN vendeur_id INTEGER".format(table))


def _pin_admin(conn):
    ligne = conn.execute("SELECT valeur FROM config WHERE cle = 'pin_admin'").fetchone()
    return ligne["valeur"] if ligne else None


def lister(conn, seulement_actifs=False):
    requete = "SELECT * FROM vendeurs"
    if seulement_actifs:
        requete += " WHERE actif = 1"
    return conn.execute(requete + " ORDER BY actif DESC, nom COLLATE NOCASE").fetchall()


def trouver_par_pin(conn, pin):
    return conn.execute("SELECT * FROM vendeurs WHERE pin = ? AND actif = 1", (pin,)).fetchone()


def nom(conn, vendeur_id):
    if vendeur_id is None:
        return None
    ligne = conn.execute("SELECT nom FROM vendeurs WHERE id = ?", (vendeur_id,)).fetchone()
    return ligne["nom"] if ligne else None


def verifier_pin_disponible(conn, pin, vendeur_id_exclu=None):
    """Renvoie None si le PIN est utilisable, sinon un message d'erreur."""
    if len(pin) != 4 or not pin.isdigit():
        return "Le code doit faire 4 chiffres."
    if pin == _pin_admin(conn):
        return "Ce code est celui de l'admin. Choisissez-en un autre."
    ligne = conn.execute(
        "SELECT id FROM vendeurs WHERE pin = ? AND actif = 1 AND id != ?",
        (pin, vendeur_id_exclu or -1),
    ).fetchone()
    if ligne:
        return "Ce code est deja utilise par un autre vendeur."
    return None


def ajouter(conn, nom_vendeur, pin):
    with conn:
        conn.execute(
            "INSERT INTO vendeurs (nom, pin, actif, cree_le) VALUES (?, ?, 1, ?)",
            (nom_vendeur, pin, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def modifier_nom(conn, vendeur_id, nom_vendeur):
    with conn:
        conn.execute("UPDATE vendeurs SET nom = ? WHERE id = ?", (nom_vendeur, vendeur_id))


def modifier_pin(conn, vendeur_id, pin):
    with conn:
        conn.execute("UPDATE vendeurs SET pin = ? WHERE id = ?", (pin, vendeur_id))


def definir_sans_comptage(conn, vendeur_id, sans):
    with conn:
        conn.execute("UPDATE vendeurs SET sans_comptage = ? WHERE id = ?", (1 if sans else 0, vendeur_id))


def definir_actif(conn, vendeur_id, actif):
    with conn:
        conn.execute("UPDATE vendeurs SET actif = ? WHERE id = ?", (1 if actif else 0, vendeur_id))


def pin_admin_disponible(conn, pin):
    """Le nouveau code admin ne doit correspondre a aucun vendeur actif."""
    if len(pin) != 4 or not pin.isdigit():
        return "Le code doit faire 4 chiffres."
    if conn.execute("SELECT 1 FROM vendeurs WHERE pin = ? AND actif = 1", (pin,)).fetchone():
        return "Ce code est deja celui d'un vendeur."
    return None


def definir_pin_admin(conn, pin):
    with conn:
        conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES ('pin_admin', ?)", (pin,))


def ouvrir_connexion(conn, vendeur_id):
    with conn:
        cur = conn.execute(
            "INSERT INTO connexions (vendeur_id, debut) VALUES (?, ?)",
            (vendeur_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    return cur.lastrowid


def fermer_connexion(conn, connexion_id):
    if connexion_id is None:
        return
    with conn:
        conn.execute(
            "UPDATE connexions SET fin = ? WHERE id = ? AND fin IS NULL",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), connexion_id),
        )


def fermer_connexions_orphelines(conn):
    """Connexions restees ouvertes (logiciel ferme brutalement, coupure de
    courant) : on les cloture au demarrage avec une fin 'inconnue'."""
    with conn:
        conn.execute("UPDATE connexions SET fin = 'inconnue' WHERE fin IS NULL")
