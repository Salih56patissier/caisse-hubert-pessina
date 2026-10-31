# -*- coding: utf-8 -*-
"""
Ecran de connexion vendeur : recouvre toute la caisse tant qu'aucun
vendeur n'est connecte. Le vendeur tape son code a 4 chiffres, la
validation est automatique au 4e chiffre.

Le code ADMIN tape ici ouvre le Mode Admin (pour creer les vendeurs la
premiere fois) mais ne connecte personne a la caisse.
"""

import tkinter as tk

from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, FRAMBOISE, ROUGE,
    HEADER_DEGRADE_DROITE, POLICE_CATEGORIE, POLICE_PRODUIT_NOM, POLICE_TITRE,
    BoutonArrondi,
)

TOUCHES = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["", "0", "<-"],
]


class EcranConnexion(tk.Frame):
    """`verifier_pin(pin)` renvoie True si le PIN a ete accepte (vendeur
    connecte ou admin ouvert), False sinon."""

    def __init__(self, parent, verifier_pin, message_aide=""):
        super().__init__(parent, bg=CREME)
        self.verifier_pin = verifier_pin
        self.saisie = ""

        bandeau = tk.Frame(self, bg=HEADER_DEGRADE_DROITE, height=64)
        bandeau.pack(side="top", fill="x")
        bandeau.pack_propagate(False)
        tk.Label(bandeau, text="Hubert & Pessina", font=POLICE_TITRE,
                 bg=HEADER_DEGRADE_DROITE, fg=BLANC).pack(expand=True)

        centre = tk.Frame(self, bg=CREME)
        centre.pack(expand=True)

        tk.Label(centre, text="Tapez votre code vendeur", font=("Segoe UI", 20, "bold"),
                 bg=CREME, fg=BRUN_700).pack(pady=(0, 4))
        # 4 pastilles : pleines au fur et a mesure de la saisie
        self.label_points = tk.Label(centre, text="", font=("Segoe UI", 26), bg=CREME, fg=FRAMBOISE, width=10)
        self.label_points.pack()
        self.label_message = tk.Label(centre, text=message_aide, font=POLICE_PRODUIT_NOM,
                                      bg=CREME, fg=BRUN_500, height=1)
        self.label_message.pack(pady=(0, 6))

        pave = tk.Frame(centre, bg=CREME)
        pave.pack()
        for r, ligne in enumerate(TOUCHES):
            for c, valeur in enumerate(ligne):
                if not valeur:
                    continue
                if valeur == "<-":
                    bouton = BoutonArrondi(
                        pave, lignes=[("<-", POLICE_CATEGORIE, BLANC)], commande=self._effacer,
                        largeur=104, hauteur=68, rayon=16, couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=CREME,
                    )
                else:
                    bouton = BoutonArrondi(
                        pave, lignes=[(valeur, ("Segoe UI", 26, "bold"), BRUN_800)],
                        commande=lambda v=valeur: self._appuyer(v),
                        largeur=104, hauteur=68, rayon=16, couleur_fond=BLANC, couleur_bordure=BRUN_200, bg=CREME,
                    )
                bouton.grid(row=r, column=c, padx=5, pady=4)

        self.bind_all("<Key>", self._sur_touche, add="+")
        self._rafraichir()

    def _sur_touche(self, event):
        # uniquement quand l'ecran de connexion est affiche ET que la frappe
        # vient de la fenetre principale (pas d'un formulaire de l'admin)
        if not self.winfo_ismapped():
            return
        try:
            if event.widget.winfo_toplevel() is not self.winfo_toplevel():
                return
        except (AttributeError, tk.TclError):
            return
        if event.char and event.char in "0123456789":
            self._appuyer(event.char)
        elif event.keysym == "BackSpace":
            self._effacer()

    def _appuyer(self, chiffre):
        if len(self.saisie) >= 4:
            return
        self.saisie += chiffre
        self._rafraichir()
        if len(self.saisie) == 4:
            self.after(120, self._valider)

    def _effacer(self):
        self.saisie = self.saisie[:-1]
        self._rafraichir()

    def _rafraichir(self):
        self.label_points.configure(text=" ".join(["●"] * len(self.saisie) + ["○"] * (4 - len(self.saisie))))

    def _valider(self):
        pin, self.saisie = self.saisie, ""
        self._rafraichir()
        if not self.verifier_pin(pin):
            self.afficher_message("Code incorrect", erreur=True)

    def afficher_message(self, texte, erreur=False):
        self.label_message.configure(text=texte, fg=ROUGE if erreur else BRUN_500)

    def reinitialiser(self, message=""):
        self.saisie = ""
        self._rafraichir()
        self.afficher_message(message)
