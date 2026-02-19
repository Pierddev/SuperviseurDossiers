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

from main import (
    connecter_base_de_donnees,
    deconnecter_base_de_donnees,
    creer_scan,
    terminer_scan,
    inserer_ou_mettre_a_jour_dossier,
)


class TestConnecterBaseDeDonnees(unittest.TestCase):
    """Tests pour la fonction connecter_base_de_donnees."""

    @patch("main.mysql.connector.connect")
    def test_connexion_reussie(self, mock_connect):
        """Doit retourner un objet connexion si la connexion réussit."""
        mock_connexion = MagicMock()
        mock_connect.return_value = mock_connexion
        resultat = connecter_base_de_donnees()
        self.assertEqual(resultat, mock_connexion)

    @patch("main.mysql.connector.connect")
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

    @patch("main.envoyer_notif_teams")
    @patch("main.mysql.connector.connect")
    def test_connexion_echouee_retourne_none(self, mock_connect, mock_notif):
        """Doit retourner None si la connexion échoue."""
        mock_connect.side_effect = mysql.connector.Error("Connexion refusée")
        resultat = connecter_base_de_donnees()
        self.assertIsNone(resultat)

    @patch("main.envoyer_notif_teams")
    @patch("main.mysql.connector.connect")
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
        self.assertIn("INSERT INTO sudo_scans", requete)
        self.assertIn("en_cours", requete)

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

    @patch("main.envoyer_notif_teams")
    def test_erreur_retourne_none(self, mock_notif):
        """Doit retourner None en cas d'erreur SQL."""
        mock_connexion = MagicMock()
        mock_connexion.cursor.side_effect = mysql.connector.Error("Erreur SQL")

        resultat = creer_scan(mock_connexion)
        self.assertIsNone(resultat)

    @patch("main.envoyer_notif_teams")
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

        terminer_scan(mock_connexion, 42, "termine")
        requete = mock_curseur.execute.call_args[0][0]
        params = mock_curseur.execute.call_args[0][1]
        self.assertIn("UPDATE sudo_scans", requete)
        self.assertEqual(params, ("termine", 42))

    def test_fait_un_commit(self):
        """Doit faire un commit après la mise à jour."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_connexion.cursor.return_value = mock_curseur

        terminer_scan(mock_connexion, 1, "termine")
        mock_connexion.commit.assert_called_once()

    def test_ferme_le_curseur(self):
        """Doit fermer le curseur après l'opération."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_connexion.cursor.return_value = mock_curseur

        terminer_scan(mock_connexion, 1, "termine")
        mock_curseur.close.assert_called_once()

    @patch("main.envoyer_notif_teams")
    def test_erreur_envoie_notification(self, mock_notif):
        """Doit envoyer une notification Teams en cas d'erreur SQL."""
        mock_connexion = MagicMock()
        mock_connexion.cursor.side_effect = mysql.connector.Error("Erreur SQL")

        terminer_scan(mock_connexion, 1, "termine")
        mock_notif.assert_called_once()
        self.assertIn(
            "Erreur lors de la terminaison du scan", mock_notif.call_args[0][0]
        )


