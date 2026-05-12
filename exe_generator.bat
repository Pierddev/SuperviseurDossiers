@echo off
echo === Mise a jour du Superviseur de Dossiers ===

REM Arrête le processus en cours s'il tourne
taskkill /IM SuperviseurDossiers.exe /F 2>nul

REM Met à jour le dépôt
git pull

REM Crée le venv si nécessaire et installe les dépendances
if not exist ".venv" python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

REM Génère le nouvel exe (avec openpyxl, locales MySQL et ressources intranet)
.venv\Scripts\pyinstaller --onefile --name SuperviseurDossiers --icon=icone.ico --hidden-import openpyxl --collect-all mysql.connector --add-data "intranet/templates;intranet/templates" --add-data "intranet/static;intranet/static" main.py

REM Copie le nouvel exe à côté de ce script
@REM copy /Y dist\SuperviseurDossiers.exe \\server\user\me\SuperviseurDossiers
@REM copy /Y .env.example \\server\user\me\SuperviseurDossiers
@REM rename \\server\user\me\SuperviseurDossiers\.env.example .env

REM Copie le dossier des plugins
@REM xcopy /S /I /Y plugins \\server\user\me\SuperviseurDossiers\plugins

echo === Mise a jour terminee ===
pause
