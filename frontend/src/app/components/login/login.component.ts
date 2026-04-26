
import { Component, inject, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ApiService } from '../../services/api.service';

const OAUTH_ERROR_MESSAGES: { [code: string]: string } = {
  oauth_not_configured: 'Login social non disponibile: provider non configurato.',
  oauth_unsupported_provider: 'Provider social non supportato.',
  oauth_unhandled_provider: 'Provider social non gestito.',
  oauth_client_init_failed: 'Errore inizializzazione client OAuth.',
  oauth_redirect_failed: 'Impossibile avviare il login social.',
  oauth_no_email: 'Il provider non ha fornito un indirizzo email.',
  oauth_callback_error: 'Errore durante il login social. Riprova.',
};

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './login.component.html',
  styleUrl: './login.component.css'
})
export class LoginComponent implements OnInit {
  auth = inject(AuthService);
  api = inject(ApiService);
  router = inject(Router);
  route = inject(ActivatedRoute);

  email = '';
  password = '';
  error = '';
  loading = false;

  oauthProviders = signal<{ [provider: string]: boolean }>({
    google: false,
    facebook: false,
    twitter: false,
  });

  ngOnInit() {
    const params = this.route.snapshot.queryParamMap;
    const errCode = params.get('error');
    const provider = params.get('provider');
    if (errCode) {
      const base = OAUTH_ERROR_MESSAGES[errCode] || 'Errore login social.';
      this.error = provider ? `${base} (${provider})` : base;
    }

    this.api.getOAuthProviders().subscribe({
      next: (res) => this.oauthProviders.set(res.providers || {}),
      error: () => {/* silent: keep all disabled */ },
    });
  }

  isProviderAvailable(provider: string): boolean {
    return !!this.oauthProviders()[provider];
  }

  onSubmit() {
    if (!this.email || !this.password) return;

    this.loading = true;
    this.error = '';

    this.auth.login({ email: this.email, password: this.password }).subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.error = err.error?.message || 'Errore durante il login.';
        this.loading = false;
      }
    });
  }
}
