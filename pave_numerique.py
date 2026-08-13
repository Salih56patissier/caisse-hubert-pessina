# -*- coding: utf-8 -*-
"""
Pave numerique tactile reutilisable : quantite (etape 3), prix et PIN
(etapes suivantes) passent tous par ce meme composant, jamais par une
saisie clavier obligatoire.
"""

import tkinter as tk

from styles import (
    BLANC, BRUN_200, BRUN_700, BRUN_800, BRUN_500, CREME, VERT, ROUGE,
    POLICE_SOUS_TITRE, POLICE_CATEGORIE, POLICE_BOUTON_ROND, BoutonArrondi,
)

DISPOSITION_TOUCHES = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["Effacer", "0", "OK"],
]

# Variante utilisee quand la saisie doit accepter des centimes (prix) : la
# virgule prend la place d'"OK" dans la grille, qui devient un grand bouton
# a part (comme "Annuler") pour ne pas avoir a etirer la grille sur une
# 4e colonne.
DISPOSITION_TOUCHES_DECIMALES = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["Effacer", "0", ","],
]


class PaveNumerique(tk.Toplevel):
    """Fenetre modale avec un pave numerique 0-9 + effacer + valider.

    `callback_validation(valeur_entiere)` est appele uniquement si la
    saisie est un entier strictement positif au moment de valider.
    `masquer=True` affiche des points (utile pour un PIN) au lieu des
    chiffres tapes.
    """

    def __init__(self, parent, titre, callback_validation, masquer=False, chiffres_max=5,
                 longueur_exacte=None, renvoyer_texte=False, validation_auto=False,
                 delai_validation_auto_ms=650, permettre_decimales=False):
        super().__init__(parent)
        self.callback_validation = callback_validation
        self.masquer = masquer
        self.chiffres_max = chiffres_max
        self.longueur_exacte = longueur_exacte
        self.renvoyer_texte = renvoyer_texte
        self.validation_auto = validation_auto
        self.delai_validation_auto_ms = delai_validation_auto_ms
        self.permettre_decimales = permettre_decimales
        self._job_validation_auto = None
        self.saisie = ""

        self.title(titre)
        self.configure(bg=BLANC)
        self.resizable(False, False)
        self.transient(parent)

        # Un bouton "Valider" supplementaire (grand bouton, hors grille) est
        # ajoute en mode decimales : il faut donc un peu plus de hauteur.
        largeur, hauteur = 340, (605 if permettre_decimales else 545)
        x = parent.winfo_rootx() + (parent.winfo_width() - largeur) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - hauteur) // 2
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, max(x, 0), max(y, 0)))

        tk.Label(self, text=titre, font=POLICE_SOUS_TITRE, bg=BLANC, fg=BRUN_700,
                 wraplength=260, pady=14).pack(side="top", fill="x")

        self.label_affichage = tk.Label(self, text="0", font=("Segoe UI", 36, "bold"),
                                         bg=BLANC, fg=BRUN_800)
        self.label_affichage.pack(side="top", fill="x", pady=(0, 14))

        cadre_pad = tk.Frame(self, bg=BLANC)
        cadre_pad.pack(side="top")

        disposition = DISPOSITION_TOUCHES_DECIMALES if permettre_decimales else DISPOSITION_TOUCHES
        for r, ligne_touches in enumerate(disposition):
            for c, valeur in enumerate(ligne_touches):
                bouton = self._creer_touche(cadre_pad, valeur)
                bouton.grid(row=r, column=c, padx=4, pady=4)

        if permettre_decimales:
            BoutonArrondi(
                self, lignes=[("OK", POLICE_CATEGORIE, BLANC)],
                commande=self._valider, largeur=296, hauteur=52, rayon=12,
                couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
            ).pack(side="top", pady=(12, 0))

        BoutonArrondi(
            self, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)],
            commande=self._annuler, largeur=296, hauteur=52, rayon=12,
            couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(side="top", pady=(16, 10))

        self._rafraichir_affichage()

        self.grab_set()
        self.focus_set()

    def _creer_touche(self, parent, valeur):
        if valeur == "Effacer":
            return BoutonArrondi(
                parent, lignes=[("<-", POLICE_BOUTON_ROND, BLANC)],
                commande=self._effacer, largeur=92, hauteur=70, rayon=12,
                couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BLANC,
            )
        if valeur == "OK":
            return BoutonArrondi(
                parent, lignes=[("OK", POLICE_BOUTON_ROND, BLANC)],
                commande=self._valider, largeur=92, hauteur=70, rayon=12,
                couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
            )
        return BoutonArrondi(
            parent, lignes=[(valeur, ("Segoe UI", 20, "bold"), BRUN_800)],
            commande=lambda v=valeur: self._appuyer(v), largeur=92, hauteur=70, rayon=12,
            couleur_fond=CREME, couleur_bordure=BRUN_200, bg=BLANC,
        )

    def _appuyer(self, chiffre):
        if chiffre == "," and "," in self.saisie:
            return  # une seule virgule possible
        if chiffre == "," and self.saisie == "":
            chiffre = "0,"  # une virgule seule ne veut rien dire ; "0," oui
        if len(self.saisie) + len(chiffre) <= self.chiffres_max:
            self.saisie += chiffre
            self._rafraichir_affichage()
            if self.validation_auto:
                self._reprogrammer_validation_auto()

    def _effacer(self):
        self._annuler_validation_auto()
        self.saisie = self.saisie[:-1]
        self._rafraichir_affichage()

    def _reprogrammer_validation_auto(self):
        """Valide automatiquement apres un court delai sans nouvelle saisie
        (ex: quantite) - permet un chiffre seul en un tap, tout en laissant
        le temps de taper un 2eme chiffre pour un nombre a 2 chiffres."""
        self._annuler_validation_auto()
        self._job_validation_auto = self.after(self.delai_validation_auto_ms, self._valider)

    def _annuler_validation_auto(self):
        if self._job_validation_auto is not None:
            self.after_cancel(self._job_validation_auto)
            self._job_validation_auto = None

    def _rafraichir_affichage(self):
        if not self.saisie:
            texte = "0"
        elif self.masquer:
            texte = "-" * len(self.saisie)
        else:
            texte = self.saisie
        self.label_affichage.configure(text=texte)

    def _annuler(self):
        self._annuler_validation_auto()
        self.destroy()

    def _valider(self):
        self._annuler_validation_auto()
        if self.longueur_exacte is not None:
            if len(self.saisie) != self.longueur_exacte:
                return
            valeur = self.saisie if self.renvoyer_texte else int(self.saisie)
            self.destroy()
            self.callback_validation(valeur)
            return

        if not self.saisie:
            return
        valeur = float(self.saisie.replace(",", ".")) if self.permettre_decimales else int(self.saisie)
        if valeur <= 0:
            return
        self.destroy()
        self.callback_validation(valeur)
