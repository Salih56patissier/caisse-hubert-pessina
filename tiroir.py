# -*- coding: utf-8 -*-
"""
Tiroir-caisse : ouverture + journal.

Regles :
- le tiroir ne s'ouvre qu'apres une vente payee en ESPECES (une vente
  carte n'a pas besoin du tiroir), ou via "Ouvrir sans vente" avec un
  motif obligatoire ;
- CHAQUE ouverture (reussie ou non) est ecrite dans journal_tiroir, avec
  l'heure, le type, le motif et (bientot) le vendeur connecte.
"""

import threading
from datetime import datetime

import database
import impression

TYPE_VENTE = "vente"
TYPE_SANS_VENTE = "sans_vente"
TYPE_TEST = "test"
TYPE_RELEVE = "releve"   # ouverture pour compter (fond, changement, fermeture)
TYPE_SORTIE = "sortie"   # sortie d'especes (fournisseur...)
TYPE_ANNULATION = "annulation"  # argent rendu au client (vente especes annulee)

MOTIFS_SANS_VENTE = ["Rendu monnaie", "Erreur", "Autre"]


def tiroir_actif(conn):
    return database.obtenir_config_texte(conn, "tiroir_actif", "1") == "1"


def definir_tiroir_actif(conn, actif):
    database.definir_config_texte(conn, "tiroir_actif", "1" if actif else "0")


def ouvrir(conn, type_ouverture, motif=None, vente_id=None, vendeur_id=None):
    """Ouvre le tiroir (si active dans l'admin) et journalise.
    Renvoie (ok, message_erreur_ou_None). Ne leve jamais d'exception : un
    probleme d'imprimante ne doit jamais bloquer ni annuler une vente."""
    if not tiroir_actif(conn):
        resultat, ok, erreur = "desactive", True, None
    else:
        try:
            impression.ouvrir_tiroir(database.obtenir_nom_imprimante(conn))
            resultat, ok, erreur = "ok", True, None
        except Exception as exc:  # imprimante eteinte, debranchee, mal nommee...
            erreur = str(exc)
            resultat, ok = "erreur : {}".format(erreur)[:200], False

    maintenant = datetime.now()
    try:
        with conn:
            conn.execute(
                "INSERT INTO journal_tiroir (date, heure, type, motif, vente_id, vendeur_id, resultat) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (maintenant.strftime("%Y-%m-%d"), maintenant.strftime("%H:%M:%S"),
                 type_ouverture, motif, vente_id, vendeur_id, resultat),
            )
    except Exception:
        pass
    return ok, erreur


def journal_du_jour(conn, date_texte, types=(TYPE_SANS_VENTE, TYPE_TEST)):
    marques = ",".join("?" for _ in types)
    return conn.execute(
        "SELECT * FROM journal_tiroir WHERE date = ? AND type IN ({}) ORDER BY heure DESC".format(marques),
        (date_texte,) + tuple(types),
    ).fetchall()


def ouvrir_en_fond(type_ouverture, motif=None, vente_id=None, vendeur_id=None):
    """Meme chose qu'ouvrir(), mais dans un fil a part avec sa propre
    connexion : quand l'imprimante est eteinte (cas normal au magasin),
    l'envoi attend 3 s avant d'etre annule ; la caisse ne doit pas rester
    figee pendant ce temps. Le resultat est seulement note dans le journal."""
    def travail():
        try:
            conn = database.get_connection()
            try:
                ouvrir(conn, type_ouverture, motif=motif, vente_id=vente_id, vendeur_id=vendeur_id)
            finally:
                conn.close()
        except Exception:
            pass
    threading.Thread(target=travail, name="tiroir", daemon=True).start()
