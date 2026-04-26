export interface SearchResult {
  nome: string;
  prezzo: string;
  prezzo_numerico: number;
  prezzo_originale: string;
  prezzo_originale_numerico: number;
  link: string;
  immagine: string;
  sito: string;
  sconto_percentuale: number;
  relevance_score?: number;
}

export interface SiteStats {
  oggetti: number;
  stato: 'ok' | 'errore' | 'timeout';
  errore?: string;
}

export interface SearchStats {
  [key: string]: SiteStats | number | undefined;
  _tempo_totale?: number;
}

export interface SearchResponse {
  results: SearchResult[];
  stats: SearchStats;
  top_discounts: SearchResult[];
  search_mode: 'strict' | 'fuzzy';
  count: number;
  normalized_query: string;
}
