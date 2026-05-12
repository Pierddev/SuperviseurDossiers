"""
Superviseur de Dossiers - Point d'entrée.
Script de surveillance de dossiers pour Windows Server.
"""

import argparse
import logging
import os
import signal
import sys
import threading
import time
from datetime import datetime

import dotenv
import schedule

from version import __version__

# Imports des modules locaux
from db import (
    connecter_base_de_donnees,
    deconnecter_base_de_donnees,
    parser_seuils_personnalises,
)
from notifications import envoyer_notif_teams
from scanner import scanner
from plugin_loader import charger_plugins, get_registre

# Détermine le dossier où se trouve l'exécutable (ou le script)
if getattr(sys, "frozen", False):
    DOSSIER_APP = os.path.dirname(sys.executable)
else:
    DOSSIER_APP = os.path.dirname(os.path.abspath(__file__))

dotenv.load_dotenv(os.path.join(DOSSIER_APP, ".env"))

# Configure le logging pour écrire UNIQUEMENT les erreurs dans un fichier log
logging.basicConfig(
    filename=os.path.join(DOSSIER_APP, "superviseur.log"),
    level=logging.ERROR,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True,
)

# Désactive les logs d'information des bibliothèques tierces
logging.getLogger("werkzeug").setLevel(logging.ERROR)
logging.getLogger("flask").setLevel(logging.ERROR)
logging.getLogger("livereload").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("mysql.connector").setLevel(logging.ERROR)


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

    arret_demande = False

    def _handler_arret(signum, frame):
        """Signal handler pour SIGINT et SIGBREAK."""
        global arret_demande
        arret_demande = True
        print("\n⏳ Arrêt demandé, fin de la boucle en cours...")

    signal.signal(signal.SIGINT, _handler_arret)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _handler_arret)

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

    # Nettoyage des scans orphelins laissés par un arrêt brutal précédent
    try:
        _conn = connecter_base_de_donnees()
        if _conn:
            _cur = _conn.cursor()
            _cur.execute(
                "UPDATE scans SET status = 'interrupted', date_end = NOW() "
                "WHERE status = 'in_progress'"
            )
            _conn.commit()
            _cur.close()
            deconnecter_base_de_donnees(_conn)
    except Exception:
        pass

    try:
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

        def scanner_en_thread():
            """Lance le scan dans un thread daemon pour ne pas bloquer la boucle principale."""
            threading.Thread(target=scanner, daemon=True, name="scan-quotidien").start()

        # Planification du scan (dans un thread pour ne pas bloquer run_pending)
        schedule.every().day.at(heure_scan).do(scanner_en_thread).tag("daily_scan")

        delai_verification = int(os.getenv("DELAI_VERIFICATION", 300))

        print(f"🚀 Superviseur de Dossiers v{__version__} - Démarré")
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
        plugins_attendus = len(fichiers_py)

        print("🔌 Chargement des plugins...")
        plugins = charger_plugins(DOSSIER_APP)

        # Retry si des plugins sont en erreur (ex: partage réseau pas encore monté au boot)
        if len(plugins) < plugins_attendus:
            MAX_RETRIES = 5
            DELAI_RETRY = 60  # secondes
            for tentative in range(1, MAX_RETRIES + 1):
                print(
                    f"⚠️ {plugins_attendus - len(plugins)} plugin(s) non chargé(s) sur {plugins_attendus}. "
                    f"Nouvelle tentative {tentative}/{MAX_RETRIES} dans {DELAI_RETRY}s..."
                )
                time.sleep(DELAI_RETRY)
                plugins = charger_plugins(DOSSIER_APP)
                if len(plugins) == plugins_attendus:
                    print(
                        f"✅ Tous les plugins chargés lors de la tentative {tentative}."
                    )
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
        debug_mode = False  # Sera mis à True si le mode debug/livereload est activé
        statut_intranet = "❌ Désactivé"
        if intranet_enabled:
            try:
                from intranet.app import creer_app

                intra_port = int(os.getenv("INTRA_PORT", 5000))
                app = creer_app()

                # Gestion du mode Debug / Hot-Reload
                debug_mode = os.getenv("FLASK_DEBUG", "0") == "1"

                # Désactive le debug_mode (et donc livereload) si on est dans un EXE (Frozen)
                if getattr(sys, "frozen", False):
                    debug_mode = False

                if debug_mode:
                    # En mode debug, on utilise livereload pour rafraîchir le navigateur automatiquement
                    # lors des modifications de CSS (style inline dans les templates) ou de fichiers statiques.
                    from livereload import Server  # type: ignore[import-untyped]

                    # Dict mutable partagé par référence — évite nonlocal dans les fonctions imbriquées
                    _etat = {
                        "heure_scan": heure_scan,
                        "delai_verification": delai_verification,
                    }

                    # On lance l'ordonnanceur dans un thread séparé (uniquement dans le processus principal de livereload)
                    def executer_ordonnanceur():
                        """Boucle de l'ordonnanceur avec support du rechargement dynamique."""
                        print("⏱️  Ordonnanceur de scan démarré en arrière-plan")
                        env_path_ord = os.path.join(DOSSIER_APP, ".env")

                        while True:
                            schedule.run_pending()

                            try:
                                # Relit le .env à chaque itération
                                dotenv.load_dotenv(env_path_ord, override=True)
                                h_env = os.getenv("HEURE_SCAN", "17:30")
                                d_env = int(os.getenv("DELAI_VERIFICATION", 300))

                                # Mise à jour de l'heure de scan si modifiée
                                if h_env != _etat["heure_scan"]:
                                    print(
                                        f"⏰ Heure de scan modifiée : "
                                        f"{_etat['heure_scan']} → {h_env}"
                                    )
                                    schedule.clear("daily_scan")
                                    schedule.every().day.at(h_env).do(scanner_en_thread).tag("daily_scan")
                                    _etat["heure_scan"] = h_env

                                    # Cas critique : heure déjà passée
                                    h_part, m_part = h_env.split(":")
                                    maintenant = datetime.now()
                                    heure_cible = maintenant.replace(
                                        hour=int(h_part), minute=int(m_part),
                                        second=0, microsecond=0
                                    )
                                    if maintenant >= heure_cible:
                                        print(
                                            f"⏳ {h_env} déjà passé "
                                            f"— lancement du scan immédiat..."
                                        )
                                        scanner_en_thread()

                                # Mise à jour du délai de vérification
                                if d_env != _etat["delai_verification"]:
                                    print(
                                        f"⏱️ Délai mis à jour : "
                                        f"{_etat['delai_verification']}s → {d_env}s"
                                    )
                                    _etat["delai_verification"] = d_env

                            except Exception as e:
                                print(f"⚠️ Erreur rechargement config : {e}")

                            time.sleep(_etat["delai_verification"])

                    thread_scan = threading.Thread(
                        target=executer_ordonnanceur, daemon=True
                    )
                    thread_scan.start()

                    server = Server(app.wsgi_app)

                    # Surveiller les templates et les fichiers statiques
                    server.watch(os.path.join(DOSSIER_APP, "intranet", "templates"))
                    server.watch(os.path.join(DOSSIER_APP, "intranet", "static"))

                    statut_intranet = f"✅ Actif (LIVE RELOAD) sur le port {intra_port}"
                    print(
                        f"🌐 Intranet démarré sur http://0.0.0.0:{intra_port} (Live Reload actif)"
                    )

                    # Server.serve bloque l'exécution
                    server.serve(port=intra_port, host="0.0.0.0")
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

        # Vérifie la connexion BDD + envoie la notification de démarrage dans un thread
        # pour ne pas bloquer la boucle principale (le scheduler doit démarrer immédiatement)
        def _notif_demarrage():
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

            statut_bdd_emoji = "✅ OK" if "OK" in statut_bdd else "❌ ÉCHEC"

            # Prépare le statut des plugins pour la notification
            registre_plugins = get_registre()
            plugins_actifs = [n for n, info in registre_plugins.items() if info["actif"]]
            plugins_en_erreur = [
                n
                for n, info in registre_plugins.items()
                if not info["actif"] and info["erreur"]
            ]

            if plugins_actifs:
                statut_plugins = f"✅ {len(plugins_actifs)} chargé(s) : " + ", ".join(
                    plugins_actifs
                )
                if plugins_en_erreur:
                    statut_plugins += (
                        f"<br>⚠️ {len(plugins_en_erreur)} en erreur : "
                        + ", ".join(plugins_en_erreur)
                    )
            else:
                dossier_plugins_notif = os.path.join(DOSSIER_APP, "plugins")
                fichiers_py_notif = (
                    [
                        f
                        for f in os.listdir(dossier_plugins_notif)
                        if f.endswith(".py") and not f.startswith("__")
                    ]
                    if os.path.exists(dossier_plugins_notif)
                    else []
                )
                if fichiers_py_notif:
                    statut_plugins = f"❌ ÉCHEC ({len(fichiers_py_notif)} fichier(s) présent(s) mais non chargés)"
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

        threading.Thread(target=_notif_demarrage, daemon=True).start()

        print("-" * 60)
        print("ℹ️ NOTE : Si vous avez configuré la tâche planifiée Windows,")
        print("ce script démarrera automatiquement en arrière-plan")
        print("à chaque redémarrage du serveur (sans fenêtre visible).")
        print("=" * 60)
        print("Le programme est en cours d'execution... Ne fermez pas cette fenetre")


        # Boucle infinie pour que le programme continue de tourner
        # En mode debug, le scheduler tourne déjà dans un thread séparé (executer_ordonnanceur)
        # donc on ne lance pas la boucle ici pour éviter un double scan.
        if not debug_mode:
            env_path = os.path.join(DOSSIER_APP, ".env")
            while not arret_demande:
                schedule.run_pending()

                try:
                    dotenv.load_dotenv(env_path, override=True)
                    h_env = os.getenv("HEURE_SCAN", "17:30")
                    d_env = int(os.getenv("DELAI_VERIFICATION", 300))

                    if h_env != heure_scan:
                        print(f"⏰ Heure de scan modifiée : {heure_scan} → {h_env}")
                        schedule.clear("daily_scan")
                        schedule.every().day.at(h_env).do(scanner_en_thread).tag("daily_scan")
                        heure_scan = h_env

                        h_part, m_part = h_env.split(":")
                        maintenant = datetime.now()
                        heure_cible = maintenant.replace(
                            hour=int(h_part), minute=int(m_part),
                            second=0, microsecond=0
                        )
                        if maintenant >= heure_cible:
                            print(
                                f"⏳ {h_env} déjà passé — lancement du scan immédiat..."
                            )
                            scanner_en_thread()

                    if d_env != delai_verification:
                        print(
                            f"⏱️ Délai mis à jour : {delai_verification}s → {d_env}s"
                        )
                        delai_verification = d_env

                except Exception as e:
                    print(f"⚠️ Erreur rechargement config : {e}")

                time.sleep(delai_verification)

    except KeyboardInterrupt:
        print("\n⏳ Arrêt demandé...")
    finally:
        # Nettoyage des scans laissés en in_progress
        try:
            _conn = connecter_base_de_donnees()
            if _conn:
                _cur = _conn.cursor()
                _cur.execute(
                    "UPDATE scans SET status = 'interrupted', date_end = NOW() "
                    "WHERE status = 'in_progress'"
                )
                _conn.commit()
                _cur.close()
                deconnecter_base_de_donnees(_conn)
        except Exception:
            pass
