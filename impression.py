# -*- coding: utf-8 -*-
"""
Impression des tickets de caisse sur l'imprimante thermique (protocole
ESC/POS, envoye en RAW au pilote Windows de l'imprimante via pywin32).

L'imprimante testee est une Gprinter GP-C80250I Plus (thermique 80mm, USB),
reconnue par Windows sous le nom 'GP-C80250 Series' - ce nom est stocke en
base (voir database.obtenir_nom_imprimante) et modifiable depuis le Mode
Admin si l'imprimante change, sans toucher au code.
"""

import time

import win32print

try:
    from PIL import Image
except ImportError:  # Pillow absent : on imprime simplement sans logo
    Image = None

NOM_COMMERCE = "Hubert & Pessina"
MESSAGE_REMERCIEMENT = "Merci de votre visite"
LARGEUR_TICKET = 42  # caracteres par ligne (police standard, ticket 80mm)
LARGEUR_LOGO_PIXELS_MAX = 384  # largeur d'image conseillee pour un ticket 80mm

ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"
ALIGN_GAUCHE = ESC + b"a" + b"\x00"
ALIGN_CENTRE = ESC + b"a" + b"\x01"
GRAS_ON = ESC + b"E" + b"\x01"
GRAS_OFF = ESC + b"E" + b"\x00"
DOUBLE_TAILLE_ON = GS + b"!" + b"\x11"
DOUBLE_TAILLE_OFF = GS + b"!" + b"\x00"
SAUT_LIGNES_FINAL = b"\n\n\n"
COUPE_PAPIER = GS + b"V" + b"\x01"
# Impulsion d'ouverture du tiroir-caisse branche sur le port RJ11 (DK) de
# l'imprimante : ESC p m t1 t2 -> broche 2 (m=0), 50 ms ON, 500 ms OFF.
# Rien n'est imprime, aucun papier consomme.
OUVRIR_TIROIR = ESC + b"p" + b"\x00" + b"\x19" + b"\xfa"

LIBELLES_PAIEMENT = {"especes": "Especes", "carte": "Carte"}
LIBELLES_MODE_VENTE = {"sur_place": "Sur place", "a_emporter": "A emporter"}


def _texte(chaine):
    return chaine.encode("cp437", errors="replace")


def _ligne_separatrice():
    return "-" * LARGEUR_TICKET


def _ligne_deux_colonnes(gauche, droite):
    """Aligne 'gauche' a gauche et 'droite' a droite sur la largeur du
    ticket ; tronque 'gauche' si les deux ne tiennent pas ensemble (nom de
    produit tres long)."""
    espace_disponible = LARGEUR_TICKET - len(droite)
    if espace_disponible < 1:
        return (gauche + " " + droite)[:LARGEUR_TICKET]
    return gauche[:espace_disponible - 1].ljust(espace_disponible) + droite


def _octets_logo(chemin_logo):
    """Convertit une image (PNG/JPEG, N&B ou couleur) en commande ESC/POS
    d'image raster (GS v 0). Renvoie None si aucune image n'est configuree,
    si Pillow n'est pas installe, ou si le fichier est illisible - dans
    tous ces cas le ticket s'imprime simplement sans logo plutot que de
    faire echouer toute l'impression."""
    if not chemin_logo or Image is None:
        return None
    try:
        image = Image.open(chemin_logo).convert("L")
        if image.width > LARGEUR_LOGO_PIXELS_MAX:
            ratio = LARGEUR_LOGO_PIXELS_MAX / image.width
            image = image.resize((LARGEUR_LOGO_PIXELS_MAX, max(1, int(image.height * ratio))))
        # seuillage simple noir/blanc : plus fiable qu'un dithering pour un
        # logo (traits nets) imprime sur une imprimante thermique
        image = image.point(lambda pixel: 255 if pixel >= 128 else 0)
        largeur, hauteur = image.size
        largeur_octets = (largeur + 7) // 8
        pixels = image.load()

        donnees_image = bytearray()
        for y in range(hauteur):
            octet, nb_bits = 0, 0
            for x in range(largeur):
                octet = (octet << 1) | (1 if pixels[x, y] == 0 else 0)
                nb_bits += 1
                if nb_bits == 8:
                    donnees_image.append(octet)
                    octet, nb_bits = 0, 0
            if nb_bits:
                octet <<= (8 - nb_bits)
                donnees_image.append(octet)

        en_tete = GS + b"v0" + b"\x00" + bytes([
            largeur_octets & 0xFF, (largeur_octets >> 8) & 0xFF,
            hauteur & 0xFF, (hauteur >> 8) & 0xFF,
        ])
        return en_tete + bytes(donnees_image)
    except Exception:
        return None


