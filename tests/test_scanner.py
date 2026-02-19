"""
Tests pour la fonction principale scanner.
Vérifie l'orchestration complète du processus de scan.
NB: Ces tests ont été réalisés avec l'aide de l'Intelligence Artificielle.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import scanner


class TestScanner(unittest.TestCase):
    """Tests pour la fonction scanner (orchestration)."""

    @patch("main.deconnecter_base_de_donnees")
    @patch("main.envoyer_notif_teams")
    @patch("main.terminer_scan")
    @patch("main.inserer_ou_mettre_a_jour_dossier")
    @patch("main.calculer_taille_dossier")
    @patch("main.lister_tous_les_dossier")
    @patch("main.creer_scan")
    @patch("main.connecter_base_de_donnees")
    def test_sequence_complete(
        self,
        mock_connect,
        mock_creer,
        mock_lister,
        mock_taille,
        mock_inserer,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le scanner doit suivre la séquence : connecter → créer scan → lister → traiter → terminer → notifier → déconnecter."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_lister.return_value = ["C:\\test"]
        mock_taille.return_value = 0
        mock_inserer.return_value = None

        scanner()

        mock_connect.assert_called_once()
        mock_creer.assert_called_once()
        mock_lister.assert_called_once()
        mock_terminer.assert_called_once()
        mock_notif.assert_called_once()
        mock_deconnect.assert_called_once()

    @patch("main.deconnecter_base_de_donnees")
    @patch("main.envoyer_notif_teams")
    @patch("main.terminer_scan")
    @patch("main.inserer_ou_mettre_a_jour_dossier")
    @patch("main.calculer_taille_dossier")
    @patch("main.lister_tous_les_dossier")
    @patch("main.creer_scan")
    @patch("main.connecter_base_de_donnees")
    def test_scan_termine_avec_statut_termine(
        self,
        mock_connect,
        mock_creer,
        mock_lister,
        mock_taille,
        mock_inserer,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le scan doit être terminé avec le statut 'termine'."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_lister.return_value = []
        mock_inserer.return_value = None

        scanner()

        args = mock_terminer.call_args[0]
        self.assertEqual(args[1], 1)  # id_scan
        self.assertEqual(args[2], "termine")  # statut

    @patch("main.deconnecter_base_de_donnees")
    @patch("main.envoyer_notif_teams")
    @patch("main.terminer_scan")
    @patch("main.inserer_ou_mettre_a_jour_dossier")
    @patch("main.calculer_taille_dossier")
    @patch("main.lister_tous_les_dossier")
    @patch("main.creer_scan")
    @patch("main.connecter_base_de_donnees")
    def test_message_contient_nouveaux_dossiers(
        self,
        mock_connect,
        mock_creer,
        mock_lister,
        mock_taille,
        mock_inserer,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le message Teams doit mentionner les nouveaux dossiers."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_lister.return_value = ["C:\\nouveau"]
        mock_taille.return_value = 200 * 1024 * 1024  # 200 Mo en octets
        mock_inserer.return_value = {
            "type": "nouveau",
            "chemin": "C:\\nouveau",
            "taille": 200,
        }

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("Nouveaux dossiers", message)
        self.assertIn("C:\\nouveau", message)

    @patch("main.deconnecter_base_de_donnees")
    @patch("main.envoyer_notif_teams")
    @patch("main.terminer_scan")
    @patch("main.inserer_ou_mettre_a_jour_dossier")
    @patch("main.calculer_taille_dossier")
    @patch("main.lister_tous_les_dossier")
    @patch("main.creer_scan")
    @patch("main.connecter_base_de_donnees")
    def test_message_contient_dossiers_modifies(
        self,
        mock_connect,
        mock_creer,
        mock_lister,
        mock_taille,
        mock_inserer,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le message Teams doit mentionner les dossiers modifiés."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_lister.return_value = ["C:\\modifie"]
        mock_taille.return_value = 0
        mock_inserer.return_value = {
            "type": "modification",
            "chemin": "C:\\modifie",
            "difference": 150,
        }

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("Dossiers modifiés", message)
        self.assertIn("C:\\modifie", message)
        self.assertIn("+150", message)

    @patch("main.deconnecter_base_de_donnees")
    @patch("main.envoyer_notif_teams")
    @patch("main.terminer_scan")
    @patch("main.inserer_ou_mettre_a_jour_dossier")
    @patch("main.calculer_taille_dossier")
    @patch("main.lister_tous_les_dossier")
    @patch("main.creer_scan")
    @patch("main.connecter_base_de_donnees")
    def test_message_sans_modification(
        self,
        mock_connect,
        mock_creer,
        mock_lister,
        mock_taille,
        mock_inserer,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le message doit indiquer qu'aucun dossier n'a été modifié."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_lister.return_value = ["C:\\stable"]
        mock_taille.return_value = 0
        mock_inserer.return_value = None

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("Aucun dossier modifié ou nouveau", message)

    @patch("main.deconnecter_base_de_donnees")
    @patch("main.envoyer_notif_teams")
    @patch("main.terminer_scan")
    @patch("main.inserer_ou_mettre_a_jour_dossier")
    @patch("main.calculer_taille_dossier")
    @patch("main.lister_tous_les_dossier")
    @patch("main.creer_scan")
    @patch("main.connecter_base_de_donnees")
    def test_message_contient_la_date(
        self,
        mock_connect,
        mock_creer,
        mock_lister,
        mock_taille,
        mock_inserer,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Le message doit contenir la date et l'heure du scan."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_lister.return_value = []
        mock_inserer.return_value = None

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("Scan du", message)

    @patch("main.deconnecter_base_de_donnees")
    @patch("main.envoyer_notif_teams")
    @patch("main.terminer_scan")
    @patch("main.inserer_ou_mettre_a_jour_dossier")
    @patch("main.calculer_taille_dossier")
    @patch("main.lister_tous_les_dossier")
    @patch("main.creer_scan")
    @patch("main.connecter_base_de_donnees")
    def test_signe_negatif_pour_reduction(
        self,
        mock_connect,
        mock_creer,
        mock_lister,
        mock_taille,
        mock_inserer,
        mock_terminer,
        mock_notif,
        mock_deconnect,
    ):
        """Une réduction de taille doit afficher un signe négatif."""
        mock_connect.return_value = MagicMock()
        mock_creer.return_value = 1
        mock_lister.return_value = ["C:\\reduit"]
        mock_taille.return_value = 0
        mock_inserer.return_value = {
            "type": "modification",
            "chemin": "C:\\reduit",
            "difference": -200,
        }

        scanner()

        message = mock_notif.call_args[0][0]
        self.assertIn("-200", message)


if __name__ == "__main__":
    unittest.main()
