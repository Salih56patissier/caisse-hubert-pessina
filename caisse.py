# -*- coding: utf-8 -*-
"""
Controle de caisse : fond de caisse, releves (comptage du tiroir) et
sorties d'especes.

Principe : la caisse est "ouverte" entre une releve d'OUVERTURE et une
releve de FERMETURE. Chaque releve enregistre le montant compte dans le
tiroir. A chaque changement de vendeur et a la fermeture :

    attendu = base + ventes especes - sorties   (depuis la releve precedente)
    ecart   = compte - attendu

`base` = montant compte a la releve precedente. L'ecart n'est JAMAIS
montre au vendeur (comptage "a l'aveugle") : il n'apparait que dans
l'Historique, protege par le code admin.

Les periodes sont delimitees par les id de ventes / sorties (et non par
l'heure), pour qu'aucune vente ne puisse etre comptee deux fois ou oubliee.
"""

from datetime import datetime

import annulations
import comptage

OUVERTURE = "ouverture"
CHANGEMENT = "changement"
FERMETURE = "fermeture"

# Codes gardes pour compatibilite avec les releves deja enregistres :
#   ouverture  = PRISE DE POSTE (le vendeur qui arrive compte : son fond)
#   changement = FIN DE POSTE   (le vendeur qui part compte : son ecart)
#   fermeture  = FIN DE POSTE + fin de journee (reference du lendemain)
LIBELLES = {OUVERTURE: "Prise de poste", CHANGEMENT: "Fin de poste", FERMETURE: "Fermeture"}
TYPES_FIN_DE_POSTE = (CHANGEMENT, FERMETURE)


def libelle_ecart(type_releve):
    """Prise de poste : ecart de PASSATION (comptage de l'arrivant -
    comptage de celui qui est parti, doit etre 0). Fin de poste : ecart
    de POSTE (compte - attendu)."""
    return "Ecart de passation" if type_releve == OUVERTURE else "Ecart de poste"

TYPE_SORTIE = "sortie"
TYPE_DEPOT_COFFRE = "depot_coffre"
MOTIF_DEPOT_COFFRE = "Depot coffre"

MOTIFS_SORTIE = ["Paiement fournisseur", "Achat pour le magasin", "Retrait patron", "Autre"]


def creer_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS releves (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            date               TEXT NOT NULL,
            heure              TEXT NOT NULL,
            type               TEXT NOT NULL,
            vendeur_id         INTEGER,
            compte_par_id      INTEGER,
            montant_compte     REAL NOT NULL,
            base               REAL,
            ventes_especes     REAL,
            sorties            REAL,
            attendu            REAL,
            ecart              REAL,
            derniere_vente_id  INTEGER NOT NULL,
            derniere_sortie_id INTEGER NOT NULL,
            note               TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sorties_especes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            heure       TEXT NOT NULL,
            montant     REAL NOT NULL,
            motif       TEXT NOT NULL,
            vendeur_id  INTEGER
        )
    """)
    # V2 : une sortie peut etre un DEPOT COFFRE (billets mis dans la boite
    # sous le tiroir). Il sort du tiroir comme une sortie, mais doit se
    # retrouver dans le coffre : voir releves_coffre.
    colonnes = [row[1] for row in cur.execute("PRAGMA table_info(sorties_especes)").fetchall()]
    if "type" not in colonnes:
        cur.execute("ALTER TABLE sorties_especes ADD COLUMN type TEXT NOT NULL DEFAULT 'sortie'")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS releves_coffre (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            date             TEXT NOT NULL,
            heure            TEXT NOT NULL,
            montant_compte   REAL NOT NULL,
            attendu          REAL NOT NULL,
            ecart            REAL NOT NULL,
            nb_depots        INTEGER NOT NULL,
            dernier_depot_id INTEGER NOT NULL
        )
    """)


def _max_id(conn, table):
    return conn.execute("SELECT COALESCE(MAX(id), 0) AS m FROM {}".format(table)).fetchone()["m"]


def derniere_releve(conn):
    return conn.execute("SELECT * FROM releves ORDER BY id DESC LIMIT 1").fetchone()


def est_ouverte(conn):
    r = derniere_releve(conn)
    return r is not None and r["type"] != FERMETURE


