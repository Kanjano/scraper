
import { Injectable, signal, WritableSignal } from '@angular/core';
import { ApiService } from './api.service';
import { Router } from '@angular/router';
import { tap } from 'rxjs/operators';

export interface User {
  id?: number;
  email: string;
  name?: string;
  surname?: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  // Using Signals for state management
  currentUser: WritableSignal<User | null> = signal(null);

  constructor(private api: ApiService, private router: Router) {
    this.checkSession();
  }

  checkSession() {
    this.api.getCurrentUser().subscribe({
      next: (res) => {
        if (res.authenticated) {
          this.currentUser.set(res.user ?? null);
        } else {
          this.currentUser.set(null);
        }
      },
      error: () => this.currentUser.set(null)
    });
  }

  login(credentials: any) {
    return this.api.login(credentials).pipe(
      tap((res: any) => {
        if (res.success) {
          this.currentUser.set(res.user);
        }
      })
    );
  }

  signup(data: any) {
    return this.api.signup(data).pipe(
      tap((res: any) => {
        if (res.success) {
          this.currentUser.set(res.user);
        }
      })
    );
  }

  logout() {
    this.api.logout().subscribe(() => {
      this.currentUser.set(null);
      this.router.navigate(['/']);
    });
  }

  isLoggedIn(): boolean {
    return !!this.currentUser();
  }
}
