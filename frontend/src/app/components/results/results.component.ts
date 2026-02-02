
import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { ApiService } from '../../services/api.service';

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
  Object = Object;

  query = '';
  selectedSites: string[] = [];

  results: any[] = [];
  filteredResults: any[] = [];
  stats: any = null;
  sitesCount: any = {};

  loading = false;
  error = '';
  currentSiteFilter: string | null = null;

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

    this.api.search(this.query, this.selectedSites).subscribe({
      next: (data) => {
        this.results = data.results || [];
        this.stats = data.stats;
        this.calculateSitesCount();
        this.filterBySite(null); // Reset filter
        this.loading = false;
      },
      error: (err) => {
        console.error('Search error', err);
        this.error = 'Si è verificato un errore durante la ricerca.';
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
    if (site) {
      this.filteredResults = this.results.filter(r => r.sito === site);
    } else {
      this.filteredResults = this.results;
    }
  }
}
