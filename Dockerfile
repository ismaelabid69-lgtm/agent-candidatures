# ---- Image de base : Python léger (Debian "slim") ----
FROM python:3.12-slim

# Pas de fichiers .pyc, logs affichés immédiatement, heure de Paris
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Paris \
    DOSSIER_DONNEES=/data

WORKDIR /app

# 1) Les dépendances d'abord : Docker garde cette étape en cache
#    tant que requirements.txt ne change pas (builds beaucoup plus rapides)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2) Puis le code
COPY *.py modele_mail.txt ./

# Sécurité : on ne tourne pas en root dans le conteneur
RUN useradd --create-home --uid 1000 agent \
    && mkdir -p /data && chown agent:agent /data
USER agent

EXPOSE 8000

# Docker vérifie toutes les 30 s que l'API répond (statut "healthy")
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/sante', timeout=4)"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
