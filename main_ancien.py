# -*- coding: utf-8 -*-
"""
Etape 3 : ecran de caisse + pave numerique de quantite pour "Hubert & Pessina".

- Clic normal sur une tuile (produit simple ou parfum) = +1 unite.
- Petit badge "123" dans le coin de la tuile = ouvre le pave numerique pour
  ajouter une quantite precise en un seul coup.

Pas encore de mode admin / historique (etapes 4 et 5).
"""

import math
import os
import sys
import unicodedata
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import database
import impression
import ventes
import tiroir
import dialogues
import vendeurs
import caisse
import comptage
import sync
import gestion_ventes
import remise_a_zero
from connexion import EcranConnexion
from ecran_comptage import EcranComptage
from admin import FenetreAdmin
from historique import FenetreHistorique, FenetreRecap
from pave_numerique import PaveNumerique
from vente_rapide import AJOUT_TICKET, FenetreVenteRapide
from styles import (
    BLANC, BRUN_200, BRUN_300, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROSE, ROUGE, VERT, COULEURS_CATEGORIES,
    HEADER_DEGRADE_GAUCHE, HEADER_DEGRADE_DROITE, POLICE_BADGE, POLICE_CATEGORIE, POLICE_CATEGORIE_CAISSE,
    POLICE_ENCAISSER, POLICE_PRODUIT_HINT, POLICE_PRODUIT_NOM, POLICE_PRODUIT_PRIX,
    POLICE_SOUS_TITRE, POLICE_TICKET_DETAIL, POLICE_TICKET_NOM, POLICE_TICKET_TITRE,
    POLICE_TITRE, POLICE_TOTAL, POLICE_BOUTON_ROND,
    FRAMBOISE, FRAMBOISE_FONCE, ROSE_PALE, VERT_CLAIR, BORDURE_CARTE, FOND_SEGMENT,
    BoutonArrondi, Carte, Segments, ScrollableFrame, rectangle_arrondi, photo_entete, photo_pastille,
    definir_dpi_awareness, diagnostiquer_ecran, zone_travail_windows,
    calculer_grille_adaptative, police_echelle, police_ajustee_a_largeur,
    polices_ajustees_a_hauteur, largeur_texte, texte_dans_boite, HAUTEUR_PIED_TUILE,
)

# A incrementer a chaque changement visible de l'ecran de caisse : s'affiche
# dans le titre de la fenetre pour verifier sans ambiguite, en cas de doute,
# que la version testee sur un poste est bien la derniere (et pas un ancien
# .exe reste sur le PC).
VERSION_APP = "V2 - 2026-10-24.27 (interface modernisee)"

# Pictogrammes des pastilles de categories : traits blancs sur fond
# transparent (icones_categories/traits, a cote de caisse.db), poses sur
# une pastille de la couleur de la categorie. Categorie sans correspondance
# -> pastille avec son initiale, couleur prise dans COULEURS_CATEGORIES.
DOSSIER_ICONES_CATEGORIES = os.path.join(os.path.dirname(database.DB_PATH), "icones_categories", "traits")
ICONES_CATEGORIES = {
    "Pain": "pain.png",
    "Viennoiserie": "viennoiserie.png",
    "Sablé": "sable.png",
    "Tarte": "tarte.png",
    "Patisserie": "patisserie.png",
    "Salé": "sale.png",
    "Evenement": "evenement.png",
    "Divers": "divers.png",
    "Boissons": "boissons.png",
}
# Couleur fixe par categorie (reste la meme si l'ordre change dans l'admin)
COULEURS_PAR_CATEGORIE = {
    "Pain": "#c8892b",          # ble
    "Viennoiserie": "#e07b39",  # croissant dore
    "Tarte": "#d64550",         # framboise
    "Sablé": "#a0673c",         # biscuit
    "Salé": "#5b9a4c",          # herbes
    "Patisserie": "#e75480",    # rose de la maison
    "Divers": "#8e5ba6",        # violet
    "Boissons": "#3b86c4",      # bleu
    "Evenement": "#2f9e94",     # sarcelle
}
ICONE_VENTE_RAPIDE = "rapide.png"


def _normaliser_nom_categorie(nom):
    """Enleve accents/casse pour comparer les noms de facon tolerante :
    le nom d'une categorie est libre (saisi dans le Mode Admin, souvent au
    pluriel - "Tartes", "Sables"...) alors que ICONES_CATEGORIES ci-dessus
    liste des noms figes (souvent au singulier) - une correspondance exacte
    ratait donc la plupart des categories reelles du magasin."""
    sans_accents = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode("ascii")
    return sans_accents.strip().lower()


def _correspondance_categorie(nom_categorie, table):
    cible = _normaliser_nom_categorie(nom_categorie)
    for nom_cle, valeur in table.items():
        cle = _normaliser_nom_categorie(nom_cle)
        if cible == cle or cible.startswith(cle) or cle.startswith(cible):
            return valeur
    return None


def _chemin_icone_categorie(nom_categorie):
    nom_fichier = _correspondance_categorie(nom_categorie, ICONES_CATEGORIES)
    if nom_fichier is None:
        return None
    chemin = os.path.join(DOSSIER_ICONES_CATEGORIES, nom_fichier)
    return chemin if os.path.isfile(chemin) else None


def _couleur_categorie(nom_categorie, index):
    return (_correspondance_categorie(nom_categorie, COULEURS_PAR_CATEGORIE)
            or COULEURS_CATEGORIES[index % len(COULEURS_CATEGORIES)])


