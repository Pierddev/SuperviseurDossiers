"""
Tests pour les fonctions liées à la base de données.
Vérifie connecter_base_de_donnees, deconnecter_base_de_donnees,
creer_scan, terminer_scan et inserer_ou_mettre_a_jour_dossier.
NB: Ces tests ont été réalisés avec l'aide de l'Intelligence Artificielle.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

import mysql.connector

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import (
    connecter_base_de_donnees,
    deconnecter_base_de_donnees,
    creer_scan,
    terminer_scan,
    traiter_dossiers_en_lot,
    parser_seuils_personnalises,
    obtenir_seuil_pour_chemin,
)


class TestConnecterBaseDeDonnees(unittest.TestCase):
    """Tests pour la fonction connecter_base_de_donnees."""

    @patch.dict(os.environ, {"DB_HOST": "localhost", "DB_PORT": "3306", "DB_USER": "root", "DB_PASSWORD": "", "DB_NAME": "test"})
    @patch("db.mysql.connector.connect")
    def test_connexion_reussie(self, mock_connect):
        """Doit retourner un objet connexion si la connexion réussit."""
        mock_connexion = MagicMock()
        mock_connect.return_value = mock_connexion
        resultat = connecter_base_de_donnees()
        self.assertEqual(resultat, mock_connexion)

    @patch.dict(os.environ, {"DB_HOST": "localhost", "DB_PORT": "3306", "DB_USER": "root", "DB_PASSWORD": "", "DB_NAME": "test"})
    @patch("db.mysql.connector.connect")
    def test_connexion_utilise_variables_env(self, mock_connect):
        """Doit utiliser les variables d'environnement pour la connexion."""
        mock_connect.return_value = MagicMock()
        connecter_base_de_donnees()
        mock_connect.assert_called_once()
        kwargs = mock_connect.call_args[1]
        self.assertIn("host", kwargs)
        self.assertIn("port", kwargs)
        self.assertIn("user", kwargs)
        self.assertIn("password", kwargs)
        self.assertIn("database", kwargs)

    @patch("db.envoyer_notif_teams")
    @patch("db.mysql.connector.connect")
    def test_connexion_echouee_retourne_none(self, mock_connect, mock_notif):
        """Doit retourner None si la connexion échoue."""
        mock_connect.side_effect = mysql.connector.Error("Connexion refusée")
        resultat = connecter_base_de_donnees()
        self.assertIsNone(resultat)

    @patch("db.envoyer_notif_teams")
    @patch("db.mysql.connector.connect")
    def test_connexion_echouee_envoie_notification(self, mock_connect, mock_notif):
        """Doit envoyer une notification Teams si la connexion échoue."""
        mock_connect.side_effect = mysql.connector.Error("Connexion refusée")
        connecter_base_de_donnees()
        mock_notif.assert_called_once()
        self.assertIn("Erreur de connexion", mock_notif.call_args[0][0])


class TestDeconnecterBaseDeDonnees(unittest.TestCase):
    """Tests pour la fonction deconnecter_base_de_donnees."""

    def test_appelle_close(self):
        """Doit appeler la méthode close() sur la connexion."""
        mock_connexion = MagicMock()
        deconnecter_base_de_donnees(mock_connexion)
        mock_connexion.close.assert_called_once()


class TestCreerScan(unittest.TestCase):
    """Tests pour la fonction creer_scan."""

    def test_retourne_id_scan(self):
        """Doit retourner l'id du scan créé."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_curseur.lastrowid = 42
        mock_connexion.cursor.return_value = mock_curseur

        resultat = creer_scan(mock_connexion)
        self.assertEqual(resultat, 42)

    def test_execute_insert(self):
        """Doit exécuter une requête INSERT avec le statut 'en_cours'."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_connexion.cursor.return_value = mock_curseur

        creer_scan(mock_connexion)
        requete = mock_curseur.execute.call_args[0][0]
        self.assertIn("INSERT INTO scans", requete)
        self.assertIn("in_progress", requete)

    def test_fait_un_commit(self):
        """Doit faire un commit après l'insertion."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_connexion.cursor.return_value = mock_curseur

        creer_scan(mock_connexion)
        mock_connexion.commit.assert_called_once()

    def test_ferme_le_curseur(self):
        """Doit fermer le curseur après l'opération."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_connexion.cursor.return_value = mock_curseur

        creer_scan(mock_connexion)
        mock_curseur.close.assert_called_once()

    @patch("db.envoyer_notif_teams")
    def test_erreur_retourne_none(self, mock_notif):
        """Doit retourner None en cas d'erreur SQL."""
        mock_connexion = MagicMock()
        mock_connexion.cursor.side_effect = mysql.connector.Error("Erreur SQL")

        resultat = creer_scan(mock_connexion)
        self.assertIsNone(resultat)

    @patch("db.envoyer_notif_teams")
    def test_erreur_envoie_notification(self, mock_notif):
        """Doit envoyer une notification Teams en cas d'erreur SQL."""
        mock_connexion = MagicMock()
        mock_connexion.cursor.side_effect = mysql.connector.Error("Erreur SQL")

        creer_scan(mock_connexion)
        mock_notif.assert_called_once()
        self.assertIn("Erreur lors de la création du scan", mock_notif.call_args[0][0])


