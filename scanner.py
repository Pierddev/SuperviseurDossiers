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
    enregistrer_totaux_scan,
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
        total_changement_taille = 0
        total_dossiers_scannes = 0
        taille_totale_racines_ko = 0

        for chemin_racine in chemins_racines:
            chemin_racine = chemin_racine.strip()
            if not chemin_racine:
                continue
            dossiers_avec_tailles = scanner_arborescence(chemin_racine, chemins_exclus)
            (
                nouveaux,
                modifies,
                taille_scan,
                changement_racine,
            ) = traiter_dossiers_en_lot(
                connexion_mysql, dossiers_avec_tailles, chemin_racine, id_scan
            )
            nouveaux_dossiers.extend(nouveaux)
            dossiers_modifies.extend(modifies)
            taille_totale_scan += taille_scan
            total_changement_taille += changement_racine
            total_dossiers_scannes += len(dossiers_avec_tailles)
            # Taille de la racine uniquement (inclut déjà ses enfants)
            taille_totale_racines_ko += round(
                dossiers_avec_tailles.get(chemin_racine, 0) / 1024
            )

        # Enregistrer les totaux corrects dans la table scans
        enregistrer_totaux_scan(
            connexion_mysql, id_scan, total_dossiers_scannes, taille_totale_racines_ko
        )

        # Filtre les dossiers parents redondants pour la notification
        nouveaux_dossiers = filtrer_dossiers_redondants(nouveaux_dossiers)
        dossiers_modifies = filtrer_dossiers_redondants(dossiers_modifies)

        # Convertir les totaux de Ko en Mo pour l'affichage dans la notification
        total_changement_mo = round(total_changement_taille / 1024)

        # Construction du message pour la notification Teams
        signe = "+" if total_changement_mo > 0 else ""
        message = "✅ **Scan terminé avec succès**"

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

        message += f"\n<br>📅 {datetime.now().strftime('%d/%m/%Y à %H:%M')} ⏱️ Durée du scan : {duree_formatee}"
        message += f"\n<br>📊 **Résumé** : {len(nouveaux_dossiers) + len(dossiers_modifies)} changements détectés (Total {signe}{total_changement_mo} Mo) \n"

        # Seuil pour la mise en évidence par poids (5 * SEUIL_DEFAUT)
        seuil_poids = int(os.getenv("SEUIL_DEFAUT", 100)) * 5

        if len(nouveaux_dossiers) > 0:
            message += "\n<br>🆕 **Nouveaux dossiers**:\n```"
            for dossier in nouveaux_dossiers:
                marqueur = "⚠️ " if dossier["taille"] > seuil_poids else "➖ "
                dossier["chemin"] = dossier["chemin"].replace("\\", " > ")
                message += (
                    f"\n{marqueur}(+ {dossier['taille']:>6} Mo)   {dossier['chemin']}"
                )
            message += "\n```"

        if len(dossiers_modifies) > 0:
            message += "\n<br>📝 **Dossiers modifiés**:\n```"
            for dossier in dossiers_modifies:
                diff = dossier["difference"]
                signe_mod = "+" if diff > 0 else "-"
                abs_diff = abs(diff)
                marqueur = "⚠️ " if abs_diff > seuil_poids else "➖ "
                dossier["chemin"] = dossier["chemin"].replace("\\", " > ")
                message += (
                    f"\n{marqueur}({signe_mod} {abs_diff:>6} Mo)   {dossier['chemin']}"
                )
            message += "\n```"

        if len(nouveaux_dossiers) == 0 and len(dossiers_modifies) == 0:
            message += "\n\nAucun dossier modifié ou nouveau"

        terminer_scan(connexion_mysql, id_scan, "completed")
        envoyer_notif_teams(message)

    except Exception as e:
        # En cas d'erreur, marquer le scan comme "failed" et notifier
        envoyer_notif_teams(f"❌ Erreur critique durant le scan : {e}")
        if connexion_mysql and id_scan:
            terminer_scan(connexion_mysql, id_scan, "failed")

    finally:
        # Toujours se déconnecter de la BDD, même en cas d'erreur
        if connexion_mysql:
            deconnecter_base_de_donnees(connexion_mysql)
