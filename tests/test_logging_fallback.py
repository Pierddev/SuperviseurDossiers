"""
Tests pour le mécanisme de logging fallback.
Vérifie que lorsque les notifications Teams échouent,
les erreurs sont correctement loguées dans superviseur.log.
NB: Ces tests ont été réalisés avec l'aide de l'Intelligence Artificielle.
"""

import logging
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ajoute le dossier parent au path pour pouvoir importer main
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import envoyer_notif_teams, logger


class TestLoggingFallback(unittest.TestCase):
    """Tests pour le fallback logging quand les notifications Teams échouent."""

    # --- Tests de la configuration du logger ---

    def test_logger_existe(self):
        """Le logger du module main doit exister."""
        self.assertIsNotNone(logger)

    def test_logger_nom_correct(self):
        """Le logger doit porter le nom du module 'main'."""
        self.assertEqual(logger.name, "main")

    def test_logger_niveau_error(self):
        """Le root logger doit être configuré au niveau ERROR."""
        root_logger = logging.getLogger()
        self.assertEqual(root_logger.level, logging.ERROR)

    def test_logger_a_un_file_handler(self):
        """Le root logger doit avoir au moins un FileHandler vers 'superviseur.log'."""
        root_logger = logging.getLogger()
        file_handlers = [
            h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
        ]
        self.assertTrue(
            len(file_handlers) > 0, "Aucun FileHandler trouvé sur le root logger"
        )

    def test_logger_fichier_superviseur_log(self):
        """Le FileHandler doit pointer vers 'superviseur.log'."""
        root_logger = logging.getLogger()
        file_handlers = [
            h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
        ]
        noms_fichiers = [os.path.basename(h.baseFilename) for h in file_handlers]
        self.assertIn("superviseur.log", noms_fichiers)

    def test_logger_format_correct(self):
        """Le format du logger doit contenir asctime, levelname et message."""
        root_logger = logging.getLogger()
        file_handlers = [
            h for h in root_logger.handlers if isinstance(h, logging.FileHandler)
        ]
        for handler in file_handlers:
            fmt = handler.formatter._fmt
            self.assertIn("%(asctime)s", fmt)
            self.assertIn("%(levelname)s", fmt)
            self.assertIn("%(message)s", fmt)

    # --- Tests du fallback : erreur Teams => log dans le fichier ---

    @patch("main.requests.post")
    def test_erreur_connexion_teams_est_loguee(self, mock_post):
        """Quand requests.post lève une exception, l'erreur doit être loguée."""
        from requests.exceptions import ConnectionError

        mock_post.side_effect = ConnectionError("Connexion impossible")

        with patch.object(logger, "error") as mock_logger_error:
            envoyer_notif_teams("Test message")
            mock_logger_error.assert_called_once()
            args = mock_logger_error.call_args[0][0]
            self.assertIn("Erreur lors de l'envoi de la notification", args)

    @patch("main.requests.post")
    def test_erreur_timeout_teams_est_loguee(self, mock_post):
        """Quand requests.post timeout, l'erreur doit être loguée."""
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout("Délai dépassé")

        with patch.object(logger, "error") as mock_logger_error:
            envoyer_notif_teams("Test message")
            mock_logger_error.assert_called_once()
            args = mock_logger_error.call_args[0][0]
            self.assertIn("Erreur lors de l'envoi de la notification", args)

    @patch("main.requests.post")
    def test_erreur_http_teams_est_loguee(self, mock_post):
        """Quand le webhook Teams retourne un code 4xx/5xx, l'erreur doit être loguée."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = __import__(
            "requests"
        ).exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        with patch.object(logger, "error") as mock_logger_error:
            envoyer_notif_teams("Test message")
            mock_logger_error.assert_called_once()
            args = mock_logger_error.call_args[0][0]
            self.assertIn("Erreur lors de l'envoi de la notification", args)

    @patch("main.requests.post")
    def test_pas_de_log_si_teams_ok(self, mock_post):
        """Si la notification Teams réussit, aucune erreur ne doit être loguée."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        with patch.object(logger, "error") as mock_logger_error:
            envoyer_notif_teams("Test message")
            mock_logger_error.assert_not_called()

    @patch("main.requests.post")
    def test_notif_teams_ne_leve_pas_exception(self, mock_post):
        """La fonction envoyer_notif_teams ne doit jamais propager d'exception."""
        from requests.exceptions import ConnectionError

        mock_post.side_effect = ConnectionError("Erreur reseau")
        # Ne doit pas lever d'exception
        try:
            envoyer_notif_teams("Test message")
        except Exception:
            self.fail("envoyer_notif_teams a propagé une exception non gérée")

    @patch("main.requests.post")
    def test_log_contient_details_erreur(self, mock_post):
        """Le message de log doit contenir les détails de l'erreur originale."""
        from requests.exceptions import ConnectionError

        mock_post.side_effect = ConnectionError("DNS resolution failed")

        with patch.object(logger, "error") as mock_logger_error:
            envoyer_notif_teams("Test message")
            args = mock_logger_error.call_args[0][0]
            self.assertIn("DNS resolution failed", args)

    @patch("main.requests.post")
    @patch.dict(os.environ, {"TEAMS_WEBHOOK_URL": ""})
    def test_url_webhook_vide(self, mock_post):
        """Avec une URL webhook vide, la fonction doit gérer l'erreur sans crash."""
        from requests.exceptions import MissingSchema

        mock_post.side_effect = MissingSchema("URL invalide")

        with patch.object(logger, "error") as mock_logger_error:
            envoyer_notif_teams("Test message")
            mock_logger_error.assert_called_once()


if __name__ == "__main__":
    unittest.main()