def calcul_attendu(conn):
    """Renvoie dict {base, ventes_especes, sorties, attendu,
    derniere_vente_id, derniere_sortie_id} depuis la derniere releve."""
    r = derniere_releve(conn)
    base = r["montant_compte"] if r else 0.0
    depuis_vente = r["derniere_vente_id"] if r else 0
    depuis_sortie = r["derniere_sortie_id"] if r else 0
    depuis_annulation = (r["derniere_annulation_id"] or 0) if r else 0
    max_vente = _max_id(conn, "ventes")
    max_sortie = _max_id(conn, "sorties_especes")
    max_annulation = _max_id(conn, "annulations")
    # ventes especes de la periode (annulees comprises) MOINS l'argent rendu
    # pour les annulations especes faites pendant la periode : voir
    # annulations.py (une vente annulee dans le meme poste s'annule a 0)
    ventes_especes = conn.execute(
        "SELECT COALESCE(SUM(total), 0) AS s FROM ventes "
        "WHERE mode_paiement = 'especes' AND id > ? AND id <= ?",
        (depuis_vente, max_vente),
    ).fetchone()["s"]
    ventes_especes = round(ventes_especes - annulations.especes_annulees(conn, depuis_annulation, max_annulation), 2)
    sorties = conn.execute(
        "SELECT COALESCE(SUM(montant), 0) AS s FROM sorties_especes WHERE id > ? AND id <= ?",
        (depuis_sortie, max_sortie),
    ).fetchone()["s"]
    return {
        "base": base, "ventes_especes": ventes_especes, "sorties": sorties,
        "attendu": round(base + ventes_especes - sorties, 2),
        "derniere_vente_id": max_vente, "derniere_sortie_id": max_sortie,
        "derniere_annulation_id": max_annulation,
    }


NOTE_SANS_COMPTAGE = "prise de poste sans comptage (reprise du dernier comptage)"


def derniere_releve_comptee(conn):
    """Dernier comptage REEL du tiroir (pas une prise de poste automatique)."""
    return conn.execute(
        "SELECT * FROM releves WHERE COALESCE(note, '') != ? AND COALESCE(note, '') NOT LIKE 'sans comptage%' "
        "ORDER BY id DESC LIMIT 1",
        (NOTE_SANS_COMPTAGE,),
    ).fetchone()


def prise_de_poste_sans_comptage(conn, vendeur_id):
    """Prise de poste du patron : pas de comptage, le fond de caisse est
    l'attendu actuel (= dernier comptage, + ventes especes - sorties
    depuis, normalement rien). Pas d'ecart. Renvoie le montant repris."""
    montant = calcul_attendu(conn)["attendu"]
    enregistrer_releve(conn, OUVERTURE, montant, vendeur_id, vendeur_id, note=NOTE_SANS_COMPTAGE,
                       sans_comptage=True)
    return montant


MOTIF_RETRAIT_PATRON = "Retrait patron"


def depart_sans_comptage(conn, type_releve, montant_laisse, vendeur_id):
    """Fin de poste / fermeture du patron, SANS comptage : il declare
    seulement ce qu'il laisse dans le tiroir. La difference avec l'attendu
    est enregistree comme sortie "Retrait patron" (les billets qu'il
    emporte), puis la releve prend le montant laisse comme base. Aucun
    ecart : c'est le comptage du vendeur suivant qui verifiera (ecart de
    passation). Renvoie le montant du retrait."""
    retrait = round(calcul_attendu(conn)["attendu"] - montant_laisse, 2)
    if retrait > 0:
        enregistrer_sortie(conn, retrait, MOTIF_RETRAIT_PATRON, vendeur_id)
    if retrait > 0:
        note = "sans comptage : laisse {:g} DH declare, retrait patron {:g} DH".format(montant_laisse, retrait)
    else:
        note = "sans comptage : rien pris, fond repris {:g} DH".format(montant_laisse)
    enregistrer_releve(conn, type_releve, montant_laisse, vendeur_id, vendeur_id, note=note, sans_comptage=True)
    return max(retrait, 0)


def enregistrer_releve(conn, type_releve, montant_compte, vendeur_id, compte_par_id, note=None,
                       details=None, sans_comptage=False):
    """Enregistre une releve. Pour l'ouverture, pas d'ecart calcule (le
    fond de caisse EST la nouvelle base). Renvoie l'id de la releve.
    sans_comptage=True : rien n'a ete compte, aucun ecart enregistre."""
    calc = calcul_attendu(conn)
    maintenant = datetime.now()
    if type_releve == OUVERTURE and derniere_releve(conn) is None:
        base = ventes = sorties = attendu = ecart = None  # tout premier comptage : rien a comparer
    else:
        # prise de poste : l'attendu est le dernier comptage (+ ventes /
        # sorties eventuelles depuis, normalement aucune) -> ecart de passation
        base, ventes, sorties, attendu = calc["base"], calc["ventes_especes"], calc["sorties"], calc["attendu"]
        ecart = round(montant_compte - attendu, 2)
    if sans_comptage:
        ecart = None
    with conn:
        cur = conn.execute(
            "INSERT INTO releves (date, heure, type, vendeur_id, compte_par_id, montant_compte, base, "
            "ventes_especes, sorties, attendu, ecart, derniere_vente_id, derniere_sortie_id, note, "
            "derniere_annulation_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (maintenant.strftime("%Y-%m-%d"), maintenant.strftime("%H:%M:%S"), type_releve,
             vendeur_id, compte_par_id, montant_compte, base, ventes, sorties, attendu, ecart,
             calc["derniere_vente_id"], calc["derniere_sortie_id"], note, calc["derniere_annulation_id"]),
        )
        if details:
            comptage.enregistrer_details(conn, cur.lastrowid, details)
    return cur.lastrowid


