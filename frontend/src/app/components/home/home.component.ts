
import { Component, inject, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged, switchMap, catchError } from 'rxjs/operators';
import { of } from 'rxjs';
import { ApiService } from '../../services/api.service';
import { SearchResult } from '../../models/search.models';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css'
})
export class HomeComponent implements OnDestroy {
  router = inject(Router);
  api = inject(ApiService);

  searchQuery = '';
  suggestions: string[] = [];
  showSuggestions = false;

  availableSites = [
    { id: 'thomann',          name: 'Thomann' },
    { id: 'musik_produktiv',  name: 'Musik Produktiv' },
    { id: 'gear4music',       name: 'Gear4music' },
    { id: 'andertons',        name: 'Andertons' },
    { id: 'centrochitarre',   name: 'Centro Chitarre' },
    { id: 'tomassone',        name: 'Tomassone' },
    { id: 'strumentimusicali',name: 'Strumenti Musicali' },
  ];

  selectedSites: string[] = this.availableSites.map(s => s.id);
  topDiscounts: SearchResult[] = [];

  private queryInput$ = new Subject<string>();
  private sub: Subscription;

  constructor() {
    this.sub = this.queryInput$.pipe(
      debounceTime(300),
      distinctUntilChanged(),
      switchMap(q => {
        if (q.length < 3) return of({ suggestions: [], normalized_query: '' });
        return this.api.getSuggestions(q).pipe(catchError(() => of({ suggestions: [], normalized_query: '' })));
      })
    ).subscribe(res => {
      this.suggestions = res.suggestions;
      this.showSuggestions = this.suggestions.length > 0;
    });
  }

  onQueryChange() {
    this.queryInput$.next(this.searchQuery);
    if (this.searchQuery.length < 3) {
      this.showSuggestions = false;
    }
  }

  selectSuggestion(s: string) {
    this.searchQuery = s;
    this.showSuggestions = false;
    this.onSearch();
  }

  hideSuggestions() {
    setTimeout(() => { this.showSuggestions = false; }, 150);
  }

  toggleSite(id: string) {
    if (this.selectedSites.includes(id)) {
      this.selectedSites = this.selectedSites.filter(s => s !== id);
    } else {
      this.selectedSites.push(id);
    }
  }

  onSearch() {
    if (!this.searchQuery.trim()) return;
    this.showSuggestions = false;
    this.router.navigate(['/search'], {
      queryParams: { q: this.searchQuery, sites: this.selectedSites.join(',') }
    });
  }

  ngOnDestroy() {
    this.sub.unsubscribe();
  }
}
