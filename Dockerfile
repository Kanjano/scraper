# INSTRINDER — API + web page in one image.
#
#   docker build -t instrinder .
#   docker run -p 8000:8000 --env-file .env -v "$PWD/data:/app/data" instrinder
#
# Multi-arch: on amd64 Google Chrome is installed for the "stealth" shops; on
# arm64 (no Linux Chrome build exists) those shops use patchright's bundled
# Chromium automatically.
FROM python:3.12-slim-bookworm

ARG TARGETARCH
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    MODELS_DIR=/opt/models

WORKDIR /app

# Python deps, then the browsers they drive (Playwright's Chromium with its
# system libraries, and patchright's Chromium for stealth rendering).
COPY requirements.txt .
RUN pip install -r requirements.txt \
 && playwright install --with-deps chromium \
 && patchright install chromium \
 && rm -rf /var/lib/apt/lists/*

# Google Chrome where it exists (amd64): the best disguise for protected shops.
RUN if [ "$TARGETARCH" = "amd64" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends wget ca-certificates \
      && wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
      && apt-get install -y --no-install-recommends /tmp/chrome.deb \
      && rm -f /tmp/chrome.deb && rm -rf /var/lib/apt/lists/*; \
    fi

COPY . .

# The multilingual search model (~240 MB) is baked into the image, outside the
# data volume, so containers start offline and ready.
RUN python -c "from scrapers.relevance import _model; assert _model() is not None" \
 && useradd --create-home --uid 10001 app \
 && mkdir -p /app/data/cache /app/data/logs \
 && chown -R app:app /app /opt/models

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/admin/health-check', timeout=4)"

CMD ["python", "main.py"]
