"""
Module Intranet - Application Flask pour l'interface d'administration.
Fournit un dashboard, l'historique des dossiers et la configuration.
"""

import os

from flask import Flask, redirect, render_template, request, url_for, flash
from flask_login import (
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
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    app.config["SECRET_KEY"] = os.getenv("INTRA_SECRET_KEY", "change-me-in-production")

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
        return render_template("dashboard.html")

    @app.route("/history")
    @login_required
    def history():
        return render_template("history.html")

    @app.route("/settings")
    @login_required
    def settings():
        return render_template("settings.html")

    return app
