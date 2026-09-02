# -*- coding: utf-8 -*-
"""
Etape 3 : ecran de caisse + pave numerique de quantite pour "Hubert & Pessina".

- Clic normal sur une tuile (produit simple ou parfum) = +1 unite.
- Petit badge "123" dans le coin de la tuile = ouvre le pave numerique pour
  ajouter une quantite precise en un seul coup.

Pas encore de mode admin / historique (etapes 4 et 5).
"""

import os
import sys
import unicodedata
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import database
import impression
from admin import FenetreAdmin
from historique import FenetreHistorique, FenetreRecap, FenetrePeriode
from pave_numerique import PaveNumerique
from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROSE, ROUGE, VERT, COULEURS_CATEGORIES,
    HEADER_DEGRADE_GAUCHE, HEADER_DEGRADE_DROITE, POLICE_BADGE, POLICE_CATEGORIE, POLICE_CATEGORIE_CAISSE,
    POLICE_ENCAISSER, POLICE_PRODUIT_HINT, POLICE_PRODUIT_NOM, POLICE_PRODUIT_PRIX,
    POLICE_SOUS_TITRE, POLICE_TICKET_DETAIL, POLICE_TICKET_NOM, POLICE_TICKET_TITRE,
    POLICE_TITRE, POLICE_TOTAL, POLICE_BOUTON_ROND,
    BoutonArrondi, ScrollableFrame, rectangle_arrondi,
    definir_dpi_awareness, diagnostiquer_ecran, zone_travail_windows,
    calculer_grille_adaptative, police_echelle, police_ajustee_a_largeur,
    polices_ajustees_a_hauteur, HAUTEUR_PIED_TUILE,
)

# A incrementer a chaque changement visible de l'ecran de caisse : s'affiche
# dans le titre de la fenetre pour verifier sans ambiguite, en cas de doute,
# que la version testee sur un poste est bien la derniere (et pas un ancien
# .exe reste sur le PC).
VERSION_APP = "2026-08-14.2"

# Pictogrammes des pastilles de categories (dossier a cote de caisse.db,
# donc a cote de l'exe une fois empaquete - meme logique que le logo du
# ticket). Categorie sans correspondance -> pas d'icone, juste le texte.
DOSSIER_ICONES_CATEGORIES = os.path.join(os.path.dirname(database.DB_PATH), "icones_categories")
ICONES_CATEGORIES = {
    "Pain": "pain.png",
    "Viennoiserie": "viennoiserie.png",
    "Sablé": "biscuits.png",
    "Tarte": "tartes.png",
    "Patisserie": "patisseries.png",
    "Salé": "sandwichs.png",
    "Evenement": "gateaux.png",
    "Divers": "bonbons.png",
    "Boissons": "boissons.png",
}


def _normaliser_nom_categorie(nom):
    """Enleve accents/casse pour comparer les noms de facon tolerante :
    le nom d'une categorie est libre (saisi dans le Mode Admin, souvent au
    pluriel - "Tartes", "Sables"...) alors que ICONES_CATEGORIES ci-dessus
    liste des noms figes (souvent au singulier) - une correspondance exacte
    ratait donc la plupart des categories reelles du magasin."""
    sans_accents = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode("ascii")
    return sans_accents.strip().lower()


