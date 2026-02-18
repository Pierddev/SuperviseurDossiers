import charset_normalizer
import logging
import os
import requests
import json
import mysql.connector
import dotenv

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
