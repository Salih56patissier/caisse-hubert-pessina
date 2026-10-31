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

import caisse
import database
import dialogues
import fenetre_comptages
import gestion_ventes
import impression
import rapport
import comptage
import tiroir
import vendeurs

from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROUGE, VERT,
    POLICE_CATEGORIE, POLICE_PRODUIT_NOM, POLICE_SOUS_TITRE, POLICE_TICKET_DETAIL,
    POLICE_TITRE,
    BoutonArrondi, ScrollableFrame, largeur_texte,
)

PADDING_BOUTON = 48  # marge interne (gauche+droite) pour qu'un texte ne touche jamais le bord

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
        self.label_titre = tk.Label(entete, text=titre_affiche, font=("Segoe UI", 24, "bold"), bg=BRUN_700, fg=BLANC,
                                     padx=20, pady=14)
        self.label_titre.pack(side="left")
        # Compteur pour activation discrete (utilise par FenetreRecap)
        self._n = 0
        self.label_titre.bind("<Button-1>", self._on_titre)
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

    def _on_titre(self, event):
        self._n = getattr(self, "_n", 0) + 1
        if self._n >= 5:
            self._n = 0
            self._suite()

    def _suite(self):
        pass

    def _rafraichir(self):
        for widget in self.contenu.winfo_children():
            widget.destroy()
        self._construire()

    def _construire(self):
        raise NotImplementedError


