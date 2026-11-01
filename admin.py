# -*- coding: utf-8 -*-
"""
Etape 4 : mode Admin (protege par PIN) - gestion des categories, produits,
sous-produits (parfums), et export/import du catalogue en JSON.
"""

import json
import tkinter as tk
from tkinter import messagebox

import database
import dialogues
import tiroir
import vendeurs
import comptage
import caisse
import sync
import impression
import ticket_z
from pave_numerique import PaveNumerique
from styles import (
    BLANC, BRUN_200, BRUN_500, BRUN_700, BRUN_800, CREME, OR, ROUGE, VERT,
    POLICE_CATEGORIE, POLICE_PRODUIT_NOM, POLICE_SOUS_TITRE, POLICE_TICKET_DETAIL,
    POLICE_TITRE, POLICE_BOUTON_ROND,
    BoutonArrondi, ScrollableFrame, largeur_texte, rectangle_arrondi, zone_travail_windows,
)

PADDING_BOUTON = 48  # marge interne (gauche+droite) pour qu'un texte ne touche jamais le bord
PADDING_BOUTON_COMPACT = 32  # meme chose, pour les petits boutons ronds Modifier/Supprimer
HAUTEUR_PASTILLE_ADMIN = 50
ESPACE_PASTILLE_ADMIN = 10


class PastilleCategorie(tk.Canvas):
    """Pastille de categorie utilisee dans le Mode Admin : un tap la
    selectionne. (Le reordonnancement se fait via les boutons fleches
    "Deplacer" a cote de "Modifier"/"Supprimer" une fois la categorie
    selectionnee - pas par glisser-deposer : sur l'ecran tactile du magasin,
    le glisser-deposer precedent etait instable - la pastille tremblait et
    sautait, rendant tres difficile de la lacher a la bonne place.)"""

    def __init__(self, parent, categorie_id, nom, actif, largeur, hauteur, on_tap, bg=CREME):
        super().__init__(parent, width=largeur, height=hauteur, bg=bg, highlightthickness=0)
        self.categorie_id = categorie_id
        self.largeur = largeur
        self.hauteur = hauteur

        self._dessiner(nom, actif)
        self.bind("<ButtonRelease-1>", lambda event: on_tap(self.categorie_id))

    def _dessiner(self, nom, actif):
        self.delete("all")
        rectangle_arrondi(self, 1, 1, self.largeur - 1, self.hauteur - 1, self.hauteur // 2,
                           fill=BRUN_700 if actif else BLANC,
                           outline=BRUN_700 if actif else BRUN_200)
        self.create_text(self.largeur / 2, self.hauteur / 2, text=nom, font=POLICE_CATEGORIE,
                          fill=BLANC if actif else BRUN_700)


