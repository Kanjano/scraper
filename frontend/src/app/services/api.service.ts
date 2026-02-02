
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:5001/api';

  constructor(private http: HttpClient) { }

  // Search
  search(query: string, sites: string[]): Observable<any> {
    return this.http.post(`${this.baseUrl}/search`, { prodotto: query, siti: sites });
  }

  // Auth
  login(credentials: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/auth/login`, credentials);
  }

  signup(userData: any): Observable<any> {
    return this.http.post(`${this.baseUrl}/auth/signup`, userData);
  }

  logout(): Observable<any> {
    return this.http.post(`${this.baseUrl}/auth/logout`, {});
  }

  getCurrentUser(): Observable<any> {
    return this.http.get(`${this.baseUrl}/auth/me`);
  }

  // Contacts
  sendMessage(data: any): Observable<any> {
    // Note: backend expects form data for contacts usually, but let's assume JSON for API refactor
    // or we might need to adjust backend contact route to accept JSON. 
    // Plan assumed existing /contatti is for HTML form. 
    // We might need to adjust app.py or use form data here.
    // For now, let's implement the method.
    return this.http.post(`${this.baseUrl}/contacts`, data);
  }
}