def _construire_ticket_octets(lignes_vente, mode_vente, mode_paiement, repartition_tva,
                               total_ht, total_tva, total_ttc, date_heure, chemin_logo=None,
                               remise_pourcentage=0):
    donnees = bytearray()
    donnees += INIT

    donnees += ALIGN_CENTRE
    octets_logo = _octets_logo(chemin_logo)
    if octets_logo:
        donnees += octets_logo
        donnees += b"\n"

    donnees += DOUBLE_TAILLE_ON + GRAS_ON
    donnees += _texte(NOM_COMMERCE + "\n")
    donnees += DOUBLE_TAILLE_OFF + GRAS_OFF
    donnees += _texte(date_heure + "\n")
    donnees += _texte(LIBELLES_MODE_VENTE.get(mode_vente, mode_vente) + "\n")
    donnees += _texte(_ligne_separatrice() + "\n")

    donnees += ALIGN_GAUCHE
    for ligne in lignes_vente:
        quantite, prix_unitaire = ligne["quantite"], ligne["prix_unitaire"]
        sous_total = quantite * prix_unitaire
        donnees += _texte(ligne["nom"] + "\n")
        detail_gauche = "{:g} x {:g} DH".format(quantite, prix_unitaire)
        detail_droite = "{:g} DH".format(sous_total)
        donnees += _texte(_ligne_deux_colonnes(detail_gauche, detail_droite) + "\n")

    donnees += _texte(_ligne_separatrice() + "\n")
    if remise_pourcentage:
        donnees += _texte(_ligne_deux_colonnes("Remise", "-{:g}%".format(remise_pourcentage)) + "\n")
    donnees += _texte(_ligne_deux_colonnes("Total HT", "{:.2f} DH".format(total_ht)) + "\n")
    for groupe in repartition_tva:
        libelle = "TVA {:g}%".format(groupe["taux"])
        donnees += _texte(_ligne_deux_colonnes(libelle, "{:.2f} DH".format(groupe["montant"])) + "\n")
    donnees += _texte(_ligne_separatrice() + "\n")

    donnees += DOUBLE_TAILLE_ON + GRAS_ON
    donnees += _texte(_ligne_deux_colonnes("TOTAL", "{:.2f} DH".format(total_ttc)) + "\n")
    donnees += DOUBLE_TAILLE_OFF + GRAS_OFF

    donnees += _texte(_ligne_separatrice() + "\n")
    donnees += _texte("Paiement : {}\n".format(LIBELLES_PAIEMENT.get(mode_paiement, mode_paiement)))

    donnees += ALIGN_CENTRE
    donnees += _texte("\n" + MESSAGE_REMERCIEMENT + "\n")

    donnees += SAUT_LIGNES_FINAL
    donnees += COUPE_PAPIER
    return bytes(donnees)


# Documents envoyes par la caisse (pour ne purger QUE les notres dans la
# file d'attente Windows, jamais ceux d'un autre logiciel).
NOMS_DOCUMENTS_CAISSE = ("Ticket de caisse", "Ouverture tiroir")

# Temps laisse a l'imprimante pour avaler un envoi. Au-dela, on considere
# qu'elle est eteinte/debranchee et on SUPPRIME l'envoi de la file Windows :
# sinon Windows le garde et l'imprime (ou ouvre le tiroir) plus tard, des
# qu'on rallume l'imprimante - tous les tickets cliques par erreur sortiraient.
DELAI_ENVOI_SECONDES = 3.0
JOB_CONTROL_DELETE = getattr(win32print, "JOB_CONTROL_DELETE", 5)
JOB_STATUS_TERMINE = 0x80 | 0x100 | 0x1000  # PRINTED | DELETED | COMPLETE


class ImprimanteInjoignable(Exception):
    pass


def _travaux_caisse_en_attente(handle):
    try:
        travaux = win32print.EnumJobs(handle, 0, 999, 1)
    except Exception:
        return []
    return [t for t in travaux
            if t.get("pDocument") in NOMS_DOCUMENTS_CAISSE and not (t.get("Status", 0) & JOB_STATUS_TERMINE)]


