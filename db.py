"""
Module de gestion de la base de données MySQL.
"""

import os

import mysql.connector

from notifications import envoyer_notif_teams


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
