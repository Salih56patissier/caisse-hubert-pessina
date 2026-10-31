# -*- coding: utf-8 -*-
"""
Palette, polices et composants graphiques partages par tous les ecrans
(caisse, pave numerique, futur admin/historique/PIN).

Design inspire d'une maquette HTML fournie par le client (palette bruns /
creme / or, formes arrondies).
"""

import ctypes
import tkinter as tk
from tkinter import font as tkfont

try:
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageTk
except ImportError:  # Pillow absent : les tuiles fonctionnent sans icone ni rendu lisse
    Image = ImageChops = ImageDraw = ImageFilter = ImageTk = None

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BRUN_900 = "#2b1b18"
BRUN_800 = "#3b2723"
BRUN_700 = "#5b433c"
BRUN_600 = "#6f564e"
BRUN_500 = "#8a7168"
BRUN_300 = "#b3a29b"
BRUN_200 = "#e3dad5"
BRUN_100 = "#f1ece9"
CREME = "#f7f4f1"
OR = "#d68a1f"
OR_CLAIR = "#eba94a"
VERT = "#2f9e57"
ROSE = "#e8467f"
ROUGE = "#df4b43"
BLANC = "#ffffff"

HEADER_DEGRADE_GAUCHE = "#e63e7c"
HEADER_DEGRADE_DROITE = "#b8155d"

# Ecran de caisse (cartes) : framboise = rose fonce de l'en-tete
FRAMBOISE = "#c4155e"
FRAMBOISE_FONCE = "#a30f4d"
ROSE_PALE = "#fde8f0"
ROSE_TRES_PALE = "#fef4f8"
VERT_CLAIR = "#43b66b"
VERT_FONCE = "#27874a"
BORDURE_CARTE = "#ebe4df"
FOND_SEGMENT = "#f1ebe7"
COULEUR_OMBRE = "#3b2723"

# Une couleur distincte par categorie (dans l'ordre), pour les reperer d'un
# coup d'oeil sur l'ecran de caisse plutot que devoir lire chaque etiquette.
# Cycle si plus de categories que de couleurs. Toutes assez saturees/foncees
# pour rester lisibles avec du texte blanc par-dessus.
COULEURS_CATEGORIES = [
    OR,        # or
    VERT,      # vert
    ROUGE,     # terracotta
    "#e75480", # rose
    BRUN_500,  # brun
    "#3d7ea6", # bleu ardoise
    "#8e5572", # prune
    "#3f8f7f", # sarcelle
    "#b8860b", # moutarde
]

# Hauteur de la bande du bas d'une tuile produit, quand elle a un prix/pied
# et/ou un badge de quantite ("123") - voir Carte._dessiner. Sert
# aussi cote appelant (main.py) pour savoir combien de place reste pour le
# nom du produit au-dessus.
HAUTEUR_PIED_TUILE = 46

# Georgia n'est gardee que pour le nom de la patisserie : ses chiffres sont
# "elzeviriens" (hauteur variable, le 0 ressemble a un o) - a eviter pour
# tout montant, d'ou Segoe UI partout ailleurs.
POLICE_TITRE = ("Georgia", 26, "bold")
POLICE_BADGE = ("Segoe UI", 10, "bold")
POLICE_TICKET_TITRE = ("Segoe UI", 16, "bold")
POLICE_CATEGORIE = ("Segoe UI", 17, "bold")
POLICE_CATEGORIE_CAISSE = ("Segoe UI", 22, "bold")  # pastilles de categories de l'ecran de caisse (compact mais tactile)
POLICE_PRODUIT_NOM = ("Segoe UI", 14, "bold")
POLICE_PRODUIT_PRIX = ("Segoe UI", 15, "bold")
POLICE_PRODUIT_HINT = ("Segoe UI", 11, "italic")
POLICE_SOUS_TITRE = ("Segoe UI", 16, "bold")
POLICE_TOTAL = ("Segoe UI", 24, "bold")
POLICE_TICKET_NOM = ("Segoe UI", 12, "bold")
POLICE_TICKET_DETAIL = ("Segoe UI", 11)
POLICE_BOUTON_ROND = ("Segoe UI", 13, "bold")
POLICE_ENCAISSER = ("Segoe UI", 18, "bold")
POLICE_BADGE_QTE = ("Segoe UI", 13, "bold")


