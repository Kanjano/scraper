# Nuove Funzionalità Implementate

Questo documento descrive le nuove funzionalità aggiunte al progetto Scraper, incluse l'autenticazione utenti, la cronologia ricerche, la newsletter e il social login.

## 1. Autenticazione Utente
È stato implementato un sistema completo di gestione utenti.

### Funzionalità
- **Registrazione (`/signup`)**: Gli utenti possono creare un account fornendo Nome, Cognome, Email e Password.
    - **Privacy Policy**: È obbligatorio accettare la privacy policy (checkbox con modale).
    - **Newsletter**: Opzione facoltativa per iscriversi alla newsletter settimanale.
- **Login (`/login`)**: Accesso tramite email e password.
- **Logout**: Disconnessione sicura tramite il menu profilo.
- **Protezione Password**: Le password sono hashate utilizzando `pbkdf2:sha256`.

## 2. Profilo Utente e Cronologia
Ogni utente registrato ha accesso alla propria area personale.

### Funzionalità
- **Pagina Profilo (`/profile`)**: Visualizza i dati dell'utente.
- **Cronologia Ricerche**:
    - Ogni ricerca effettuata da loggato viene salvata automaticamente.
    - Vengono mostrate le ultime 20 ricerche uniche.
    - Cliccando su una voce della cronologia, la ricerca viene rieseguita.

## 3. Newsletter Settimanale
Un sistema automatico per notificare gli utenti sulle offerte relative ai loro interessi.

### Come Funziona
1.  Il sistema recupera gli utenti iscritti alla newsletter.
2.  Analizza le ultime 5 ricerche uniche di ogni utente.
3.  Esegue una scansione "leggera" (attualmente su Thomann e StrumentiMusicali) per cercare prodotti scontati (>10%) corrispondenti a quei termini.
4.  Invia un'email riassuntiva con le migliori offerte trovate.

### Esecuzione
La newsletter è gestita tramite un comando CLI, ideale per essere schedulato (es. cron job settimanale):

```bash
flask send-newsletter
```

## 4. Social Login
È possibile accedere o registrarsi utilizzando account Google, Facebook o X (Twitter).

### Configurazione
Per abilitare questa funzionalità, è necessario configurare le chiavi API nel file `.env`:

```bash
# Google
GOOGLE_CLIENT_ID=tua_client_id
GOOGLE_CLIENT_SECRET=tua_client_secret

# Facebook
FACEBOOK_CLIENT_ID=tua_client_id
FACEBOOK_CLIENT_SECRET=tua_client_secret

# X (Twitter)
TWITTER_CLIENT_ID=tua_client_id
TWITTER_CLIENT_SECRET=tua_client_secret
```

Se le chiavi non sono configurate, il sistema mostrerà un avviso all'utente invece di generare un errore.

## 5. Struttura del Database
Il database SQLite (`instance/scraper.db`) è stato aggiornato con le seguenti tabelle:

- **User**:
    - `id`, `email`, `password_hash`, `name`, `surname`
    - `newsletter_opt_in`, `privacy_accepted`
    - `oauth_provider`, `oauth_id` (per social login)
- **SearchHistory**:
    - `id`, `user_id`, `search_term`, `timestamp`

Le migrazioni sono gestite tramite **Flask-Migrate**.

---

## Comandi Utili

- **Avviare il server**: `python3 app.py`
- **Inviare newsletter**: `flask send-newsletter`
- **Eseguire test**: `python3 test_user_flow.py`
