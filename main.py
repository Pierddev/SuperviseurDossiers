import argparse
import logging
import os
import sys
import requests
import json
import time
import mysql.connector
import dotenv
import schedule
from datetime import datetime

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
logger = logging.getLogger(__name__)


def connecter_base_de_donnees() -> mysql.connector.MySQLConnection | None:
    """
    Connecte à la base de données.
    """
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
        )
    except mysql.connector.Error as err:
        # Envoie une notification à Microsoft Teams si la connexion à la base de données échoue
        envoyer_notif_teams(f"Erreur de connexion à la base de données : {err}")
        return None


def deconnecter_base_de_donnees(
    connexion: mysql.connector.MySQLConnection,
) -> None:
    """
    Déconnecte de la base de données.
    """
    connexion.close()


def envoyer_notif_teams(message: str) -> None:
    """
    Envoie une notification à Microsoft Teams.
    """
    try:
        url = os.getenv("TEAMS_WEBHOOK_URL")
        headers = {"Content-Type": "application/json"}
        payload = {"text": message}
        response = requests.post(
            url, headers=headers, data=json.dumps(payload), timeout=10
        )
        # Lève une HTTPError si le code de retour est 4xx ou 5xx
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de l'envoi de la notification : {e}")


def calculer_taille_dossier(chemin_dossier: str) -> int:
    """
    Calcule la taille totale d'un dossier en incluant tous les sous-dossiers et fichiers.
    """
    taille_totale = 0
    # os.walk() parcourt tous les dossiers et fichiers de manière itérative
    for dossier, sous_dossiers, fichiers in os.walk(chemin_dossier, followlinks=False):
        for fichier in fichiers:
            try:
                # Ajoute la taille du fichier à la taille totale
                taille_totale += os.path.getsize(os.path.join(dossier, fichier))
            except (OSError, PermissionError):
                # Ignore les erreurs d'accès
                pass
    return taille_totale


def est_chemin_exclu(chemin: str, chemins_exclus: list[str]) -> bool:
    """
    Vérifie si un chemin doit être exclu du scan.
    Retourne True si le chemin commence par l'un des chemins exclus.
    La comparaison est insensible à la casse (Windows).
    """
    chemin_normalise = os.path.normcase(os.path.normpath(chemin))
    for chemin_exclu in chemins_exclus:
        exclu_normalise = os.path.normcase(os.path.normpath(chemin_exclu))
        if chemin_normalise == exclu_normalise or chemin_normalise.startswith(
            exclu_normalise + os.sep
        ):
            return True
    return False


def lister_tous_les_dossier(
    chemin_racine: str, chemins_exclus: list[str] = None
) -> list[str]:
    """
    Liste tous les dossiers à partir d'un chemin racine.
    Si chemins_exclus est fourni, les dossiers correspondants et leurs
    sous-dossiers sont ignorés.
    """
    liste_des_dossiers = [chemin_racine]
    for dossier, sous_dossiers, fichiers in os.walk(chemin_racine, followlinks=False):
        if chemins_exclus:
            # Filtre en place pour empêcher os.walk de descendre dans les dossiers exclus
            sous_dossiers[:] = [
                sd
                for sd in sous_dossiers
                if not est_chemin_exclu(os.path.join(dossier, sd), chemins_exclus)
            ]
        for sous_dossier in sous_dossiers:
            # Ajoute le chemin complet du sous-dossier à la liste
            liste_des_dossiers.append(os.path.join(dossier, sous_dossier))
    return liste_des_dossiers


def scanner_arborescence(
    chemin_racine: str, chemins_exclus: list[str] = None
) -> dict[str, int]:
    """
    Parcourt l'arborescence en un seul pass (bottom-up) et retourne un dictionnaire
    {chemin_dossier: taille_en_octets} incluant les sous-dossiers.
    """
    tailles = {}

    for dossier, sous_dossiers, fichiers in os.walk(
        chemin_racine, topdown=False, followlinks=False
    ):
        # Vérifie si le dossier est exclu
        if chemins_exclus and est_chemin_exclu(dossier, chemins_exclus):
            continue

        # Calcule la taille des fichiers directs du dossier
        taille_fichiers = 0
        for fichier in fichiers:
            try:
                taille_fichiers += os.path.getsize(os.path.join(dossier, fichier))
            except (OSError, PermissionError):
                pass

        # Ajoute la taille des sous-dossiers (déjà calculés car topdown=False)
        taille_sous_dossiers = sum(
            tailles.get(os.path.join(dossier, sd), 0) for sd in sous_dossiers
        )

        tailles[dossier] = taille_fichiers + taille_sous_dossiers

    return tailles


