# Instrinder — Strumenti Musicali Price Scraper

> Applicazione full-stack per cercare e confrontare in tempo reale i prezzi di strumenti musicali sui principali negozi online italiani ed europei.

Instrinder esegue uno **scraping parallelo** su sette store, normalizza i risultati, calcola gli sconti, applica eventuali link referral e mostra i prodotti ordinati per pertinenza e prezzo. È composta da un backend **Flask** (REST API + scraping) e da una **Single Page Application Angular 17** servita come asset statico in produzione.

---

## Indice

1. [Funzionalità principali](#funzionalità-principali)
2. [Stack tecnologico](#stack-tecnologico)
3. [Architettura](#architettura)
4. [Struttura del repository](#struttura-del-repository)
5. [Requisiti](#requisiti)
6. [Installazione e avvio locale](#installazione-e-avvio-locale)
7. [Variabili d'ambiente](#variabili-dambiente)
8. [Comandi CLI](#comandi-cli)
9. [API REST](#api-rest)
10. [Negozi supportati](#negozi-supportati)
11. [Frontend Angular](#frontend-angular)
12. [Database e migrazioni](#database-e-migrazioni)
13. [Sistema referral](#sistema-referral)
14. [Testing](#testing)
15. [Deploy](#deploy)
16. [Contribuire](#contribuire)
17. [Licenza](#licenza)

---

## Funzionalità principali

- **Ricerca parallela** su 7 negozi (IT/DE/UK) con `ThreadPoolExecutor` e timeout per sito configurabile.
- **Normalizzazione query** (lowercase, rimozione accenti, stopwords italiane) e **fuzzy matching** con `rapidfuzz` per gestire typo e varianti morfologiche.
- **Modalità ricerca strict / fuzzy**: se il filtro strict restituisce meno di `STRICT_MIN_RESULTS` (5) item, il backend ricade automaticamente su un ranking fuzzy senza interrompere l'esperienza utente.
- **Calcolo sconti** con confronto fra prezzo corrente e prezzo originale, esposto come campo `sconto_percentuale`.
- **Top Discounts**: i 10 prodotti con lo sconto percentuale più alto vengono restituiti come lista separata.
- **Suggerimenti di ricerca** basati sullo storico delle query salvate.
- **Autenticazione** con sessione Flask-Login: signup/login email+password (hash `pbkdf2:sha256`) e **OAuth** Google / Facebook / X (Twitter) via Authlib.
- **Cronologia ricerche** per utente loggato.
- **Newsletter settimanale** opt-in con i migliori sconti sui prodotti cercati dall'utente (comando Flask CLI).
- **Sistema referral** plug-in: i link verso gli store vengono riscritti in link affiliato se presenti nel DB JSON.
- **Frontend SPA Angular 17** standalone (signals, control-flow `@if`/`@for`, route guard) servito da Flask in produzione.

---

## Stack tecnologico

**Backend**
- Python 3.9
- Flask 2.2, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-Login, Flask-CORS
- Authlib (OAuth 1.0a / OIDC)
- SQLite (default) — `instance/scraper.db`
- `requests` + `BeautifulSoup` + `curl_cffi` per scraping HTTP
- `selenium` + `undetected-chromedriver` (legacy, attualmente non più richiesti dagli scraper in produzione)
- `rapidfuzz` per fuzzy matching
- Gunicorn come WSGI server

**Frontend**
- Angular 17 (standalone components, signals)
- RxJS 7
- TypeScript 5.4

**Infrastruttura**
- Docker (`Dockerfile` + `docker-compose.yml`)
- Render.com (`render.yaml`) o Heroku (`Procfile`)

---

## Architettura

```
┌──────────────────────┐       HTTPS        ┌────────────────────────────┐
│   Browser            │ ─────────────────► │   Flask app (app.py)        │
│   Angular SPA        │                    │                              │
│   /static/index.html │ ◄───── JSON ────── │   /api/* endpoints           │
└──────────────────────┘                    │   /login/<provider>          │
                                            │                              │
                                            │   ┌──────────────────────┐   │
                                            │   │ scraper_service      │   │
                                            │   │  ThreadPoolExecutor  │   │
                                            │   │  + retry + lock UC   │   │
                                            │   └────────┬─────────────┘   │
                                            │            │                  │
                                            │  ┌─────────┼──────────┐       │
                                            │  ▼         ▼          ▼       │
                                            │ scraper_thomann   ...   scraper_strumentimusicali
                                            │            │                  │
                                            │   ┌────────▼─────────┐        │
                                            │   │ search_normalizer │        │
                                            │   │ (rapidfuzz)       │        │
                                            │   └───────────────────┘        │
                                            │            │                  │
                                            │   ┌────────▼─────────┐        │
                                            │   │ ReferralDBManager │        │
                                            │   │ (data/referral_*) │        │
                                            │   └───────────────────┘        │
                                            │            │                  │
                                            │   ┌────────▼─────────┐        │
                                            │   │ SQLAlchemy        │        │
                                            │   │ instance/scraper.db│       │
                                            │   └───────────────────┘        │
                                            └──────────────────────────────┘
```

### Pipeline di una richiesta `POST /api/search`

1. `normalize_query` ripulisce la query (accenti, stopwords).
2. `run_all_scrapers` lancia i 7 scraper in parallelo (`MAX_WORKERS` default 8, timeout per sito `SCRAPER_TIMEOUT` default 90s) e raccoglie sia i risultati sia le statistiche per sito (`ok` / `errore` / `timeout`).
3. `calculate_discounts` aggiunge `sconto_percentuale` a ciascun item.
4. `apply_referral_links` sostituisce i link con quelli affiliati se mappati nel DB referral.
5. `filter_and_rank_results` applica il filtro strict-or-fuzzy e ordina per `relevance_score` decrescente, poi prezzo crescente.
6. `get_top_discounts` estrae i 10 prodotti con sconto più alto.
7. Se l'utente è loggato, la query viene registrata in `SearchHistory`.
8. Risposta JSON con `results`, `top_discounts`, `stats`, `search_mode`, `count`, `normalized_query`.

---

## Struttura del repository

```
.
├── backend/                          # API Flask + scraper
│   ├── app.py                        # bootstrap Flask, routing, OAuth, API
│   ├── scraper_service.py            # orchestrazione parallela degli scraper
│   ├── scraper_*.py                  # uno per ogni store supportato
│   ├── search_normalizer.py          # normalizzazione + fuzzy matching
│   ├── browser_manager.py            # wrapper undetected-chromedriver (legacy)
│   ├── cache_manager.py              # cleanup cache UC
│   ├── captcha_solver.py             # gestione CAPTCHA (legacy)
│   ├── referral_db_manager.py        # DB JSON dei link referral
│   ├── referral_manager.py           # logica costruzione referral dinamica
│   ├── newsletter_manager.py         # invio newsletter settimanale
│   ├── models.py                     # SQLAlchemy: User, SearchHistory
│   ├── migrations/                   # Alembic (Flask-Migrate)
│   ├── tests/                        # pytest: API, scraper service, normalizer
│   ├── translations/                 # IT, EN, DE, FR, ES (legacy Jinja)
│   ├── static/                       # bundle Angular (popolato in build)
│   ├── data/referral_links.json      # mapping URL → link affiliato
│   ├── instance/scraper.db           # SQLite (gitignored in prod)
│   ├── gunicorn.conf.py              # config WSGI
│   ├── pytest.ini
│   └── requirements.txt
│
├── frontend/                         # SPA Angular 17
│   ├── src/
│   │   ├── app/
│   │   │   ├── app.component.*       # shell + navbar
│   │   │   ├── app.config.ts         # provideRouter + provideHttpClient
│   │   │   ├── app.routes.ts         # routing
│   │   │   ├── auth.guard.ts         # CanActivateFn
│   │   │   ├── components/
│   │   │   │   ├── home/             # ricerca + multi-select store
│   │   │   │   ├── results/          # risultati, filtro per store, paginazione
│   │   │   │   ├── login/
│   │   │   │   ├── signup/
│   │   │   │   └── profile/
│   │   │   ├── services/
│   │   │   │   ├── api.service.ts    # wrapper HTTP
│   │   │   │   └── auth.service.ts   # signal currentUser
│   │   │   └── models/               # interfacce TS
│   │   ├── index.html
│   │   ├── main.ts
│   │   └── styles.css
│   ├── angular.json
│   ├── package.json
│   └── tsconfig*.json
│
├── docs/                             # documentazione di feature/frontend
│   ├── FRONTEND_DOCS.md
│   └── NEW_FEATURES.md
│
├── Dockerfile                        # immagine Python 3.9 + Chromium
├── docker-compose.yml
├── render.yaml                       # blueprint Render.com (FE build + BE)
├── Procfile                          # Heroku-style (gunicorn)
├── runtime.txt                       # python-3.9.18
└── README.md
```

---

## Requisiti

- **Python** 3.9+ (consigliato 3.9.18 per parità con la produzione su Render).
- **Node.js** 20.x (per build del frontend).
- **Chrome / Chromium** installato a livello di sistema (solo se si riattivano scraper Selenium; quelli in produzione sono ora interamente HTTP).
- Connessione Internet.

---

## Installazione e avvio locale

### 1. Clone

```bash
git clone https://github.com/Kanjano/scraper.git
cd scraper
```

### 2. Backend

```bash
python -m venv venv
source venv/bin/activate          # macOS/Linux
# .\venv\Scripts\activate         # Windows

cd backend
pip install -r requirements.txt
flask db upgrade                  # applica le migrazioni Alembic
python app.py                     # in ascolto su http://localhost:5001
```

In produzione il punto d'ingresso è gunicorn:

```bash
gunicorn app:app -c gunicorn.conf.py
```

### 3. Frontend

In una seconda shell:

```bash
cd frontend
npm ci
npm start                         # dev server su http://localhost:4200
```

Il dev server Angular si appoggia al backend Flask sulla porta 5001 — assicurati che sia attivo. In sviluppo puoi configurare un proxy Angular oppure servirti del CORS già abilitato (`flask-cors` su `/api/*`).

### 4. Build di produzione (FE + BE serviti da Flask)

Replica esattamente quello che fa Render:

```bash
cd frontend && npm ci && npm run build
cd ..
rm -rf backend/static && mkdir -p backend/static
cp -r frontend/dist/frontend/browser/* backend/static/
cd backend && gunicorn app:app -c gunicorn.conf.py
```

A questo punto l'app (SPA + API) è disponibile sulla porta gestita da gunicorn. La rotta catch-all in `app.py` serve `index.html` per qualunque path non statico e non sotto `/api/`.

---

## Variabili d'ambiente

Crea un file `.env` nella root (caricato da `python-dotenv`):

| Variabile | Obbligatoria | Default | Descrizione |
|-----------|--------------|---------|-------------|
| `SECRET_KEY` | sì in produzione | `dev-fallback-non-sicuro` | Chiave Flask per cookie/sessione. |
| `MAX_WORKERS` | no | `8` | Worker `ThreadPoolExecutor` per scraping. |
| `SCRAPER_TIMEOUT` | no | `90` | Timeout (s) per singolo scraper. |
| `EMAIL_SENDER` | per `/api/contacts` e newsletter | — | Mittente SMTP Gmail. |
| `EMAIL_PASSWORD` | per `/api/contacts` e newsletter | — | App password Gmail. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | per OAuth Google | — | Credenziali OIDC. |
| `FACEBOOK_CLIENT_ID` / `FACEBOOK_CLIENT_SECRET` | per OAuth Facebook | — | Credenziali Graph API. |
| `TWITTER_CLIENT_ID` / `TWITTER_CLIENT_SECRET` | per OAuth X | — | Credenziali Twitter OAuth 1.0a. |
| `CHROME_VERSION_MAIN` | no | autodetect | Override major version Chrome (per `undetected-chromedriver`). |

Se un provider OAuth non è configurato, `GET /api/auth/oauth/providers` lo segnala come `false` e il frontend nasconde il pulsante.

---

## Comandi CLI

```bash
# applicare le migrazioni
flask db upgrade

# creare una nuova migrazione dopo aver modificato models.py
flask db migrate -m "descrizione"

# invio newsletter settimanale (da schedulare via cron)
flask send-newsletter
```

---

## API REST

Tutti gli endpoint hanno prefisso `/api`. Le risposte sono JSON. I cookie di sessione sono inviati con `credentials: 'include'` lato frontend (`withCredentials: true`).

### Auth

| Metodo | Path | Auth | Descrizione |
|--------|------|------|-------------|
| `POST` | `/api/auth/signup` | no | Registrazione (`email`, `password`, `name`, `surname`, `privacy_accepted`, `newsletter_opt_in`). |
| `POST` | `/api/auth/login` | no | Login email+password. |
| `POST` | `/api/auth/logout` | sì | Logout. |
| `GET` | `/api/auth/me` | no | Restituisce `{authenticated, user}`. |
| `GET` | `/api/auth/oauth/providers` | no | Provider OAuth abilitati `{google, facebook, twitter}`. |

### OAuth (redirect-based, non `/api`)

| Metodo | Path | Descrizione |
|--------|------|-------------|
| `GET` | `/login/<provider>` | Avvia il flow OAuth. |
| `GET` | `/login/<provider>/callback` | Callback di Authlib. Sui fallimenti reindirizza a `/login?error=<codice>&provider=<p>`. |

Codici d'errore standardizzati: `oauth_unsupported_provider`, `oauth_not_configured`, `oauth_client_init_failed`, `oauth_redirect_failed`, `oauth_no_email`, `oauth_unhandled_provider`, `oauth_callback_error`.

### Ricerca

| Metodo | Path | Descrizione |
|--------|------|-------------|
| `POST` | `/api/search` | Body: `{prodotto: string, siti: string[]}`. Restituisce `{results, top_discounts, stats, search_mode, count, normalized_query}`. |
| `POST` | `/api/search/suggestions` | Body: `{query}`. Restituisce `{suggestions[], normalized_query}` basato sullo storico. |

### Contatti

| Metodo | Path | Descrizione |
|--------|------|-------------|
| `POST` | `/api/contacts` | Body: `{nome, email, message}`. Invia email via SMTP Gmail. |

---

## Negozi supportati

Tutti gli scraper in produzione sono HTTP-only (niente Selenium). Ogni scraper espone una funzione `cerca_<nome>(query)` registrata in `scraper_service.ALL_SCRAPERS`.

| Key | Nome visualizzato | Paese | Implementazione |
|-----|-------------------|-------|-----------------|
| `thomann` | Thomann | DE | `requests` + BS4 |
| `musik_produktiv` | Musik Produktiv | DE | `requests` + BS4 |
| `gear4music` | Gear4music | UK | `requests` + BS4 |
| `andertons` | Andertons | UK | `requests` + BS4 |
| `centrochitarre` | Centro Chitarre | IT | `requests` + BS4 |
| `tomassone` | Tomassone | IT | `requests` + BS4 |
| `strumentimusicali` | StrumentiMusicali.net | IT | `requests` + BS4 + cookie di sessione (`strumentimusicali_cookies.json`) |

Output normalizzato per ogni item:

```json
{
  "nome": "Fender Stratocaster ...",
  "prezzo": "€ 1.299,00",
  "prezzo_numerico": 1299.00,
  "prezzo_originale": "€ 1.499,00",
  "prezzo_originale_numerico": 1499.00,
  "sconto_percentuale": 13,
  "link": "https://...",
  "immagine": "https://...",
  "sito": "Thomann",
  "relevance_score": 87
}
```

### Aggiungere un nuovo scraper

1. Crea `backend/scraper_<nome>.py` esponendo `def cerca_<nome>(query: str) -> list[dict]`.
2. Ritorna oggetti con il payload sopra (almeno `nome`, `prezzo_numerico`, `link`).
3. Registralo in `scraper_service.ALL_SCRAPERS` con `{"<key>": ("<Nome Visualizzato>", cerca_<nome>)}`.
4. Aggiungilo nel selettore frontend (`home.component.ts` → `availableSites`).
5. Se Selenium-based, aggiungilo a `scraper_service.SELENIUM_SCRAPER_KEYS` per serializzare tramite `_SELENIUM_LOCK`.

---

## Frontend Angular

### Routing

| Path | Component | Guard |
|------|-----------|-------|
| `/` | `HomeComponent` | — |
| `/search` (alias `/results`) | `ResultsComponent` | — |
| `/login` | `LoginComponent` | — |
| `/signup` | `SignupComponent` | — |
| `/profile` | `ProfileComponent` | `authGuard` |
| `**` | redirect a `/` | — |

### Servizi

- `ApiService` — wrapper `HttpClient` con `withCredentials: true` su `/api/*`.
- `AuthService` — stato utente reattivo con `WritableSignal<User | null>`. `checkSession()` viene chiamato al bootstrap.
- `authGuard` — CanActivateFn che reindirizza a `/login` se `!auth.isLoggedIn()`.

### UX

- Home con multi-select dei negozi (tutti selezionati di default), input con suggerimenti debounced (`debounceTime(300)`, `distinctUntilChanged`).
- Pagina risultati con filtro per negozio, paginazione client-side (20/pagina), banner che segnala l'attivazione della modalità fuzzy.
- Tema scuro impostato da `styles.css`.

---

## Database e migrazioni

SQLite di default (`instance/scraper.db`), gestito da SQLAlchemy + Flask-Migrate.

### Schema

**`user`**
- `id` (PK), `email` (unique), `password_hash`, `name`, `surname`, `created_at`
- `newsletter_opt_in`, `privacy_accepted`
- `oauth_provider`, `oauth_id`

**`search_history`**
- `id` (PK), `user_id` (FK → user.id), `search_term`, `filters` (JSON string), `timestamp`

### Comandi

```bash
flask db upgrade                       # apply latest
flask db migrate -m "add column foo"   # genera migrazione
flask db downgrade -1                  # rollback
```

---

## Sistema referral

Due strategie complementari:

1. **`ReferralDBManager`** (`backend/referral_db_manager.py`): mappa esatta URL originale → URL affiliato, persistita in `backend/data/referral_links.json`. Si può abilitare/disabilitare globalmente con `REFERRAL_SYSTEM_ENABLED` e per singolo store via `STORE_CONFIG`. Attualmente solo Thomann è attivo.
2. **`ReferralManager`** (`backend/referral_manager.py`): costruzione dinamica (es. append di parametri `partner_id`).

`apply_referral_links()` viene chiamato dopo `calculate_discounts` nella pipeline di `/api/search`.

Per popolare in bulk il DB:

```python
from referral_db_manager import ReferralDBManager
ReferralDBManager.bulk_import_referrals([
    {"original_url": "https://...", "referral_url": "https://...?aff=ID", "store": "Thomann"},
])
```

Lo script `backend/import_referrals.py` automatizza l'import da fonti esterne.

---

## Testing

Test backend con pytest:

```bash
cd backend
pytest                            # tutti i test
pytest tests/test_api_search.py   # singolo file
```

Suite incluse:
- `tests/test_api_auth.py` — signup/login/logout, sessioni.
- `tests/test_api_oauth.py` — flow OAuth + provider availability.
- `tests/test_api_search.py` — endpoint `/api/search` con scraper mockati.
- `tests/test_scraper_service.py` — coordinator parallelo, retry, timeout.
- `tests/test_search_normalizer.py` — normalizzazione, fuzzy, stopwords.

Test integrativi end-to-end ad-hoc (`test_three_queries.py`, `test_twenty_queries.py`, `test_multi_search.py`, `test_veracity.py`) generano report JSON con statistiche reali per sito.

Test frontend con Karma + Jasmine:

```bash
cd frontend
npm test
```

---

## Deploy

### Render.com (raccomandato)

Blueprint pronto in `render.yaml`. Il build:

1. Installa dipendenze npm e fa il build Angular.
2. Copia `frontend/dist/frontend/browser/*` in `backend/static/`.
3. Installa le dipendenze Python.

Start command:

```bash
cd backend && gunicorn app:app -c gunicorn.conf.py
```

`SECRET_KEY` viene generata automaticamente. Variabili sensibili (OAuth, email) vanno aggiunte da dashboard.

### Docker

```bash
docker build -t instrinder .
docker run -p 5001:5001 --env-file .env instrinder
```

L'immagine include Chromium e ChromeDriver — utile se in futuro si riattivano scraper Selenium.

### Heroku (legacy)

```bash
heroku create
heroku buildpacks:add heroku/nodejs
heroku buildpacks:add heroku/python
git push heroku master
```

`Procfile` lancia gunicorn dalla cartella `backend`.

---

## Contribuire

1. Fork → branch feature → PR verso `master`.
2. Commit format: [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `perf:`, `refactor:`, `test:`, `docs:`).
3. Esegui `pytest` e `npm test` prima di aprire la PR.
4. Per nuovi scraper segui la sezione [Aggiungere un nuovo scraper](#aggiungere-un-nuovo-scraper).

### Note operative

- Cookie di sessione di StrumentiMusicali (`backend/strumentimusicali_cookies.json`) **non devono mai** essere condivisi pubblicamente o committati con credenziali valide.
- Rispetta i `robots.txt` e i ToS dei singoli store.
- Mantieni delay/timeout sani per non sovraccaricare i server di terzi.

---

## Licenza

Progetto a scopo personale e didattico. Aggiungere un file `LICENSE` formale prima di redistribuzione pubblica.

## Contatti

Antonio Cangiano — [antonio.web2music@gmail.com](mailto:antonio.web2music@gmail.com)
