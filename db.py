"""
Module de gestion de la base de données MySQL.
"""

import os

import mysql.connector

from notifications import envoyer_notif_teams


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

    for paire in valeur.split(";"):
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
    seuil: int | None = None,
) -> dict[str, str] | None:
    """
    Insère ou met à jour un dossier dans la table sudo_dossiers.
    Retourne un dictionnaire avec les informations du dossier si la modification
    de sa taille est supérieure au seuil.
    Si seuil n'est pas fourni, utilise SEUIL_DEFAUT du .env.
    """
    if seuil is None:
        seuil = int(os.getenv("SEUIL_DEFAUT"))

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

            if taille_dossier > seuil:
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

            if difference_taille_dossier > seuil:
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
    seuil_defaut = int(os.getenv("SEUIL_DEFAUT"))
    seuils_personnalises = parser_seuils_personnalises()
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

            seuil = obtenir_seuil_pour_chemin(chemin, seuils_personnalises, seuil_defaut)
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
    return nouveaux_dossiers, dossiers_modifies, taille_totale_scan
