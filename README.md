# Instrinder - Strumenti Musicali Price Scraper

## Descrizione
Instrinder è un'applicazione web che permette di confrontare i prezzi di strumenti musicali e accessori tra diversi rivenditori online. Il sistema è in grado di effettuare ricerche su vari negozi online, estrarre informazioni sui prodotti e presentare i risultati in un'interfaccia unificata.

## Funzionalità

- Ricerca prodotti su diversi negozi di strumenti musicali italiani e internazionali
- Confronto prezzi in tempo reale
- Interfaccia web intuitiva e reattiva
- Supporto multilingua (Italiano, Inglese, Tedesco, Francese, Spagnolo)
- Gestione avanzata di reCAPTCHA e protezioni anti-bot
- Ordinamento dei risultati per prezzo, nome o negozio

## Struttura del Progetto

```
.
├── app.py                  # Applicazione Flask principale
├── browser_manager.py      # Gestione del browser per lo scraping
├── captcha_solver.py       # Gestione e risoluzione dei CAPTCHA
├── requirements.txt        # Dipendenze del progetto
├── strumentimusicali_cookies.json  # Cookie di sessione per Strumenti Musicali
├── scraper_*.py            # Moduli di scraping per i vari negozi
└── templates/              # Template HTML
    ├── base.html           # Template base
    ├── index.html          # Pagina principale di ricerca
    ├── results.html        # Pagina dei risultati
    └── contatti.html       # Pagina contatti
└── translations/          # File di traduzione
    ├── __init__.py
    ├── de.py              # Tedesco
    ├── en.py              # Inglese
    ├── es.py              # Spagnolo
    ├── fr.py              # Francese
    └── it.py              # Italiano
```

## Requisiti di Sistema

- Python 3.8 o superiore
- Chrome/Chromium installato
- Connessione a Internet

## Installazione

1. Clona il repository:
   ```bash
   git clone [URL_DEL_REPOSITORY]
   cd Scraper
   ```

2. Crea e attiva un ambiente virtuale (consigliato):
   ```bash
   python -m venv venv
   source venv/bin/activate  # Su Linux/Mac
   # Oppure su Windows: .\venv\Scripts\activate
   ```

3. Installa le dipendenze:
   ```bash
   pip install -r requirements.txt
   ```

## Configurazione

Prima di avviare l'applicazione, assicurati di avere installato Chrome/Chromium sul sistema. L'applicazione utilizza undetected-chromedriver per gestire il browser in modo automatico.

## Utilizzo

1. Avvia l'applicazione Flask:
   ```bash
   python app.py
   ```
   Oppure utilizza il file `run_app.py` per avviare su una porta specifica (default: 5002):
   ```bash
   python run_app.py
   ```

2. Apri il browser e vai all'indirizzo `http://localhost:5002`

3. Inserisci il nome del prodotto che desideri cercare e clicca su "Cerca"

## Negozi Supportati

### Italia
- Strumenti Musicali
- Centro Chitarre
- Tomassone
- Strumenti Musicali.net
- Gino Musica (Non testato)
- Esse-Music (Non testato)
- Begnis Music (Non testato)
- Luckymusic (Non testato)
- RRF Guitars (Non testato)

### Internazionali
- Thomann (Germania)
- Andertons (UK)
- Gear4Music (UK)
- Musik Produktiv (Germania)


## Gestione dei CAPTCHA

L'applicazione include un sistema avanzato per la gestione dei CAPTCHA che utilizza:
- undetected-chromedriver per evitare il rilevamento
- Gestione dei cookie di sessione
- Ritardi casuali tra le richieste
- User-Agent personalizzati

## File di Configurazione

- `strumentimusicali_cookies.json`: Contiene i cookie di autenticazione per il sito Strumenti Musicali
- `requirements.txt`: Elenco delle dipendenze Python richieste

## Sviluppo

### Aggiungere un nuovo negozio

1. Crea un nuovo file `scraper_nome.py` nella directory principale
2. Implementa la funzione `search_nome(prodotto, max_results=10)` che restituisce una lista di dizionari con la struttura:
   ```python
   {
       'nome': 'Nome del prodotto',
       'prezzo': 999.99,  # float
       'url': 'https://url-del-prodotto',
       'negozio': 'Nome Negozio',
       'posizione': 'Paese',
       'spedizione': 'Spedizione gratuita'  # opzionale
   }
   ```
3. Importa e registra la funzione in `app.py`

### Esecuzione dei test

```bash
# Avvia l'applicazione in modalità sviluppo
FLASK_ENV=development flask run --port=5002
```

## Traduzioni

Le traduzioni sono gestite tramite i file nella cartella `translations/`. Per aggiungere una nuova lingua:

1. Crea un nuovo file `lingua.py` (es. `es.py` per lo spagnolo)
2. Aggiungi le traduzioni nel formato:
   ```python
   translations = {
       'search_placeholder': 'Buscar instrumentos musicales...',
       # altre traduzioni...
   }
   ```
3. Aggiungi la lingua al selettore in `templates/base.html`

## Note sulla Sicurezza

- Non condividere mai i file dei cookie (`strumentimusicali_cookies.json`)
- L'applicazione è progettata per uso personale e didattico
- Rispettare i termini di servizio dei siti web sottostanti
- Utilizzare ritardi appropriati tra le richieste per evitare di sovraccaricare i server

## Licenza

[Inserire tipo di licenza qui]

## Contatti

Per domande o segnalazioni, contattare [informazioni di contatto]
