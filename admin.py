# -*- coding: utf-8 -*-
"""
Etape 4 : mode Admin (protege par PIN) - gestion des categories, produits,
sous-produits (parfums), et export/import du catalogue en JSON.
"""

import json
import tkinter as tk
from tkinter import messagebox

import database
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
        tk.Label(entete, text="Mode Admin", font=POLICE_TITRE, bg=BRUN_700, fg=BLANC,
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

        tk.Label(self.frame_categorie_actions, text="Categorie selectionnee : {}".format(categorie["nom"]),
                  font=POLICE_PRODUIT_NOM, bg=CREME, fg=BRUN_700).pack(side="left", padx=(0, 14))
        BoutonArrondi(
            self.frame_categorie_actions, lignes=[("< Deplacer", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda: self._deplacer_categorie(-1),
            largeur=largeur_texte("< Deplacer", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=CREME,
        ).pack(side="left", padx=(0, 4))
        BoutonArrondi(
            self.frame_categorie_actions, lignes=[("Deplacer >", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda: self._deplacer_categorie(1),
            largeur=largeur_texte("Deplacer >", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=BRUN_500, couleur_bordure=BRUN_500, bg=CREME,
        ).pack(side="left", padx=(0, 14))
        BoutonArrondi(
            self.frame_categorie_actions, lignes=[("Modifier", POLICE_BOUTON_ROND, BLANC)],
            commande=lambda c=categorie: self._ouvrir_modifier_categorie(c),
            largeur=largeur_texte("Modifier", POLICE_BOUTON_ROND) + PADDING_BOUTON_COMPACT,
            hauteur=40, rayon=10, couleur_fond=OR, couleur_bordure=OR, bg=CREME,
        ).pack(side="left", padx=(0, 8))
        BoutonArrondi(
            self.frame_categorie_actions, lignes=[("Supprimer la categorie", POLICE_BOUTON_ROND, BLANC)],
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