class TestInsererOuMettreAJourDossier(unittest.TestCase):
    """Tests pour la fonction inserer_ou_mettre_a_jour_dossier."""

    def _mock_connexion_nouveau_dossier(self):
        """Crée un mock pour le cas d'un nouveau dossier (SELECT retourne None)."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        mock_curseur.fetchone.return_value = None  # dossier n'existe pas
        mock_curseur.lastrowid = 1
        mock_connexion.cursor.return_value = mock_curseur
        return mock_connexion, mock_curseur

    def _mock_connexion_dossier_existant(self, taille_actuelle=50):
        """Crée un mock pour le cas d'un dossier existant."""
        mock_connexion = MagicMock()
        mock_curseur = MagicMock()
        # Premier fetchone: SELECT sudo_dossiers (id=1, chemin, est_nouveau=0)
        # Deuxième fetchone: SELECT sudo_tailles (id=1, taille_actuel, taille_dernier)
        mock_curseur.fetchone.side_effect = [
            (1, "C:\\test", 0),  # sudo_dossiers
            (1, taille_actuelle, None),  # sudo_tailles
        ]
        mock_connexion.cursor.return_value = mock_curseur
        return mock_connexion, mock_curseur

    @patch.dict(os.environ, {"MODIFICATION_TAILLE_IMPORTANTE": "100"})
    def test_nouveau_dossier_petit_retourne_none(self):
        """Un nouveau dossier sous le seuil ne doit pas déclencher de notification."""
        mock_connexion, _ = self._mock_connexion_nouveau_dossier()
        resultat = inserer_ou_mettre_a_jour_dossier(mock_connexion, "C:\\test", 50)
        self.assertIsNone(resultat)

    @patch.dict(os.environ, {"MODIFICATION_TAILLE_IMPORTANTE": "100"})
    def test_nouveau_dossier_gros_retourne_dict(self):
        """Un nouveau dossier au-dessus du seuil doit retourner un dictionnaire."""
        mock_connexion, _ = self._mock_connexion_nouveau_dossier()
        resultat = inserer_ou_mettre_a_jour_dossier(mock_connexion, "C:\\gros", 200)
        self.assertIsNotNone(resultat)
        self.assertEqual(resultat["type"], "nouveau")
        self.assertEqual(resultat["chemin"], "C:\\gros")
        self.assertEqual(resultat["taille"], 200)

    @patch.dict(os.environ, {"MODIFICATION_TAILLE_IMPORTANTE": "100"})
    def test_nouveau_dossier_insere_dans_deux_tables(self):
        """Un nouveau dossier doit être inséré dans sudo_dossiers ET sudo_tailles."""
        mock_connexion, mock_curseur = self._mock_connexion_nouveau_dossier()
        inserer_ou_mettre_a_jour_dossier(mock_connexion, "C:\\test", 50)
        requetes = [appel[0][0] for appel in mock_curseur.execute.call_args_list]
        self.assertTrue(any("INSERT INTO sudo_dossiers" in r for r in requetes))
        self.assertTrue(any("INSERT INTO sudo_tailles" in r for r in requetes))

    @patch.dict(os.environ, {"MODIFICATION_TAILLE_IMPORTANTE": "100"})
    def test_dossier_existant_petite_modif_retourne_none(self):
        """Une modification sous le seuil ne doit pas déclencher de notification."""
        mock_connexion, _ = self._mock_connexion_dossier_existant(taille_actuelle=50)
        resultat = inserer_ou_mettre_a_jour_dossier(mock_connexion, "C:\\test", 60)
        self.assertIsNone(resultat)

    @patch.dict(os.environ, {"MODIFICATION_TAILLE_IMPORTANTE": "100"})
    def test_dossier_existant_grosse_modif_retourne_dict(self):
        """Une modification au-dessus du seuil doit retourner un dictionnaire."""
        mock_connexion, _ = self._mock_connexion_dossier_existant(taille_actuelle=50)
        resultat = inserer_ou_mettre_a_jour_dossier(mock_connexion, "C:\\test", 200)
        self.assertIsNotNone(resultat)
        self.assertEqual(resultat["type"], "modification")
        self.assertEqual(resultat["chemin"], "C:\\test")
        self.assertEqual(resultat["difference"], 150)  # 200 - 50

    @patch.dict(os.environ, {"MODIFICATION_TAILLE_IMPORTANTE": "100"})
    def test_dossier_existant_reduction_taille(self):
        """Une réduction de taille au-dessus du seuil doit aussi être détectée."""
        mock_connexion, _ = self._mock_connexion_dossier_existant(taille_actuelle=300)
        resultat = inserer_ou_mettre_a_jour_dossier(mock_connexion, "C:\\test", 100)
        self.assertIsNotNone(resultat)
        self.assertEqual(resultat["difference"], -200)  # 100 - 300

    @patch.dict(os.environ, {"MODIFICATION_TAILLE_IMPORTANTE": "100"})
    def test_fait_un_commit(self):
        """Doit faire un commit après l'opération."""
        mock_connexion, _ = self._mock_connexion_nouveau_dossier()
        inserer_ou_mettre_a_jour_dossier(mock_connexion, "C:\\test", 50)
        mock_connexion.commit.assert_called()

    @patch.dict(os.environ, {"MODIFICATION_TAILLE_IMPORTANTE": "100"})
    @patch("main.envoyer_notif_teams")
    def test_erreur_sql_envoie_notification(self, mock_notif):
        """Doit envoyer une notification Teams en cas d'erreur SQL."""
        mock_connexion = MagicMock()
        mock_connexion.cursor.side_effect = mysql.connector.Error("Erreur SQL")
        inserer_ou_mettre_a_jour_dossier(mock_connexion, "C:\\test", 50)
        mock_notif.assert_called_once()
        self.assertIn("Erreur lors de l'insertion", mock_notif.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
