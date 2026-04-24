
import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { SearchResult, SearchResponse, SearchStats } from '../../models/search.models';

@Component({
  selector: 'app-results',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './results.component.html',
  styleUrl: './results.component.css'
})
export class ResultsComponent implements OnInit {
  route = inject(ActivatedRoute);
  api = inject(ApiService);

  query = '';
  normalizedQuery = '';
  searchMode: 'strict' | 'fuzzy' = 'strict';
  selectedSites: string[] = [];

  results: SearchResult[] = [];
  topDiscounts: SearchResult[] = [];
  filteredResults: SearchResult[] = [];
  stats: SearchStats | null = null;
  sitesCount: { [site: string]: number } = {};

  loading = false;
  error = '';
  currentSiteFilter: string | null = null;

  currentPage = 1;
  readonly pageSize = 20;

  get paginatedResults(): SearchResult[] {
    const start = (this.currentPage - 1) * this.pageSize;
    return this.filteredResults.slice(start, start + this.pageSize);
  }

  get totalPages(): number {
    return Math.ceil(this.filteredResults.length / this.pageSize);
  }

  get showFuzzyBanner(): boolean {
    return this.searchMode === 'fuzzy' &&
      !!this.normalizedQuery &&
      this.normalizedQuery !== this.query.toLowerCase();
  }

  ngOnInit() {
    this.route.queryParams.subscribe(params => {
      this.query = params['q'] || '';
      const sitesParam = params['sites'];
      this.selectedSites = sitesParam ? sitesParam.split(',') : [];
      if (this.query) {
        this.search();
      }
    });
  }

  search() {
    this.loading = true;
    this.error = '';
    this.results = [];
    this.topDiscounts = [];
    this.currentPage = 1;

    this.api.search(this.query, this.selectedSites).subscribe({
      next: (data: SearchResponse) => {
        this.results = data.results || [];
        this.topDiscounts = data.top_discounts || [];
        this.stats = data.stats;
        this.searchMode = data.search_mode;
        this.normalizedQuery = data.normalized_query || '';
        this.calculateSitesCount();
        this.filterBySite(null);
        this.loading = false;
      },
      error: () => {
        this.error = 'Si è verificato un errore durante la ricerca. Riprova tra qualche istante.';
        this.loading = false;
      }
    });
  }

  calculateSitesCount() {
    this.sitesCount = {};
    for (const item of this.results) {
      const site = item.sito || 'Altro';
      this.sitesCount[site] = (this.sitesCount[site] || 0) + 1;
    }
  }

  filterBySite(site: string | null) {
    this.currentSiteFilter = site;
    this.currentPage = 1;
    this.filteredResults = site
      ? this.results.filter(r => r.sito === site)
      : [...this.results];
  }

  goToPage(page: number) {
    if (page >= 1 && page <= this.totalPages) {
      this.currentPage = page;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  siteKeys(): string[] {
    return Object.keys(this.sitesCount);
  }
}
