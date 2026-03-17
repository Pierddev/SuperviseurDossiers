"""
Superviseur de Dossiers - Point d'entrée.
Script de surveillance de dossiers pour Windows Server.
"""

import argparse
import logging
import os
import sys
import time
from datetime import datetime

import dotenv
import schedule

# Détermine le dossier où se trouve l'exécutable (ou le script)
if getattr(sys, "frozen", False):
    DOSSIER_APP = os.path.dirname(sys.executable)
else:
    DOSSIER_APP = os.path.dirname(os.path.abspath(__file__))

dotenv.load_dotenv(os.path.join(DOSSIER_APP, ".env"))

# Configure le logging pour écrire les erreurs dans un fichier log
# (essentiellement lorsque les notifications Teams échouent)
logging.basicConfig(
    filename=os.path.join(DOSSIER_APP, "superviseur.log"),
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

from db import (
    connecter_base_de_donnees,
    deconnecter_base_de_donnees,
    parser_seuils_personnalises,
)
from notifications import envoyer_notif_teams
from scanner import scanner


if __name__ == "__main__":
    # Parse les arguments en ligne de commande
    parser = argparse.ArgumentParser(description="Superviseur de Dossiers")
    parser.add_argument(
        "--scan-now",
        action="store_true",
        help="Lance un scan immédiatement et quitte",
    )
    args = parser.parse_args()

    if args.scan_now:
        # Mode scan immédiat
        print("=" * 60)
        print("🔍 Superviseur de Dossiers - Scan manuel")
        print("=" * 60)
        scanner()
        print("✅ Scan terminé.")
    else:
        # Mode planifié (comportement par défaut)
        heure_scan = os.getenv("HEURE_SCAN", "17:30")
        schedule.every().day.at(heure_scan).do(scanner)

        delai_verification = int(os.getenv("DELAI_VERIFICATION", 300))

        print("=" * 60)
        print("🚀 Superviseur de Dossiers - Démarré")
        print("=" * 60)
        print(f"📅 Prochain scan prévu à : {heure_scan}")
        print(f"⏱️ Vérification toutes les : {delai_verification} secondes")

        # Affiche les chemins exclus
        chemins_exclus = [
            c.strip() for c in os.getenv("CHEMINS_EXCLUS", "").split(",") if c.strip()
        ]
        if chemins_exclus:
            print(f"🚫 Chemins exclus : {', '.join(chemins_exclus)}")
        else:
            print("🚫 Aucun chemin exclu")

        # Affiche les seuils personnalisés
        seuil_defaut = os.getenv("SEUIL_DEFAUT", "100")
        print(f"📏 Seuil de notification par défaut : {seuil_defaut} Mo")
        seuils = parser_seuils_personnalises()
        if seuils:
            print("📏 Seuils personnalisés :")
            for chemin_seuil, valeur_seuil in seuils.items():
                print(f"   - {chemin_seuil} : {valeur_seuil} Mo")

        print("-" * 60)

        # Vérifie la connexion à la base de données au démarrage
        statut_bdd = "OK"
        try:
            test_connexion = connecter_base_de_donnees()
            if test_connexion:
                print("✅ Connexion à la base de données : OK")
                deconnecter_base_de_donnees(test_connexion)
            else:
                statut_bdd = "ÉCHEC"
                print("❌ Connexion à la base de données : ÉCHEC")
        except Exception as e:
            statut_bdd = f"ÉCHEC ({e})"
            print(f"❌ Connexion à la base de données : {statut_bdd}")

        # Envoie une notification Teams pour confirmer le démarrage du script
        message_demarrage = (
            f"Superviseur de Dossiers - Démarré<br>"
            f"Date : {datetime.now().strftime('%d/%m/%Y à %H:%M')}<br>"
            f"Prochain scan prévu à : {heure_scan}<br>"
            f"Base de données : {statut_bdd}"
        )
        envoyer_notif_teams(message_demarrage)

        print("-" * 60)
        print("ℹ️ NOTE : Si vous avez configuré la tâche planifiée Windows,")
        print("ce script démarrera automatiquement en arrière-plan")
        print("à chaque redémarrage du serveur (sans fenêtre visible).")
        print("=" * 60)
        print("Le programme est en cours d'execution... Ne fermez pas cette fenetre")

        # Boucle infinie pour que le programme continue de tourner
        while True:
            schedule.run_pending()
            time.sleep(delai_verification)
