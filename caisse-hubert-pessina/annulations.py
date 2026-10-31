# -*- coding: utf-8 -*-
"""
Annulation des ventes ("Gestion des ventes").

Regles :
- une vente n'est JAMAIS supprimee : elle est marquee annulee
  (ventes.annulee = 1) et l'annulation est enregistree dans la table
  `annulations` (qui, quand, motif, montant, code admin ou non) ;
- une vente annulee sort du CA, des tickets, du recap, du rapport et de
  l'attendu especes, mais reste visible (barree) dans l'Historique ;
- annulation TOTALE uniquement (pas de retrait d'une ligne) : on annule
  le ticket et on le refait si besoin ;
- le vendeur annule seul SES ventes du poste en cours, pendant
  DELAI_MINUTES apres l'encaissement, motif obligatoire. Au-dela (ou
  vente d'un autre vendeur / d'un poste deja compte) : code admin.

Especes : le calcul de l'attendu (caisse.calcul_attendu) retire les
annulations especes "rembourse_tiroir" faites pendant la periode :
- vente du poste en cours : toujours retiree (+X puis -X = 0), que
  l'argent ait ete rendu au client ou jamais recu (erreur de saisie) ;
- vente d'un poste DEJA COMPTE (admin uniquement) : l'admin choisit
  * "rendre l'argent maintenant" : le tiroir s'ouvre, -X sur le poste en
    cours, qui a effectivement rendu l'argent ;
  * "correction seulement" : rien ne sort du tiroir, l'attendu du poste
    en cours ne bouge pas (l'ecart du poste d'origine reste tel quel).
Les periodes sont delimitees par l'id des annulations (comme pour les
ventes et les sorties), jamais par l'heure.
"""

from datetime import datetime

DELAI_MINUTES = 10

MOTIFS = [
    "Client a change d'avis",
    "Erreur de saisie",
    "Erreur especes / carte",
    "Autre",
]


def creer_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS annulations (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            date           TEXT NOT NULL,
            heure          TEXT NOT NULL,
            vente_id       INTEGER NOT NULL UNIQUE,
            montant        REAL NOT NULL,
            mode_paiement  TEXT,
            motif          TEXT NOT NULL,
            vendeur_id     INTEGER,
            par_admin      INTEGER NOT NULL DEFAULT 0,
            rembourse_tiroir INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (vente_id) REFERENCES ventes(id)
        )
    """)
    colonnes = [row[1] for row in cur.execute("PRAGMA table_info(ventes)").fetchall()]
    if "annulee" not in colonnes:
        cur.execute("ALTER TABLE ventes ADD COLUMN annulee INTEGER NOT NULL DEFAULT 0")
    # releves : derniere annulation prise en compte (NULL sur les anciennes
    # releves = 0, aucune annulation n'existait avant)
    colonnes = [row[1] for row in cur.execute("PRAGMA table_info(releves)").fetchall()]
    if "derniere_annulation_id" not in colonnes:
        cur.execute("ALTER TABLE releves ADD COLUMN derniere_annulation_id INTEGER")


def _datetime_vente(vente):
    try:
        return datetime.strptime("{} {}".format(vente["date"], vente["heure"]), "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return None


def vente(conn, vente_id):
    return conn.execute("SELECT * FROM ventes WHERE id = ?", (vente_id,)).fetchone()


def annulation_de(conn, vente_id):
    return conn.execute("SELECT * FROM annulations WHERE vente_id = ?", (vente_id,)).fetchone()


def ventes_du_jour(conn, date_texte, limite=None):
    """Ventes du jour, les plus recentes d'abord (annulees comprises)."""
    requete = "SELECT * FROM ventes WHERE date = ? ORDER BY id DESC"
    if limite:
        requete += " LIMIT {:d}".format(int(limite))
    return conn.execute(requete, (date_texte,)).fetchall()


def annulations_du_jour(conn, date_texte):
    return conn.execute("SELECT * FROM annulations WHERE date = ? ORDER BY id", (date_texte,)).fetchall()


def dans_poste_en_cours(conn, v):
    """La vente fait-elle partie du poste en cours (pas encore comptee
    dans une fin de poste / fermeture) ?"""
    import caisse  # import local : caisse importe aussi ce module
    r = caisse.derniere_releve(conn)
    return r is not None and r["type"] not in caisse.TYPES_FIN_DE_POSTE and v["id"] > r["derniere_vente_id"]


def autorisation_vendeur(conn, v, vendeur_id, maintenant=None):
    """Le vendeur connecte peut-il annuler `v` SANS le code admin ?
    Renvoie (True, None) ou (False, raison lisible)."""
    maintenant = maintenant or datetime.now()
    if v["annulee"]:
        return False, "Vente deja annulee."
    if vendeur_id is None or v["vendeur_id"] != vendeur_id:
        return False, "Vente d'un autre vendeur."
    if not dans_poste_en_cours(conn, v):
        return False, "Vente d'un poste deja compte."
    quand = _datetime_vente(v)
    if quand is None or (maintenant - quand).total_seconds() > DELAI_MINUTES * 60:
        return False, "Plus de {} minutes depuis la vente.".format(DELAI_MINUTES)
    return True, None


def annuler(conn, vente_id, motif, vendeur_id, par_admin=False, rembourse_tiroir=True, maintenant=None):
    """Annule la vente (une seule fois). Renvoie la ligne `annulations`
    creee. Leve ValueError si la vente n'existe pas ou est deja annulee.
    rembourse_tiroir=False : correction sans mouvement d'especes (vente
    d'un poste deja compte), ignoree par le calcul de l'attendu."""
    maintenant = maintenant or datetime.now()
    with conn:
        v = conn.execute("SELECT * FROM ventes WHERE id = ?", (vente_id,)).fetchone()
        if v is None:
            raise ValueError("Vente introuvable.")
        if v["annulee"]:
            raise ValueError("Vente deja annulee.")
        cur = conn.execute(
            "INSERT INTO annulations (date, heure, vente_id, montant, mode_paiement, motif, vendeur_id, "
            "par_admin, rembourse_tiroir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (maintenant.strftime("%Y-%m-%d"), maintenant.strftime("%H:%M:%S"), vente_id, v["total"],
             v["mode_paiement"], motif, vendeur_id, 1 if par_admin else 0, 1 if rembourse_tiroir else 0),
        )
        conn.execute("UPDATE ventes SET annulee = 1 WHERE id = ?", (vente_id,))
    return conn.execute("SELECT * FROM annulations WHERE id = ?", (cur.lastrowid,)).fetchone()


def especes_annulees(conn, depuis_id, jusqua_id):
    """Total des annulations de ventes ESPECES dont l'id est dans
    ]depuis_id, jusqua_id] (argent rendu depuis le tiroir)."""
    return conn.execute(
        "SELECT COALESCE(SUM(montant), 0) AS s FROM annulations "
        "WHERE mode_paiement = 'especes' AND rembourse_tiroir = 1 AND id > ? AND id <= ?",
        (depuis_id, jusqua_id),
    ).fetchone()["s"]
