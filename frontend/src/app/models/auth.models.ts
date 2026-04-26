export interface User {
  id: number;
  email: string;
  name: string;
  surname: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  email: string;
  password: string;
  name: string;
  surname: string;
  privacy_accepted: boolean;
  newsletter_opt_in: boolean;
}

export interface AuthResponse {
  success: boolean;
  user?: { email: string; name: string };
  message?: string;
}

export interface AuthState {
  authenticated: boolean;
  user?: User;
}

export interface OAuthProvidersResponse {
  providers: { [provider: string]: boolean };
}
