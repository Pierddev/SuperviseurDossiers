"""
Superviseur de Dossiers - Point d'entrée.
Script de surveillance de dossiers pour Windows Server.
"""

import argparse
import logging
import os
import sys
import threading
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
from plugin_loader import charger_plugins


def verifier_chemins_manquants(chemins_manquants: list[str]) -> None:
    """
    Vérifie si les chemins précédemment manquants sont maintenant disponibles.
    """
    if not chemins_manquants:
        return

    trouves = []
    for chemin in chemins_manquants[
        :
    ]:  # Copie pour pouvoir modifier la liste originale
        if os.path.exists(chemin):
            print(f"✨ Chemin re-détecté : `{chemin}`")
            trouves.append(chemin)
            chemins_manquants.remove(chemin)

    if trouves:
        message = (
            "✅ **Chemin(s) re-détecté(s)**<br>"
            "Les dossiers suivants sont à nouveau accessibles :<br>- "
            + "<br>- ".join(trouves)
        )
        envoyer_notif_teams(message)


if __name__ == "__main__":
    # Parse les arguments en ligne de commande
    parser = argparse.ArgumentParser(description="Superviseur de Dossiers")
    parser.add_argument(
        "--scan-now",
        action="store_true",
        help="Lance un scan immédiatement et quitte",
    )
    parser.add_argument(
        "--run-plugin",
        type=str,
        help="Lance un plugin spécifique immédiatement et quitte (ex: --run-plugin verif_auteur)",
        metavar="NOM_PLUGIN",
    )
    args = parser.parse_args()

    # --- Vérification globale des chemins racines (exécuté pour tous les modes) ---
    chemins_racines_env = os.getenv("CHEMINS_RACINES", "").split(",")
    statuts_chemins = []
    chemins_manquants = []
    print("=" * 60)
    print("📁 Vérification des chemins racines :")
    for chemin in chemins_racines_env:
        chemin = chemin.strip()
        if not chemin:
            continue

        existe = os.path.exists(chemin)
        statut = "✅ DÉTECTÉ" if existe else "❌ NON DÉTECTÉ"
        print(f"   - {chemin} : {statut}")
        statuts_chemins.append(f"{chemin} ({'OK' if existe else 'MANQUANT'})")

        if not existe:
            chemins_manquants.append(chemin)
    print("=" * 60)

    if args.scan_now:
        # Mode scan immédiat
        print("🔍 Superviseur de Dossiers - Scan manuel")
        scanner()
        print("✅ Scan terminé.")
    elif args.run_plugin:
        # Mode exécution de plugin manuel
        print(f"🔌 Exécution manuelle du plugin : {args.run_plugin}")
        plugins = charger_plugins(DOSSIER_APP)
        plugin_trouve = False
        for plugin in plugins:
            if plugin.__name__ == args.run_plugin:
                plugin_trouve = True
                if hasattr(plugin, "executer"):
                    plugin.executer()
                else:
                    print(
                        f"❌ Le plugin '{args.run_plugin}' ne possède pas de fonction 'executer()'."
                    )
                break

        if not plugin_trouve:
            print(f"❌ Plugin introuvable : {args.run_plugin}")
            print("Plugins disponibles :")
            for p in plugins:
                print(f" - {p.__name__}")
        print("✅ Terminé.")
    else:
        # Mode planifié (comportement par défaut)
        heure_scan = os.getenv("HEURE_SCAN", "17:30")
        schedule.every().day.at(heure_scan).do(scanner)

        delai_verification = int(os.getenv("DELAI_VERIFICATION", 300))

        print("🚀 Superviseur de Dossiers - Démarré")
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

        # Charge et planifie les plugins
        # (avec retry si le dossier plugins/ est temporairement inaccessible au démarrage du serveur)
        print("🔌 Chargement des plugins...")
        plugins = charger_plugins(DOSSIER_APP)

        # Retry si aucun plugin chargé (ex: partage réseau pas encore monté au boot)
        if not plugins:
            dossier_plugins = os.path.join(DOSSIER_APP, "plugins")
            fichiers_py = (
                [
                    f
                    for f in os.listdir(dossier_plugins)
                    if f.endswith(".py") and not f.startswith("__")
                ]
                if os.path.exists(dossier_plugins)
                else []
            )

            if fichiers_py:
                # Des fichiers .py existent mais n'ont pas pu être chargés → on réessaie
                MAX_RETRIES = 5
                DELAI_RETRY = 60  # secondes
                for tentative in range(1, MAX_RETRIES + 1):
                    print(
                        f"⚠️ Aucun plugin chargé alors que {len(fichiers_py)} fichier(s) existent. Nouvelle tentative {tentative}/{MAX_RETRIES} dans {DELAI_RETRY}s..."
                    )
                    time.sleep(DELAI_RETRY)
                    plugins = charger_plugins(DOSSIER_APP)
                    if plugins:
                        print(f"✅ Plugins chargés lors de la tentative {tentative}.")
                        break

        if plugins:
            print(f"✅ {len(plugins)} plugin(s) chargé(s) :")
            for plugin in plugins:
                plugin.afficher_statut()
                plugin.planifier(schedule)
        else:
            print("ℹ️ Aucun plugin chargé.")
        print("-" * 60)

        # Démarrage conditionnel de l'Intranet (interface web)
        intranet_enabled = os.getenv("INTRANET_ENABLED", "0") == "1"
        statut_intranet = "❌ Désactivé"
        if intranet_enabled:
            try:
                from intranet.app import creer_app

                intra_port = int(os.getenv("INTRA_PORT", 5000))
                app = creer_app()

                # Gestion du mode Debug / Hot-Reload
                debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"
                
                if debug_mode:
                    # En mode debug, Flask doit tourner sur le thread principal pour le reloader
                    # On lance donc l'ordonnanceur de scan dans un thread séparé
                    def lancer_ordonnanceur():
                        print("⏱️  Ordonnanceur de scan démarré en arrière-plan")
                        while True:
                            schedule.run_pending()
                            time.sleep(delai_verification)
                            
                    thread_scan = threading.Thread(target=lancer_ordonnanceur, daemon=True)
                    thread_scan.start()
                    
                    # On lance Flask en bloquant (avec reloader actif)
                    # Note : Cela ne s'exécutera que si INTRANET_ENABLED=1
                    statut_intranet = f"✅ Actif (RELOAD) sur le port {intra_port}"
                    print(f"🌐 Intranet démarré sur http://0.0.0.0:{intra_port} (Auto-reload actif)")
                    app.run(host="0.0.0.0", port=intra_port, debug=True)
                    # Le code s'arrête ici tant que Flask tourne
                else:
                    # Mode production / normal : Flask en arrière-plan
                    thread_intranet = threading.Thread(
                        target=app.run,
                        kwargs={"host": "0.0.0.0", "port": intra_port, "debug": False},
                        daemon=True,
                    )
                    thread_intranet.start()
                    statut_intranet = f"✅ Actif sur le port {intra_port}"
                    print(f"🌐 Intranet démarré sur http://0.0.0.0:{intra_port}")
            except Exception as e:
                statut_intranet = f"❌ Erreur ({e})"
                print(f"❌ Erreur lors du démarrage de l'Intranet : {e}")

        # Planifie la vérification périodique des chemins manquants si nécessaire
        if chemins_manquants:
            schedule.every(10).minutes.do(verifier_chemins_manquants, chemins_manquants)
            print(
                f"ℹ️ {len(chemins_manquants)} chemin(s) manquant(s) seront re-vérifiés toutes les 10 minutes."
            )

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
        statut_bdd_emoji = "✅ OK" if "OK" in statut_bdd else "❌ ÉCHEC"

        # Prépare le statut des plugins pour la notification
        if plugins:
            statut_plugins = f"✅ {len(plugins)} chargé(s) : " + ", ".join(
                getattr(p, "__name__", str(p)) for p in plugins
            )
        else:
            dossier_plugins = os.path.join(DOSSIER_APP, "plugins")
            fichiers_py = (
                [
                    f
                    for f in os.listdir(dossier_plugins)
                    if f.endswith(".py") and not f.startswith("__")
                ]
                if os.path.exists(dossier_plugins)
                else []
            )
            if fichiers_py:
                statut_plugins = f"❌ ÉCHEC ({len(fichiers_py)} fichier(s) présent(s) mais non chargés)"
            else:
                statut_plugins = "ℹ️ Aucun plugin"

        message_demarrage = (
            f"🚀 **Superviseur de Dossiers - Démarré**<br><br>"
            f"📅 **Date** : {datetime.now().strftime('%d/%m/%Y à %H:%M')}<br>"
            f"⏱️ **Prochain scan** : {heure_scan}<br>"
            f"🗄️ **Base de données** : {statut_bdd_emoji}<br>"
            f"🔌 **Plugins** : {statut_plugins}<br>"
            f"🌐 **Intranet** : {statut_intranet}<br><br>"
            f"📁 **État des chemins racines** :<br>"
        )

        for p_statut in statuts_chemins:
            emoji_path = "✅" if "(OK)" in p_statut else "❌"
            path_name = p_statut.split(" (")[0]
            message_demarrage += f"- `{path_name}` : {emoji_path}<br>"

        envoyer_notif_teams(message_demarrage)

        print("-" * 60)
        print("ℹ️ NOTE : Si vous avez configuré la tâche planifiée Windows,")
        print("ce script démarrera automatiquement en arrière-plan")
        print("à chaque redémarrage du serveur (sans fenêtre visible).")
        print("=" * 60)
        print("Le programme est en cours d'execution... Ne fermez pas cette fenetre")

        # Boucle infinie pour que le programme continue de tourner
        # (Seulement si non-bloqué par Flask Debug au-dessus)
        if os.getenv("FLASK_DEBUG", "0") != "1":
            while True:
                schedule.run_pending()
                time.sleep(delai_verification)
