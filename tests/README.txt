==============================
  Tests - Superviseur Dossiers
==============================

Les tests se trouvent dans le dossier tests/.
Chaque fichier de test commence par le préfixe "test_".

--- Prérequis ---
- Avoir le venv activé ou utiliser .venv\Scripts\python.exe

--- Commandes ---

Lancer TOUS les tests :
  .venv\Scripts\python.exe -m unittest discover -s tests -v

Lancer un fichier de test spécifique :
  .venv\Scripts\python.exe -m unittest tests.test_logging_fallback -v

--- Ajouter un nouveau test ---

1. Créer un fichier dans tests/ avec le préfixe "test_" (ex: test_scanner.py)
2. La commande "discover" le détectera automatiquement