def _supprimer_travail(handle, job_id):
    try:
        win32print.SetJob(handle, job_id, 0, None, JOB_CONTROL_DELETE)
    except Exception:
        pass


def purger_file_attente(nom_imprimante):
    """Supprime de la file Windows tous les envois de la caisse restes
    bloques (imprimante eteinte). A appeler au demarrage et avant chaque
    envoi. Ne leve jamais d'exception."""
    try:
        handle = win32print.OpenPrinter(nom_imprimante)
    except Exception:
        return
    try:
        for travail in _travaux_caisse_en_attente(handle):
            _supprimer_travail(handle, travail["JobId"])
    finally:
        win32print.ClosePrinter(handle)


def _envoyer_brut(nom_imprimante, donnees, nom_document):
    """Envoie des octets ESC/POS bruts. Si l'imprimante ne les a pas pris
    en DELAI_ENVOI_SECONDES, l'envoi est annule (retire de la file) et
    ImprimanteInjoignable est levee : rien ne sortira plus tard."""
    purger_file_attente(nom_imprimante)
    handle = win32print.OpenPrinter(nom_imprimante)
    try:
        job_id = win32print.StartDocPrinter(handle, 1, (nom_document, None, "RAW"))
        try:
            win32print.StartPagePrinter(handle)
            win32print.WritePrinter(handle, donnees)
            win32print.EndPagePrinter(handle)
        finally:
            win32print.EndDocPrinter(handle)

        limite = time.monotonic() + DELAI_ENVOI_SECONDES
        while True:
            en_attente = [t for t in _travaux_caisse_en_attente(handle) if t["JobId"] == job_id]
            if not en_attente:
                return
            if time.monotonic() >= limite:
                _supprimer_travail(handle, job_id)
                raise ImprimanteInjoignable("Imprimante eteinte ou debranchee : envoi annule.")
            time.sleep(0.15)
    finally:
        win32print.ClosePrinter(handle)


def ouvrir_tiroir(nom_imprimante):
    """Envoie uniquement l'impulsion d'ouverture du tiroir (aucune
    impression). Leve une exception si l'imprimante est introuvable."""
    _envoyer_brut(nom_imprimante, INIT + OUVRIR_TIROIR, "Ouverture tiroir")


def imprimer_ticket(nom_imprimante, lignes_vente, mode_vente, mode_paiement, repartition_tva,
                     total_ht, total_tva, total_ttc, date_heure, chemin_logo=None,
                     remise_pourcentage=0):
    """Envoie le ticket a l'imprimante Windows nommee `nom_imprimante`, en
    mode RAW (les octets ESC/POS sont transmis tels quels au peripherique,
    sans passer par le rendu graphique du pilote). Leve une exception
    (a charge de l'appelant de l'afficher) si l'imprimante est injoignable
    ou introuvable - ne doit jamais faire planter la caisse."""
    donnees = _construire_ticket_octets(
        lignes_vente, mode_vente, mode_paiement, repartition_tva,
        total_ht, total_tva, total_ttc, date_heure, chemin_logo=chemin_logo,
        remise_pourcentage=remise_pourcentage,
    )

    _envoyer_brut(nom_imprimante, donnees, "Ticket de caisse")


def imprimer_rapport(nom_imprimante, titre, lignes):
    """Ticket texte simple (rapport du jour). `lignes` : voir rapport.py."""
    donnees = bytearray()
    donnees += INIT + ALIGN_CENTRE + DOUBLE_TAILLE_ON + GRAS_ON
    donnees += _texte(NOM_COMMERCE + "\n")
    donnees += DOUBLE_TAILLE_OFF
    donnees += _texte(titre + "\n")
    donnees += GRAS_OFF + ALIGN_GAUCHE
    for ligne in lignes:
        if ligne[0] == "titre":
            donnees += _texte(_ligne_separatrice() + "\n")
            donnees += GRAS_ON + _texte(ligne[1] + "\n") + GRAS_OFF
        elif ligne[0] == "ligne":
            donnees += _texte(_ligne_deux_colonnes(ligne[1], ligne[2]) + "\n")
        else:
            donnees += _texte(ligne[1][:LARGEUR_TICKET] + "\n")
    donnees += SAUT_LIGNES_FINAL + COUPE_PAPIER
    _envoyer_brut(nom_imprimante, bytes(donnees), "Ticket de caisse")
