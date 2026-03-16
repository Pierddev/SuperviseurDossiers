"""
Module de notifications Microsoft Teams.
"""

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)


def envoyer_notif_teams(message: str) -> None:
    """
    Envoie une notification à Microsoft Teams.
    """
    try:
        url = os.getenv("TEAMS_WEBHOOK_URL")
        headers = {"Content-Type": "application/json"}
        payload = {"text": message}
        response = requests.post(
            url, headers=headers, data=json.dumps(payload), timeout=10
        )
        # Lève une HTTPError si le code de retour est 4xx ou 5xx
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur lors de l'envoi de la notification : {e}")
