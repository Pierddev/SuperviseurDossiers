import mysql.connector.cursor_cext
import logging
import os
import requests
import json
import mysql.connector
import dotenv
from datetime import datetime

dotenv.load_dotenv()

# Configure le logging pour écrire les erreurs dans un fichier log
# (essentiellement lorsque les notifications Teams échouent)
logging.basicConfig(
    filename="superviseur.log",
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


def lister_tous_les_dossier(chemin_racine: str) -> list[str]:
    """
    Liste tous les dossiers à partir d'un chemin racine.
    """
    liste_des_dossiers = [chemin_racine]
    for dossier, sous_dossiers, fichiers in os.walk(chemin_racine, followlinks=False):
        for sous_dossier in sous_dossiers:
            # Ajoute le chemin complet du sous-dossier à la liste
            liste_des_dossiers.append(os.path.join(dossier, sous_dossier))
    return liste_des_dossiers


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


def scanner() -> None:
    """
    Scanne tous les dossiers à partir d'un chemin racine.
    """
    connexion_mysql = connecter_base_de_donnees()
    id_scan = creer_scan(connexion_mysql)
    liste_dossiers = lister_tous_les_dossier(os.getenv("CHEMIN_RACINE"))

    nouveaux_dossiers = []
    dossiers_modifies = []

    for dossier in liste_dossiers:
        taille_dossier = calculer_taille_dossier(dossier)
        taille_en_mo = round(
            taille_dossier / (1024**2), 2
        )  # Convertit en Mo avec 2 décimales
        resultat = inserer_ou_mettre_a_jour_dossier(
            connexion_mysql, dossier, taille_en_mo
        )

        if resultat:
            if resultat["type"] == "nouveau":
                nouveaux_dossiers.append(resultat)
            elif resultat["type"] == "modification":
                dossiers_modifies.append(resultat)

    # Construction du message pour la notification Teams
    message = f"Scan du {datetime.now().strftime('%d/%m/%Y à %H:%M')}:\n\n"

    if len(nouveaux_dossiers) > 0:
        message += "\nNouveaux dossiers:\n"
        for dossier in nouveaux_dossiers:
            message += f"- {dossier['chemin']} (+{dossier['taille']} Mo)\n"

    if len(dossiers_modifies) > 0:
        message += "\nDossiers modifiés:\n"
        for dossier in dossiers_modifies:
            signe = "+" if dossier["difference"] > 0 else ""
            message += f"- {dossier['chemin']} ({signe}{dossier['difference']} Mo)\n"

    message += "\n\nScan terminé avec succès"

    if len(nouveaux_dossiers) == 0 and len(dossiers_modifies) == 0:
        message += "\n\nAucun dossier modifié ou nouveau"

    terminer_scan(connexion_mysql, id_scan, "termine")
    envoyer_notif_teams(message)
    deconnecter_base_de_donnees(connexion_mysql)


scanner()