def enregistrer_sortie(conn, montant, motif, vendeur_id):
    maintenant = datetime.now()
    with conn:
        cur = conn.execute(
            "INSERT INTO sorties_especes (date, heure, montant, motif, vendeur_id) VALUES (?, ?, ?, ?, ?)",
            (maintenant.strftime("%Y-%m-%d"), maintenant.strftime("%H:%M:%S"), montant, motif, vendeur_id),
        )
    return cur.lastrowid


def comptage_requis_a_la_connexion(conn, vendeur_id):
    """Que faut-il faire quand `vendeur_id` tape son code ?

    Regle : chaque vendeur compte en PRENANT son poste et en le QUITTANT
    (les vendeurs ne se croisent pas forcement, ex: pause de la priere).

    Renvoie un tuple (action, info) :
    - ("ouverture", None)             aucun poste en cours (fin de poste ou
                                      fermeture faite) -> prise de poste
    - ("fermeture_oubliee", ancien)   caisse restee ouverte un jour precedent
                                      -> compter (cloture de la veille, puis
                                      ce montant devient le fond du jour)
    - ("releve_absente", ancien)      un AUTRE vendeur tenait la caisse sans
                                      avoir fait sa releve (logiciel ferme,
                                      coupure...) -> compter maintenant, ecart
                                      attribue a l'ancien vendeur
    - (None, None)                    rien a compter, connexion directe
    `ancien` = id du vendeur responsable de la periode non cloturee."""
    r = derniere_releve(conn)
    if r is None or r["type"] in TYPES_FIN_DE_POSTE:
        return "ouverture", None
    ts_releve = "{} {}".format(r["date"], r["heure"])
    derniere_cnx = conn.execute(
        "SELECT vendeur_id FROM connexions WHERE debut >= ? ORDER BY id DESC LIMIT 1", (ts_releve,)
    ).fetchone()
    ancien = derniere_cnx["vendeur_id"] if derniere_cnx else r["vendeur_id"]
    if r["date"] != datetime.now().strftime("%Y-%m-%d"):
        return "fermeture_oubliee", ancien
    if derniere_cnx is not None and derniere_cnx["vendeur_id"] != vendeur_id:
        return "releve_absente", ancien
    return None, None


def releves_du_jour(conn, date_texte):
    return conn.execute("SELECT * FROM releves WHERE date = ? ORDER BY id", (date_texte,)).fetchall()


def sorties_du_jour(conn, date_texte):
    return conn.execute("SELECT * FROM sorties_especes WHERE date = ? ORDER BY id", (date_texte,)).fetchall()


# ---------------------------------------------------------------------------
# Coffre (boite sous le tiroir)
# ---------------------------------------------------------------------------
def enregistrer_depot_coffre(conn, montant, vendeur_id):
    maintenant = datetime.now()
    with conn:
        cur = conn.execute(
            "INSERT INTO sorties_especes (date, heure, montant, motif, vendeur_id, type) VALUES (?, ?, ?, ?, ?, ?)",
            (maintenant.strftime("%Y-%m-%d"), maintenant.strftime("%H:%M:%S"), montant,
             MOTIF_DEPOT_COFFRE, vendeur_id, TYPE_DEPOT_COFFRE),
        )
    return cur.lastrowid


def dernier_releve_coffre(conn):
    return conn.execute("SELECT * FROM releves_coffre ORDER BY id DESC LIMIT 1").fetchone()


def coffre_attendu(conn):
    """Total des depots enregistres depuis le dernier releve du coffre.
    Renvoie (montant, nombre_de_depots, id_du_dernier_depot)."""
    r = dernier_releve_coffre(conn)
    depuis = r["dernier_depot_id"] if r else 0
    ligne = conn.execute(
        "SELECT COALESCE(SUM(montant), 0) AS s, COUNT(*) AS n, COALESCE(MAX(id), ?) AS m "
        "FROM sorties_especes WHERE type = ? AND id > ?",
        (depuis, TYPE_DEPOT_COFFRE, depuis),
    ).fetchone()
    return ligne["s"], ligne["n"], ligne["m"]


def enregistrer_releve_coffre(conn, montant_compte):
    """Salih vide le coffre et tape ce qu'il a trouve. Ecart = trouve -
    total des depots enregistres depuis le releve precedent."""
    attendu, nb, dernier_id = coffre_attendu(conn)
    ecart = round(montant_compte - attendu, 2)
    maintenant = datetime.now()
    with conn:
        conn.execute(
            "INSERT INTO releves_coffre (date, heure, montant_compte, attendu, ecart, nb_depots, dernier_depot_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (maintenant.strftime("%Y-%m-%d"), maintenant.strftime("%H:%M:%S"), montant_compte,
             attendu, ecart, nb, dernier_id),
        )
    return attendu, ecart


def derniers_releves_coffre(conn, limite=5):
    return conn.execute("SELECT * FROM releves_coffre ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
