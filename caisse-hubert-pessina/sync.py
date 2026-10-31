# -*- coding: utf-8 -*-
"""
Synchronisation vers Google Sheets (consultable sur telephone).

Principe (fonctionne sans internet) :
- rien n'est jamais bloque par la synchro : la caisse enregistre tout en
  local (caisse.db), comme avant ;
- un fil en arriere-plan envoie toutes les 60 s les NOUVELLES lignes de
  chaque table a un script Google (Apps Script, voir
  google_apps_script.txt) qui les ajoute dans la feuille ;
- pour chaque table on retient le dernier id envoye avec succes. Sans
  connexion, l'envoi echoue et sera simplement retente plus tard : rien
  n'est perdu. Le script ignore les lignes deja presentes (meme id), donc
  un double envoi ne cree pas de doublon.

Reglages (Mode Admin) : adresse du script + code secret partage.
"""

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

import comptage
import database
import vendeurs

INTERVALLE_SECONDES = 60
TAILLE_LOT = 50  # petits paquets : Google repond avant le delai
# Google (Apps Script) met souvent 15 a 30 s a repondre, meme pour un
# petit envoi : un delai trop court faisait croire a un echec alors que
# les lignes etaient bien arrivees (renvoyees ensuite pour rien).
DELAI_RESEAU = 120

ETAT = {"message": "Pas encore synchronise", "ok": None, "heure": None, "en_attente": 0}
_verrou = threading.Lock()
_reveil = threading.Event()


# ---------------------------------------------------------------------------
# Reglages
# ---------------------------------------------------------------------------
FICHIER_REGLAGES = os.path.join(os.path.dirname(database.DB_PATH), "google_sheets.json")


