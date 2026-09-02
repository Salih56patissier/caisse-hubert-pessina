# -*- coding: utf-8 -*-
"""
Etape 5 : Historique des ventes + Recap (chiffre d'affaires, ticket moyen et
quantites vendues par produit), tous deux proteges par le PIN. S'ouvrent
toujours sur la date du jour ; un calendrier permet de revenir a n'importe
quelle date passee.
"""

import calendar
import tkinter as tk
from datetime import date

from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROUGE, VERT,
    POLICE_CATEGORIE, POLICE_PRODUIT_NOM, POLICE_SOUS_TITRE, POLICE_TICKET_DETAIL,
    POLICE_TITRE, POLICE_BOUTON_ROND,
    BoutonArrondi, ScrollableFrame, largeur_texte,
)

PADDING_BOUTON = 48  # marge interne (gauche+droite) pour qu'un texte ne touche jamais le bord
PADDING_BOUTON_COMPACT = 32  # meme chose, pour les petits boutons ronds

NOMS_JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
NOMS_MOIS = ["Janvier", "Fevrier", "Mars", "Avril", "Mai", "Juin", "Juillet",
             "Aout", "Septembre", "Octobre", "Novembre", "Decembre"]


class _FenetreBase(tk.Toplevel):
    """Squelette commun : en-tete brun + bouton Fermer + barre de date
    (Aujourd'hui / Calendrier) + zone defilante rafraichie a chaque date."""

    def __init__(self, parent, titre_fenetre, titre_affiche):
        super().__init__(parent)
        self.title(titre_fenetre)
        self.configure(bg=CREME)
        largeur, hauteur = 760, 740
        x = parent.winfo_rootx() + max((parent.winfo_width() - largeur) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))
        self.minsize(480, 400)
        self.transient(parent)

        self.date_affichee = date.today()

        entete = tk.Frame(self, bg=BRUN_700, height=64)
        entete.pack(side="top", fill="x")
        tk.Label(entete, text=titre_affiche, font=POLICE_TITRE, bg=BRUN_700, fg=BLANC,
                 padx=20, pady=14).pack(side="left")
        BoutonArrondi(
            entete, lignes=[("Fermer", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=largeur_texte("Fermer", POLICE_CATEGORIE) + PADDING_BOUTON, hauteur=48, rayon=12,
            couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BRUN_700,
        ).pack(side="right", padx=16, pady=12)

        barre_date = tk.Frame(self, bg=CREME)
        barre_date.pack(side="top", fill="x", padx=20, pady=(14, 0))
        self.label_date = tk.Label(barre_date, text="", font=POLICE_SOUS_TITRE, bg=CREME, fg=BRUN_700)
        self.label_date.pack(side="left")
        BoutonArrondi(
            barre_date, lignes=[("Calendrier", POLICE_CATEGORIE, BLANC)], commande=self._ouvrir_calendrier,
            largeur=largeur_texte("Calendrier", POLICE_CATEGORIE) + PADDING_BOUTON, hauteur=44, rayon=12,
            couleur_fond=OR, couleur_bordure=OR, bg=CREME,
        ).pack(side="right")
        BoutonArrondi(
            barre_date, lignes=[("Aujourd'hui", POLICE_CATEGORIE, BLANC)], commande=self._revenir_aujourdhui,
            largeur=largeur_texte("Aujourd'hui", POLICE_CATEGORIE) + PADDING_BOUTON, hauteur=44, rayon=12,
            couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=CREME,
        ).pack(side="right", padx=(0, 8))

        zone_scroll = ScrollableFrame(self, bg=CREME)
        zone_scroll.pack(side="top", fill="both", expand=True)
        self.contenu = tk.Frame(zone_scroll.interior, bg=CREME)
        self.contenu.pack(fill="x", padx=20, pady=16)

        self._mettre_a_jour_label_date()
        self.grab_set()

    def _mettre_a_jour_label_date(self):
        d = self.date_affichee
        texte = "{} {} {} {}".format(NOMS_JOURS[d.weekday()], d.day, NOMS_MOIS[d.month - 1], d.year)
        self.label_date.configure(text=texte)

    def _revenir_aujourdhui(self):
        self.date_affichee = date.today()
        self._mettre_a_jour_label_date()
        self._rafraichir()

    def _ouvrir_calendrier(self):
        SelecteurDate(self, date_initiale=self.date_affichee, callback=self._choisir_date)

    def _choisir_date(self, nouvelle_date):
        self.date_affichee = nouvelle_date
        self._mettre_a_jour_label_date()
        self._rafraichir()

    def _rafraichir(self):
        for widget in self.contenu.winfo_children():
            widget.destroy()
        self._construire()

    def _construire(self):
        raise NotImplementedError


class FenetreHistorique(_FenetreBase):
    def __init__(self, parent, conn):
        self.conn = conn
        super().__init__(parent, "Historique des ventes", "Historique")
        self._construire()

    def _construire(self):
        date_texte = self.date_affichee.strftime("%Y-%m-%d")
        ventes = self.conn.execute(
            "SELECT * FROM ventes WHERE date = ? ORDER BY heure DESC", (date_texte,)
        ).fetchall()

        if not ventes:
            tk.Label(self.contenu, text="Aucune vente encaissee ce jour-la.",
                     font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_500).pack(pady=30)
            return

        for vente in ventes:
            lignes = self.conn.execute(
                "SELECT * FROM vente_lignes WHERE vente_id = ? ORDER BY id", (vente["id"],)
            ).fetchall()

            carte = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
            carte.pack(fill="x", pady=6)

            haut = tk.Frame(carte, bg=BLANC)
            haut.pack(fill="x", padx=12, pady=(10, 4))
            tk.Label(haut, text=vente["heure"], font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_700).pack(side="left")
            tk.Label(haut, text="{:g} DH".format(vente["total"]), font=POLICE_PRODUIT_NOM,
                     bg=BLANC, fg=OR).pack(side="right")

            for ligne in lignes:
                sous_total = ligne["quantite"] * ligne["prix_unitaire"]
                tk.Label(
                    carte, text="{:g} x {}  =  {:g} DH".format(ligne["quantite"], ligne["nom_produit"], sous_total),
                    font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500, anchor="w",
                ).pack(fill="x", padx=20, pady=1)

            tk.Frame(carte, bg=BLANC, height=8).pack()


class FenetreRecap(_FenetreBase):
    def __init__(self, parent, conn):
        self.conn = conn
        super().__init__(parent, "Recap des ventes", "Recap")
        self._construire()

    def _construire(self):
        date_texte = self.date_affichee.strftime("%Y-%m-%d")
        ventes = self.conn.execute("SELECT * FROM ventes WHERE date = ?", (date_texte,)).fetchall()

        if not ventes:
            tk.Label(self.contenu, text="Aucune vente encaissee ce jour-la.",
                     font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_500).pack(pady=30)
            return

        total_jour = sum(v["total"] for v in ventes)
        nb_tickets = len(ventes)
        ticket_moyen = total_jour / nb_tickets

        cadre_stats = tk.Frame(self.contenu, bg=CREME)
        cadre_stats.pack(fill="x", pady=(4, 20))
        cadre_stats.grid_columnconfigure(0, weight=1)
        cadre_stats.grid_columnconfigure(1, weight=1)
        cadre_stats.grid_columnconfigure(2, weight=1)
        self._construire_case_stat(cadre_stats, "{:g} DH".format(total_jour), "CA du jour", 0)
        self._construire_case_stat(cadre_stats, str(nb_tickets), "Tickets", 1)
        self._construire_case_stat(cadre_stats, "{:g} DH".format(round(ticket_moyen, 2)), "Ticket moyen", 2)

        compteur = {}
        for vente in ventes:
            lignes = self.conn.execute(
                "SELECT * FROM vente_lignes WHERE vente_id = ?", (vente["id"],)
            ).fetchall()
            for ligne in lignes:
                compteur[ligne["nom_produit"]] = compteur.get(ligne["nom_produit"], 0) + ligne["quantite"]

        tk.Label(self.contenu, text="Quantites vendues par produit", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(0, 8))

        for nom, quantite in sorted(compteur.items(), key=lambda item: item[1], reverse=True):
            ligne_frame = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
            ligne_frame.pack(fill="x", pady=3)
            tk.Label(ligne_frame, text=nom, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_800,
                     anchor="w").pack(side="left", padx=10, pady=6)
            tk.Label(ligne_frame, text="{:g} vendus".format(quantite), font=POLICE_PRODUIT_NOM,
                     bg=BLANC, fg=VERT).pack(side="right", padx=10, pady=6)

    def _construire_case_stat(self, parent, valeur, libelle, colonne):
        case = tk.Frame(parent, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
        case.grid(row=0, column=colonne, sticky="nsew", padx=4)
        tk.Label(case, text=valeur, font=("Georgia", 24, "bold"), bg=BLANC, fg=BRUN_800).pack(pady=(10, 0))
        tk.Label(case, text=libelle, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500).pack(pady=(0, 10))


class SelecteurDate(tk.Toplevel):
    """Popup calendrier (mois par mois) pour choisir une date passee."""

    def __init__(self, parent, date_initiale, callback):
        super().__init__(parent)
        self.callback = callback
        self.date_initiale = date_initiale
        self.annee = date_initiale.year
        self.mois = date_initiale.month

        self.title("Choisir une date")
        self.configure(bg=BLANC)
        self.resizable(False, False)
        self.transient(parent)

        largeur, hauteur = 360, 440
        x = parent.winfo_rootx() + max((parent.winfo_width() - largeur) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))

        barre_nav = tk.Frame(self, bg=BLANC)
        barre_nav.pack(fill="x", padx=14, pady=14)
        BoutonArrondi(
            barre_nav, lignes=[("<", POLICE_CATEGORIE, BLANC)], commande=self._mois_precedent,
            largeur=50, hauteur=42, rayon=10, couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=BLANC,
        ).pack(side="left")
        self.label_mois = tk.Label(barre_nav, text="", font=POLICE_SOUS_TITRE, bg=BLANC, fg=BRUN_700)
        self.label_mois.pack(side="left", expand=True)
        BoutonArrondi(
            barre_nav, lignes=[(">", POLICE_CATEGORIE, BLANC)], commande=self._mois_suivant,
            largeur=50, hauteur=42, rayon=10, couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=BLANC,
        ).pack(side="right")

        self.frame_jours = tk.Frame(self, bg=BLANC)
        self.frame_jours.pack(padx=14)

        BoutonArrondi(
            self, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=320, hauteur=48, rayon=12, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(pady=16)

        self._dessiner_mois()
        self.grab_set()

    def _mois_precedent(self):
        self.mois -= 1
        if self.mois < 1:
            self.mois = 12
            self.annee -= 1
        self._dessiner_mois()

    def _mois_suivant(self):
        self.mois += 1
        if self.mois > 12:
            self.mois = 1
            self.annee += 1
        self._dessiner_mois()

    def _dessiner_mois(self):
        for widget in self.frame_jours.winfo_children():
            widget.destroy()

        self.label_mois.configure(text="{} {}".format(NOMS_MOIS[self.mois - 1], self.annee))

        for colonne, initiale in enumerate(["L", "M", "M", "J", "V", "S", "D"]):
            tk.Label(self.frame_jours, text=initiale, font=POLICE_TICKET_DETAIL, bg=BLANC,
                     fg=BRUN_500, width=4).grid(row=0, column=colonne, pady=(0, 4))

        aujourdhui = date.today()
        cal = calendar.Calendar(firstweekday=0)
        for rangee, semaine in enumerate(cal.monthdayscalendar(self.annee, self.mois), start=1):
            for colonne, jour in enumerate(semaine):
                if jour == 0:
                    continue
                jour_date = date(self.annee, self.mois, jour)
                est_selectionne = jour_date == self.date_initiale
                est_aujourdhui = jour_date == aujourdhui
                if est_selectionne:
                    fond, texte_couleur = BRUN_700, BLANC
                elif est_aujourdhui:
                    fond, texte_couleur = OR, BLANC
                else:
                    fond, texte_couleur = BLANC, BRUN_800

                case = tk.Label(
                    self.frame_jours, text=str(jour), font=("Segoe UI", 13, "bold"),
                    bg=fond, fg=texte_couleur, width=4, height=2, cursor="hand2",
                    highlightbackground=BRUN_200, highlightthickness=1,
                )
                case.grid(row=rangee, column=colonne, padx=1, pady=1)
                case.bind("<Button-1>", lambda e, d=jour_date: self._choisir(d))

    def _choisir(self, jour_date):
        self.destroy()
        self.callback(jour_date)


class FenetrePeriode(tk.Toplevel):
    """Rapport sur une periode (date de debut -> date de fin, incluses) :
    chiffre d'affaires, nombre de tickets, ticket moyen, et ventes (quantite
    + montant) par categorie et par produit. Pour sortir par exemple "tout
    ce qui a ete vendu en janvier" sans avoir a rouvrir l'Historique jour
    par jour."""

    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.title("Rapport de periode")
        self.configure(bg=CREME)

        largeur, hauteur = 760, 740
        x = parent.winfo_rootx() + max((parent.winfo_width() - largeur) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))
        self.minsize(480, 400)
        self.transient(parent)

        aujourdhui = date.today()
        self.date_debut = aujourdhui.replace(day=1)  # defaut : le mois en cours
        self.date_fin = aujourdhui

        entete = tk.Frame(self, bg=BRUN_700, height=64)
        entete.pack(side="top", fill="x")
        tk.Label(entete, text="Rapport de periode", font=POLICE_TITRE, bg=BRUN_700, fg=BLANC,
                 padx=20, pady=14).pack(side="left")
        BoutonArrondi(
            entete, lignes=[("Fermer", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=largeur_texte("Fermer", POLICE_CATEGORIE) + PADDING_BOUTON, hauteur=48, rayon=12,
            couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BRUN_700,
        ).pack(side="right", padx=16, pady=12)

        barre_dates = tk.Frame(self, bg=CREME)
        barre_dates.pack(side="top", fill="x", padx=20, pady=(14, 4))

        cadre_debut = tk.Frame(barre_dates, bg=CREME)
        cadre_debut.pack(side="left")
        tk.Label(cadre_debut, text="Du", font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500).pack(anchor="w")
        self.label_debut = tk.Label(cadre_debut, text="", font=POLICE_SOUS_TITRE, bg=CREME, fg=BRUN_700)
        self.label_debut.pack(anchor="w")
        BoutonArrondi(
            cadre_debut, lignes=[("Changer", POLICE_BOUTON_ROND, BLANC)], commande=self._choisir_debut,
            largeur=largeur_texte("Changer", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT, hauteur=36, rayon=8,
            couleur_fond=OR, couleur_bordure=OR, bg=CREME,
        ).pack(anchor="w", pady=(4, 0))

        cadre_fin = tk.Frame(barre_dates, bg=CREME)
        cadre_fin.pack(side="left", padx=(30, 0))
        tk.Label(cadre_fin, text="Au", font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500).pack(anchor="w")
        self.label_fin = tk.Label(cadre_fin, text="", font=POLICE_SOUS_TITRE, bg=CREME, fg=BRUN_700)
        self.label_fin.pack(anchor="w")
        BoutonArrondi(
            cadre_fin, lignes=[("Changer", POLICE_BOUTON_ROND, BLANC)], commande=self._choisir_fin,
            largeur=largeur_texte("Changer", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT, hauteur=36, rayon=8,
            couleur_fond=OR, couleur_bordure=OR, bg=CREME,
        ).pack(anchor="w", pady=(4, 0))

        zone_scroll = ScrollableFrame(self, bg=CREME)
        zone_scroll.pack(side="top", fill="both", expand=True)
        self.contenu = tk.Frame(zone_scroll.interior, bg=CREME)
        self.contenu.pack(fill="x", padx=20, pady=16)

        self._mettre_a_jour_labels_dates()
        self._rafraichir()
        self.grab_set()

    def _mettre_a_jour_labels_dates(self):
        self.label_debut.configure(text=self._formater_date(self.date_debut))
        self.label_fin.configure(text=self._formater_date(self.date_fin))

    @staticmethod
    def _formater_date(d):
        return "{} {} {}".format(d.day, NOMS_MOIS[d.month - 1], d.year)

    def _choisir_debut(self):
        SelecteurDate(self, date_initiale=self.date_debut, callback=self._definir_debut)

    def _definir_debut(self, nouvelle_date):
        self.date_debut = nouvelle_date
        if self.date_fin < self.date_debut:
            self.date_fin = nouvelle_date
        self._mettre_a_jour_labels_dates()
        self._rafraichir()

    def _choisir_fin(self):
        SelecteurDate(self, date_initiale=self.date_fin, callback=self._definir_fin)

    def _definir_fin(self, nouvelle_date):
        self.date_fin = nouvelle_date
        if self.date_debut > self.date_fin:
            self.date_debut = nouvelle_date
        self._mettre_a_jour_labels_dates()
        self._rafraichir()

    def _rafraichir(self):
        for widget in self.contenu.winfo_children():
            widget.destroy()
        self._construire()

    def _construire(self):
        debut_texte = self.date_debut.strftime("%Y-%m-%d")
        fin_texte = self.date_fin.strftime("%Y-%m-%d")
        ventes = self.conn.execute(
            "SELECT * FROM ventes WHERE date >= ? AND date <= ? ORDER BY date, heure",
            (debut_texte, fin_texte),
        ).fetchall()

        if not ventes:
            tk.Label(self.contenu, text="Aucune vente encaissee sur cette periode.",
                     font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_500).pack(pady=30)
            return

        total_periode = sum(v["total"] for v in ventes)
        nb_tickets = len(ventes)
        ticket_moyen = total_periode / nb_tickets

        cadre_stats = tk.Frame(self.contenu, bg=CREME)
        cadre_stats.pack(fill="x", pady=(4, 20))
        cadre_stats.grid_columnconfigure(0, weight=1)
        cadre_stats.grid_columnconfigure(1, weight=1)
        cadre_stats.grid_columnconfigure(2, weight=1)
        self._case_stat(cadre_stats, "{:g} DH".format(total_periode), "CA de la periode", 0)
        self._case_stat(cadre_stats, str(nb_tickets), "Tickets", 1)
        self._case_stat(cadre_stats, "{:g} DH".format(round(ticket_moyen, 2)), "Ticket moyen", 2)

        # Chaque ligne de vente ne garde que le nom du produit en texte libre
        # (pour rester correcte meme si le produit est renomme/supprime plus
        # tard) : on retrouve sa categorie en le comparant aux produits
        # actuels - avec la categorie du jour, donc, pas forcement celle du
        # jour de la vente si le produit a change de categorie depuis.
        index_categories = self._index_categories()
        par_produit = {}
        par_categorie = {}
        for vente in ventes:
            lignes = self.conn.execute(
                "SELECT * FROM vente_lignes WHERE vente_id = ?", (vente["id"],)
            ).fetchall()
            for ligne in lignes:
                sous_total = ligne["quantite"] * ligne["prix_unitaire"]

                entree = par_produit.setdefault(ligne["nom_produit"], {"quantite": 0, "total": 0.0})
                entree["quantite"] += ligne["quantite"]
                entree["total"] += sous_total

                nom_categorie = self._categorie_de(ligne["nom_produit"], index_categories)
                entree_cat = par_categorie.setdefault(nom_categorie, {"quantite": 0, "total": 0.0})
                entree_cat["quantite"] += ligne["quantite"]
                entree_cat["total"] += sous_total

        tk.Label(self.contenu, text="Ventes par categorie", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(0, 8))
        for nom, info in sorted(par_categorie.items(), key=lambda item: item[1]["total"], reverse=True):
            self._ligne_resultat(nom, info)

        tk.Label(self.contenu, text="Ventes par produit", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(20, 8))
        for nom, info in sorted(par_produit.items(), key=lambda item: item[1]["total"], reverse=True):
            self._ligne_resultat(nom, info)

    def _ligne_resultat(self, nom, info):
        ligne_frame = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
        ligne_frame.pack(fill="x", pady=3)
        tk.Label(ligne_frame, text=nom, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_800,
                 anchor="w").pack(side="left", padx=10, pady=6)
        tk.Label(
            ligne_frame, text="{:g} vendus  -  {:g} DH".format(info["quantite"], info["total"]),
            font=POLICE_PRODUIT_NOM, bg=BLANC, fg=VERT,
        ).pack(side="right", padx=10, pady=6)

    def _case_stat(self, parent, valeur, libelle, colonne):
        case = tk.Frame(parent, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
        case.grid(row=0, column=colonne, sticky="nsew", padx=4)
        tk.Label(case, text=valeur, font=("Georgia", 24, "bold"), bg=BLANC, fg=BRUN_800).pack(pady=(10, 0))
        tk.Label(case, text=libelle, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500).pack(pady=(0, 10))

    def _index_categories(self):
        lignes = self.conn.execute(
            "SELECT p.nom AS nom_produit, c.nom AS nom_categorie "
            "FROM produits p JOIN categories c ON c.id = p.categorie_id"
        ).fetchall()
        # plus long nom en premier : un produit a sous-produits ("Eclairs")
        # apparait dans les ventes comme "Eclairs <parfum>" - on veut le
        # rattacher a "Eclairs", pas a un autre produit dont le nom serait
        # par coincidence un prefixe plus court.
        return sorted(
            ((r["nom_produit"], r["nom_categorie"]) for r in lignes),
            key=lambda item: len(item[0]), reverse=True,
        )

    @staticmethod
    def _categorie_de(nom_produit, index):
        for nom_ref, nom_categorie in index:
            if nom_produit == nom_ref or nom_produit.startswith(nom_ref + " "):
                return nom_categorie
        return "Sans categorie"
