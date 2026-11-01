# -*- coding: utf-8 -*-
"""
Ecran de comptage du tiroir = la "Feuille de caisse" a l'ecran.

- 9 lignes dans l'ordre de la feuille papier : pieces (grammes) puis
  billets (nombre). Une ligne active a la fois, saisie au pave numerique.
- Touche SUIVANT : valide la ligne et passe a la suivante. Ligne vide = 0.
  On peut aussi toucher directement une ligne pour la corriger.
- Detail par ligne et total general calcules en direct.
- Le montant ATTENDU n'est jamais affiche ici (comptage a l'aveugle).

`callback(total, details)` est appele apres confirmation.
"""

import tkinter as tk

import comptage
import dialogues
from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROUGE, VERT,
    POLICE_CATEGORIE, POLICE_PRODUIT_NOM, POLICE_TICKET_DETAIL,
    BoutonArrondi,
)

TOUCHES = [
    ["7", "8", "9"],
    ["4", "5", "6"],
    ["1", "2", "3"],
    [",", "0", "<-"],
]
FOND_ACTIF = "#fff3d6"


def _format_dh(montant):
    return "{:,.2f}".format(montant).replace(",", " ").replace(".", ",") + " DH"


class EcranComptage(tk.Toplevel):

    def __init__(self, parent, conn, titre, callback, sous_titre=""):
        super().__init__(parent)
        self.conn = conn
        self.callback = callback
        self.lignes = comptage.lignes_de_comptage(conn)
        self.saisies = [""] * len(self.lignes)
        self.index_actif = 0
        self._widgets = []

        self.title(titre)
        self.configure(bg=CREME)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        largeur = min(max(parent.winfo_width(), 900), 950)
        hauteur = min(max(parent.winfo_height(), 640), 680)
        x = parent.winfo_rootx() + (parent.winfo_width() - largeur) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - hauteur) // 2
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, max(x, 0), max(y, 0)))

        bandeau = tk.Frame(self, bg=BRUN_700, height=52)
        bandeau.pack(side="top", fill="x")
        bandeau.pack_propagate(False)
        tk.Label(bandeau, text=titre, font=("Segoe UI", 18, "bold"), bg=BRUN_700, fg=BLANC).pack(side="left", padx=16)
        if sous_titre:
            tk.Label(bandeau, text=sous_titre, font=POLICE_PRODUIT_NOM, bg=BRUN_700, fg=BLANC).pack(side="right", padx=16)

        corps = tk.Frame(self, bg=CREME)
        corps.pack(side="top", fill="both", expand=True, padx=12, pady=8)

        # ---------------- droite : pave ----------------
        droite = tk.Frame(corps, bg=CREME)
        droite.pack(side="right", fill="y", padx=(12, 0))
        pave = tk.Frame(droite, bg=CREME)
        pave.pack(side="top")
        for r, rangee in enumerate(TOUCHES):
            for c, v in enumerate(rangee):
                if v == "<-":
                    b = BoutonArrondi(pave, lignes=[("<-", POLICE_CATEGORIE, BLANC)], commande=lambda: self._touche("<-"),
                                      largeur=92, hauteur=66, rayon=12, couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=CREME)
                else:
                    b = BoutonArrondi(pave, lignes=[(v, ("Segoe UI", 22, "bold"), BRUN_800)],
                                      commande=lambda v=v: self._touche(v), largeur=92, hauteur=66, rayon=12,
                                      couleur_fond=BLANC, couleur_bordure=BRUN_200, bg=CREME)
                b.grid(row=r, column=c, padx=3, pady=3)
        BoutonArrondi(droite, lignes=[("SUIVANT  >", POLICE_CATEGORIE, BLANC)], commande=self._suivant,
                      largeur=290, hauteur=66, rayon=12, couleur_fond=OR, couleur_bordure=OR, bg=CREME,
                      ).pack(side="top", pady=(8, 0))
        BoutonArrondi(droite, lignes=[("Valider le comptage", POLICE_CATEGORIE, BLANC)], commande=self._valider,
                      largeur=290, hauteur=66, rayon=12, couleur_fond=VERT, couleur_bordure=VERT, bg=CREME,
                      ).pack(side="top", pady=(8, 0))
        BoutonArrondi(droite, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
                      largeur=290, hauteur=50, rayon=12, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=CREME,
                      ).pack(side="top", pady=(8, 0))

        # ---------------- gauche : la feuille ----------------
        feuille = tk.Frame(corps, bg=CREME)
        feuille.pack(side="left", fill="both", expand=True)

        bas = tk.Frame(feuille, bg=BRUN_800)
        bas.pack(side="bottom", fill="x", pady=(6, 0))
        tk.Label(bas, text="TOTAL GENERAL", font=("Segoe UI", 15, "bold"), bg=BRUN_800, fg=BLANC).pack(side="left", padx=14, pady=6)
        self.label_total = tk.Label(bas, text="0 DH", font=("Segoe UI", 20, "bold"), bg=BRUN_800, fg=BLANC)
        self.label_total.pack(side="right", padx=14)

        tk.Label(feuille, text="Tarer la balance avec le recipient vide avant chaque pesee",
                 font=("Segoe UI", 11, "bold"), bg=CREME, fg=ROUGE, anchor="w").pack(fill="x")
        tk.Label(feuille, text="PIECES (poids en grammes)", font=POLICE_TICKET_DETAIL,
                 bg=CREME, fg=BRUN_700, anchor="w").pack(fill="x")
        for i, ligne in enumerate(self.lignes):
            if i == len(comptage.PIECES):
                tk.Label(feuille, text="BILLETS (nombre de billets)", font=POLICE_TICKET_DETAIL,
                         bg=CREME, fg=BRUN_700, anchor="w").pack(fill="x", pady=(6, 0))
            self._widgets.append(self._creer_ligne(feuille, i, ligne))

        self.bind("<Key>", self._clavier)
        self._rafraichir()
        self.grab_set()
        self.focus_force()

    # ------------------------------------------------------------------
    def _creer_ligne(self, parent, index, ligne):
        cadre = tk.Frame(parent, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
        cadre.pack(fill="x", pady=1)
        # libelle court : la section (PIECES / BILLETS) est deja indiquee
        texte = "50 centimes" if ligne["valeur"] == 0.5 else "{:g} DH".format(ligne["valeur"])
        if ligne["nature"] == "piece" and ligne["methode"] == comptage.METHODE_COMPTAGE:
            texte += " (compter)"
        lab = tk.Label(cadre, text=texte, font=("Segoe UI", 13, "bold"), bg=BLANC, fg=BRUN_800, anchor="w", width=16)
        lab.pack(side="left", padx=(10, 4), pady=3)
        champ = tk.Label(cadre, text="", font=("Segoe UI", 15, "bold"), bg=CREME, fg=BRUN_800, width=7,
                         anchor="e", relief="flat", bd=0, highlightthickness=1, highlightbackground=BRUN_200,
                         padx=6)
        champ.pack(side="left", padx=4, pady=3)
        unite = "g" if ligne["methode"] == comptage.METHODE_PESEE else ("pieces" if ligne["nature"] == "piece" else "billets")
        lab_unite = tk.Label(cadre, text=unite, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500, width=6, anchor="w")
        lab_unite.pack(side="left")
        resultat = tk.Label(cadre, text="", font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_700, anchor="e")
        resultat.pack(side="right", padx=8)
        for w in (cadre, lab, champ, resultat):
            w.bind("<Button-1>", lambda e, i=index: self._activer(i))
        return {"cadre": cadre, "champ": champ, "resultat": resultat, "label": lab, "unite": lab_unite}

    def _valeur_saisie(self, i):
        s = self.saisies[i]
        if not s or s == ",":
            return 0.0
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return 0.0

    def _details(self):
        details = []
        for i, ligne in enumerate(self.lignes):
            saisie = self._valeur_saisie(i)
            quantite, montant = comptage.calculer_ligne(ligne, saisie)
            details.append({"nature": ligne["nature"], "valeur": ligne["valeur"], "methode": ligne["methode"],
                            "saisie": saisie, "poids_unitaire": ligne["poids_unitaire"],
                            "quantite": quantite, "montant": montant})
        return details

    def _rafraichir(self):
        details = self._details()
        for i, (w, d) in enumerate(zip(self._widgets, details)):
            actif = (i == self.index_actif)
            fond = FOND_ACTIF if actif else BLANC
            w["cadre"].configure(bg=fond, highlightbackground=OR if actif else BRUN_200,
                                 highlightthickness=2 if actif else 1)
            w["label"].configure(bg=fond)
            w["resultat"].configure(bg=fond)
            w["unite"].configure(bg=fond)
            w["champ"].configure(text=self.saisies[i] + ("_" if actif else ""))
            if self.lignes[i]["methode"] == comptage.METHODE_PESEE:
                texte = "{} p. = {}".format(d["quantite"], _format_dh(d["montant"])) if d["saisie"] else ""
            else:
                texte = "= {}".format(_format_dh(d["montant"])) if d["saisie"] else ""
            w["resultat"].configure(text=texte)
        self.label_total.configure(text=_format_dh(sum(d["montant"] for d in details)))

    def _activer(self, i):
        self.index_actif = i
        self._rafraichir()

    def _touche(self, t):
        s = self.saisies[self.index_actif]
        pesee = self.lignes[self.index_actif]["methode"] == comptage.METHODE_PESEE
        if t == "<-":
            s = s[:-1]
        elif t == ",":
            if not pesee or "," in s:
                return  # virgule seulement pour un poids
            s = (s or "0") + ","
        elif len(s) < 7:
            s = ("" if s == "0" else s) + t
        self.saisies[self.index_actif] = s
        self._rafraichir()

    def _suivant(self):
        if self.index_actif < len(self.lignes) - 1:
            self.index_actif += 1
            self._rafraichir()
        else:
            self._valider()

    def _clavier(self, event):
        if event.char and event.char in "0123456789":
            self._touche(event.char)
        elif event.char in (",", "."):
            self._touche(",")
        elif event.keysym == "BackSpace":
            self._touche("<-")
        elif event.keysym in ("Return", "KP_Enter", "Tab", "Down"):
            self._suivant()
        elif event.keysym == "Up" and self.index_actif > 0:
            self._activer(self.index_actif - 1)

    def _valider(self):
        if getattr(self, "_deja_valide", False) or not self.winfo_exists():
            return
        details = self._details()
        total = round(sum(d["montant"] for d in details), 2)

        def confirmer():
            if getattr(self, "_deja_valide", False):
                return  # anti double validation : un seul enregistrement
            self._deja_valide = True
            self.destroy()
            self.callback(total, details)

        dialogues.confirmer(self, "Confirmer le comptage",
                            "Total compte : {}\nC'est bien ca ?".format(_format_dh(total)),
                            "Confirmer", confirmer)