class TestTerminerScan(unittest.TestCase):
    """Tests pour la fonction terminer_scan."""

    def test_execute_update(self):
        """Doit exécuter une requête UPDATE avec le bon statut et id."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_connexion.cursor.return_value = mock_curseur

        terminer_scan(mock_connexion, 42, "completed")
        requete = mock_curseur.execute.call_args[0][0]
        params = mock_curseur.execute.call_args[0][1]
        self.assertIn("UPDATE scans", requete)
        self.assertEqual(params, ("completed", 42))

    def test_fait_un_commit(self):
        """Doit faire un commit après la mise à jour."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_connexion.cursor.return_value = mock_curseur

        terminer_scan(mock_connexion, 1, "completed")
        mock_connexion.commit.assert_called_once()

    def test_ferme_le_curseur(self):
        """Doit fermer le curseur après l'opération."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_connexion.cursor.return_value = mock_curseur

        terminer_scan(mock_connexion, 1, "completed")
        mock_curseur.close.assert_called_once()

    @patch("db.envoyer_notif_teams")
    def test_erreur_envoie_notification(self, mock_notif):
        """Doit envoyer une notification Teams en cas d'erreur SQL."""
        mock_connexion = MagicMock()
        mock_connexion.cursor.side_effect = mysql.connector.Error("Erreur SQL")

        terminer_scan(mock_connexion, 1, "completed")
        mock_notif.assert_called_once()
        self.assertIn(
            "Erreur lors de la terminaison du scan", mock_notif.call_args[0][0]
        )


