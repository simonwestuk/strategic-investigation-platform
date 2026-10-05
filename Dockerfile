# syntax=docker/dockerfile:1
#
# API image: FastAPI + LangGraph backend (package `sip`).
#   docker build -t sip-api .
# Runtime contract: `sip db upgrade` runs on start (disable with SIP_RUN_MIGRATIONS=false), then `sip serve`.

ARG PYTHON_VERSION=3.12

# ---- build: install the package and its dependencies into an isolated virtualenv ------------
# NOTE: `sip.config.REPO_ROOT` is derived from the location of config.py (parents[2]) and is used to find
# alembic.ini, migrations/ and data/. A regular `pip install .` would put config.py in site-packages and
# break that lookup, so the package is installed in editable mode from /app/src and the runtime stage keeps
# the identical /app layout (SIP_REPO_ROOT can override the root for a non-editable install). The `azure`
# extra adds the Application Insights exporter.
FROM python:${PYTHON_VERSION}-slim AS build
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install -e ".[azure]"

# ---- runtime: slim image, no build tooling, non-root ----------------------------------------
FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SIP_ENV=local \
    SIP_LOG_JSON=true \
    SIP_DATA_DIR=/app/data/synthetic \
    SIP_VAR_DIR=/app/var \
    SIP_RUN_MIGRATIONS=true

RUN groupadd --system --gid 10001 sip \
 && useradd --system --uid 10001 --gid sip --home-dir /app --no-create-home --shell /usr/sbin/nologin sip

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build /app/src ./src
# Synthetic scenario data (offline demo / evaluation) and Alembic migrations, resolved relative to /app.
COPY pyproject.toml alembic.ini ./
COPY migrations ./migrations
COPY data ./data
COPY --chmod=0755 infra/docker/api-entrypoint.sh /usr/local/bin/api-entrypoint.sh

# var/ holds the local raw-content quarantine and (SQLite mode only) databases; owner-only permissions.
RUN mkdir -p /app/var && chown -R sip:sip /app/var && chmod 0700 /app/var

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

ENTRYPOINT ["/usr/local/bin/api-entrypoint.sh"]
CMD ["sip", "serve", "--host", "0.0.0.0", "--port", "8000"]
