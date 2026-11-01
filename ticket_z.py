# -*- coding: utf-8 -*-
"""
Ticket Z : cloture de periode + remise a zero de la caisse.

Deroulement (Mode Admin) :
1. controles : caisse fermee (fermeture du soir faite) et plus aucune
   ligne en attente d'envoi vers Google (le Sheet garde tout l'historique) ;
2. impression du ticket Z (totaux reels depuis le dernier Z) ;
3. l'admin confirme que le ticket est bien sorti ;
4. EFFACEMENT DEFINITIF (sans copie) : ventes, lignes, annulations,
   comptages, sorties / depots coffre, releves du coffre, journal du
   tiroir, connexions. Sont conserves : categories, produits, vendeurs,
   reglages (TVA, codes, imprimante, etalonnage, Google...).

Les numeros (id) ne repartent PAS a 1 (AUTOINCREMENT conserve) : le
Google Sheet ignore les id deja presents, des id reutilises y seraient
donc perdus. Le numero de Z est un compteur (config z_numero).
"""

from datetime import datetime

import caisse
import comptage
import sync
import tiroir
import vendeurs

# ordre : tables "filles" avant les tables "meres" (cles etrangeres)
TABLES_EFFACEES = [
    "vente_lignes", "annulations", "ventes",
    "releve_details", "releves",
    "sorties_especes", "releves_coffre",
    "journal_tiroir", "connexions",
]

LIBELLES_MODE = {"sur_place": "Sur place", "a_emporter": "A emporter"}


def numero_suivant(conn):
    ligne = conn.execute("SELECT valeur FROM config WHERE cle = 'z_numero'").fetchone()
    try:
        return int(ligne["valeur"]) + 1 if ligne else 1
    except (TypeError, ValueError):
        return 1


def verifier(conn):
    """Renvoie (True, None) ou (False, raison lisible)."""
    r = caisse.derniere_releve(conn)
    if r is not None and r["type"] != caisse.FERMETURE:
        return False, "La caisse est ouverte.\nFaites d'abord la fermeture du soir (Menu > Fermer la caisse)."
    en_attente = sync.lignes_en_attente(conn)
    if en_attente:
        sync.demander_synchro()
        return False, ("{} ligne(s) pas encore envoyee(s) a Google.\n"
                       "Synchro relancee : reessayez dans une minute (internet necessaire).").format(en_attente)
    if conn.execute("SELECT COUNT(*) AS n FROM ventes").fetchone()["n"] == 0:
        return False, "Aucune vente depuis le dernier Z."
    return True, None


def _dh(x):
    return "{:.2f} DH".format(x or 0)


