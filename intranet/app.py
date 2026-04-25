"""
Module Intranet - Application Flask pour l'interface d'administration.
Fournit un dashboard, l'historique des dossiers et la configuration.
"""

import os
import dotenv

from version import __version__
from flask import Flask, redirect, render_template, request, url_for, flash
from flask_login import (  # type: ignore[import-untyped]
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)


class Admin(UserMixin):
    """
    Modèle utilisateur simple pour l'authentification admin.
    Un seul utilisateur est supporté (défini dans le .env).
    """

    def __init__(self, id: str):
        self.id = id


def creer_app() -> Flask:
    """
    Factory Flask : crée et configure l'application Intranet.
    """
    # Charger le .env s'il ne l'est pas déjà (utile si lancé sans main.py)
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    if os.path.exists(env_path):
        dotenv.load_dotenv(env_path)

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    # Injection globale de la version
    app.jinja_env.globals["DS_VERSION"] = __version__

    app.config["SECRET_KEY"] = os.getenv("INTRA_SECRET_KEY", "change-me-in-production")
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    @app.template_filter("format_size")
    def format_size(kb: float | int | None) -> str:
        """Formate une taille en Ko vers l'unité la plus appropriée (Ko, Mo, Go, To)."""
        if kb is None:
            return "—"
        units = ["Ko", "Mo", "Go", "To", "Po"]
        size = float(kb)
        is_negative = size < 0
        abs_size = abs(size)
        unit_idx = 0
        while abs_size >= 1024 and unit_idx < len(units) - 1:
            abs_size /= 1024
            unit_idx += 1

        # Formatage avec le signe original
        final_val = abs_size
        if unit_idx >= 2:
            res = f"{final_val:.2f} {units[unit_idx]}"
        elif unit_idx == 1:
            res = f"{final_val:.1f} {units[unit_idx]}"
        else:
            res = f"{int(final_val)} {units[unit_idx]}"

        res = res.replace(".", ",")
        return f"-{res}" if is_negative else res

    # --- Flask-Login ---
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = "login"
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def charger_utilisateur(user_id):
        admin_user = os.getenv("INTRA_ADMIN_USER", "admin")
        if user_id == admin_user:
            return Admin(user_id)
        return None

    # --- Routes ---

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")

            admin_user = os.getenv("INTRA_ADMIN_USER", "admin")
            admin_pwd = os.getenv("INTRA_ADMIN_PWD", "admin")

            if username == admin_user and password == admin_pwd:
                user = Admin(username)
                login_user(user)
                # Redirige vers la page demandée ou le dashboard
                next_page = request.args.get("next")
                return redirect(next_page or url_for("dashboard"))
            else:
                flash("Identifiants incorrects.", "error")

        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        from intranet.queries import get_stats_dashboard

        stats = get_stats_dashboard()
        return render_template("dashboard.html", stats=stats)

    @app.route("/history")
    @login_required
    def history():
        from intranet.queries import get_dossiers_racines

        racines = get_dossiers_racines()
        return render_template("history.html", racines=racines)

    @app.route("/scans")
    @login_required
    def scans():
        from intranet.queries import get_scans_history

        # On limite aux 50 derniers scans pour l'affichage
        liste_scans = get_scans_history(limit=50)
        return render_template("scans.html", scans=liste_scans)

    @app.route("/api/enfants")
    @login_required
    def api_enfants():
        from flask import jsonify, request as req
        from intranet.queries import get_enfants_dossier

        parent_path = req.args.get("path", "")
        if not parent_path:
            return jsonify([])
        return jsonify(get_enfants_dossier(parent_path))

    @app.route("/api/historique/<int:id_folder>")
    @login_required
    def api_historique(id_folder: int):
        from flask import jsonify, request as req
        from intranet.queries import get_historique_dossier

        periode = req.args.get("periode", "30")
        data = get_historique_dossier(id_folder, periode)
        return jsonify(data)

    @app.route("/api/recherche")
    @login_required
    def api_recherche():
        from flask import jsonify, request as req
        from intranet.queries import rechercher_dossiers

        q = req.args.get("q", "").strip()
        if len(q) < 2:
            return jsonify([])
        return jsonify(rechercher_dossiers(q))

    @app.route("/api/scan-details/<int:id_scan>")
    @login_required
    def api_scan_details(id_scan: int):
        from flask import jsonify
        from intranet.queries import get_scan_details

        data = get_scan_details(id_scan)
        if not data:
            return jsonify({"error": "Scan introuvable"}), 404
        return jsonify(data)

    @app.route("/plugins")
    @login_required
    def plugins():
        import plugin_loader

        # Initialise le registre si le dossier_app n'a pas encore été défini
        if not plugin_loader._DOSSIER_APP:
            plugin_loader.charger_plugins(os.path.dirname(os.path.dirname(__file__)))

        registre = plugin_loader.get_registre()
        return render_template("plugins.html", registre=registre)

    @app.route("/api/plugins")
    @login_required
    def api_plugins_list():
        from flask import jsonify
        import plugin_loader

        if not plugin_loader._DOSSIER_APP:
            plugin_loader.charger_plugins(os.path.dirname(os.path.dirname(__file__)))

        return jsonify(plugin_loader.get_registre())

    @app.route("/api/plugins/<nom>/activer", methods=["POST"])
    @login_required
    def api_plugin_activer(nom: str):
        from flask import jsonify
        import plugin_loader

        if not plugin_loader._DOSSIER_APP:
            plugin_loader.charger_plugins(os.path.dirname(os.path.dirname(__file__)))

        resultat = plugin_loader.activer_plugin(nom)
        return jsonify(resultat)

    @app.route("/api/plugins/<nom>/desactiver", methods=["POST"])
    @login_required
    def api_plugin_desactiver(nom: str):
        from flask import jsonify
        import plugin_loader

        if not plugin_loader._DOSSIER_APP:
            plugin_loader.charger_plugins(os.path.dirname(os.path.dirname(__file__)))

        resultat = plugin_loader.desactiver_plugin(nom)
        return jsonify(resultat)

    @app.route("/api/plugins/recharger", methods=["POST"])
    @login_required
    def api_plugins_recharger():
        from flask import jsonify
        import plugin_loader

        if not plugin_loader._DOSSIER_APP:
            plugin_loader.charger_plugins(os.path.dirname(os.path.dirname(__file__)))

        plugin_loader.recharger_plugins()
        return jsonify({"ok": True, "registre": plugin_loader.get_registre()})

    @app.route("/settings", methods=["GET", "POST"])
    @login_required
    def settings():
        from datetime import datetime

        env_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

        if request.method == "POST":

            # Vérification que le .env est accessible en écriture
            # (en Docker, s'assurer que le volume n'est PAS monté en :ro)
            if not os.access(env_file, os.W_OK):
                flash(
                    "Impossible d'écrire dans le fichier .env : "
                    "vérifiez que le volume Docker n'est pas monté en lecture seule (:ro).",
                    "error",
                )
                return redirect(url_for("settings"))

            def _save(key, val):
                """
                Écrit clé=valeur directement dans le .env (lecture → modif → écriture en place).
                Évite le rename atomique de dotenv.set_key() qui échoue sur les fichiers
                bind-mountés dans Docker Linux (EBUSY / inode verrouillé).
                """
                try:
                    with open(env_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except FileNotFoundError:
                    lines = []

                key_found = False
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    # Ligne correspondant à la clé (avec ou sans espace autour du =)
                    if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                        new_lines.append(f"{key}={val}\n")
                        key_found = True
                    else:
                        new_lines.append(line)

                if not key_found:
                    # Clé absente : on l'ajoute en fin de fichier
                    new_lines.append(f"{key}={val}\n")

                # Écriture directe en place (pas de fichier temporaire)
                with open(env_file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)

                os.environ[key] = val

            try:
                # --- Base de données ---
                _save("DB_HOST", request.form.get("db_host", "localhost"))
                _save("DB_PORT", request.form.get("db_port", "3306"))
                _save("DB_USER", request.form.get("db_user", "root"))
                _save("DB_NAME", request.form.get("db_name", "superviseur_dossiers"))
                pwd = request.form.get("db_password", "")
                if pwd:  # Ne remplace le mot de passe que s'il est renseigné
                    _save("DB_PASSWORD", pwd)

                # --- Teams ---
                _save("TEAMS_WEBHOOK_URL", request.form.get("teams_webhook", ""))

                # --- Planning ---
                _save("HEURE_SCAN", request.form.get("heure_scan", "17:30"))
                _save("DELAI_VERIFICATION", request.form.get("delai_verification", "300"))

                # --- Chemins racines (liste → CSV) ---
                racines = [
                    c.strip()
                    for c in request.form.get("chemins_racines", "").split("\n")
                    if c.strip()
                ]
                _save("CHEMINS_RACINES", ",".join(racines))

                # --- Chemins exclus (liste → CSV) ---
                exclus = [
                    c.strip()
                    for c in request.form.get("chemins_exclus", "").split("\n")
                    if c.strip()
                ]
                _save("CHEMINS_EXCLUS", ",".join(exclus))

                # --- Seuils ---
                _save("SEUIL_DEFAUT", request.form.get("seuil_defaut", "100"))

                chemins_seuil = request.form.getlist("custom_path[]")
                valeurs_seuil = request.form.getlist("custom_val[]")
                seuils_valides = [
                    f"{c.strip()}={v.strip()}"
                    for c, v in zip(chemins_seuil, valeurs_seuil)
                    if c.strip() and v.strip()
                ]
                _save("SEUILS_PERSONNALISES", ",".join(seuils_valides))

                # Horodatage de la dernière sauvegarde
                _save("LAST_SAVED", datetime.now().strftime("%Y-%m-%d %H:%M"))

                flash("Configuration sauvegardée avec succès.", "success")

            except OSError as e:
                flash(
                    f"Erreur lors de la sauvegarde du fichier .env : {e}",
                    "error",
                )

            return redirect(url_for("settings"))

        # --- Lecture / préparation des données pour la vue ---
        def _get(key, default=""):
            return os.getenv(key, default)

        chemins_racines = [
            c.strip() for c in _get("CHEMINS_RACINES").split(",") if c.strip()
        ]
        chemins_exclus = [
            c.strip() for c in _get("CHEMINS_EXCLUS").split(",") if c.strip()
        ]

        seuils_perso = []
        for paire in _get("SEUILS_PERSONNALISES").split(","):
            if "=" in paire:
                chemin, val = paire.rsplit("=", 1)
                seuils_perso.append({"path": chemin.strip(), "val": val.strip()})

        ctx = {
            "db_host": _get("DB_HOST", "localhost"),
            "db_port": _get("DB_PORT", "3306"),
            "db_user": _get("DB_USER", "root"),
            "db_name": _get("DB_NAME", "superviseur_dossiers"),
            "teams_webhook": _get("TEAMS_WEBHOOK_URL"),
            "heure_scan": _get("HEURE_SCAN", "17:30"),
            "delai_verification": _get("DELAI_VERIFICATION", "300"),
            "chemins_racines": chemins_racines,
            "chemins_exclus": chemins_exclus,
            "seuil_defaut": _get("SEUIL_DEFAUT", "100"),
            "seuils_perso": seuils_perso,
            "last_saved": _get("LAST_SAVED", "Jamais"),
        }
        return render_template("settings.html", **ctx)

    @app.route("/api/test-db", methods=["POST"])
    @login_required
    def api_test_db():
        from flask import jsonify, request

        try:
            import mysql.connector

            data = request.get_json() or {}

            # Utilise les données du POST, sinon les variables d'env
            host = data.get("host") or os.getenv("DB_HOST", "localhost")
            port = data.get("port") or os.getenv("DB_PORT", "3306")
            user = data.get("user") or os.getenv("DB_USER", "root")
            db_name = data.get("name") or os.getenv("DB_NAME", "superviseur_dossiers")

            # Pour le mot de passe, si c'est vide dans les données reçues, on prend l'env
            # (car l'input sur le front peut être vide pour "ne pas changer")
            password = data.get("password") or os.getenv("DB_PASSWORD", "")

            conn = mysql.connector.connect(
                host=host,
                port=int(port),
                user=user,
                password=password,
                database=db_name,
                connect_timeout=5,
            )
            conn.close()
            return jsonify(
                {"ok": True, "msg": "Connexion à la base de données réussie."}
            )
        except Exception as e:
            return jsonify({"ok": False, "msg": f"Échec : {str(e)}"})

    @app.route("/api/test-teams", methods=["POST"])
    @login_required
    def api_test_teams():
        from flask import jsonify, request
        import urllib.request
        import json as _json

        data = request.get_json() or {}
        url = data.get("webhook") or os.getenv("TEAMS_WEBHOOK_URL", "")

        if not url:
            return jsonify({"ok": False, "msg": "URL du webhook non configurée."})
        try:
            payload = _json.dumps(
                {"text": "✅ Test de notification — SuperviseurDossiers (Live Test)"}
            ).encode()
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                return jsonify(
                    {"ok": True, "msg": f"Notification envoyée (HTTP {resp.status})."}
                )
        except Exception as e:
            return jsonify({"ok": False, "msg": f"Échec : {str(e)}"})

    return app
