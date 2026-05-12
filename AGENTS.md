# SuperviseurDossiers — Agent Guide

## Entrypoints
- `main.py` — CLI entrypoint. Modes: default (scheduled loop), `--scan-now`, `--run-plugin <name>`
- `intranet/app.py` — Flask factory `creer_app()` for web admin UI (requires `INTRANET_ENABLED=1`)

## Dev commands
```powershell
.venv\Scripts\activate
pip install -r requirements.txt
python main.py                    # scheduled mode (default)
python main.py --scan-now        # one-shot scan + exit
python main.py --run-plugin X    # run plugin's executer() + exit
```

## Verification commands (CI order: lint → typecheck → test → coverage)
```powershell
ruff check .
mypy .
pytest -v
coverage run -m pytest; coverage report
```

## Single test file
```powershell
python -m unittest tests.test_systeme_fichiers -v
```

## Project structure
- `main.py` — scheduler loop, arg parsing, retry plugin loader, startup notification
- `scanner.py` — orchestrates scan: BDD → walk filesystem → detect changes → notify Teams
- `db.py` — MariaDB CRUD (tables: `folders`, `scans`, `sizes`)
- `fichiers.py` — filesystem walk + parallel file size via `ThreadPoolExecutor` (8 threads by default)
- `notifications.py` — Teams webhook POST
- `plugin_loader.py` — dynamic `importlib` plugin loading from `plugins/` dir
- `version.py` — just `__version__ = "2.0.0"`

## Framework & quirks
- **No `pyproject.toml` or `setup.cfg`**. Single-module layout, not a package.
- **`.env` re-read at runtime** — `main.py` reloads env every `DELAI_VERIFICATION` seconds with `dotenv.load_dotenv(override=True)`. Changes to `HEURE_SCAN`/`DELAI_VERIFICATION` apply live.
- **`NB_THREADS_SCAN` read at import time** in `fichiers.py` — env changes won't take effect without restart.
- **Logging**: only `ERROR` level to `superviseur.log`. Third-party loggers (`werkzeug`, `flask`, `livereload`, etc.) suppressed.
- **Flask debug mode** (`FLASK_DEBUG=1`): uses `livereload` server → hot-reload templates/static/`.env`. Scheduler runs in a separate thread. Disabled in frozen `.exe`.

## Plugin system
- Each `.py` in `plugins/` must define `configurer(dossier_app)`, `planifier(scheduler)`, `afficher_statut()`.
- Optional `executer()` needed for `--run-plugin`.
- Retry: up to 5 attempts, 60s apart, if plugins fail to load at startup.
- `plugins/` is gitignored.

## Tests
- `unittest` framework (no pytest fixtures).
- Filesystem tests use `tempfile.mkdtemp()` + `shutil.rmtree` in setUp/tearDown.
- `test_base_de_donnees.py` and `test_queries.py` require live MariaDB.
- Test coverage skip: `tests/*`, temp dirs (`.coveragerc`).

## Docker
- `python:3.12-slim` base. Requires `libmariadb-dev-compat` for mysql-connector.
- `requirements-docker.txt` — no Windows-only packages (no PyInstaller).
- `.env` mounted as volume (must be writable for settings UI).
- **Timezone must be set**: `TZ=Europe/Paris` env var, otherwise `schedule` lib uses UTC.

## Windows deployment
- Built with PyInstaller: `exe_generator.bat` (or manual `pyinstaller --onefile ...`).
- Runs as Windows scheduled task at boot.
- **Must use domain user** (not SYSTEM) to access UNC paths (`\\server\share`).
- Recommended boot delay: 2-3 minutes for network initialization.

## Database
- MariaDB, 3 tables: `folders(path, is_new, is_deleted, is_root)`, `scans(date_, date_end, status, total_folders, total_size_kb)`, `sizes(id_scan, id_folder, size_kb)`.
- Migration: `mariadb -u root -p < sql/migration.sql`
- Orphaned scans (status `in_progress` from crash) cleaned on startup.