def definir_dpi_awareness():
    """A appeler tout au debut du programme, avant de creer la fenetre Tk.

    Sans ceci, sur un PC configure avec une mise a l'echelle Windows
    differente de 100% (tres courant), Windows agrandit la fenetre a
    l'affichage sans que le programme le sache : la fenetre deborde alors
    de l'ecran (le ticket a droite et/ou le bas de la liste de categories
    se retrouvent hors champ) alors que tout semblait correct sur un PC
    regle a 100%."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def zone_travail_windows():
    """Renvoie (x, y, largeur, hauteur) de la zone d'ecran utile, hors barre
    des taches (contrairement a winfo_screenwidth/height qui donnent la
    taille totale de l'ecran et font passer le bas des fenetres dessous)."""
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    rect = RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


def diagnostiquer_ecran():
    """Renvoie un texte listant ce que Windows/Tkinter voient reellement sur
    ce poste (resolution brute, zone de travail hors barre des taches, DPI).
    Sert uniquement a diagnostiquer un probleme d'affichage a distance (ex:
    fenetre qui deborde sur un poste donne) - aucun impact sur la taille de
    la fenetre elle-meme, qui reste fixe."""
    lignes = []
    try:
        largeur_brute = ctypes.windll.user32.GetSystemMetrics(0)
        hauteur_brute = ctypes.windll.user32.GetSystemMetrics(1)
        lignes.append("Resolution ecran brute (GetSystemMetrics) : {} x {}".format(
            largeur_brute, hauteur_brute))
    except Exception as exc:
        lignes.append("Resolution ecran brute : indisponible ({})".format(exc))

    try:
        x, y, largeur_travail, hauteur_travail = zone_travail_windows()
        lignes.append(
            "Zone de travail hors barre des taches (SPI_GETWORKAREA) : "
            "{} x {} (origine x={}, y={})".format(largeur_travail, hauteur_travail, x, y)
        )
    except Exception as exc:
        lignes.append("Zone de travail hors barre des taches : indisponible ({})".format(exc))

    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        lignes.append("DPI systeme (GetDpiForSystem) : {} ({}% d'echelle)".format(
            dpi, round(dpi / 96 * 100)))
    except Exception as exc:
        lignes.append("DPI systeme : indisponible ({})".format(exc))

    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# Composants graphiques reutilisables (rectangles/pilules arrondis sur Canvas)
# ---------------------------------------------------------------------------
def _assombrir_couleur(hex_couleur, facteur=0.85):
    hex_couleur = hex_couleur.lstrip("#")
    r = int(hex_couleur[0:2], 16)
    g = int(hex_couleur[2:4], 16)
    b = int(hex_couleur[4:6], 16)
    r = max(0, int(r * facteur))
    g = max(0, int(g * facteur))
    b = max(0, int(b * facteur))
    return "#{:02x}{:02x}{:02x}".format(r, g, b)


def rectangle_arrondi(canvas, x1, y1, x2, y2, rayon, **kwargs):
    r = rayon
    points = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


_POLICES_TK = {}


def _police_tk(police):
    """tkfont.Font memorisee par police (tuple) : creer une Font a chaque
    mesure ralentirait beaucoup le redessin des grilles de tuiles."""
    f = _POLICES_TK.get(police)
    if f is None:
        f = _POLICES_TK[police] = tkfont.Font(font=police)
    return f


def _decouper(texte, police, largeur_max):
    """Coupe `texte` aux espaces (et aux retours a la ligne voulus) pour
    tenir dans `largeur_max` px. Renvoie (lignes, un_mot_depasse) : un mot
    seul plus large que la boite ne peut pas etre coupe proprement."""
    f = _police_tk(police)
    lignes, depasse = [], False
    for paragraphe in str(texte).split("\n"):
        courante = ""
        for mot in paragraphe.split():
            essai = (courante + " " + mot).strip()
            if f.measure(essai) <= largeur_max:
                courante = essai
            else:
                if courante:
                    lignes.append(courante)
                courante = mot
                depasse = depasse or f.measure(mot) > largeur_max
        lignes.append(courante)
    return lignes, depasse


def ajuster_texte(texte, police, largeur_max, hauteur_max, taille_min=8, taille_depart=None, lignes_max=3):
    """Plus grande taille de `police` (a partir de `taille_depart`, sans
    descendre sous `taille_min`) pour laquelle `texte` tient dans la boite
    sans qu'aucune lettre ne depasse : aucun mot coupe, `lignes_max` lignes
    au plus, hauteur respectee. Renvoie (police, lignes, hauteur_totale).
    C'est ce qui empeche les libelles trop longs ("Supprimer la categorie")
    d'etre rognes dans leur bouton."""
    taille = taille_depart or police[1]
    while True:
        p = (police[0], taille) + tuple(police[2:])
        lignes, depasse = _decouper(texte, p, largeur_max)
        hauteur = len(lignes) * _police_tk(p).metrics("linespace")
        if (not depasse and len(lignes) <= lignes_max and hauteur <= hauteur_max) or taille <= taille_min:
            return p, lignes, hauteur
        taille -= 1


class BoutonBase(tk.Canvas):
    """Bouton a coins arrondis dessine sur un Canvas (Tkinter n'a pas de
    bouton arrondi natif). Sert de base a Carte et de rendu de secours quand
    Pillow est absent. Accepte plusieurs lignes de texte, chacune avec
    sa propre police/couleur (ex: le nom d'une categorie).

    `pied` (optionnel) est un texte secondaire (ex: le prix) affiche en bas
    a gauche, sur une bande dediee en bas de la tuile - separee des lignes
    principales pour ne jamais les gener, meme quand celles-ci sont ecrites
    en grand.

    Si `commande_quantite` est fourni, un badge distinct ("123") apparait en
    bas a droite (sur la meme bande que `pied`) : cliquer dessus appelle
    `commande_quantite` au lieu de `commande` (utilise pour ouvrir le pave
    numerique de quantite sans declencher l'ajout normal x1).

    `image_chemin` (optionnel) affiche une icone (PNG, idealement avec fond
    transparent) au-dessus des lignes de texte, redimensionnee a chaque
    redessin pour suivre la taille reelle de la tuile (grille adaptative)."""

    def __init__(self, parent, lignes, commande=None, largeur=160, hauteur=76,
                 rayon=14, couleur_fond=BLANC, couleur_bordure=BRUN_200,
                 bg=CREME, commande_quantite=None, pied=None, image_chemin=None, **kwargs):
        super().__init__(parent, width=largeur, height=hauteur, bg=bg,
                          highlightthickness=0, **kwargs)
        self.commande = commande
        self.commande_quantite = commande_quantite
        self.couleur_fond = couleur_fond
        self.couleur_bordure = couleur_bordure
        self.lignes = lignes
        self.pied = pied
        self.rayon = rayon
        self._image_source = None  # image PIL d'origine, chargee une seule fois
        self._photo_image = None  # reference gardee pour eviter le garbage collection
        if image_chemin and Image is not None:
            try:
                self._image_source = Image.open(image_chemin).convert("RGBA")
            except Exception:
                self._image_source = None
        self._largeur = largeur
        self._hauteur = hauteur
        self._zone_badge = None
        self.bind("<Configure>", self._on_configure)
        self.bind("<ButtonPress-1>", lambda e: self._dessiner(appuye=True))
        self.bind("<ButtonRelease-1>", self._on_release)
        self._dessiner()

    def _on_configure(self, event):
        self._largeur = event.width
        self._hauteur = event.height
        self._dessiner()

    def _on_release(self, event):
        self._dessiner(appuye=False)
        if self._zone_badge:
            bx1, by1, bx2, by2 = self._zone_badge
            if bx1 <= event.x <= bx2 and by1 <= event.y <= by2:
                if self.commande_quantite:
                    self.commande_quantite()
                return
        if self.commande and 0 <= event.x <= self._largeur and 0 <= event.y <= self._hauteur:
            self.commande()

    def _dessiner(self, appuye=False):
        self.delete("all")
        w, h = self._largeur, self._hauteur
        fond = _assombrir_couleur(self.couleur_fond) if appuye else self.couleur_fond
        rectangle_arrondi(self, 1, 1, w - 1, h - 1, self.rayon,
                           fill=fond, outline=self.couleur_bordure, width=1)

        # Le prix/complement ("pied") et le badge de quantite ("123") vivent
        # tous les deux sur une bande dediee EN BAS de la tuile (pied a
        # gauche, badge a droite), plutot que le badge en haut a droite
        # comme avant : ca laissait moins de place au nom du produit, qui
        # devait etre decale et retreci pour ne pas passer dessous. En bas,
        # le nom garde toute la tuile pour lui et peut s'afficher plus gros.
        hauteur_pied = HAUTEUR_PIED_TUILE if (self.pied is not None or self.commande_quantite) else 0
        zone_hauteur = h - hauteur_pied

        # Si une icone est fournie (categories), elle occupe le haut de la
        # zone et le texte (nom de la categorie) se recentre dans le reste
        # en dessous, plutot que sur la hauteur complete.
        hauteur_icone = zone_hauteur * 0.6 if self._image_source is not None else 0
        zone_texte_haut = hauteur_icone
        zone_texte_hauteur = zone_hauteur - hauteur_icone

        hauteurs_lignes = [tkfont.Font(font=police).metrics("linespace") for _, police, _ in self.lignes]
        espace_extra = max(zone_texte_hauteur - sum(hauteurs_lignes), 0)
        interligne = espace_extra / (len(self.lignes) + 1) if self.lignes else 0

        y = zone_texte_haut + interligne
        for (texte, police, couleur), hauteur_ligne in zip(self.lignes, hauteurs_lignes):
            self.create_text(w / 2, y + hauteur_ligne / 2, text=texte, font=police, fill=couleur,
                              justify="center", width=w - 12)
            y += hauteur_ligne + interligne

        if hauteur_icone > 10:
            marge_icone = 10
            largeur_max = max(w - marge_icone * 2, 1)
            hauteur_max = max(hauteur_icone - marge_icone, 1)
            ratio = min(largeur_max / self._image_source.width, hauteur_max / self._image_source.height)
            if ratio > 0:
                taille = (max(1, int(self._image_source.width * ratio)),
                          max(1, int(self._image_source.height * ratio)))
                image_redim = self._image_source.resize(taille, Image.LANCZOS)
                self._photo_image = ImageTk.PhotoImage(image_redim)
                self.create_image(w / 2, hauteur_icone / 2, image=self._photo_image)

        if hauteur_pied:
            y_pied = h - hauteur_pied / 2
            if self.pied is not None:
                texte_pied, police_pied, couleur_pied = self.pied
                largeur_pied = w - 16
                if self.commande_quantite:
                    largeur_pied -= 54  # laisse la place au badge a droite
                self.create_text(10, y_pied, text=texte_pied, font=police_pied, fill=couleur_pied,
                                  anchor="w", justify="left", width=max(largeur_pied, 20))
            if self.commande_quantite:
                bw, bh = 48, 30
                bx2, by2 = w - 6, h - 4
                bx1, by1 = bx2 - bw, by2 - bh
                self._zone_badge = (bx1, by1, bx2, by2)
                rectangle_arrondi(self, bx1, by1, bx2, by2, 6, fill=BRUN_700, outline=BRUN_700)
                self.create_text((bx1 + bx2) / 2, (by1 + by2) / 2, text="123",
                                  font=POLICE_BADGE_QTE, fill=BLANC)
            else:
                self._zone_badge = None
        else:
            self._zone_badge = None

    def definir_lignes(self, lignes):
        self.lignes = lignes
        self._dessiner()

    def definir_fond(self, couleur_fond, couleur_bordure=None):
        self.couleur_fond = couleur_fond
        if couleur_bordure:
            self.couleur_bordure = couleur_bordure
        self._dessiner()


def largeur_texte(texte, police):
    return tkfont.Font(font=police).measure(texte)


def calculer_grille_adaptative(nombre_elements, largeur_dispo, hauteur_dispo, espace=14,
                                largeur_min=120, largeur_max=520, hauteur_min=70, hauteur_max=260):
    """Calcule une grille (colonnes, lignes, largeur de case, hauteur de
    case) qui remplit au mieux l'espace disponible avec `nombre_elements`
    cases : peu d'elements = grandes cases, beaucoup d'elements = cases plus
    petites mais toujours reparties pour remplir tout l'espace, sans jamais
    avoir besoin de scroller.

    Essaie tous les nombres de colonnes possibles et garde celui qui
    approche le mieux (largeur_min, hauteur_min) SANS jamais depasser
    l'espace reellement disponible : largeur_min/hauteur_min sont une
    preference, pas une garantie - avec beaucoup d'elements dans un petit
    espace, mieux vaut des cases un peu plus petites que des cases qui
    debordent hors de l'ecran (et forcent a scroller)."""
    if nombre_elements <= 0 or largeur_dispo <= 1 or hauteur_dispo <= 1:
        return 1, 1, largeur_min, hauteur_min

    meilleur = None
    for colonnes in range(1, nombre_elements + 1):
        lignes = -(-nombre_elements // colonnes)  # arrondi superieur
        largeur_case = (largeur_dispo - espace * (colonnes + 1)) / colonnes
        hauteur_case = (hauteur_dispo - espace * (lignes + 1)) / lignes
        if largeur_case <= 20 or hauteur_case <= 20:
            continue  # case inutilisable, meme en dernier recours

        manque = max(0, largeur_min - largeur_case) + max(0, hauteur_min - hauteur_case)
        taille_effective = min(largeur_case, largeur_max) + min(hauteur_case, hauteur_max)
        score = taille_effective - manque * 10  # penalise fort le fait de ne pas atteindre le minimum souhaite

        if meilleur is None or score > meilleur[0]:
            meilleur = (score, colonnes, lignes, largeur_case, hauteur_case)

    if meilleur is None:
        # espace vraiment trop petit pour la moindre grille : une seule
        # colonne, quitte a devoir scroller (cas extreme, pas le cas normal)
        return 1, nombre_elements, max(largeur_dispo - 2 * espace, largeur_min), hauteur_min

    _, colonnes, lignes, largeur_case, hauteur_case = meilleur
    largeur_case = min(largeur_case, largeur_max)
    hauteur_case = min(hauteur_case, hauteur_max)
    return colonnes, lignes, largeur_case, hauteur_case


def police_echelle(police_base, hauteur_case, taille_min=None, taille_max=None):
    """Renvoie une variante de `police_base` dont la taille suit grosso modo
    la hauteur de case disponible (case plus grande = texte plus grand),
    pour que les tuiles qui grandissent (peu d'elements a l'ecran) affichent
    aussi un texte plus lisible plutot qu'un texte fixe perdu au milieu."""
    taille_base = police_base[1]
    taille_min = taille_min if taille_min is not None else taille_base
    taille_max = taille_max if taille_max is not None else taille_base * 2
    taille = max(taille_min, min(round(hauteur_case * 0.22), taille_max))
    return (police_base[0], taille) + tuple(police_base[2:])


def police_ajustee_a_largeur(texte, police, largeur_max, taille_min=14):
    """Reduit la taille de `police` (sans descendre sous `taille_min`)
    jusqu'a ce que `texte` tienne sur une seule ligne dans `largeur_max`
    pixels. Sert pour les noms de categorie composes d'un seul mot (ex:
    "Viennoiserie", "Patisserie") : sans espace, Tkinter ne peut les couper
    qu'au milieu du mot faute de place, ce qui est illisible - mieux vaut
    rapetisser le texte que le voir coupe n'importe ou."""
    taille = police[1]
    while taille > taille_min:
        police_test = (police[0], taille) + tuple(police[2:])
        if largeur_texte(texte, police_test) <= largeur_max:
            return police_test
        taille -= 1
    return (police[0], taille_min) + tuple(police[2:])


def polices_ajustees_a_hauteur(polices, hauteur_max, taille_min=9):
    """Reduit la taille d'une liste de polices (une par ligne de texte,
    empilees dans une meme tuile) si leur hauteur cumulee depasse
    `hauteur_max`, pour que le texte ne deborde jamais hors du bas de sa
    tuile - meme logique que police_ajustee_a_largeur, mais en hauteur et
    pour plusieurs lignes qui se partagent le meme espace."""
    def hauteur_totale(pols):
        return sum(tkfont.Font(font=p).metrics("linespace") for p in pols)

    polices = list(polices)
    if hauteur_totale(polices) <= hauteur_max:
        return polices

    total = hauteur_totale(polices)
    facteur = hauteur_max / total if total > 0 else 1
    polices = [(p[0], max(taille_min, int(p[1] * facteur))) + tuple(p[2:]) for p in polices]

    # Le facteur proportionnel est approximatif (tailles entieres, metriques
    # de police non parfaitement lineaires) : on affine ensuite ligne par
    # ligne au besoin, en reduisant toujours la plus grande en premier,
    # jusqu'a rentrer dans hauteur_max ou atteindre taille_min partout.
    while hauteur_totale(polices) > hauteur_max and any(p[1] > taille_min for p in polices):
        i_max = max(range(len(polices)), key=lambda i: polices[i][1])
        p = polices[i_max]
        polices[i_max] = (p[0], p[1] - 1) + tuple(p[2:])

    return polices


class ScrollableFrame(tk.Frame):
    """Frame avec ascenseur vertical (molette active seulement au survol)."""

    def __init__(self, parent, bg=CREME, masquer_barre_auto=False, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.interior = tk.Frame(self.canvas, bg=bg)
        # masquer_barre_auto : l'ascenseur n'apparait que si le contenu
        # depasse vraiment (ecran de caisse : il tient presque toujours)
        self._masquer_barre_auto = masquer_barre_auto
        self._barre_visible = not masquer_barre_auto

        self.interior.bind("<Configure>", self._maj_region)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # La scrollbar DOIT etre empaquetee avant le canvas : sinon le canvas
        # (fill="both", expand=True) reclame toute la cavite disponible en
        # premier et ne laisse plus aucune place a la scrollbar, qui se
        # retrouve avec une taille de 1x1 px, invisible et inutilisable -
        # bug present depuis le debut, jamais remarque tant que le contenu
        # tenait sans avoir besoin de defiler.
        if self._barre_visible:
            self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _maj_region(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if self._masquer_barre_auto:
            self.after_idle(self._maj_barre)

    def _maj_barre(self):
        if not self.winfo_exists():
            return
        boite = self.canvas.bbox("all")
        hauteur_contenu = (boite[3] - boite[1]) if boite else 0
        besoin = hauteur_contenu > self.canvas.winfo_height() + 1
        if besoin == self._barre_visible:
            return
        self._barre_visible = besoin
        if besoin:
            self.scrollbar.pack(side="right", fill="y", before=self.canvas)
        else:
            self.scrollbar.pack_forget()
            self.canvas.yview_moveto(0)

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        if self._masquer_barre_auto:
            self.after_idle(self._maj_barre)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


# ---------------------------------------------------------------------------
# Rendu lisse (Pillow) de l'ecran de caisse : cartes a coins arrondis
# anticrenelees, ombre douce, pastilles rondes avec pictogramme. Le fond est
# une image (dessinee 3x plus grande puis reduite) ; le texte reste dessine
# par Tk par-dessus (net, ClearType). Sans Pillow : rendu BoutonBase.
# ---------------------------------------------------------------------------
def _rgb(couleur):
    c = couleur.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _rgba(couleur):
    """'#rrggbb' ou ('#rrggbb', opacite 0-255)."""
    if isinstance(couleur, tuple):
        return _rgb(couleur[0]) + (couleur[1],)
    return _rgb(couleur) + (255,)


def melanger(c1, c2, t):
    """Couleur intermediaire entre c1 (t=0) et c2 (t=1)."""
    a, b = _rgb(c1), _rgb(c2)
    return "#{:02x}{:02x}{:02x}".format(*(int(round(x + (y - x) * t)) for x, y in zip(a, b)))


_CACHE_PHOTOS = {}
_CACHE_ICONES = {}
TAILLE_MAX_CACHE = 300


def _photo_en_cache(cle, fabrique):
    """PhotoImage memorisee par cle : les tuiles identiques (meme taille,
    memes couleurs) partagent la meme image, rendue une seule fois."""
    photo = _CACHE_PHOTOS.get(cle)
    if photo is None:
        if len(_CACHE_PHOTOS) >= TAILLE_MAX_CACHE:
            _CACHE_PHOTOS.clear()  # chaque widget garde sa propre reference
        photo = _CACHE_PHOTOS[cle] = ImageTk.PhotoImage(fabrique())
    return photo


def _icone(chemin):
    if chemin not in _CACHE_ICONES:
        try:
            _CACHE_ICONES[chemin] = Image.open(chemin).convert("RGBA")
        except Exception:
            _CACHE_ICONES[chemin] = None
    return _CACHE_ICONES[chemin]


def _degrade(taille, c1, c2, sens="v"):
    w, h = taille
    masque = Image.linear_gradient("L")  # 256x256, noir en haut -> blanc en bas
    if sens == "h":
        masque = masque.transpose(Image.ROTATE_90)  # noir a gauche -> c1 a gauche
    masque = masque.resize((w, h), Image.BILINEAR)
    return Image.composite(Image.new("RGB", (w, h), _rgb(c2)), Image.new("RGB", (w, h), _rgb(c1)), masque)


def _trait_rond(draw, points, couleur, epaisseur):
    draw.line(points, fill=couleur, width=int(epaisseur))
    r = epaisseur / 2
    for x, y in points:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=couleur)


def _dessiner_chevron(draw, k, chevron):
    cx, cy, taille, couleur, sens, epaisseur = chevron
    t = taille * k
    cx, cy = cx * k, cy * k
    if sens == "droite":
        pts = [(cx - t / 4, cy - t / 2), (cx + t / 4, cy), (cx - t / 4, cy + t / 2)]
    elif sens == "gauche":
        pts = [(cx + t / 4, cy - t / 2), (cx - t / 4, cy), (cx + t / 4, cy + t / 2)]
    else:  # bas
        pts = [(cx - t / 2, cy - t / 4), (cx, cy + t / 4), (cx + t / 2, cy - t / 4)]
    _trait_rond(draw, pts, _rgba(couleur), epaisseur * k)


def boite_carte(w, h, ombre, appuye=False):
    """Rectangle (x1, y1, x2, y2) de la carte dans son canevas : marge pour
    l'ombre, et carte decalee de 2 px vers le bas quand elle est enfoncee."""
    if not ombre:
        return 0, 0, w - 1, h - 1
    decalage = 2 if appuye else 0
    return 5, 3 + decalage, w - 6, h - 10 + decalage


def rendre_carte(w, h, rayon, fond, bordure, bg, ombre=True, appuye=False, accent=None,
                 degrade=None, pastilles=(), badge=None, chevrons=(), puces=()):
    """Image Pillow (RGB, w x h) d'une carte complete, sans le texte.
    degrade : (couleur1, couleur2[, "v"|"h"]) a la place de `fond`.
    accent : couleur d'une pastille verticale a gauche (inseree dans la carte).
    pastilles : [(cx, cy, diametre, couleur, chemin_icone, fraction_icone)].
    badge / puces : (x1, y1, x2, y2, couleur) pilules (badge unique ; puces en nombre libre).
    chevrons : voir _dessiner_chevron."""
    k = 3 if w * h <= 120000 else 2
    x1, y1, x2, y2 = boite_carte(w, h, ombre, appuye)
    image = Image.new("RGB", (w, h), _rgb(bg))
    if ombre:
        dy, flou, force = (1, 3, 0.10) if appuye else (4, 6, 0.13)
        masque = Image.new("L", (w, h), 0)
        ImageDraw.Draw(masque).rounded_rectangle([x1, y1 + dy, x2, y2 + dy], rayon, fill=int(255 * force))
        image.paste(_rgb(COULEUR_OMBRE), (0, 0, w, h), masque.filter(ImageFilter.GaussianBlur(flou)))
    W, H = w * k, h * k
    image = image.resize((W, H), Image.BILINEAR)
    forme = Image.new("L", (W, H), 0)
    ImageDraw.Draw(forme).rounded_rectangle([x1 * k, y1 * k, x2 * k + k - 1, y2 * k + k - 1], rayon * k, fill=255)

    if degrade:
        c1, c2 = degrade[0], degrade[1]
        if appuye:
            c1, c2 = _assombrir_couleur(c1, 0.9), _assombrir_couleur(c2, 0.9)
        couche = _degrade((W, H), c1, c2, degrade[2] if len(degrade) > 2 else "v")
    else:
        couche = Image.new("RGB", (W, H), _rgb(fond))
    couche = couche.convert("RGBA")
    calque = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    if accent:
        # pastille verticale inseree (et non une barre collee au bord)
        d.rounded_rectangle([(x1 + 12) * k, (y1 + 16) * k, (x1 + 17) * k, (y2 - 16) * k], 3 * k,
                            fill=_rgba(accent))
    for px1, py1, px2, py2, couleur in puces:
        d.rounded_rectangle([px1 * k, py1 * k, px2 * k, py2 * k], (py2 - py1) / 2 * k, fill=_rgba(couleur))
    for cx, cy, diametre, couleur, chemin, fraction in pastilles:
        r = diametre * k / 2
        d.ellipse([cx * k - r, cy * k - r, cx * k + r, cy * k + r], fill=_rgba(couleur))
        icone = _icone(chemin) if chemin else None
        if icone is not None:
            t = max(1, int(diametre * k * fraction))
            calque.alpha_composite(icone.resize((t, t), Image.LANCZOS), (int(cx * k - t / 2), int(cy * k - t / 2)))
    if badge:
        bx1, by1, bx2, by2, couleur = badge
        d.rounded_rectangle([bx1 * k, by1 * k, bx2 * k, by2 * k], (by2 - by1) / 2 * k, fill=_rgba(couleur))
    for chevron in chevrons:
        _dessiner_chevron(d, k, chevron)
    couche = Image.alpha_composite(couche, calque).convert("RGB")
    if bordure:
        interieur = Image.new("L", (W, H), 0)
        ImageDraw.Draw(interieur).rounded_rectangle(
            [x1 * k + k, y1 * k + k, x2 * k - 1, y2 * k - 1], max(rayon * k - k, 1), fill=255)
        couche.paste(_rgb(bordure), (0, 0, W, H), ImageChops.subtract(forme, interieur))
    image.paste(couche, (0, 0), forme)
    return image.resize((w, h), Image.LANCZOS)


def photo_pastille(diametre, couleur, chemin_icone, bg, fraction=0.58):
    """Pastille ronde coloree + pictogramme (titre de l'ecran produits)."""
    if Image is None:
        return None
    cle = ("pastille", diametre, couleur, chemin_icone, bg, fraction)
    r = diametre / 2
    return _photo_en_cache(cle, lambda: rendre_carte(
        diametre, diametre, 1, bg, None, bg, ombre=False,
        pastilles=[(r, r, diametre - 1, couleur, chemin_icone, fraction)]))


class Carte(BoutonBase):
    """Bouton / tuile au rendu lisse (meme interface que BoutonBase :
    lignes, pied, commande, commande_quantite, definir_lignes, definir_fond).

    Le texte est ajuste automatiquement a la place disponible (voir
    ajuster_texte) : il reduit ou passe sur plusieurs lignes plutot que de
    depasser de la carte.

    disposition :
      "centre"    texte centre (boutons) ;
      "categorie" pastille coloree + pictogramme, nom dessous ;
      "produit"   nom a gauche, prix (pied) dans une puce en bas a gauche,
                  badge "123" en bas a droite, pastille `accent` a gauche ;
      "bandeau"   pastille a gauche, texte aligne a gauche, chevron a droite.
    """

    def __init__(self, parent, lignes, commande=None, largeur=160, hauteur=76, rayon=18,
                 couleur_fond=BLANC, couleur_bordure=BORDURE_CARTE, bg=CREME,
                 commande_quantite=None, pied=None, ombre=True, accent=None, degrade=None,
                 icone=None, couleur_pastille=None, disposition="centre", chevron=None,
                 couleur_chevron=BRUN_500, couleur_appui=None,
                 couleurs_badge=(FOND_SEGMENT, BRUN_700), diametre_pastille=None, lignes_max=2, **kwargs):
        self._bg = bg
        self.ombre = ombre
        self.accent = accent
        self.degrade = degrade
        self.icone = icone
        self.couleur_pastille = couleur_pastille
        self.disposition = disposition
        self.chevron = chevron
        self.couleur_chevron = couleur_chevron
        self.couleur_appui = couleur_appui
        self.couleurs_badge = couleurs_badge
        self.diametre_pastille = diametre_pastille
        self.lignes_max = lignes_max
        self._photo_fond = None
        super().__init__(parent, lignes, commande=commande, largeur=largeur, hauteur=hauteur,
                         rayon=rayon, couleur_fond=couleur_fond, couleur_bordure=couleur_bordure,
                         bg=bg, commande_quantite=commande_quantite, pied=pied, **kwargs)

    def _fond_appuye(self):
        if self.couleur_appui:
            return self.couleur_appui
        if self.couleur_fond.lower() == BLANC:
            return ROSE_TRES_PALE
        return _assombrir_couleur(self.couleur_fond, 0.9)

    def _blocs(self, largeur_max, hauteur_max, taille_min=8):
        """[(texte_rendu, police, couleur, hauteur)] : une entree par ligne
        de `self.lignes`, chacune ajustee a la largeur, puis l'ensemble
        reduit (la plus grande police d'abord) jusqu'a tenir en hauteur."""
        largeur_max, hauteur_max = max(largeur_max, 10), max(hauteur_max, 10)
        tailles = [police[1] for _, police, _ in self.lignes]
        while True:
            blocs = []
            for (texte, police, couleur), taille in zip(self.lignes, tailles):
                p, lignes, h = ajuster_texte(texte, police, largeur_max, hauteur_max, taille_min=taille_min,
                                             taille_depart=taille, lignes_max=self.lignes_max)
                blocs.append(("\n".join(lignes), p, couleur, h))
            if not blocs or sum(b[3] for b in blocs) <= hauteur_max or all(t <= taille_min for t in tailles):
                return blocs
            i = max(range(len(blocs)), key=lambda k: blocs[k][1][1])
            tailles[i] = blocs[i][1][1] - 1

    def _dessiner(self, appuye=False):
        if Image is None:
            self.couleur_bordure = self.couleur_bordure or self.couleur_fond
            BoutonBase._dessiner(self, appuye)
            return
        self.delete("all")
        w, h = int(self._largeur), int(self._hauteur)
        if w < 12 or h < 12:
            return
        x1, y1, x2, y2 = boite_carte(w, h, self.ombre, appuye)
        pastilles, chevrons, puces, badge = [], [], [], None
        textes = []  # (x, y, texte, police, couleur, ancre, largeur_max)
        self._zone_badge = None

        if self.disposition == "categorie":
            blocs = self._blocs(x2 - x1 - 16, max((y2 - y1) * 0.34, 22))
            hauteur_texte = sum(b[3] for b in blocs)
            ecart = 8
            diametre = self.diametre_pastille or int(min((y2 - y1) - hauteur_texte - ecart - 20, (x2 - x1) * 0.5, 84))
            diametre = max(diametre, 24)
            haut = y1 + ((y2 - y1) - (diametre + ecart + hauteur_texte)) / 2
            if self.icone or self.couleur_pastille:
                pastilles.append(((x1 + x2) / 2, haut + diametre / 2, diametre,
                                  self.couleur_pastille or FRAMBOISE, self.icone, 0.58))
                if not self.icone and self.lignes:
                    # pas de pictogramme (categorie ajoutee plus tard) : initiale
                    textes.append(((x1 + x2) / 2, haut + diametre / 2, self.lignes[0][0][:1].upper(),
                                   ("Segoe UI", max(int(diametre * 0.34), 10), "bold"), BLANC, "center", diametre))
            y = haut + diametre + ecart
            for texte, police, couleur, hb in blocs:
                textes.append(((x1 + x2) / 2, y + hb / 2, texte, police, couleur, "center", x2 - x1 - 16))
                y += hb

        elif self.disposition == "bandeau":
            diametre = self.diametre_pastille or int(min((y2 - y1) - 22, 60))
            cx = x1 + 18 + diametre / 2
            cy = (y1 + y2) / 2
            if self.icone or self.couleur_pastille:
                pastilles.append((cx, cy, diametre, self.couleur_pastille or ("#ffffff", 46), self.icone, 0.52))
            if self.chevron:
                chevrons.append((x2 - 30, cy, 22, self.couleur_chevron, "droite", 3.2))
            xt = cx + diametre / 2 + 16
            blocs = self._blocs(x2 - xt - 50, (y2 - y1) - 16)
            y = cy - sum(b[3] for b in blocs) / 2
            for texte, police, couleur, hb in blocs:
                textes.append((xt, y + hb / 2, texte, police, couleur, "w", x2 - xt - 50))
                y += hb

        elif self.disposition == "produit":
            gauche = x1 + (24 if self.accent else 16)
            hauteur_pied = HAUTEUR_PIED_TUILE if (self.pied is not None or self.commande_quantite) else 0
            zone_haut, zone_bas = y1 + 10, y2 - hauteur_pied - 2
            largeur_nom = x2 - gauche - 14
            blocs = self._blocs(largeur_nom, zone_bas - zone_haut)
            y = zone_haut + max((zone_bas - zone_haut) - sum(b[3] for b in blocs), 0) / 2
            for texte, police, couleur, hb in blocs:
                textes.append((gauche, y + hb / 2, texte, police, couleur, "w", largeur_nom))
                y += hb
            if hauteur_pied:
                bas, haut_pied = y2 - 11, y2 - 11 - 30
                droite_libre = x2 - 12
                if self.commande_quantite:
                    bw = 52
                    bx2 = x2 - 12
                    bx1 = bx2 - bw
                    badge = (bx1, haut_pied, bx2, bas, self.couleurs_badge[0])
                    textes.append(((bx1 + bx2) / 2, (haut_pied + bas) / 2, "123", POLICE_BADGE_QTE,
                                   self.couleurs_badge[1], "center", bw))
                    # zone tactile un peu plus large que le dessin
                    self._zone_badge = (bx1 - 6, haut_pied - 10, w, h)
                    droite_libre = bx1 - 8
                if self.pied is not None:
                    texte_pied, police_pied, couleur_pied = self.pied
                    x_pied = gauche - 4  # aligne sur le nom, a droite de la pastille d'accent
                    largeur_pied = max(droite_libre - x_pied - 8, 20)
                    police_pied = police_ajustee_a_largeur(texte_pied, police_pied, largeur_pied - 20, taille_min=9)
                    if "italic" in police_pied:  # indication ("Voir les parfums") : sans puce
                        textes.append((gauche, (haut_pied + bas) / 2, texte_pied, police_pied, couleur_pied,
                                       "w", largeur_pied))
                    else:
                        lt = _police_tk(police_pied).measure(texte_pied)
                        px2 = min(x_pied + lt + 22, droite_libre)
                        puces.append((x_pied, haut_pied, px2, bas, melanger(self.accent or FRAMBOISE, BLANC, 0.88)))
                        textes.append(((x_pied + px2) / 2, (haut_pied + bas) / 2, texte_pied, police_pied,
                                       couleur_pied, "center", px2 - x_pied))

        else:  # centre
            decalage = 0
            marge_texte = 16
            if self.chevron == "gauche":
                largeur_texte_max = max((_police_tk(p).measure(t) for t, p, _ in self.lignes), default=0)
                cx_chevron = (x1 + x2) / 2 - largeur_texte_max / 2 - 4
                decalage = 9
                chevrons.append((cx_chevron - 6 + decalage / 2, (y1 + y2) / 2, 14, self.couleur_chevron, "gauche", 2.6))
                marge_texte += 2 * decalage
            blocs = self._blocs(x2 - x1 - marge_texte, (y2 - y1) - 8)
            espace = max((y2 - y1) - sum(b[3] for b in blocs), 0)
            interligne = espace / (len(blocs) + 1) if blocs else 0
            y = y1 + interligne
            for texte, police, couleur, hb in blocs:
                textes.append(((x1 + x2) / 2 + decalage, y + hb / 2, texte, police, couleur, "center",
                               x2 - x1 - marge_texte))
                y += hb + interligne

        fond = self._fond_appuye() if appuye else self.couleur_fond
        bordure = self.couleur_bordure if (self.couleur_bordure and self.couleur_bordure != self.couleur_fond) else None
        cle = ("carte", w, h, self.rayon, fond, bordure, self._bg, self.ombre, appuye, self.accent,
               self.degrade, tuple(pastilles), badge, tuple(chevrons), tuple(puces))
        self._photo_fond = _photo_en_cache(cle, lambda: rendre_carte(
            w, h, self.rayon, fond, bordure, self._bg, ombre=self.ombre, appuye=appuye,
            accent=self.accent, degrade=self.degrade, pastilles=pastilles, badge=badge, chevrons=chevrons,
            puces=puces))
        self.create_image(0, 0, anchor="nw", image=self._photo_fond)
        for x, y, texte, police, couleur, ancre, largeur_max in textes:
            self.create_text(x, y, text=texte, font=police, fill=couleur, anchor=ancre,
                             justify="center" if ancre == "center" else "left", width=max(largeur_max, 10) + 4)


class BoutonArrondi(Carte):
    """Bouton plat a coins arrondis (dialogues, pave numerique, admin...) :
    meme rendu lisse et meme ajustement automatique du texte que Carte, sans
    ombre. Interface historique conservee (lignes, commande, couleur_fond,
    couleur_bordure...) pour que tous les ecrans en profitent d'un coup."""

    def __init__(self, parent, lignes, commande=None, largeur=160, hauteur=76,
                 rayon=14, couleur_fond=BLANC, couleur_bordure=BRUN_200,
                 bg=CREME, commande_quantite=None, pied=None, image_chemin=None, **kwargs):
        kwargs.setdefault("ombre", False)
        # coins plus ronds qu'avant, sans depasser la demi-hauteur (pilule)
        rayon = int(min(max(rayon, 14) + 4, hauteur // 2))
        super().__init__(parent, lignes, commande=commande, largeur=largeur, hauteur=hauteur, rayon=rayon,
                         couleur_fond=couleur_fond, couleur_bordure=couleur_bordure, bg=bg,
                         commande_quantite=commande_quantite, pied=pied, **kwargs)


class Segments(tk.Canvas):
    """Choix exclusif sur une pilule claire (ex: Sur place / A emporter) :
    l'option active est en framboise. commande(cle) a chaque tap."""

    def __init__(self, parent, options, commande, largeur=272, hauteur=46, bg=BLANC,
                 police=POLICE_BOUTON_ROND, couleur_active=FRAMBOISE):
        super().__init__(parent, width=largeur, height=hauteur, bg=bg, highlightthickness=0)
        self.options = list(options)
        self.commande = commande
        self.police = police
        self.couleur_active = couleur_active
        self._bg = bg
        self.actif = None
        self._photo = None
        self._largeur, self._hauteur = largeur, hauteur
        self.bind("<Configure>", self._sur_configure)
        self.bind("<ButtonRelease-1>", self._sur_clic)
        self._dessiner()

    def _sur_configure(self, event):
        self._largeur, self._hauteur = event.width, event.height
        self._dessiner()

    def _sur_clic(self, event):
        if not (0 <= event.x <= self._largeur and 0 <= event.y <= self._hauteur):
            return
        index = min(int(event.x / (self._largeur / len(self.options))), len(self.options) - 1)
        self.commande(self.options[index][0])

    def definir_actif(self, cle):
        self.actif = cle
        self._dessiner()

    def _dessiner(self):
        self.delete("all")
        w, h = int(self._largeur), int(self._hauteur)
        if w < 20 or h < 10:
            return
        n = len(self.options)
        largeur_seg = w / n
        cles = [c for c, _ in self.options]
        index = cles.index(self.actif) if self.actif in cles else -1
        if Image is not None:
            def fabrique():
                image = rendre_carte(w, h, 12, FOND_SEGMENT, None, self._bg, ombre=False)
                if index >= 0:
                    sx1 = int(index * largeur_seg) + 3
                    pouce = rendre_carte(int(largeur_seg) - 6, h - 6, 10, self.couleur_active, None,
                                         FOND_SEGMENT, ombre=False)
                    image.paste(pouce, (sx1, 3))
                return image
            self._photo = _photo_en_cache(("segments", w, h, n, index, self._bg, self.couleur_active), fabrique)
            self.create_image(0, 0, anchor="nw", image=self._photo)
        else:
            rectangle_arrondi(self, 1, 1, w - 1, h - 1, 12, fill=FOND_SEGMENT, outline=FOND_SEGMENT)
            if index >= 0:
                rectangle_arrondi(self, index * largeur_seg + 3, 3, (index + 1) * largeur_seg - 3, h - 3, 10,
                                  fill=self.couleur_active, outline=self.couleur_active)
        for i, (cle, texte) in enumerate(self.options):
            police = police_ajustee_a_largeur(texte, self.police, largeur_seg - 14, taille_min=9)
            self.create_text((i + 0.5) * largeur_seg, h / 2, text=texte, font=police,
                             fill=BLANC if i == index else BRUN_700)


def rendre_entete(w, h, couleur_gauche, couleur_droite, pilules=(), cercles=(), chevrons=()):
    """Fond de l'en-tete (degrade horizontal) avec pilules et cercles lisses.
    pilules : [(x1, y1, x2, y2, remplissage, contour ou None)] ;
    cercles : [(cx, cy, rayon, couleur)] ; couleurs '#rrggbb' ou (hex, opacite)."""
    k = 2
    image = _degrade((w * k, h * k), couleur_gauche, couleur_droite, "h").convert("RGBA")
    calque = Image.new("RGBA", image.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(calque)
    for x1, y1, x2, y2, remplissage, contour in pilules:
        d.rounded_rectangle([x1 * k, y1 * k, x2 * k, y2 * k], (y2 - y1) / 2 * k, fill=_rgba(remplissage),
                            outline=_rgba(contour) if contour else None, width=k if contour else 0)
    for cx, cy, r, couleur in cercles:
        d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=_rgba(couleur))
    for chevron in chevrons:
        _dessiner_chevron(d, k, chevron)
    return Image.alpha_composite(image, calque).convert("RGB").resize((w, h), Image.LANCZOS)


def photo_entete(w, h, couleur_gauche, couleur_droite, pilules=(), cercles=(), chevrons=()):
    if Image is None:
        return None
    cle = ("entete", w, h, couleur_gauche, couleur_droite, tuple(pilules), tuple(cercles), tuple(chevrons))
    return _photo_en_cache(cle, lambda: rendre_entete(w, h, couleur_gauche, couleur_droite,
                                                      pilules, cercles, chevrons))


def texte_dans_boite(texte, police, largeur_max, hauteur_max, taille_min=10, lignes_max=3):
    """Plus grande taille de `police` (sans descendre sous taille_min) pour
    laquelle `texte`, coupe aux espaces, tient dans la boite. Renvoie
    (police, [lignes]) : "Framboise vanille citron" passe sur 2 lignes
    plutot que d'etre ecrit en tout petit sur une seule."""
    mots = texte.split() or [texte]
    taille = police[1]
    while True:
        p = (police[0], taille) + tuple(police[2:])
        f = tkfont.Font(font=p)
        lignes, courante = [], ""
        trop_long = False
        for mot in mots:
            essai = (courante + " " + mot).strip()
            if f.measure(essai) <= largeur_max:
                courante = essai
            else:
                if courante:
                    lignes.append(courante)
                courante = mot
                trop_long = trop_long or f.measure(mot) > largeur_max
        lignes.append(courante)
        tient = (not trop_long and len(lignes) <= lignes_max
                 and len(lignes) * f.metrics("linespace") <= hauteur_max)
        if tient or taille <= taille_min:
            return p, lignes
        taille -= 1
