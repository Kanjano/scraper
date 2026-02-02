# Documentazione Frontend Angular - Instrinder

Questa documentazione fornisce una panoramica dettagliata della nuova architettura frontend sviluppata in Angular 17+ per il progetto Instrinder.

## Panoramica Architettura

Il frontend è stato riscritto utilizzando le più recenti funzionalità di Angular, tra cui:
- **Standalone Components**: Eliminazione dei moduli (`NgModule`) per una struttura più leggera e modulare.
- **Signals**: Utilizzati per la gestione reattiva dello stato (es. `AuthService`).
- **Control Flow Syntax**: Nuova sintassi `@if`, `@for` nei template.

## Struttura dei File

### Configurazione Globale

#### `src/app/app.config.ts`
Gestisce la configurazione globale dell'applicazione.
- **`appConfig`**: Esporta la configurazione che viene usata nel bootstrap dell'applicazione.
- **Providers**:
  - `provideRouter(routes)`: Abilita il routing definito in `app.routes.ts`.
  - `provideHttpClient(withFetch())`: Configura il client HTTP per usare l'API Fetch nativa del browser per migliori performance.

#### `src/app/app.routes.ts`
Definisce le rotte di navigazione.
- **Path vuoto (`''`)**: Porta alla `HomeComponent`.
- **`/search`**: Porta alla pagina dei risultati (`ResultsComponent`).
- **`/login`**, **`/signup`**, **`/profile`**: Gestione autenticazione e utente.
- **Wildcard (`**`)**: Reindirizza alla home per qualsiasi URL non valido.

#### `src/app/app.component.ts`
Il componente radice che fa da contenitore per l'intera app.
- **Template**: Contiene la navbar di navigazione e il `<router-outlet>` dove vengono renderizzate le pagine.
- **Logica**:
  - Inietta `AuthService` per gestire la visibilità dei link nella navbar (Login/Signup vs Profile/Logout) in base allo stato di autenticazione.
  - gestisce il logout tramite il metodo `logout()`.

---

### Servizi (Services)

#### `src/app/services/api.service.ts`
Gestisce tutte le comunicazioni HTTP con il backend Flask.
- **Metodi Principali**:
  - `search(query, sites)`: Invia una richiesta POST a `/api/search` per cercare prodotti.
  - `login`, `signup`, `logout`: Endpoints per l'autenticazione.
  - `getCurrentUser()`: Recupera i dati dell'utente loggato.
  - `sendMessage()`: Per il modulo contatti.

#### `src/app/services/auth.service.ts`
Gestisce lo stato di autenticazione lato client.
- **Stato Reattivo**: Usa `WritableSignal` (`currentUser`) per mantenere e aggiornare lo stato dell'utente in tempo reale in tutta l'app.
- **`checkSession()`**: Verifica all'avvio se l'utente è già loggato.
- **Metodi**: Wrappa le chiamate di `ApiService` (`login`, `signup`) aggiornando il signal `currentUser` in caso di successo.
- **`isLoggedIn()`**: Helper per verificare rapidamente se l'utente è autenticato.

---

### Componenti (Components)

#### `src/app/components/home/home.component.ts`
La pagina principale di ricerca.
- **Gestione Siti**:
  - `availableSites`: Lista statica dei negozi supportati (ID e Nome).
  - `selectedSites`: Array degli ID dei siti selezionati per la ricerca.
  - `toggleSite(id)`: Aggiunge o rimuove un sito dalla selezione.
- **Ricerca**:
  - `onSearch()`: Naviga verso `/search` passando la query e i siti selezionati come parametri URL (Query Params).

#### `src/app/components/results/results.component.ts`
Visualizza i risultati della ricerca.
- **Inizializzazione (`ngOnInit`)**:
  - Legge i parametri dalla URL (`q`, `sites`).
  - Avvia automaticamente la ricerca se è presente una query.
- **Logica di Ricerca**:
  - `search()`: Chiama `api.search()`.
  - Gestisce gli stati di caricamento (`loading`) ed errore (`error`).
- **Filtraggio Frontend**:
  - `calculateSitesCount()`: Calcola quanti risultati ci sono per ogni negozio.
  - `filterBySite(site)`: Permette di filtrare i risultati visualizzati senza ricaricare la pagina.
  - `topDiscounts`: (Predisposto) per mostrare le migliori offerte.

#### `src/app/components/login/login.component.ts`
Modulo di accesso.
- Gestisce il form di login.
- Chiama `auth.login()` e reindirizza alla home in caso di successo.
- Gestisce e mostra messaggi di errore restituiti dal backend.

#### `src/app/components/signup/signup.component.ts`
Modulo di registrazione.
- Gestisce campi estesi: Nome, Cognome, Email, Password, Accettazione Privacy, Opt-in Newsletter.
- Effettua validazione base lato client (campi obbligatori).
- Chiama `auth.signup()` e reindirizza alla home.

#### `src/app/components/profile/profile.component.ts`
Pagina profilo utente.
- Visualizza i dati dell'utente loggato recuperati tramite `auth.currentUser()`.
- Semplice visualizzazione read-only (al momento).
