# Guida all'utilizzo — INSTRINDER

INSTRINDER cerca uno strumento musicale in 76 negozi di Europa, Stati
Uniti e Asia, converte i prezzi in euro e li mette a confronto. Questa guida è
divisa in due parti: **usare il sito** e **installarlo e gestirlo**.

---

## Parte 1 — Usare il sito

### Cercare

1. Apri la pagina iniziale e scrivi cosa cerchi: una marca, un modello o un tipo
   di strumento (es. `fender stratocaster custom shop`, `violino 4/4`,
   `batteria elettronica roland`). Puoi scrivere nella tua lingua: la ricerca
   viene inviata anche in inglese ai negozi esteri.
2. Premi **Invio** (Shift+Invio va a capo). Il tasto `/` porta il cursore nella
   barra da qualunque punto della pagina.
3. Facoltativo, prima di cercare: limita l'area (**Europa**, **USA**, **Asia**)
   o scegli **Solo grandi negozi** per una ricerca più veloce.

Le ricerche recenti compaiono sotto la barra: frecce ↑/↓ per sceglierne una,
× per cancellarla. Restano solo nel tuo browser.

### Mentre cerca

La ricerca interroga ogni negozio e può durare da pochi secondi a un paio di
minuti. Vedi in tempo reale:

- la barra di avanzamento in alto (quanti negozi hanno già risposto);
- le fasi: *Preparo la ricerca → Visito N negozi → Tengo le offerte pertinenti →
  Ordino per prezzo*, con le icone dei negozi che rispondono (un "!" indica un
  negozio in errore);
- i primi risultati, che compaiono appena arrivano.

**Interrompi** (o il tasto **Esc**) ferma la ricerca e tiene i risultati già
ricevuti.

### Leggere i risultati

Ogni risultato mostra negozio, link, nome del prodotto, **prezzo in euro** in
grassetto, prezzo originale nella valuta del negozio e paese. Se il negozio lo
dichiara in sconto vedi anche il prezzo precedente barrato e l'etichetta
arancione **−N%**. Ricambi e accessori (pickup, custodie, corde, spartiti…)
sono segnati **Accessorio** e messi in fondo, così non falsano il prezzo più
basso.

- **Schede Tutti / Europa / USA / Asia**: filtrano i risultati già trovati.
- **Ordina per**: *Pertinenza* (predefinito: prima i prodotti che corrispondono
  meglio a ciò che hai scritto), *Prezzo crescente*, *Prezzo decrescente*,
  *Nome (A–Z)*.
- **⋮** accanto a un risultato: apri nel negozio, copia il link, copia i dati.
- **Altri risultati** in fondo mostra i successivi 20.

### Offerte e sconti

La colonna di destra (sotto la lista su schermi stretti) raccoglie i prodotti
in sconto, dal più scontato: foto, negozio, prezzo attuale e precedente. Un
clic sul riquadro apre la pagina del prodotto sul sito del negozio. Gli sconti
sono quelli dichiarati da ciascun negozio.

Il riquadro **Riepilogo della ricerca** (schermi larghi) riporta negozi
interrogati, negozi con offerte, negozi in errore, durata, prezzo più basso e
media di mercato.

### Condividere una ricerca

L'indirizzo nella barra del browser contiene la ricerca, l'area e
l'ordinamento (`?q=…&area=europe&sort=price_asc`): copialo per condividerla o
salvarla nei preferiti.

### Lingua e tema

La lingua viene scelta dal paese da cui ti colleghi; cambiala dal menu in alto
a destra (18 lingue). L'icona a forma di luna alterna tema chiaro e scuro.

### Contattami

Il pulsante **Contattami** in alto apre un modulo (nome, email, messaggio). Il
messaggio arriva al gestore del sito; la tua email serve solo per la risposta.

---

## Parte 2 — Installare e gestire

### Requisiti

- Python 3.11+ (verificato su 3.12)
- Google Chrome installato (per i negozi che richiedono un browser vero)
- Circa 1 GB di spazio (modello di ricerca, browser Playwright)

### Installazione con Docker (consigliata)

```bash
git clone https://github.com/Kanjano/scraper.git instrinder && cd instrinder
cp .env.example .env          # poi modifica .env (vedi sotto)
docker compose up -d --build  # http://localhost:8000
```