class TestTraiterDossiersEnLot(unittest.TestCase):
    """Tests pour la fonction traiter_dossiers_en_lot."""

    def _mock_connexion_nouveau_dossier(self):
        """Mock pour un nouveau dossier (folders vide)."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        # 1: Dernier scan, 2: Folders existants
        mock_curseur.fetchone.return_value = [10] # id_dernier_scan
        mock_curseur.fetchall.side_effect = [
            [], # folders existants
            [(1, 100)] # tailles précédentes pour scan 10 (id_folder, size_kb)
        ]
        mock_curseur.lastrowid = 1
        mock_connexion.cursor.return_value = mock_curseur
        return mock_connexion, mock_curseur

    def _mock_connexion_dossier_existant(self, taille_precedente_kb=50):
        """Mock pour un dossier existant."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        # 1: Dernier scan, 2: Folders existants, 3: Tailles précédentes
        mock_curseur.fetchone.return_value = [10] # id_dernier_scan
        mock_curseur.fetchall.side_effect = [
            [(1, "C:\\test")], # folders existants
            [(1, taille_precedente_kb)] # tailles précédentes
        ]
        mock_connexion.cursor.return_value = mock_curseur
        return mock_connexion, mock_curseur

    @patch.dict(os.environ, {"SEUIL_DEFAUT": "100"})
    def test_nouveau_dossier_petit_retourne_liste_vide(self):
        """Un nouveau dossier sous le seuil ne doit pas être dans la liste des nouveaux."""
        mock_connexion, _ = self._mock_connexion_nouveau_dossier()
        nouveaux, modifies, _, _ = traiter_dossiers_en_lot(mock_connexion, {"C:\\test": 50 * 1024}, id_scan=11)
        self.assertEqual(len(nouveaux), 0)

    @patch.dict(os.environ, {"SEUIL_DEFAUT": "100"})
    def test_nouveau_dossier_gros_retourne_element(self):
        """Un nouveau dossier au-dessus du seuil doit être retourné."""
        mock_connexion, _ = self._mock_connexion_nouveau_dossier()
        # 200 Mo = 200 * 1024 * 1024 octets
        nouveaux, _, _, _ = traiter_dossiers_en_lot(mock_connexion, {"C:\\gros": 200 * 1024 * 1024}, id_scan=11)
        self.assertEqual(len(nouveaux), 1)
        self.assertEqual(nouveaux[0]["type"], "nouveau")
        self.assertEqual(nouveaux[0]["chemin"], "C:\\gros")
        self.assertEqual(nouveaux[0]["taille"], 200)

    @patch.dict(os.environ, {"SEUIL_DEFAUT": "100"})
    def test_nouveau_dossier_insere_dans_deux_tables(self):
        """Un nouveau dossier doit être inséré dans folders ET sizes."""
        mock_connexion, mock_curseur = self._mock_connexion_nouveau_dossier()
        traiter_dossiers_en_lot(mock_connexion, {"C:\\test": 50 * 1024 * 1024}, id_scan=11)
        requetes = [appel[0][0] for appel in mock_curseur.execute.call_args_list]
        self.assertTrue(any("INSERT INTO folders" in r for r in requetes))
        self.assertTrue(any("INSERT INTO sizes" in r for r in requetes))

    @patch.dict(os.environ, {"SEUIL_DEFAUT": "100"})
    def test_dossier_existant_petite_modif_retourne_liste_vide(self):
        """Une modification sous le seuil ne doit pas être retournée."""
        mock_connexion, _ = self._mock_connexion_dossier_existant(taille_precedente_kb=50 * 1024)
        nouveaux, modifies, _, _ = traiter_dossiers_en_lot(mock_connexion, {"C:\\test": 60 * 1024 * 1024}, id_scan=11)
        self.assertEqual(len(modifies), 0)

    @patch.dict(os.environ, {"SEUIL_DEFAUT": "100"})
    def test_dossier_existant_grosse_modif_retourne_element(self):
        """Une modification au-dessus du seuil doit être retournée."""
        mock_connexion, _ = self._mock_connexion_dossier_existant(taille_precedente_kb=50 * 1024)
        _, modifies, _, _ = traiter_dossiers_en_lot(mock_connexion, {"C:\\test": 200 * 1024 * 1024}, id_scan=11)
        self.assertEqual(len(modifies), 1)
        self.assertEqual(modifies[0]["type"], "modification")
        self.assertEqual(modifies[0]["chemin"], "C:\\test")
        self.assertEqual(modifies[0]["difference"], 150) # 200 - 50

    @patch.dict(os.environ, {"SEUIL_DEFAUT": "100"})
    def test_dossier_existant_reduction_taille(self):
        """Une réduction de taille au-dessus du seuil doit aussi être détectée."""
        mock_connexion, _ = self._mock_connexion_dossier_existant(taille_precedente_kb=300 * 1024)
        _, modifies, _, _ = traiter_dossiers_en_lot(mock_connexion, {"C:\\test": 100 * 1024 * 1024}, id_scan=11)
        self.assertEqual(len(modifies), 1)
        self.assertEqual(modifies[0]["difference"], -200) # 100 - 300

    @patch.dict(os.environ, {"SEUIL_DEFAUT": "100"})
    def test_fait_un_commit(self):
        """Doit faire un commit après l'opération."""
        mock_connexion, _ = self._mock_connexion_nouveau_dossier()
        traiter_dossiers_en_lot(mock_connexion, {"C:\\test": 50 * 1024 * 1024}, id_scan=11)
        mock_connexion.commit.assert_called()

    @patch.dict(os.environ, {"SEUIL_DEFAUT": "100"})
    @patch("db.envoyer_notif_teams")
    def test_erreur_sql_envoie_notification(self, mock_notif):
        """Doit envoyer une notification Teams en cas d'erreur SQL."""
        mock_connexion = MagicMock()
        mock_connexion.cursor.side_effect = mysql.connector.Error("Erreur SQL")
        traiter_dossiers_en_lot(mock_connexion, {"C:\\test": 50}, id_scan=11)
        mock_notif.assert_called_once()
        self.assertIn("Erreur lors du traitement des dossiers", mock_notif.call_args[0][0])