def creer_scan(connexion_mysql: mysql.connector.MySQLConnection) -> int | None:
    """
    Crée un nouveau scan dans la table sudo_scans avec le statut 'en_cours'.
    Retourne l'id_scan créé.
    """
    try:
        # Crée un curseur pour exécuter des commandes SQL
        curseur = connexion_mysql.cursor()
        curseur.execute(
            "INSERT INTO sudo_scans (scan_date, scan_statut) VALUES (NOW(), 'en_cours')"
        )
        connexion_mysql.commit()
        # Récupère l'id du dernier enregistrement inséré
        id_scan = curseur.lastrowid
        curseur.close()
        return id_scan
    except mysql.connector.Error as err:
        envoyer_notif_teams(f"Erreur lors de la création du scan : {err}")
        return None


def terminer_scan(
    connexion_mysql: mysql.connector.MySQLConnection, id_scan: int, statut: str
) -> None:
    """
    Termine un scan en mettant à jour son statut dans la table sudo_scans.
    """
    try:
        # Crée un curseur pour exécuter des commandes SQL
        curseur = connexion_mysql.cursor()
        curseur.execute(
            "UPDATE sudo_scans SET scan_statut = %s WHERE id_scan = %s",
            (statut, id_scan),
        )
        connexion_mysql.commit()
        curseur.close()
    except mysql.connector.Error as err:
        envoyer_notif_teams(f"Erreur lors de la terminaison du scan : {err}")


def inserer_ou_mettre_a_jour_dossier(
    connexion_mysql: mysql.connector.MySQLConnection,
    chemin_dossier: str,
    taille_dossier: int,
) -> dict[str, str] | None:
    """
    Insère ou met à jour un dossier dans la table sudo_dossiers.
    Retourne un dictionnaire avec les informations du dossier la modification de sa taille est supérieure à la taille définie dans le fichier .env.
    """
    dictionnaire_de_retour = None
    try:
        # Crée un curseur pour exécuter des commandes SQL
        curseur = connexion_mysql.cursor()
        # Vérifie si le dossier existe déjà
        curseur.execute(
            "SELECT * FROM sudo_dossiers WHERE dossier_chemin = %s", (chemin_dossier,)
        )
        resultat_dossier = curseur.fetchone()

        # Gestion des nouveaux dossiers
        if resultat_dossier is None:
            # Insère le dossier
            curseur.execute(
                "INSERT INTO sudo_dossiers (dossier_chemin, dossier_est_nouveau) VALUES (%s, %s)",
                (chemin_dossier, 1),
            )
            id_dossier = curseur.lastrowid
            curseur.execute(
                "INSERT INTO sudo_tailles (id_dossier, taille_actuel_scan) VALUES (%s, %s)",
                (id_dossier, taille_dossier),
            )

            if taille_dossier > int(os.getenv("MODIFICATION_TAILLE_IMPORTANTE")):
                # Retourne le dictionnaire avec les informations du nouveau dossier pour l'insérer dans la notification Teams
                dictionnaire_de_retour = {
                    "type": "nouveau",
                    "chemin": chemin_dossier,
                    "taille": taille_dossier,
                }
        else:
            id_dossier = resultat_dossier[0]
            # Marquer comme non nouveau
            if resultat_dossier[2] == 1:
                curseur.execute(
                    "UPDATE sudo_dossiers SET dossier_est_nouveau = 0 WHERE id_dossier = %s",
                    (id_dossier,),
                )

            # Récupérer les tailles actuelles nécessaire pour calculer la différence
            curseur.execute(
                "SELECT * FROM sudo_tailles WHERE id_dossier = %s",
                (id_dossier,),
            )
            resultat_tailles = curseur.fetchone()
            taille_actuel_scan = resultat_tailles[1]

            # Décaler les tailles en une seule requête
            curseur.execute(
                "UPDATE sudo_tailles SET taille_dernier_scan = taille_actuel_scan, taille_actuel_scan = %s WHERE id_dossier = %s",
                (taille_dossier, id_dossier),
            )

            difference_taille_dossier = abs(
                int(taille_actuel_scan) - int(taille_dossier)
            )

            if difference_taille_dossier > int(
                os.getenv("MODIFICATION_TAILLE_IMPORTANTE")
            ):
                # Retourne le dictionnaire si la taille de la modification est supérieure à la taille définie dans le fichier .env
                dictionnaire_de_retour = {
                    "type": "modification",
                    "chemin": chemin_dossier,
                    "difference": int(taille_dossier) - int(taille_actuel_scan),
                }

        connexion_mysql.commit()
        curseur.close()

        if dictionnaire_de_retour:
            return dictionnaire_de_retour
        else:
            return None
    except mysql.connector.Error as err:
        envoyer_notif_teams(
            f"Erreur lors de l'insertion ou de la mise à jour du dossier : {err}"
        )


