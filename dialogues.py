# -*- coding: utf-8 -*-
"""
Petites fenetres tactiles reutilisables (gros boutons, couleurs de la
caisse) a utiliser a la place des boites Windows standard (messagebox),
dont le bouton OK est trop petit pour un ecran tactile.
"""

import tkinter as tk

from styles import (
    BLANC, BRUN_300, BRUN_500, BRUN_700, BRUN_800, OR, ROUGE, VERT,
    POLICE_CATEGORIE, POLICE_SOUS_TITRE, POLICE_PRODUIT_NOM,
    BoutonArrondi,
)


def _centrer(fenetre, parent, largeur, hauteur):
    x = parent.winfo_rootx() + (parent.winfo_width() - largeur) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - hauteur) // 2
    fenetre.geometry("{}x{}+{}+{}".format(largeur, hauteur, max(x, 0), max(y, 0)))


def _ajuster_hauteur(fenetre, parent, largeur, hauteur_mini):
    """Recentre `fenetre` avec une hauteur au moins egale a `hauteur_mini`
    mais jamais inferieure a ce que demande son contenu (texte agrandi par la
    mise a l'echelle Windows, message plus long que prevu...) : sans ca le
    bouton du bas ou la fin du texte etaient coupes."""
    fenetre.update_idletasks()
    _centrer(fenetre, parent, largeur, max(hauteur_mini, fenetre.winfo_reqheight()))


class Message(tk.Toplevel):
    """Message modal avec un seul gros bouton OK. `niveau` : 'info',
    'attention' ou 'erreur' (change la couleur du bandeau)."""

    COULEURS = {"info": BRUN_700, "attention": OR, "erreur": ROUGE}

    def __init__(self, parent, titre, texte, niveau="info", callback_ok=None):
        super().__init__(parent)
        self.callback_ok = callback_ok
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=BLANC, highlightbackground=BRUN_300, highlightthickness=1)
        _centrer(self, parent, 540, 360)
        couleur = self.COULEURS.get(niveau, BRUN_700)

        bandeau = tk.Frame(self, bg=couleur, height=56)
        bandeau.pack(side="top", fill="x")
        bandeau.pack_propagate(False)
        tk.Label(bandeau, text=titre, font=POLICE_SOUS_TITRE, bg=couleur, fg=BLANC).pack(side="left", padx=18)

        BoutonArrondi(
            self, lignes=[("OK", ("Segoe UI", 22, "bold"), BLANC)], commande=self._ok,
            largeur=260, hauteur=68, rayon=14, couleur_fond=couleur, couleur_bordure=couleur, bg=BLANC,
        ).pack(side="bottom", pady=(0, 20))
        tk.Label(self, text=texte, font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_800,
                 wraplength=490, justify="center").pack(side="top", fill="both", expand=True, padx=20, pady=(10, 0))

        _ajuster_hauteur(self, parent, 540, 360)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._ok())
        self.grab_set()
        self.focus_force()

    def _ok(self):
        self.destroy()
        if self.callback_ok:
            self.callback_ok()