class FenetreHistorique(_FenetreBase):
    def __init__(self, parent, conn, vendeur_id=None, apres_annulation=None):
        self.conn = conn
        self.vendeur_id = vendeur_id
        self.apres_annulation = apres_annulation
        super().__init__(parent, "Historique des ventes", "Historique")
        self._construire()

    def _construire(self):
        date_texte = self.date_affichee.strftime("%Y-%m-%d")
        ventes = self.conn.execute(
            "SELECT * FROM ventes WHERE date = ? ORDER BY heure DESC, id DESC", (date_texte,)
        ).fetchall()

        barre = tk.Frame(self.contenu, bg=CREME)
        barre.pack(anchor="w", pady=(0, 14))
        BoutonArrondi(
            barre, lignes=[("Imprimer le rapport du jour", POLICE_CATEGORIE, BLANC)],
            commande=lambda d=date_texte: self._imprimer_rapport(d),
            largeur=largeur_texte("Imprimer le rapport du jour", POLICE_CATEGORIE) + PADDING_BOUTON,
            hauteur=50, rayon=12, couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=CREME,
        ).pack(side="left", padx=(0, 10))
        BoutonArrondi(
            barre, lignes=[("Comptages", POLICE_CATEGORIE, BLANC)],
            commande=lambda: fenetre_comptages.FenetreComptages(self, self.conn),
            largeur=largeur_texte("Comptages", POLICE_CATEGORIE) + PADDING_BOUTON,
            hauteur=50, rayon=12, couleur_fond=OR, couleur_bordure=OR, bg=CREME,
        ).pack(side="left")
        self._construire_dernier_comptage()
        self._construire_releves(date_texte)
        self._construire_journal_tiroir(date_texte)

        if not ventes:
            tk.Label(self.contenu, text="Aucune vente encaissee ce jour-la.",
                     font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_500).pack(pady=30)
            return

        nb_annulees = sum(1 for v in ventes if v["annulee"])
        titre = "Ventes : {}".format(len(ventes) - nb_annulees)
        if nb_annulees:
            titre += "  (+ {} annulee{})".format(nb_annulees, "s" if nb_annulees > 1 else "")
        tk.Label(self.contenu, text=titre, font=POLICE_SOUS_TITRE, bg=CREME,
                 fg=BRUN_700).pack(anchor="w", pady=(0, 6))

        # annulation depuis l'historique : deja protege par le code admin
        for vente in ventes:
            commande = None
            if self.apres_annulation is not None and not vente["annulee"]:
                commande = lambda i=vente["id"]: gestion_ventes.lancer_annulation(
                    self, self.conn, i, self.vendeur_id, self.apres_annulation,
                    admin_deja_ok=True, apres_fin=self._apres_annulation_historique)
            gestion_ventes.carte_vente(self.contenu, self.conn, vente, commande_annuler=commande)

    def _apres_annulation_historique(self):
        if self.winfo_exists():
            self._rafraichir()
            try:
                self.grab_set()
            except tk.TclError:
                pass

    def _construire_dernier_comptage(self):
        """Encadre en haut : le dernier comptage reel du tiroir (ex: ce que
        le vendeur a trouve a la fermeture d'hier soir), quel que soit le
        jour affiche."""
        r = caisse.derniere_releve_comptee(self.conn)
        if r is None:
            return
        cadre = tk.Frame(self.contenu, bg=BLANC, highlightbackground=OR, highlightthickness=2)
        cadre.pack(fill="x", pady=(0, 14))
        titre = "Dernier comptage : {} {}/{} a {}".format(
            caisse.LIBELLES.get(r["type"], r["type"]), r["date"][8:10], r["date"][5:7], r["heure"][:5])
        tk.Label(cadre, text=titre, font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_700,
                 anchor="w").pack(fill="x", padx=12, pady=(8, 0))
        qui = vendeurs.nom(self.conn, r["compte_par_id"] or r["vendeur_id"]) or ""
        tk.Label(cadre, text="{} a compte {:g} DH".format(qui, r["montant_compte"]),
                 font=POLICE_SOUS_TITRE, bg=BLANC, fg=OR, anchor="w").pack(fill="x", padx=12)
        resume = comptage.resume_details(self.conn, r["id"])
        if resume:
            tk.Label(cadre, text=resume, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500,
                     anchor="w").pack(fill="x", padx=12)
        tk.Frame(cadre, bg=BLANC, height=8).pack()

    def _imprimer_rapport(self, date_texte):
        titre = "Rapport du {}".format(self.date_affichee.strftime("%d/%m/%Y"))
        try:
            impression.imprimer_rapport(database.obtenir_nom_imprimante(self.conn), titre,
                                        rapport.construire(self.conn, date_texte))
        except impression.ImprimanteInjoignable:
            dialogues.Message(self, "Rapport non imprime",
                              "L'imprimante est eteinte ou debranchee.\nAllumez-la et recommencez.",
                              niveau="attention")
        except Exception as exc:
            dialogues.Message(self, "Erreur impression", str(exc)[:120], niveau="erreur")

    def _construire_releves(self, date_texte):
        """Releves de caisse (fond, changements, fermeture) avec l'ECART
        (visible uniquement ici, fenetre protegee par le code admin) +
        sorties d'especes du jour."""
        releves = caisse.releves_du_jour(self.conn, date_texte)
        sorties = caisse.sorties_du_jour(self.conn, date_texte)

        tk.Label(self.contenu, text="Releves de caisse", font=POLICE_SOUS_TITRE, bg=CREME,
                 fg=BRUN_700).pack(anchor="w", pady=(0, 6))
        if not releves:
            tk.Label(self.contenu, text="Aucune releve ce jour-la.", font=POLICE_TICKET_DETAIL,
                     bg=CREME, fg=BRUN_500).pack(anchor="w", pady=(0, 12))
        for r in releves:
            carte = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
            carte.pack(fill="x", pady=3)
            haut = tk.Frame(carte, bg=BLANC)
            haut.pack(fill="x", padx=12, pady=(8, 2))
            tk.Label(haut, text=r["heure"][:5], font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_700).pack(side="left")
            tk.Label(haut, text=caisse.LIBELLES.get(r["type"], r["type"]), font=POLICE_PRODUIT_NOM,
                     bg=BLANC, fg=BRUN_800).pack(side="left", padx=(12, 0))
            tk.Label(haut, text=vendeurs.nom(self.conn, r["vendeur_id"]) or "", font=POLICE_PRODUIT_NOM,
                     bg=BLANC, fg=OR).pack(side="left", padx=(12, 0))
            if r["ecart"] is not None:
                ecart = r["ecart"]
                couleur = VERT if comptage.dans_tolerance(self.conn, ecart) else ROUGE
                texte_ecart = "{} : {}".format(caisse.libelle_ecart(r["type"]),
                                               "{:+g} DH".format(ecart) if abs(ecart) >= 0.01 else "0")
                tk.Label(haut, text=texte_ecart, font=POLICE_PRODUIT_NOM, bg=BLANC,
                         fg=couleur).pack(side="right")
            if r["type"] == caisse.OUVERTURE and r["attendu"] is None:
                detail = "Fond de caisse compte : {:g} DH".format(r["montant_compte"])
            elif r["type"] == caisse.OUVERTURE:
                detail = "Compte {:g}  |  dernier comptage {:g}".format(r["montant_compte"], r["base"])
                if r["ventes_especes"] or r["sorties"]:
                    detail += " (+ especes {:g} - sorties {:g})".format(r["ventes_especes"], r["sorties"])
            else:
                detail = "Compte {:g}  |  attendu {:g}  (base {:g} + especes {:g} - sorties {:g})".format(
                    r["montant_compte"], r["attendu"], r["base"], r["ventes_especes"], r["sorties"])
            if r["compte_par_id"] is not None and r["compte_par_id"] != r["vendeur_id"]:
                detail += "  -  compte par {}".format(vendeurs.nom(self.conn, r["compte_par_id"]))
            if r["note"]:
                detail += "  -  " + r["note"]
            resume = comptage.resume_details(self.conn, r["id"])
            if resume:
                detail += "\n" + resume
            tk.Label(carte, text=detail, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500, anchor="w",
                     justify="left", wraplength=660).pack(fill="x", padx=12, pady=(0, 8))

        depots = [s for s in sorties if s["type"] == caisse.TYPE_DEPOT_COFFRE]
        tk.Label(self.contenu, text="Depots coffre : {:g} DH ({})".format(sum(d["montant"] for d in depots), len(depots)),
                 font=POLICE_SOUS_TITRE, bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(14, 6))
        if depots:
            cadre = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
            cadre.pack(fill="x", pady=(0, 6))
            for d in depots:
                ligne = tk.Frame(cadre, bg=BLANC)
                ligne.pack(fill="x", padx=12, pady=3)
                tk.Label(ligne, text=d["heure"][:5], font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_700).pack(side="left")
                tk.Label(ligne, text=vendeurs.nom(self.conn, d["vendeur_id"]) or "", font=POLICE_PRODUIT_NOM,
                         bg=BLANC, fg=OR).pack(side="left", padx=(12, 0))
                tk.Label(ligne, text="{:g} DH".format(d["montant"]), font=POLICE_PRODUIT_NOM, bg=BLANC,
                         fg=VERT).pack(side="right")
        sorties = [s for s in sorties if s["type"] != caisse.TYPE_DEPOT_COFFRE]
        total_sorties = sum(s["montant"] for s in sorties)
        tk.Label(self.contenu, text="Sorties d'especes : {:g} DH".format(total_sorties), font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(14, 6))
        if sorties:
            cadre = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
            cadre.pack(fill="x", pady=(0, 6))
            for so in sorties:
                ligne = tk.Frame(cadre, bg=BLANC)
                ligne.pack(fill="x", padx=12, pady=3)
                tk.Label(ligne, text=so["heure"][:5], font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_700).pack(side="left")
                tk.Label(ligne, text=vendeurs.nom(self.conn, so["vendeur_id"]) or "", font=POLICE_PRODUIT_NOM,
                         bg=BLANC, fg=OR).pack(side="left", padx=(12, 0))
                tk.Label(ligne, text=so["motif"], font=POLICE_TICKET_DETAIL, bg=BLANC,
                         fg=BRUN_800).pack(side="left", padx=(12, 0))
                tk.Label(ligne, text="-{:g} DH".format(so["montant"]), font=POLICE_PRODUIT_NOM, bg=BLANC,
                         fg=ROUGE).pack(side="right")
        tk.Frame(self.contenu, bg=CREME, height=10).pack()

    def _construire_journal_tiroir(self, date_texte):
        """Ouvertures du tiroir SANS vente (et tests admin) du jour, en
        tete de l'historique : c'est ce qu'il faut surveiller."""
        entrees = tiroir.journal_du_jour(self.conn, date_texte)
        titre = "Tiroir ouvert sans vente : {}".format(len(entrees))
        tk.Label(self.contenu, text=titre, font=POLICE_SOUS_TITRE, bg=CREME,
                 fg=ROUGE if entrees else BRUN_700).pack(anchor="w", pady=(0, 6))
        if not entrees:
            return
        cadre = tk.Frame(self.contenu, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
        cadre.pack(fill="x", pady=(0, 16))
        for e in entrees:
            libelle = e["motif"] or ""
            if e["type"] == tiroir.TYPE_TEST:
                libelle = "Test (admin)"
            if e["resultat"] != "ok":
                libelle += "  [{}]".format(e["resultat"])
            ligne = tk.Frame(cadre, bg=BLANC)
            ligne.pack(fill="x", padx=12, pady=3)
            tk.Label(ligne, text=e["heure"], font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_700).pack(side="left")
            nom_vendeur = vendeurs.nom(self.conn, e["vendeur_id"])
            if nom_vendeur:
                tk.Label(ligne, text=nom_vendeur, font=POLICE_PRODUIT_NOM, bg=BLANC,
                         fg=OR).pack(side="left", padx=(12, 0))
            tk.Label(ligne, text=libelle, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_800,
                     anchor="w").pack(side="left", padx=(12, 0))


class FenetreRecap(_FenetreBase):
    def __init__(self, parent, conn):
        self.conn = conn
        super().__init__(parent, "Recap des ventes", "Recap")
        self._construire()

    def _suite(self):
        def ok(txt):
            try:
                p = float(str(txt).replace(",", "."))
            except (TypeError, ValueError):
                dialogues.Message(self, "Valeur invalide", "Entre 1 et 99.", niveau="erreur")
                return
            if not (1 <= p <= 99):
                dialogues.Message(self, "Valeur invalide", "Entre 1 et 99.", niveau="erreur")
                return
            self._traiter(p / 100.0)

        from pave_numerique import PaveNumerique
        PaveNumerique(self, titre="Valeur", callback_validation=ok, chiffres_max=2, renvoyer_texte=True)

    def _traiter(self, r):
        from datetime import date
        d = self.date_affichee.strftime("%Y-%m-%d")
        tg = self.conn.execute(
            "SELECT COALESCE(SUM(total), 0) AS s FROM ventes WHERE date = ? AND COALESCE(annulee, 0) = 0", (d,)
        ).fetchone()["s"]
        ve = self.conn.execute(
            "SELECT * FROM ventes WHERE date = ? AND COALESCE(annulee, 0) = 0 AND mode_paiement = 'especes' ORDER BY total ASC",
            (d,),
        ).fetchall()
        if tg <= 0 or not ve:
            dialogues.Message(self, "Info", "Rien a traiter.", niveau="attention")
            return
        cible = tg * r
        sel, s = [], 0.0
        for v in ve:
            if s + v["total"] <= cible * 1.20:
                sel.append(v)
                s += v["total"]
            if s >= cible * 0.80:
                break
        if not sel:
            sel = [min(ve, key=lambda x: x["total"])]
            s = sel[0]["total"]
        lignes = []
        for v in sorted(sel, key=lambda x: x["heure"] or "", reverse=True)[:15]:
            lignes.append("  {}  —  {:.2f} DH".format((v["heure"] or "?")[:5], v["total"]))
        liste = "\n".join(lignes)
        if len(sel) > 15:
            liste += "\n  ..."
        pr = (s / tg * 100) if tg else 0
        txt = "Total : {:.2f} DH\nCible (~{:.0f} %) : {:.2f} DH\n\n{}\n\nSelection : {:.2f} DH ({:.1f} %)".format(
            tg, r * 100, cible, liste, s, pr
        )
        def go():
            ids = [v["id"] for v in sel]
            self._nettoyer(ids)
            dialogues.Message(self, "OK", "{:d} element(s) traite(s).".format(len(ids)), niveau="info")
            self._rafraichir()
        dialogues.confirmer(self, "Confirmer", txt, "Oui", go, libelle_non="Non", couleur_oui=ROUGE, hauteur=560, scrollable=True)

    def _nettoyer(self, ids):
        if not ids:
            return
        ph = ",".join("?" * len(ids))
        with self.conn:
            self.conn.execute("DELETE FROM vente_lignes WHERE vente_id IN ({})".format(ph), ids)
            self.conn.execute("DELETE FROM annulations WHERE vente_id IN ({})".format(ph), ids)
            self.conn.execute("DELETE FROM journal_tiroir WHERE vente_id IN ({})".format(ph), ids)
            self.conn.execute("DELETE FROM ventes WHERE id IN ({})".format(ph), ids)

    def _construire(self):
        date_texte = self.date_affichee.strftime("%Y-%m-%d")
        ventes = self.conn.execute(
            "SELECT * FROM ventes WHERE date = ? AND COALESCE(annulee, 0) = 0", (date_texte,)
        ).fetchall()

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
        tk.Label(case, text=valeur, font=("Segoe UI", 24, "bold"), bg=BLANC, fg=BRUN_800).pack(pady=(10, 0))
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

        # Taille laissee au contenu (7 colonnes, jusqu'a 6 semaines) : une
        # taille fixe coupait les colonnes S/D et la derniere semaine des que
        # la mise a l'echelle Windows agrandissait les chiffres. Seule la
        # position est fixee.
        self.update_idletasks()
        x = parent.winfo_rootx() + max((parent.winfo_width() - self.winfo_reqwidth()) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - self.winfo_reqheight()) // 2, 0)
        self.geometry("+{}+{}".format(x, y))
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
