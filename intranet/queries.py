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


def _get_id_dernier_scan(cur) -> int | None:
    """Retourne l'id_scan du dernier scan complété (helper interne)."""
    cur.execute(
        "SELECT id_scan FROM scans WHERE status = 'completed' ORDER BY date_ DESC LIMIT 1"
    )
    row = cur.fetchone()
    return row["id_scan"] if row else None


def _enrichir_avec_taille(cur, rows: list[dict], id_scan: int | None) -> list[dict]:
    """
    Ajoute has_children à chaque ligne en vérifiant si des enfants existent en BDD.
    is_new est converti en bool Python.
    """
    sep = "\\"
    result = []
    for row in rows:
        path = row["path"]
        # Vérifie si ce dossier a des enfants via LEFT() — LIKE avec \ pose problème dans MariaDB
        prefix = path.rstrip(sep) + sep
        cur.execute(
            "SELECT 1 FROM folders WHERE LEFT(path, %s) = %s LIMIT 1",
            (len(prefix), prefix),
        )
        has_children = cur.fetchone() is not None
        result.append({
            "id_folder": row["id_folder"],
            "path": path,
            "is_new": bool(row.get("is_new", 0)),
            "size_kb": row.get("size_kb", 0),
            "has_children": has_children,
        })
    return result


def get_dossiers_racines() -> list[dict]:
    """
    Retourne uniquement les dossiers racines (définis dans CHEMINS_RACINES du .env)
    avec leur taille lors du dernier scan complété.
    Charge UNIQUEMENT ces N chemins — jamais les 200k dossiers.
    """
    chemins_racines = [
        c.strip()
        for c in os.getenv("CHEMINS_RACINES", "").split(",")
        if c.strip()
    ]
    if not chemins_racines:
        return []

    conn = get_connexion()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        id_scan = _get_id_dernier_scan(cur)

        placeholders = ",".join(["%s"] * len(chemins_racines))
        cur.execute(
            f"""
            SELECT
                f.id_folder, f.path, f.is_new,
                COALESCE(sz.size_kb, 0) AS size_kb
            FROM folders f
            LEFT JOIN sizes sz
                ON f.id_folder = sz.id_folder AND sz.id_scan = %s
            WHERE f.path IN ({placeholders})
            ORDER BY f.path
            """,
            (id_scan, *chemins_racines),
        )
        rows = cur.fetchall()
        return _enrichir_avec_taille(cur, rows, id_scan)
    except mysql.connector.Error:
        return []
    finally:
        conn.close()


def get_enfants_dossier(parent_path: str) -> list[dict]:
    """
    Retourne les enfants DIRECTS d'un dossier donné, sans charger les petits-enfants.
    Utilise LEFT() + comptage de séparateurs pour garantir un seul niveau de profondeur.
    """
    original_parent_path = parent_path
    sep = "\\"
    parent_path = parent_path.rstrip(sep)
    # Nombre de séparateurs dans le parent → les enfants en ont exactement un de plus
    sep_count_parent = parent_path.count(sep)
    sep_count_children = sep_count_parent + 1
    # Préfixe avec le séparateur final (ex: 'D:\\Foo\\')
    prefix = parent_path + sep

    conn = get_connexion()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        id_scan = _get_id_dernier_scan(cur)

        # LEFT(path, n) = prefix évite les problèmes d'échappement du backslash dans LIKE MariaDB
        # f.path != original_parent_path empêche le dossier racine (ex: D:\) d'apparaître comme son propre enfant
        cur.execute(
            """
            SELECT
                f.id_folder, f.path, f.is_new,
                COALESCE(sz.size_kb, 0) AS size_kb
            FROM folders f
            LEFT JOIN sizes sz
                ON f.id_folder = sz.id_folder AND sz.id_scan = %s
            WHERE LEFT(f.path, %s) = %s
              AND (LENGTH(f.path) - LENGTH(REPLACE(f.path, %s, ''))) = %s
              AND f.path != %s
            ORDER BY f.path
            """,
            (id_scan, len(prefix), prefix, sep, sep_count_children, original_parent_path),
        )
        rows = cur.fetchall()
        return _enrichir_avec_taille(cur, rows, id_scan)
    except mysql.connector.Error:
        return []
    finally:
        conn.close()


def get_historique_dossier(id_folder: int) -> dict:
    """
    Retourne les données nécessaires au graphique Chart.js pour un dossier donné :
    - Les informations du dossier (chemin, is_new)
    - L'historique des tailles [{date, size_mb}] sur tous les scans complétés
    """
    conn = get_connexion()
    if not conn:
        return {}
    try:
        cur = conn.cursor(dictionary=True)

        # Info du dossier
        cur.execute(
            "SELECT id_folder, path, is_new FROM folders WHERE id_folder = %s",
            (id_folder,),
        )
        dossier = cur.fetchone()
        if not dossier:
            return {}

        # Historique des tailles par scan (30 derniers jours)
        cur.execute(
            """
            SELECT
                sc.date_,
                sz.size_kb
            FROM sizes sz
            JOIN scans sc ON sz.id_scan = sc.id_scan
            WHERE sz.id_folder = %s
              AND sc.status = 'completed'
              AND sc.date_ >= DATE_SUB(NOW(), INTERVAL 30 DAY)
            ORDER BY sc.date_ ASC
            """,
            (id_folder,),
        )
        historique_raw = cur.fetchall()

        labels = []
        data = []
        history_table = []

        prev_size = None
        for row in historique_raw:
            d_str = row["date_"].strftime("%d/%m/%Y %H:%M")
            sz_mo = round(row["size_kb"] / 1024, 2)
            
            delta = 0.0
            if prev_size is not None:
                delta = round(sz_mo - prev_size, 2)
            prev_size = sz_mo

            labels.append(d_str)
            data.append(sz_mo)
            history_table.append({
                "date": d_str,
                "size_mo": sz_mo,
                "delta": delta
            })
        
        # Le tableau HTML affichera du plus récent au plus ancien
        history_table.reverse()

        return {
            "dossier": dossier,
            "labels": labels,
            "data": data,
            "history_table": history_table,
        }
    except mysql.connector.Error:
        return {}
    finally:
        conn.close()
