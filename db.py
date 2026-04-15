"""
Module de gestion de la base de données MariaDB.
"""

import os

import mysql.connector

from notifications import envoyer_notif_teams

import logging

logger = logging.getLogger(__name__)


def parser_seuils_personnalises() -> dict[str, int]:
    """
    Parse la variable d'environnement SEUILS_PERSONNALISES.
    Format attendu : chemin1=seuil1;chemin2=seuil2
    Retourne un dictionnaire {chemin_normalisé: seuil_en_mo}.
    """
    seuils = {}
    valeur = os.getenv("SEUILS_PERSONNALISES", "")
    if not valeur.strip():
        return seuils

    for paire in valeur.split(","):
        paire = paire.strip()
        if "=" not in paire:
            continue
        chemin, seuil_str = paire.rsplit("=", 1)
        chemin = chemin.strip()
        seuil_str = seuil_str.strip()
        if not chemin or not seuil_str:
            continue
        try:
            seuils[os.path.normpath(chemin)] = int(seuil_str)
        except ValueError:
            # Ignore les entrées avec un seuil non numérique
            continue
    return seuils


def obtenir_seuil_pour_chemin(
    chemin: str,
    seuils_personnalises: dict[str, int],
    seuil_defaut: int,
) -> int:
    """
    Retourne le seuil à appliquer pour un chemin donné.
    Cherche le préfixe le plus spécifique (chemin le plus long) dans
    seuils_personnalises. Si aucun match, retourne seuil_defaut.
    """
    chemin_normalise = os.path.normpath(chemin)
    meilleur_match = None
    meilleure_longueur = -1

    for chemin_seuil, seuil in seuils_personnalises.items():
        # Vérifie que le chemin commence par le préfixe + séparateur
        # ou est exactement le préfixe
        if (
            chemin_normalise == chemin_seuil
            or chemin_normalise.startswith(chemin_seuil + os.sep)
        ):
            if len(chemin_seuil) > meilleure_longueur:
                meilleure_longueur = len(chemin_seuil)
                meilleur_match = seuil

    return meilleur_match if meilleur_match is not None else seuil_defaut


def connecter_base_de_donnees() -> mysql.connector.MySQLConnection | None:
    """
    Connecte à la base de données MariaDB.
    """
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            use_pure=True,
        )
    except mysql.connector.Error as err:
        envoyer_notif_teams(f"Erreur de connexion à la base de données : {err}")
        return None


def deconnecter_base_de_donnees(
    connexion: mysql.connector.MySQLConnection,
) -> None:
    """
    Déconnecte de la base de données.
    """
    connexion.close()


