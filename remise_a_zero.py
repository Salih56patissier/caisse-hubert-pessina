# -*- coding: utf-8 -*-
"""
Remise a zero ponctuelle (fin des tests), declenchee par un fichier
"remise_a_zero.flag" depose a cote de caisse.db et contenant le mot
CONFIRMER. Au demarrage de la caisse : toutes les donnees de vente sont
effacees (comme un ticket Z, sans impression), le fichier est supprime et
l'operation est notee dans remise_a_zero.log. Produits, vendeurs et
reglages sont conserves. Les id continuent (pas de doublon dans Google).
"""

import os
from datetime import datetime

import database
import ticket_z

DOSSIER = os.path.dirname(database.DB_PATH)
FICHIER_FLAG = os.path.join(DOSSIER, "remise_a_zero.flag")
FICHIER_LOG = os.path.join(DOSSIER, "remise_a_zero.log")


def appliquer_si_demandee(conn):
    if not os.path.exists(FICHIER_FLAG):
        return False
    try:
        with open(FICHIER_FLAG, encoding="utf-8") as f:
            ok = "CONFIRMER" in f.read()
    except OSError:
        ok = False
    if not ok:
        return False
    compte = {t: conn.execute("SELECT COUNT(*) AS n FROM {}".format(t)).fetchone()["n"]
              for t in ticket_z.TABLES_EFFACEES}
    with conn:
        for table in ticket_z.TABLES_EFFACEES:
            conn.execute("DELETE FROM {}".format(table))
    conn.execute("VACUUM")
    os.remove(FICHIER_FLAG)
    with open(FICHIER_LOG, "a", encoding="utf-8") as f:
        f.write("{}  remise a zero : {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), compte))
    return True