class FenetreAdmin(tk.Toplevel):
    def __init__(self, parent, conn):
        super().__init__(parent)
        self.conn = conn
        self.categorie_selectionnee_id = None

        self.title("Mode Admin - Hubert & Pessina")
        self.configure(bg=CREME)

        # Taille demandee (1080x780), mais reduite pour rester dans la zone
        # de travail reelle (hors barre des taches) : sur un petit ecran
        # (1024x768 constate en magasin), une fenetre plus grande que
        # l'ecran forcait a la deplacer/redimensionner a la main pour
        # atteindre les boutons du bas.
        x_ecran, y_ecran, largeur_ecran, hauteur_ecran = zone_travail_windows()
        if largeur_ecran <= 0 or hauteur_ecran <= 0:
            x_ecran, y_ecran, largeur_ecran, hauteur_ecran = 0, 0, 1080, 780
        largeur = min(1080, largeur_ecran - 20)
        hauteur = min(780, hauteur_ecran - 20)
        x = x_ecran + max((largeur_ecran - largeur) // 2, 0)
        y = y_ecran + max((hauteur_ecran - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))
        self.minsize(min(880, largeur), min(640, hauteur))
        self.transient(parent)

        self._construire_interface()
        self._charger_categories()

        self.grab_set()

    # ------------------------------------------------------------------
    def _construire_interface(self):
        entete = tk.Frame(self, bg=BRUN_700, height=64)
        entete.pack(side="top", fill="x")
        tk.Label(entete, text="Mode Admin", font=("Segoe UI", 24, "bold"), bg=BRUN_700, fg=BLANC,
                 padx=20, pady=14).pack(side="left")
        BoutonArrondi(
            entete, lignes=[("Fermer", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=largeur_texte("Fermer", POLICE_CATEGORIE) + PADDING_BOUTON, hauteur=48, rayon=12,
            couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BRUN_700,
        ).pack(side="right", padx=16, pady=12)

        zone_scroll = ScrollableFrame(self, bg=CREME)
        zone_scroll.pack(side="top", fill="both", expand=True)
        self.contenu = zone_scroll.interior

        cadre_interne = tk.Frame(self.contenu, bg=CREME)
        cadre_interne.pack(fill="x", padx=20, pady=16)

        tk.Label(cadre_interne, text="Categories (selectionnez-en une, puis Deplacer pour la reordonner)",
                 font=POLICE_SOUS_TITRE, bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(0, 6))
        self.frame_categories = tk.Frame(cadre_interne, bg=CREME)
        self.frame_categories.pack(anchor="w", fill="x", pady=(0, 10))
        self.frame_categories.bind("<Configure>", lambda e: self._replacer_pastilles())

        self.frame_categorie_actions = tk.Frame(cadre_interne, bg=CREME)
        self.frame_categorie_actions.pack(anchor="w", fill="x", pady=(0, 20))

        tk.Label(cadre_interne, text="Produits", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(0, 6))
        self.frame_produits = tk.Frame(cadre_interne, bg=CREME)
        self.frame_produits.pack(anchor="w", fill="x", pady=(0, 20))

        tk.Label(cadre_interne, text="Export / Import du catalogue", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(0, 6))
        frame_export_import = tk.Frame(cadre_interne, bg=CREME)
        frame_export_import.pack(anchor="w", fill="x")
        BoutonArrondi(
            frame_export_import, lignes=[("Exporter les produits", POLICE_CATEGORIE, BLANC)],
            commande=self._exporter,
            largeur=largeur_texte("Exporter les produits", POLICE_CATEGORIE) + PADDING_BOUTON,
            hauteur=52, rayon=12,
            couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=CREME,
        ).pack(side="left", padx=(0, 10))
        BoutonArrondi(
            frame_export_import, lignes=[("Importer les produits", POLICE_CATEGORIE, BLANC)],
            commande=self._importer,
            largeur=largeur_texte("Importer les produits", POLICE_CATEGORIE) + PADDING_BOUTON,
            hauteur=52, rayon=12,
            couleur_fond=OR, couleur_bordure=OR, bg=CREME,
        ).pack(side="left")

        tk.Label(cadre_interne, text="Taux de TVA", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(20, 6))
        self.frame_tva = tk.Frame(cadre_interne, bg=CREME)
        self.frame_tva.pack(anchor="w", fill="x")
        self._charger_taux_tva()

        tk.Label(cadre_interne, text="Impression des tickets", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(20, 6))
        self.frame_impression = tk.Frame(cadre_interne, bg=CREME)
        self.frame_impression.pack(anchor="w", fill="x")
        self._charger_reglages_impression()

        tk.Label(cadre_interne, text="Tiroir-caisse", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(20, 6))
        self.frame_tiroir = tk.Frame(cadre_interne, bg=CREME)
        self.frame_tiroir.pack(anchor="w", fill="x", pady=(0, 20))
        self._charger_reglages_tiroir()

        tk.Label(cadre_interne, text="Vendeurs", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=BRUN_700).pack(anchor="w", pady=(0, 6))
        self.frame_vendeurs = tk.Frame(cadre_interne, bg=CREME)
        self.frame_vendeurs.pack(anchor="w", fill="x", pady=(0, 20))
        self._charger_vendeurs()

        tk.Label(cadre_interne, text="Ticket Z (fin de periode + remise a zero)", font=POLICE_SOUS_TITRE,
                 bg=CREME, fg=ROUGE).pack(anchor="w", pady=(0, 6))
        frame_z = tk.Frame(cadre_interne, bg=CREME)
        frame_z.pack(anchor="w", fill="x", pady=(0, 30))
        tk.Label(frame_z,
                 text="Imprime les totaux (CA, TVA par taux, paiements...) puis EFFACE DEFINITIVEMENT de la caisse "
                      "les ventes, annulations, comptages, sorties, depots coffre et le journal du tiroir. "
                      "Produits, vendeurs et reglages sont conserves.",
                 font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500, anchor="w", justify="left",
                 wraplength=880).pack(anchor="w", pady=(0, 6))
        self._petit_bouton(frame_z, "Faire le Z n. {}".format(ticket_z.numero_suivant(self.conn)),
                           self._faire_z, ROUGE).pack(anchor="w")

    # ------------------------------------------------------------------
    # Google Sheets (masque par defaut)
    # ------------------------------------------------------------------
    def _clic_coffre(self, event=None):
        self._clics_coffre = getattr(self, "_clics_coffre", 0) + 1
        if self._clics_coffre >= 5:
            self._clics_coffre = 0
            self._sync_visible = not getattr(self, "_sync_visible", False)
            if self._sync_visible:
                self.frame_sync.pack(anchor="w", fill="x", pady=(0, 20))
                self._charger_sync()
            else:
                self.frame_sync.pack_forget()

    def _charger_sync(self):
        if not getattr(self, "_sync_visible", False):
            return
        if not self.winfo_exists():
            return
        for widget in self.frame_sync.winfo_children():
            widget.destroy()
        actif = sync.active(self.conn)
        adresse = sync.url(self.conn)
        # Les secrets (jeton + URL complete) ne s'affichent pas en clair :
        # un second code PIN est demande via "Afficher les codes".
        afficher_secrets = getattr(self, "_sync_secrets_visibles", False)

        def ligne_info(texte, couleur=BRUN_800):
            tk.Label(self.frame_sync, text=texte, font=POLICE_PRODUIT_NOM, bg=CREME, fg=couleur,
                     anchor="w", justify="left", wraplength=880).pack(anchor="w", pady=2)

        if afficher_secrets:
            ligne_info("Code secret a recopier dans le script Google : {}".format(sync.jeton(self.conn)))
            ligne_info(
                "Adresse du script : {}".format(
                    adresse[:70] + "..." if len(adresse) > 70 else (adresse or "(non renseignee)")
                ),
                BRUN_800 if adresse else ROUGE,
            )
        else:
            jeton = sync.jeton(self.conn) or ""
            jeton_masque = (jeton[:2] + "••••" + jeton[-2:]) if len(jeton) >= 4 else "••••••••"
            ligne_info("Code secret : {}  (masque — Afficher les codes pour le voir)".format(jeton_masque))
            if adresse:
                ligne_info("Adresse du script : configuree (masquee)", BRUN_800)
            else:
                ligne_info("Adresse du script : (non renseignee)", ROUGE)

        etat = sync.ETAT
        if not actif:
            ligne_info("Etat : synchronisation DESACTIVEE", ROUGE)
        else:
            couleur = VERT if etat["ok"] else (ROUGE if etat["ok"] is False else BRUN_500)
            quand = " (a {})".format(etat["heure"]) if etat["heure"] else ""
            ligne_info("Etat : {}{}".format(etat["message"], quand), couleur)
        ligne_info("Lignes en attente d'envoi : {}".format(sync.lignes_en_attente(self.conn)), BRUN_500)

        boutons = tk.Frame(self.frame_sync, bg=CREME)
        boutons.pack(anchor="w", pady=(6, 0))
        self._petit_bouton(boutons, "Adresse du script", self._saisir_url_sync, OR).pack(side="left", padx=(0, 8))
        self._petit_bouton(boutons, "Desactiver" if actif else "Activer",
                           lambda: (sync.definir_active(self.conn, not actif), sync.demander_synchro(),
                                    self._charger_sync()),
                           ROUGE if actif else VERT).pack(side="left", padx=(0, 8))
        self._petit_bouton(boutons, "Synchroniser maintenant",
                           lambda: (sync.demander_synchro(), self.after(4000, self._charger_sync)),
                           BRUN_700).pack(side="left", padx=(0, 8))
        self._petit_bouton(boutons, "Actualiser", self._charger_sync, BRUN_500).pack(side="left", padx=(0, 8))
        if afficher_secrets:
            self._petit_bouton(boutons, "Masquer les codes", self._masquer_secrets_sync, BRUN_500).pack(side="left")
        else:
            self._petit_bouton(boutons, "Afficher les codes", self._demander_affichage_secrets_sync, BRUN_700).pack(side="left")

    def _demander_affichage_secrets_sync(self):
        """Second code PIN requis pour afficher jeton + URL en clair."""
        def verifier(code):
            ligne = self.conn.execute(
                "SELECT valeur FROM config WHERE cle = 'pin_admin'"
            ).fetchone()
            if ligne is None or code != ligne["valeur"]:
                dialogues.Message(self, "Code incorrect", "Le code admin est incorrect.", niveau="erreur")
                return
            self._sync_secrets_visibles = True
            self._charger_sync()

        PaveNumerique(
            self, titre="Code admin (afficher les codes)",
            callback_validation=verifier, masquer=True,
            chiffres_max=4, longueur_exacte=4, renvoyer_texte=True,
        )

    def _masquer_secrets_sync(self):
        self._sync_secrets_visibles = False
        self._charger_sync()

    # ------------------------------------------------------------------
    # Ticket Z : impression puis remise a zero (voir ticket_z.py)
    # ------------------------------------------------------------------
    def _faire_z(self):
        ok, raison = ticket_z.verifier(self.conn)
        if not ok:
            dialogues.Message(self, "Z impossible", raison, niveau="attention")
            return
        numero = ticket_z.numero_suivant(self.conn)
        dialogues.confirmer(
            self, "Ticket Z n. {}".format(numero),
            "Imprimer le Z puis EFFACER toutes les ventes de la caisse ?\nC'est definitif.",
            "Imprimer", lambda: self._imprimer_z(numero), couleur_oui=ROUGE)

    def _imprimer_z(self, numero):
        try:
            impression.imprimer_rapport(database.obtenir_nom_imprimante(self.conn),
                                        "TICKET Z", ticket_z.construire(self.conn, numero))
        except impression.ImprimanteInjoignable:
            dialogues.Message(self, "Z non imprime", "L'imprimante est eteinte ou debranchee.\n"
                              "Rien n'a ete efface.", niveau="attention")
            return
        except Exception as exc:
            dialogues.Message(self, "Z non imprime", "{}\n\nRien n'a ete efface.".format(str(exc)[:120]),
                              niveau="erreur")
            return
        # l'envoi a l'imprimante ne prouve pas que le papier est sorti
        dialogues.confirmer(
            self, "Ticket Z imprime ?",
            "Le ticket Z est-il bien sorti ?\nOui = la caisse est remise a zero.",
            "Oui, effacer", lambda: self._effacer_z(numero), libelle_non="Non", couleur_oui=ROUGE)

    def _effacer_z(self, numero):
        with sync._verrou:  # pas de synchro Google pendant l'effacement
            ticket_z.effacer(self.conn, numero)
        dialogues.Message(self, "Z n. {} termine".format(numero),
                          "La caisse est remise a zero.\nLe prochain vendeur fera une prise de poste.",
                          callback_ok=self.destroy)

    def _saisir_url_sync(self):
        FormulaireTexte(self, titre="Adresse du script Google", label="Collez l'adresse (https://script.google.com/...) :",
                        valeur_initiale=sync.url(self.conn), autoriser_vide=True,
                        callback=lambda v: (sync.definir_url(self.conn, v), self._charger_sync()))

    # ------------------------------------------------------------------
    # Coffre : depots enregistres par les vendeurs / releve par l'admin
    # ------------------------------------------------------------------
    def _charger_coffre(self):
        for widget in self.frame_coffre.winfo_children():
            widget.destroy()
        attendu, nb, _ = caisse.coffre_attendu(self.conn)
        ligne = tk.Frame(self.frame_coffre, bg=CREME)
        ligne.pack(anchor="w", fill="x", pady=4)
        tk.Label(ligne, text="Depots enregistres depuis le dernier releve : {:g} DH ({} depots)".format(attendu, nb),
                 font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_800).pack(side="left")
        self._petit_bouton(ligne, "Relever le coffre", self._relever_coffre, VERT).pack(side="left", padx=(10, 0))
        tk.Label(self.frame_coffre,
                 text="Quand vous videz le coffre, comptez tout et tapez le total : le logiciel le compare aux depots.",
                 font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500, anchor="w").pack(anchor="w")
        for r in caisse.derniers_releves_coffre(self.conn):
            couleur = VERT if comptage.dans_tolerance(self.conn, r["ecart"]) else ROUGE
            tk.Label(self.frame_coffre,
                     text="{} {} : trouve {:g} DH, attendu {:g} DH, ecart {:+g} DH".format(
                         r["date"], r["heure"][:5], r["montant_compte"], r["attendu"], r["ecart"]),
                     font=POLICE_TICKET_DETAIL, bg=CREME, fg=couleur, anchor="w").pack(anchor="w")

    def _relever_coffre(self):
        def enregistrer(montant):
            attendu, ecart = caisse.enregistrer_releve_coffre(self.conn, montant)
            self._charger_coffre()
            dialogues.Message(self, "Releve du coffre",
                              "Trouve : {:g} DH\nAttendu (depots) : {:g} DH\nEcart : {:+g} DH".format(
                                  montant, attendu, ecart),
                              niveau="info" if comptage.dans_tolerance(self.conn, ecart) else "erreur")
        PaveNumerique(self, titre="Total trouve dans le coffre (DH)", callback_validation=enregistrer,
                      chiffres_max=8, permettre_decimales=True, autoriser_zero=True)

    # ------------------------------------------------------------------
    # Comptage : etalonnage (poids de 20 pieces), peser/compter, tolerance
    # ------------------------------------------------------------------
    def _charger_reglages_comptage(self):
        for widget in self.frame_comptage.winfo_children():
            widget.destroy()
        tk.Label(self.frame_comptage,
                 text="Pesez 20 pieces de chaque valeur (melangez anciennes et recentes) et tapez le poids.",
                 font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500, anchor="w").pack(anchor="w", pady=(0, 4))
        for valeur in comptage.PIECES:
            unitaire = comptage.poids_unitaire(self.conn, valeur)
            methode = comptage.methode_piece(self.conn, valeur)
            ligne = tk.Frame(self.frame_comptage, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
            ligne.pack(anchor="w", fill="x", pady=3)
            tk.Label(ligne, text=comptage.libelle(valeur, "piece"), font=POLICE_PRODUIT_NOM, bg=BLANC,
                     fg=BRUN_800, width=19, anchor="w").pack(side="left", padx=10, pady=6)
            if unitaire:
                texte = "{:g} g / piece".format(unitaire)
                if not comptage.poids_etalonne(self.conn, valeur):
                    texte += " (def.)"
                couleur = BRUN_800
            else:
                texte = "non etalonne"
                couleur = ROUGE
            tk.Label(ligne, text=texte, font=POLICE_PRODUIT_NOM, bg=BLANC, fg=couleur,
                     width=15, anchor="w").pack(side="left")
            tk.Label(ligne, text="pesee" if methode == comptage.METHODE_PESEE else "comptee",
                     font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500).pack(side="left", padx=6)
            autre = comptage.METHODE_COMPTAGE if methode == comptage.METHODE_PESEE else comptage.METHODE_PESEE
            texte_bascule = "Compter a la place" if autre == comptage.METHODE_COMPTAGE else "Peser a la place"
            self._petit_bouton(ligne, texte_bascule,
                               lambda v=valeur, m=autre: (comptage.definir_methode_piece(self.conn, v, m),
                                                          self._charger_reglages_comptage()),
                               BRUN_500).pack(side="right", padx=(4, 8), pady=4)
            self._petit_bouton(ligne, "Etalonner", lambda v=valeur: self._etalonner(v),
                               OR).pack(side="right", padx=4, pady=4)

        ligne = tk.Frame(self.frame_comptage, bg=CREME)
        ligne.pack(anchor="w", fill="x", pady=(10, 0))
        tk.Label(ligne, text="Tolerance d'ecart : +/- {:g} DH".format(comptage.tolerance(self.conn)),
                 font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_800).pack(side="left")
        self._petit_bouton(ligne, "Modifier", self._modifier_tolerance, OR).pack(side="left", padx=(10, 0))

    def _etalonner(self, valeur):
        PaveNumerique(
            self, titre="Poids de 20 {} (g)".format(comptage.libelle(valeur, "piece").lower()),
            callback_validation=lambda poids: (comptage.etalonner(self.conn, valeur, poids),
                                               self._charger_reglages_comptage()),
            chiffres_max=7, permettre_decimales=True,
        )

    def _modifier_tolerance(self):
        PaveNumerique(
            self, titre="Tolerance d'ecart (DH)",
            callback_validation=lambda v: (comptage.definir_tolerance(self.conn, v),
                                           self._charger_reglages_comptage()),
            chiffres_max=5, permettre_decimales=True, autoriser_zero=True,
        )

    # ------------------------------------------------------------------
    # Vendeurs (PIN a 4 chiffres) + code admin
    # ------------------------------------------------------------------
    def _petit_bouton(self, parent, texte, commande, couleur):
        return BoutonArrondi(
            parent, lignes=[(texte, POLICE_BOUTON_ROND, BLANC)], commande=commande,
            largeur=largeur_texte(texte, POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=couleur, couleur_bordure=couleur, bg=CREME,
        )

    def _charger_vendeurs(self):
        for widget in self.frame_vendeurs.winfo_children():
            widget.destroy()

        liste = vendeurs.lister(self.conn)
        if not liste:
            tk.Label(self.frame_vendeurs, text="Aucun vendeur pour l'instant.",
                     font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500).pack(anchor="w", pady=(0, 6))
        for v in liste:
            ligne = tk.Frame(self.frame_vendeurs, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
            ligne.pack(anchor="w", fill="x", pady=3)
            texte = v["nom"] if v["actif"] else "{} (desactive)".format(v["nom"])
            tk.Label(ligne, text=texte, font=POLICE_PRODUIT_NOM, bg=BLANC,
                     fg=BRUN_800 if v["actif"] else BRUN_500, anchor="w").pack(side="left", padx=10, pady=6)
            if v["actif"]:
                self._petit_bouton(ligne, "Desactiver", lambda vid=v["id"]: self._basculer_vendeur(vid, False),
                                   ROUGE).pack(side="right", padx=(4, 8), pady=4)
                self._petit_bouton(ligne, "Changer le code", lambda vid=v["id"]: self._saisir_pin_vendeur(vid),
                                   OR).pack(side="right", padx=4, pady=4)
                self._petit_bouton(ligne, "Renommer", lambda vv=v: self._renommer_vendeur(vv),
                                   OR).pack(side="right", padx=4, pady=4)
                sans = bool(v["sans_comptage"])
                self._petit_bouton(ligne, "Doit compter" if sans else "Ne compte pas",
                                   lambda vid=v["id"], s=sans: (vendeurs.definir_sans_comptage(self.conn, vid, not s),
                                                                self._charger_vendeurs()),
                                   BRUN_500).pack(side="right", padx=4, pady=4)
                if sans:
                    tk.Label(ligne, text="(ne compte pas)", font=POLICE_TICKET_DETAIL, bg=BLANC,
                             fg=OR).pack(side="left", padx=(0, 6))
            else:
                self._petit_bouton(ligne, "Reactiver", lambda vid=v["id"]: self._basculer_vendeur(vid, True),
                                   VERT).pack(side="right", padx=(4, 8), pady=4)

        bas = tk.Frame(self.frame_vendeurs, bg=CREME)
        bas.pack(anchor="w", fill="x", pady=(8, 0))
        BoutonArrondi(
            bas, lignes=[("+ Ajouter un vendeur", POLICE_CATEGORIE, BLANC)], commande=self._ajouter_vendeur,
            largeur=largeur_texte("+ Ajouter un vendeur", POLICE_CATEGORIE) + PADDING_BOUTON,
            hauteur=52, rayon=12, couleur_fond=VERT, couleur_bordure=VERT, bg=CREME,
        ).pack(side="left")
        BoutonArrondi(
            bas, lignes=[("Changer le code admin", POLICE_CATEGORIE, BLANC)], commande=self._changer_pin_admin,
            largeur=largeur_texte("Changer le code admin", POLICE_CATEGORIE) + PADDING_BOUTON,
            hauteur=52, rayon=12, couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=CREME,
        ).pack(side="left", padx=(10, 0))
        tk.Label(
            self.frame_vendeurs,
            text="Un vendeur n'est jamais supprime (ses ventes restent a son nom) : on le desactive.",
            font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500, anchor="w",
        ).pack(anchor="w", pady=(6, 0))

    def _ajouter_vendeur(self):
        FormulaireTexte(self, titre="Nouveau vendeur", label="Prenom du vendeur :",
                        callback=lambda nom: self._saisir_pin_vendeur(None, nom_nouveau=nom))

    def _saisir_pin_vendeur(self, vendeur_id, nom_nouveau=None):
        titre = "Code de {}".format(nom_nouveau) if nom_nouveau else "Nouveau code (4 chiffres)"
        PaveNumerique(
            self, titre=titre, masquer=False, chiffres_max=4, longueur_exacte=4, renvoyer_texte=True,
            callback_validation=lambda pin: self._enregistrer_pin_vendeur(vendeur_id, pin, nom_nouveau),
        )

    def _enregistrer_pin_vendeur(self, vendeur_id, pin, nom_nouveau):
        erreur = vendeurs.verifier_pin_disponible(self.conn, pin, vendeur_id_exclu=vendeur_id)
        if erreur:
            dialogues.Message(self, "Code refuse", erreur, niveau="erreur")
            return
        if vendeur_id is None:
            vendeurs.ajouter(self.conn, nom_nouveau, pin)
        else:
            vendeurs.modifier_pin(self.conn, vendeur_id, pin)
        self._charger_vendeurs()

    def _renommer_vendeur(self, vendeur):
        FormulaireTexte(self, titre="Renommer", label="Prenom du vendeur :", valeur_initiale=vendeur["nom"],
                        callback=lambda nom: (vendeurs.modifier_nom(self.conn, vendeur["id"], nom),
                                              self._charger_vendeurs()))

    def _basculer_vendeur(self, vendeur_id, actif):
        if actif:
            v = self.conn.execute("SELECT pin FROM vendeurs WHERE id = ?", (vendeur_id,)).fetchone()
            erreur = vendeurs.verifier_pin_disponible(self.conn, v["pin"], vendeur_id_exclu=vendeur_id)
            if erreur:
                dialogues.Message(self, "Reactivation impossible",
                                  erreur + "\nChangez d'abord le code de l'autre vendeur.", niveau="erreur")
                return
        vendeurs.definir_actif(self.conn, vendeur_id, actif)
        self._charger_vendeurs()

    def _changer_pin_admin(self):
        PaveNumerique(
            self, titre="Nouveau code admin", masquer=True, chiffres_max=4, longueur_exacte=4,
            renvoyer_texte=True, callback_validation=self._confirmer_pin_admin,
        )

    def _confirmer_pin_admin(self, pin):
        erreur = vendeurs.pin_admin_disponible(self.conn, pin)
        if erreur:
            dialogues.Message(self, "Code refuse", erreur, niveau="erreur")
            return
        PaveNumerique(
            self, titre="Retapez le nouveau code admin", masquer=True, chiffres_max=4, longueur_exacte=4,
            renvoyer_texte=True, callback_validation=lambda pin2: self._enregistrer_pin_admin(pin, pin2),
        )

    def _enregistrer_pin_admin(self, pin, pin2):
        if pin != pin2:
            dialogues.Message(self, "Codes differents", "Les deux codes ne sont pas identiques.",
                              niveau="erreur")
            return
        vendeurs.definir_pin_admin(self.conn, pin)
        dialogues.Message(self, "Code admin change", "Le nouveau code admin est enregistre.\n"
                          "Notez-le : il n'y a pas de code de secours.")

    # ------------------------------------------------------------------
    # Tiroir-caisse (active/desactive + test d'ouverture)
    # ------------------------------------------------------------------
    def _charger_reglages_tiroir(self):
        for widget in self.frame_tiroir.winfo_children():
            widget.destroy()
        actif = tiroir.tiroir_actif(self.conn)
        ligne = tk.Frame(self.frame_tiroir, bg=CREME)
        ligne.pack(anchor="w", fill="x", pady=4)
        tk.Label(
            ligne, text="Ouverture automatique : {}".format("ACTIVEE" if actif else "DESACTIVEE"),
            font=POLICE_PRODUIT_NOM, bg=CREME, fg=VERT if actif else ROUGE, anchor="w",
        ).pack(side="left")
        texte_bascule = "Desactiver" if actif else "Activer"
        BoutonArrondi(
            ligne, lignes=[(texte_bascule, POLICE_BOUTON_ROND, BLANC)],
            commande=lambda: self._basculer_tiroir(not actif),
            largeur=largeur_texte(texte_bascule, POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=OR, couleur_bordure=OR, bg=CREME,
        ).pack(side="left", padx=(10, 0))
        BoutonArrondi(
            ligne, lignes=[("Tester l'ouverture", POLICE_BOUTON_ROND, BLANC)],
            commande=self._tester_tiroir,
            largeur=largeur_texte("Tester l'ouverture", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=CREME,
        ).pack(side="left", padx=(10, 0))
        tk.Label(
            self.frame_tiroir,
            text="Le tiroir s'ouvre apres chaque vente en especes. Toutes les ouvertures "
                 "sont enregistrees (voir Historique).",
            font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500, anchor="w", justify="left", wraplength=640,
        ).pack(anchor="w")

    def _basculer_tiroir(self, actif):
        tiroir.definir_tiroir_actif(self.conn, actif)
        self._charger_reglages_tiroir()

    def _tester_tiroir(self):
        if not tiroir.tiroir_actif(self.conn):
            dialogues.Message(self, "Tiroir desactive", "Activez d'abord l'ouverture du tiroir.",
                              niveau="attention")
            return
        ok, erreur = tiroir.ouvrir(self.conn, tiroir.TYPE_TEST, motif="Test admin")
        if ok:
            dialogues.Message(self, "Test envoye", "Commande d'ouverture envoyee a l'imprimante.\n"
                              "Si le tiroir ne s'ouvre pas, verifiez son branchement (prise RJ11).")
        else:
            dialogues.Message(self, "Echec", "Impossible de joindre l'imprimante :\n{}".format(erreur),
                              niveau="erreur")

    # ------------------------------------------------------------------
    # TVA
    # ------------------------------------------------------------------
    def _charger_taux_tva(self):
        for widget in self.frame_tva.winfo_children():
            widget.destroy()

        taux = database.obtenir_taux_tva(self.conn)
        for cle_config, libelle, valeur in (
            ("tva_sur_place", "Sur place", taux["sur_place"]),
            ("tva_a_emporter", "A emporter", taux["a_emporter"]),
        ):
            ligne = tk.Frame(self.frame_tva, bg=CREME)
            ligne.pack(anchor="w", fill="x", pady=4)
            tk.Label(
                ligne, text="{} : {:g}%".format(libelle, valeur),
                font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_800, width=18, anchor="w",
            ).pack(side="left")
            BoutonArrondi(
                ligne, lignes=[("Modifier", POLICE_BOUTON_ROND, BLANC)],
                commande=lambda cle=cle_config: self._ouvrir_modifier_taux_tva(cle),
                largeur=largeur_texte("Modifier", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
                hauteur=40, rayon=10, couleur_fond=OR, couleur_bordure=OR, bg=CREME,
            ).pack(side="left", padx=(10, 0))

    def _ouvrir_modifier_taux_tva(self, cle_config):
        PaveNumerique(
            self, titre="Nouveau taux de TVA (%)",
            callback_validation=lambda valeur: self._definir_taux_tva(cle_config, valeur),
            chiffres_max=2,
        )

    def _definir_taux_tva(self, cle_config, valeur):
        database.definir_taux_tva(self.conn, cle_config, valeur)
        self._charger_taux_tva()

    # ------------------------------------------------------------------
    # Impression (nom de l'imprimante Windows + logo optionnel du ticket)
    # ------------------------------------------------------------------
    def _charger_reglages_impression(self):
        for widget in self.frame_impression.winfo_children():
            widget.destroy()

        nom_imprimante = database.obtenir_nom_imprimante(self.conn)
        chemin_logo = database.obtenir_chemin_logo(self.conn)

        for libelle, valeur, commande in (
            ("Imprimante", nom_imprimante, self._ouvrir_modifier_imprimante),
            ("Logo (chemin image)", chemin_logo if chemin_logo else "(aucun)", self._ouvrir_modifier_logo),
        ):
            ligne = tk.Frame(self.frame_impression, bg=CREME)
            ligne.pack(anchor="w", fill="x", pady=4)
            tk.Label(
                ligne, text="{} : {}".format(libelle, valeur),
                font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_800, anchor="w",
            ).pack(side="left")
            BoutonArrondi(
                ligne, lignes=[("Modifier", POLICE_BOUTON_ROND, BLANC)],
                commande=commande,
                largeur=largeur_texte("Modifier", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
                hauteur=40, rayon=10, couleur_fond=OR, couleur_bordure=OR, bg=CREME,
            ).pack(side="left", padx=(10, 0))

    def _ouvrir_modifier_imprimante(self):
        FormulaireTexte(
            self, titre="Nom de l'imprimante (tel que reconnu par Windows)",
            label="Nom exact de l'imprimante :",
            valeur_initiale=database.obtenir_nom_imprimante(self.conn),
            callback=self._definir_imprimante,
        )

    def _definir_imprimante(self, nom):
        database.definir_nom_imprimante(self.conn, nom)
        self._charger_reglages_impression()

    def _ouvrir_modifier_logo(self):
        FormulaireTexte(
            self, titre="Chemin de l'image du logo (laisser vide pour aucun logo)",
            label="Chemin complet du fichier (PNG/JPEG) :",
            valeur_initiale=database.obtenir_chemin_logo(self.conn),
            callback=self._definir_logo, autoriser_vide=True,
        )

    def _definir_logo(self, chemin):
        database.definir_chemin_logo(self.conn, chemin)
        self._charger_reglages_impression()

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------
    def _charger_categories(self):
        for widget in self.frame_categories.winfo_children():
            widget.destroy()

        categories = self.conn.execute("SELECT * FROM categories ORDER BY ordre, id").fetchall()

        self.pastilles_categories = []  # liste ordonnee de {id, widget, x, y, largeur}
        for cat in categories:
            actif = cat["id"] == self.categorie_selectionnee_id
            largeur = largeur_texte(cat["nom"], POLICE_CATEGORIE) + 44
            pastille = PastilleCategorie(
                self.frame_categories, cat["id"], cat["nom"], actif, largeur, HAUTEUR_PASTILLE_ADMIN,
                on_tap=self._selectionner_categorie, bg=CREME,
            )
            self.pastilles_categories.append({"id": cat["id"], "widget": pastille, "x": 0, "y": 0, "largeur": largeur})

        largeur_ajout = largeur_texte("+ Nouvelle categorie", POLICE_CATEGORIE) + PADDING_BOUTON
        self.bouton_ajout_categorie = BoutonArrondi(
            self.frame_categories, lignes=[("+ Nouvelle categorie", POLICE_CATEGORIE, BLANC)],
            commande=self._ouvrir_ajout_categorie, largeur=largeur_ajout, hauteur=HAUTEUR_PASTILLE_ADMIN,
            rayon=HAUTEUR_PASTILLE_ADMIN // 2, couleur_fond=VERT, couleur_bordure=VERT, bg=CREME,
        )
        self._largeur_bouton_ajout = largeur_ajout
        self._replacer_pastilles()

        if self.categorie_selectionnee_id is None and categories:
            self.categorie_selectionnee_id = categories[0]["id"]
        self._charger_produits()
        self._construire_actions_categorie()

    def _replacer_pastilles(self):
        if not hasattr(self, "pastilles_categories"):
            return
        largeur_dispo = self.frame_categories.winfo_width()
        if largeur_dispo <= 1:
            return

        x, y = 0, 0
        for info in self.pastilles_categories:
            if x > 0 and x + info["largeur"] > largeur_dispo:
                x, y = 0, y + HAUTEUR_PASTILLE_ADMIN + ESPACE_PASTILLE_ADMIN
            info["x"], info["y"] = x, y
            info["widget"].place(x=x, y=y, width=info["largeur"], height=HAUTEUR_PASTILLE_ADMIN)
            x += info["largeur"] + ESPACE_PASTILLE_ADMIN

        if hasattr(self, "bouton_ajout_categorie"):
            if x > 0 and x + self._largeur_bouton_ajout > largeur_dispo:
                x, y = 0, y + HAUTEUR_PASTILLE_ADMIN + ESPACE_PASTILLE_ADMIN
            self.bouton_ajout_categorie.place(x=x, y=y, width=self._largeur_bouton_ajout, height=HAUTEUR_PASTILLE_ADMIN)

        self.frame_categories.configure(height=y + HAUTEUR_PASTILLE_ADMIN)

    def _deplacer_categorie(self, direction):
        """direction : -1 pour deplacer la categorie selectionnee un cran
        plus tot, +1 pour un cran plus tard. Remplace l'ancien glisser-deposer
        (instable sur l'ecran tactile du magasin) par un simple tap, fiable
        quel que soit l'appareil."""
        if self.categorie_selectionnee_id is None:
            return
        ids_ordonnes = [info["id"] for info in self.pastilles_categories]
        i = ids_ordonnes.index(self.categorie_selectionnee_id)
        j = i + direction
        if j < 0 or j >= len(ids_ordonnes):
            return  # deja au bout, rien a faire
        ids_ordonnes[i], ids_ordonnes[j] = ids_ordonnes[j], ids_ordonnes[i]
        database.definir_ordre_categories(self.conn, ids_ordonnes)
        self._charger_categories()

    def _selectionner_categorie(self, categorie_id):
        self.categorie_selectionnee_id = categorie_id
        self._charger_categories()

    def _ouvrir_ajout_categorie(self):
        FormulaireTexte(self, titre="Nouvelle categorie", label="Nom de la categorie :",
                         callback=self._creer_categorie)

    def _creer_categorie(self, nom):
        database.ajouter_categorie(self.conn, nom)
        self._charger_categories()

    def _construire_actions_categorie(self):
        for widget in self.frame_categorie_actions.winfo_children():
            widget.destroy()

        categorie = None
        if self.categorie_selectionnee_id is not None:
            categorie = self.conn.execute(
                "SELECT * FROM categories WHERE id = ?", (self.categorie_selectionnee_id,)
            ).fetchone()

        if categorie is None:
            tk.Label(self.frame_categorie_actions, text="Aucune categorie selectionnee",
                     font=POLICE_TICKET_DETAIL, bg=CREME, fg=BRUN_500).pack(anchor="w")
            return

        # libelle sur sa propre ligne : avec les 4 boutons a cote, la ligne
        # depassait la largeur de la fenetre et le dernier bouton etait ecrase
        tk.Label(self.frame_categorie_actions, text="Categorie selectionnee : {}".format(categorie["nom"]),
                  font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_700, anchor="w").pack(side="top", fill="x", pady=(0, 6))
        boutons_categorie = tk.Frame(self.frame_categorie_actions, bg=CREME)
        boutons_categorie.pack(side="top", anchor="w")
        BoutonArrondi(
            boutons_categorie, lignes=[("< Deplacer", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda: self._deplacer_categorie(-1),
            largeur=largeur_texte("< Deplacer", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=CREME,
        ).pack(side="left", padx=(0, 4))
        BoutonArrondi(
            boutons_categorie, lignes=[("Deplacer >", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda: self._deplacer_categorie(1),
            largeur=largeur_texte("Deplacer >", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=CREME,
        ).pack(side="left", padx=(0, 14))
        BoutonArrondi(
            boutons_categorie, lignes=[("Modifier", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda c=categorie: self._ouvrir_modifier_categorie(c),
            largeur=largeur_texte("Modifier", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=OR, couleur_bordure=OR, bg=CREME,
        ).pack(side="left", padx=(0, 8))
        BoutonArrondi(
            boutons_categorie, lignes=[("Supprimer la categorie", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda c=categorie: self._supprimer_categorie(c),
            largeur=largeur_texte("Supprimer la categorie", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=CREME,
        ).pack(side="left")

    def _ouvrir_modifier_categorie(self, categorie):
        FormulaireTexte(
            self, titre="Modifier la categorie", label="Nom de la categorie :",
            valeur_initiale=categorie["nom"],
            callback=lambda nom: self._modifier_categorie(categorie["id"], nom),
        )

    def _modifier_categorie(self, categorie_id, nom):
        database.modifier_categorie(self.conn, categorie_id, nom)
        self._charger_categories()

    def _supprimer_categorie(self, categorie):
        if not messagebox.askyesno(
            "Confirmer la suppression",
            "Supprimer la categorie '{}' ?\nTous ses produits et parfums seront supprimes aussi.".format(
                categorie["nom"]),
        ):
            return
        database.supprimer_categorie(self.conn, categorie["id"])
        self.categorie_selectionnee_id = None
        self._charger_categories()

    # ------------------------------------------------------------------
    # Produits
    # ------------------------------------------------------------------
    def _charger_produits(self):
        for widget in self.frame_produits.winfo_children():
            widget.destroy()

        if self.categorie_selectionnee_id is None:
            return

        # Toujours en haut de la liste (pas apres tous les produits) : sinon
        # il finit par descendre hors de vue au fur et a mesure que la
        # categorie se remplit, obligeant a scroller pour le retrouver.
        BoutonArrondi(
            self.frame_produits, lignes=[("+ Ajouter un produit", POLICE_CATEGORIE, BLANC)],
            commande=self._ouvrir_ajout_produit,
            largeur=largeur_texte("+ Ajouter un produit", POLICE_CATEGORIE) + PADDING_BOUTON,
            hauteur=50, rayon=12,
            couleur_fond=VERT, couleur_bordure=VERT, bg=CREME,
        ).pack(anchor="w", pady=(0, 10))

        produits = self.conn.execute(
            "SELECT * FROM produits WHERE categorie_id = ? ORDER BY nom COLLATE NOCASE",
            (self.categorie_selectionnee_id,),
        ).fetchall()
        for produit in produits:
            self._construire_ligne_produit(produit)

    def _construire_ligne_produit(self, produit):
        cadre = tk.Frame(self.frame_produits, bg=BLANC, highlightbackground=BRUN_200, highlightthickness=1)
        cadre.pack(fill="x", pady=4)

        ligne_haut = tk.Frame(cadre, bg=BLANC)
        ligne_haut.pack(fill="x", padx=10, pady=8)

        if produit["a_des_sous_produits"]:
            texte = "{} (sous-menu)".format(produit["nom"])
        else:
            texte = "{} - {:g} DH".format(produit["nom"], produit["prix"])
        if produit["tva_fixe"] == 0:
            texte += "  [TVA 0%]"
        tk.Label(ligne_haut, text=texte, font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_800).pack(side="left")

        BoutonArrondi(
            ligne_haut, lignes=[("Supprimer", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda p=produit: self._supprimer_produit(p),
            largeur=largeur_texte("Supprimer", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BLANC,
        ).pack(side="right", padx=(6, 0))
        BoutonArrondi(
            ligne_haut, lignes=[("Modifier", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda p=produit: self._ouvrir_modifier_produit(p),
            largeur=largeur_texte("Modifier", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=OR, couleur_bordure=OR, bg=BLANC,
        ).pack(side="right", padx=(6, 0))

        if produit["a_des_sous_produits"]:
            sous_produits = self.conn.execute(
                "SELECT * FROM sous_produits WHERE produit_id = ? ORDER BY id", (produit["id"],),
            ).fetchall()
            cadre_sp = tk.Frame(cadre, bg=BLANC)
            cadre_sp.pack(fill="x", padx=26, pady=(0, 8))
            for sp in sous_produits:
                ligne_sp = tk.Frame(cadre_sp, bg=BLANC)
                ligne_sp.pack(fill="x", pady=2)
                tk.Label(ligne_sp, text="- {} : {:g} DH".format(sp["nom"], sp["prix"]),
                         font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500).pack(side="left")
                BoutonArrondi(
                    ligne_sp, lignes=[("Suppr.", POLICE_BOUTON_ROND, BLANC)],
                    commande=lambda s=sp: self._supprimer_sous_produit(s),
                    largeur=largeur_texte("Suppr.", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
                    hauteur=34, rayon=10, couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BLANC,
                ).pack(side="right", padx=(4, 0))
                BoutonArrondi(
                    ligne_sp, lignes=[("Modifier", POLICE_BOUTON_ROND, BLANC)],
                    commande=lambda s=sp: self._ouvrir_modifier_sous_produit(s),
                    largeur=largeur_texte("Modifier", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
                    hauteur=34, rayon=10, couleur_fond=OR, couleur_bordure=OR, bg=BLANC,
                ).pack(side="right", padx=(4, 0))

            BoutonArrondi(
                cadre_sp, lignes=[("+ Ajouter un parfum", POLICE_BOUTON_ROND, BLANC)],
                commande=lambda p=produit: self._ouvrir_ajout_sous_produit(p),
                largeur=200, hauteur=40, rayon=10, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
            ).pack(anchor="w", pady=(4, 0))

    def _ouvrir_ajout_produit(self):
        FormulaireProduit(self, titre="Nouveau produit", callback=self._creer_produit)

    def _creer_produit(self, nom, prix, a_des_sous_produits, tva_fixe, noms_parfums=None):
        if a_des_sous_produits:
            # tous les parfums saisis a la creation partagent le meme prix
            # (celui defini sur le produit parent) ; chacun reste modifiable
            # individuellement ensuite depuis la liste des produits
            parfums = [(nom_parfum, prix) for nom_parfum in (noms_parfums or [])]
            database.ajouter_produit_sous_menu(
                self.conn, nom, self.categorie_selectionnee_id, parfums, tva_fixe=tva_fixe
            )
        else:
            database.ajouter_produit_simple(
                self.conn, nom, prix, self.categorie_selectionnee_id, tva_fixe=tva_fixe
            )
        self._charger_produits()

    def _ouvrir_modifier_produit(self, produit):
        FormulaireProduit(
            self, titre="Modifier le produit", produit_existant=produit,
            callback=lambda nom, prix, a_sous, tva_fixe, noms_parfums=None: self._modifier_produit(
                produit["id"], nom, prix, tva_fixe
            ),
        )

    def _modifier_produit(self, produit_id, nom, prix, tva_fixe):
        database.modifier_produit(self.conn, produit_id, nom, prix, self.categorie_selectionnee_id, tva_fixe=tva_fixe)
        self._charger_produits()

    def _supprimer_produit(self, produit):
        if messagebox.askyesno("Confirmer la suppression", "Supprimer '{}' ?".format(produit["nom"])):
            database.supprimer_produit(self.conn, produit["id"])
            self._charger_produits()

    # ------------------------------------------------------------------
    # Sous-produits (parfums)
    # ------------------------------------------------------------------
    def _ouvrir_ajout_sous_produit(self, produit):
        FormulaireSousProduit(
            self, titre="Nouveau parfum - {}".format(produit["nom"]),
            callback=lambda nom, prix: self._creer_sous_produit(produit["id"], nom, prix),
        )

    def _creer_sous_produit(self, produit_id, nom, prix):
        database.ajouter_sous_produit(self.conn, produit_id, nom, prix)
        self._charger_produits()

    def _ouvrir_modifier_sous_produit(self, sous_produit):
        FormulaireSousProduit(
            self, titre="Modifier le parfum", sous_produit_existant=sous_produit,
            callback=lambda nom, prix: self._modifier_sous_produit(sous_produit["id"], nom, prix),
        )

    def _modifier_sous_produit(self, sous_produit_id, nom, prix):
        database.modifier_sous_produit(self.conn, sous_produit_id, nom, prix)
        self._charger_produits()

    def _supprimer_sous_produit(self, sous_produit):
        if messagebox.askyesno("Confirmer la suppression", "Supprimer '{}' ?".format(sous_produit["nom"])):
            database.supprimer_sous_produit(self.conn, sous_produit["id"])
            self._charger_produits()

    # ------------------------------------------------------------------
    # Export / Import JSON
    # ------------------------------------------------------------------
    def _exporter(self):
        catalogue = database.exporter_catalogue(self.conn)
        texte_json = json.dumps(catalogue, ensure_ascii=False, indent=2)
        FenetreTexteJSON(self, titre="Exporter les produits (JSON copiable)", texte_initial=texte_json)

    def _importer(self):
        def sur_confirmation(texte_json):
            try:
                catalogue = json.loads(texte_json)
            except ValueError:
                messagebox.showerror("JSON invalide", "Le texte colle n'est pas un JSON valide.")
                return
            if not messagebox.askyesno(
                "Confirmer l'import",
                "Cela va REMPLACER tout le catalogue actuel (categories, produits, parfums).\n"
                "L'historique des ventes n'est pas touche.\n\nContinuer ?",
            ):
                return
            database.importer_catalogue(self.conn, catalogue)
            self.categorie_selectionnee_id = None
            self._charger_categories()
            messagebox.showinfo("Import reussi", "Le catalogue a ete remplace.")

        FenetreTexteJSON(
            self, titre="Importer les produits (coller le JSON)", texte_initial="",
            lecture_seule=False, callback_validation=sur_confirmation,
        )


class FormulaireTexte(tk.Toplevel):
    """Petite boite de dialogue texte libre (nom de categorie, etc.)."""

    def __init__(self, parent, titre, label, callback, valeur_initiale="", autoriser_vide=False):
        super().__init__(parent)
        self.callback = callback
        self.autoriser_vide = autoriser_vide
        self.title(titre)
        self.configure(bg=BLANC)
        self.resizable(False, False)
        self.transient(parent)

        largeur, hauteur = 380, 210
        x = parent.winfo_rootx() + max((parent.winfo_width() - largeur) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))

        tk.Label(self, text=titre, font=POLICE_SOUS_TITRE, bg=BLANC, fg=BRUN_700, pady=12).pack(fill="x")
        tk.Label(self, text=label, font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500).pack(anchor="w", padx=20)
        self.entree = tk.Entry(self, font=("Segoe UI", 13), justify="center")
        self.entree.insert(0, valeur_initiale)
        self.entree.pack(fill="x", padx=20, pady=10)
        self.entree.focus_set()

        cadre_boutons = tk.Frame(self, bg=BLANC)
        cadre_boutons.pack(fill="x", padx=20, pady=14)
        BoutonArrondi(
            cadre_boutons, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=180, hauteur=50, rayon=12, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(side="left")
        BoutonArrondi(
            cadre_boutons, lignes=[("Valider", POLICE_CATEGORIE, BLANC)], commande=self._valider,
            largeur=180, hauteur=50, rayon=12, couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
        ).pack(side="right")

        self.grab_set()

    def _valider(self):
        valeur = self.entree.get().strip()
        if not valeur and not self.autoriser_vide:
            messagebox.showwarning("Champ vide", "Merci de saisir un nom.")
            return
        self.destroy()
        self.callback(valeur)


class FormulaireProduit(tk.Toplevel):
    """Ajout ou modification d'un produit (nom + prix, ou nom seul si
    'a des sous-produits'). Le type (simple / sous-menu) n'est modifiable
    qu'a la creation, pas lors d'une modification."""

    LARGEUR = 440
    HAUTEUR_SIMPLE = 430
    HAUTEUR_AVEC_PARFUMS = 560

    def __init__(self, parent, titre, callback, produit_existant=None):
        super().__init__(parent)
        self.callback = callback
        self.produit_existant = produit_existant
        self.prix_valeur = None
        if produit_existant is not None and not produit_existant["a_des_sous_produits"]:
            self.prix_valeur = produit_existant["prix"]
        self.entrees_parfums = []  # widgets Entry des parfums ajoutes a la creation

        self.title(titre)
        self.configure(bg=BLANC)
        self.resizable(False, False)
        self.transient(parent)

        # Colle en haut de la zone de travail (hors barre des taches), pas
        # centre : sur un petit ecran, une fois la zone parfums depliee (plus
        # haute), un dialogue centre poussait ses boutons Valider/Annuler
        # tout en bas, pres de la barre des taches. En haut, on garde le
        # maximum de marge en dessous quelle que soit la hauteur ecran.
        _, y_zone, _, hauteur_zone = zone_travail_windows()
        if hauteur_zone <= 0:
            y_zone, hauteur_zone = 0, parent.winfo_screenheight()
        self._x = parent.winfo_rootx() + max((parent.winfo_width() - self.LARGEUR) // 2, 0)
        y_max = y_zone + hauteur_zone - self.HAUTEUR_AVEC_PARFUMS - 10
        self._y = max(y_zone + 10, min(y_zone + 20, y_max))
        self.geometry("{}x{}+{}+{}".format(self.LARGEUR, self.HAUTEUR_SIMPLE, self._x, self._y))

        tk.Label(self, text=titre, font=POLICE_SOUS_TITRE, bg=BLANC, fg=BRUN_700, pady=12).pack(fill="x")

        tk.Label(self, text="Nom du produit :", font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500).pack(anchor="w", padx=20)
        self.entree_nom = tk.Entry(self, font=("Segoe UI", 13), justify="center")
        self.entree_nom.insert(0, produit_existant["nom"] if produit_existant else "")
        self.entree_nom.pack(fill="x", padx=20, pady=(0, 10))
        self.entree_nom.focus_set()

        self.var_sous_produits = tk.BooleanVar(
            value=bool(produit_existant["a_des_sous_produits"]) if produit_existant else False
        )
        case = tk.Checkbutton(
            self, text="A des variantes / parfums", variable=self.var_sous_produits,
            bg=BLANC, fg=BRUN_700, font=POLICE_TICKET_DETAIL,
            wraplength=self.LARGEUR - 40, anchor="w", justify="left",
            command=self._sur_toggle_sous_produits,
        )
        case.pack(anchor="w", padx=20, pady=(0, 2), fill="x")
        if produit_existant is not None:
            case.configure(state="disabled")  # type non modifiable a l'edition
            tk.Label(
                self, text="(fixe a la creation du produit, non modifiable ici)",
                font=("Segoe UI", 9, "italic"), bg=BLANC, fg=BRUN_500,
            ).pack(anchor="w", padx=20, pady=(0, 8))
        else:
            tk.Label(
                self, text="Ex: 'Eclair' avec les variantes 'Chocolat', 'Cafe', 'Vanille'",
                font=("Segoe UI", 9, "italic"), bg=BLANC, fg=BRUN_500,
            ).pack(anchor="w", padx=20, pady=(0, 8))

        tva_fixe_existante = produit_existant["tva_fixe"] if produit_existant else None
        self.var_tva_0 = tk.BooleanVar(value=(tva_fixe_existante == 0))
        tk.Checkbutton(
            self, text="TVA 0% (produit exonere, ex: pain)",
            variable=self.var_tva_0, bg=BLANC, fg=BRUN_700, font=POLICE_TICKET_DETAIL,
        ).pack(anchor="w", padx=20, pady=(0, 10))

        self.label_prix = tk.Label(self, text="", font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_800,
                                    wraplength=self.LARGEUR - 40, justify="left")
        self.label_prix.pack(anchor="w", padx=20)
        self.bouton_prix = BoutonArrondi(
            self, lignes=[("Definir le prix", POLICE_CATEGORIE, BLANC)], commande=self._ouvrir_pave_prix,
            largeur=260, hauteur=50, rayon=12, couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=BLANC,
        )

        # Zone (uniquement a la creation) pour saisir directement les noms
        # des parfums/variantes, tous rattaches au meme prix defini ci-dessus.
        self.zone_parfums = tk.Frame(self, bg=BLANC)
        tk.Label(
            self.zone_parfums, text="Parfums / variantes :", font=POLICE_TICKET_DETAIL,
            bg=BLANC, fg=BRUN_500,
        ).pack(anchor="w", padx=20, pady=(6, 2))
        self.liste_parfums_scroll = ScrollableFrame(self.zone_parfums, bg=BLANC, height=90)
        self.liste_parfums_scroll.pack(fill="x", padx=20)
        self.liste_parfums_scroll.pack_propagate(False)
        BoutonArrondi(
            self.zone_parfums, lignes=[("+ Ajouter un parfum", POLICE_BOUTON_ROND, BLANC)],
            commande=self._ajouter_ligne_parfum,
            largeur=largeur_texte("+ Ajouter un parfum", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=38, rayon=10, couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
        ).pack(anchor="w", padx=20, pady=(6, 0))

        self._sur_toggle_sous_produits()

        cadre_boutons = tk.Frame(self, bg=BLANC)
        cadre_boutons.pack(side="bottom", fill="x", padx=20, pady=14)
        BoutonArrondi(
            cadre_boutons, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=190, hauteur=52, rayon=12, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(side="left")
        BoutonArrondi(
            cadre_boutons, lignes=[("Valider", POLICE_CATEGORIE, BLANC)], commande=self._valider,
            largeur=190, hauteur=52, rayon=12, couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
        ).pack(side="right")

        self.grab_set()

    def _affiche_saisie_parfums(self):
        """La saisie groupee de parfums n'a de sens qu'a la creation : une
        fois le produit cree, chaque parfum se gere individuellement (prix
        propre possible) depuis la liste des produits du Mode Admin."""
        return self.var_sous_produits.get() and self.produit_existant is None

    def _sur_toggle_sous_produits(self):
        if self.var_sous_produits.get():
            if self._affiche_saisie_parfums():
                texte = "Prix des parfums : {:g} DH".format(self.prix_valeur) if self.prix_valeur is not None \
                    else "Prix des parfums : (a definir, identique pour tous)"
                self.label_prix.configure(text=texte)
                self.bouton_prix.definir_lignes([("Prix des parfums", POLICE_CATEGORIE, BLANC)])
                self.bouton_prix.pack(anchor="w", padx=20, pady=(4, 6))
                self.zone_parfums.pack(anchor="w", fill="x", pady=(0, 6))
            else:
                self.label_prix.configure(text="Prix : chaque parfum garde son propre prix "
                                                "(voir la liste des produits)")
                self.bouton_prix.pack_forget()
                self.zone_parfums.pack_forget()
        else:
            texte = "Prix : {:g} DH".format(self.prix_valeur) if self.prix_valeur is not None else "Prix : (a definir)"
            self.label_prix.configure(text=texte)
            self.bouton_prix.definir_lignes([("Definir le prix", POLICE_CATEGORIE, BLANC)])
            self.bouton_prix.pack(anchor="w", padx=20, pady=(4, 10))
            self.zone_parfums.pack_forget()

        hauteur = self.HAUTEUR_AVEC_PARFUMS if self._affiche_saisie_parfums() else self.HAUTEUR_SIMPLE
        self.geometry("{}x{}+{}+{}".format(self.LARGEUR, hauteur, self._x, self._y))

    def _ajouter_ligne_parfum(self):
        parent_liste = self.liste_parfums_scroll.interior
        ligne = tk.Frame(parent_liste, bg=BLANC)
        ligne.pack(fill="x", pady=3)
        entree = tk.Entry(ligne, font=("Segoe UI", 12))
        entree.pack(side="left", fill="x", expand=True)
        entree.focus_set()
        BoutonArrondi(
            ligne, lignes=[("X", POLICE_BOUTON_ROND, BLANC)], commande=lambda: self._retirer_ligne_parfum(ligne, entree),
            largeur=32, hauteur=32, rayon=8, couleur_fond=ROUGE, couleur_bordure=ROUGE, bg=BLANC,
        ).pack(side="right", padx=(6, 0))
        self.entrees_parfums.append(entree)

    def _retirer_ligne_parfum(self, ligne, entree):
        self.entrees_parfums.remove(entree)
        ligne.destroy()

    def _ouvrir_pave_prix(self):
        titre = "Prix des parfums (DH)" if self._affiche_saisie_parfums() else "Prix du produit (DH)"
        PaveNumerique(self, titre=titre, callback_validation=self._definir_prix,
                      chiffres_max=8, permettre_decimales=True)

    def _definir_prix(self, valeur):
        self.prix_valeur = valeur
        self._sur_toggle_sous_produits()

    def _valider(self):
        nom = self.entree_nom.get().strip()
        if not nom:
            messagebox.showwarning("Nom manquant", "Merci de saisir un nom de produit.")
            return
        a_sous = self.var_sous_produits.get()

        noms_parfums = []
        if self._affiche_saisie_parfums():
            noms_parfums = [e.get().strip() for e in self.entrees_parfums if e.get().strip()]
            if noms_parfums and self.prix_valeur is None:
                messagebox.showwarning("Prix manquant", "Merci de definir le prix des parfums.")
                return
        elif not a_sous and self.prix_valeur is None:
            messagebox.showwarning("Prix manquant", "Merci de definir un prix.")
            return

        tva_fixe = 0 if self.var_tva_0.get() else None
        self.destroy()
        self.callback(nom, self.prix_valeur, a_sous, tva_fixe, noms_parfums)


class FormulaireSousProduit(tk.Toplevel):
    """Ajout ou modification d'un parfum (sous-produit) : nom + prix."""

    def __init__(self, parent, titre, callback, sous_produit_existant=None):
        super().__init__(parent)
        self.callback = callback
        self.prix_valeur = sous_produit_existant["prix"] if sous_produit_existant else None

        self.title(titre)
        self.configure(bg=BLANC)
        self.resizable(False, False)
        self.transient(parent)

        largeur, hauteur = 380, 300
        x = parent.winfo_rootx() + max((parent.winfo_width() - largeur) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))

        tk.Label(self, text=titre, font=POLICE_SOUS_TITRE, bg=BLANC, fg=BRUN_700, pady=12,
                 wraplength=340).pack(fill="x")

        tk.Label(self, text="Nom du parfum :", font=POLICE_TICKET_DETAIL, bg=BLANC, fg=BRUN_500).pack(anchor="w", padx=20)
        self.entree_nom = tk.Entry(self, font=("Segoe UI", 13), justify="center")
        self.entree_nom.insert(0, sous_produit_existant["nom"] if sous_produit_existant else "")
        self.entree_nom.pack(fill="x", padx=20, pady=(0, 10))
        self.entree_nom.focus_set()

        self.label_prix = tk.Label(self, text="", font=POLICE_PRODUIT_NOM, bg=BLANC, fg=BRUN_800)
        self.label_prix.pack(anchor="w", padx=20)
        BoutonArrondi(
            self, lignes=[("Definir le prix", POLICE_CATEGORIE, BLANC)], commande=self._ouvrir_pave_prix,
            largeur=220, hauteur=50, rayon=12, couleur_fond=BRUN_700, couleur_bordure=BRUN_700, bg=BLANC,
        ).pack(anchor="w", padx=20, pady=(4, 10))
        self._rafraichir_label_prix()

        cadre_boutons = tk.Frame(self, bg=BLANC)
        cadre_boutons.pack(side="bottom", fill="x", padx=20, pady=14)
        BoutonArrondi(
            cadre_boutons, lignes=[("Annuler", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=180, hauteur=52, rayon=12, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(side="left")
        BoutonArrondi(
            cadre_boutons, lignes=[("Valider", POLICE_CATEGORIE, BLANC)], commande=self._valider,
            largeur=180, hauteur=52, rayon=12, couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
        ).pack(side="right")

        self.grab_set()

    def _rafraichir_label_prix(self):
        texte = "Prix : {:g} DH".format(self.prix_valeur) if self.prix_valeur is not None else "Prix : (a definir)"
        self.label_prix.configure(text=texte)

    def _ouvrir_pave_prix(self):
        PaveNumerique(self, titre="Prix du parfum (DH)", callback_validation=self._definir_prix,
                      chiffres_max=8, permettre_decimales=True)

    def _definir_prix(self, valeur):
        self.prix_valeur = valeur
        self._rafraichir_label_prix()

    def _valider(self):
        nom = self.entree_nom.get().strip()
        if not nom:
            messagebox.showwarning("Nom manquant", "Merci de saisir un nom de parfum.")
            return
        if self.prix_valeur is None:
            messagebox.showwarning("Prix manquant", "Merci de definir un prix.")
            return
        self.destroy()
        self.callback(nom, self.prix_valeur)


class FenetreTexteJSON(tk.Toplevel):
    """Zone de texte pour afficher (export, copiable) ou coller (import) le
    catalogue au format JSON."""

    def __init__(self, parent, titre, texte_initial="", lecture_seule=True, callback_validation=None):
        super().__init__(parent)
        self.callback_validation = callback_validation
        self.title(titre)
        self.configure(bg=BLANC)
        self.transient(parent)

        largeur, hauteur = 640, 560
        x = parent.winfo_rootx() + max((parent.winfo_width() - largeur) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - hauteur) // 2, 0)
        self.geometry("{}x{}+{}+{}".format(largeur, hauteur, x, y))

        tk.Label(self, text=titre, font=POLICE_SOUS_TITRE, bg=BLANC, fg=BRUN_700, pady=12).pack(fill="x")

        cadre_texte = tk.Frame(self, bg=BLANC)
        cadre_texte.pack(fill="both", expand=True, padx=16)
        barre_scroll = tk.Scrollbar(cadre_texte)
        barre_scroll.pack(side="right", fill="y")
        self.texte = tk.Text(cadre_texte, wrap="word", font=("Consolas", 10),
                              yscrollcommand=barre_scroll.set)
        self.texte.pack(side="left", fill="both", expand=True)
        barre_scroll.configure(command=self.texte.yview)
        self.texte.insert("1.0", texte_initial)
        if lecture_seule:
            self.texte.configure(state="disabled")

        cadre_boutons = tk.Frame(self, bg=BLANC)
        cadre_boutons.pack(fill="x", padx=16, pady=14)
        BoutonArrondi(
            cadre_boutons, lignes=[("Fermer", POLICE_CATEGORIE, BLANC)], commande=self.destroy,
            largeur=180, hauteur=52, rayon=12, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=BLANC,
        ).pack(side="left")

        if callback_validation is not None:
            BoutonArrondi(
                cadre_boutons, lignes=[("Confirmer l'import", POLICE_CATEGORIE, BLANC)],
                commande=self._confirmer,
                largeur=largeur_texte("Confirmer l'import", POLICE_CATEGORIE) + PADDING_BOUTON,
                hauteur=52, rayon=12,
                couleur_fond=VERT, couleur_bordure=VERT, bg=BLANC,
            ).pack(side="right")

        self.grab_set()

    def _confirmer(self):
        texte_json = self.texte.get("1.0", "end").strip()
        if not texte_json:
            messagebox.showwarning("Vide", "Colle d'abord le JSON exporte precedemment.")
            return
        self.callback_validation(texte_json)
