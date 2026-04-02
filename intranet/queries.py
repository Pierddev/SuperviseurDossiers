"""
Requêtes SQL dédiées à l'interface Intranet.
Séparées de db.py pour ne pas alourdir le cœur du scanner.
"""

import os

import mysql.connector


def get_connexion() -> mysql.connector.MySQLConnection | None:
    """Ouvre une connexion à la BDD MariaDB."""
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
        )
    except mysql.connector.Error:
        return None


def get_derniers_scans(limit: int = 10) -> list[dict]:
    """Retourne les derniers scans ordonnés par date décroissante."""
    conn = get_connexion()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id_scan, date_, status FROM scans "
            "ORDER BY date_ DESC LIMIT %s",
            (limit,),
        )
        return cur.fetchall()
    except mysql.connector.Error:
        return []
    finally:
        conn.close()


def get_stats_dashboard() -> dict:
    """
    Retourne les statistiques pour le tableau de bord :
    - Dernier scan (date, statut)
    - Nombre total de dossiers surveillés
    - Nombre total de scans effectués
    - Top 5 dossiers avec le plus grand changement entre les 2 derniers scans
    """
    conn = get_connexion()
    if not conn:
        return {}

    try:
        cur = conn.cursor(dictionary=True)

        # --- Dernier scan ---
        cur.execute(
            "SELECT id_scan, date_, status FROM scans ORDER BY date_ DESC LIMIT 1"
        )
        dernier_scan = cur.fetchone()

        # --- Nombre total de dossiers ---
        cur.execute("SELECT COUNT(*) as total FROM folders")
        total_dossiers = cur.fetchone()["total"]

        # --- Nombre total de scans ---
        cur.execute("SELECT COUNT(*) as total FROM scans WHERE status = 'completed'")
        total_scans = cur.fetchone()["total"]

        # --- Top 5 changements ---
        top_changements = []
        if total_scans >= 2:
            # Récupère les 2 derniers scans complétés
            cur.execute(
                "SELECT id_scan FROM scans WHERE status = 'completed' "
                "ORDER BY date_ DESC LIMIT 2"
            )
            deux_derniers = cur.fetchall()
            id_scan_actuel = deux_derniers[0]["id_scan"]
            id_scan_precedent = deux_derniers[1]["id_scan"]

            cur.execute(
                """
                SELECT
                    f.path,
                    s1.size_kb AS size_actuel_kb,
                    s2.size_kb AS size_precedent_kb,
                    (s1.size_kb - s2.size_kb) AS diff_kb
                FROM sizes s1
                JOIN sizes s2 ON s1.id_folder = s2.id_folder
                JOIN folders f ON s1.id_folder = f.id_folder
                WHERE s1.id_scan = %s AND s2.id_scan = %s
                ORDER BY ABS(s1.size_kb - s2.size_kb) DESC
                LIMIT 5
                """,
                (id_scan_actuel, id_scan_precedent),
            )
            top_changements = cur.fetchall()

        return {
            "dernier_scan": dernier_scan,
            "total_dossiers": total_dossiers,
            "total_scans": total_scans,
            "top_changements": top_changements,
        }

    except mysql.connector.Error:
        return {}
    finally:
        conn.close()


