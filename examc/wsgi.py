# examc/wsgi.py
import os, sys
from django.core.wsgi import get_wsgi_application
from dotenv import load_dotenv

# Ajoute le projet au PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Charge automatiquement .env.dev si présent (utile en dev local hors Docker)
default_env = os.path.join(os.path.dirname(__file__), "../.env.dev")
if os.path.exists(default_env):
    load_dotenv(default_env)

# Désormais on vise le settings unique
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "examc.settings")

application = get_wsgi_application()
