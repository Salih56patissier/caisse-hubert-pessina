# -*- coding: utf-8 -*-
"""
Fenetre "Comptages par vendeur" (Historique, donc protegee par le code
admin) : filtres par periode et par vendeur, total des ecarts par vendeur,
puis le detail de chaque comptage.

Deux sortes d'ecart (voir caisse.py) :
- ecart de POSTE (fin de poste / fermeture) : compte - attendu, c'est la
  responsabilite du vendeur qui quitte son poste ;
- ecart de PASSATION (prise de poste) : comptage de l'arrivant - comptage
  de celui qui est parti ; normalement 0, sinon quelqu'un s'est trompe en
  comptant (ou de l'argent a bouge entre les deux).
"""

import tkinter as tk
from datetime import date, timedelta

import caisse
import comptage
import vendeurs
from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROUGE, VERT,
    POLICE_BOUTON_ROND, POLICE_CATEGORIE, POLICE_PRODUIT_NOM, POLICE_SOUS_TITRE,
    POLICE_TICKET_DETAIL, POLICE_TITRE,
    BoutonArrondi, ScrollableFrame, largeur_texte,
)

PERIODES = ["Aujourd'hui", "7 jours", "Ce mois", "Mois dernier", "Tout"]


# ---------------------------------------------------------------------------
# Donnees (sans interface, testable)
# ---------------------------------------------------------------------------
def bornes_periode(conn, nom, aujourdhui=None):
    """(date_debut, date_fin) incluses, pour un nom de PERIODES."""
    j = aujourdhui or date.today()
    if nom == "Aujourd'hui":
        return j, j
    if nom == "7 jours":
        return j - timedelta(days=6), j
    if nom == "Ce mois":
        return j.replace(day=1), j
    if nom == "Mois dernier":
        fin = j.replace(day=1) - timedelta(days=1)
        return fin.replace(day=1), fin
    premiere = conn.execute("SELECT MIN(date) AS d FROM releves").fetchone()["d"]
    return (date.fromisoformat(premiere) if premiere else j), j


def releves(conn, debut, fin, vendeur_id=None):
    requete = "SELECT * FROM releves WHERE date BETWEEN ? AND ?"
    params = [debut.isoformat(), fin.isoformat()]
    if vendeur_id is not None:
        requete += " AND vendeur_id = ?"
        params.append(vendeur_id)
    return conn.execute(requete + " ORDER BY date DESC, heure DESC, id DESC", params).fetchall()


def resume_par_vendeur(conn, liste):
    """{vendeur_id: dict} avec les totaux d'ecarts de poste et de passation."""
    res = {}
    for r in liste:
        d = res.setdefault(r["vendeur_id"], {
            "postes": 0, "ecart_poste": 0.0, "hors_poste": 0, "pire": 0.0,
            "passations": 0, "ecart_passation": 0.0, "hors_passation": 0,
        })
        if r["ecart"] is None:
            continue
        hors = not comptage.dans_tolerance(conn, r["ecart"])
        if r["type"] in caisse.TYPES_FIN_DE_POSTE:
            d["postes"] += 1
            d["ecart_poste"] += r["ecart"]
            d["hors_poste"] += hors
            d["pire"] = min(d["pire"], r["ecart"])
        else:
            d["passations"] += 1
            d["ecart_passation"] += r["ecart"]
            d["hors_passation"] += hors
    return res


def _dh(x):
    x = round(x or 0, 2)
    return "0" if abs(x) < 0.005 else "{:+g} DH".format(x)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