class ChoixMotif(tk.Toplevel):
    """Choix obligatoire d'un motif parmi `motifs` (un gros bouton chacun)
    + Annuler. `callback(motif)` n'est appele que si un motif est choisi."""

    def __init__(self, parent, titre, motifs, callback, libelle_retour="Annuler"):
        super().__init__(parent)
        self.callback = callback
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=BLANC, highlightbackground=BRUN_300, highlightthickness=1)
        hauteur = 56 + 30 + len(motifs) * 82 + 90
        _centrer(self, parent, 460, hauteur)

        bandeau = tk.Frame(self, bg=OR, height=56)
        bandeau.pack(side="top", fill="x")
        bandeau.pack_propagate(False)
        tk.Label(bandeau, text=titre, font=POLICE_SOUS_TITRE, bg=OR, fg=BLANC).pack(side="left", padx=18)

        tk.Label(self, text="Motif obligatoire :", font=POLICE_PRODUIT_NOM, bg=BLANC,
                 fg=BRUN_500).pack(side="top", pady=(8, 2))
        for motif in motifs:
            BoutonArrondi(
                self, lignes=[(motif, POLICE_CATEGORIE, BLANC)], commande=lambda m=motif: self._choisir(m),
                largeur=380, hauteur=70, rayon=14, couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=BLANC,
            ).pack(side="top", pady=6)
        BoutonArrondi(
            self, lignes=[(libelle_retour, POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=380, hauteur=60, rayon=14, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(side="top", pady=(12, 10))

        _ajuster_hauteur(self, parent, 460, hauteur)
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.focus_force()

    def _choisir(self, motif):
        self.destroy()
        self.callback(motif)


class Menu(tk.Toplevel):
    """Liste de gros boutons : options = [(libelle, commande, couleur)].
    Un bouton Annuler est ajoute en bas."""

    def __init__(self, parent, titre, options, libelle_retour="Annuler"):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=BLANC, highlightbackground=BRUN_300, highlightthickness=1)
        hauteur = 56 + 16 + len(options) * 82 + 86
        _centrer(self, parent, 460, hauteur)

        bandeau = tk.Frame(self, bg=BRUN_700, height=56)
        bandeau.pack(side="top", fill="x")
        bandeau.pack_propagate(False)
        tk.Label(bandeau, text=titre, font=POLICE_SOUS_TITRE, bg=BRUN_700, fg=BLANC).pack(side="left", padx=18)
        tk.Frame(self, bg=BLANC, height=10).pack(side="top")
        for libelle, commande, couleur in options:
            BoutonArrondi(
                self, lignes=[(libelle, POLICE_CATEGORIE, BLANC)],
                commande=lambda c=commande: self._choisir(c),
                largeur=380, hauteur=70, rayon=14, couleur_fond=couleur, couleur_bordure=couleur, bg=BLANC,
            ).pack(side="top", pady=6)
        BoutonArrondi(
            self, lignes=[(libelle_retour, POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=380, hauteur=60, rayon=14, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(side="top", pady=(10, 10))
        _ajuster_hauteur(self, parent, 460, hauteur)
        self.bind("<Escape>", lambda e: self.destroy())
        self.grab_set()
        self.focus_force()

    def _choisir(self, commande):
        self.destroy()
        commande()


def confirmer(parent, titre, texte, libelle_oui, callback_oui, libelle_non="Annuler", couleur_oui=VERT, hauteur=300, scrollable=False):
    """Question oui/non tactile : `callback_oui()` seulement si confirme.
    Si scrollable=True, le texte est dans une zone defilante."""
    fen = tk.Toplevel(parent)
    fen.overrideredirect(True)
    fen.attributes("-topmost", True)
    fen.configure(bg=BLANC, highlightbackground=BRUN_300, highlightthickness=1)
    _centrer(fen, parent, 540, hauteur)
    bandeau = tk.Frame(fen, bg=BRUN_700, height=56)
    bandeau.pack(side="top", fill="x")
    bandeau.pack_propagate(False)
    tk.Label(bandeau, text=titre, font=POLICE_SOUS_TITRE, bg=BRUN_700, fg=BLANC).pack(side="left", padx=18)
    bas = tk.Frame(fen, bg=BLANC)
    bas.pack(side="bottom", fill="x", padx=20, pady=(0, 16))

    def oui():
        fen.destroy()
        callback_oui()

    BoutonArrondi(
        bas, lignes=[(libelle_oui, POLICE_CATEGORIE, BLANC)], commande=oui,
        largeur=220, hauteur=60, rayon=14, couleur_fond=couleur_oui, couleur_bordure=couleur_oui, bg=BLANC,
    ).pack(side="left", expand=True, padx=(0, 8))
    BoutonArrondi(
        bas, lignes=[(libelle_non, POLICE_CATEGORIE, BLANC)], commande=fen.destroy,
        largeur=220, hauteur=60, rayon=14, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
    ).pack(side="left", expand=True)

    if scrollable:
        # Zone defilante pour les longues listes de tickets
        cadre_scroll = tk.Frame(fen, bg=BLANC)
        cadre_scroll.pack(side="top", fill="both", expand=True, padx=12, pady=(8, 4))
        canvas = tk.Canvas(cadre_scroll, bg=BLANC, highlightthickness=0)
        scrollbar = tk.Scrollbar(cadre_scroll, orient="vertical", command=canvas.yview)
        cadre_interne = tk.Frame(canvas, bg=BLANC)
        cadre_interne.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=cadre_interne, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        tk.Label(cadre_interne, text=texte, font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_800,
                 justify="left", anchor="nw").pack(anchor="nw", padx=8, pady=8)
        # Molette
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    else:
        tk.Label(fen, text=texte, font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_800,
                 wraplength=480, justify="left").pack(side="top", fill="both", expand=True, padx=20, pady=10)

    if not scrollable:
        _ajuster_hauteur(fen, parent, 540, hauteur)
    fen.grab_set()
    fen.focus_force()
    return fen