def traiter_dossiers_en_lot(
    connexion_mysql: mysql.connector.MySQLConnection,
    dossiers_avec_tailles: dict[str, int],
) -> tuple[list, list, int]:
    """
    Traite tous les dossiers en lot pour optimiser les accès BDD.
    Charge tous les dossiers existants en mémoire (1 seul SELECT),
    puis fait les INSERT/UPDATE avec un commit tous les 5000 dossiers.
    Retourne (nouveaux_dossiers, dossiers_modifies, taille_totale_scan).
    """
    seuil = int(os.getenv("MODIFICATION_TAILLE_IMPORTANTE"))
    curseur = connexion_mysql.cursor()

    # Charge TOUS les dossiers existants en mémoire (1 seule requête)
    curseur.execute(
        "SELECT d.id_dossier, d.dossier_chemin, d.dossier_est_nouveau, "
        "t.taille_actuel_scan FROM sudo_dossiers d "
        "LEFT JOIN sudo_tailles t ON d.id_dossier = t.id_dossier"
    )
    dossiers_existants = {
        row[1]: {"id": row[0], "est_nouveau": row[2], "taille": row[3]}
        for row in curseur.fetchall()
    }

    nouveaux_dossiers = []
    dossiers_modifies = []
    taille_totale_scan = 0
    compteur = 0

    for chemin, taille_octets in dossiers_avec_tailles.items():
        taille_en_mo = round(taille_octets / (1024**2))
        taille_totale_scan += taille_en_mo

        if chemin in dossiers_existants:
            # Dossier existant → UPDATE
            info = dossiers_existants[chemin]
            id_dossier = info["id"]
            taille_precedente = info["taille"] or 0

            if info["est_nouveau"] == 1:
                curseur.execute(
                    "UPDATE sudo_dossiers SET dossier_est_nouveau = 0 WHERE id_dossier = %s",
                    (id_dossier,),
                )

            curseur.execute(
                "UPDATE sudo_tailles SET taille_dernier_scan = taille_actuel_scan, "
                "taille_actuel_scan = %s WHERE id_dossier = %s",
                (taille_en_mo, id_dossier),
            )

            difference = abs(int(taille_precedente) - taille_en_mo)
            if difference > seuil:
                dossiers_modifies.append(
                    {
                        "type": "modification",
                        "chemin": chemin,
                        "difference": taille_en_mo - int(taille_precedente),
                    }
                )
        else:
            # Nouveau dossier → INSERT
            curseur.execute(
                "INSERT INTO sudo_dossiers (dossier_chemin, dossier_est_nouveau) VALUES (%s, 1)",
                (chemin,),
            )
            id_dossier = curseur.lastrowid
            curseur.execute(
                "INSERT INTO sudo_tailles (id_dossier, taille_actuel_scan) VALUES (%s, %s)",
                (id_dossier, taille_en_mo),
            )

            if taille_en_mo > seuil:
                nouveaux_dossiers.append(
                    {
                        "type": "nouveau",
                        "chemin": chemin,
                        "taille": taille_en_mo,
                    }
                )

        compteur += 1
        if compteur % 5000 == 0:
            connexion_mysql.commit()

    connexion_mysql.commit()
    curseur.close()
    return nouveaux_dossiers, dossiers_modifies, taille_totale_scan


def filtrer_dossiers_redondants(dossiers: list[dict]) -> list[dict]:
    """
    Filtre les dossiers parents redondants dans la liste de notification.
    Un dossier est redondant s'il est un parent d'un autre dossier dans la liste.
    Seuls les dossiers les plus profonds (feuilles) sont conservés.
    """
    chemins = [os.path.normcase(os.path.normpath(d["chemin"])) for d in dossiers]
    resultat = []
    for i, dossier in enumerate(dossiers):
        chemin = chemins[i]
        # Vérifie si un autre dossier de la liste est un enfant de celui-ci
        est_parent = any(
            autre.startswith(chemin + os.sep)
            for j, autre in enumerate(chemins)
            if j != i
        )
        if not est_parent:
            resultat.append(dossier)
    return resultat


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
        message = f"Scan du {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n"

        if len(nouveaux_dossiers) > 0:
            message += "\nNouveaux dossiers:\n"
            for dossier in nouveaux_dossiers:
                message += f"- {dossier['chemin']} (+{dossier['taille']} Mo)\n"

        if len(dossiers_modifies) > 0:
            message += "\nDossiers modifiés:\n"
            for dossier in dossiers_modifies:
                signe = "+" if dossier["difference"] > 0 else ""
                message += (
                    f"- {dossier['chemin']} ({signe}{dossier['difference']} Mo)\n"
                )

        message += "\n<br><br>Scan terminé avec succès"

        if len(nouveaux_dossiers) == 0 and len(dossiers_modifies) == 0:
            message += "\n\nAucun dossier modifié ou nouveau"

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
        message += f"<br>⏱️ Durée du scan : {duree_formatee}"

        terminer_scan(connexion_mysql, id_scan, "termine")
        envoyer_notif_teams(message)

    except Exception as e:
        # En cas d'erreur, marquer le scan comme "erreur" et notifier
        envoyer_notif_teams(f"Erreur critique durant le scan : {e}")
        if connexion_mysql and id_scan:
            terminer_scan(connexion_mysql, id_scan, "erreur")

    finally:
        # Toujours se déconnecter de la BDD, même en cas d'erreur
        if connexion_mysql:
            deconnecter_base_de_donnees(connexion_mysql)


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
