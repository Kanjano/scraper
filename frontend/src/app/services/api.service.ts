
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { SearchResponse } from '../models/search.models';
import { AuthResponse, AuthState, LoginRequest, SignupRequest } from '../models/auth.models';
import { SuggestionResponse } from '../models/suggestion.models';

const API_OPTS = { withCredentials: true };

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = '/api';

  constructor(private http: HttpClient) { }

  search(query: string, sites: string[]): Observable<SearchResponse> {
    return this.http.post<SearchResponse>(
      `${this.baseUrl}/search`,
      { prodotto: query, siti: sites },
      API_OPTS
    );
  }

  getSuggestions(query: string): Observable<SuggestionResponse> {
    return this.http.post<SuggestionResponse>(
      `${this.baseUrl}/search/suggestions`,
      { query },
      API_OPTS
    );
  }

  login(credentials: LoginRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.baseUrl}/auth/login`, credentials, API_OPTS);
  }

  signup(userData: SignupRequest): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.baseUrl}/auth/signup`, userData, API_OPTS);
  }

  logout(): Observable<{ success: boolean }> {
    return this.http.post<{ success: boolean }>(`${this.baseUrl}/auth/logout`, {}, API_OPTS);
  }

  getCurrentUser(): Observable<AuthState> {
    return this.http.get<AuthState>(`${this.baseUrl}/auth/me`, API_OPTS);
  }

  sendMessage(data: { nome: string; email: string; message: string }): Observable<{ success: boolean; message: string }> {
    return this.http.post<{ success: boolean; message: string }>(`${this.baseUrl}/contacts`, data, API_OPTS);
  }
}
