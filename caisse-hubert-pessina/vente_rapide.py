# -*- coding: utf-8 -*-
"""
Fenetre "VENTE RAPIDE" : le vendeur tape uniquement le montant total du
client, choisit (optionnellement) une categorie, puis valide par ESPECES
ou CARTE. 1 validation = 1 ticket = 1 client.

Objectif : moins de 5 secondes par client en rush du matin.
Parcours minimal : VENTE RAPIDE -> 2 ou 3 chiffres -> ESPECES.
Le clavier physique marche aussi : chiffres, virgule/point, Retour arriere,
Entree = ESPECES, Echap = Annuler.

Ticket mixte : si un ticket detaille est en cours (mode_ajout=True), la
fenetre ne propose plus ESPECES/CARTE mais "AJOUTER AU TICKET" : le montant
devient une ligne "Vente rapide" du ticket en cours (ex: nouveau gateau pas
encore au catalogue), encaissee ensuite avec le reste via ENCAISSER.
Sans ticket en cours, le bouton "+ Ticket" demarre un ticket avec cette
ligne (on ajoute ensuite les produits du catalogue).
"""

AJOUT_TICKET = "ticket"  # valeur passee au callback a la place du mode de paiement

import tkinter as tk

from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROSE, ROUGE, VERT,
    POLICE_CATEGORIE, POLICE_SOUS_TITRE, POLICE_BOUTON_ROND, POLICE_ENCAISSER,
    BoutonArrondi, police_ajustee_a_largeur,
)

MONTANT_MAX = 99999
CHIFFRES_MAX_ENTIERS = 5

TOUCHES = [
    ["7", "8", "9"],
    ["4", "5", "6"],
    ["1", "2", "3"],
    [",", "0", "<-"],
]


