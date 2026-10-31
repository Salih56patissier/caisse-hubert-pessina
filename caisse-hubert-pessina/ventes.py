# -*- coding: utf-8 -*-
"""
Point d'entree UNIQUE pour enregistrer une vente en base, quel que soit le
mode (detaille produit par produit, ou vente rapide au montant).

Tout ce qui doit se passer a chaque vente (rattachement au vendeur,
ouverture du tiroir, file de synchronisation Google Sheets...) sera
branche ici, une seule fois, au lieu d'etre recopie dans chaque ecran.

Regle : une vente enregistree n'est JAMAIS modifiee ni supprimee. Seule
exception : le drapeau `annulee`, pose par annulations.annuler().
"""

from datetime import datetime

TYPE_DETAILLEE = "detaillee"
TYPE_RAPIDE = "rapide"


def enregistrer_vente(conn, lignes, mode_vente, mode_paiement, total_ht, total_tva, total_ttc,
                      remise_pourcentage=0, type_vente=TYPE_DETAILLEE, categorie_rapide=None,
                      vendeur_id=None, maintenant=None):
    """lignes : liste de dicts {nom, quantite, prix_unitaire, taux_tva}.
    Renvoie (vente_id, maintenant). Tout est ecrit dans une seule
    transaction : soit la vente complete est enregistree, soit rien."""
    maintenant = maintenant or datetime.now()
    with conn:
        curseur = conn.execute(
            "INSERT INTO ventes (date, heure, total, note, mode_vente, total_ht, total_tva, "
            "mode_paiement, remise_pourcentage, type_vente, categorie_rapide, vendeur_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (maintenant.strftime("%Y-%m-%d"), maintenant.strftime("%H:%M:%S"), total_ttc, None,
             mode_vente, total_ht, total_tva, mode_paiement, remise_pourcentage,
             type_vente, categorie_rapide, vendeur_id),
        )
        vente_id = curseur.lastrowid
        for ligne in lignes:
            # prix nominal (avant remise) : la remise n'est appliquee qu'au
            # niveau des totaux de la vente, pas ligne par ligne
            conn.execute(
                "INSERT INTO vente_lignes (vente_id, nom_produit, quantite, prix_unitaire, taux_tva) "
                "VALUES (?, ?, ?, ?, ?)",
                (vente_id, ligne["nom"], ligne["quantite"], ligne["prix_unitaire"], ligne["taux_tva"]),
            )
    return vente_id, maintenant


def taux_tva_vente_rapide(conn, nom_categorie, taux_mode_vente):
    """Taux de TVA applique a une vente rapide. Sans categorie : celui du
    mode de vente (Sur place / A emporter). Avec categorie : si TOUS les
    produits de la categorie ont la meme TVA fixe (ex: 0% sur tout le
    pain), on l'applique ; sinon on retombe sur le taux du mode de vente."""
    if not nom_categorie:
        return taux_mode_vente
    lignes = conn.execute(
        "SELECT p.tva_fixe FROM produits p JOIN categories c ON c.id = p.categorie_id WHERE c.nom = ?",
        (nom_categorie,),
    ).fetchall()
    taux = {ligne["tva_fixe"] for ligne in lignes}
    if len(taux) == 1:
        (unique,) = taux
        if unique is not None:
            return unique
    return taux_mode_vente


def preparer_vente_rapide(conn, montant, nom_categorie, mode_vente, taux_mode_vente):
    """Construit la ligne unique et les totaux d'une vente rapide.
    Renvoie (lignes, total_ht, total_tva, total_ttc, repartition_tva)."""
    taux = taux_tva_vente_rapide(conn, nom_categorie, taux_mode_vente)
    nom = "Vente rapide - {}".format(nom_categorie) if nom_categorie else "Vente rapide"
    total_ttc = round(float(montant), 2)
    total_ht = total_ttc / (1 + taux / 100)
    total_tva = total_ttc - total_ht
    lignes = [{"nom": nom, "quantite": 1, "prix_unitaire": total_ttc, "taux_tva": taux}]
    repartition = [{"taux": taux, "base_ht": total_ht, "montant": total_tva}]
    return lignes, total_ht, total_tva, total_ttc, repartition
