# -*- coding: utf-8 -*-
"""
Gestion des ventes : liste des ventes du jour et annulation d'une vente
(voir annulations.py pour les regles).

- Menu vendeur > "Annuler une vente" : le vendeur annule seul ses ventes
  du poste en cours (10 min max), sinon le code admin est demande.
- Historique (deja protege par le code admin) : bouton "Annuler" sur
  chaque vente, sans nouvelle demande de code.

`apres_annulation(annulation, vente)` est appele une fois l'annulation
enregistree (ouverture du tiroir, message "rendez X DH"...).
"""

import tkinter as tk
from datetime import date

import annulations
import dialogues
import vendeurs
from pave_numerique import PaveNumerique
from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROUGE,
    POLICE_CATEGORIE, POLICE_PRODUIT_NOM, POLICE_TICKET_DETAIL, POLICE_TITRE,
    BoutonArrondi, ScrollableFrame, largeur_texte,
)

GRIS = "#9e9e9e"
NB_VENTES_AFFICHEES = 40
NB_LIGNES_DETAIL = 3


def _libelle_paiement(v):
    return "Carte" if v["mode_paiement"] == "carte" else "Especes"


def resume_lignes(conn, vente_id, maximum=NB_LIGNES_DETAIL):
    lignes = conn.execute(
        "SELECT * FROM vente_lignes WHERE vente_id = ? ORDER BY id", (vente_id,)
    ).fetchall()
    textes = ["{:g} x {}".format(l["quantite"], l["nom_produit"]) for l in lignes[:maximum]]
    if len(lignes) > maximum:
        textes.append("... (+{} ligne(s))".format(len(lignes) - maximum))
    return textes


def _pin_admin_correct(conn, code):
    ligne = conn.execute("SELECT valeur FROM config WHERE cle = 'pin_admin'").fetchone()
    return ligne is not None and code == ligne["valeur"]


def lancer_annulation(fenetre, conn, vente_id, vendeur_id, apres_annulation, admin_deja_ok=False,
                      apres_fin=None):
    """Enchaine : controle des droits (code admin si besoin) -> motif ->
    (vente especes d'un poste deja compte : rendre l'argent ?) ->
    confirmation -> annulation. `apres_fin()` est appele a la fin, que
    l'annulation ait eu lieu ou non (pour rafraichir une liste)."""
    v = annulations.vente(conn, vente_id)
    if v is None or v["annulee"]:
        dialogues.Message(fenetre, "Deja annulee", "Cette vente est deja annulee.", niveau="attention",
                          callback_ok=apres_fin)
        return

    def etape_motif(par_admin):
        dialogues.ChoixMotif(fenetre, "Annuler {:g} DH".format(v["total"]), annulations.MOTIFS,
                             lambda motif: etape_remboursement(par_admin, motif), libelle_retour="Retour")

    def etape_remboursement(par_admin, motif):
        # vente especes d'un poste deja compte : l'argent sort-il du tiroir
        # maintenant ? (sinon simple correction, sans effet sur l'attendu)
        if v["mode_paiement"] == "especes" and not annulations.dans_poste_en_cours(conn, v):
            dialogues.Menu(fenetre, "Rendre l'argent ?", [
                ("Rendre {:g} DH (tiroir)".format(v["total"]),
                 lambda: etape_confirmation(par_admin, motif, True), OR),
                ("Correction seulement", lambda: etape_confirmation(par_admin, motif, False), BRUN_700),
            ], libelle_retour="Retour")
            return
        etape_confirmation(par_admin, motif, True)

    def etape_confirmation(par_admin, motif, rembourse):
        texte = "Vente de {} - {:g} DH ({})\nMotif : {}".format(
            v["heure"][:5], v["total"], _libelle_paiement(v), motif)
        if v["mode_paiement"] == "especes" and not rembourse:
            texte += "\nAucun argent ne sort du tiroir."
        dialogues.confirmer(fenetre, "Annuler cette vente ?", texte, "Oui, annuler",
                            lambda: executer(par_admin, motif, rembourse), libelle_non="Retour", couleur_oui=ROUGE)

    def executer(par_admin, motif, rembourse):
        try:
            annulation = annulations.annuler(conn, vente_id, motif, vendeur_id, par_admin=par_admin,
                                             rembourse_tiroir=rembourse)
        except ValueError as exc:
            dialogues.Message(fenetre, "Annulation impossible", str(exc), niveau="attention",
                              callback_ok=apres_fin)
            return
        apres_annulation(annulation, v, apres_fin)

    if admin_deja_ok:
        etape_motif(True)
        return
    ok, raison = annulations.autorisation_vendeur(conn, v, vendeur_id)
    if ok:
        etape_motif(False)
        return

    def verifier(code):
        if _pin_admin_correct(conn, code):
            etape_motif(True)
        else:
            dialogues.Message(fenetre, "Code incorrect", "Le code admin est incorrect.", niveau="erreur")

    def demander_code():
        PaveNumerique(fenetre, titre="Code admin", callback_validation=verifier, masquer=True,
                      chiffres_max=4, longueur_exacte=4, renvoyer_texte=True)

    dialogues.confirmer(fenetre, "Code admin necessaire", raison, "Code admin", demander_code,
                        libelle_non="Retour")


