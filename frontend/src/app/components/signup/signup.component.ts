
import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-signup',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './signup.component.html',
  styleUrl: './signup.component.css'
})
export class SignupComponent {
  auth = inject(AuthService);
  router = inject(Router);

  email = '';
  password = '';
  name = '';
  surname = '';
  privacyAccepted = false;
  newsletterOptIn = false;

  error = '';
  loading = false;

  onSubmit() {
    if (!this.email || !this.password || !this.name || !this.surname) {
      this.error = 'Compila tutti i campi obbligatori.';
      return;
    }

    if (!this.privacyAccepted) {
      this.error = 'Devi accettare la privacy policy.';
      return;
    }

    this.loading = true;
    this.error = '';

    const userData = {
      email: this.email,
      password: this.password,
      name: this.name,
      surname: this.surname,
      privacy_accepted: this.privacyAccepted,
      newsletter_opt_in: this.newsletterOptIn
    };

    this.auth.signup(userData).subscribe({
      next: () => {
        this.router.navigate(['/']);
      },
      error: (err) => {
        this.error = err.error?.message || 'Errore durante la registrazione.';
        this.loading = false;
      }
    });
  }
}
