# Code Review Report — Progetto Scraper Negozi Musicali
**Data:** 2026-04-24  
**Revisore:** Senior Code Reviewer (Claude Sonnet 4.6)  
**Stack:** Flask (Python) + Selenium backend, Angular 17 standalone frontend

---

## Indice
1. [Backend — Duplicazione di codice](#1-backend--duplicazione-di-codice)
2. [Backend — Gestione degli errori](#2-backend--gestione-degli-errori)
3. [Backend — Typo handling / fuzzy match](#3-backend--typo-handling--fuzzy-match)
4. [Backend — Performance](#4-backend--performance)
5. [Backend — Sicurezza](#5-backend--sicurezza)
6. [Backend — API contract e struttura](#6-backend--api-contract-e-struttura)
7. [Frontend — Type safety](#7-frontend--type-safety)
8. [Frontend — Gestione stato](#8-frontend--gestione-stato)
9. [Frontend — UX della ricerca](#9-frontend--ux-della-ricerca)
10. [Frontend — Error handling e loading states](#10-frontend--error-handling-e-loading-states)
11. [Frontend — Routing e guard](#11-frontend--routing-e-guard)
12. [Priorità di intervento](#12-priorità-di-intervento)

---

## 1. Backend — Duplicazione di codice

### CRITICAL — Logica di scraping duplicata tra `/search` e `/api/search`

**File:** `backend/app.py` — righe 441–668 (`/search`) e 835–976 (`/api/search`)

Il commento al rigo 875 lo ammette esplicitamente: `# --- SCRAPING LOGIC (Copied/Adapted from search route) ---`. Le due route contengono copie quasi identiche delle seguenti sezioni:

| Blocco di codice | Riga in `/search` | Riga in `/api/search` |
|---|---|---|
| Definizione `all_scrapers` dict | 492–500 | 879–887 |
| Filtraggio `active_scrapers` | 502–505 | 889–892 |
| Lettura `MAX_WORKERS` da env | 509–512 | 894–897 |
| `ThreadPoolExecutor` con `run_scraper` | 516–536 | 899–917 |
| Chiamata a `filter_strict` + fallback fuzzy | 538–552 | 920–928 |
| Ordinamento risultati per prezzo/punteggio | 556–563 | 930–937 |
| Applicazione referral link | 589–592 | 940–942 |
| Calcolo `sconto_percentuale` per ogni risultato | 624–635 | 945–954 |
| Calcolo `top_sconti` (top 10) | 637–643 | 956–960 |
| Salvataggio cronologia (`SearchHistory`) | 473–482 | 861–872 |

**Conseguenze:** qualsiasi bug fix o modifica alla logica deve essere applicata in due posti. Già oggi si nota una piccola divergenza: in `/search` il `bare except` al riga 634 è `except Exception:` mentre in `/api/search` al riga 953 è un `except:` nudo (che cattura anche `SystemExit` e `KeyboardInterrupt`).

**Raccomandazione:** Estrarre tutta la logica di scraping in una funzione privata `_execute_search(search_query, siti_selezionati) -> dict` che restituisce un dizionario con `results`, `stats`, `top_discounts`, `search_mode`. Entrambe le route chiamano questa funzione e formattano l'output nel modo appropriato (HTML vs JSON).

---

### HIGH — Tre scraper "aggregatori" raddoppiano gli import

**File:** `backend/scraper_germania.py`, `backend/scraper_italia.py`, `backend/scraper_inghilterra.py`

Questi file reimplementano la logica di iterazione sugli scraper (loop + try/except) che esiste già in `app.py` tramite `run_scraper`. Non vengono usati da `app.py` (che chiama direttamente le funzioni individuali), quindi sono codice morto che può creare confusione.

**Raccomandazione:** Eliminare questi file o trasformarli in semplici costanti che raggruppano le chiavi degli scraper per regione geografica, da usare eventualmente per filtrare in `app.py`.

---

### MEDIUM — Logica di scroll duplicata in `scraper_strumentimusicali.py`

**File:** `backend/scraper_strumentimusicali.py` — righe 88–119 (in `make_request`) e 178–213 (in `extract_product_details`)

Il blocco di scroll con `last_height`, `scroll_attempts` e `max_scroll_attempts` è identico. La funzione `make_request` non viene peraltro mai chiamata da `search_strumentimusicali` (che usa direttamente `BrowserManager.create_driver`), rendendola codice inutilizzato.

**Raccomandazione:** Estrarre lo scroll in una funzione helper `scroll_to_bottom(driver, max_attempts=5)`. Rimuovere o integrare `make_request` se non usata.

---

### MEDIUM — Logica `estrai_float_prezzo` replicata in ogni scraper

Ogni scraper ha la propria variante per convertire stringhe prezzo in float: `estrai_float_prezzo` in Thomann, `clean_price` in StrumentiMusicali, regex inline in CentroChitarre, Tomassone, Gear4music, Andertons. Nessuna è condivisa.

**Raccomandazione:** Creare un modulo `backend/price_utils.py` con una funzione `parse_price(text: str) -> float` robusta e centralizzata, usata da tutti gli scraper.

---

## 2. Backend — Gestione degli errori

### HIGH — `bare except:` silenziosi in tutti gli scraper

**File:** `backend/scraper_andertons.py` rigo 81, `backend/scraper_centrochitarre.py` rigo 91, `backend/scraper_musik_produktiv.py` rigo 96, `backend/scraper_gear4music.py` righe 103 e 119, `backend/scraper_strumentimusicali.py` righe 391, 692, 694, 746, `backend/app.py` rigo 953.

`except:` senza tipo cattura `SystemExit`, `KeyboardInterrupt` e `GeneratorExit`, impedendo la corretta interruzione del processo. In alcuni casi l'eccezione viene ignorata con `pass` o `continue` senza nemmeno un log, rendendo impossibile il debug in produzione.

**Raccomandazione:** Sostituire tutti i `bare except:` con `except Exception as e:` e aggiungere almeno un `logger.warning(...)`. Per il blocco price-parsing in `scraper_andertons.py` (riga 81) che usa `except: pass`, questo ha già nascosto un bug: se il JSON è malformato l'intera lista prodotti è silenziosa.

---

### HIGH — Retry logic non uniforme tra gli scraper

`run_scraper` in `app.py` (righe 349–420) implementa un secondo tentativo solo se `cleanup_on_error` lo autorizza (cioè se l'errore sembra correlato al driver). Ma la logica di retry è assente negli scraper stessi: se Thomann restituisce un timeout di rete, lo scraper restituisce lista vuota senza ritentare. Solo `scraper_strumentimusicali.py` ha un proprio ciclo `max_retries=3`, ma il `driver` viene creato dentro il ciclo solo al primo tentativo (righe 32–46 nella funzione `make_request` non utilizzata), mentre in `search_strumentimusicali` il driver viene creato fuori dal loop try, quindi un singolo errore di rete non viene ri-tentato.

**Raccomandazione:** Definire un decorator `@with_retry(max_attempts=2, delay=3)` o una funzione helper da applicare uniformemente nelle funzioni di scraping. Il `run_scraper` in `app.py` può essere semplificato rimuovendo la duplicazione del retry.

---

### MEDIUM — Driver non chiuso in caso di eccezione in `scraper_strumentimusicali.py`

**File:** `backend/scraper_strumentimusicali.py` — riga 593

Il blocco `except Exception as e:` al rigo 591 chiama `BrowserManager.close_driver(driver)` e poi `return []`. Ma il blocco `finally:` al rigo 841 chiude il driver di nuovo. Questo non è un bug critico (chiudere un driver già chiuso è innocuo), ma la struttura è confusa: il driver viene chiuso in due posti distinti. Nel caso normale di successo, la variabile `driver` usata nel blocco principale (righe 596–838) è la stessa istanza creata al rigo 383, e il `finally` al rigo 841 la chiude correttamente. Il problema è che se l'eccezione avviene prima del rigo 596, `risultati = []` al rigo 595 non viene eseguito e si ottiene `NameError` su `risultati`. 

**Raccomandazione:** Spostare `risultati = []` subito dopo la creazione del driver, e usare un unico `try/finally` per la chiusura.

---

### MEDIUM — Salvataggio di file di debug in produzione

**File:** `backend/scraper_strumentimusicali.py` righe 49, 55, 451, 495, 513, 578–580; `backend/scraper_essemusic.py` riga 75; `backend/scraper_ginomusica.py` riga 65; `backend/scraper_luckymusic.py` riga 95.

Gli scraper scrivono su disco file come `debug_strumenti_last_page.html`, `strumentimusicali_results.html`, `captcha_page.html`, `essemusic_dump.html`, ecc. su ogni richiesta in produzione. Questo:
- Rallenta le richieste (I/O bloccante nel thread di scraping)
- Consuma spazio disco illimitato
- Può esporre HTML con dati utente se la directory è accessibile

**Raccomandazione:** Condizionare il salvataggio debug a una variabile d'ambiente `DEBUG_SCRAPER=true`. In produzione disabilitare completamente.

---

### LOW — `version_main=145` hardcoded in BrowserManager

**File:** `backend/browser_manager.py` — righe 22 e 40

La versione Chrome è hardcoded a `145`. Quando Chrome si aggiorna automaticamente sul server, `undetected_chromedriver` non riesce più ad avviarsi e tutti gli scraper falliscono silenziosamente.

**Raccomandazione:** Leggere la versione da variabile d'ambiente `CHROME_VERSION` con fallback a `None` (autodetect di `undetected_chromedriver`):
```python
version_main = int(os.environ.get('CHROME_VERSION', 0)) or None
```

---

## 3. Backend — Typo handling / fuzzy match

### HIGH — `filtra_risultati` non fa fuzzy match: il nome è fuorviante

**File:** `backend/app.py` — righe 60–86

La funzione `filtra_risultati` descritta nei commenti come parte del sistema fuzzy in realtà **non filtra nulla**: ordina semplicemente i risultati per prezzo crescente. Il parametro `query` e `soglia_similarita` sono dichiarati ma non usati (il commento alla riga 66 lo conferma: "non utilizzata"). Il vero fuzzy matching è in `match_fuzzy` (righe 232–241), ma questa funzione non viene mai chiamata nelle route `/search` o `/api/search`.

**Raccomandazione:** Rinominare `filtra_risultati` in `sort_by_price` per chiarire il suo scopo. Implementare effettivamente `match_fuzzy` come passo di filtro nella modalità fuzzy, oppure rimuoverla se davvero non serve.

---

### HIGH — La logica strict/fuzzy ha una soglia arbitraria e non documentata

**File:** `backend/app.py` — righe 544–551 e 924–928

La soglia `if len(risultati_strict) >= 5` per decidere se usare strict o fuzzy è arbitraria: con 4 risultati esatti si passa alla modalità fuzzy che può restituire prodotti irrilevanti. Non c'è documentazione sul perché sia 5.

**Raccomandazione:** Rendere la soglia configurabile via `STRICT_MIN_RESULTS` (env var), documentarne il ragionamento, e valutare se abbia senso applicare entrambi i filtri (prima strict, poi completare con fuzzy fino a N risultati totali) piuttosto che scegliere l'uno o l'altro.

---

### MEDIUM — Manca "Did you mean?" / correzione typo

Non esiste alcun meccanismo che suggerisca all'utente una query alternativa in caso di zero risultati. `difflib.SequenceMatcher` è importato ma usato solo in `similar()` (riga 56–58), funzione anch'essa mai chiamata nelle route principali.

**Raccomandazione:** In caso di zero risultati, usare `difflib.get_close_matches` su un vocabolario di brand/modelli comuni (es. da un file JSON statico) per suggerire correzioni. Restituire il campo `suggestion` nella risposta API.

---

### MEDIUM — `match_fuzzy` usa `cutoff=0.7` troppo elevato per nomi di prodotti tecnici

**File:** `backend/app.py` — riga 237

"Fender Stratocaster" vs "Stratocaster Fender" avrebbe score basso con `cutoff=0.7` word-by-word. Nomi di prodotti tecnici (es. "Eventide H90" vs "eventide-h90") hanno differenze di formato ma stesso significato.

**Raccomandazione:** Abbassare il cutoff a 0.6, normalizzare i nomi (lowercase, rimozione trattini/underscore) prima del confronto, e considerare una libreria come `rapidfuzz` al posto di `difflib` per prestazioni migliori.

---

## 4. Backend — Performance

### HIGH — MAX_WORKERS=2 con 7 siti Selenium: bottleneck estremo

**File:** `backend/app.py` — righe 509–512 e 894–897

Con 7 scraper di cui 5 basati su Selenium (Thomann, Gear4music, Andertons, CentroChitarre, Tomassone, StrumentiMusicali), il limite a 2 worker significa che i 7 scraper vengono eseguiti in ~4 round sequenziali. Ogni istanza Selenium impiega 5–15 secondi. Il tempo totale può superare i 60 secondi, oltre il timeout di gunicorn (120s in `gunicorn.conf.py`) o il timeout del browser.

**Raccomandazione:** Aumentare `MAX_WORKERS` a `min(7, cpu_count())` o almeno 4–5. Valutare l'uso di `asyncio` + `playwright` per gli scraper che non richiedono Selenium pesante, oppure separare gli scraper leggeri (requests-based, es. Musik Produktiv) da quelli Selenium.

---

### HIGH — Nessun caching dei risultati di ricerca

Ogni richiesta avvia da zero tutti gli scraper Selenium, anche per query identiche eseguite a pochi secondi di distanza. Non esiste Redis, memcache o anche una semplice cache in-memory con TTL.

**Raccomandazione:** Implementare una cache con TTL di 5–10 minuti. Flask-Caching con backend Redis è la soluzione più semplice:
```python
from flask_caching import Cache
cache = Cache(app, config={'CACHE_TYPE': 'RedisCache', 'CACHE_DEFAULT_TIMEOUT': 600})
```
In alternativa, un dict in-memory con `functools.lru_cache` e timestamp di scadenza per ambienti senza Redis.

---

### HIGH — Ogni scraper Selenium crea e distrugge un'istanza Chrome per ogni richiesta

**File:** `backend/browser_manager.py` — `create_driver()` chiamata in ogni scraper

Con 5 scraper Selenium paralleli per richiesta, si aprono 5 istanze Chrome da zero (cold start ~3–5 secondi ciascuna). Un pool di driver riutilizzabili ridurrebbe drasticamente il tempo di avvio.

**Raccomandazione:** Implementare un `BrowserPool` che mantiene driver pre-inizializzati (es. pool di 3–5), con checkout/checkin thread-safe. Aggiungere health check per rilevare driver "morti".

---

### MEDIUM — `time.sleep()` fissi e arbitrari in tutti gli scraper

Ogni scraper usa `time.sleep(2)`, `time.sleep(3)`, `time.sleep(5)` dopo il caricamento della pagina, senza attendere un elemento specifico. In `scraper_andertons.py` il sleep è di 5 secondi (riga 17) senza WebDriverWait.

**Raccomandazione:** Sostituire i sleep fissi con `WebDriverWait` + `expected_conditions` (come già fatto parzialmente in Thomann e CentroChitarre). Usare sleep solo come fallback con valori più bassi (0.5–1s).

---

### MEDIUM — `scraper_musik_produktiv.py`: chiamata HTTP per ogni immagine (N+1)

**File:** `backend/scraper_musik_produktiv.py` — righe 15–23 e 80

La funzione `get_musikprodukt_image(link)` effettua una GET HTTP per ogni prodotto trovato per estrarre l'immagine OpenGraph. Con 20 prodotti, sono 20 richieste HTTP sequenziali aggiuntive.

**Raccomandazione:** Verificare se le immagini sono disponibili direttamente nel JSON del `gtmDataLayer` (campo `imageUrl` o simile). Se no, parallelizzare le richieste immagine con `ThreadPoolExecutor` o semplicemente omettere le immagini se non critiche per la UX.

---

### LOW — `gunicorn.conf.py`: 1 worker sincrono non sfrutta i thread

**File:** `backend/gunicorn.conf.py`

Con `workers=1` e `threads=3`, in modalità sync solo 3 richieste concorrenti sono gestite. Con scraping che impiega 30–60 secondi, l'applicazione è di fatto single-user.

**Raccomandazione:** Usare `worker_class='gthread'` con `workers=2, threads=4`, oppure `worker_class='gevent'` se si adotta un approccio asincrono. In alternativa, separare il backend di scraping in worker Celery per disaccoppiare le richieste HTTP dal lavoro pesante.

---

## 5. Backend — Sicurezza

### CRITICAL — `secret_key` hardcoded in chiaro nel codice sorgente

**File:** `backend/app.py` — riga 103

```python
app.secret_key = 'supersegreto'
```

Questa chiave è usata per firmare i cookie di sessione Flask e i token Flask-Login. Con la chiave in chiaro nel repository, chiunque abbia accesso al codice (compresi collaboratori futuri, CI/CD logs, repository pubblici) può forgiare sessioni arbitrarie.

**Raccomandazione:** Spostare in variabile d'ambiente e generare una chiave sicura:
```python
app.secret_key = os.environ['SECRET_KEY']  # Obbligatorio, non opzionale
```
Generare con: `python -c "import secrets; print(secrets.token_hex(32))"`.

---

### CRITICAL — Credenziali email e app password in chiaro nel file `.env` committato

**File:** `backend/.env` — righe 1–2

```
EMAIL_SENDER=antonio.web2music@gmail.com
EMAIL_PASSWORD=ifcc ysdg lbji oevm
```

Il file `.env` è presente nella directory del progetto (e presumibilmente nel repository). Contiene l'app password Gmail in chiaro. Chiunque legga il repository può accedere all'account email.

**Raccomandazione:** 
1. Aggiungere `.env` al `.gitignore` **immediatamente**.
2. Revocare l'app password corrente su Google Account e generarne una nuova.
3. Fornire un file `.env.example` con valori placeholder.

---

### HIGH — CORS completamente aperto su tutte le route API

**File:** `backend/app.py` — riga 102

```python
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
```

`origins="*"` con `supports_credentials=True` è una combinazione problematica: i browser moderni rifiutano le richieste credenziali cross-origin con wildcard origin, ma questa configurazione indica che non è stata fatta una revisione della policy CORS. In produzione, qualsiasi sito può fare richieste autenticate all'API.

**Raccomandazione:** Specificare esplicitamente le origini permesse:
```python
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:4200",
    "https://tuodominio.com"
]}}, supports_credentials=True)
```

---

### HIGH — `/api/auth/signup`: nessuna validazione dell'email

**File:** `backend/app.py` — righe 810–833

Il campo `email` viene accettato senza validazione del formato. `email_validator` è in `requirements.txt` ma non viene importato né usato. Un utente può registrarsi con `email=""` o `email="notanemail"`.

**Raccomandazione:**
```python
from email_validator import validate_email, EmailNotValidError
try:
    validate_email(email)
except EmailNotValidError:
    return {"success": False, "message": "Email non valida"}, 400
```

---

### HIGH — `/api/auth/signup`: nessuna validazione della password

**File:** `backend/app.py` — righe 810–833

Vengono accettate password vuote (`password=None` o `password=""`). Il campo `password` non ha requisiti minimi di lunghezza o complessità.

**Raccomandazione:** Verificare `len(password) >= 8` prima di chiamare `set_password`. Considerare l'aggiunta di requisiti di complessità di base.

---

### HIGH — Email destinatario hardcoded in `/api/contacts`

**File:** `backend/app.py` — riga 992

```python
msg['To'] = "antonio.web2music@gmail.com"
```

L'indirizzo email del destinatario è hardcoded nel codice sorgente. Spostarlo in variabile d'ambiente `EMAIL_RECIPIENT`.

---

### MEDIUM — `/test_sentry` espone un endpoint che causa un errore intenzionale in produzione

**File:** `backend/app.py` — righe 423–425

```python
@app.route('/test_sentry')
def trigger_error():
    division_by_zero = 1 / 0
```

Questo endpoint è senza autenticazione e accessibile da chiunque. In produzione genera un 500 error loggato come se fosse un errore reale.

**Raccomandazione:** Proteggere con `@login_required` e un check per `current_user.is_admin`, oppure rimuovere completamente dall'ambiente di produzione tramite variabile d'ambiente `FLASK_ENV`.

---

### MEDIUM — OAuth: nessuna validazione del parametro `provider`

**File:** `backend/app.py` — righe 677–689

Il parametro `provider` arriva dall'URL (`/login/<provider>`) e viene passato direttamente a `oauth.create_client(provider)`. Anche se Authlib gestisce provider non registrati, il log al riga 683 include il valore non validato dell'utente nel messaggio di flash.

**Raccomandazione:** Aggiungere una whitelist esplicita:
```python
ALLOWED_PROVIDERS = {'google', 'facebook', 'twitter'}
if provider not in ALLOWED_PROVIDERS:
    return redirect('/login')
```

---

### LOW — `app.config['SQLALCHEMY_DATABASE_URI']` hardcoded su SQLite

**File:** `backend/app.py` — riga 106

In produzione SQLite ha limitazioni di concorrenza (write lock globale). Con Gunicorn multi-thread, le scritture concorrenti (es. `SearchHistory`) possono causare `OperationalError: database is locked`.

**Raccomandazione:** Leggere da env var `DATABASE_URL` con fallback a SQLite solo per sviluppo:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///scraper.db')
```

---

## 6. Backend — API contract e struttura

### HIGH — Scraper non registrati in `app.py`: begnismusic, essemusic, ginomusica, luckymusic, rrguitars

**File:** `backend/app.py` — dizionario `all_scrapers` (righe 492–500 e 879–887)

Sono presenti 5 scraper completi (`scraper_begnismusic.py`, `scraper_essemusic.py`, `scraper_ginomusica.py`, `scraper_luckymusic.py`, `scraper_rrguitars.py`) che non vengono mai importati né usati da `app.py`. Non sono nemmeno esposti come opzione nel frontend (`home.component.ts` lista solo 7 siti). Questi scraper sono codice morto.

**Raccomandazione:** Decidere se integrarli (aggiungendoli all'`all_scrapers` dict e al frontend) o rimuoverli dal repository per ridurre il debito tecnico.

---

### HIGH — Nessun endpoint API per la cronologia delle ricerche

Il modello `SearchHistory` esiste (salva le ricerche degli utenti loggati) ma non c'è alcun endpoint `GET /api/history` per recuperarla. Il `ProfileComponent` del frontend non mostra la cronologia.

**Raccomandazione:** Aggiungere `GET /api/history` (paginato) e `DELETE /api/history/<id>` per permettere all'utente di visualizzare e gestire la propria cronologia.

---

### MEDIUM — Manca endpoint `DELETE /api/auth/account` per cancellazione account

Non c'è modo per un utente di eliminare il proprio account tramite API, violando i requisiti GDPR sul "diritto all'oblio".

**Raccomandazione:** Implementare `DELETE /api/auth/account` con conferma password, che cancella utente e cronologia associata.

---

### MEDIUM — La risposta di `/api/search` non include le immagini dei prodotti

I campi `immagine` (snake_case, non uniformato) vengono inclusi nella risposta JSON, ma il template `results.component.html` non mostra le immagini. La risposta API non documenta il contratto (nessun schema OpenAPI/Swagger).

**Raccomandazione:** Aggiungere `<img>` al card dei risultati nel frontend, e definire uno schema OpenAPI per `/api/search` con i campi attesi: `nome`, `prezzo`, `prezzo_numerico`, `prezzo_originale`, `prezzo_originale_numerico`, `link`, `immagine`, `sito`, `sconto_percentuale`.

---

### MEDIUM — `requirements.txt` senza versioni pinned per molte dipendenze

**File:** `backend/requirements.txt` — righe 12–16

```
Flask-SQLAlchemy
Flask-Login
Flask-Migrate
email_validator
Authlib
flask-cors
```

Queste dipendenze non hanno versioni pinned. Un `pip install` futuro può installare versioni incompatibili silenziosamente.

**Raccomandazione:** Generare un `requirements.txt` completo con `pip freeze > requirements.txt` e aggiungere `flask-babel` (usato in `app.py` al riga 29 ma non in `requirements.txt`).

---

### MEDIUM — `scraper_strumentimusicali.py`: `driver` non inizializzato nel path di errore `NameError`

**File:** `backend/scraper_strumentimusicali.py` — righe 380 e 596

```python
driver = None  # riga 377
risultati = []
# ...
try:
    driver = BrowserManager.create_driver()  # riga 383
    # ...
except Exception as e:
    BrowserManager.close_driver(driver)  # riga 593 - OK, driver è None o inizializzato
    return []
risultati = []  # riga 595 - FUORI dal try/except! Se si arriva qui dopo un'eccezione diversa...
```

In realtà la riga 595 (`risultati = []`) è al di fuori del blocco `try/except` e subito prima del loop di elaborazione. Se `product_items` è `None` per via del flusso di controllo (riga 558 ritorna `[]`, riga 576 ritorna `[]`), `product_items` non è mai definita per il loop al riga 599. Non c'è un `product_items = []` di default prima del blocco try.

**Raccomandazione:** Inizializzare `product_items = []` prima del blocco `try`, spostare `risultati = []` all'interno del blocco `try` subito dopo la creazione del driver.

---

### LOW — `scraper_strumentimusicali.py` ha codice irraggiungibile (dead code)

**File:** `backend/scraper_strumentimusicali.py` — righe 576–582

```python
if not product_items:  # riga 573 già gestisce questo caso con return []
    logger.warning(...)
    return []

if not product_items:  # SECONDO if identico, mai raggiunto
    logger.error(...)
    return []
```

Il secondo blocco `if not product_items:` al riga 577 è identico e irraggiungibile perché il primo al riga 573 già fa `return []`.

**Raccomandazione:** Rimuovere il blocco duplicato (righe 577–582).

---

### LOW — `cerca_multiprodotti` in `scraper_strumentimusicali.py` è incompleta

**File:** `backend/scraper_strumentimusicali.py` — righe 846–851

```python
def cerca_multiprodotti(lista_prodotti, num_processi=4):
    # Per ora restituiamo solo i risultati di una singola ricerca
    if not lista_prodotti:
        return []
    return search_strumentimusicali(lista_prodotti[0])
```

Ignora tutti gli elementi della lista tranne il primo. Il commento dice "può essere espansa" ma questa funzione è un placeholder non funzionale. Identico problema in `scraper_gear4music.py` dove `cerca_multiprodotti` usa `multiprocessing.Pool` ma la funzione principale non viene mai chiamata in modalità multi-prodotto.

**Raccomandazione:** Implementare correttamente o rimuovere. Non lasciare placeholder in produzione.

---

## 7. Frontend — Type safety

### HIGH — Uso pervasivo di `any` nei componenti

| File | Riga | Utilizzo di `any` |
|---|---|---|
| `results.component.ts` | 22 | `results: any[] = []` |
| `results.component.ts` | 23 | `filteredResults: any[] = []` |
| `results.component.ts` | 24 | `stats: any = null` |
| `results.component.ts` | 25 | `sitesCount: any = {}` |
| `home.component.ts` | 29 | `topDiscounts: any[] = []` |
| `api.service.ts` | 16 | `search(...): Observable<any>` |
| `api.service.ts` | 27 | `login(credentials: any): Observable<any>` |
| `api.service.ts` | 31 | `signup(userData: any): Observable<any>` |
| `api.service.ts` | 35 | `logout(): Observable<any>` |
| `api.service.ts` | 39 | `getCurrentUser(): Observable<any>` |
| `api.service.ts` | 44 | `sendMessage(data: any): Observable<any>` |
| `auth.service.ts` | 38 | `login(credentials: any)` |
| `auth.service.ts` | 48 | `signup(data: any)` |

**Raccomandazione:** Definire interfacce TypeScript in un file `frontend/src/app/models/`:

```typescript
// models/product.model.ts
export interface Product {
  nome: string;
  prezzo: string;
  prezzo_numerico: number;
  prezzo_originale: string;
  prezzo_originale_numerico: number;
  link: string;
  immagine: string;
  sito: string;
  sconto_percentuale: number;
}

// models/search-result.model.ts
export interface SearchResult {
  results: Product[];
  stats: SearchStats;
  top_discounts: Product[];
  search_mode: 'strict' | 'fuzzy';
  count: number;
}

// models/auth.model.ts
export interface LoginCredentials { email: string; password: string; }
export interface SignupData { email: string; password: string; name: string; surname: string; privacy_accepted: boolean; newsletter_opt_in: boolean; }
```

---

### MEDIUM — Template HTML usa campi non tipizzati con fallback non documentati

**File:** `frontend/src/app/components/results/results.component.html` — riga 37

```html
<h3>{{ item.nome || item.titolo }}</h3>
```

Il fallback `item.titolo` esiste per compatibilità con il vecchio backend HTML, ma nell'API JSON il campo è sempre `nome`. Con tipizzazione forte, questo fallback non sarebbe necessario e il codice sarebbe più chiaro.

**File:** `frontend/src/app/components/results/results.component.html` — riga 42

```html
<span class="current-price">€ {{ item.prezzo || item.prezzo_numerico }}</span>
```

`item.prezzo` può essere una stringa già formattata con il simbolo `€` (es. `"€ 299,00"` da Thomann), quindi mostrare "€ € 299,00". Non c'è normalizzazione.

**Raccomandazione:** Normalizzare il campo `prezzo` nel backend (restituire sempre solo il numero numerico) e usare il `currency` pipe di Angular: `{{ item.prezzo_numerico | currency:'EUR':'symbol':'1.2-2':'it' }}`.

---

### MEDIUM — `*ngIf` (sintassi Angular 14) mescolata con `@if` (Angular 17) nello stesso template

**File:** `frontend/src/app/components/home/home.component.html` — riga 36

```html
<span class="original-price" *ngIf="item.prezzo_originale_numerico > 0">
```

Il resto del template usa la nuova sintassi `@if` / `@for` di Angular 17. L'uso di `*ngIf` richiede `CommonModule` già importato, ma mescola le due sintassi rende il codice inconsistente e può causare problemi con future migrazioni.

**Raccomandazione:** Sostituire con `@if (item.prezzo_originale_numerico > 0)`.

---

## 8. Frontend — Gestione stato

### MEDIUM — Nessun state management: la ricerca si ripete ad ogni navigazione

**File:** `frontend/src/app/components/results/results.component.ts` — riga 31

`ngOnInit` si sottoscrive a `queryParams` e riavvia la ricerca ogni volta che il componente viene inizializzato. Se l'utente naviga ai risultati, poi torna alla home, poi ri-naviga ai risultati con la stessa query, una nuova chiamata API (e quindi un nuovo ciclo di scraping da 30–60 secondi) viene avviata.

**Raccomandazione:** Implementare un servizio `SearchStateService` che cachi l'ultima query, i risultati e il timestamp. Se la stessa query viene ripetuta entro 5 minuti, i risultati cached vengono restituiti immediatamente. Per progetti più grandi, considerare NgRx o Akita.

---

### MEDIUM — `AuthService` usa Signals per l'utente ma `ApiService` non è reattivo

**File:** `frontend/src/app/services/auth.service.ts` — riga 19

`currentUser` è un `WritableSignal<User | null>`, scelta moderna e corretta. Tuttavia `ApiService` restituisce `Observable<any>` non connessi ai signal. Il componente `ProfileComponent` usa `auth.currentUser()` (computed signal), ma altri componenti non reagiscono a cambiamenti dell'utente.

**Raccomandazione:** Aggiungere `effect()` nel `AppComponent` o in un layout wrapper per reagire ai cambiamenti di `currentUser` (es. mostrare/nascondere menu di navigazione, redirect automatico).

---

### LOW — `topDiscounts` in `HomeComponent` è inizializzato vuoto e non viene mai popolato

**File:** `frontend/src/app/components/home/home.component.ts` — riga 29

```typescript
topDiscounts: any[] = []; // In future, fetch this from API on init
```

Il commento "In future" indica che questa feature non è implementata. Il blocco `@if (topDiscounts.length > 0)` nel template non verrà mai visualizzato.

**Raccomandazione:** Implementare un endpoint `GET /api/top-discounts` o popolarlo con i dati dell'ultima ricerca salvata in cache. Rimuovere il blocco template se non si intende implementarlo a breve.

---

## 9. Frontend — UX della ricerca

### HIGH — Nessun debounce sull'input di ricerca

**File:** `frontend/src/app/components/home/home.component.html` — riga 7

La ricerca si avvia solo al click del pulsante o al tasto Enter (nessun autocomplete in tempo reale), il che è corretto dato il costo dello scraping. Tuttavia non c'è nemmeno validazione della lunghezza minima della query (es. almeno 3 caratteri). Una query di un singolo carattere avvia uno scraping completo.

**Raccomandazione:** Aggiungere validazione minima `if (this.searchQuery.trim().length < 3) return;` in `onSearch()`. Per autocomplete future, usare `debounceTime(300)` da RxJS.

---

### HIGH — Nessun feedback "Did you mean?" o suggerimento in caso di zero risultati

**File:** `frontend/src/app/components/results/results.component.html` — riga 47

Il template mostra solo "Nessun risultato trovato." senza alcun suggerimento alternativo. Non c'è link per tornare alla home e modificare la ricerca.

**Raccomandazione:** Il backend dovrebbe includere `"suggestion": "forse cercavi X?"` nella risposta API. Il frontend dovrebbe mostrarlo con un link cliccabile per ri-eseguire la ricerca corretta.

---

### MEDIUM — Immagini dei prodotti non mostrate nei risultati

**File:** `frontend/src/app/components/results/results.component.html`

Il backend restituisce il campo `immagine` per ogni prodotto, ma il template dei risultati non ha un `<img>` tag. Le card mostrano solo testo (nome, prezzo, sito, link).

**Raccomandazione:** Aggiungere l'immagine del prodotto alla card, con fallback a un'immagine placeholder per i casi in cui `immagine === "N/A"`.

---

### MEDIUM — La lista dei siti nel frontend non è sincronizzata con il backend

**File:** `frontend/src/app/components/home/home.component.ts` — righe 18–26

```typescript
availableSites = [
    { id: 'thomann', name: 'Thomann' },
    // ... 7 siti
];
```

Questa lista è hardcoded. Se un nuovo scraper viene aggiunto al backend, il frontend non lo mostrerà automaticamente. Non esiste un endpoint `GET /api/sites` che restituisca i siti disponibili.

**Raccomandazione:** Creare endpoint `GET /api/sites` che restituisca la lista degli scraper attivi con nome, id e flag `enabled`. Il frontend la fetcha all'inizializzazione.

---

### LOW — Prezzo mostrato con formato inconsistente nelle card

**File:** `frontend/src/app/components/results/results.component.html` — riga 42

```html
<span class="current-price">€ {{ item.prezzo || item.prezzo_numerico }}</span>
```

`item.prezzo` può essere `"€ 299,00"` (Thomann/Tomassone con `€` incluso) o `"€ 299.00"` (Musik Produktiv) o `"€ 2.113,00"` (Gear4music). Il template aggiunge sempre un ulteriore `€`, portando a output come `"€ € 299,00"`.

**Raccomandazione:** Normalizzare nel backend: restituire sempre `prezzo_numerico` (float) e usare il currency pipe Angular per la formattazione locale, eliminando il campo `prezzo` stringa dalla risposta API.

---

## 10. Frontend — Error handling e loading states

### MEDIUM — Loading state non resettato in caso di navigazione durante la ricerca

**File:** `frontend/src/app/components/results/results.component.ts` — righe 31–41

`ngOnInit` sottoscrive i `queryParams` ma non gestisce la disiscrizione (unsubscribe). Se l'utente naviga via mentre la ricerca è in corso, la subscription rimane attiva, e quando i dati arrivano vengono assegnati a un componente distrutto (memory leak).

**Raccomandazione:**
```typescript
private destroy$ = new Subject<void>();

ngOnInit() {
    this.route.queryParams
        .pipe(takeUntil(this.destroy$))
        .subscribe(params => { ... });
}

ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
    // Cancellare anche la subscription HTTP se possibile
}
```

---

### MEDIUM — Messaggio di errore generico non aiuta l'utente

**File:** `frontend/src/app/components/results/results.component.ts` — riga 60

```typescript
this.error = 'Si è verificato un errore durante la ricerca.';
```

L'errore HTTP (500, 503, timeout di rete) viene mappato sempre allo stesso messaggio generico. L'utente non sa se il problema è temporaneo (riprova) o strutturale.

**Raccomandazione:** Differenziare per tipo di errore:
- `err.status === 0` → "Impossibile raggiungere il server. Controlla la connessione."
- `err.status === 500` → "Errore del server. Riprova tra qualche minuto."
- `err.status === 503` → "Il servizio è momentaneamente sovraccarico."

---

### LOW — `loading` non viene resettato se l'utente naviga via e poi torna

**File:** `frontend/src/app/components/results/results.component.ts` — riga 44

`this.loading = true` viene impostato in `search()`, ma se il componente viene distrutto e ricreato (navigazione back/forward), lo stato iniziale è `false` (corretto). Tuttavia, la subscription a `queryParams` può triggerare una nuova ricerca prima che la precedente sia completata, con `loading` che viene resettato a `true` senza attendere la chiusura della chiamata precedente.

**Raccomandazione:** Cancellare la chiamata HTTP precedente con `switchMap` invece di `subscribe` diretto:
```typescript
this.route.queryParams.pipe(
    switchMap(params => {
        this.loading = true;
        return this.api.search(this.query, this.selectedSites);
    }),
    takeUntil(this.destroy$)
).subscribe({ next: ..., error: ... });
```

---

## 11. Frontend — Routing e guard

### HIGH — Route `/profile` accessibile senza autenticazione

**File:** `frontend/src/app/app.routes.ts` — riga 14

```typescript
{ path: 'profile', component: ProfileComponent },
```

La route del profilo non ha alcun `canActivate` guard. Un utente non autenticato può visitare `/profile` direttamente. Il `ProfileComponent` mostra `auth.currentUser()` che sarà `null`, ma non redirige al login.

**Raccomandazione:** Creare un `AuthGuard`:
```typescript
// guards/auth.guard.ts
export const authGuard: CanActivateFn = () => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (auth.isLoggedIn()) return true;
    return router.createUrlTree(['/login']);
};
```
E applicarlo: `{ path: 'profile', component: ProfileComponent, canActivate: [authGuard] }`.

---

### MEDIUM — Route `**` redirige alla home perdendo il contesto

**File:** `frontend/src/app/app.routes.ts` — riga 15

```typescript
{ path: '**', redirectTo: '' }
```

Un URL non valido come `/prodotti/chitarre` viene silenziosamente rediretto alla home senza mostrare un messaggio 404. L'utente potrebbe pensare che l'URL sia valido.

**Raccomandazione:** Creare un componente `NotFoundComponent` con messaggio chiaro e link alla home:
```typescript
{ path: '**', component: NotFoundComponent }
```

---

### MEDIUM — `withCredentials` non configurato globalmente per le chiamate HTTP

**File:** `frontend/src/app/app.config.ts`

```typescript
provideHttpClient(withFetch())
```

Flask-Login usa cookie di sessione. Per inviare i cookie con le richieste cross-origin, è necessario `withCredentials: true`. Senza un `HttpInterceptor` che lo imposti, le chiamate API non inviano il cookie di sessione e l'utente risulta sempre non autenticato sul backend (che è session-based).

**Raccomandazione:** Aggiungere un interceptor:
```typescript
// interceptors/credentials.interceptor.ts
export const credentialsInterceptor: HttpInterceptorFn = (req, next) => {
    return next(req.clone({ withCredentials: true }));
};
```
E registrarlo: `provideHttpClient(withFetch(), withInterceptors([credentialsInterceptor]))`.

---

### LOW — Login OAuth con redirect href non gestisce errori nel frontend

**File:** `frontend/src/app/components/login/login.component.html` — righe 30–37

```html
<a href="/login/google" class="btn-social google">Google</a>
```

I link OAuth usano `href` diretto (non `routerLink`), che causa un full page reload. Se OAuth fallisce, il backend fa un `flash()` + `redirect('/login')`, ma la sessione Flask non è condivisa con Angular (SPA), quindi il messaggio flash non viene mai visualizzato.

**Raccomandazione:** Dopo il redirect OAuth, il backend dovrebbe impostare un query parameter di errore (es. `/login?error=oauth_failed`) che il `LoginComponent` legge e mostra come messaggio di errore.

---

## 12. Priorità di intervento

### P0 — Sicurezza critica (da fare immediatamente)

| # | Problema | File | Azione |
|---|---|---|---|
| 1 | `.env` con credenziali committato | `.env` | Aggiungere a `.gitignore`, revocare app password Gmail, rigenerare `SECRET_KEY` |
| 2 | `secret_key = 'supersegreto'` | `app.py:103` | Spostare in variabile d'ambiente obbligatoria |
| 3 | Email hardcoded nel codice | `app.py:992` | Spostare in `EMAIL_RECIPIENT` env var |

### P1 — Bug funzionali e regressioni potenziali

| # | Problema | File | Azione |
|---|---|---|---|
| 4 | `withCredentials` mancante | `app.config.ts` | Aggiungere HttpInterceptor, altrimenti login/logout non funzionano |
| 5 | `bare except:` silenziosi | Tutti gli scraper | Sostituire con `except Exception as e:` + logging |
| 6 | Route `/profile` senza guard | `app.routes.ts` | Implementare `AuthGuard` |
| 7 | Validazione email/password mancante in signup | `app.py:810-833` | Usare `email_validator`, validare lunghezza password |
| 8 | `filtra_risultati` non filtra | `app.py:60-86` | Rinominare in `sort_by_price`, implementare il vero fuzzy filter |

### P2 — Performance e scalabilità

| # | Problema | File | Azione |
|---|---|---|---|
| 9 | Nessun caching dei risultati | `app.py` | Implementare Flask-Caching con TTL 5-10 min |
| 10 | MAX_WORKERS=2 con 7 siti Selenium | `app.py` | Aumentare a 4-5 o separare scraper leggeri/pesanti |
| 11 | Istanza Chrome per ogni richiesta | `browser_manager.py` | Implementare `BrowserPool` con driver pre-inizializzati |
| 12 | `time.sleep()` fissi | Tutti gli scraper | Sostituire con `WebDriverWait` |
| 13 | N+1 requests per immagini | `scraper_musik_produktiv.py` | Parallelizzare o eliminare il fetch immagini |

### P3 — Qualità del codice e manutenibilità

| # | Problema | File | Azione |
|---|---|---|---|
| 14 | Logica di scraping duplicata | `app.py:441-668` e `835-976` | Estrarre in `_execute_search()` privata |
| 15 | Type safety mancante nel frontend | Tutti i componenti | Definire interfacce `Product`, `SearchResult`, `LoginCredentials` |
| 16 | Logica prezzo duplicata in ogni scraper | Tutti gli scraper | Creare `price_utils.py` con `parse_price()` centralizzata |
| 17 | Scraper non registrati (`begnismusic`, ecc.) | `app.py` | Integrare o rimuovere |
| 18 | Prezzo con formato inconsistente | Template + scraper | Normalizzare a float nel backend, usare currency pipe Angular |
| 19 | `chrome_version=145` hardcoded | `browser_manager.py` | Leggere da env var |

### P4 — UX e feature mancanti

| # | Problema | File | Azione |
|---|---|---|---|
| 20 | Nessun suggerimento "Did you mean?" | Backend + frontend | Implementare endpoint suggerimenti + UI |
| 21 | Immagini prodotti non mostrate | `results.component.html` | Aggiungere `<img>` con fallback placeholder |
| 22 | Lista siti hardcoded nel frontend | `home.component.ts` | Creare `GET /api/sites`, fetcharla all'init |
| 23 | Endpoint cronologia ricerche mancante | `app.py` | Implementare `GET /api/history` |
| 24 | Nessuna paginazione API nel frontend | `results.component.ts` | Implementare paginazione lato frontend |
| 25 | `topDiscounts` mai popolato | `home.component.ts` | Implementare o rimuovere dalla UI |

---

*Report generato il 2026-04-24. Basato sull'analisi statica del codice; alcuni problemi potrebbero avere impatti diversi in base all'ambiente di deployment specifico.*
