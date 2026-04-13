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


def get_scans_history(limit: int = 50) -> list[dict]:
    """
    Retourne l'historique complet des scans avec leur durée et le nombre de dossiers mis à jour.
    """
    conn = get_connexion()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT 
                sc.id_scan, 
                sc.date_, 
                sc.date_end, 
                sc.status,
                TIMESTAMPDIFF(SECOND, sc.date_, sc.date_end) AS duration_sec,
                COUNT(sz.id_folder) AS folders_updated
            FROM scans sc
            LEFT JOIN sizes sz ON sc.id_scan = sz.id_scan
            GROUP BY sc.id_scan
            ORDER BY sc.date_ DESC 
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()
    except mysql.connector.Error:
        return []
    finally:
        conn.close()


def get_scan_details(id_scan: int) -> dict:
    """
    Retourne les détails complets d'un scan :
    - Le résumé statistique du cycle (nb dossiers, volume total, variation)
    - La liste des alertes : nouveaux dossiers + dossiers ayant dépassé leur seuil
    """
    conn = get_connexion()
    if not conn:
        return {}
    try:
        cur = conn.cursor(dictionary=True)

        # 1. Infos du scan
        cur.execute(
            """
            SELECT id_scan, date_, date_end, status,
                   TIMESTAMPDIFF(SECOND, date_, date_end) AS duration_sec
            FROM scans WHERE id_scan = %s
            """,
            (id_scan,),
        )
        scan = cur.fetchone()
        if not scan:
            return {}

        # 2. Résumé : nb dossiers analysés + volume total pour ce scan
        cur.execute(
            """
            SELECT COUNT(*) AS nb_dossiers, SUM(size_kb) AS total_kb
            FROM sizes WHERE id_scan = %s
            """,
            (id_scan,),
        )
        resume_row = cur.fetchone()
        nb_dossiers = resume_row["nb_dossiers"] or 0
        total_kb = resume_row["total_kb"] or 0

        # 3. Scan précédent immédiat (pour calcul de variation totale)
        cur.execute(
            """
            SELECT id_scan FROM scans
            WHERE status = 'completed' AND id_scan < %s
            ORDER BY id_scan DESC LIMIT 1
            """,
            (id_scan,),
        )
        row_prev = cur.fetchone()
        id_scan_prev = row_prev["id_scan"] if row_prev else None

        variation_kb = None
        if id_scan_prev:
            cur.execute(
                "SELECT SUM(size_kb) AS total_kb FROM sizes WHERE id_scan = %s",
                (id_scan_prev,),
            )
            prev_row = cur.fetchone()
            prev_kb = prev_row["total_kb"] or 0
            variation_kb = total_kb - prev_kb

        # 4. Nouveaux dossiers (première apparition dans sizes à cet id_scan)
        #    Filtrés : uniquement ceux dont la taille dépasse le seuil configuré
        seuil_mo = int(os.getenv("SEUIL_DEFAUT", 100))
        seuil_kb = seuil_mo * 1024
        cur.execute(
            """
            SELECT f.path, sz.size_kb
            FROM sizes sz
            JOIN folders f ON sz.id_folder = f.id_folder
            WHERE sz.id_scan = %s
              AND sz.size_kb > %s
              AND NOT EXISTS (
                  SELECT 1 FROM sizes sz2
                  WHERE sz2.id_folder = sz.id_folder AND sz2.id_scan < %s
              )
            ORDER BY sz.size_kb DESC
            LIMIT 100
            """,
            (id_scan, seuil_kb, id_scan),
        )
        nouveaux = [
            {
                "type": "nouveau",
                "chemin": r["path"],
                "taille_kb": r["size_kb"],
            }
            for r in cur.fetchall()
        ]

        # 5. Dossiers modifiés (variation > SEUIL_DEFAUT) par rapport au scan précédent
        alertes_modifs = []
        if id_scan_prev:
            cur.execute(
                """
                SELECT f.path,
                       sz_cur.size_kb AS size_kb_cur,
                       sz_prev.size_kb AS size_kb_prev,
                       (sz_cur.size_kb - sz_prev.size_kb) AS diff_kb
                FROM sizes sz_cur
                JOIN sizes sz_prev ON sz_cur.id_folder = sz_prev.id_folder
                JOIN folders f ON sz_cur.id_folder = f.id_folder
                WHERE sz_cur.id_scan = %s
                  AND sz_prev.id_scan = %s
                  AND ABS(sz_cur.size_kb - sz_prev.size_kb) > %s
                ORDER BY ABS(sz_cur.size_kb - sz_prev.size_kb) DESC
                LIMIT 100
                """,
                (id_scan, id_scan_prev, seuil_kb),
            )
            alertes_modifs = [
                {
                    "type": "modification",
                    "chemin": r["path"],
                    "diff_kb": r["diff_kb"],
                    "taille_kb": r["size_kb_cur"],
                }
                for r in cur.fetchall()
            ]

        # Convertit la date pour la sérialisation JSON
        if scan.get("date_"):
            scan["date_"] = scan["date_"].strftime("%d/%m/%Y à %H:%M:%S")
        if scan.get("date_end"):
            scan["date_end"] = scan["date_end"].strftime("%d/%m/%Y à %H:%M:%S")

        return {
            "scan": scan,
            "resume": {
                "nb_dossiers": nb_dossiers,
                "total_kb": total_kb,
                "variation_kb": variation_kb,
            },
            "alertes": nouveaux + alertes_modifs,
        }

    except mysql.connector.Error:
        return {}
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
                    f.id_folder, f.path,
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

        prev_size_kb = None
        for row in historique_raw:
            d_str = row["date_"].strftime("%d/%m/%Y %H:%M")
            sz_kb = row["size_kb"]
            sz_mo = round(sz_kb / 1024, 2)
            
            delta_kb = 0
            if prev_size_kb is not None:
                delta_kb = sz_kb - prev_size_kb
            prev_size_kb = sz_kb

            labels.append(d_str)
            data.append(sz_mo)
            history_table.append({
                "date": d_str,
                "size_kb": sz_kb,
                "delta_kb": delta_kb
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


def rechercher_dossiers(query: str, limit: int = 30) -> list[dict]:
    """
    Recherche des dossiers dont le chemin contient le texte donné (insensible à la casse).
    Retourne les résultats avec leur taille au dernier scan.
    """
    if not query or len(query) < 2:
        return []

    conn = get_connexion()
    if not conn:
        return []
    try:
        cur = conn.cursor(dictionary=True)
        id_scan = _get_id_dernier_scan(cur)

        # Recherche LIKE sur le path — échappe les caractères spéciaux SQL
        # Le backslash doit être échappé EN PREMIER (c'est le char d'échappement de LIKE)
        search_term = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        search_term = f"%{search_term}%"

        cur.execute(
            """
            SELECT
                f.id_folder, f.path, f.is_new,
                COALESCE(sz.size_kb, 0) AS size_kb
            FROM folders f
            LEFT JOIN sizes sz
                ON f.id_folder = sz.id_folder AND sz.id_scan = %s
            WHERE f.path LIKE %s
            ORDER BY LENGTH(f.path) ASC, f.path ASC
            LIMIT %s
            """,
            (id_scan, search_term, limit),
        )
        rows = cur.fetchall()
        return [
            {
                "id_folder": row["id_folder"],
                "path": row["path"],
                "is_new": bool(row.get("is_new", 0)),
                "size_kb": row.get("size_kb", 0),
            }
            for row in rows
        ]
    except mysql.connector.Error:
        return []
    finally:
        conn.close()