class FenetreVenteRapide(tk.Toplevel):
    """`callback_validation(montant, nom_categorie_ou_None, mode_paiement)`
    est appele une seule fois, a la validation, avec un montant > 0.
    mode_paiement vaut AJOUT_TICKET quand le montant doit etre ajoute au
    ticket en cours au lieu d'etre encaisse."""

    def __init__(self, parent, noms_categories, libelle_mode_vente, callback_validation, mode_ajout=False):
        super().__init__(parent)
        self.callback_validation = callback_validation
        self.saisie = ""
        self.categorie_choisie = None
        self._boutons_categories = {}
        self._valide = False

        self.title("Vente rapide")
        self.configure(bg=BLANC)
        self.resizable(False, False)
        self.transient(parent)

        largeur = min(900, max(parent.winfo_width() - 20, 700))
        hauteur = min(630, max(parent.winfo_height() - 20, 560))
        x = parent.winfo_rootx() + (parent.winfo_width() - largeur) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - hauteur) // 2
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, max(x, 0), max(y, 0)))

        # --- bandeau titre ---
        bandeau = tk.Frame(self, bg=ROSE, height=54)
        bandeau.pack(side="top", fill="x")
        bandeau.pack_propagate(False)
        tk.Label(bandeau, text="AJOUTER AU TICKET (prix libre)" if mode_ajout else "VENTE RAPIDE",
                 font=("Segoe UI", 20, "bold"),
                 bg=ROSE, fg=BLANC).pack(side="left", padx=18)
        tk.Label(bandeau, text=libelle_mode_vente, font=POLICE_BOUTON_ROND,
                 bg=ROSE, fg=BLANC).pack(side="right", padx=18)

        corps = tk.Frame(self, bg=BLANC)
        corps.pack(side="top", fill="both", expand=True, padx=16, pady=12)

        # --- gauche : montant + pave ---
        gauche = tk.Frame(corps, bg=BLANC)
        gauche.pack(side="left", fill="y")

        cadre_affichage = tk.Frame(gauche, bg=CREME, highlightbackground=BRUN_200, highlightthickness=1)
        cadre_affichage.pack(side="top", fill="x", pady=(0, 10))
        self.label_montant = tk.Label(cadre_affichage, text="0 DH", font=("Segoe UI", 40, "bold"),
                                      bg=CREME, fg=BRUN_800, anchor="e", padx=16, pady=6)
        self.label_montant.pack(fill="x")

        pave = tk.Frame(gauche, bg=BLANC)
        pave.pack(side="top")
        for r, ligne in enumerate(TOUCHES):
            for c, valeur in enumerate(ligne):
                self._creer_touche(pave, valeur).grid(row=r, column=c, padx=4, pady=4)

        # --- droite : categories (optionnel) + validation ---
        droite = tk.Frame(corps, bg=BLANC)
        droite.pack(side="left", fill="both", expand=True, padx=(18, 0))

        tk.Label(droite, text="Categorie (facultatif)", font=POLICE_BOUTON_ROND,
                 bg=BLANC, fg=BRUN_500, anchor="w").pack(side="top", fill="x")

        grille_cat = tk.Frame(droite, bg=BLANC)
        grille_cat.pack(side="top", fill="x", pady=(4, 0))
        colonnes = 3
        largeur_droite = largeur - 16 * 2 - 3 * (104 + 8) - 18
        largeur_chip = max((largeur_droite - (colonnes - 1) * 8) // colonnes, 80)
        for i in range(colonnes):
            grille_cat.grid_columnconfigure(i, weight=1)
        for index, nom in enumerate(noms_categories):
            r, c = divmod(index, colonnes)
            police = police_ajustee_a_largeur(nom, POLICE_BOUTON_ROND, largeur_chip - 12, taille_min=9)
            bouton = BoutonArrondi(
                grille_cat, lignes=[(nom, police, BRUN_700)],
                commande=lambda n=nom: self._basculer_categorie(n),
                largeur=largeur_chip, hauteur=48, rayon=10,
                couleur_fond=BLANC, couleur_bordure=BRUN_200, bg=BLANC,
            )
            bouton.grid(row=r, column=c, padx=4, pady=4, sticky="ew")
            self._boutons_categories[nom] = (bouton, police)

        bas = tk.Frame(droite, bg=BLANC)
        bas.pack(side="bottom", fill="x")
        largeur_bouton = max(largeur_droite, 200)
        if mode_ajout:
            validation_entree = AJOUT_TICKET
            BoutonArrondi(
                bas, lignes=[("AJOUTER AU TICKET", ("Segoe UI", 24, "bold"), BLANC),
                             ("encaisse ensuite avec le reste", POLICE_CATEGORIE, BLANC)],
                commande=lambda: self._valider(AJOUT_TICKET), largeur=largeur_bouton, hauteur=92, rayon=16,
                couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
            ).pack(side="top", fill="x", pady=(0, 8))
            BoutonArrondi(
                bas, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)],
                commande=self.destroy, largeur=largeur_bouton, hauteur=60, rayon=14,
                couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
            ).pack(side="top", fill="x")
        else:
            validation_entree = "especes"
            BoutonArrondi(
                bas, lignes=[("ESPECES", ("Segoe UI", 26, "bold"), BLANC)],
                commande=lambda: self._valider("especes"), largeur=largeur_bouton, hauteur=92, rayon=16,
                couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
            ).pack(side="top", fill="x", pady=(0, 8))
            ligne_bas = tk.Frame(bas, bg=BLANC)
            ligne_bas.pack(side="top", fill="x")
            tiers = (largeur_bouton - 16) // 3
            BoutonArrondi(
                ligne_bas, lignes=[("CARTE", POLICE_ENCAISSER, BLANC)],
                commande=lambda: self._valider("carte"), largeur=tiers, hauteur=60, rayon=14,
                couleur_fond=OR, couleur_bordure=OR, bg=BLANC,
            ).pack(side="left", fill="x", expand=True, padx=(0, 4))
            BoutonArrondi(
                ligne_bas, lignes=[("+ Ticket", POLICE_CATEGORIE, BLANC)],
                commande=lambda: self._valider(AJOUT_TICKET), largeur=tiers, hauteur=60, rayon=14,
                couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=BLANC,
            ).pack(side="left", fill="x", expand=True, padx=4)
            BoutonArrondi(
                ligne_bas, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)],
                commande=self.destroy, largeur=tiers, hauteur=60, rayon=14,
                couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
            ).pack(side="left", fill="x", expand=True, padx=(4, 0))

        # clavier physique (si un clavier est branche sur le poste)
        self.bind("<Key>", self._sur_touche_clavier)
        self.bind("<Return>", lambda e: self._valider(validation_entree))
        self.bind("<KP_Enter>", lambda e: self._valider(validation_entree))
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<BackSpace>", lambda e: self._appuyer("<-"))

        self._rafraichir_affichage()
        self.grab_set()
        self.focus_force()

    # ------------------------------------------------------------------
    def _creer_touche(self, parent, valeur):
        if valeur == "<-":
            return BoutonArrondi(
                parent, lignes=[("<-", POLICE_CATEGORIE, BLANC)],
                commande=lambda: self._appuyer("<-"), largeur=104, hauteur=80, rayon=12,
                couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BLANC,
            )
        return BoutonArrondi(
            parent, lignes=[(valeur, ("Segoe UI", 26, "bold"), BRUN_800)],
            commande=lambda v=valeur: self._appuyer(v), largeur=104, hauteur=80, rayon=12,
            couleur_fond=CREME, couleur_bordure=BRUN_200, bg=BLANC,
        )

    def _sur_touche_clavier(self, event):
        if event.char and event.char in "0123456789":
            self._appuyer(event.char)
        elif event.char in (",", "."):
            self._appuyer(",")

    def _appuyer(self, touche):
        s = self.saisie
        if touche == "<-":
            s = s[:-1]
        elif touche == ",":
            if "," in s:
                return
            s = (s or "0") + ","
        else:
            if "," in s:
                if len(s.split(",")[1]) >= 2:
                    return  # 2 decimales maximum
            elif len(s) >= CHIFFRES_MAX_ENTIERS:
                return
            if s == "0":
                s = ""  # pas de zero en tete
            s += touche
        self.saisie = s
        self._rafraichir_affichage()

    def _montant(self):
        if not self.saisie:
            return 0.0
        try:
            return float(self.saisie.replace(",", "."))
        except ValueError:
            return 0.0

    def _rafraichir_affichage(self):
        texte = (self.saisie or "0") + " DH"
        self.label_montant.configure(text=texte)

    def _basculer_categorie(self, nom):
        self.categorie_choisie = None if self.categorie_choisie == nom else nom
        for nom_cat, (bouton, police) in self._boutons_categories.items():
            actif = (nom_cat == self.categorie_choisie)
            bouton.definir_lignes([(nom_cat, police, BLANC if actif else BRUN_700)])
            bouton.definir_fond(BRUN_700 if actif else BLANC, BRUN_700 if actif else BRUN_200)

    def _valider(self, mode_paiement):
        if self._valide:
            return  # anti double-tap : une seule vente par validation
        montant = self._montant()
        if montant <= 0 or montant > MONTANT_MAX:
            self.label_montant.configure(fg=ROUGE)
            self.after(400, lambda: self.label_montant.winfo_exists() and self.label_montant.configure(fg=BRUN_800))
            return
        self._valide = True
        categorie = self.categorie_choisie
        self.destroy()
        self.callback_validation(montant, categorie, mode_paiement)
