import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ResultsComponent } from './results.component';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { ActivatedRoute } from '@angular/router';
import { of } from 'rxjs';
import { SearchResult } from '../../models/search.models';

const MOCK_RESULTS: SearchResult[] = [
  { nome: 'Chitarra A', prezzo: '500,00', prezzo_numerico: 500, prezzo_originale: '600,00',
    prezzo_originale_numerico: 600, link: 'http://a.com', immagine: 'img.jpg',
    sito: 'Thomann', sconto_percentuale: 17 },
  { nome: 'Chitarra B', prezzo: '300,00', prezzo_numerico: 300, prezzo_originale: '300,00',
    prezzo_originale_numerico: 300, link: 'http://b.com', immagine: 'N/A',
    sito: 'Gear4music', sconto_percentuale: 0 },
];

describe('ResultsComponent', () => {
  let component: ResultsComponent;
  let fixture: ComponentFixture<ResultsComponent>;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ResultsComponent, HttpClientTestingModule, RouterTestingModule],
      providers: [
        { provide: ActivatedRoute, useValue: { queryParams: of({ q: 'chitarra', sites: 'thomann' }) } }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ResultsComponent);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('should create', () => {
    fixture.detectChanges();
    http.expectOne('/api/search').flush({ results: [], count: 0, stats: { siti: {} }, top_discounts: [], search_mode: 'strict', normalized_query: 'chitarra' });
    expect(component).toBeTruthy();
  });

  it('should set loading = true on search start', () => {
    fixture.detectChanges();
    expect(component.loading).toBeTrue();
    http.expectOne('/api/search').flush({ results: MOCK_RESULTS, count: 2, stats: { siti: {} }, top_discounts: [], search_mode: 'strict', normalized_query: 'chitarra' });
  });

  it('should populate results after successful response', () => {
    fixture.detectChanges();
    http.expectOne('/api/search').flush({ results: MOCK_RESULTS, count: 2, stats: { siti: {} }, top_discounts: [], search_mode: 'strict', normalized_query: 'chitarra' });
    fixture.detectChanges();
    expect(component.results.length).toBe(2);
    expect(component.loading).toBeFalse();
  });

  it('should set error on failed request', () => {
    fixture.detectChanges();
    http.expectOne('/api/search').error(new ErrorEvent('network error'));
    fixture.detectChanges();
    expect(component.error).toBeTruthy();
    expect(component.loading).toBeFalse();
  });

  it('filterBySite() should filter results by site', () => {
    component.results = MOCK_RESULTS;
    component.calculateSitesCount();
    component.filterBySite(null);
    fixture.detectChanges();
    http.expectOne('/api/search').flush({ results: [], count: 0, stats: { siti: {} }, top_discounts: [], search_mode: 'strict', normalized_query: '' });

    component.filterBySite('Thomann');
    expect(component.filteredResults.length).toBe(1);
    expect(component.filteredResults[0].sito).toBe('Thomann');
  });
});