def _chemin_icone_categorie(nom_categorie):
    cible = _normaliser_nom_categorie(nom_categorie)
    for nom_cle, nom_fichier in ICONES_CATEGORIES.items():
        cle = _normaliser_nom_categorie(nom_cle)
        if cible == cle or cible.startswith(cle) or cle.startswith(cible):
            chemin = os.path.join(DOSSIER_ICONES_CATEGORIES, nom_fichier)
            return chemin if os.path.isfile(chemin) else None
    return None


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
    LARGEUR_ZONE_TICKET = 300  # panneau de droite (ticket) ; le reste va aux categories/produits

    def __init__(self):
        super().__init__()
        self.title("Hubert & Pessina - Caisse [{}]".format(VERSION_APP))
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

        # --- zone de gauche : categories OU produits (un seul ecran a la fois,
        # pour laisser toute la place a de grandes pastilles de categories) ---
        zone_gauche = tk.Frame(corps, bg=CREME)
        zone_gauche.pack(side="left", fill="both", expand=True)

        self.zone_produits_scroll = ScrollableFrame(zone_gauche, bg=CREME)
        self.zone_produits_scroll.pack(side="top", fill="both", expand=True, padx=14, pady=14)
        self.frame_produits = self.zone_produits_scroll.interior
        # Sur le canvas (taille reellement visible), pas sur frame_produits
        # (qui grandit avec son contenu) : c'est cette taille visible qu'il
        # faut remplir au mieux avec les tuiles, sans jamais avoir a scroller.
        # add="+" : ScrollableFrame a deja son propre bind sur ce meme
        # evenement (pour synchroniser sa largeur avec le canvas) - sans
        # add="+", notre bind le remplacerait au lieu de s'y ajouter, et la
        # largeur interne resterait bloquee a sa valeur initiale (1px).
        self.zone_produits_scroll.canvas.bind("<Configure>", self._sur_redimensionnement_zone_produits, add="+")

    def _construire_entete(self):
        self.canvas_entete = tk.Canvas(self, height=72, highlightthickness=0, bg=CREME)
        self.canvas_entete.pack(side="top", fill="x")
        self.canvas_entete.bind("<Configure>", self._dessiner_entete)
        self.canvas_entete.bind("<Button-1>", self._sur_clic_entete)
        self._zones_boutons_entete = {}

    def _dessiner_entete(self, event=None):
        canvas = self.canvas_entete
        canvas.delete("all")
        w = event.width if event else canvas.winfo_width()
        h = event.height if event else canvas.winfo_height()
        if w <= 1:
            return

        c1 = HEADER_DEGRADE_GAUCHE.lstrip("#")
        c2 = HEADER_DEGRADE_DROITE.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        pas = 6
        for x in range(0, w, pas):
            t = x / float(w)
            r = int(r1 + (r2 - r1) * t)
            g = int(g1 + (g2 - g1) * t)
            b = int(b1 + (b2 - b1) * t)
            couleur = "#{:02x}{:02x}{:02x}".format(r, g, b)
            canvas.create_rectangle(x, 0, x + pas, h, fill=couleur, outline=couleur)

        # badge "Temara" en haut a gauche
        rectangle_arrondi(canvas, 14, 12, 90, 34, 10, fill=OR, outline=OR)
        canvas.create_text(52, 23, text="Temara", font=POLICE_BADGE, fill=BLANC)

        # titre centre
        canvas.create_text(w / 2, h / 2 + 6, text="Hubert & Pessina", font=POLICE_TITRE, fill=BLANC)

        # boutons "Historique" / "Recap" / "Admin" en haut a droite (proteges par PIN)
        self._zones_boutons_entete = {}
        by1 = 16
        by2 = by1 + 34
        bx2 = w - 14
        for cle, texte in (
            ("admin", "Admin"), ("recap", "Recap"), ("historique", "Historique"), ("periode", "Periode"),
        ):
            bx1 = bx2 - 90
            self._zones_boutons_entete[cle] = (bx1, by1, bx2, by2)
            rectangle_arrondi(canvas, bx1, by1, bx2, by2, 10, fill="#d16a91", outline=BLANC)
            canvas.create_text((bx1 + bx2) / 2, (by1 + by2) / 2, text=texte, font=POLICE_BADGE, fill=BLANC)
            bx2 = bx1 - 8

    def _sur_clic_entete(self, event):
        for cle, (x1, y1, x2, y2) in self._zones_boutons_entete.items():
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                if cle == "admin":
                    self._demander_pin(self._ouvrir_admin)
                elif cle == "historique":
                    self._demander_pin(self._ouvrir_historique)
                elif cle == "recap":
                    self._demander_pin(self._ouvrir_recap)
                elif cle == "periode":
                    self._demander_pin(self._ouvrir_periode)
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
        self._rafraichir_ecran()
        self._rafraichir_ticket()

    def _ouvrir_historique(self):
        FenetreHistorique(self, self.conn)

    def _ouvrir_recap(self):
        FenetreRecap(self, self.conn)

    def _ouvrir_periode(self):
        FenetrePeriode(self, self.conn)

    def _construire_ticket(self, zone_ticket):
        # Les zones du haut et du bas ont une taille FIXE (pack_propagate
        # desactive) : sur un petit ecran (1024x768 constate en magasin),
        # sans cela le gestionnaire pack peut se mettre a compresser
        # ENCAISSER et les autres boutons bien en-dessous de leur taille
        # prevue plutot que de les garder lisibles/cliquables. Seule la
        # liste des articles au milieu (zone_lignes_scroll) est elastique :
        # c'est elle qui retrecit (avec defilement) si la place manque.
        zone_haut = tk.Frame(zone_ticket, bg=BLANC, height=160)
        zone_haut.pack(side="top", fill="x")
        zone_haut.pack_propagate(False)

        tk.Label(
            zone_haut, text="Ticket en cours", font=POLICE_TICKET_TITRE,
            bg=BLANC, fg=BRUN_700, pady=8,
        ).pack(side="top", fill="x")

        cadre_mode = tk.Frame(zone_haut, bg=BLANC)
        cadre_mode.pack(side="top", fill="x", padx=14, pady=(0, 8))
        self.boutons_mode_vente = {}
        # Largeur reelle approximative de chaque bouton une fois le panneau
        # ticket (300px) reduit et les 2 boutons cote a cote : sans ajuster
        # la police au texte le plus long ("A emporter"), il pouvait
        # deborder/etre tronque et devenir illisible sur le fond fonce.
        largeur_bouton_mode = (self.LARGEUR_ZONE_TICKET - 28 - 16) // 2
        for mode, texte in (("sur_place", "Sur place"), ("a_emporter", "A emporter")):
            police = police_ajustee_a_largeur(texte, POLICE_BOUTON_ROND, largeur_bouton_mode - 16, taille_min=10)
            bouton = BoutonArrondi(
                cadre_mode, lignes=[(texte, police, BRUN_700)],
                commande=lambda m=mode: self._definir_mode_vente(m),
                largeur=largeur_bouton_mode, hauteur=44, rayon=10,
                couleur_fond=BLANC, couleur_bordure=BRUN_200, bg=BLANC,
            )
            bouton.pack(side="left", fill="x", expand=True, padx=4)
            self.boutons_mode_vente[mode] = bouton
        self._rafraichir_mode_vente()

        # Reimpression a tout moment de la derniere vente encaissee (client
        # qui redemande son ticket apres coup) : toujours accessible sans
        # avoir a repasser par le popup de fin d'encaissement.
        BoutonArrondi(
            zone_haut, lignes=[("Dernier ticket", POLICE_BOUTON_ROND, BRUN_700)],
            commande=self._imprimer_dernier_ticket, largeur=372, hauteur=32, rayon=8,
            couleur_fond=BLANC, couleur_bordure=BRUN_200, bg=BLANC,
        ).pack(side="top", padx=14, fill="x")

        self.zone_lignes_scroll = ScrollableFrame(zone_ticket, bg=BLANC)
        self.zone_lignes_scroll.pack(side="top", fill="both", expand=True, padx=10)
        self.frame_lignes_ticket = self.zone_lignes_scroll.interior

        bas_ticket = tk.Frame(zone_ticket, bg=BLANC, height=225)
        bas_ticket.pack(side="bottom", fill="x", padx=14, pady=(0, 16))
        bas_ticket.pack_propagate(False)

        separateur = tk.Frame(bas_ticket, bg=BRUN_700, height=1)
        separateur.pack(side="top", fill="x", pady=(4, 6))

        self.label_ht = tk.Label(
            bas_ticket, text="Total HT : 0 DH", font=POLICE_TICKET_DETAIL,
            bg=BLANC, fg=BRUN_500, anchor="e",
        )
        self.label_ht.pack(side="top", fill="x")

        self.label_tva = tk.Label(
            bas_ticket, text="TVA : 0 DH", font=POLICE_TICKET_DETAIL,
            bg=BLANC, fg=BRUN_500, anchor="e",
        )
        self.label_tva.pack(side="top", fill="x", pady=(0, 4))

        # Remise globale (%) sur le ticket en cours (ex: prix de gros pour
        # un client qui prend plusieurs gateaux) : appliquee juste avant
        # l'encaissement, sur le total complet.
        cadre_remise = tk.Frame(bas_ticket, bg=BLANC)
        cadre_remise.pack(side="top", fill="x", pady=(0, 2))
        self.label_remise = tk.Label(
            cadre_remise, text="Remise : aucune", font=POLICE_TICKET_DETAIL,
            bg=BLANC, fg=BRUN_500, anchor="w",
        )
        self.label_remise.pack(side="left")
        self.bouton_retirer_remise = BoutonArrondi(
            cadre_remise, lignes=[("X", POLICE_BOUTON_ROND, BLANC)],
            commande=self._retirer_remise, largeur=24, hauteur=24, rayon=7,
            couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BLANC,
        )
        BoutonArrondi(
            cadre_remise, lignes=[("Remise %", POLICE_BOUTON_ROND, BLANC)],
            commande=self._ouvrir_remise, largeur=90, hauteur=24, rayon=7,
            couleur_fond=OR, couleur_bordure=OR, bg=BLANC,
        ).pack(side="right")

        self.label_total = tk.Label(
            bas_ticket, font=POLICE_TOTAL, bg=BLANC, fg=BRUN_800, anchor="e",
        )
        self.label_total.pack(side="top", fill="x", pady=(0, 10))
        self._definir_texte_total_ttc("Total TTC : 0.00 DH")

        self.bouton_encaisser = BoutonArrondi(
            bas_ticket, lignes=[("ENCAISSER", POLICE_ENCAISSER, BLANC)],
            commande=self._encaisser, largeur=372, hauteur=64, rayon=12,
            couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
        )
        self.bouton_encaisser.pack(side="top", fill="x")

    def _definir_mode_vente(self, mode):
        self.mode_vente = mode
        self._rafraichir_mode_vente()
        self._rafraichir_ticket()

    def _rafraichir_mode_vente(self):
        largeur_bouton_mode = (self.LARGEUR_ZONE_TICKET - 28 - 16) // 2
        for mode, bouton in self.boutons_mode_vente.items():
            actif = (mode == self.mode_vente)
            texte = "Sur place" if mode == "sur_place" else "A emporter"
            police = police_ajustee_a_largeur(texte, POLICE_BOUTON_ROND, largeur_bouton_mode - 16, taille_min=10)
            bouton.definir_lignes([(texte, police, BLANC if actif else BRUN_700)])
            bouton.definir_fond(BRUN_700 if actif else BLANC, BRUN_700 if actif else BRUN_200)

    def _definir_texte_total_ttc(self, texte):
        """Le montant grandit avec le panier (ex: '1234.00 DH'), et le
        panneau ticket est etroit (300px) : sans reduire la police au
        besoin, le debut du texte ('Total') sortait du cadre (anchor='e'
        le pousse hors-champ a gauche) et n'affichait que la fin, du genre
        'al TTC : 0.00 DH'."""
        largeur_dispo = self.LARGEUR_ZONE_TICKET - 28
        police = police_ajustee_a_largeur(texte, POLICE_TOTAL, largeur_dispo, taille_min=16)
        self.label_total.configure(text=texte, font=police)

    # ------------------------------------------------------------------
    # Navigation : ecran categories <-> ecran produits <-> ecran parfums
    # ------------------------------------------------------------------
    def _rafraichir_ecran(self):
        for widget in self.frame_produits.winfo_children():
            widget.destroy()

        if self.categorie_active_id is None:
            self._construire_selection_categories()
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
        if not categories:
            return

        largeur_dispo, hauteur_dispo = self._zone_produits_taille_visible()
        espace = 16
        colonnes, lignes, largeur_case, hauteur_case = calculer_grille_adaptative(
            len(categories), largeur_dispo, hauteur_dispo, espace=espace,
            largeur_min=150, largeur_max=560, hauteur_min=90, hauteur_max=260,
        )
        # Si au moins une categorie a une icone, le texte doit se contenter
        # de la bande du bas (l'icone prend le haut - voir BoutonArrondi._dessiner,
        # meme fraction 0.6) : on part d'une reference plus basse pour ne
        # jamais avoir a rapetisser en catastrophe apres coup.
        a_des_icones = any(_chemin_icone_categorie(cat["nom"]) for cat in categories)
        hauteur_texte_ref = hauteur_case * 0.4 if a_des_icones else hauteur_case
        police_max = police_echelle(POLICE_CATEGORIE_CAISSE, hauteur_texte_ref, taille_min=14, taille_max=44)

        for index, cat in enumerate(categories):
            ligne, colonne = divmod(index, colonnes)
            x = espace + colonne * (largeur_case + espace)
            y = espace + ligne * (hauteur_case + espace)
            couleur = COULEURS_CATEGORIES[index % len(COULEURS_CATEGORIES)]
            chemin_icone = _chemin_icone_categorie(cat["nom"])
            # Taille ajustee par categorie : un nom compose d'un seul mot
            # long (ex: "Viennoiserie") doit rapetisser pour tenir sur une
            # ligne plutot que de se couper au milieu, faute d'espace ou le
            # scinder proprement - et en hauteur si une icone reduit la
            # place disponible pour le texte.
            police = police_ajustee_a_largeur(cat["nom"], police_max, largeur_case - 24, taille_min=12)
            if chemin_icone:
                police, = polices_ajustees_a_hauteur([police], hauteur_case * 0.4, taille_min=12)
            bouton = BoutonArrondi(
                self.frame_produits, lignes=[(cat["nom"], police, BLANC)],
                commande=lambda cid=cat["id"]: self._selectionner_categorie(cid),
                largeur=largeur_case, hauteur=hauteur_case, rayon=20,
                couleur_fond=couleur, couleur_bordure=couleur, bg=CREME,
                image_chemin=chemin_icone,
            )
            bouton.place(x=x, y=y, width=largeur_case, height=hauteur_case)

        # place() ne fait pas grandir automatiquement son conteneur (contrairement
        # a grid) : sans ceci le cadre reste minuscule et les pastilles, bien que
        # "placees", restent invisibles car en dehors de la zone visible/defilante.
        self.frame_produits.configure(height=max(hauteur_dispo, lignes * (hauteur_case + espace) + espace))

    def _sur_redimensionnement_zone_produits(self, event):
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
        hauteur_nom_dispo = hauteur_case - HAUTEUR_PIED_TUILE

        police_nom = police_echelle(POLICE_PRODUIT_NOM, hauteur_nom_dispo, taille_min=18, taille_max=44)
        police_nom = police_ajustee_a_largeur(nom, police_nom, largeur_case - 20, taille_min=10)
        police_nom, = polices_ajustees_a_hauteur([police_nom], hauteur_nom_dispo, taille_min=10)

        if hint:
            police_pied = police_echelle(POLICE_PRODUIT_HINT, HAUTEUR_PIED_TUILE, taille_min=9, taille_max=14)
            texte_pied = hint
        else:
            # prix demande "un peu plus gros" : echelle sur POLICE_PRODUIT_PRIX,
            # deja plus grande de base que POLICE_PRODUIT_HINT
            police_pied = police_echelle(POLICE_PRODUIT_PRIX, HAUTEUR_PIED_TUILE, taille_min=12, taille_max=18)
            texte_pied = "{:g} DH".format(prix)

        return [(nom, police_nom, BLANC)], (texte_pied, police_pied, BLANC)

    HAUTEUR_ENTETE_ECRAN_PRODUITS = 60

    def _construire_grille_tuiles(self, nombre, constructeur_tuile, hauteur_reservee_haut=0, hauteur_reservee_bas=0):
        """Calcule la grille adaptative pour `nombre` tuiles dans l'espace
        visible restant, puis appelle `constructeur_tuile(index, largeur_case,
        hauteur_case)` pour chacune (elle doit renvoyer un BoutonArrondi deja
        cree, pas encore place) et la positionne. Remplit tout l'ecran
        disponible sans jamais avoir besoin de scroller ; peu de tuiles =
        tuiles plus grandes, beaucoup de tuiles = plus petites mais toujours
        reparties pour occuper toute la place."""
        largeur_dispo, hauteur_totale = self._zone_produits_taille_visible()
        hauteur_dispo = hauteur_totale - hauteur_reservee_haut - hauteur_reservee_bas
        espace = 12
        colonnes, lignes, largeur_case, hauteur_case = calculer_grille_adaptative(
            max(nombre, 1), largeur_dispo, hauteur_dispo, espace=espace,
            largeur_min=170, largeur_max=380, hauteur_min=90, hauteur_max=240,
        )
        for index in range(nombre):
            ligne, colonne = divmod(index, colonnes)
            x = espace + colonne * (largeur_case + espace)
            y = hauteur_reservee_haut + espace + ligne * (hauteur_case + espace)
            tuile = constructeur_tuile(index, largeur_case, hauteur_case)
            tuile.place(x=x, y=y, width=largeur_case, height=hauteur_case)
        hauteur_contenu = hauteur_reservee_haut + espace + lignes * (hauteur_case + espace) + hauteur_reservee_bas
        self.frame_produits.configure(height=max(hauteur_totale, hauteur_contenu))
        return max(hauteur_totale, hauteur_contenu)

    def _construire_grille_produits(self):
        categorie = self.conn.execute(
            "SELECT * FROM categories WHERE id = ?", (self.categorie_active_id,)
        ).fetchone()
        if categorie is None:  # categorie supprimee entre-temps (import, etc.)
            self._retour_categories()
            return

        BoutonArrondi(
            self.frame_produits, lignes=[("< Categories", POLICE_CATEGORIE, BLANC)],
            commande=self._retour_categories, largeur=200, hauteur=48, rayon=12,
            couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=CREME,
        ).place(x=0, y=0, width=200, height=48)
        tk.Label(
            self.frame_produits, text=categorie["nom"], font=POLICE_SOUS_TITRE,
            bg=CREME, fg=BRUN_700,
        ).place(x=214, y=8)

        produits = self.conn.execute(
            "SELECT * FROM produits WHERE categorie_id = ? ORDER BY nom COLLATE NOCASE",
            (self.categorie_active_id,),
        ).fetchall()

        def construire_tuile(index, largeur_case, hauteur_case):
            produit = produits[index]
            if produit["a_des_sous_produits"]:
                lignes, pied = self._creer_tuile_produit(produit["nom"], None, largeur_case, hauteur_case,
                                                          hint="Voir les parfums >")
                commande = lambda p=produit: self._ouvrir_sous_menu(p)
                commande_qte = None  # pas de quantite directe sur un produit sans prix propre
            else:
                lignes, pied = self._creer_tuile_produit(produit["nom"], produit["prix"], largeur_case, hauteur_case)
                nom_p, prix_p, tva_p = produit["nom"], produit["prix"], produit["tva_fixe"]
                commande = lambda nom=nom_p, prix=prix_p, tva=tva_p: self._ajouter_au_ticket(nom, prix, 1, tva)
                commande_qte = lambda nom=nom_p, prix=prix_p, tva=tva_p: self._ouvrir_pave_quantite(nom, prix, tva)
            couleur = COULEURS_CATEGORIES[index % len(COULEURS_CATEGORIES)]
            return BoutonArrondi(
                self.frame_produits, lignes=lignes, pied=pied, commande=commande,
                largeur=largeur_case, hauteur=hauteur_case, rayon=14,
                couleur_fond=couleur, couleur_bordure=couleur, bg=CREME,
                commande_quantite=commande_qte,
            )

        self._construire_grille_tuiles(
            len(produits), construire_tuile, hauteur_reservee_haut=self.HAUTEUR_ENTETE_ECRAN_PRODUITS,
        )

    def _construire_vue_sous_menu(self, produit):
        tk.Label(
            self.frame_produits, text=produit["nom"], font=POLICE_SOUS_TITRE,
            bg=CREME, fg=BRUN_700,
        ).place(x=0, y=8)

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
            couleur = COULEURS_CATEGORIES[index % len(COULEURS_CATEGORIES)]
            return BoutonArrondi(
                self.frame_produits, lignes=lignes, pied=pied, commande=commande,
                largeur=largeur_case, hauteur=hauteur_case, rayon=14,
                couleur_fond=couleur, couleur_bordure=couleur, bg=CREME,
                commande_quantite=commande_qte,
            )

        HAUTEUR_BAS = 68
        hauteur_contenu = self._construire_grille_tuiles(
            len(sous_produits), construire_tuile,
            hauteur_reservee_haut=self.HAUTEUR_ENTETE_ECRAN_PRODUITS, hauteur_reservee_bas=HAUTEUR_BAS,
        )

        BoutonArrondi(
            self.frame_produits, lignes=[("< Retour", POLICE_CATEGORIE, BLANC)],
            commande=self._fermer_sous_menu, largeur=200, hauteur=52, rayon=12,
            couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=CREME,
        ).place(x=0, y=hauteur_contenu - HAUTEUR_BAS + 8)

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
        """Taux de TVA (%) effectif pour une ligne de ticket : celui du
        produit s'il en a un fixe (ex: 0% pour le pain), sinon celui du
        mode de vente en cours (Sur place / A emporter)."""
        if ligne["tva_fixe"] is not None:
            return ligne["tva_fixe"]
        return self.taux_tva[self.mode_vente]

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

        for index, ligne in enumerate(self.ticket):
            sous_total = ligne["quantite"] * ligne["prix_unitaire"]

            cadre_ligne = tk.Frame(self.frame_lignes_ticket, bg=BLANC)
            cadre_ligne.pack(side="top", fill="x", pady=(6, 0))

            tk.Label(cadre_ligne, text=ligne["nom"], font=POLICE_TICKET_NOM,
                     bg=BLANC, fg=BRUN_800, anchor="w", wraplength=220,
                     justify="left").pack(side="top", fill="x")

            bas = tk.Frame(cadre_ligne, bg=BLANC)
            bas.pack(side="top", fill="x", pady=(2, 6))
            tk.Label(bas, text="{:g} x {:g} DH = {:g} DH".format(
                ligne["quantite"], ligne["prix_unitaire"], sous_total),
                font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500,
            ).pack(side="left")

            BoutonArrondi(
                bas, lignes=[("-1", POLICE_BOUTON_ROND, BLANC)],
                commande=lambda i=index: self._retirer_unite(i),
                largeur=40, hauteur=40, rayon=20,
                couleur_fond=OR, couleur_bordure=OR, bg=BLANC,
            ).pack(side="right", padx=(4, 0))
            BoutonArrondi(
                bas, lignes=[("X", POLICE_BOUTON_ROND, BLANC)],
                commande=lambda i=index: self._supprimer_ligne(i),
                largeur=40, hauteur=40, rayon=20,
                couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BLANC,
            ).pack(side="right", padx=(4, 0))

            # separateur en tirets, comme sur la maquette du client
            canvas_tirets = tk.Canvas(self.frame_lignes_ticket, height=2, bg=BLANC, highlightthickness=0)
            canvas_tirets.pack(side="top", fill="x")
            canvas_tirets.bind(
                "<Configure>",
                lambda e, c=canvas_tirets: (c.delete("all"), c.create_line(0, 1, e.width, 1, dash=(4, 3), fill=BRUN_200)),
            )

        total_ht, total_tva, total_ttc, _ = self._totaux_ticket()
        self.label_ht.configure(text="Total HT : {:.2f} DH".format(total_ht))
        self.label_tva.configure(text="TVA : {:.2f} DH".format(total_tva))
        self._definir_texte_total_ttc("Total TTC : {:.2f} DH".format(total_ttc))

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

        largeur, hauteur = 380, 300
        x = self.winfo_rootx() + (self.winfo_width() - largeur) // 2
        y = self.winfo_rooty() + (self.winfo_height() - hauteur) // 2
        popup.geometry("{}x{}+{}+{}".format(largeur, hauteur, max(x, 0), max(y, 0)))

        tk.Label(popup, text="Mode de paiement", font=POLICE_SOUS_TITRE, bg=BLANC, fg=BRUN_700,
                 pady=14).pack(fill="x")

        def choisir(mode):
            popup.destroy()
            callback(mode)

        BoutonArrondi(
            popup, lignes=[("ESPECES", POLICE_ENCAISSER, BLANC)], commande=lambda: choisir("especes"),
            largeur=300, hauteur=68, rayon=14, couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
        ).pack(pady=(6, 10))
        BoutonArrondi(
            popup, lignes=[("CARTE", POLICE_ENCAISSER, BLANC)], commande=lambda: choisir("carte"),
            largeur=300, hauteur=68, rayon=14, couleur_fond=OR, couleur_bordure=OR, bg=BLANC,
        ).pack(pady=(0, 14))
        BoutonArrondi(
            popup, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)], commande=popup.destroy,
            largeur=300, hauteur=48, rayon=12, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack()

        popup.grab_set()

    def _finaliser_encaissement(self, mode_paiement):
        total_ht, total_tva, total_ttc, repartition_tva = self._totaux_ticket()
        remise_pourcentage = self.remise_pourcentage
        maintenant = datetime.now()

        curseur = self.conn.execute(
            "INSERT INTO ventes (date, heure, total, note, mode_vente, total_ht, total_tva, "
            "mode_paiement, remise_pourcentage) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (maintenant.strftime("%Y-%m-%d"), maintenant.strftime("%H:%M:%S"), total_ttc, None,
             self.mode_vente, total_ht, total_tva, mode_paiement, remise_pourcentage),
        )
        vente_id = curseur.lastrowid
        for ligne in self.ticket:
            # prix nominal (avant remise) : la remise n'est appliquee qu'au
            # niveau des totaux de la vente, pas ligne par ligne
            self.conn.execute(
                "INSERT INTO vente_lignes (vente_id, nom_produit, quantite, prix_unitaire, taux_tva) "
                "VALUES (?, ?, ?, ?, ?)",
                (vente_id, ligne["nom"], ligne["quantite"], ligne["prix_unitaire"], self._taux_pour_ligne(ligne)),
            )
        self.conn.commit()

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

        self._afficher_confirmation_encaissement(total_ttc)

        self.ticket = []
        self.remise_pourcentage = 0
        self._rafraichir_ticket()

        # Retour automatique a l'ecran des categories : le client suivant ne
        # doit pas se retrouver sur le produit/categorie ou s'est arretee la
        # vente precedente, sinon il faut cliquer "< Categories" a chaque fois.
        self.categorie_active_id = None
        self.produit_sous_menu_actif = None
        self._rafraichir_ecran()

    def _charger_dernier_ticket_depuis_db(self):
        """Reconstruit `self._dernier_ticket` a partir de la derniere vente
        enregistree en base, pour que "Dernier ticket" fonctionne meme apres
        un redemarrage du logiciel (client qui redemande son ticket plus
        tard). Utilise le taux de TVA fige au moment de la vente (colonne
        vente_lignes.taux_tva), jamais le taux courant."""
        vente = self.conn.execute("SELECT * FROM ventes ORDER BY id DESC LIMIT 1").fetchone()
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
            messagebox.showinfo("Aucun ticket", "Aucune vente n'a encore ete enregistree.")
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
        except Exception as exc:
            messagebox.showerror(
                "Erreur impression",
                "Impossible d'imprimer le ticket sur '{}' :\n{}\n\n"
                "Verifiez que l'imprimante est allumee, branchee et selectionnee "
                "dans le Mode Admin.".format(nom_imprimante, exc),
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
        tk.Label(bloc_texte, text="{:g} DH".format(total), font=("Georgia", 64, "bold"),
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
    conn_init.close()

    app = CaisseApp()
    app.mainloop()