class FenetreComptages(tk.Toplevel):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.periode = "Ce mois"
        self.debut, self.fin = bornes_periode(conn, self.periode)
        self.vendeur_id = None  # None = tous

        self.title("Comptages par vendeur")
        self.configure(bg=CREME)
        largeur, hauteur = 760, 740
        x = parent.winfo_rootx() + max((parent.winfo_width() - largeur) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))
        self.minsize(480, 400)
        self.transient(parent)

        entete = tk.Frame(self, bg=BRUN_700, height=64)
        entete.pack(side="top", fill="x")
        tk.Label(entete, text="Comptages", font=("Segoe UI", 24, "bold"), bg=BRUN_700, fg=BLANC,
                 padx=20, pady=14).pack(side="left")
        BoutonArrondi(
            entete, lignes=[("Fermer", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=largeur_texte("Fermer", POLICE_CATEGORIE) + 48, hauteur=48, rayon=12,
            couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BRUN_700,
        ).pack(side="right", padx=16, pady=12)

        self.filtres = tk.Frame(self, bg=CREME)
        self.filtres.pack(side="top", fill="x", padx=20, pady=(12, 0))

        zone = ScrollableFrame(self, bg=CREME)
        zone.pack(side="top", fill="both", expand=True)
        self.contenu = tk.Frame(zone.interior, bg=CREME)
        self.contenu.pack(fill="x", padx=20, pady=10)

        self._rafraichir()
        self.grab_set()

    # --- filtres ---------------------------------------------------------
    def _puce(self, parent, texte, actif, commande):
        fond = BRUN_700 if actif else BLANC
        return BoutonArrondi(
            parent, lignes=[(texte, POLICE_BOUTON_ROND, BLANC if actif else BRUN_800)], commande=commande,
            largeur=largeur_texte(texte, POLICE_BOUTON_ROND) + 32, hauteur=42, rayon=10,
            couleur_fond=fond, couleur_bordure=BRUN_700 if actif else BRUN_200, bg=CREME,
        )

    def _construire_filtres(self):
        for w in self.filtres.winfo_children():
            w.destroy()
        ligne = tk.Frame(self.filtres, bg=CREME)
        ligne.pack(anchor="w", pady=(0, 6))
        for nom in PERIODES:
            self._puce(ligne, nom, nom == self.periode,
                       lambda n=nom: self._choisir_periode(n)).pack(side="left", padx=(0, 6))

        ligne = tk.Frame(self.filtres, bg=CREME)
        ligne.pack(anchor="w", pady=(0, 6))
        self._puce(ligne, "Du {}".format(self.debut.strftime("%d/%m/%Y")), self.periode is None,
                   lambda: self._choisir_date("debut")).pack(side="left", padx=(0, 6))
        self._puce(ligne, "Au {}".format(self.fin.strftime("%d/%m/%Y")), self.periode is None,
                   lambda: self._choisir_date("fin")).pack(side="left", padx=(0, 6))

        ligne = tk.Frame(self.filtres, bg=CREME)
        ligne.pack(anchor="w", pady=(0, 4))
        self._puce(ligne, "Tous", self.vendeur_id is None,
                   lambda: self._choisir_vendeur(None)).pack(side="left", padx=(0, 6))
        for v in vendeurs.lister(self.conn):
            self._puce(ligne, v["nom"], self.vendeur_id == v["id"],
                       lambda i=v["id"]: self._choisir_vendeur(i)).pack(side="left", padx=(0, 6))

    def _choisir_periode(self, nom):
        self.periode = nom
        self.debut, self.fin = bornes_periode(self.conn, nom)
        self._rafraichir()

    def _choisir_date(self, borne):
        from historique import SelecteurDate  # import local : historique importe ce module

        def choisir(d):
            if borne == "debut":
                self.debut = d
                self.fin = max(self.fin, d)
            else:
                self.fin = d
                self.debut = min(self.debut, d)
            self.periode = None  # periode personnalisee
            self._rafraichir()

        SelecteurDate(self, date_initiale=self.debut if borne == "debut" else self.fin, callback=choisir)

    def _choisir_vendeur(self, vendeur_id):
        self.vendeur_id = vendeur_id
        self._rafraichir()

    # --- contenu ---------------------------------------------------------
    def _rafraichir(self):
        if not self.winfo_exists():
            return
        self._construire_filtres()
        for w in self.contenu.winfo_children():
            w.destroy()
        liste = releves(self.conn, self.debut, self.fin, self.vendeur_id)
        if not liste:
            tk.Label(self.contenu, text="Aucun comptage sur cette periode.", font=POLICE_PRODUIT_NOM,
                     bg=CREME, fg=BRUN_500).pack(pady=30)
            return
        self._construire_resume(resume_par_vendeur(self.conn, liste))
        self._construire_detail(liste)
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _couleur(self, ecart, nb_hors):
        if nb_hors:
            return ROUGE
        return VERT if abs(ecart) < 0.005 else BRUN_800

    def _construire_resume(self, res):
        tk.Label(self.contenu, text="Total des ecarts par vendeur", font=POLICE_SOUS_TITRE, bg=CREME,
                 fg=BRUN_700).pack(anchor="w", pady=(0, 6))
        tableau = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
        tableau.pack(fill="x", pady=(0, 4))
        entetes = ["Vendeur", "Fins de poste", "Ecart poste", "Hors tol.", "Pire manque", "Ecart passation"]
        for col, texte in enumerate(entetes):
            tk.Label(tableau, text=texte, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500,
                     anchor="w" if col == 0 else "e").grid(row=0, column=col, sticky="ew", padx=8, pady=(8, 4))
        tableau.grid_columnconfigure(0, weight=1)

        noms = sorted(res, key=lambda vid: (vendeurs.nom(self.conn, vid) or "").lower())
        total = {"postes": 0, "ecart_poste": 0.0, "hors_poste": 0, "pire": 0.0,
                 "ecart_passation": 0.0, "hors_passation": 0}
        for ligne, vid in enumerate(noms, start=1):
            d = res[vid]
            for cle in total:
                total[cle] = min(total[cle], d[cle]) if cle == "pire" else total[cle] + d[cle]
            self._ligne_resume(tableau, ligne, vendeurs.nom(self.conn, vid) or "(inconnu)", d)
        if self.vendeur_id is None and len(noms) > 1:
            tk.Frame(tableau, bg=BRUN_200, height=1).grid(row=len(noms) + 1, column=0, columnspan=6,
                                                           sticky="ew", padx=8)
            self._ligne_resume(tableau, len(noms) + 2, "TOTAL", total, gras=True)
        tk.Label(self.contenu,
                 text="Ecart negatif = il manque de l'argent. Tolerance : +/- {:g} DH. "
                      "Passation = comptage de l'arrivant compare a celui du vendeur precedent (doit etre 0)."
                 .format(comptage.tolerance(self.conn)),
                 font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500, wraplength=700, justify="left",
                 anchor="w").pack(anchor="w", pady=(2, 14))

    def _ligne_resume(self, tableau, ligne, nom, d, gras=False):
        police = POLICE_PRODUIT_NOM if gras else (POLICE_PRODUIT_NOM[0], POLICE_PRODUIT_NOM[1])
        valeurs = [
            (nom, BRUN_800),
            (str(d["postes"]), BRUN_800),
            (_dh(d["ecart_poste"]), self._couleur(d["ecart_poste"], d["hors_poste"])),
            (str(d["hors_poste"]) if d["hors_poste"] else "-", ROUGE if d["hors_poste"] else BRUN_500),
            (_dh(d["pire"]) if d["pire"] < 0 else "-", ROUGE if not comptage.dans_tolerance(self.conn, d["pire"]) else BRUN_500),
            (_dh(d["ecart_passation"]), self._couleur(d["ecart_passation"], d["hors_passation"])),
        ]
        for col, (texte, couleur) in enumerate(valeurs):
            tk.Label(tableau, text=texte, font=police, bg=BLANC, fg=couleur,
                     anchor="w" if col == 0 else "e").grid(row=ligne, column=col, sticky="ew", padx=8, pady=4)

    def _construire_detail(self, liste):
        tk.Label(self.contenu, text="Detail des comptages ({})".format(len(liste)), font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(0, 6))
        for r in liste:
            carte = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
            carte.pack(fill="x", pady=3)
            haut = tk.Frame(carte, bg=BLANC)
            haut.pack(fill="x", padx=12, pady=(8, 2))
            quand = "{}/{} {}".format(r["date"][8:10], r["date"][5:7], r["heure"][:5])
            tk.Label(haut, text=quand, font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_700).pack(side="left")
            tk.Label(haut, text=caisse.LIBELLES.get(r["type"], r["type"]), font=POLICE_PRODUIT_NOM,
                     bg=BLANC, fg=BRUN_800).pack(side="left", padx=(12, 0))
            tk.Label(haut, text=vendeurs.nom(self.conn, r["vendeur_id"]) or "", font=POLICE_PRODUIT_NOM,
                     bg=BLANC, fg=OR).pack(side="left", padx=(12, 0))
            if r["ecart"] is not None:
                ok = comptage.dans_tolerance(self.conn, r["ecart"])
                tk.Label(haut, text=_dh(r["ecart"]), font=POLICE_PRODUIT_NOM, bg=BLANC,
                         fg=VERT if ok else ROUGE).pack(side="right")
            if r["attendu"] is None:
                detail = "Compte {:g} DH (premier comptage, rien a comparer)".format(r["montant_compte"])
            else:
                detail = "Compte {:g} DH  |  attendu {:g} DH".format(r["montant_compte"], r["attendu"])
            if r["compte_par_id"] is not None and r["compte_par_id"] != r["vendeur_id"]:
                detail += "  -  compte par {}".format(vendeurs.nom(self.conn, r["compte_par_id"]))
            if r["note"]:
                detail += "  -  " + r["note"]
            tk.Label(carte, text=detail, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500, anchor="w",
                     justify="left", wraplength=660).pack(fill="x", padx=12, pady=(0, 8))
