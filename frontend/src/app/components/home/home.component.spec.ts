import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HomeComponent } from './home.component';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { By } from '@angular/platform-browser';

describe('HomeComponent', () => {
  let component: HomeComponent;
  let fixture: ComponentFixture<HomeComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [HomeComponent, HttpClientTestingModule, RouterTestingModule]
    }).compileComponents();

    fixture = TestBed.createComponent(HomeComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });

  it('should render a search input', () => {
    const input = fixture.debugElement.query(By.css('input[type="text"]'));
    expect(input).toBeTruthy();
  });

  it('should render site checkboxes', () => {
    const checkboxes = fixture.debugElement.queryAll(By.css('input[type="checkbox"]'));
    expect(checkboxes.length).toBe(component.availableSites.length);
  });

  it('toggleSite() should add a site to selectedSites', () => {
    component.selectedSites = [];
    component.toggleSite('thomann');
    expect(component.selectedSites).toContain('thomann');
  });

  it('toggleSite() should remove a site already selected', () => {
    component.selectedSites = ['thomann', 'gear4music'];
    component.toggleSite('thomann');
    expect(component.selectedSites).not.toContain('thomann');
    expect(component.selectedSites).toContain('gear4music');
  });

  it('onSearch() should not navigate with empty query', () => {
    const router = TestBed.inject(RouterTestingModule as any);
    component.searchQuery = '';
    const spy = spyOn(component['router'], 'navigate');
    component.onSearch();
    expect(spy).not.toHaveBeenCalled();
  });
});
