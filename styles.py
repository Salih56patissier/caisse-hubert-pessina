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

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
BRUN_900 = "#3e2723"
BRUN_800 = "#4a2f2a"
BRUN_700 = "#5d4037"
BRUN_600 = "#6d4c41"
BRUN_500 = "#8d6e63"
BRUN_300 = "#a1887f"
BRUN_200 = "#d7ccc8"
BRUN_100 = "#efebe9"
CREME = "#faf6f1"
OR = "#c17f2b"
OR_CLAIR = "#e6a94f"
VERT = "#3f9142"
ROSE = "#e75480"
ROUGE = "#d1554a"
BLANC = "#ffffff"

HEADER_DEGRADE_GAUCHE = "#e75480"
HEADER_DEGRADE_DROITE = "#c2185b"

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

# Place reservee en haut d'une tuile quand elle a un badge de quantite
# ("123", coin superieur droit) : le texte de la tuile doit rester sous
# cette zone (voir BoutonArrondi._dessiner) - largeur du badge + marges.
MARGE_BADGE_QUANTITE = 48

POLICE_TITRE = ("Georgia", 26, "bold")
POLICE_BADGE = ("Segoe UI", 10, "bold")
POLICE_TICKET_TITRE = ("Georgia", 17, "bold")
POLICE_CATEGORIE = ("Segoe UI", 20, "bold")
POLICE_CATEGORIE_CAISSE = ("Segoe UI", 22, "bold")  # pastilles de categories de l'ecran de caisse (compact mais tactile)
POLICE_PRODUIT_NOM = ("Segoe UI", 14, "bold")
POLICE_PRODUIT_PRIX = ("Segoe UI", 15, "bold")
POLICE_PRODUIT_HINT = ("Segoe UI", 11, "italic")
POLICE_SOUS_TITRE = ("Georgia", 17, "bold")
POLICE_TOTAL = ("Georgia", 24, "bold")
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


class BoutonArrondi(tk.Canvas):
    """Bouton a coins arrondis dessine sur un Canvas (Tkinter n'a pas de
    bouton arrondi natif). Accepte plusieurs lignes de texte, chacune avec
    sa propre police/couleur (ex: nom du produit + prix).

    Si `commande_quantite` est fourni, un petit badge distinct ("123")
    apparait dans le coin superieur droit : cliquer dessus appelle
    `commande_quantite` au lieu de `commande` (utilise pour ouvrir le pave
    numerique de quantite sans declencher l'ajout normal x1)."""

    def __init__(self, parent, lignes, commande=None, largeur=160, hauteur=76,
                 rayon=14, couleur_fond=BLANC, couleur_bordure=BRUN_200,
                 bg=CREME, commande_quantite=None, **kwargs):
        super().__init__(parent, width=largeur, height=hauteur, bg=bg,
                          highlightthickness=0, **kwargs)
        self.commande = commande
        self.commande_quantite = commande_quantite
        self.couleur_fond = couleur_fond
        self.couleur_bordure = couleur_bordure
        self.lignes = lignes
        self.rayon = rayon
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

        # Quand la tuile a un badge de quantite ("123", coin superieur droit),
        # la 1ere ligne de texte (le nom du produit) tombe dans la meme zone
        # que ce badge : sans precaution, elle est centree sur toute la
        # largeur et vient passer dessous, invisible une fois le badge
        # dessine par-dessus. On decale donc TOUT le texte vers le bas, sous
        # le badge, plutot que de retrecir sa largeur : retrecir forcait
        # parfois Tkinter a couper un mot au milieu (ex: "Mille-feuille" /
        # "s" sur 2 lignes) faute de place, ce qui est pire que le probleme
        # d'origine. Decaler verticalement laisse toute la largeur au texte.
        bw, bh = 58, 36
        marge_badge_haut = 6
        decalage_bas = MARGE_BADGE_QUANTITE if self.commande_quantite else 0

        # Repartition verticale basee sur la vraie hauteur de chaque ligne
        # (chaque ligne peut avoir sa propre police/taille, notamment sur
        # les tuiles produits dont la police s'agrandit avec la tuile) :
        # diviser l'espace en parts egales, comme avant, ne tenait pas
        # compte de la taille reelle du texte et pouvait faire chevaucher
        # deux lignes des qu'une police etait agrandie.
        zone_haut = decalage_bas
        zone_hauteur = h - decalage_bas
        # tkfont.Font(font=police) laisse Tk interpreter directement le tuple
        # (family, taille, style...) : le style peut etre "bold", "italic"
        # ou les deux, contrairement a un mapping manuel vers weight= qui ne
        # comprend pas "italic" et plantait sur les lignes en italique.
        hauteurs_lignes = [tkfont.Font(font=police).metrics("linespace") for _, police, _ in self.lignes]
        espace_extra = max(zone_hauteur - sum(hauteurs_lignes), 0)
        interligne = espace_extra / (len(self.lignes) + 1) if self.lignes else 0

        y = zone_haut + interligne
        for (texte, police, couleur), hauteur_ligne in zip(self.lignes, hauteurs_lignes):
            self.create_text(w / 2, y + hauteur_ligne / 2, text=texte, font=police, fill=couleur,
                              justify="center", width=w - 12)
            y += hauteur_ligne + interligne

        if self.commande_quantite:
            bx2, by1 = w - 6, marge_badge_haut
            bx1, by2 = bx2 - bw, by1 + bh
            self._zone_badge = (bx1, by1, bx2, by2)
            rectangle_arrondi(self, bx1, by1, bx2, by2, 6, fill=BRUN_700, outline=BRUN_700)
            self.create_text((bx1 + bx2) / 2, (by1 + by2) / 2, text="123",
                              font=POLICE_BADGE_QTE, fill=BLANC)
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

    def __init__(self, parent, bg=CREME, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.interior = tk.Frame(self.canvas, bg=bg)

        self.interior.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # La scrollbar DOIT etre empaquetee avant le canvas : sinon le canvas
        # (fill="both", expand=True) reclame toute la cavite disponible en
        # premier et ne laisse plus aucune place a la scrollbar, qui se
        # retrouve avec une taille de 1x1 px, invisible et inutilisable -
        # bug present depuis le debut, jamais remarque tant que le contenu
        # tenait sans avoir besoin de defiler.
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