def _date(d, h):
    try:
        return datetime.strptime("{} {}".format(d, h), "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "{} {}".format(d, h)


def construire(conn, numero):
    """Lignes du ticket Z (format de rapport.py / impression.imprimer_rapport)."""
    toutes = conn.execute("SELECT * FROM ventes ORDER BY id").fetchall()
    ventes = [v for v in toutes if not v["annulee"]]
    lignes = []

    premiere, derniere = toutes[0], toutes[-1]
    lignes.append(("texte", "Z n. {}".format(numero)))
    lignes.append(("texte", "Du {}".format(_date(premiere["date"], premiere["heure"]))))
    lignes.append(("texte", "Au {}".format(_date(derniere["date"], derniere["heure"]))))
    lignes.append(("texte", "Tickets n. {} a {}".format(premiere["id"], derniere["id"])))

    ca = sum(v["total"] for v in ventes)
    lignes.append(("titre", "VENTES"))
    lignes.append(("ligne", "Chiffre d'affaires TTC", _dh(ca)))
    lignes.append(("ligne", "Tickets", str(len(ventes))))
    lignes.append(("ligne", "Panier moyen", _dh(ca / len(ventes)) if ventes else "-"))

    # TVA par taux, recalculee ligne par ligne avec la remise du ticket
    par_taux, remises = {}, 0.0
    for v in ventes:
        facteur = 1 - (v["remise_pourcentage"] or 0) / 100
        for l in conn.execute("SELECT * FROM vente_lignes WHERE vente_id = ?", (v["id"],)):
            nominal = l["quantite"] * l["prix_unitaire"]
            ttc = nominal * facteur
            remises += nominal - ttc
            taux = l["taux_tva"] if l["taux_tva"] is not None else 0
            par_taux[taux] = par_taux.get(taux, 0) + ttc
    lignes.append(("titre", "TVA PAR TAUX"))
    total_ht = total_tva = 0.0
    for taux in sorted(par_taux):
        ttc = par_taux[taux]
        ht = ttc / (1 + taux / 100)
        total_ht += ht
        total_tva += ttc - ht
        lignes.append(("texte", "Taux {:g} %".format(taux)))
        lignes.append(("ligne", "  Base HT", _dh(ht)))
        lignes.append(("ligne", "  TVA", _dh(ttc - ht)))
        lignes.append(("ligne", "  TTC", _dh(ttc)))
    lignes.append(("ligne", "Total HT", _dh(total_ht)))
    lignes.append(("ligne", "Total TVA", _dh(total_tva)))
    if remises > 0.004:
        lignes.append(("ligne", "Remises accordees", _dh(remises)))

    lignes.append(("titre", "PAIEMENTS"))
    for mode, libelle in (("especes", "Especes"), ("carte", "Carte")):
        sel = [v for v in ventes if (v["mode_paiement"] or "especes") == mode]
        lignes.append(("ligne", "{} ({} t.)".format(libelle, len(sel)), _dh(sum(v["total"] for v in sel))))

    lignes.append(("titre", "SUR PLACE / A EMPORTER"))
    for mode, libelle in LIBELLES_MODE.items():
        sel = [v for v in ventes if v["mode_vente"] == mode]
        lignes.append(("ligne", "{} ({} t.)".format(libelle, len(sel)), _dh(sum(v["total"] for v in sel))))
    rapides = [v for v in ventes if v["type_vente"] == "rapide"]
    lignes.append(("ligne", "Ventes rapides ({})".format(len(rapides)), _dh(sum(v["total"] for v in rapides))))

    annulations = conn.execute("SELECT * FROM annulations").fetchall()
    lignes.append(("titre", "VENTES ANNULEES : {}".format(len(annulations))))
    for mode, libelle in (("especes", "Especes"), ("carte", "Carte")):
        sel = [a for a in annulations if (a["mode_paiement"] or "especes") == mode]
        if sel:
            lignes.append(("ligne", "{} ({})".format(libelle, len(sel)), _dh(sum(a["montant"] for a in sel))))

    par_vendeur = {}
    for v in ventes:
        nom = vendeurs.nom(conn, v["vendeur_id"]) or "(sans vendeur)"
        total, nb = par_vendeur.get(nom, (0, 0))
        par_vendeur[nom] = (total + v["total"], nb + 1)
    lignes.append(("titre", "PAR VENDEUR"))
    for nom, (total, nb) in sorted(par_vendeur.items()):
        lignes.append(("ligne", "{} ({} t.)".format(nom, nb), _dh(total)))

    sorties = conn.execute("SELECT * FROM sorties_especes").fetchall()
    depots = [s for s in sorties if s["type"] == caisse.TYPE_DEPOT_COFFRE]
    autres = [s for s in sorties if s["type"] != caisse.TYPE_DEPOT_COFFRE]
    ecarts = [r["ecart"] for r in conn.execute("SELECT ecart FROM releves WHERE ecart IS NOT NULL")]
    hors = [e for e in ecarts if not comptage.dans_tolerance(conn, e)]
    sans_vente = conn.execute("SELECT COUNT(*) AS n FROM journal_tiroir WHERE type = ?",
                              (tiroir.TYPE_SANS_VENTE,)).fetchone()["n"]
    coffre, nb_depots, _ = caisse.coffre_attendu(conn)
    lignes.append(("titre", "CAISSE"))
    lignes.append(("ligne", "Sorties d'especes", _dh(sum(s["montant"] for s in autres))))
    lignes.append(("ligne", "Depots coffre ({})".format(len(depots)), _dh(sum(d["montant"] for d in depots))))
    lignes.append(("ligne", "Coffre non releve", _dh(coffre)))
    lignes.append(("ligne", "Ecarts de caisse", "{:+.2f} DH".format(sum(ecarts))))
    lignes.append(("ligne", "Ecarts hors tolerance", str(len(hors))))
    lignes.append(("ligne", "Tiroir ouvert sans vente", str(sans_vente)))

    lignes.append(("titre", "REMISE A ZERO"))
    lignes.append(("texte", "Caisse videe apres impression"))
    lignes.append(("texte", "Imprime le {}".format(datetime.now().strftime("%d/%m/%Y %H:%M"))))
    return lignes


def effacer(conn, numero):
    """Efface DEFINITIVEMENT les donnees de la periode (pas de copie) et
    enregistre le numero de Z. VACUUM : les donnees disparaissent aussi
    physiquement du fichier caisse.db."""
    maintenant = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with conn:
        for table in TABLES_EFFACEES:
            conn.execute("DELETE FROM {}".format(table))
        conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES ('z_numero', ?)", (str(numero),))
        conn.execute("INSERT OR REPLACE INTO config (cle, valeur) VALUES ('z_dernier', ?)", (maintenant,))
    conn.execute("VACUUM")