L'immagine (≈ 4,5 GB) contiene già browser e modello di ricerca; funziona su
server Intel/AMD e ARM. Dettagli, reverse proxy e sicurezza in
[INFRASTRUCTURE](INFRASTRUCTURE.md). **Prima di pubblicare il sito** limita
l'accesso a `/admin/…` dal reverse proxy: quegli indirizzi non hanno password.

### Installazione senza Docker

```bash
git clone https://github.com/Kanjano/scraper.git instrinder
cd instrinder
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
patchright install chromium
cp .env.example .env          # poi modifica .env (vedi sotto)
python main.py                # http://localhost:8000
```

Al primo avvio viene scaricato una sola volta il modello di ricerca (~240 MB in
`data/models/`); dopo funziona offline.

### File `.env` (configurazione)

Il file `.env` non va mai nel repository (è in `.gitignore`). Le voci
principali:

| Voce | A cosa serve |
|------|--------------|
| `SCHEDULER_ENABLED` | `False` in sviluppo: evita gli scraping periodici automatici |
| `SCRAPER_CONTACT` | email o sito con cui lo scraper si presenta ai negozi (nello user-agent) |
| `CONTACT_EMAIL` | indirizzo che riceve i messaggi del modulo Contattami |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD` | account di posta che invia i messaggi |
| `GEOIP_DB` | file per riconoscere il paese dall'IP (facoltativo) |
| `SEMANTIC_MODEL` | modello di ricerca multilingue; vuoto = solo confronto letterale |
| `USE_PROXY`, `PROXY_LIST` | proxy per i negozi più protetti |

**Modulo di contatto con Gmail:** crea una *password per le app* (Account Google
→ Sicurezza → Verifica in due passaggi → Password per le app) e imposta:

```env
CONTACT_EMAIL=tuo-indirizzo@gmail.com
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=tuo-indirizzo@gmail.com
SMTP_PASSWORD=la-password-per-le-app
```

Senza `SMTP_HOST` il modulo risponde "non disponibile" invece di perdere i
messaggi. L'indirizzo non compare mai nella pagina. Limite anti-spam: 3
messaggi ogni 10 minuti per indirizzo IP (`CONTACT_RATE_LIMIT`,
`CONTACT_RATE_WINDOW_S`).

**Riconoscimento del paese (facoltativo, da aggiornare ogni mese):**

```bash
curl -s https://download.db-ip.com/free/dbip-country-lite-$(date +%Y-%m).mmdb.gz \
  | gunzip > data/dbip-country-lite.mmdb
```

### Manutenzione dei negozi

I negozi cambiano piattaforma e pagine di ricerca. Periodicamente:

```bash
python -m scripts.probe_stores       # riscopre la rotta di ricerca di ogni negozio
python -m scripts.test_all_stores    # prova ogni negozio con una ricerca reale (~20 min)
```

Il resoconto è in `data/store_test_report.json`; i motivi per cui un negozio è
escluso sono in `GET /admin/coverage`. Per correggere a mano un negozio
(rotta, selettori CSS, modalità browser) si aggiunge una voce in
`MANUAL_OVERRIDES` di `config/sites_config.py` — esempi e spiegazioni in
[SCRAPERS](SCRAPERS.md).

### Verifiche

```bash
pytest                                   # test offline (nessuna rete)
python -m scrapers.relevance             # autocontrollo del filtro di pertinenza
python -m scrapers.query_translation     # autocontrollo della traduzione
```

Per provare tutti gli stati della pagina senza fare scraping, in locale:
`http://localhost:8000/?demo=slow&q=gibson` (anche `fast`, `empty`, `error`,
`partial`).

### Problemi comuni

| Sintomo | Causa probabile |
|---------|-----------------|
| Ricerca lenta (minuti) | molti negozi, alcuni rispondono lentamente; restringi l'area |
| Un negozio non dà mai risultati | rotta cambiata: `scripts.probe_stores --only <id>` |
| "Il modulo di contatto non è disponibile" | mancano `CONTACT_EMAIL` o `SMTP_HOST` in `.env` |
| Invio del messaggio non riuscito | credenziali SMTP errate (Gmail: serve la password per le app) |
| Negozi con verifica "press & hold" / Turnstile | servono proxy residenziali (`PROXY_LIST`) |