class FenetreGestionVentes(tk.Toplevel):
    """Ventes du jour (les plus recentes en haut) avec un bouton Annuler."""

    def __init__(self, parent, conn, vendeur_id, apres_annulation):
        super().__init__(parent)
        self.conn = conn
        self.vendeur_id = vendeur_id
        self.apres_annulation = apres_annulation
        self.title("Annuler une vente")
        self.configure(bg=CREME)
        largeur, hauteur = 760, 720
        x = parent.winfo_rootx() + max((parent.winfo_width() - largeur) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))
        self.transient(parent)

        entete = tk.Frame(self, bg=BRUN_700, height=64)
        entete.pack(side="top", fill="x")
        tk.Label(entete, text="Annuler une vente", font=("Segoe UI", 24, "bold"), bg=BRUN_700, fg=BLANC,
                 padx=20, pady=14).pack(side="left")
        BoutonArrondi(
            entete, lignes=[("Fermer", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=largeur_texte("Fermer", POLICE_CATEGORIE) + 48, hauteur=48, rayon=12,
            couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BRUN_700,
        ).pack(side="right", padx=16, pady=12)
        tk.Label(self, text="Vos ventes des {} dernieres minutes : sans code.  Autres ventes : code admin."
                 .format(annulations.DELAI_MINUTES),
                 font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500).pack(side="top", anchor="w", padx=20, pady=(10, 0))

        zone = ScrollableFrame(self, bg=CREME)
        zone.pack(side="top", fill="both", expand=True)
        self.contenu = tk.Frame(zone.interior, bg=CREME)
        self.contenu.pack(fill="x", padx=20, pady=12)
        self._construire()
        self.grab_set()

    def _rafraichir(self):
        if not self.winfo_exists():
            return
        for w in self.contenu.winfo_children():
            w.destroy()
        self._construire()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _construire(self):
        liste = annulations.ventes_du_jour(self.conn, date.today().strftime("%Y-%m-%d"),
                                           limite=NB_VENTES_AFFICHEES)
        if not liste:
            tk.Label(self.contenu, text="Aucune vente aujourd'hui.", font=POLICE_PRODUIT_NOM,
                     bg=CREME, fg=BRUN_500).pack(pady=30)
            return
        for v in liste:
            carte_vente(self.contenu, self.conn, v, commande_annuler=lambda i=v["id"]: self._annuler(i))

    def _annuler(self, vente_id):
        lancer_annulation(self, self.conn, vente_id, self.vendeur_id, self.apres_annulation,
                          apres_fin=self._rafraichir)


def carte_vente(parent, conn, v, commande_annuler=None, bg=CREME):
    """Carte d'une vente : heure, vendeur, paiement, total, detail, et
    bouton Annuler (ou mention ANNULEE + motif)."""
    annulee = bool(v["annulee"])
    couleur_texte = GRIS if annulee else BRUN_800
    carte = tk.Frame(parent, bg=BLANC, highlightbackground=ROUGE if annulee else BRUN_200, highlightthickness=1)
    carte.pack(fill="x", pady=5)

    droite = tk.Frame(carte, bg=BLANC)
    droite.pack(side="right", padx=10, pady=8)
    if annulee:
        tk.Label(droite, text="ANNULEE", font=POLICE_PRODUIT_NOM, bg=BLANC, fg=ROUGE).pack()
    elif commande_annuler is not None:
        BoutonArrondi(
            droite, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)], commande=commande_annuler,
            largeur=140, hauteur=56, rayon=12, couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BLANC,
        ).pack()

    gauche = tk.Frame(carte, bg=BLANC)
    gauche.pack(side="left", fill="x", expand=True, padx=12, pady=8)
    haut = tk.Frame(gauche, bg=BLANC)
    haut.pack(fill="x")
    tk.Label(haut, text=v["heure"][:5], font=POLICE_PRODUIT_NOM, bg=BLANC, fg=couleur_texte).pack(side="left")
    details = [vendeurs.nom(conn, v["vendeur_id"]) or "", _libelle_paiement(v)]
    if v["type_vente"] == "rapide":
        details.append("rapide")
    tk.Label(haut, text="  ".join(d for d in details if d), font=POLICE_TICKET_DETAIL, bg=BLANC,
             fg=GRIS if annulee else BRUN_500).pack(side="left", padx=(12, 0))
    police_total = POLICE_PRODUIT_NOM if not annulee else (POLICE_PRODUIT_NOM[0], POLICE_PRODUIT_NOM[1], "bold overstrike")
    tk.Label(haut, text="{:g} DH".format(v["total"]), font=police_total, bg=BLANC,
             fg=GRIS if annulee else OR).pack(side="right")
    for texte in resume_lignes(conn, v["id"]):
        tk.Label(gauche, text=texte, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=couleur_texte,
                 anchor="w").pack(fill="x", padx=(8, 0))
    if annulee:
        a = annulations.annulation_de(conn, v["id"])
        if a is not None:
            texte = "Annulee a {} par {} : {}".format(
                a["heure"][:5], vendeurs.nom(conn, a["vendeur_id"]) or "?", a["motif"])
            if a["par_admin"]:
                texte += " (code admin)"
            if a["mode_paiement"] == "especes" and not a["rembourse_tiroir"]:
                texte += " - correction, pas d'argent rendu"
            tk.Label(gauche, text=texte, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=ROUGE, anchor="w",
                     justify="left", wraplength=480).pack(fill="x", padx=(8, 0), pady=(2, 0))
    return carte