class TestParserSeuilsPersonnalises(unittest.TestCase):
    """Tests pour la fonction parser_seuils_personnalises."""

    @patch.dict(os.environ, {"SEUILS_PERSONNALISES": ""})
    def test_chaine_vide_retourne_dict_vide(self):
        """Une chaîne vide doit retourner un dictionnaire vide."""
        resultat = parser_seuils_personnalises()
        self.assertEqual(resultat, {})

    @patch.dict(os.environ, {}, clear=False)
    def test_variable_absente_retourne_dict_vide(self):
        """Si la variable n'est pas définie, doit retourner un dictionnaire vide."""
        os.environ.pop("SEUILS_PERSONNALISES", None)
        resultat = parser_seuils_personnalises()
        self.assertEqual(resultat, {})

    @patch.dict(os.environ, {"SEUILS_PERSONNALISES": "D:\\Projets=50"})
    def test_un_seul_seuil(self):
        """Un seul seuil doit être correctement parsé."""
        resultat = parser_seuils_personnalises()
        self.assertEqual(len(resultat), 1)
        chemin_normalise = os.path.normpath("D:\\Projets")
        self.assertIn(chemin_normalise, resultat)
        self.assertEqual(resultat[chemin_normalise], 50)

    @patch.dict(os.environ, {"SEUILS_PERSONNALISES": "D:\\Projets=50,D:\\Archives=500"})
    def test_plusieurs_seuils(self):
        """Plusieurs seuils séparés par , doivent être correctement parsés."""
        resultat = parser_seuils_personnalises()
        self.assertEqual(len(resultat), 2)
        self.assertEqual(resultat[os.path.normpath("D:\\Projets")], 50)
        self.assertEqual(resultat[os.path.normpath("D:\\Archives")], 500)

    @patch.dict(os.environ, {"SEUILS_PERSONNALISES": "D:\\Projets=abc,D:\\Archives=500"})
    def test_seuil_non_numerique_est_ignore(self):
        """Un seuil non numérique doit être ignoré sans erreur."""
        resultat = parser_seuils_personnalises()
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[os.path.normpath("D:\\Archives")], 500)

    @patch.dict(os.environ, {"SEUILS_PERSONNALISES": "pasdegal,=100,D:\\Ok=200"})
    def test_entrees_malformees_sont_ignorees(self):
        """Les entrées sans = ou avec chemin vide doivent être ignorées."""
        resultat = parser_seuils_personnalises()
        self.assertEqual(len(resultat), 1)
        self.assertEqual(resultat[os.path.normpath("D:\\Ok")], 200)


class TestObtenirSeuilPourChemin(unittest.TestCase):
    """Tests pour la fonction obtenir_seuil_pour_chemin."""

    def test_aucun_match_retourne_defaut(self):
        """Si aucun préfixe ne correspond, doit retourner le seuil par défaut."""
        seuils = {os.path.normpath("D:\\Projets"): 50}
        resultat = obtenir_seuil_pour_chemin("C:\\Autre", seuils, 100)
        self.assertEqual(resultat, 100)

    def test_dict_vide_retourne_defaut(self):
        """Avec un dictionnaire vide, doit retourner le seuil par défaut."""
        resultat = obtenir_seuil_pour_chemin("D:\\Projets\\Test", {}, 100)
        self.assertEqual(resultat, 100)

    def test_match_exact(self):
        """Un match exact doit retourner le seuil correspondant."""
        seuils = {os.path.normpath("D:\\Projets"): 50}
        resultat = obtenir_seuil_pour_chemin(
            os.path.normpath("D:\\Projets"), seuils, 100
        )
        self.assertEqual(resultat, 50)

    def test_match_par_prefixe(self):
        """Un sous-dossier doit matcher le seuil de son parent."""
        seuils = {os.path.normpath("D:\\Projets"): 50}
        resultat = obtenir_seuil_pour_chemin(
            os.path.normpath("D:\\Projets\\MonProjet\\src"), seuils, 100
        )
        self.assertEqual(resultat, 50)

    def test_prefixe_le_plus_specifique_gagne(self):
        """Le préfixe le plus long (le plus spécifique) doit gagner."""
        seuils = {
            os.path.normpath("D:\\Projets"): 50,
            os.path.normpath("D:\\Projets\\Client"): 10,
        }
        resultat = obtenir_seuil_pour_chemin(
            os.path.normpath("D:\\Projets\\Client\\Fichiers"), seuils, 100
        )
        self.assertEqual(resultat, 10)

    def test_prefixe_partiel_ne_matche_pas(self):
        """Un préfixe partiel de nom de dossier ne doit pas matcher."""
        seuils = {os.path.normpath("D:\\Pro"): 50}
        resultat = obtenir_seuil_pour_chemin(
            os.path.normpath("D:\\Projets\\Test"), seuils, 100
        )
        self.assertEqual(resultat, 100)


if __name__ == "__main__":
    unittest.main()
