"""
Module principal de scan.
Orchestre le processus de scan : connexion BDD, parcours des dossiers,
mise à jour des données et envoi de notifications.
"""

import os
import time
from datetime import datetime

from db import (
    connecter_base_de_donnees,
    creer_scan,
    deconnecter_base_de_donnees,
    terminer_scan,
    traiter_dossiers_en_lot,
)
from fichiers import filtrer_dossiers_redondants, scanner_arborescence
from notifications import envoyer_notif_teams


def scanner() -> None:
    """
    Scanne tous les dossiers à partir des chemins racines définis dans .env.
    """
    connexion_mysql = None
    id_scan = None
    debut_scan = time.time()
    try:
        connexion_mysql = connecter_base_de_donnees()
        id_scan = creer_scan(connexion_mysql)

        # Parse les chemins racines séparés par des virgules
        chemins_racines = os.getenv("CHEMINS_RACINES", "").split(",")

        # Parse les chemins exclus séparés par des virgules
        chemins_exclus = [
            c.strip() for c in os.getenv("CHEMINS_EXCLUS", "").split(",") if c.strip()
        ]

        nouveaux_dossiers = []
        dossiers_modifies = []
        taille_totale_scan = 0

        for chemin_racine in chemins_racines:
            chemin_racine = chemin_racine.strip()
            if not chemin_racine:
                continue
            dossiers_avec_tailles = scanner_arborescence(chemin_racine, chemins_exclus)
            nouveaux, modifies, taille_scan = traiter_dossiers_en_lot(
                connexion_mysql, dossiers_avec_tailles
            )
            nouveaux_dossiers.extend(nouveaux)
            dossiers_modifies.extend(modifies)
            taille_totale_scan += taille_scan

        # Filtre les dossiers parents redondants pour la notification
        nouveaux_dossiers = filtrer_dossiers_redondants(nouveaux_dossiers)
        dossiers_modifies = filtrer_dossiers_redondants(dossiers_modifies)

        # Construction du message pour la notification Teams
        message = "✅ Scan terminé avec succès"

        # Calcul de la durée du scan
        duree_scan = time.time() - debut_scan
        heures = int(duree_scan // 3600)
        minutes = int((duree_scan % 3600) // 60)
        secondes = int(duree_scan % 60)
        if heures > 0:
            duree_formatee = f"{heures}h {minutes}min {secondes}s"
        elif minutes > 0:
            duree_formatee = f"{minutes}min {secondes}s"
        else:
            duree_formatee = f"{secondes}s"

        message += f"\n<br>📅 {datetime.now().strftime('%d/%m/%Y à %H:%M')} | ⏱️ Durée du scan : {duree_formatee}\n"

        if len(nouveaux_dossiers) > 0:
            message += "\n<br>Nouveaux dossiers:\n"
            for dossier in nouveaux_dossiers:
                message += f"- {dossier['chemin']} (+{dossier['taille']} Mo)\n"

        if len(dossiers_modifies) > 0:
            message += "\n<br>Dossiers modifiés:\n"
            for dossier in dossiers_modifies:
                signe = "+" if dossier["difference"] > 0 else ""
                message += (
                    f"- {dossier['chemin']} ({signe}{dossier['difference']} Mo)\n"
                )

        if len(nouveaux_dossiers) == 0 and len(dossiers_modifies) == 0:
            message += "\n\nAucun dossier modifié ou nouveau"

        terminer_scan(connexion_mysql, id_scan, "termine")
        envoyer_notif_teams(message)

    except Exception as e:
        # En cas d'erreur, marquer le scan comme "erreur" et notifier
        envoyer_notif_teams(f"❌ Erreur critique durant le scan : {e}")
        if connexion_mysql and id_scan:
            terminer_scan(connexion_mysql, id_scan, "erreur")

    finally:
        # Toujours se déconnecter de la BDD, même en cas d'erreur
        if connexion_mysql:
            deconnecter_base_de_donnees(connexion_mysql)
