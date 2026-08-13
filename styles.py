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
ROUGE = "#d1554a"
BLANC = "#ffffff"

HEADER_DEGRADE_GAUCHE = "#e75480"
HEADER_DEGRADE_DROITE = "#c2185b"

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
        decalage_bas = marge_badge_haut + bh + 6 if self.commande_quantite else 0

        nb = len(self.lignes)
        hauteur_texte = h - decalage_bas
        for i, (texte, police, couleur) in enumerate(self.lignes):
            y = decalage_bas + hauteur_texte * (i + 1) / (nb + 1)
            self.create_text(w / 2, y, text=texte, font=police, fill=couleur,
                              justify="center", width=w - 12)

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
    return tkfont.Font(family=police[0], size=police[1],
                        weight=police[2] if len(police) > 2 else "normal").measure(texte)


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

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