def creer_scan(connexion_mysql: mysql.connector.MySQLConnection) -> int | None:
    """
    Crée un nouveau scan dans la table scans avec le statut 'in_progress'.
    Retourne l'id_scan créé.
    """
    try:
        curseur = connexion_mysql.cursor()
        curseur.execute(
            "INSERT INTO scans (date_, status) VALUES (NOW(), 'in_progress')"
        )
        connexion_mysql.commit()
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
    Termine un scan en mettant à jour son statut dans la table scans.
    Statuts possibles : 'completed', 'failed'.
    """
    try:
        curseur = connexion_mysql.cursor()
        curseur.execute(
            "UPDATE scans SET status = %s, date_end = NOW() WHERE id_scan = %s",
            (statut, id_scan),
        )
        connexion_mysql.commit()
        curseur.close()
    except mysql.connector.Error as err:
        envoyer_notif_teams(f"Erreur lors de la terminaison du scan : {err}")


def reset_statut_nouveaux_dossiers_racines(
    connexion_mysql: mysql.connector.MySQLConnection, chemins_racines: list[str]
) -> None:
    """
    Définit is_new = 0 pour tous les dossiers qui étaient marqués 'nouveaux'
    et qui appartiennent aux racines que l'on va scanner.
    Ceci permet de gérer le cas où un dossier nouveau est supprimé avant le scan suivant.
    """
    if not chemins_racines:
        return

    try:
        curseur = connexion_mysql.cursor()
        clauses = []
        params = []
        for racine in chemins_racines:
            racine = racine.strip()
            if racine:
                # Normalisation pour correspondre aux chemins stockés
                # On s'assure que le chemin finit par un séparateur pour ne matcher que le dossier exact ou ses enfants
                racine_norm = os.path.normpath(racine)
                prefix = racine_norm
                if not prefix.endswith(os.sep):
                    prefix += os.sep

                clauses.append("path = %s OR LEFT(path, %s) = %s")
                params.append(racine_norm)
                params.append(len(prefix))
                params.append(prefix)

        if clauses:
            query = f"UPDATE folders SET is_new = 0 WHERE is_new = 1 AND ({' OR '.join(clauses)})"
            curseur.execute(query, params)
            connexion_mysql.commit()
        curseur.close()
    except mysql.connector.Error as err:
        envoyer_notif_teams(f"Erreur lors de la réinitialisation des tags 'new' : {err}")


def marquer_dossiers_comme_racines(
    connexion_mysql: mysql.connector.MySQLConnection, chemins_racines: list[str]
) -> None:
    """
    Marque les dossiers de la liste en tant que racines (is_root = 1).
    Ceci permet de toujours les afficher dans l'Intranet même s'ils ne
    sont plus activement scannés.
    """
    if not chemins_racines:
        return

    try:
        curseur = connexion_mysql.cursor()
        for racine in chemins_racines:
            racine = racine.strip()
            if racine:
                racine_norm = os.path.normpath(racine)
                curseur.execute(
                    "UPDATE folders SET is_root = 1 WHERE path = %s",
                    (racine_norm,)
                )
        connexion_mysql.commit()
        curseur.close()
    except mysql.connector.Error as err:
        envoyer_notif_teams(f"Erreur lors de la mise à jour des racines : {err}")


def detecter_dossiers_supprimes(
    connexion_mysql: mysql.connector.MySQLConnection,
    chemins_disque: set[str],
    chemin_racine: str,
    id_scan: int,
) -> list[dict]:
    """
    Détecte les dossiers supprimés du disque entre deux scans.
    Compare les dossiers en base (pour la racine donnée) avec ceux trouvés sur le disque.
    Pour chaque dossier absent du disque :
      - Met is_deleted = 1 dans folders
      - Insère une entrée size_kb = 0 dans sizes
    Retourne la liste des dossiers supprimés (chemin + dernière taille connue en Mo).
    """
    chemin_racine_norm = os.path.normpath(chemin_racine)
    prefix = chemin_racine_norm
    if not prefix.endswith(os.sep):
        prefix += os.sep

    try:
        curseur = connexion_mysql.cursor()

        # Itère sur les dossiers en base sans tout charger en mémoire
        # Compare chaque chemin avec le set de chemins disque (déjà en mémoire)
        curseur.execute(
            "SELECT id_folder, path FROM folders "
            "WHERE is_deleted = 0 AND (path = %s OR LEFT(path, %s) = %s)",
            (chemin_racine_norm, len(prefix), prefix),
        )

        supprimes_ids = []
        supprimes_tuples = []
        for id_dossier, chemin in curseur:
            if chemin not in chemins_disque:
                supprimes_ids.append(id_dossier)
                supprimes_tuples.append((id_dossier, chemin))

        if not supprimes_tuples:
            curseur.close()
            return []

        # Récupérer les dernières tailles connues pour les dossiers supprimés
        placeholders = ",".join(["%s"] * len(supprimes_ids))
        curseur.execute(
            f"SELECT s.id_folder, s.size_kb FROM sizes s "
            f"INNER JOIN ("
            f"  SELECT id_folder, MAX(id_scan) AS max_scan "
            f"  FROM sizes WHERE id_folder IN ({placeholders}) "
            f"  GROUP BY id_folder"
            f") latest ON s.id_folder = latest.id_folder AND s.id_scan = latest.max_scan",
            supprimes_ids,
        )
        dernieres_tailles = {row[0]: row[1] for row in curseur.fetchall()}

        dossiers_supprimes = []
        compteur = 0
        for id_dossier, chemin in supprimes_tuples:
            derniere_taille_kb = dernieres_tailles.get(id_dossier, 0)

            # Marquer comme supprimé
            curseur.execute(
                "UPDATE folders SET is_deleted = 1 WHERE id_folder = %s",
                (id_dossier,),
            )
            # Enregistrer taille 0 pour ce scan (crée le point zéro dans l'historique)
            curseur.execute(
                "INSERT INTO sizes (id_scan, id_folder, size_kb) VALUES (%s, %s, 0)",
                (id_scan, id_dossier),
            )

            # Convertir en Mo pour la comparaison avec le seuil
            derniere_taille_mo = round(derniere_taille_kb / 1024)
            dossiers_supprimes.append(
                {
                    "type": "suppression",
                    "chemin": chemin,
                    "taille": derniere_taille_mo,
                }
            )

            compteur += 1
            if compteur % 5000 == 0:
                connexion_mysql.commit()

        connexion_mysql.commit()
        curseur.close()

        logger.info(
            "Détection suppressions pour %s : %d dossier(s) supprimé(s)",
            chemin_racine_norm,
            len(dossiers_supprimes),
        )
        return dossiers_supprimes

    except mysql.connector.Error as err:
        envoyer_notif_teams(f"Erreur lors de la détection des suppressions : {err}")
        return []


def enregistrer_totaux_scan(
    connexion_mysql: mysql.connector.MySQLConnection,
    id_scan: int,
    total_folders: int,
    total_size_kb: int,
) -> None:
    """
    Enregistre les totaux globaux du scan dans la table scans.
    total_size_kb doit être la somme des tailles des chemins racines uniquement
    (pas la somme de tous les dossiers, pour éviter le double comptage).
    """
    try:
        curseur = connexion_mysql.cursor()
        curseur.execute(
            "UPDATE scans SET total_folders = %s, total_size_kb = %s WHERE id_scan = %s",
            (total_folders, total_size_kb, id_scan),
        )
        connexion_mysql.commit()
        curseur.close()
    except mysql.connector.Error as err:
        envoyer_notif_teams(f"Erreur lors de l'enregistrement des totaux : {err}")


def traiter_dossiers_en_lot(
    connexion_mysql: mysql.connector.MySQLConnection,
    dossiers_avec_tailles: dict[str, int],
    chemin_racine: str = None,
    id_scan: int = None,
) -> tuple[list, list, int, int]:
    """
    Traite tous les dossiers en lot pour optimiser les accès BDD.
    Charge tous les dossiers existants en mémoire (1 seul SELECT),
    puis fait les INSERT/UPDATE avec un commit tous les 5000 dossiers.

    Les tailles sont stockées en Ko dans la table sizes.
    Pour déterminer les changements, on compare avec le dernier scan enregistré.

    Retourne (nouveaux_dossiers, dossiers_modifies, taille_totale_scan_ko, changement_racine_ko).
    """
    seuil_defaut = int(os.getenv("SEUIL_DEFAUT"))
    seuils_personnalises = parser_seuils_personnalises()
    curseur = connexion_mysql.cursor()

    # Normalisation du chemin racine pour comparaison
    chemin_racine_norm = os.path.normpath(chemin_racine) if chemin_racine else None

    # Récupère l'id du dernier scan terminé pour comparer les tailles
    curseur.execute(
        "SELECT id_scan FROM scans WHERE status = 'completed' "
        "ORDER BY date_ DESC LIMIT 1"
    )
    dernier_scan = curseur.fetchone()
    id_dernier_scan = dernier_scan[0] if dernier_scan else None

    # Charge TOUS les dossiers existants en mémoire (1 seule requête)
    curseur.execute("SELECT id_folder, path FROM folders")
    dossiers_existants = {row[1]: row[0] for row in curseur.fetchall()}

    # Si un scan précédent existe, charger les tailles correspondantes
    tailles_precedentes = {}
    if id_dernier_scan:
        curseur.execute(
            "SELECT id_folder, size_kb FROM sizes WHERE id_scan = %s",
            (id_dernier_scan,),
        )
        tailles_precedentes = {row[0]: row[1] for row in curseur.fetchall()}

    nouveaux_dossiers = []
    dossiers_modifies = []
    taille_totale_scan = 0
    changement_racine = 0
    compteur = 0

    for chemin, taille_octets in dossiers_avec_tailles.items():
        taille_en_ko = round(taille_octets / 1024)
        taille_totale_scan += taille_en_ko
        chemin_norm = os.path.normpath(chemin)

        if chemin in dossiers_existants:
            # Dossier existant → récupérer l'id et la taille précédente
            id_dossier = dossiers_existants[chemin]

            # Résurrection : si le dossier était marqué supprimé, le réactiver
            curseur.execute(
                "UPDATE folders SET is_deleted = 0 WHERE id_folder = %s AND is_deleted = 1",
                (id_dossier,),
            )

            taille_precedente = tailles_precedentes.get(id_dossier, 0)
            diff_ko = taille_en_ko - int(taille_precedente)

            if chemin_racine_norm and chemin_norm == chemin_racine_norm:
                changement_racine = diff_ko

            # N'insérer dans sizes que si la taille a changé
            if taille_en_ko != int(taille_precedente):
                curseur.execute(
                    "INSERT INTO sizes (id_scan, id_folder, size_kb) VALUES (%s, %s, %s)",
                    (id_scan, id_dossier, taille_en_ko),
                )

            # Convertir en Mo pour la comparaison avec le seuil (qui est en Mo)
            diff_mo = round(diff_ko / 1024)
            seuil = obtenir_seuil_pour_chemin(chemin, seuils_personnalises, seuil_defaut)
            if abs(diff_mo) > seuil:
                dossiers_modifies.append(
                    {
                        "type": "modification",
                        "chemin": chemin,
                        "difference": diff_mo,
                    }
                )
        else:
            # Nouveau dossier → INSERT dans folders + sizes
            curseur.execute(
                "INSERT INTO folders (path, is_new) VALUES (%s, 1)",
                (chemin,),
            )
            id_dossier = curseur.lastrowid
            curseur.execute(
                "INSERT INTO sizes (id_scan, id_folder, size_kb) VALUES (%s, %s, %s)",
                (id_scan, id_dossier, taille_en_ko),
            )

            if chemin_racine_norm and chemin_norm == chemin_racine_norm:
                changement_racine = taille_en_ko

            # Convertir en Mo pour la comparaison avec le seuil
            taille_en_mo = round(taille_en_ko / 1024)
            seuil = obtenir_seuil_pour_chemin(chemin, seuils_personnalises, seuil_defaut)
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
    return nouveaux_dossiers, dossiers_modifies, taille_totale_scan, changement_racine