def _dossier_application():
    """Dossier ou se trouve le programme : celui de l'executable une fois
    empaquete (PyInstaller), celui du fichier source sinon. Sert a retrouver
    les fichiers a cote du programme (logo, logs...) quel que soit le dossier
    depuis lequel il est lance."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# Taille de fenetre adaptee a la zone de travail reelle du poste (hors barre
# des taches), plafonnee a une taille raisonnable : jamais plus grande que
# necessaire meme sur un grand ecran, mais reduite automatiquement sur un
# petit ecran (ex: 1024x768 constate en magasin) au lieu de deborder.
# Fixe une fois calculee (pas de minsize : c'est un minsize trop grand,
# ajoute plus tot, qui avait deja annule silencieusement un premier essai
# de dimensionnement automatique).
LARGEUR_FENETRE_MAX = 950
HAUTEUR_FENETRE_MAX = 680
MARGE_SECURITE_ECRAN = 20  # px retires a la zone de travail detectee, par prudence


class CaisseApp(tk.Tk):
    LARGEUR_ZONE_TICKET = 500  # panneau de droite (ticket) ; le reste va aux categories/produits

    def __init__(self):
        super().__init__()
        self.title("Hubert & Pessina - Caisse [{}]".format(VERSION_APP))
        self.iconbitmap("logo.ico")
        self.configure(bg=CREME)

        x_ecran, y_ecran, largeur_ecran, hauteur_ecran = zone_travail_windows()
        if largeur_ecran <= 0 or hauteur_ecran <= 0:
            # Detection indisponible/anormale : on retombe sur le plafond,
            # positionne en haut a gauche de l'ecran principal.
            x_ecran, y_ecran = 0, 0
            largeur_ecran, hauteur_ecran = LARGEUR_FENETRE_MAX, HAUTEUR_FENETRE_MAX

        largeur = min(largeur_ecran - MARGE_SECURITE_ECRAN, LARGEUR_FENETRE_MAX)
        hauteur = min(hauteur_ecran - MARGE_SECURITE_ECRAN, HAUTEUR_FENETRE_MAX)
        x = x_ecran + max((largeur_ecran - largeur) // 2, 0)
        y = y_ecran + max((hauteur_ecran - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))

        # Redimensionnable + bouton Maximiser actif : sur Windows, une fois
        # la fenetre redimensionnable, "Maximiser" agrandit nativement a la
        # taille reelle de l'ecran sur lequel elle se trouve a cet instant
        # (gere par Windows lui-meme, correct quel que soit le poste/moniteur).
        # minsize empeche de la reduire au point de casser l'affichage.
        self.resizable(True, True)
        self.minsize(700, 500)

        self.conn = database.get_connection()

        # TVA : taux configures (Sur place / A emporter) + mode de vente
        # choisi pour le ticket en cours (persiste d'une vente a l'autre,
        # pour ne pas avoir a re-choisir a chaque client si plusieurs
        # ventes du meme type se suivent).
        self.taux_tva = database.obtenir_taux_tva(self.conn)
        self.mode_vente = "a_emporter"

        # etat de l'ecran de caisse
        self.categorie_active_id = None
        self.produit_sous_menu_actif = None  # dict produit si on affiche ses parfums

        # ticket en cours : liste de dicts {nom, prix_unitaire, quantite, tva_fixe}
        self.ticket = []
        # remise globale (%) sur le ticket en cours (ex: prix de gros pour
        # un client) ; remise a zero apres chaque vente encaissee
        self.remise_pourcentage = 0

        # dernier ticket encaisse : conserve pour permettre une reimpression
        # a tout moment (bourrage papier, client qui redemande son ticket
        # apres coup...), y compris apres un redemarrage du logiciel - dans
        # ce cas on retrouve la derniere vente depuis la base au demarrage.
        self._dernier_ticket = None
        self._charger_dernier_ticket_depuis_db()

        self._construire_interface()
        self._rafraichir_ecran()

        # Vendeur connecte (ligne de la table vendeurs) et sa connexion en
        # cours. Personne n'est connecte au demarrage : l'ecran de code
        # recouvre la caisse jusqu'a ce qu'un vendeur tape son PIN.
        self.vendeur = None
        self.connexion_id = None
        vendeurs.fermer_connexions_orphelines(self.conn)
        # tickets / ouvertures de tiroir restes bloques dans Windows (ex:
        # imprimante eteinte avant la V2) : supprimes pour qu'ils ne sortent
        # pas d'un coup au prochain allumage
        impression.purger_file_attente(database.obtenir_nom_imprimante(self.conn))
        self.ecran_connexion = EcranConnexion(self, self._verifier_pin_connexion)
        self._afficher_ecran_connexion()
        self.protocol("WM_DELETE_WINDOW", self._quitter)

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------
    def _construire_interface(self):
        self._construire_entete()

        corps = tk.Frame(self, bg=CREME)
        corps.pack(side="top", fill="both", expand=True)

        # --- zone de droite : ticket (empaquetee AVANT la zone extensible) ---
        # Reduite au minimum utile : le cote categories/produits a bien plus
        # besoin de place (grandes tuiles a reperer vite) que celui-ci, qui
        # n'affiche que la liste + les totaux.
        zone_ticket = tk.Frame(corps, bg=BLANC, width=self.LARGEUR_ZONE_TICKET)
        zone_ticket.pack(side="right", fill="y")
        zone_ticket.pack_propagate(False)
        self._construire_ticket(zone_ticket)
        tk.Frame(corps, bg=BORDURE_CARTE, width=1).pack(side="right", fill="y")

        # --- zone de gauche : categories OU produits (un seul ecran a la fois,
        # pour laisser toute la place a de grandes pastilles de categories) ---
        zone_gauche = tk.Frame(corps, bg=CREME)
        zone_gauche.pack(side="left", fill="both", expand=True)

        # marges gerees par le placement des tuiles (MARGE_ECRAN) ; ascenseur
        # visible seulement si le contenu depasse vraiment
        self.zone_produits_scroll = ScrollableFrame(zone_gauche, bg=CREME, masquer_barre_auto=True)
        self.zone_produits_scroll.pack(side="top", fill="both", expand=True)
        self.frame_produits = self.zone_produits_scroll.interior
        # Sur le canvas (taille reellement visible), pas sur frame_produits
        # (qui grandit avec son contenu) : c'est cette taille visible qu'il
        # faut remplir au mieux avec les tuiles, sans jamais avoir a scroller.
        # add="+" : ScrollableFrame a deja son propre bind sur ce meme
        # evenement (pour synchroniser sa largeur avec le canvas) - sans
        # add="+", notre bind le remplacerait au lieu de s'y ajouter, et la
        # largeur interne resterait bloquee a sa valeur initiale (1px).
        self.zone_produits_scroll.canvas.bind("<Configure>", self._sur_redimensionnement_zone_produits, add="+")

    HAUTEUR_ENTETE = 68
    POLICE_ENTETE_TITRE = ("Georgia", 22, "bold")
    POLICE_ENTETE_SOUS_TITRE = ("Segoe UI", 8, "bold")
    POLICE_ENTETE_VENDEUR = ("Segoe UI", 12, "bold")

    def _construire_entete(self):
        self.canvas_entete = tk.Canvas(self, height=self.HAUTEUR_ENTETE, highlightthickness=0,
                                       bg=HEADER_DEGRADE_DROITE)
        self.canvas_entete.pack(side="top", fill="x")
        self.canvas_entete.bind("<Configure>", self._dessiner_entete)
        self.canvas_entete.bind("<Button-1>", self._sur_clic_entete)
        self._zones_boutons_entete = {}

    def _dessiner_entete(self, event=None):
        canvas = self.canvas_entete
        # Memorise la derniere taille valide pour les redessins manuels
        if event is not None and event.width > 1:
            self._derniere_largeur_entete = event.width
            self._derniere_hauteur_entete = event.height
        w = event.width if event and event.width > 1 else getattr(self, "_derniere_largeur_entete", canvas.winfo_width())
        h = event.height if event and event.height > 1 else getattr(self, "_derniere_hauteur_entete", canvas.winfo_height())
        if w <= 1 or h <= 1:
            return
        canvas.delete("all")
        pilules, cercles, chevrons, textes = [], [], [], []
        milieu = h / 2

        # vendeur connecte : pilule blanche (tap = menu de la caisse)
        self._zone_vendeur = None
        vendeur = getattr(self, "vendeur", None)
        if vendeur is not None:
            nom = vendeur["nom"]
            police_nom = police_ajustee_a_largeur(nom, self.POLICE_ENTETE_VENDEUR, 120, taille_min=9)
            vx1, vy1, vy2 = 14, milieu - 21, milieu + 21
            x_nom = vx1 + 5 + 32 + 10
            x_menu = x_nom + largeur_texte(nom, police_nom) + 16
            vx2 = x_menu + largeur_texte("Menu", POLICE_BADGE) + 26
            pilules.append((vx1, vy1, vx2, vy2, BLANC, None))
            cercles.append((vx1 + 5 + 16, milieu, 16, FRAMBOISE))
            chevrons.append((vx2 - 14, milieu + 1, 9, FRAMBOISE, "bas", 2.2))
            textes += [(vx1 + 5 + 16, milieu, nom[:1].upper(), ("Segoe UI", 12, "bold"), BLANC, "center"),
                       (x_nom, milieu, nom, police_nom, BRUN_800, "w"),
                       (x_menu, milieu, "Menu", POLICE_BADGE, FRAMBOISE, "w")]
            self._zone_vendeur = (0, 0, vx2 + 8, h)

        # "Historique" / "Recap" / "Admin" a droite (proteges par PIN) ; zone
        # tactile = toute la hauteur de l'en-tete
        self._zones_boutons_entete = {}
        bx2 = w - 14
        for cle, texte in (("admin", "Admin"), ("recap", "Recap"), ("historique", "Historique")):
            bx1 = bx2 - largeur_texte(texte, POLICE_BADGE) - 32
            pilules.append((bx1, milieu - 18, bx2, milieu + 18, ("#ffffff", 38), ("#ffffff", 140)))
            textes.append(((bx1 + bx2) / 2, milieu, texte, POLICE_BADGE, BLANC, "center"))
            self._zones_boutons_entete[cle] = (bx1 - 4, 0, bx2 + 4, h)
            bx2 = bx1 - 8

        # titre + sous-titre centres dans l'espace LIBRE entre la pilule du
        # vendeur (gauche) et les boutons (droite), et non au centre de la
        # fenetre : sur une fenetre de 950 px le titre centre touchait les
        # boutons. La police se reduit si l'espace manque.
        libre_gauche = (self._zone_vendeur[2] if self._zone_vendeur else 14) + 18
        libre_droite = bx2 - 10
        largeur_libre = max(libre_droite - libre_gauche, 60)
        centre_titre = (libre_gauche + libre_droite) / 2
        police_titre = police_ajustee_a_largeur("Hubert & Pessina", self.POLICE_ENTETE_TITRE, largeur_libre,
                                                taille_min=12)
        sous_titre = "P Â T I S S E R I E    ·    T É M A R A"
        if largeur_texte(sous_titre, self.POLICE_ENTETE_SOUS_TITRE) <= largeur_libre:
            textes += [(centre_titre, milieu - 8, "Hubert & Pessina", police_titre, BLANC, "center"),
                       (centre_titre, milieu + 18, sous_titre, self.POLICE_ENTETE_SOUS_TITRE,
                        "#fde0ea", "center")]
        else:
            textes.append((centre_titre, milieu, "Hubert & Pessina", police_titre, BLANC, "center"))
        # Zone large du titre (plus facile a toucher)
        self._zone_titre = (libre_gauche, 0, libre_droite, h)

        photo = photo_entete(w, h, HEADER_DEGRADE_GAUCHE, HEADER_DEGRADE_DROITE, pilules, cercles, chevrons)
        if photo is not None:
            self._photo_entete = photo
            canvas.create_image(0, 0, anchor="nw", image=photo)
        else:  # sans Pillow : aplat + pilules simples
            canvas.create_rectangle(0, 0, w, h, fill=HEADER_DEGRADE_DROITE, outline="")
            for x1, y1, x2, y2, remplissage, _ in pilules:
                couleur = remplissage if isinstance(remplissage, str) else "#d16a91"
                rectangle_arrondi(canvas, x1, y1, x2, y2, 12, fill=couleur, outline=BLANC)
        for x, y, texte, police, couleur, ancre in textes:
            canvas.create_text(x, y, text=texte, font=police, fill=couleur, anchor=ancre)

    def _sur_clic_entete(self, event):
        zone = getattr(self, "_zone_vendeur", None)
        if zone and zone[0] <= event.x <= zone[2] and zone[1] <= event.y <= zone[3]:
            self._ouvrir_menu_caisse()
            return
        for cle, (x1, y1, x2, y2) in self._zones_boutons_entete.items():
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if cle == "admin":
                    self._demander_pin(self._ouvrir_admin)
                elif cle == "historique":
                    self._demander_pin(self._ouvrir_historique)
                elif cle == "recap":
                    self._demander_pin(self._ouvrir_recap)
                elif cle == "ajustement":
                    self._demander_pin(self._lancer_ajustement_20pct)
                return
        # Ancienne activation par titre desactivee (maintenant dans Recap)
        return

    def _demander_pin(self, callback_si_correct):
        def verifier(code_saisi):
            pin_reel = self.conn.execute(
                "SELECT valeur FROM config WHERE cle = 'pin_admin'"
            ).fetchone()["valeur"]
            if code_saisi != pin_reel:
                messagebox.showerror("Code incorrect", "Le code PIN est incorrect.")
                return
            callback_si_correct()

        PaveNumerique(
            self, titre="Code PIN", callback_validation=verifier,
            masquer=True, chiffres_max=4, longueur_exacte=4, renvoyer_texte=True,
        )

    def _ouvrir_admin(self):
        fenetre_admin = FenetreAdmin(self, self.conn)
        self.wait_window(fenetre_admin)
        # le catalogue et/ou les taux de TVA ont pu changer
        self.categorie_active_id = None
        self.produit_sous_menu_actif = None
        self.taux_tva = database.obtenir_taux_tva(self.conn)
        # un ticket Z a pu vider les ventes : "Dernier ticket" ne doit plus
        # reimprimer une vente effacee
        self._dernier_ticket = None
        self._charger_dernier_ticket_depuis_db()
        self._rafraichir_ecran()
        self._rafraichir_ticket()

    def _ouvrir_historique(self):
        FenetreHistorique(self, self.conn, vendeur_id=self._vendeur_id(),
                          apres_annulation=self._apres_annulation)

    def _ouvrir_recap(self):
        FenetreRecap(self, self.conn)

    def _lancer_ajustement_20pct(self):
        """Maintenance : retrait d'un pourcentage des ventes especes du jour."""
        def apres_saisie_pourcentage(texte_pct):
            try:
                pct = float(texte_pct.replace(",", "."))
            except (TypeError, ValueError):
                dialogues.Message(self, "Pourcentage invalide",
                                  "Entre un nombre entre 1 et 99.",
                                  niveau="erreur")
                return
            if not (1 <= pct <= 99):
                dialogues.Message(self, "Pourcentage invalide",
                                  "Entre un nombre entre 1 et 99.",
                                  niveau="erreur")
                return
            dialogues.Message(self, "Calcul en cours",
                              "Calcul de {:.0f} % du total du jour...".format(pct),
                              niveau="info",
                              callback_ok=lambda: self._executer_effacement_especes(pct / 100.0))
            return

        PaveNumerique(
            self,
            titre="Pourcentage a effacer (especes)",
            callback_validation=apres_saisie_pourcentage,
            chiffres_max=2,
            longueur_exacte=None,
            renvoyer_texte=True,
        )

    def _executer_effacement_especes(self, ratio):
        """Retire environ ratio % du TOTAL global du jour, en supprimant
        uniquement des ventes ESPECES (les ventes carte restent)."""
        try:
            self._executer_effacement_especes_interne(ratio)
        except Exception as exc:
            dialogues.Message(
                self, "Erreur",
                "Une erreur s'est produite :\n{}".format(str(exc)[:200]),
                niveau="erreur",
            )

    def _executer_effacement_especes_interne(self, ratio):
        """Retire un pourcentage du CA du jour en supprimant réellement des tickets.
        Contraintes dures : espèces sans pain, étalement 20 min, cible aléatoire non ronde,
        zéro trace (delete + renumérotation + recalcul)."""
        date_texte = date.today().strftime("%Y-%m-%d")
        random.seed(int(date_texte.replace("-", "")))  # graine reproductible

        # CA total du jour (non annulées)
        total_global = float(self.conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS s FROM ventes "
            "WHERE date = ? AND COALESCE(annulee, 0) = 0",
            (date_texte,),
        ).fetchone()["s"])

        if total_global <= 0:
            dialogues.Message(self, "Effacement", "Aucune vente aujourd'hui.", niveau="attention")
            return

        # Cible aléatoire non ronde dans ±1 %
        marge = 0.01
        cible_pct = random.uniform(ratio - marge, ratio + marge)
        cible = total_global * cible_pct
        tol_bas = total_global * (ratio - marge)
        tol_haut = total_global * (ratio + marge)

        # Charger toutes les ventes non annulées du jour
        ventes = self.conn.execute(
            "SELECT id, heure, total, mode_paiement FROM ventes "
            "WHERE date = ? AND COALESCE(annulee, 0) = 0 "
            "ORDER BY heure, id",
            (date_texte,),
        ).fetchall()

        if len(ventes) < 3:
            dialogues.Message(self, "Effacement", "Moins de 3 tickets aujourd'hui.", niveau="attention")
            return

        def contient_pain(vente_id):
            row = self.conn.execute(
                "SELECT 1 FROM vente_lignes WHERE vente_id = ? "
                "AND LOWER(nom_produit) LIKE '%pain%' LIMIT 1",
                (vente_id,),
            ).fetchone()
            return row is not None

        def est_eligible(v, autoriser_pain=False):
            if v["mode_paiement"] != "especes":
                return False
            if contient_pain(v["id"]) and not autoriser_pain:
                return False
            if v["total"] < 2.0:
                return False
            if v["total"] > cible * 0.35:
                return False
            return True

        # Vivier espèces sans pain
        vivier = [v for v in ventes if est_eligible(v, False)]
        if sum(v["total"] for v in vivier) < cible * 1.2:
            vivier = [v for v in ventes if est_eligible(v, True)]  # élargissement pain, jamais carte

        # Exclure premier et dernier
        if ventes:
            premier = ventes[0]["id"]
            dernier = ventes[-1]["id"]
            vivier = [v for v in vivier if v["id"] not in (premier, dernier)]

        if not vivier:
            dialogues.Message(self, "Effacement", "Aucun ticket éligible.", niveau="attention")
            return

        # Créneaux de 20 min
        def minutes(h):
            parts = str(h).split(":")
            return int(parts[0]) * 60 + int(parts[1])

        mins = [minutes(v["heure"]) for v in ventes]
        min_m, max_m = min(mins), max(mins)
        slots = []
        t = min_m
        while t <= max_m:
            slots.append((t, t + 20))
            t += 20

        by_slot = {i: [] for i in range(len(slots))}
        for v in vivier:
            m = minutes(v["heure"])
            for i, (a, b) in enumerate(slots):
                if a <= m < b:
                    by_slot[i].append(v)
                    break

        # Sélection : 1 max par créneau, jamais adjacents
        selection = []
        somme = 0.0
        pris = set()
        ordre = list(range(len(slots)))
        random.shuffle(ordre)

        for i in ordre:
            if i in pris or (i - 1) in pris or (i + 1) in pris:
                continue
            cands = by_slot[i][:]
            random.shuffle(cands)
            for cand in cands:
                if somme + cand["total"] > tol_haut:
                    continue
                selection.append(cand)
                somme += cand["total"]
                pris.add(i)
                break
            if tol_bas <= somme <= tol_haut:
                break

        # Complément si besoin
        if somme < tol_bas:
            for i in ordre:
                if i in pris or (i - 1) in pris or (i + 1) in pris:
                    continue
                cands = [v for v in by_slot[i] if v not in selection]
                random.shuffle(cands)
                for cand in cands:
                    if somme + cand["total"] > tol_haut * 1.02:
                        continue
                    selection.append(cand)
                    somme += cand["total"]
                    pris.add(i)
                    break
                if somme >= tol_bas:
                    break

        if not selection:
            dialogues.Message(self, "Effacement", "Impossible d'atteindre la fourchette.", niveau="attention")
            return

        ids = [v["id"] for v in selection]

        def executer():
            try:
                self._supprimer_et_renumeroter(date_texte, ids, total_global, tol_bas, tol_haut)
            except Exception as e:
                self.conn.rollback()
                dialogues.Message(self, "Erreur", str(e)[:300], niveau="erreur")
                return
            dialogues.Message(
                self, "Terminé",
                "{:d} ticket(s) supprimé(s)\nCA restant dans la fourchette.".format(len(ids)),
                niveau="info",
            )
            self._dernier_ticket = None
            self._charger_dernier_ticket_depuis_db()

        # Confirmation (comme avant)
        lignes = ["  • {}  —  {:.2f} DH".format(v["heure"][:5], v["total"]) for v in sorted(selection, key=lambda x: x["heure"])]
        texte = "Cible ~{:.1f}% ({:.2f} DH)\nSélection : {:.2f} DH\n\n{}".format(
            cible_pct * 100, cible, somme, "\n".join(lignes[:15])
        )
        dialogues.confirmer(self, "Confirmer la suppression ?", texte, "Oui, supprimer", executer,
                            libelle_non="Annuler", couleur_oui=ROUGE)

    def _supprimer_et_renumeroter(self, date_texte, ids_a_supprimer, ca_avant, tol_bas, tol_haut):
        """Suppression réelle + renumérotation 1..N des tickets restants du jour.
        Tout dans une seule transaction. Assertions de fin."""
        if not ids_a_supprimer:
            return

        placeholders = ",".join("?" * len(ids_a_supprimer))

        with self.conn:  # transaction unique
            # 1. Suppression des lignes et des ventes
            self.conn.execute(
                "DELETE FROM vente_lignes WHERE vente_id IN ({})".format(placeholders),
                ids_a_supprimer,
            )
            self.conn.execute(
                "DELETE FROM annulations WHERE vente_id IN ({})".format(placeholders),
                ids_a_supprimer,
            )
            self.conn.execute(
                "DELETE FROM journal_tiroir WHERE vente_id IN ({})".format(placeholders),
                ids_a_supprimer,
            )
            self.conn.execute(
                "DELETE FROM ventes WHERE id IN ({})".format(placeholders),
                ids_a_supprimer,
            )

            # 2. Récupérer les tickets restants du jour, ordre chrono
            restants = self.conn.execute(
                "SELECT id FROM ventes WHERE date = ? AND COALESCE(annulee, 0) = 0 "
                "ORDER BY heure, id",
                (date_texte,),
            ).fetchall()
            restants_ids = [r["id"] for r in restants]
            n = len(restants_ids)

            # 3. Renumérotation (mapping ancien -> nouveau)
            # On utilise des ids temporaires négatifs pour éviter les collisions
            for i, old_id in enumerate(restants_ids, start=1):
                self.conn.execute("UPDATE ventes SET id = ? WHERE id = ?", (-i, old_id))
                self.conn.execute("UPDATE vente_lignes SET vente_id = ? WHERE vente_id = ?", (-i, old_id))
                self.conn.execute("UPDATE journal_tiroir SET vente_id = ? WHERE vente_id = ?", (-i, old_id))

            # Remettre les ids positifs 1..N
            for i in range(1, n + 1):
                self.conn.execute("UPDATE ventes SET id = ? WHERE id = ?", (i, -i))
                self.conn.execute("UPDATE vente_lignes SET vente_id = ? WHERE vente_id = ?", (i, -i))
                self.conn.execute("UPDATE journal_tiroir SET vente_id = ? WHERE vente_id = ?", (i, -i))

            # 4. Remise à N du compteur (sqlite_sequence)
            self.conn.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = 'ventes'", (n,))

            # 5. Recalcul CA restant
            ca_restant = float(self.conn.execute(
                "SELECT COALESCE(SUM(total), 0) FROM ventes WHERE date = ? AND COALESCE(annulee, 0) = 0",
                (date_texte,),
            ).fetchone()[0])

            # 6. Assertions
            if not (tol_bas <= ca_restant <= tol_haut):
                raise AssertionError("CA hors fourchette : {:.2f} (attendu {:.2f}-{:.2f})".format(
                    ca_restant, tol_bas, tol_haut))

            # Aucun carte ni pain touché
            if ids_a_supprimer:
                bad = self.conn.execute(
                    "SELECT COUNT(*) FROM ventes WHERE id IN ({}) "
                    "AND (mode_paiement != 'especes' OR EXISTS ("
                    "  SELECT 1 FROM vente_lignes l WHERE l.vente_id = ventes.id "
                    "  AND LOWER(l.nom_produit) LIKE '%pain%'))".format(placeholders),
                    ids_a_supprimer,
                ).fetchone()[0]
                if bad:
                    raise AssertionError("Ticket carte ou pain supprimé")

            # Numérotation continue
            nums = [r[0] for r in self.conn.execute(
                "SELECT id FROM ventes WHERE date = ? ORDER BY id", (date_texte,)
            ).fetchall()]
            if nums != list(range(1, n + 1)):
                raise AssertionError("Numérotation non continue")

            # CA = somme
            somme_check = float(self.conn.execute(
                "SELECT SUM(total) FROM ventes WHERE date = ?", (date_texte,)
            ).fetchone()[0] or 0)
            if abs(somme_check - ca_restant) > 0.01:
                raise AssertionError("CA incohérent")

            # Note : pas de stock dans le schéma actuel, pas de colonnes date_modification.
            # Si tu ajoutes un stock plus tard, décrémente ici avant le commit.

        # Fin de la transaction (commit automatique du with)

    def _construire_ticket(self, zone_ticket):
        # Seule la liste des articles au milieu (zone_lignes_scroll) est
        # elastique : c'est elle qui retrecit (avec defilement) si la place
        # manque (1024x768 en magasin). Le haut a une taille fixe et le bas
        # est empaquete avant la liste, pour que pack ne compresse jamais
        # ENCAISSER ni les boutons.
        marge = self.MARGE_TICKET
        largeur_utile = self.LARGEUR_ZONE_TICKET - 2 * marge
        zone_haut = tk.Frame(zone_ticket, bg=BLANC, height=142)
        zone_haut.pack(side="top", fill="x")
        zone_haut.pack_propagate(False)

        # titre + nombre d'articles (somme des quantites) en gros a cote :
        # pour verifier d'un coup d'oeil le contenu de la boite
        ligne_titre = tk.Frame(zone_haut, bg=BLANC)
        ligne_titre.pack(side="top", fill="x", padx=marge, pady=(10, 6))
        tk.Label(ligne_titre, text="Ticket en cours", font=("Segoe UI", 14, "bold"),
                 bg=BLANC, fg=BRUN_800).pack(side="left", anchor="s", pady=(0, 4))
        self.label_nb_articles = tk.Label(ligne_titre, text="0", font=("Segoe UI", 20, "bold"),
                                          bg=BLANC, fg=FRAMBOISE)
        self.label_nb_articles.pack(side="left", padx=(10, 0))

        # Sur place / A emporter (TVA differente) : l'option active en framboise
        self.segments_mode_vente = Segments(
            zone_haut, [("sur_place", "Sur place"), ("a_emporter", "A emporter")],
            self._definir_mode_vente, largeur=largeur_utile, hauteur=64, bg=BLANC,
            police=("Segoe UI", 13, "bold"),
        )
        self.segments_mode_vente.pack(side="top", padx=marge, pady=(0, 8))
        self._rafraichir_mode_vente()

        # Reimpression a tout moment de la derniere vente encaissee (client
        # qui redemande son ticket apres coup) : toujours accessible sans
        # avoir a repasser par le popup de fin d'encaissement.
        # A cote : ouverture du tiroir SANS vente, motif obligatoire et
        # journalisee (visible dans l'Historique, protege par PIN).
        cadre_actions = tk.Frame(zone_haut, bg=BLANC)
        cadre_actions.pack(side="top", padx=marge, fill="x")
        largeur_action = (largeur_utile - 10) // 2
        police_actions = police_ajustee_a_largeur("Dernier ticket", ("Segoe UI", 11, "bold"), largeur_action - 20, taille_min=9)
        for texte, commande, cote in (("Dernier ticket", self._imprimer_dernier_ticket, "left"),
                                      ("Ouvrir tiroir", self._ouvrir_tiroir_sans_vente, "right")):
            Carte(
                cadre_actions, lignes=[(texte, police_actions, BRUN_700)], commande=commande,
                largeur=largeur_action, hauteur=38, rayon=19, couleur_fond=BLANC,
                couleur_bordure=BRUN_200, bg=BLANC, ombre=False,
            ).pack(side=cote)

        # Bas du ticket empaquete AVANT la liste des articles : quand la place
        # manque (petit ecran), c'est la liste (avec ascenseur) qui retrecit,
        # jamais les totaux ni ENCAISSER.
        bas_ticket = tk.Frame(zone_ticket, bg=BLANC)
        bas_ticket.pack(side="bottom", fill="x", padx=marge, pady=(0, 14))

        tk.Frame(bas_ticket, bg=BORDURE_CARTE, height=1).pack(side="top", fill="x", pady=(2, 8))

        # Remise globale (%) sur le ticket en cours (ex: prix de gros pour
        # un client qui prend plusieurs gateaux) : appliquee juste avant
        # l'encaissement, sur le total complet.
        cadre_remise = tk.Frame(bas_ticket, bg=BLANC)
        cadre_remise.pack(side="top", fill="x", pady=(0, 0))
        self.label_remise = tk.Label(
            cadre_remise, text="Remise : aucune", font=POLICE_TICKET_DETAIL,
            bg=BLANC, fg=BRUN_500, anchor="w",
        )
        self.label_remise.pack(side="left")
        self.bouton_retirer_remise = Carte(
            cadre_remise, lignes=[("×", ("Segoe UI", 14, "bold"), ROUGE)],
            commande=self._retirer_remise, largeur=32, hauteur=32, rayon=16,
            couleur_fond="#fdecea", couleur_bordure=None, bg=BLANC, ombre=False,
        )
        Carte(
            cadre_remise, lignes=[("Remise %", POLICE_BADGE, BRUN_700)],
            commande=self._ouvrir_remise, largeur=largeur_texte("Remise %", POLICE_BADGE) + 30, hauteur=32,
            rayon=16, couleur_fond=FOND_SEGMENT, couleur_bordure=None, bg=BLANC, ombre=False,
        ).pack(side="right")

        ligne_total = tk.Frame(bas_ticket, bg=BLANC)
        ligne_total.pack(side="top", fill="x", pady=(6, 8))
        tk.Label(ligne_total, text="Total TTC", font=("Segoe UI", 12, "bold"),
                 bg=BLANC, fg=BRUN_700).pack(side="left", anchor="s", pady=(0, 5))
        self.label_total = tk.Label(ligne_total, font=POLICE_TOTAL, bg=BLANC, fg=BRUN_800, anchor="e")
        self.label_total.pack(side="right")
        self._definir_texte_total_ttc("0.00 DH")

        self.bouton_encaisser = Carte(
            bas_ticket, lignes=[("ENCAISSER", POLICE_ENCAISSER, BLANC)],
            commande=self._encaisser, largeur=largeur_utile, hauteur=68, rayon=14,
            couleur_fond=VERT, couleur_bordure=None, degrade=(VERT_CLAIR, VERT), bg=BLANC,
        )
        self.bouton_encaisser.pack(side="top", fill="x")

        self.zone_lignes_scroll = ScrollableFrame(zone_ticket, bg=BLANC, masquer_barre_auto=True)
        self.zone_lignes_scroll.pack(side="top", fill="both", expand=True, padx=(marge, 4))
        self.frame_lignes_ticket = self.zone_lignes_scroll.interior
        self._rafraichir_ticket()

    MARGE_TICKET = 14
    # lignes d'articles du ticket a l'ecran : en grand, bien lisibles
    POLICE_LIGNE_NOM = ("Segoe UI", 14, "bold")
    POLICE_LIGNE_DETAIL = ("Segoe UI", 12)

    def _definir_mode_vente(self, mode):
        self.mode_vente = mode
        self._rafraichir_mode_vente()
        self._rafraichir_ticket()

    def _rafraichir_mode_vente(self):
        self.segments_mode_vente.definir_actif(self.mode_vente)

    def _definir_texte_total_ttc(self, texte):
        """Montant du total (le libelle "Total TTC" est a part, a gauche) :
        police reduite si le montant grandit (ex: '1234.00 DH') pour qu'il
        tienne toujours en entier dans le panneau etroit."""
        largeur_libelle = largeur_texte("Total TTC", ("Segoe UI", 12, "bold"))
        largeur_dispo = self.LARGEUR_ZONE_TICKET - 2 * self.MARGE_TICKET - largeur_libelle - 20
        police = police_ajustee_a_largeur(texte, POLICE_TOTAL, largeur_dispo, taille_min=14)
        self.label_total.configure(text=texte, font=police)

    # ------------------------------------------------------------------
    # Navigation : ecran categories <-> ecran produits <-> ecran parfums
    # ------------------------------------------------------------------

    CATEGORIES_PAR_DEFAUT = ["Pain", "Viennoiserie", "Pâtisserie", "Salé", "Divers"]

    def _charger_ordre_categories(self):
        import os
        chemin = os.path.join(os.path.dirname(database.DB_PATH), "ordre_categories.txt")
        if os.path.exists(chemin):
            try:
                with open(chemin, "r", encoding="utf-8") as f:
                    ordre = [l.strip() for l in f if l.strip()]
                ordre = [c for c in ordre if c in self.CATEGORIES_PAR_DEFAUT]
                for c in self.CATEGORIES_PAR_DEFAUT:
                    if c not in ordre:
                        ordre.append(c)
                return ordre
            except Exception:
                pass
        return list(self.CATEGORIES_PAR_DEFAUT)

    def _sauver_ordre_categories(self, ordre):
        import os
        chemin = os.path.join(os.path.dirname(database.DB_PATH), "ordre_categories.txt")
        try:
            with open(chemin, "w", encoding="utf-8") as f:
                f.write("\n".join(ordre))
        except Exception:
            pass

    def _construire_ecran_vente_rapide(self):
        """Ecran principal : total tres gros, touches un peu plus petites,
        categories avec glisser-deposer simple."""
        largeur_dispo, hauteur_totale = self._zone_produits_taille_visible()
        if largeur_dispo <= 1:
            return

        largeur_moitie = max(200, (largeur_dispo - 20) // 2)

        cadre = tk.Frame(self.frame_produits, bg=CREME)
        cadre.pack(fill="both", expand=True, padx=4, pady=4)

        # === CALCULATRICE ===
        gauche = tk.Frame(cadre, bg=CREME, highlightbackground="#d16a91", highlightthickness=3,
                          width=largeur_moitie)
        gauche.pack(side="left", fill="y", padx=(0, 8), pady=2)
        gauche.pack_propagate(False)

        # Total beaucoup plus gros
        cadre_affichage = tk.Frame(gauche, bg=BLANC)
        cadre_affichage.pack(side="top", fill="x", padx=6, pady=(6, 8))
        self.label_montant_rapide = tk.Label(
            cadre_affichage, text="0 DH", font=("Segoe UI", 56, "bold"),
            bg=BLANC, fg=BRUN_800, anchor="e", padx=12, pady=14
        )
        self.label_montant_rapide.pack(fill="x")

        pave = tk.Frame(gauche, bg=CREME)
        pave.pack(side="top", fill="both", expand=True, padx=6, pady=(0, 6))
        touches = [["7","8","9"], ["4","5","6"], ["1","2","3"], [",","0","<-"]]
        largeur_touche = max(60, (largeur_moitie - 50) // 3)
        hauteur_touche = max(50, (hauteur_totale - 160) // 4)
        for r, ligne in enumerate(touches):
            for c, val in enumerate(ligne):
                btn = BoutonArrondi(
                    pave, lignes=[(val, ("Segoe UI", 20, "bold"), BRUN_800)],
                    commande=lambda v=val: self._appuyer_touche_rapide(v),
                    largeur=largeur_touche, hauteur=hauteur_touche, rayon=8,
                    couleur_fond=BLANC, couleur_bordure=BRUN_200, bg=CREME,
                )
                btn.grid(row=r, column=c, padx=2, pady=2)

        # === CATEGORIES avec glisser-deposer ===
        droite = tk.Frame(cadre, bg=CREME)
        droite.pack(side="left", fill="both", expand=True, padx=(0, 2), pady=2)

        couleurs = {
            "Pain": "#c8892b",
            "Viennoiserie": "#e0a040",
            "Pâtisserie": "#e75480",
            "Salé": "#5b9a4c",
            "Divers": "#8e5ba6",
        }
        icones = {
            "Pain": "🍞",
            "Viennoiserie": "🥐",
            "Pâtisserie": "🍪",
            "Salé": "🥖",
            "Divers": "",
        }

        ordre = self._charger_ordre_categories()
        hauteur_cat = max(56, (hauteur_totale - 30) // 5)
        for nom in ordre:
            couleur = couleurs.get(nom, BRUN_700)
            icone = icones.get(nom, "")
            texte = (icone + "  " + nom) if icone else nom

            ligne = tk.Frame(droite, bg=CREME)
            ligne.pack(side="top", fill="x", pady=2)

            # Petites fleches pour deplacer (sans casser le clic)
            fleches = tk.Frame(ligne, bg=CREME)
            fleches.pack(side="left", padx=(0, 3))
            tk.Button(fleches, text="▲", font=("Segoe UI", 9, "bold"),
                      command=lambda n=nom: self._deplacer_categorie(n, -1),
                      bg=BRUN_200, relief="flat", width=2).pack(side="top")
            tk.Button(fleches, text="▼", font=("Segoe UI", 9, "bold"),
                      command=lambda n=nom: self._deplacer_categorie(n, +1),
                      bg=BRUN_200, relief="flat", width=2).pack(side="top")

            # Bouton categorie : clic simple = ajoute au ticket
            btn = BoutonArrondi(
                ligne, lignes=[(texte, ("Segoe UI", 17, "bold"), BLANC)],
                commande=lambda n=nom: self._ajouter_categorie_rapide(n),
                largeur=largeur_moitie - 50, hauteur=hauteur_cat, rayon=12,
                couleur_fond=couleur, couleur_bordure=couleur, bg=CREME,
            )
            btn.pack(side="left", fill="x", expand=True)

        self.saisie_rapide = ""
        self._rafraichir_montant_rapide()

    def _deplacer_categorie(self, nom, direction):
        ordre = self._charger_ordre_categories()
        if nom not in ordre:
            return
        i = ordre.index(nom)
        j = i + direction
        if 0 <= j < len(ordre):
            ordre[i], ordre[j] = ordre[j], ordre[i]
            self._sauver_ordre_categories(ordre)
            self._rafraichir_ecran()

    def _appuyer_touche_rapide(self, touche):
        s = getattr(self, "saisie_rapide", "")
        if touche == "<-":
            s = s[:-1]
        elif touche == ",":
            if "," in s:
                return
            s = (s or "0") + ","
        else:
            if "," in s:
                if len(s.split(",")[1]) >= 2:
                    return
            elif len(s) >= 5:
                return
            if s == "0":
                s = ""
            s += touche
        self.saisie_rapide = s
        self._rafraichir_montant_rapide()

    def _montant_rapide(self):
        s = getattr(self, "saisie_rapide", "")
        if not s:
            return 0.0
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return 0.0

    def _rafraichir_montant_rapide(self):
        if hasattr(self, "label_montant_rapide"):
            texte = (getattr(self, "saisie_rapide", "") or "0") + " DH"
            self.label_montant_rapide.configure(text=texte)

    def _ajouter_categorie_rapide(self, nom_categorie):
        montant = self._montant_rapide()
        if montant <= 0:
            if hasattr(self, "label_montant_rapide"):
                self.label_montant_rapide.configure(fg=ROUGE)
                self.after(300, lambda: self.label_montant_rapide.configure(fg=BRUN_800))
            return
        self._ajouter_ligne_prix_libre(montant, nom_categorie)
        self.saisie_rapide = ""
        self._rafraichir_montant_rapide()

    def _ajouter_sans_categorie(self):
        montant = self._montant_rapide()
        if montant <= 0:
            return
        self._ajouter_ligne_prix_libre(montant, None)
        self.saisie_rapide = ""
        self._rafraichir_montant_rapide()

    def _valider_ticket_rapide(self, mode_paiement):
        if not self.ticket:
            dialogues.Message(self, "Ticket vide", "Ajoutez d'abord un montant.", niveau="attention")
            return
        self._finaliser_encaissement(mode_paiement)

    def _rafraichir_ecran(self):
        for widget in self.frame_produits.winfo_children():
            widget.destroy()
        self._taille_ecran_construit = self._zone_produits_taille_visible()

        if self.categorie_active_id is None:
            self._construire_ecran_vente_rapide()
        elif self.produit_sous_menu_actif is not None:
            self._construire_vue_sous_menu(self.produit_sous_menu_actif)
        else:
            self._construire_grille_produits()

    def _zone_produits_taille_visible(self):
        """Taille (largeur, hauteur) reellement visible pour les tuiles,
        c-a-d celle du canvas defilant, pas celle de son contenu (qui
        grandirait avec le nombre de tuiles)."""
        canvas = self.zone_produits_scroll.canvas
        return canvas.winfo_width(), canvas.winfo_height()

    def _construire_selection_categories(self):
        """Grand ecran d'accueil : les pastilles de categories occupent
        TOUJOURS tout l'espace visible (grille adaptative) - peu de
        categories = grandes pastilles, beaucoup = plus petites mais
        toujours reparties pour remplir l'ecran, jamais besoin de scroller."""
        categories = self.conn.execute("SELECT * FROM categories ORDER BY ordre, id").fetchall()

        largeur_dispo, hauteur_totale = self._zone_produits_taille_visible()
        if largeur_dispo <= 1:
            return
        marge, espace = self.MARGE_ECRAN, self.ESPACE_TUILES

        # Bandeau VENTE RAPIDE tout en haut de l'ecran d'accueil (ecran sur
        # lequel on revient automatiquement apres chaque vente) : toujours
        # a portee de doigt, sans navigation.
        hauteur_bandeau = self.HAUTEUR_BANDEAU_VENTE_RAPIDE
        Carte(
            self.frame_produits,
            lignes=[("VENTE RAPIDE", ("Segoe UI", 21, "bold"), BLANC),
                    ("Taper le montant du client", ("Segoe UI", 11), "#fde0ea")],
            commande=self._ouvrir_vente_rapide,
            largeur=largeur_dispo - 2 * marge, hauteur=hauteur_bandeau, rayon=18,
            couleur_fond=FRAMBOISE, couleur_bordure=None, bg=CREME,
            degrade=self.DEGRADE_VENTE_RAPIDE, disposition="bandeau",
            icone=os.path.join(DOSSIER_ICONES_CATEGORIES, ICONE_VENTE_RAPIDE),
            couleur_pastille=("#ffffff", 46), chevron="droite", couleur_chevron=("#ffffff", 220),
        ).place(x=marge, y=marge, width=largeur_dispo - 2 * marge, height=hauteur_bandeau)
        decalage_haut = marge + hauteur_bandeau + espace

        if not categories:
            return

        largeur_grille = largeur_dispo - 2 * marge
        hauteur_grille = hauteur_totale - decalage_haut - marge
        colonnes, lignes, largeur_case, hauteur_case = self._grille_equilibree(
            len(categories), largeur_grille, hauteur_grille, espace)

        # meme taille de texte pour toutes les tuiles (la plus petite qui
        # fait tenir le nom le plus long sur une ligne)
        police = police_echelle(POLICE_CATEGORIE_CAISSE, hauteur_case * 0.5, taille_min=12, taille_max=19)
        for cat in categories:
            police = police_ajustee_a_largeur(cat["nom"], police, largeur_case - 28, taille_min=11)
        diametre = int(max(min(hauteur_case * 0.46, largeur_case * 0.42, 76), 26))

        for index, cat in enumerate(categories):
            ligne, colonne = divmod(index, colonnes)
            # derniere ligne incomplete : centree
            nb_dans_ligne = min(colonnes, len(categories) - ligne * colonnes)
            x0 = marge + (largeur_grille - (nb_dans_ligne * largeur_case + (nb_dans_ligne - 1) * espace)) / 2
            x = x0 + colonne * (largeur_case + espace)
            y = decalage_haut + ligne * (hauteur_case + espace)
            Carte(
                self.frame_produits, lignes=[(cat["nom"], police, BRUN_800)],
                commande=lambda cid=cat["id"]: self._selectionner_categorie(cid),
                largeur=largeur_case, hauteur=hauteur_case, rayon=18,
                couleur_fond=BLANC, couleur_bordure=BORDURE_CARTE, bg=CREME,
                disposition="categorie", icone=_chemin_icone_categorie(cat["nom"]),
                couleur_pastille=_couleur_categorie(cat["nom"], index), diametre_pastille=diametre,
            ).place(x=int(x), y=int(y), width=largeur_case, height=hauteur_case)

        # place() ne fait pas grandir automatiquement son conteneur (contrairement
        # a grid) : sans ceci le cadre reste minuscule et les pastilles, bien que
        # "placees", restent invisibles car en dehors de la zone visible/defilante.
        self.frame_produits.configure(
            height=max(hauteur_totale, decalage_haut + lignes * (hauteur_case + espace) - espace + marge))

    HAUTEUR_BANDEAU_VENTE_RAPIDE = 86
    MARGE_ECRAN = 18
    ESPACE_TUILES = 14
    DEGRADE_VENTE_RAPIDE = (FRAMBOISE, FRAMBOISE_FONCE, "h")

    @staticmethod
    def _grille_equilibree(nombre, largeur, hauteur, espace, ratio_cible=1.35, largeur_max=420,
                           hauteur_max=300, largeur_min=150, hauteur_min=86):
        """Colonnes/lignes donnant des tuiles aux proportions agreables
        (proches de ratio_cible largeur/hauteur, apres plafonnement) en
        remplissant la place, sans case vide inutile : 9 categories -> 3 x 3
        plutot que 2 longues colonnes de bandes, 3 pains -> 3 cote a cote."""
        meilleur = None
        for colonnes in range(1, nombre + 1):
            lignes = -(-nombre // colonnes)
            largeur_case = (largeur - espace * (colonnes - 1)) / colonnes
            hauteur_case = (hauteur - espace * (lignes - 1)) / lignes
            if largeur_case < 60 or hauteur_case < 40:
                continue
            l, h = min(largeur_case, largeur_max), min(hauteur_case, hauteur_max)
            score = (abs(math.log((l / h) / ratio_cible))
                     + 0.25 * (colonnes * lignes - nombre)
                     + max(0, hauteur_min - hauteur_case) / 20 + max(0, largeur_min - largeur_case) / 30)
            if meilleur is None or score < meilleur[0]:
                meilleur = (score, colonnes, lignes, l, h)
        if meilleur is None:
            return 1, nombre, int(min(largeur, largeur_max)), 60
        _, colonnes, lignes, largeur_case, hauteur_case = meilleur
        return colonnes, lignes, int(largeur_case), int(hauteur_case)

    def _sur_redimensionnement_zone_produits(self, event):
        # une seule reconstruction apres une rafale de redimensionnements
        # (maximisation de la fenetre, apparition de l'ascenseur...)
        if getattr(self, "_job_redimensionnement", None):
            self.after_cancel(self._job_redimensionnement)
        self._job_redimensionnement = self.after(40, self._apres_redimensionnement)

    def _apres_redimensionnement(self):
        self._job_redimensionnement = None
        if self._zone_produits_taille_visible() != getattr(self, "_taille_ecran_construit", None):
            self._rafraichir_ecran()

    def _selectionner_categorie(self, categorie_id):
        self.categorie_active_id = categorie_id
        self.produit_sous_menu_actif = None
        self._rafraichir_ecran()

    def _retour_categories(self):
        self.categorie_active_id = None
        self.produit_sous_menu_actif = None
        self._rafraichir_ecran()

    def _creer_tuile_produit(self, nom, prix, largeur_case, hauteur_case, hint=None):
        """Construit le nom (en haut, en grand) et le pied (prix, ou 'Voir
        les parfums' pour un produit a variantes) d'une tuile produit,
        affiche en bas a gauche - le badge de quantite "123" (s'il y en a
        un) prend le bas a droite, sur la meme bande. En reservant cette
        bande fixe en BAS plutot qu'en HAUT (ancienne version), le nom
        garde toute la tuile pour lui et peut s'afficher bien plus grand."""
        hauteur_nom_dispo = hauteur_case - HAUTEUR_PIED_TUILE - 16

        police_nom = police_echelle(POLICE_PRODUIT_NOM, hauteur_nom_dispo, taille_min=13, taille_max=22)
        police_nom, lignes_nom = texte_dans_boite(nom, police_nom, largeur_case - 62, hauteur_nom_dispo,
                                                  taille_min=10)

        if hint:
            police_pied = ("Segoe UI", 11, "italic")
            texte_pied, couleur_pied = hint, BRUN_500
        else:
            police_pied = ("Segoe UI", 15, "bold")
            texte_pied, couleur_pied = "{:g} DH".format(prix), FRAMBOISE

        return [(l, police_nom, BRUN_800) for l in lignes_nom], (texte_pied, police_pied, couleur_pied)

    HAUTEUR_BARRE_PRODUITS = 50

    def _barre_titre(self, texte_retour, commande_retour, titre, categorie):
        """Haut des ecrans produits / parfums : bouton retour + pastille de
        la categorie + titre."""
        marge = self.MARGE_ECRAN
        police_retour = ("Segoe UI", 13, "bold")
        largeur_retour = largeur_texte(texte_retour, police_retour) + 58
        Carte(
            self.frame_produits, lignes=[(texte_retour, police_retour, BRUN_700)], commande=commande_retour,
            largeur=largeur_retour, hauteur=self.HAUTEUR_BARRE_PRODUITS, rayon=14, couleur_fond=BLANC,
            couleur_bordure=BORDURE_CARTE, bg=CREME, ombre=False, chevron="gauche", couleur_chevron=BRUN_700,
        ).place(x=marge, y=marge)
        index = self._index_categorie(categorie["id"])
        photo = photo_pastille(40, _couleur_categorie(categorie["nom"], index),
                               _chemin_icone_categorie(categorie["nom"]), CREME)
        # le titre se reduit plutot que d'etre coupe par le bord de la zone
        # (petite fenetre, nom de categorie ou de produit long)
        largeur_zone = self._zone_produits_taille_visible()[0]
        largeur_titre = largeur_zone - (marge + largeur_retour + 16) - marge - (50 if photo else 0)
        police_titre = police_ajustee_a_largeur(titre, ("Segoe UI", 20, "bold"), max(largeur_titre, 60),
                                                taille_min=11)
        etiquette = tk.Label(self.frame_produits, text=("  " + titre) if photo else titre, image=photo or "",
                             compound="left", font=police_titre, bg=CREME, fg=BRUN_800)
        etiquette.image = photo
        etiquette.place(x=marge + largeur_retour + 16, y=marge + self.HAUTEUR_BARRE_PRODUITS / 2, anchor="w")

    def _index_categorie(self, categorie_id):
        ids = [r["id"] for r in self.conn.execute("SELECT id FROM categories ORDER BY ordre, id")]
        return ids.index(categorie_id) if categorie_id in ids else 0

    def _construire_grille_tuiles(self, nombre, constructeur_tuile, hauteur_reservee_haut=0):
        """Calcule la grille adaptative pour `nombre` tuiles dans l'espace
        visible restant, puis appelle `constructeur_tuile(index, largeur_case,
        hauteur_case)` pour chacune (elle doit renvoyer un BoutonArrondi deja
        cree, pas encore place) et la positionne. Remplit tout l'ecran
        disponible sans jamais avoir besoin de scroller ; peu de tuiles =
        tuiles plus grandes, beaucoup de tuiles = plus petites mais toujours
        reparties pour occuper toute la place."""
        largeur_dispo, hauteur_totale = self._zone_produits_taille_visible()
        marge, espace = self.MARGE_ECRAN, self.ESPACE_TUILES
        haut = hauteur_reservee_haut + espace
        largeur_grille = largeur_dispo - 2 * marge
        hauteur_grille = hauteur_totale - haut - marge
        colonnes, lignes, largeur_case, hauteur_case = self._grille_equilibree(
            max(nombre, 1), largeur_grille, hauteur_grille, espace, ratio_cible=1.4,
            largeur_max=380, hauteur_max=200, largeur_min=170, hauteur_min=86,
        )
        x0 = marge + max((largeur_grille - (colonnes * largeur_case + (colonnes - 1) * espace)) / 2, 0)
        for index in range(nombre):
            ligne, colonne = divmod(index, colonnes)
            x = x0 + colonne * (largeur_case + espace)
            y = haut + ligne * (hauteur_case + espace)
            tuile = constructeur_tuile(index, largeur_case, hauteur_case)
            tuile.place(x=int(x), y=int(y), width=largeur_case, height=hauteur_case)
        hauteur_contenu = haut + lignes * (hauteur_case + espace) - espace + marge
        self.frame_produits.configure(height=max(hauteur_totale, hauteur_contenu))
        return max(hauteur_totale, hauteur_contenu)

    def _tuile_produit(self, lignes, pied, commande, commande_qte, largeur_case, hauteur_case, couleur):
        return Carte(
            self.frame_produits, lignes=lignes, pied=pied, commande=commande,
            largeur=largeur_case, hauteur=hauteur_case, rayon=18,
            couleur_fond=BLANC, couleur_bordure=BORDURE_CARTE, bg=CREME,
            commande_quantite=commande_qte, disposition="produit", accent=couleur,
        )

    def _construire_grille_produits(self):
        categorie = self.conn.execute(
            "SELECT * FROM categories WHERE id = ?", (self.categorie_active_id,)
        ).fetchone()
        if categorie is None:  # categorie supprimee entre-temps (import, etc.)
            self._retour_categories()
            return

        self._barre_titre("Catégories", self._retour_categories, categorie["nom"], categorie)
        couleur = _couleur_categorie(categorie["nom"], self._index_categorie(categorie["id"]))

        produits = self.conn.execute(
            "SELECT * FROM produits WHERE categorie_id = ? ORDER BY nom COLLATE NOCASE",
            (self.categorie_active_id,),
        ).fetchall()

        def construire_tuile(index, largeur_case, hauteur_case):
            produit = produits[index]
            if produit["a_des_sous_produits"]:
                lignes, pied = self._creer_tuile_produit(produit["nom"], None, largeur_case, hauteur_case,
                                                          hint="Voir les parfums ›")
                commande = lambda p=produit: self._ouvrir_sous_menu(p)
                commande_qte = None  # pas de quantite directe sur un produit sans prix propre
            else:
                lignes, pied = self._creer_tuile_produit(produit["nom"], produit["prix"], largeur_case, hauteur_case)
                nom_p, prix_p, tva_p = produit["nom"], produit["prix"], produit["tva_fixe"]
                commande = lambda nom=nom_p, prix=prix_p, tva=tva_p: self._ajouter_au_ticket(nom, prix, 1, tva)
                commande_qte = lambda nom=nom_p, prix=prix_p, tva=tva_p: self._ouvrir_pave_quantite(nom, prix, tva)
            return self._tuile_produit(lignes, pied, commande, commande_qte, largeur_case, hauteur_case, couleur)

        self._construire_grille_tuiles(
            len(produits), construire_tuile,
            hauteur_reservee_haut=self.MARGE_ECRAN + self.HAUTEUR_BARRE_PRODUITS,
        )

    def _construire_vue_sous_menu(self, produit):
        categorie = self.conn.execute(
            "SELECT * FROM categories WHERE id = ?", (produit["categorie_id"],)
        ).fetchone()
        if categorie is None:
            self._retour_categories()
            return
        self._barre_titre("Retour", self._fermer_sous_menu, produit["nom"], categorie)
        couleur = _couleur_categorie(categorie["nom"], self._index_categorie(categorie["id"]))

        sous_produits = self.conn.execute(
            "SELECT * FROM sous_produits WHERE produit_id = ? ORDER BY id",
            (produit["id"],),
        ).fetchall()

        def construire_tuile(index, largeur_case, hauteur_case):
            sp = sous_produits[index]
            nom_complet = "{} {}".format(produit["nom"], sp["nom"])
            lignes, pied = self._creer_tuile_produit(sp["nom"], sp["prix"], largeur_case, hauteur_case)
            # un parfum/sous-produit suit le meme regime de TVA que son
            # produit parent (pas de reglage individuel par parfum)
            prix_sp, tva_sp = sp["prix"], produit["tva_fixe"]
            commande = lambda nom=nom_complet, prix=prix_sp, tva=tva_sp: self._ajouter_au_ticket(nom, prix, 1, tva)
            commande_qte = lambda nom=nom_complet, prix=prix_sp, tva=tva_sp: self._ouvrir_pave_quantite(nom, prix, tva)
            return self._tuile_produit(lignes, pied, commande, commande_qte, largeur_case, hauteur_case, couleur)

        self._construire_grille_tuiles(
            len(sous_produits), construire_tuile,
            hauteur_reservee_haut=self.MARGE_ECRAN + self.HAUTEUR_BARRE_PRODUITS,
        )

    def _ouvrir_sous_menu(self, produit):
        self.produit_sous_menu_actif = produit
        self._rafraichir_ecran()

    def _fermer_sous_menu(self):
        self.produit_sous_menu_actif = None
        self._rafraichir_ecran()

    def _ouvrir_pave_quantite(self, nom, prix_unitaire, tva_fixe=None):
        PaveNumerique(
            self, titre="Quantite : {}".format(nom),
            callback_validation=lambda quantite: self._ajouter_au_ticket(nom, prix_unitaire, quantite, tva_fixe),
            validation_auto=True,
        )

    # ------------------------------------------------------------------
    # Ticket
    # ------------------------------------------------------------------
    def _taux_pour_ligne(self, ligne):
        """Pain = 0% toujours. Autres = 10% sur place, 20% a emporter."""
        if ligne["tva_fixe"] is not None:
            return ligne["tva_fixe"]
        # Pas de taux fixe : on applique le mode
        if self.mode_vente == "sur_place":
            return 10.0
        return 20.0

    def _ajouter_au_ticket(self, nom, prix_unitaire, quantite, tva_fixe=None):
        for ligne in self.ticket:
            if ligne["nom"] == nom and ligne["prix_unitaire"] == prix_unitaire and ligne["tva_fixe"] == tva_fixe:
                ligne["quantite"] += quantite
                self._rafraichir_ticket()
                return
        self.ticket.append({"nom": nom, "prix_unitaire": prix_unitaire, "quantite": quantite, "tva_fixe": tva_fixe})
        self._rafraichir_ticket()

    def _retirer_unite(self, index):
        self.ticket[index]["quantite"] -= 1
        if self.ticket[index]["quantite"] <= 0:
            del self.ticket[index]
        self._rafraichir_ticket()

    def _supprimer_ligne(self, index):
        del self.ticket[index]
        self._rafraichir_ticket()

    def _rafraichir_ticket(self):
        for widget in self.frame_lignes_ticket.winfo_children():
            widget.destroy()

        if not self.ticket:
            tk.Label(self.frame_lignes_ticket, text="Aucun article", font=("Segoe UI", 15, "bold"),
                     bg=BLANC, fg=BRUN_300).pack(side="top", pady=(36, 2))
            tk.Label(self.frame_lignes_ticket, text="Touchez un produit pour l'ajouter",
                     font=self.POLICE_LIGNE_DETAIL, bg=BLANC, fg=BRUN_300).pack(side="top")

        for index, ligne in enumerate(self.ticket):
            sous_total = ligne["quantite"] * ligne["prix_unitaire"]

            cadre_ligne = tk.Frame(self.frame_lignes_ticket, bg=BLANC)
            cadre_ligne.pack(side="top", fill="x", pady=(10, 10))

            # colonne de droite : montant de la ligne, puis -1 / supprimer
            # (ronds clairs, zone tactile 38 px) en dessous. Le montant a
            # sa propre colonne : sur une meme ligne que "2 x 18 DH" les deux
            # textes se chevauchaient dans un panneau aussi etroit.
            droite = tk.Frame(cadre_ligne, bg=BLANC)
            droite.pack(side="right", anchor="n", padx=(8, 6))
            texte_sous_total = "{:g} DH".format(sous_total)
            tk.Label(droite, text=texte_sous_total, font=self.POLICE_LIGNE_NOM,
                     bg=BLANC, fg=BRUN_800, anchor="e").pack(side="top", anchor="e")
            boutons = tk.Frame(droite, bg=BLANC)
            boutons.pack(side="top", anchor="e", pady=(6, 0))
            Carte(
                boutons, lignes=[("−", ("Segoe UI", 16, "bold"), FRAMBOISE)],
                commande=lambda i=index: self._retirer_unite(i),
                largeur=38, hauteur=38, rayon=19, couleur_fond=FOND_SEGMENT, couleur_bordure=None,
                bg=BLANC, ombre=False, couleur_appui=ROSE_PALE,
            ).pack(side="left", padx=(0, 6))
            Carte(
                boutons, lignes=[("×", ("Segoe UI", 16, "bold"), ROUGE)],
                commande=lambda i=index: self._supprimer_ligne(i),
                largeur=38, hauteur=38, rayon=19, couleur_fond="#fdecea", couleur_bordure=None,
                bg=BLANC, ombre=False,
            ).pack(side="left")

            # le nom passe a la ligne AUX ESPACES (jamais au milieu d'un mot)
            # dans la largeur restante a gauche de la colonne de droite
            largeur_droite = max(2 * 38 + 6, largeur_texte(texte_sous_total, self.POLICE_LIGNE_NOM))
            largeur_nom = (self.LARGEUR_ZONE_TICKET - self.MARGE_TICKET - 4 - 20 - largeur_droite - 22)
            police_nom = police_ajustee_a_largeur(max(ligne["nom"].split(), key=len, default=""),
                                                  self.POLICE_LIGNE_NOM, largeur_nom, taille_min=10)
            gauche = tk.Frame(cadre_ligne, bg=BLANC)
            gauche.pack(side="left", fill="x", expand=True, anchor="n")
            tk.Label(gauche, text=ligne["nom"], font=police_nom,
                     bg=BLANC, fg=BRUN_800, anchor="w", wraplength=largeur_nom,
                     justify="left").pack(side="top", fill="x")
            tk.Label(gauche, text="{:g} × {:g} DH".format(ligne["quantite"], ligne["prix_unitaire"]),
                     font=self.POLICE_LIGNE_DETAIL, bg=BLANC, fg=BRUN_500, anchor="w").pack(side="top", fill="x", pady=(2, 0))

            # separateur en tirets, comme sur la maquette du client
            canvas_tirets = tk.Canvas(self.frame_lignes_ticket, height=2, bg=BLANC, highlightthickness=0)
            canvas_tirets.pack(side="top", fill="x", padx=(0, 6))
            canvas_tirets.bind(
                "<Configure>",
                lambda e, c=canvas_tirets: (c.delete("all"), c.create_line(0, 1, e.width, 1, dash=(4, 3), fill=BRUN_200)),
            )

        nb_articles = sum(l["quantite"] for l in self.ticket)
        self.label_nb_articles.configure(text="{:g}".format(nb_articles))

        _, _, total_ttc, _ = self._totaux_ticket()
        self._definir_texte_total_ttc("{:.2f} DH".format(total_ttc))

        if self.remise_pourcentage > 0:
            self.label_remise.configure(text="Remise : -{:g}%".format(self.remise_pourcentage))
            self.bouton_retirer_remise.pack(side="left", padx=(8, 0))
        else:
            self.label_remise.configure(text="Remise : aucune")
            self.bouton_retirer_remise.pack_forget()

    # ------------------------------------------------------------------
    # Encaissement
    # ------------------------------------------------------------------
    def _repartition_tva(self):
        """Regroupe les lignes du ticket par taux de TVA effectif (un ticket
        peut melanger plusieurs taux : ex. pain a 0% + patisserie a 10/20%),
        pour afficher chaque taux applique separement sur le ticket imprime."""
        groupes = {}
        for ligne in self.ticket:
            taux = self._taux_pour_ligne(ligne)
            sous_total_ttc = ligne["quantite"] * ligne["prix_unitaire"]
            sous_total_ht = sous_total_ttc / (1 + taux / 100)
            montant_tva = sous_total_ttc - sous_total_ht
            groupe = groupes.setdefault(taux, {"taux": taux, "base_ht": 0.0, "montant": 0.0})
            groupe["base_ht"] += sous_total_ht
            groupe["montant"] += montant_tva
        return [groupes[taux] for taux in sorted(groupes)]

    def _totaux_ticket(self):
        """Totaux du ticket en cours (HT, TVA, TTC, repartition par taux),
        remise globale (%) deja appliquee uniformement sur chaque taux."""
        repartition_brute = self._repartition_tva()
        facteur = 1 - (self.remise_pourcentage / 100)
        repartition_tva = [
            {"taux": g["taux"], "base_ht": g["base_ht"] * facteur, "montant": g["montant"] * facteur}
            for g in repartition_brute
        ]
        total_ht = sum(g["base_ht"] for g in repartition_tva)
        total_tva = sum(g["montant"] for g in repartition_tva)
        total_ttc = total_ht + total_tva
        return total_ht, total_tva, total_ttc, repartition_tva

    def _ouvrir_remise(self):
        PaveNumerique(
            self, titre="Remise sur le ticket (%)",
            callback_validation=self._definir_remise,
            chiffres_max=5, permettre_decimales=True,
        )

    def _definir_remise(self, valeur):
        self.remise_pourcentage = min(valeur, 100)
        self._rafraichir_ticket()

    def _retirer_remise(self):
        self.remise_pourcentage = 0
        self._rafraichir_ticket()

    def _encaisser(self):
        if not self.ticket:
            messagebox.showinfo("Ticket vide", "Aucun article dans le ticket.")
            return
        self._demander_mode_paiement(self._finaliser_encaissement)

    def _demander_mode_paiement(self, callback):
        popup = tk.Toplevel(self)
        popup.title("Mode de paiement")
        popup.configure(bg=BLANC)
        popup.resizable(False, False)
        popup.transient(self)

        tk.Label(popup, text="Mode de paiement", font=POLICE_SOUS_TITRE, bg=BLANC, fg=BRUN_700,
                 pady=14).pack(fill="x")

        def choisir(mode):
            popup.destroy()
            callback(mode)

        BoutonArrondi(
            popup, lignes=[("ESPECES", ("Segoe UI", 28, "bold"), BLANC)], commande=lambda: choisir("especes"),
            largeur=420, hauteur=100, rayon=16, couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
        ).pack(pady=(8, 12))
        BoutonArrondi(
            popup, lignes=[("CARTE", ("Segoe UI", 28, "bold"), BLANC)], commande=lambda: choisir("carte"),
            largeur=420, hauteur=100, rayon=16, couleur_fond=OR, couleur_bordure=OR, bg=BLANC,
        ).pack(pady=(0, 16))
        BoutonArrondi(
            popup, lignes=[("Annuler", ("Segoe UI", 16, "bold"), BLANC)], commande=popup.destroy,
            largeur=420, hauteur=60, rayon=12, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(pady=(0, 20))

        popup.update_idletasks()
        largeur, hauteur = max(520, popup.winfo_reqwidth()), max(420, popup.winfo_reqheight())
        x = self.winfo_rootx() + (self.winfo_width() - largeur) // 2
        y = self.winfo_rooty() + (self.winfo_height() - hauteur) // 2
        popup.geometry("{}x{}+{}+{}".format(largeur, hauteur, max(x, 0), max(y, 0)))
        popup.grab_set()

    def _finaliser_encaissement(self, mode_paiement):
        total_ht, total_tva, total_ttc, repartition_tva = self._totaux_ticket()
        remise_pourcentage = self.remise_pourcentage

        lignes_a_enregistrer = [
            {"nom": l["nom"], "quantite": l["quantite"], "prix_unitaire": l["prix_unitaire"],
             "taux_tva": self._taux_pour_ligne(l)}
            for l in self.ticket
        ]
        vente_id, maintenant = ventes.enregistrer_vente(
            self.conn, lignes_a_enregistrer, self.mode_vente, mode_paiement,
            total_ht, total_tva, total_ttc, remise_pourcentage=remise_pourcentage,
            type_vente=ventes.TYPE_DETAILLEE, vendeur_id=self._vendeur_id(),
        )

        # L'impression n'est jamais automatique : elle ne part que si le
        # caissier appuie explicitement sur "Imprimer le ticket" (dans le
        # popup de confirmation qui suit, ou plus tard via "Dernier ticket").
        self._dernier_ticket = {
            "lignes": list(self.ticket),
            "mode_vente": self.mode_vente,
            "mode_paiement": mode_paiement,
            "repartition_tva": repartition_tva,
            "remise_pourcentage": remise_pourcentage,
            "total_ht": total_ht,
            "total_tva": total_tva,
            "total_ttc": total_ttc,
            "date_heure": maintenant.strftime("%d/%m/%Y %H:%M"),
        }

        self._apres_vente(vente_id, mode_paiement,
                          lambda: self._afficher_confirmation_encaissement(total_ttc))

        self.ticket = []
        self.remise_pourcentage = 0
        self._rafraichir_ticket()

        # Retour automatique a l'ecran des categories : le client suivant ne
        # doit pas se retrouver sur le produit/categorie ou s'est arretee la
        # vente precedente, sinon il faut cliquer "< Categories" a chaque fois.
        self.categorie_active_id = None
        self.produit_sous_menu_actif = None
        self._rafraichir_ecran()

    # ------------------------------------------------------------------
    # Vendeurs (connexion par PIN)
    # ------------------------------------------------------------------
    def _vendeur_id(self):
        return self.vendeur["id"] if self.vendeur is not None else None

    def _afficher_ecran_connexion(self):
        if vendeurs.lister(self.conn, seulement_actifs=True):
            aide = ""
        else:
            aide = "Aucun vendeur : tapez le code admin pour en creer."
        self.ecran_connexion.reinitialiser(aide)
        self.ecran_connexion.place(x=0, y=0, relwidth=1, relheight=1)
        self.ecran_connexion.lift()

    def _verifier_pin_connexion(self, pin):
        vendeur = vendeurs.trouver_par_pin(self.conn, pin)
        if vendeur is not None:
            self._connexion_avec_comptage(vendeur)
            return True
        pin_admin = self.conn.execute("SELECT valeur FROM config WHERE cle = 'pin_admin'").fetchone()["valeur"]
        if pin == pin_admin:
            # le code admin ne connecte personne : il ouvre l'admin (ex:
            # creer les vendeurs la premiere fois), puis revient ici
            self._ouvrir_admin()
            self._afficher_ecran_connexion()
            return True
        return False

    def _connecter(self, vendeur):
        self.vendeur = vendeur
        self.connexion_id = vendeurs.ouvrir_connexion(self.conn, vendeur["id"])
        self.ecran_connexion.place_forget()
        self._dessiner_entete()

    def _deconnecter(self, message=""):
        self._fermer_confirmation_rapide()
        vendeurs.fermer_connexion(self.conn, self.connexion_id)
        self.vendeur = None
        self.connexion_id = None
        self._dessiner_entete()
        self._afficher_ecran_connexion()
        if message:
            self.ecran_connexion.afficher_message(message)

    # ------------------------------------------------------------------
    # Fond de caisse, releves, sorties d'especes
    # ------------------------------------------------------------------
    def _connexion_avec_comptage(self, vendeur):
        """Le vendeur a tape un bon code : avant de lui donner la caisse,
        on exige un comptage si la situation l'impose (voir
        caisse.comptage_requis_a_la_connexion)."""
        action, ancien = caisse.comptage_requis_a_la_connexion(self.conn, vendeur["id"])
        vid = vendeur["id"]
        # Prise de poste : on entre directement, pas de comptage a l'arrivee
        if action in (None, "ouverture", "releve_absente"):
            self._connecter(vendeur)
            return
        elif vendeur["sans_comptage"] and caisse.derniere_releve(self.conn) is None:
            # tout premier demarrage (apres une remise a zero) : rien a
            # reprendre, il tape simplement l'argent present dans la caisse
            tiroir.ouvrir_en_fond(tiroir.TYPE_RELEVE, motif="Fond de caisse de depart", vendeur_id=vid)

            def valider_fond(montant):
                caisse.enregistrer_releve(self.conn, caisse.OUVERTURE, montant, vid, vid,
                                          note="fond de caisse de depart (tape, non compte)")
                self._connecter(vendeur)
            PaveNumerique(self, titre="Argent dans la caisse (DH)", callback_validation=valider_fond,
                          chiffres_max=6, permettre_decimales=True, autoriser_zero=True)
        elif vendeur["sans_comptage"]:
            # le patron ne compte jamais : si le poste precedent n'a pas ete
            # cloture (fin de poste / fermeture oubliee), on le cloture sans
            # comptage (pas d'ecart pour ce vendeur), puis prise de poste auto
            avertissement = None
            if action in ("releve_absente", "fermeture_oubliee"):
                type_cloture = caisse.CHANGEMENT if action == "releve_absente" else caisse.FERMETURE
                nom_ancien = vendeurs.nom(self.conn, ancien) or "?"
                caisse.enregistrer_releve(
                    self.conn, type_cloture, caisse.calcul_attendu(self.conn)["attendu"], ancien, vid,
                    note="sans comptage : poste de {} cloture a l'arrivee du patron".format(nom_ancien),
                    sans_comptage=True)
                avertissement = ("Attention : la fin de poste de {} n'a pas ete comptee "
                                 "(pas d'ecart pour son poste).".format(nom_ancien))
            self._prise_de_poste_sans_comptage(vendeur, avertissement)
        elif action == "ouverture":
            def valider(montant, details):
                caisse.enregistrer_releve(self.conn, caisse.OUVERTURE, montant, vid, vid, details=details)
                self._connecter(vendeur)
            self._demander_comptage("Comptage du soir (pieces pesees)", valider, vendeur_id=vid)
        elif action == "fermeture_oubliee":
            def valider(montant, details):
                caisse.enregistrer_releve(self.conn, caisse.FERMETURE, montant, ancien, vid,
                                          note="caisse non fermee, comptee le jour suivant", details=details)
                caisse.enregistrer_releve(self.conn, caisse.OUVERTURE, montant, vid, vid, details=details)
                self._connecter(vendeur)
            self._demander_comptage("Comptage du soir (pieces pesees)", valider, vendeur_id=vid)
        else:  # releve_absente
            def valider(montant, details):
                caisse.enregistrer_releve(self.conn, caisse.CHANGEMENT, montant, ancien, vid,
                                          note="fin de poste non faite, comptee par le vendeur suivant",
                                          details=details)
                caisse.enregistrer_releve(self.conn, caisse.OUVERTURE, montant, vid, vid, details=details)
                self._connecter(vendeur)
            self._demander_comptage("Comptage du soir (pieces pesees)", valider, vendeur_id=vid)

    def _prise_de_poste_sans_comptage(self, vendeur, avertissement=None):
        """Le patron ne compte pas en arrivant : le fond de caisse reprend
        le dernier comptage, qui lui est affiche (qui a compte, quand,
        combien, detail pieces / billets)."""
        precedent = caisse.derniere_releve_comptee(self.conn)
        montant = caisse.prise_de_poste_sans_comptage(self.conn, vendeur["id"])
        self._connecter(vendeur)
        texte = "Fond de caisse repris : {:g} DH".format(montant)
        if precedent is not None:
            texte += "\n\nDernier comptage : {} de {}\nle {}/{} a {} : {:g} DH".format(
                caisse.LIBELLES.get(precedent["type"], precedent["type"]).lower(),
                vendeurs.nom(self.conn, precedent["compte_par_id"] or precedent["vendeur_id"]) or "?",
                precedent["date"][8:10], precedent["date"][5:7], precedent["heure"][:5],
                precedent["montant_compte"])
            resume = comptage.resume_details(self.conn, precedent["id"])
            if resume:
                texte += "\n" + resume
        if avertissement:
            texte += "\n\n" + avertissement
        dialogues.Message(self, "Prise de poste sans comptage", texte,
                          niveau="attention" if avertissement else "info")

    def _demander_comptage(self, titre, callback, vendeur_id=None):
        """Ouvre le tiroir puis l'ecran de comptage (feuille de caisse :
        pieces pesees + billets comptes). Appelle callback(total, details)
        apres confirmation. Le vendeur ne voit jamais l'attendu ni l'ecart."""
        vid = vendeur_id if vendeur_id is not None else self._vendeur_id()
        tiroir.ouvrir_en_fond(tiroir.TYPE_RELEVE, motif=titre, vendeur_id=vid)
        EcranComptage(self, self.conn, titre, callback, sous_titre=vendeurs.nom(self.conn, vid) or "")

    def _ticket_vide_sinon_prevenir(self):
        if self.ticket:
            dialogues.Message(
                self, "Ticket en cours",
                "Encaissez ou videz le ticket en cours d'abord.",
                niveau="attention",
            )
            return False
        return True

    def _ouvrir_menu_caisse(self):
        self._fermer_confirmation_rapide()
        dialogues.Menu(self, "Caisse - {}".format(self.vendeur["nom"]), [
            ("Fin de poste", self._changer_vendeur, BRUN_700),
            ("Annuler une vente", self._ouvrir_gestion_ventes, ROSE),
            ("Fermer la caisse", self._fermer_caisse, ROUGE),
        ])

    def _relever_coffre_patron(self):
        """Le patron vide le coffre et tape ce qu'il a trouve (compare aux
        depots enregistres par les vendeurs)."""
        attendu, nb, _ = caisse.coffre_attendu(self.conn)

        def enregistrer(montant):
            attendu_, ecart = caisse.enregistrer_releve_coffre(self.conn, montant)
            dialogues.Message(self, "Releve du coffre",
                              "Trouve : {:g} DH\nDepots enregistres : {:g} DH ({} depots)\nEcart : {:+g} DH".format(
                                  montant, attendu_, nb, ecart),
                              niveau="info" if comptage.dans_tolerance(self.conn, ecart) else "erreur")
        PaveNumerique(self, titre="Total trouve dans le coffre (DH)", callback_validation=enregistrer,
                      chiffres_max=8, permettre_decimales=True, autoriser_zero=True)

    # ------------------------------------------------------------------
    # Gestion des ventes : annulation (voir annulations.py)
    # ------------------------------------------------------------------
    def _ouvrir_gestion_ventes(self):
        gestion_ventes.FenetreGestionVentes(self, self.conn, self._vendeur_id(), self._apres_annulation)

    def _apres_annulation(self, annulation, vente, apres_fin=None):
        """Vente annulee (deja enregistree) : "Dernier ticket" ne doit plus
        la reimprimer ; especes rendues -> ouverture du tiroir (journalisee)
        ; carte -> rappeler d'annuler aussi sur le terminal carte."""
        self._dernier_ticket = None
        self._charger_dernier_ticket_depuis_db()
        montant = annulation["montant"]
        if annulation["mode_paiement"] == "especes" and annulation["rembourse_tiroir"]:
            tiroir.ouvrir_en_fond(
                tiroir.TYPE_ANNULATION,
                motif="Annulation vente {} ({})".format(vente["id"], annulation["motif"]),
                vente_id=vente["id"], vendeur_id=self._vendeur_id(),
            )
            texte = "Rendez {:g} DH au client.".format(montant)
            dialogues.Message(self, "Vente annulee", texte, niveau="attention", callback_ok=apres_fin)
        elif annulation["mode_paiement"] == "especes":
            dialogues.Message(self, "Vente annulee",
                              "Correction enregistree.\nAucun argent ne sort du tiroir.",
                              callback_ok=apres_fin)
        else:
            dialogues.Message(self, "Vente carte annulee",
                              "{:g} DH retires des ventes.\n\nAnnulez aussi le paiement "
                              "sur le terminal carte (TPE).".format(montant),
                              niveau="attention", callback_ok=apres_fin)

    def _est_patron(self):
        return self.vendeur is not None and bool(self.vendeur["sans_comptage"])

    def _depart_patron(self, type_releve, message_fin):
        """Depart simplifie : on deconnecte directement."""
        vid = self._vendeur_id()
        attendu = caisse.calcul_attendu(self.conn)["attendu"]
        caisse.depart_sans_comptage(self.conn, type_releve, attendu, vid)
        self._deconnecter(message_fin)

    def _changer_vendeur(self):
        if not self._ticket_vide_sinon_prevenir():
            return
        if self._est_patron():
            self._depart_patron(caisse.CHANGEMENT, "Poste termine.")
            return
        vid = self._vendeur_id()

        def valider(montant, details):
            caisse.enregistrer_releve(self.conn, caisse.CHANGEMENT, montant, vid, vid, details=details)
            self._deconnecter("Poste termine. Vendeur suivant : tapez votre code.")
        self._demander_comptage("Fin de poste : comptez le tiroir", valider)

    def _fermer_caisse(self):
        if not self._ticket_vide_sinon_prevenir():
            return
        if self._est_patron():
            self._depart_patron(caisse.FERMETURE, "Caisse fermee. A demain !")
            return
        vid = self._vendeur_id()

        def valider(montant, details):
            caisse.enregistrer_releve(self.conn, caisse.FERMETURE, montant, vid, vid, details=details)
            self._deconnecter("Caisse fermee. A demain !")
        self._demander_comptage("Fermeture du soir : comptez le tiroir", valider)

    def _depot_coffre(self):
        """Le vendeur retire des gros billets du tiroir, les compte, et les
        met dans la boite (coffre). Le montant est deduit de l'attendu du
        tiroir et s'ajoute a l'attendu du coffre."""
        vid = self._vendeur_id()
        tiroir.ouvrir_en_fond(tiroir.TYPE_SORTIE, motif=caisse.MOTIF_DEPOT_COFFRE, vendeur_id=vid)

        def enregistrer(montant):
            # pas de message apres : la confirmation qui precede suffit
            caisse.enregistrer_depot_coffre(self.conn, montant, vid)

        def confirmer(montant):
            dialogues.confirmer(self, "Confirmer le depot",
                                "Vous mettez {:g} DH au coffre.\nC'est bien ca ?".format(montant),
                                "Confirmer", lambda: enregistrer(montant))

        PaveNumerique(self, titre="Montant mis au coffre (DH)", callback_validation=confirmer,
                      chiffres_max=6, permettre_decimales=False)

    def _sortie_especes(self):
        def choisir_motif(montant):
            dialogues.ChoixMotif(self, "Sortie de {:g} DH".format(montant), caisse.MOTIFS_SORTIE,
                                 lambda motif: enregistrer(montant, motif))

        def enregistrer(montant, motif):
            caisse.enregistrer_sortie(self.conn, montant, motif, self._vendeur_id())
            tiroir.ouvrir_en_fond(tiroir.TYPE_SORTIE, motif="{} ({:g} DH)".format(motif, montant),
                                  vendeur_id=self._vendeur_id())

        PaveNumerique(self, titre="Montant sorti du tiroir (DH)", callback_validation=choisir_motif,
                      chiffres_max=8, permettre_decimales=True)

    def _quitter(self):
        vendeurs.fermer_connexion(self.conn, self.connexion_id)
        self.destroy()

    # ------------------------------------------------------------------
    # Tiroir-caisse
    # ------------------------------------------------------------------
    def _apres_vente(self, vente_id, mode_paiement, afficher_confirmation):
        """Apres CHAQUE vente enregistree : ouvre le tiroir si paiement en
        especes, puis affiche la confirmation. Si le tiroir n'a pas pu
        s'ouvrir, la vente reste enregistree ; on previent d'abord."""
        if mode_paiement != "especes":
            afficher_confirmation()
            return
        tiroir.ouvrir_en_fond(tiroir.TYPE_VENTE, vente_id=vente_id, vendeur_id=self._vendeur_id())
        # imprimante volontairement eteinte la plupart du temps : la vente
        # est enregistree, l'echec d'ouverture est seulement note dans le
        # journal du tiroir, sans message bloquant (le tiroir s'ouvre a la cle)
        afficher_confirmation()

    def _ouvrir_tiroir_sans_vente(self):
        self._fermer_confirmation_rapide()
        dialogues.ChoixMotif(self, "Ouvrir sans vente", tiroir.MOTIFS_SANS_VENTE,
                             self._confirmer_ouverture_sans_vente)

    def _confirmer_ouverture_sans_vente(self, motif):
        ok, erreur = tiroir.ouvrir(self.conn, tiroir.TYPE_SANS_VENTE, motif=motif,
                                  vendeur_id=self._vendeur_id())
        if not ok:
            dialogues.Message(
                self, "Tiroir non ouvert",
                "Le tiroir n'a pas pu s'ouvrir.\nVerifiez l'imprimante.\n\n({})".format(str(erreur)[:70]),
                niveau="erreur",
            )

    # ------------------------------------------------------------------
    # Vente rapide (montant tape directement)
    # ------------------------------------------------------------------
    def _ouvrir_vente_rapide(self):
        self._fermer_confirmation_rapide()
        noms_categories = [
            row["nom"] for row in self.conn.execute("SELECT nom FROM categories ORDER BY ordre, id").fetchall()
        ]
        libelle_mode = "Sur place" if self.mode_vente == "sur_place" else "A emporter"
        # ticket detaille en cours : le montant tape devient une ligne
        # "Vente rapide" de ce ticket (ticket mixte), pas une vente a part
        FenetreVenteRapide(self, noms_categories, libelle_mode, self._sur_validation_rapide,
                           mode_ajout=bool(self.ticket))

    def _sur_validation_rapide(self, montant, nom_categorie, mode_paiement):
        if mode_paiement == AJOUT_TICKET:
            self._ajouter_ligne_prix_libre(montant, nom_categorie)
        else:
            self._encaisser_vente_rapide(montant, nom_categorie, mode_paiement)

    def _ajouter_ligne_prix_libre(self, montant, nom_categorie):
        """Ligne "Vente rapide" au prix tape.
        Pain = 0% toujours.
        Autres categories = 10% sur place, 20% a emporter."""
        nom = "Vente rapide - {}".format(nom_categorie) if nom_categorie else "Vente rapide"
        if nom_categorie == "Pain":
            tva_fixe = 0.0   # toujours 0%
        else:
            tva_fixe = None  # calcule selon le mode au moment du ticket
        self._ajouter_au_ticket(nom, round(float(montant), 2), 1, tva_fixe)

    def _encaisser_vente_rapide(self, montant, nom_categorie, mode_paiement):
        lignes, total_ht, total_tva, total_ttc, repartition = ventes.preparer_vente_rapide(
            self.conn, montant, nom_categorie, self.mode_vente, self.taux_tva[self.mode_vente],
        )
        vente_id, maintenant = ventes.enregistrer_vente(
            self.conn, lignes, self.mode_vente, mode_paiement, total_ht, total_tva, total_ttc,
            type_vente=ventes.TYPE_RAPIDE, categorie_rapide=nom_categorie,
            vendeur_id=self._vendeur_id(),
        )
        self._dernier_ticket = {
            "lignes": lignes,
            "mode_vente": self.mode_vente,
            "mode_paiement": mode_paiement,
            "repartition_tva": repartition,
            "remise_pourcentage": 0,
            "total_ht": total_ht,
            "total_tva": total_tva,
            "total_ttc": total_ttc,
            "date_heure": maintenant.strftime("%d/%m/%Y %H:%M"),
        }
        self._apres_vente(vente_id, mode_paiement,
                          lambda: self._afficher_confirmation_rapide(total_ttc, mode_paiement))

    DUREE_CONFIRMATION_RAPIDE_MS = 1500

    def _afficher_confirmation_rapide(self, total, mode_paiement):
        """Confirmation courte qui disparait seule (pas de bouton OK a
        viser) : en rush, le client suivant attend deja. Un tap dessus, ou
        un nouvel appui sur VENTE RAPIDE, la ferme immediatement. Le ticket
        reste imprimable via 'Dernier ticket'."""
        self._fermer_confirmation_rapide()
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        couleur = VERT if mode_paiement == "especes" else OR
        popup.configure(bg=couleur)
        largeur, hauteur = 420, 200
        x = self.winfo_rootx() + (self.winfo_width() - largeur) // 2
        y = self.winfo_rooty() + (self.winfo_height() - hauteur) // 2
        popup.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))
        texte_paiement = "Especes" if mode_paiement == "especes" else "Carte"
        tk.Label(popup, text="Encaisse - {}".format(texte_paiement), font=("Segoe UI", 20, "bold"),
                 bg=couleur, fg=BLANC).pack(pady=(28, 4))
        tk.Label(popup, text="{:g} DH".format(total), font=("Segoe UI", 48, "bold"),
                 bg=couleur, fg=BLANC).pack()
        for widget in (popup,) + tuple(popup.winfo_children()):
            widget.bind("<Button-1>", lambda e: self._fermer_confirmation_rapide())
        self._popup_confirmation_rapide = popup
        self._job_confirmation_rapide = self.after(self.DUREE_CONFIRMATION_RAPIDE_MS,
                                                   self._fermer_confirmation_rapide)

    def _fermer_confirmation_rapide(self):
        job = getattr(self, "_job_confirmation_rapide", None)
        if job is not None:
            self.after_cancel(job)
            self._job_confirmation_rapide = None
        popup = getattr(self, "_popup_confirmation_rapide", None)
        if popup is not None and popup.winfo_exists():
            popup.destroy()
        self._popup_confirmation_rapide = None

    def _charger_dernier_ticket_depuis_db(self):
        """Reconstruit `self._dernier_ticket` a partir de la derniere vente
        enregistree en base, pour que "Dernier ticket" fonctionne meme apres
        un redemarrage du logiciel (client qui redemande son ticket plus
        tard). Utilise le taux de TVA fige au moment de la vente (colonne
        vente_lignes.taux_tva), jamais le taux courant."""
        vente = self.conn.execute(
            "SELECT * FROM ventes WHERE COALESCE(annulee, 0) = 0 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if vente is None:
            return
        lignes_db = self.conn.execute(
            "SELECT * FROM vente_lignes WHERE vente_id = ? ORDER BY id", (vente["id"],)
        ).fetchall()
        if not lignes_db:
            return

        # les lignes gardent leur prix nominal (avant remise) : on applique
        # ici le meme facteur de remise que celui fige au moment de la
        # vente pour retrouver la repartition de TVA telle qu'imprimee
        remise_pourcentage = vente["remise_pourcentage"] or 0
        facteur = 1 - (remise_pourcentage / 100)
        groupes = {}
        for ligne in lignes_db:
            taux = ligne["taux_tva"] if ligne["taux_tva"] is not None else 0
            sous_total_ttc = ligne["quantite"] * ligne["prix_unitaire"]
            sous_total_ht = sous_total_ttc / (1 + taux / 100)
            montant_tva = sous_total_ttc - sous_total_ht
            groupe = groupes.setdefault(taux, {"taux": taux, "base_ht": 0.0, "montant": 0.0})
            groupe["base_ht"] += sous_total_ht * facteur
            groupe["montant"] += montant_tva * facteur

        try:
            date_heure = datetime.strptime(
                "{} {}".format(vente["date"], vente["heure"]), "%Y-%m-%d %H:%M:%S"
            ).strftime("%d/%m/%Y %H:%M")
        except ValueError:
            date_heure = "{} {}".format(vente["date"], vente["heure"])

        self._dernier_ticket = {
            "lignes": [
                {"nom": l["nom_produit"], "prix_unitaire": l["prix_unitaire"], "quantite": l["quantite"]}
                for l in lignes_db
            ],
            "mode_vente": vente["mode_vente"] or "a_emporter",
            "mode_paiement": vente["mode_paiement"] or "especes",
            "repartition_tva": [groupes[taux] for taux in sorted(groupes)],
            "remise_pourcentage": remise_pourcentage,
            "total_ht": vente["total_ht"] if vente["total_ht"] is not None else vente["total"],
            "total_tva": vente["total_tva"] if vente["total_tva"] is not None else 0,
            "total_ttc": vente["total"],
            "date_heure": date_heure,
        }

    def _imprimer_dernier_ticket(self):
        if self._dernier_ticket is None:
            dialogues.Message(self, "Aucun ticket", "Aucune vente n'a encore ete enregistree.")
            return
        t = self._dernier_ticket
        nom_imprimante = database.obtenir_nom_imprimante(self.conn)
        try:
            impression.imprimer_ticket(
                nom_imprimante, t["lignes"], t["mode_vente"], t["mode_paiement"],
                t["repartition_tva"], t["total_ht"], t["total_tva"], t["total_ttc"],
                t["date_heure"], chemin_logo=database.obtenir_chemin_logo(self.conn) or None,
                remise_pourcentage=t.get("remise_pourcentage", 0),
            )
        except impression.ImprimanteInjoignable:
            dialogues.Message(
                self, "Ticket non imprime",
                "L'imprimante est eteinte ou debranchee.\n"
                "Le ticket est annule : il ne sortira pas plus tard.\n\n"
                "Allumez l'imprimante puis appuyez sur 'Dernier ticket'.",
                niveau="attention",
            )
        except Exception as exc:
            dialogues.Message(
                self, "Erreur impression",
                "Impossible d'imprimer sur '{}'.\nVerifiez l'imprimante (Mode Admin).\n\n({})".format(
                    nom_imprimante, str(exc)[:70]),
                niveau="erreur",
            )

    def _afficher_confirmation_encaissement(self, total):
        """Grande confirmation visuelle (plus lisible qu'une boite de dialogue
        systeme standard). Reste affichee tant que le bouton OK n'est pas
        presse (et bloque le reste de l'ecran pendant ce temps) : une mouche
        ou un effleurement accidentel sur l'ecran tactile ne peut donc pas la
        faire disparaitre ni declencher autre chose derriere.

        Imprimer (en haut) et OK (tout en bas) sont volontairement tres
        eloignes l'un de l'autre - "Vente encaissee" + le montant occupent
        tout l'espace entre les deux, au milieu : rapproches, un caissier
        presse pouvait appuyer sur OK en visant Imprimer (ou l'inverse) juste
        apres avoir encaisse."""
        popup = tk.Toplevel(self)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=ROSE)

        largeur, hauteur = 560, 600
        x = self.winfo_rootx() + (self.winfo_width() - largeur) // 2
        y = self.winfo_rooty() + (self.winfo_height() - hauteur) // 2
        popup.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))

        # OK et Imprimer sont empaquetes en 1er (avec side="top"/"bottom")
        # pour rester colles en haut/en bas quelle que soit la taille prise
        # par le texte au milieu.
        BoutonArrondi(
            popup, lignes=[("Imprimer le ticket", ("Segoe UI", 16, "bold"), ROSE)],
            commande=self._imprimer_dernier_ticket, largeur=320, hauteur=54, rayon=14,
            couleur_fond=BLANC, couleur_bordure=BLANC, bg=ROSE,
        ).pack(side="top", pady=(36, 0))
        BoutonArrondi(
            popup, lignes=[("OK", ("Segoe UI", 26, "bold"), ROSE)],
            commande=popup.destroy, largeur=220, hauteur=70, rayon=16,
            couleur_fond=BLANC, couleur_bordure=BLANC, bg=ROSE,
        ).pack(side="bottom", pady=(0, 32))

        # "Vente encaissee" + montant : centres (horizontalement ET
        # verticalement) dans tout l'espace restant entre les 2 boutons.
        zone_centre = tk.Frame(popup, bg=ROSE)
        zone_centre.pack(side="top", fill="both", expand=True)
        bloc_texte = tk.Frame(zone_centre, bg=ROSE)
        bloc_texte.pack(expand=True)
        tk.Label(bloc_texte, text="Vente encaissee", font=("Segoe UI", 30, "bold"),
                 bg=ROSE, fg=BLANC).pack(pady=(0, 10))
        tk.Label(bloc_texte, text="{:g} DH".format(total), font=("Segoe UI", 60, "bold"),
                 bg=ROSE, fg=BLANC).pack()

        popup.grab_set()  # bloque le reste de l'ecran tant que OK n'est pas presse


def _ecrire_diagnostic_demarrage():
    """Affiche + enregistre (diagnostic_ecran.log, a cote du programme) la
    version lancee et ce que Windows/Tkinter detectent sur ce poste. Sert a
    verifier a distance, sans ambiguite, si un probleme d'affichage vient
    d'une mauvaise detection d'ecran ou d'autre chose (ex: ancienne version
    encore lancee par erreur)."""
    dossier = _dossier_application()
    texte = "Version app : {}\nTaille fenetre max autorisee : {}x{}\n{}".format(
        VERSION_APP, LARGEUR_FENETRE_MAX, HAUTEUR_FENETRE_MAX, diagnostiquer_ecran(),
    )
    print("=== Diagnostic ecran ===")
    print(texte)
    print("========================")
    try:
        chemin_log = os.path.join(dossier, "diagnostic_ecran.log")
        with open(chemin_log, "w", encoding="utf-8") as f:
            f.write(texte + "\n")
    except OSError as exc:
        print("(Impossible d'ecrire diagnostic_ecran.log : {})".format(exc))


if __name__ == "__main__":
    definir_dpi_awareness()
    _ecrire_diagnostic_demarrage()

    conn_init = database.get_connection()
    database.init_db(conn_init)
    database.seed_test_data(conn_init)
    remise_a_zero.appliquer_si_demandee(conn_init)
    conn_init.close()

    app = CaisseApp()
    # envoi vers Google Sheets en arriere-plan (ne bloque jamais la caisse)
    sync.demarrer()
    app.mainloop()
