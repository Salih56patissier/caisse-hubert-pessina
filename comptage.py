# -*- coding: utf-8 -*-
"""
Comptage du tiroir, comme la "Feuille de caisse" papier :
- PIECES pesees : pour chaque valeur, poids total en grammes ; nombre de
  pieces = poids / poids unitaire (arrondi a l'entier). Une valeur peut
  etre reglee en "compter" dans l'admin (on tape alors le nombre).
- BILLETS comptes : nombre de billets par valeur.

L'etalonnage (poids unitaire de chaque piece) et la tolerance d'ecart sont
stockes dans la table config.
"""

import database

PIECES = [0.5, 1, 2, 5, 10]
BILLETS = [20, 50, 100, 200]

TOLERANCE_PAR_DEFAUT = 10.0

# Poids approximatifs d'une piece (g) donnes par Salih, utilises tant
# qu'aucun etalonnage n'a ete fait dans l'admin.
POIDS_PAR_DEFAUT = {0.5: 4.0, 1: 6.0, 2: 7.0, 5: 7.5, 10: 10.0}
NB_PIECES_ETALONNAGE = 20

METHODE_PESEE = "pesee"
METHODE_COMPTAGE = "comptage"


def libelle(valeur, nature):
    if nature == "piece":
        return "Pieces de 50 centimes" if valeur == 0.5 else "Pieces de {:g} DH".format(valeur)
    return "Billets de {:g} DH".format(valeur)


def _cle(prefixe, valeur):
    return "{}_{:g}".format(prefixe, valeur)


def creer_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS releve_details (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            releve_id       INTEGER NOT NULL,
            nature          TEXT NOT NULL,
            valeur          REAL NOT NULL,
            methode         TEXT NOT NULL,
            saisie          REAL NOT NULL,
            poids_unitaire  REAL,
            quantite        INTEGER NOT NULL,
            montant         REAL NOT NULL,
            FOREIGN KEY (releve_id) REFERENCES releves(id)
        )
    """)


# ---------------------------------------------------------------------------
# Reglages (admin)
# ---------------------------------------------------------------------------
def poids_etalonne(conn, valeur):
    texte = database.obtenir_config_texte(conn, _cle("poids_piece", valeur), "")
    try:
        return float(texte) if texte else None
    except ValueError:
        return None


def poids_unitaire(conn, valeur):
    """Poids etalonne dans l'admin, sinon poids par defaut, sinon None."""
    return poids_etalonne(conn, valeur) or POIDS_PAR_DEFAUT.get(valeur)


def etalonner(conn, valeur, poids_de_20_pieces):
    unitaire = round(poids_de_20_pieces / NB_PIECES_ETALONNAGE, 4)
    database.definir_config_texte(conn, _cle("poids_piece", valeur), str(unitaire))
    return unitaire


def methode_piece(conn, valeur):
    return database.obtenir_config_texte(conn, _cle("methode_piece", valeur), METHODE_PESEE)


def definir_methode_piece(conn, valeur, methode):
    database.definir_config_texte(conn, _cle("methode_piece", valeur), methode)


def methode_effective(conn, valeur):
    """Pesee impossible sans etalonnage : on bascule alors en comptage."""
    if methode_piece(conn, valeur) == METHODE_PESEE and poids_unitaire(conn, valeur):
        return METHODE_PESEE
    return METHODE_COMPTAGE


def tolerance(conn):
    try:
        return float(database.obtenir_config_texte(conn, "tolerance_ecart", str(TOLERANCE_PAR_DEFAUT)))
    except ValueError:
        return TOLERANCE_PAR_DEFAUT


def definir_tolerance(conn, valeur):
    database.definir_config_texte(conn, "tolerance_ecart", "{:g}".format(valeur))


def dans_tolerance(conn, ecart):
    return abs(ecart) <= tolerance(conn) + 1e-9


# ---------------------------------------------------------------------------
# Calcul
# ---------------------------------------------------------------------------
def lignes_de_comptage(conn):
    """Les 9 lignes de la feuille, dans l'ordre : pieces puis billets."""
    lignes = []
    for v in PIECES:
        methode = methode_effective(conn, v)
        lignes.append({"nature": "piece", "valeur": v, "methode": methode,
                       "poids_unitaire": poids_unitaire(conn, v) if methode == METHODE_PESEE else None})
    for v in BILLETS:
        lignes.append({"nature": "billet", "valeur": v, "methode": METHODE_COMPTAGE, "poids_unitaire": None})
    return lignes


def calculer_ligne(ligne, saisie):
    """saisie = grammes (pesee) ou nombre (comptage). Renvoie (quantite, montant)."""
    saisie = saisie or 0
    if ligne["methode"] == METHODE_PESEE:
        quantite = int(round(saisie / ligne["poids_unitaire"])) if ligne["poids_unitaire"] else 0
    else:
        quantite = int(round(saisie))
    return quantite, round(quantite * ligne["valeur"], 2)


def enregistrer_details(conn, releve_id, details):
    """details : liste de dicts produits par l'ecran de comptage. Appelee
    dans la meme transaction que la releve (voir caisse.enregistrer_releve)."""
    for d in details:
        conn.execute(
            "INSERT INTO releve_details (releve_id, nature, valeur, methode, saisie, poids_unitaire, "
            "quantite, montant) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (releve_id, d["nature"], d["valeur"], d["methode"], d["saisie"], d["poids_unitaire"],
             d["quantite"], d["montant"]),
        )


def details_releve(conn, releve_id):
    return conn.execute(
        "SELECT * FROM releve_details WHERE releve_id = ? ORDER BY id", (releve_id,)
    ).fetchall()


def resume_details(conn, releve_id):
    """Texte court pour l'historique : '0,5x186  1x28 ... | 20x6  100x3'."""
    details = details_releve(conn, releve_id)
    if not details:
        return ""
    pieces = ["{:g}x{}".format(d["valeur"], d["quantite"]) for d in details if d["nature"] == "piece" and d["quantite"]]
    billets = ["{:g}x{}".format(d["valeur"], d["quantite"]) for d in details if d["nature"] == "billet" and d["quantite"]]
    return "Pieces : {}   |   Billets : {}".format("  ".join(pieces) or "-", "  ".join(billets) or "-")
