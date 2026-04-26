import { Component, inject, OnInit, OnDestroy, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from './services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent implements OnInit, OnDestroy {
  auth = inject(AuthService);
  clock = '';
  private timer: any;

  ngOnInit() {
    this.tick();
    this.timer = setInterval(() => this.tick(), 1000);
  }

  ngOnDestroy() {
    if (this.timer) clearInterval(this.timer);
  }

  private tick() {
    const d = new Date();
    const pad = (n: number) => n.toString().padStart(2, '0');
    const offsetMin = -d.getTimezoneOffset();
    const sign = offsetMin >= 0 ? '+' : '-';
    const oh = Math.floor(Math.abs(offsetMin) / 60);
    this.clock = `Roma ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())} GMT ${sign}${oh}`;
  }

  logout() {
    this.auth.logout();
  }
}
