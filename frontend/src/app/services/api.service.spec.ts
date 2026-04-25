import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ApiService } from './api.service';

describe('ApiService', () => {
  let service: ApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule]
    });
    service = TestBed.inject(ApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('search() should POST to /api/search with correct body', () => {
    service.search('chitarra', ['thomann']).subscribe();
    const req = http.expectOne('/api/search');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ prodotto: 'chitarra', siti: ['thomann'] });
    req.flush({ results: [], count: 0, stats: {}, top_discounts: [], search_mode: 'strict', normalized_query: 'chitarra' });
  });

  it('login() should POST to /api/auth/login', () => {
    service.login({ email: 'a@b.com', password: '123' }).subscribe();
    const req = http.expectOne('/api/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body.email).toBe('a@b.com');
    req.flush({ success: true });
  });

  it('getCurrentUser() should GET /api/auth/me', () => {
    service.getCurrentUser().subscribe();
    const req = http.expectOne('/api/auth/me');
    expect(req.request.method).toBe('GET');
    req.flush({ authenticated: false });
  });

  it('getSuggestions() should POST to /api/search/suggestions', () => {
    service.getSuggestions('chitarr').subscribe();
    const req = http.expectOne('/api/search/suggestions');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ query: 'chitarr' });
    req.flush({ suggestions: ['chitarra'], normalized_query: 'chitarr' });
  });
});