def _fichier():
    """Reglages fournis dans google_sheets.json (a cote de caisse.db) :
    evite d'avoir a recopier l'adresse et le code a la main. Les reglages
    faits dans le Mode Admin restent prioritaires."""
    try:
        with open(FICHIER_REGLAGES, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def url(conn):
    return database.obtenir_config_texte(conn, "gsheet_url", "") or _fichier().get("url", "")


def definir_url(conn, valeur):
    database.definir_config_texte(conn, "gsheet_url", valeur.strip())


def jeton(conn):
    """Code secret partage avec le script Google (genere une fois)."""
    valeur = database.obtenir_config_texte(conn, "gsheet_jeton", "") or _fichier().get("jeton", "")
    if not valeur:
        valeur = secrets.token_hex(4).upper()
        database.definir_config_texte(conn, "gsheet_jeton", valeur)
    return valeur


def active(conn):
    """Active par defaut des que google_sheets.json fournit une adresse ;
    le bouton Activer/Desactiver de l'admin a toujours le dernier mot."""
    reglage = database.obtenir_config_texte(conn, "gsheet_actif", "")
    if reglage:
        return reglage == "1"
    return bool(_fichier().get("url"))


def definir_active(conn, actif):
    database.definir_config_texte(conn, "gsheet_actif", "1" if actif else "0")


def _dernier_id(conn, table):
    try:
        return int(database.obtenir_config_texte(conn, "gsheet_dernier_" + table, "0"))
    except ValueError:
        return 0


def _definir_dernier_id(conn, table, valeur):
    database.definir_config_texte(conn, "gsheet_dernier_" + table, str(valeur))


# ---------------------------------------------------------------------------
# Construction des lignes (1re colonne = id, pour eviter les doublons)
# ---------------------------------------------------------------------------
def _nom(conn, vendeur_id):
    return vendeurs.nom(conn, vendeur_id) or ""


def _lignes_ventes(conn, depuis):
    lignes = []
    for v in conn.execute("SELECT * FROM ventes WHERE id > ? ORDER BY id LIMIT ?", (depuis, TAILLE_LOT)):
        detail = "; ".join(
            "{:g}x {}".format(l["quantite"], l["nom_produit"])
            for l in conn.execute("SELECT * FROM vente_lignes WHERE vente_id = ? ORDER BY id", (v["id"],))
        )
        lignes.append([v["id"], v["date"], v["heure"], _nom(conn, v["vendeur_id"]),
                       v["type_vente"] or "detaillee", v["mode_paiement"] or "", v["mode_vente"] or "",
                       v["total"], round(v["total_ht"] or 0, 2), round(v["total_tva"] or 0, 2),
                       v["remise_pourcentage"] or 0, v["categorie_rapide"] or "", detail,
                       "ANNULEE" if v["annulee"] else ""])
    return lignes


def _lignes_comptages(conn, depuis):
    import caisse
    lignes = []
    for r in conn.execute("SELECT * FROM releves WHERE id > ? ORDER BY id LIMIT ?", (depuis, TAILLE_LOT)):
        ecart = r["ecart"]
        lignes.append([r["id"], r["date"], r["heure"], caisse.LIBELLES.get(r["type"], r["type"]),
                       _nom(conn, r["vendeur_id"]), _nom(conn, r["compte_par_id"]), r["montant_compte"],
                       "" if r["attendu"] is None else r["attendu"], "" if ecart is None else ecart,
                       "" if ecart is None else ("oui" if comptage.dans_tolerance(conn, ecart) else "NON"),
                       comptage.resume_details(conn, r["id"]), r["note"] or ""])
    return lignes


def _lignes_sorties(conn, depuis):
    return [[s["id"], s["date"], s["heure"], "Depot coffre" if s["type"] == "depot_coffre" else "Sortie",
             _nom(conn, s["vendeur_id"]), s["motif"], s["montant"]]
            for s in conn.execute("SELECT * FROM sorties_especes WHERE id > ? ORDER BY id LIMIT ?",
                                  (depuis, TAILLE_LOT))]


def _lignes_tiroir(conn, depuis):
    return [[t["id"], t["date"], t["heure"], t["type"], _nom(conn, t["vendeur_id"]), t["motif"] or "",
             t["resultat"], t["vente_id"] or ""]
            for t in conn.execute("SELECT * FROM journal_tiroir WHERE id > ? ORDER BY id LIMIT ?",
                                  (depuis, TAILLE_LOT))]


def _lignes_coffre(conn, depuis):
    return [[c["id"], c["date"], c["heure"], c["montant_compte"], c["attendu"], c["ecart"], c["nb_depots"]]
            for c in conn.execute("SELECT * FROM releves_coffre WHERE id > ? ORDER BY id LIMIT ?",
                                  (depuis, TAILLE_LOT))]


def _lignes_annulations(conn, depuis):
    return [[a["id"], a["date"], a["heure"], a["vente_id"], _nom(conn, a["vendeur_id"]), a["montant"],
             a["mode_paiement"] or "", a["motif"], "oui" if a["par_admin"] else "non",
             ("oui" if a["rembourse_tiroir"] else "non") if a["mode_paiement"] == "especes" else "-"]
            for a in conn.execute("SELECT * FROM annulations WHERE id > ? ORDER BY id LIMIT ?",
                                  (depuis, TAILLE_LOT))]


# (table locale, nom de l'onglet Google, fonction)
TABLES = [
    ("ventes", "Ventes", _lignes_ventes),
    ("releves", "Comptages", _lignes_comptages),
    ("sorties_especes", "Sorties", _lignes_sorties),
    ("journal_tiroir", "Tiroir", _lignes_tiroir),
    ("releves_coffre", "Coffre", _lignes_coffre),
    ("annulations", "Annulations", _lignes_annulations),
]


# tables dont l'envoi n'est considere reussi que si la reponse du script
# a ete lue (un ancien script refuserait l'onglet sans qu'on le sache)
TABLES_A_CONFIRMER = {"annulations"}


def lignes_en_attente(conn):
    total = 0
    for table, _, _ in TABLES:
        total += conn.execute("SELECT COUNT(*) AS n FROM {} WHERE id > ?".format(table),
                              (_dernier_id(conn, table),)).fetchone()["n"]
    return total


# ---------------------------------------------------------------------------
# Envoi
# ---------------------------------------------------------------------------
class _PasDeRedirection(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None  # on gere nous-memes la redirection de Google


_ouvreur = urllib.request.build_opener(_PasDeRedirection)
DELAI_LECTURE_REPONSE = 20


def _poster(adresse, contenu):
    """Envoi en 2 temps, adapte au fonctionnement de Google Apps Script :
    1) POST vers /exec : Google execute le script (ajout des lignes) PUIS
       repond par une redirection (302) vers la page de resultat ;
    2) lecture de cette page de resultat (souvent tres lente, parfois
       bloquee cote Google).
    Recevoir le 302 prouve que le script a fini de s'executer : si la
    lecture du resultat traine, on considere l'envoi reussi (le script
    ignore de toute facon les doublons si on renvoie). Seul un refus
    explicite (code secret faux...) est traite comme une erreur."""
    donnees = json.dumps(contenu).encode("utf-8")
    requete = urllib.request.Request(adresse, data=donnees, headers={"Content-Type": "application/json"})
    try:
        with _ouvreur.open(requete, timeout=DELAI_RESEAU) as reponse:
            return json.loads(reponse.read().decode("utf-8"))  # reponse directe (rare)
    except urllib.error.HTTPError as err:
        if err.code not in (301, 302, 303, 307, 308):
            raise
        destination = err.headers.get("Location")
    if not destination:
        return {"ok": True, "note": "execute (pas de page de resultat)"}
    try:
        with urllib.request.urlopen(destination, timeout=DELAI_LECTURE_REPONSE) as reponse:
            return json.loads(reponse.read().decode("utf-8"))
    except Exception:
        return {"ok": True, "note": "execute (resultat non lu)"}


def synchroniser(conn):
    """Envoie tout ce qui est en attente. Renvoie (ok, message)."""
    adresse = url(conn)
    if not adresse:
        return False, "Adresse du script Google non renseignee"
    code = jeton(conn)
    envoyees = 0
    onglets_inconnus = []
    for table, onglet, construire in TABLES:
        while True:
            depuis = _dernier_id(conn, table)
            lignes = construire(conn, depuis)
            if not lignes:
                break
            try:
                reponse = _poster(adresse, {"jeton": code, "onglet": onglet, "lignes": lignes})
            except Exception as exc:  # pas d'internet, Google trop lent...
                # les paquets deja envoyes dans ce passage sont acquis : le
                # journal doit le dire, sinon il affiche une fausse panne
                if envoyees:
                    return False, "{} ligne(s) envoyee(s), puis coupure ({}) - {} en attente".format(
                        envoyees, str(exc)[:80], lignes_en_attente(conn))
                return False, "Pas de connexion ({}) - {} en attente".format(
                    str(exc)[:80], lignes_en_attente(conn))
            if not reponse.get("ok"):
                if reponse.get("erreur") == "onglet inconnu":
                    # script Google pas encore mis a jour pour ce nouvel
                    # onglet : on garde ces lignes en attente, les autres
                    # tables continuent d'etre envoyees
                    onglets_inconnus.append(onglet)
                    break
                return False, "Refuse par Google : {}".format(reponse.get("erreur", "?"))
            if table in TABLES_A_CONFIRMER and "ajoutees" not in reponse:
                # reponse de Google non lue : impossible de savoir si le
                # script connait deja cet onglet -> on renverra plus tard
                # (pas de doublon possible, le script ignore les id deja la)
                break
            _definir_dernier_id(conn, table, lignes[-1][0])
            envoyees += len(lignes)
    if onglets_inconnus:
        return False, "{} ligne(s) envoyee(s) ; script Google a mettre a jour (onglet {})".format(
            envoyees, ", ".join(onglets_inconnus))
    return True, "{} ligne(s) envoyee(s)".format(envoyees)


def lancer_une_fois():
    """Une synchro complete, avec sa propre connexion (appelable depuis
    n'importe quel fil). Met a jour ETAT."""
    with _verrou:
        conn = database.get_connection()
        try:
            if not active(conn):
                ETAT.update(message="Synchronisation desactivee", ok=None)
                return
            try:
                ok, message = synchroniser(conn)
            except Exception as exc:  # pas d'internet, Google injoignable...
                ok, message = False, "Pas de connexion ({})".format(str(exc)[:80])
            _journaliser(message)
            ETAT.update(message=message, ok=ok, heure=datetime.now().strftime("%H:%M"),
                        en_attente=lignes_en_attente(conn))
        finally:
            conn.close()


FICHIER_JOURNAL = os.path.join(os.path.dirname(database.DB_PATH), "synchro_google.log")


def _journaliser(message):
    """Garde les 200 derniers resultats de synchro (diagnostic a distance)."""
    try:
        lignes = []
        if os.path.exists(FICHIER_JOURNAL):
            with open(FICHIER_JOURNAL, encoding="utf-8") as f:
                lignes = f.read().splitlines()[-199:]
        lignes.append("{}  {}".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message))
        with open(FICHIER_JOURNAL, "w", encoding="utf-8") as f:
            f.write("\n".join(lignes) + "\n")
    except OSError:
        pass


def demander_synchro():
    """Reveille le fil de synchro tout de suite (bouton admin)."""
    _reveil.set()


def demarrer():
    """A appeler une fois au lancement de la caisse."""
    def boucle():
        time.sleep(5)
        while True:
            try:
                lancer_une_fois()
            except Exception:
                pass
            _reveil.wait(INTERVALLE_SECONDES)
            _reveil.clear()

    threading.Thread(target=boucle, name="synchro-google", daemon=True).start()
