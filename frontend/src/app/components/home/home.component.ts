
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css'
})
export class HomeComponent {
  router = inject(Router);
  searchQuery = '';

  availableSites = [
    { id: 'thomann', name: 'Thomann' },
    { id: 'musik_produktiv', name: 'Musik Produktiv' },
    { id: 'gear4music', name: 'Gear4music' },
    { id: 'andertons', name: 'Andertons' },
    { id: 'centrochitarre', name: 'Centro Chitarre' },
    { id: 'tomassone', name: 'Tomassone' },
    { id: 'strumentimusicali', name: 'Strumenti Musicali' }
  ];

  selectedSites: string[] = [];
  topDiscounts: any[] = []; // In future, fetch this from API on init

  constructor() {
    // Select all by default
    this.selectedSites = this.availableSites.map(s => s.id);
  }

  toggleSite(id: string) {
    if (this.selectedSites.includes(id)) {
      this.selectedSites = this.selectedSites.filter(s => s !== id);
    } else {
      this.selectedSites.push(id);
    }
  }

  onSearch() {
    if (this.searchQuery.trim()) {
      this.router.navigate(['/search'], {
        queryParams: {
          q: this.searchQuery,
          sites: this.selectedSites.join(',')
        }
      });
    }
  }
}
