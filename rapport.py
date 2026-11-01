# -*- coding: utf-8 -*-
"""
Rapport de fin de journee (admin) : un resume imprimable sur l'imprimante
ticket, a tirer le soir. Contient les ecarts : ne jamais le proposer aux
vendeurs (il est accessible uniquement depuis l'Historique, protege par
le code admin).

Format des lignes renvoyees : ("titre", texte) | ("ligne", gauche, droite)
| ("texte", texte).
"""

from datetime import datetime

import annulations
import caisse
import comptage
import tiroir
import vendeurs


def _dh(x):
    return "{:.2f} DH".format(x or 0)


def construire(conn, date_texte):
    lignes = []
    ventes = conn.execute(
        "SELECT * FROM ventes WHERE date = ? AND COALESCE(annulee, 0) = 0", (date_texte,)
    ).fetchall()
    ca = sum(v["total"] for v in ventes)
    especes = sum(v["total"] for v in ventes if v["mode_paiement"] == "especes")
    carte = sum(v["total"] for v in ventes if v["mode_paiement"] == "carte")
    rapides = [v for v in ventes if v["type_vente"] == "rapide"]

    lignes.append(("titre", "VENTES"))
    lignes.append(("ligne", "Chiffre d'affaires", _dh(ca)))
    lignes.append(("ligne", "Tickets", str(len(ventes))))
    lignes.append(("ligne", "Panier moyen", _dh(ca / len(ventes)) if ventes else "-"))
    lignes.append(("ligne", "Especes", _dh(especes)))
    lignes.append(("ligne", "Carte", _dh(carte)))
    lignes.append(("ligne", "Ventes rapides ({})".format(len(rapides)), _dh(sum(v["total"] for v in rapides))))

    par_vendeur = {}
    for v in ventes:
        nom = vendeurs.nom(conn, v["vendeur_id"]) or "(sans vendeur)"
        total, nb = par_vendeur.get(nom, (0, 0))
        par_vendeur[nom] = (total + v["total"], nb + 1)
    if par_vendeur:
        lignes.append(("titre", "PAR VENDEUR"))
        for nom, (total, nb) in sorted(par_vendeur.items()):
            lignes.append(("ligne", "{} ({} t.)".format(nom, nb), _dh(total)))

    annulees = annulations.annulations_du_jour(conn, date_texte)
    lignes.append(("titre", "VENTES ANNULEES : {}".format(len(annulees))))
    for a in annulees:
        paiement = "carte" if a["mode_paiement"] == "carte" else "esp."
        lignes.append(("ligne", "{} {} {}".format(a["heure"][:5], vendeurs.nom(conn, a["vendeur_id"]) or "",
                                                 paiement), _dh(a["montant"])))
        detail = "  " + a["motif"]
        if a["par_admin"]:
            detail += " (admin)"
        if a["mode_paiement"] == "especes" and not a["rembourse_tiroir"]:
            detail += " - correction"
        lignes.append(("texte", detail))
    if annulees:
        lignes.append(("ligne", "Total annule", _dh(sum(a["montant"] for a in annulees))))

    sorties = caisse.sorties_du_jour(conn, date_texte)
    depots = [s for s in sorties if s["type"] == caisse.TYPE_DEPOT_COFFRE]
    autres = [s for s in sorties if s["type"] != caisse.TYPE_DEPOT_COFFRE]
    lignes.append(("titre", "DEPOTS COFFRE"))
    for d in depots:
        lignes.append(("ligne", "{} {}".format(d["heure"][:5], vendeurs.nom(conn, d["vendeur_id"]) or ""), _dh(d["montant"])))
    lignes.append(("ligne", "Total depots", _dh(sum(d["montant"] for d in depots))))
    lignes.append(("titre", "SORTIES D'ESPECES"))
    for so in autres:
        lignes.append(("ligne", "{} {}".format(so["heure"][:5], so["motif"]), _dh(so["montant"])))
    lignes.append(("ligne", "Total sorties", _dh(sum(so["montant"] for so in autres))))

    lignes.append(("titre", "COMPTAGES DU TIROIR"))
    releves = caisse.releves_du_jour(conn, date_texte)
    if not releves:
        lignes.append(("texte", "Aucun comptage"))
    for r in releves:
        nom = vendeurs.nom(conn, r["vendeur_id"]) or ""
        lignes.append(("texte", "{} {} - {}".format(r["heure"][:5], caisse.LIBELLES.get(r["type"], r["type"]), nom)))
        lignes.append(("ligne", "  Compte", _dh(r["montant_compte"])))
        if r["ecart"] is not None:
            lignes.append(("ligne", "  Attendu", _dh(r["attendu"])))
            alerte = "" if comptage.dans_tolerance(conn, r["ecart"]) else "  <<<"
            libelle = "  ECART PASSATION" if r["type"] == caisse.OUVERTURE else "  ECART POSTE"
            lignes.append(("ligne", libelle, "{:+.2f} DH{}".format(r["ecart"], alerte)))

    ouvertures = tiroir.journal_du_jour(conn, date_texte)
    lignes.append(("titre", "TIROIR OUVERT SANS VENTE : {}".format(len(ouvertures))))
    for e in reversed(ouvertures):
        lignes.append(("texte", "{} {} {}".format(e["heure"][:5], vendeurs.nom(conn, e["vendeur_id"]) or "",
                                                  e["motif"] or "")))

    attendu_coffre, nb_depots, _ = caisse.coffre_attendu(conn)
    lignes.append(("titre", "COFFRE"))
    lignes.append(("ligne", "Attendu ({} depots)".format(nb_depots), _dh(attendu_coffre)))
    lignes.append(("texte", "Imprime le {}".format(datetime.now().strftime("%d/%m/%Y %H:%M"))))
    return lignes
