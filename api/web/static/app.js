// INSTRINDER — search UI. No dependencies: state machine + SSE client + components.

const $ = (s, el = document) => el.querySelector(s);
const T = JSON.parse($("#i18n").textContent);
const fill = (s, v) => s.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
const LOCALE = document.documentElement.lang;
const reduced = matchMedia("(prefers-reduced-motion: reduce)");
const PAGE = 20;          // results rendered per "More results"
const STREAM_CAP = 24;    // results shown while shops are still answering
const ANIMATED = 8;       // only the first ones get an entrance animation

const el = {
  body: document.body, topbar: $("#topbar"), brandWord: $("#brand-word"),
  form: $("#search"), card: $("#search-card"), q: $("#q"), clear: $("#clear"),
  suggest: $("#suggest"), filters: $("#filters"), major: $("#major"),
  tabs: $("#tabs"), ink: $(".tab-ink"), progress: $("#progress"),
  results: $("#results"), statusText: $("#status-text"), stop: $("#stop"),
  banner: $("#banner"), bannerText: $("#banner-text"), retry: $("#retry"),
  phases: $("#phases"), phasesToggle: $("#phases-toggle"), phasesSummary: $("#phases-summary"),
  phaseList: $("#phase-list"), sites: $("#sites"), sitesCount: $("#sites-count"),
  list: $("#list"), empty: $("#empty"), more: $("#more"),
  summary: $("#summary"), summaryList: $("#summary-list"),
  toast: $("#toast"), announce: $("#announce"), menu: $("#menu"),
  health: $("#health"), healthText: $("#health-text"),
  tplResult: $("#tpl-result"), tplSkeleton: $("#tpl-skeleton"), tplDeal: $("#tpl-deal"),
  sort: $("#sort"), sortWrap: $("#sort-wrap"), deals: $("#deals"), dealGrid: $("#deal-grid"),
  contact: $("#contact"), contactForm: $("#contact-form"), contactStatus: $("#contact-status"),
};
const DEALS = 8;          // cards in the right column

/* ---------- small helpers ---------- */
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const formats = new Map();  // Intl formatters are costly to build: one per currency/precision
const money = (n, cur = "EUR") => {
  if (n == null) return "–";
  const key = cur + (n >= 1000 ? 0 : 2);
  if (!formats.has(key)) formats.set(key, new Intl.NumberFormat(LOCALE, {
    style: "currency", currency: cur, maximumFractionDigits: n >= 1000 ? 0 : 2 }));
  return formats.get(key).format(n);
};
let regions;
try { regions = new Intl.DisplayNames([LOCALE], { type: "region" }); } catch { regions = null; }
const countryName = c => { try { return c && regions ? regions.of(c) : c || ""; } catch { return c || ""; } };
const secs = ms => (ms / 1000).toLocaleString(LOCALE, { maximumFractionDigits: 1 });
function announce(text) { el.announce.textContent = ""; requestAnimationFrame(() => { el.announce.textContent = text; }); }
let toastTimer;
function toast(text) {
  el.toast.textContent = text;
  el.toast.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.toast.classList.remove("show"), 1500);
}
function transition(update) {
  if (!document.startViewTransition || reduced.matches) { update(); return Promise.resolve(); }
  return document.startViewTransition(update).finished;
}
function countUp(node, to, render) {
  if (reduced.matches) { node.textContent = render(to); return; }
  const t0 = performance.now();
  const step = t => {
    const k = Math.min(1, (t - t0) / 400);
    node.textContent = render(Math.round(to * (1 - (1 - k) ** 3)));
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
function faviconFor(siteKey, name, box) {
  const img = $("img", box), letter = $("b", box);
  letter.textContent = (name || "?").trim()[0]?.toUpperCase() || "?";
  if (!siteKey) { img.remove(); return; }
  img.addEventListener("load", () => box.classList.add("has-img"), { once: true });
  img.addEventListener("error", () => img.remove(), { once: true });
  img.src = `/favicon/${encodeURIComponent(siteKey)}`;  // same origin: no third-party requests
}
function crumb(url) {
  try {
    const u = new URL(url);
    const parts = u.pathname.split("/").filter(Boolean).slice(0, 2).map(p => decodeURIComponent(p).slice(0, 24));
    return [u.origin, ...parts].join(" › ") + (u.pathname.split("/").filter(Boolean).length > 2 ? " › …" : "");
  } catch { return url || ""; }
}

/* ---------- theme ---------- */
const media = matchMedia("(prefers-color-scheme: dark)");
const currentTheme = () => document.documentElement.dataset.theme || (media.matches ? "dark" : "light");
$("#theme").addEventListener("click", e => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  const r = e.currentTarget.getBoundingClientRect();
  document.documentElement.style.setProperty("--tx", `${r.left + r.width / 2}px`);
  document.documentElement.style.setProperty("--ty", `${r.top + r.height / 2}px`);
  document.documentElement.classList.add("theme-switching");
  transition(() => { document.documentElement.dataset.theme = next; })
    .finally(() => document.documentElement.classList.remove("theme-switching"));
  try { localStorage.setItem("instrinder.theme", next); } catch {}  // raw string: read before paint
});

$("#lang").addEventListener("change", e => {
  const u = new URL(location.href);
  u.searchParams.set("lang", e.target.value);
  location.href = u;
});

/* ---------- brand entrance, once per session ---------- */
if (!new URLSearchParams(location.search).get("q") && !sessionStorage.getItem("instrinder.intro") && !reduced.matches) {
  const word = el.brandWord.textContent;
  el.brandWord.setAttribute("aria-label", word);
  el.brandWord.innerHTML = [...word].map((c, i) => `<span class="l" style="--i:${i}" aria-hidden="true">${c}</span>`).join("");
  el.brandWord.classList.add("intro");
  sessionStorage.setItem("instrinder.intro", "1");
}

/* ---------- search bar ---------- */
const HISTORY = "instrinder.history";
const history_ = {
  all: () => store.get(HISTORY, []),
  add(q) { store.set(HISTORY, [q, ...this.all().filter(x => x !== q)].slice(0, 8)); },
  remove(q) { store.set(HISTORY, this.all().filter(x => x !== q)); },
};
const autosize = !CSS.supports("field-sizing", "content");
function syncBar() {
  el.clear.hidden = !el.q.value;
  if (autosize) {
    el.q.style.height = "auto";
    el.q.style.height = Math.min(el.q.scrollHeight, 142) + "px";
  }
}
let active = -1;
function openSuggest() {
  const typed = el.q.value.trim().toLowerCase();
  const items = history_.all().filter(h => !typed || h.toLowerCase().includes(typed)).slice(0, 8);
  if (!items.length || document.activeElement !== el.q) { closeSuggest(); return; }
  active = -1;
  el.suggest.innerHTML = `<div class="suggest-label">${T.recent}</div>`;
  items.forEach((h, i) => {
    const row = document.createElement("div");
    row.className = "suggest-item";
    row.id = `sg-${i}`;
    row.setAttribute("role", "option");
    row.setAttribute("aria-selected", "false");
    row.innerHTML = `<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/></svg><span></span>
      <button type="button" class="icon-btn" tabindex="-1" aria-label="${T.remove}"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6 6 18"/></svg></button>`;
    $("span", row).textContent = h;
    row.addEventListener("mousedown", e => {
      e.preventDefault();
      if (e.target.closest("button")) { history_.remove(h); openSuggest(); return; }
      el.q.value = h; syncBar(); closeSuggest(); submit();
    });
    el.suggest.append(row);
  });
  el.suggest.hidden = false;
  el.card.classList.add("open");
}
function closeSuggest() {
  el.suggest.hidden = true;
  el.card.classList.remove("open");
  el.q.removeAttribute("aria-activedescendant");
  active = -1;
}
function moveSuggest(dir) {
  const rows = [...el.suggest.querySelectorAll(".suggest-item")];
  if (!rows.length) return;
  active = (active + dir + rows.length) % rows.length;
  rows.forEach((r, i) => r.setAttribute("aria-selected", String(i === active)));
  el.q.setAttribute("aria-activedescendant", rows[active].id);
  el.q.value = $("span", rows[active]).textContent;
  syncBar();
}
el.q.addEventListener("input", () => { syncBar(); openSuggest(); });
el.q.addEventListener("focus", openSuggest);
el.q.addEventListener("blur", () => setTimeout(closeSuggest, 120));
el.q.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); closeSuggest(); submit(); }
  else if (e.key === "ArrowDown" && !el.suggest.hidden) { e.preventDefault(); moveSuggest(1); }
  else if (e.key === "ArrowUp" && !el.suggest.hidden) { e.preventDefault(); moveSuggest(-1); }
});
el.clear.addEventListener("click", () => { el.q.value = ""; syncBar(); el.q.focus(); });
el.form.addEventListener("submit", e => { e.preventDefault(); submit(); });

/* home chips: real search scopes (area, major shops) */
const scope = { area: "", priority: "" };
el.filters.addEventListener("click", e => {
  const chip = e.target.closest(".chip");
  if (!chip) return;
  if (chip === el.major) {
    scope.priority = scope.priority ? "" : "1";
    el.major.setAttribute("aria-pressed", String(!!scope.priority));
    return;
  }
  scope.area = chip.dataset.area;
  el.filters.querySelectorAll("[role=radio]").forEach(c => c.setAttribute("aria-checked", String(c === chip)));
});

document.addEventListener("keydown", e => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
  if (e.key === "/" && !typing) { e.preventDefault(); el.q.focus(); }
  if (e.key === "Escape") {
    if (!el.suggest.hidden) closeSuggest();
    else if (run?.busy) run.controller.abort();
  }
});

/* ---------- layout plumbing ---------- */
new ResizeObserver(() => {
  const h = el.body.dataset.view === "results" ? el.topbar.offsetHeight : 0;
  document.documentElement.style.setProperty("--header-h", h + "px");
}).observe(el.topbar);
addEventListener("scroll", () => el.topbar.classList.toggle("scrolled", scrollY > 4), { passive: true });

function setView(view) {
  if (el.body.dataset.view === view) return Promise.resolve();
  const apply = () => { el.body.dataset.view = view; };
  if (document.startViewTransition && !reduced.matches) return transition(apply);
  apply();
  $("#page").classList.remove("page-enter");
  void $("#page").offsetWidth;
  $("#page").classList.add("page-enter");
  return Promise.resolve();
}

/* ---------- tabs (client-side area filter of the results) ---------- */
let tab = "";
function moveInk() {
  const btn = el.tabs.querySelector('[aria-selected="true"]');
  if (!btn) return;
  el.ink.style.transform = `translateX(${btn.offsetLeft}px) scaleX(${btn.offsetWidth / 100})`;
}
el.tabs.addEventListener("click", e => {
  const btn = e.target.closest("[role=tab]");
  if (!btn) return;
  tab = btn.dataset.tab;
  el.tabs.querySelectorAll("[role=tab]").forEach(b => b.setAttribute("aria-selected", String(b === btn)));
  moveInk();
  if (run?.final) renderFinal(false);
});
addEventListener("resize", moveInk);

/* ---------- results rendering ---------- */
function resultNode(o, animateIndex) {
  const node = el.tplResult.content.firstElementChild.cloneNode(true);
  faviconFor(o.site_key, o.site, $(".fav", node));
  $(".src-site", node).textContent = o.site || "";
  $(".src-crumb", node).textContent = crumb(o.url);
  const a = $(".result-title a", node);
  a.textContent = o.name;
  if (o.url) a.href = o.url;
  const snip = $(".result-snippet", node);
  const b = document.createElement("b");
  b.textContent = money(o.price_eur, "EUR");
  snip.append(b);
  const extra = [];
  if (o.currency && o.currency !== "EUR") extra.push(money(o.price, o.currency));
  if (o.country) extra.push(countryName(o.country));
  if (o.discount_pct > 0 && o.original_price_eur) {
    const was = document.createElement("s");
    was.textContent = money(o.original_price_eur, "EUR");
    was.setAttribute("aria-label", `${T.was_price} ${was.textContent}`);
    snip.append(" ", was);
  }
  if (extra.length) snip.append(" · " + extra.join(" · "));
  if (o.discount_pct > 0) {
    const tag = document.createElement("span");
    tag.className = "tag tag--sale";
    tag.textContent = `−${o.discount_pct}%`;
    snip.append(tag);
  }
  if (o.is_accessory) {
    node.classList.add("accessory");
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = T.accessory;
    snip.append(tag);
  }
  $(".result-menu", node).addEventListener("click", ev => openMenu(ev.currentTarget, o));
  if (animateIndex != null && animateIndex < ANIMATED && !reduced.matches) {
    node.classList.add("enter");
    node.style.setProperty("--d", `${animateIndex * 50}ms`);
  }
  return node;
}
/* deals: discounted items, biggest discount first, in the right column */
function dealNode(o) {
  const node = el.tplDeal.content.firstElementChild.cloneNode(true);
  if (o.url) node.href = o.url;
  node.setAttribute("aria-label", `${o.name} — ${o.site} — −${o.discount_pct}%`);
  const box = $(".deal-img", node), img = $(".deal-img > img", node);
  const noImage = () => {
    box.classList.add("no-img");
    img.src = `/favicon/${encodeURIComponent(o.site_key)}`;  // shop icon as a placeholder
    img.style.width = img.style.height = "48px";
  };
  if (o.image) {
    img.addEventListener("error", noImage, { once: true });
    img.src = o.image;  // shop CDN; no referrer is sent
  } else noImage();
  $(".deal-badge", node).textContent = `−${o.discount_pct}%`;
  const shopIcon = $(".deal-shop img", node);
  shopIcon.src = `/favicon/${encodeURIComponent(o.site_key)}`;
  $(".deal-shop span", node).textContent = o.site;
  $(".deal-name", node).textContent = o.name;
  $(".deal-price b", node).textContent = money(o.price_eur, "EUR");
  $(".deal-price s", node).textContent = money(o.original_price_eur, "EUR");
  return node;
}
function renderDeals(offers) {
  const deals = offers
    .filter(o => o.discount_pct > 0 && !o.is_accessory && !o.discount_everywhere && o.url)
    .sort((a, b) => b.discount_pct - a.discount_pct || a.price_eur - b.price_eur)
    .slice(0, DEALS);
  el.dealGrid.replaceChildren(...deals.map(dealNode));
  el.deals.hidden = !deals.length;
}

/* sorting: relevance (default), price up/down, name; parts stay after items */
let sortMode = "relevance";
const byAccessory = (a, b) => (a.is_accessory ? 1 : 0) - (b.is_accessory ? 1 : 0);
const collator = new Intl.Collator(LOCALE, { sensitivity: "base", numeric: true });
const SORTS = {
  relevance: (a, b) => byAccessory(a, b) || b.relevance - a.relevance || a.price_eur - b.price_eur,
  price_asc: (a, b) => byAccessory(a, b) || a.price_eur - b.price_eur,
  price_desc: (a, b) => byAccessory(a, b) || b.price_eur - a.price_eur,
  alpha: (a, b) => collator.compare(a.name || "", b.name || ""),
};
el.sort.addEventListener("change", () => {
  sortMode = SORTS[el.sort.value] ? el.sort.value : "relevance";
  const u = new URL(location.href);
  if (sortMode === "relevance") u.searchParams.delete("sort"); else u.searchParams.set("sort", sortMode);
  history.replaceState(history.state, "", u);
  if (run?.final) { run.page = 1; renderFinal(false); }
});

function skeletons(n) {
  return Array.from({ length: n }, (_, i) => {
    const s = el.tplSkeleton.content.firstElementChild.cloneNode(true);
    s.querySelectorAll(".sk").forEach((sk, j) => sk.style.setProperty("--sd", `${(i * 4 + j) * 80}ms`));
    return s;
  });
}

let menuOffer = null;
function openMenu(btn, offer) {
  menuOffer = offer;
  const r = btn.getBoundingClientRect();
  el.menu.style.top = `${Math.min(r.bottom + 4, innerHeight - 150)}px`;
  el.menu.style.left = `${Math.max(8, Math.min(r.right - 200, innerWidth - 208))}px`;
  el.menu.showPopover?.();
  $("button", el.menu).focus();
}
el.menu.addEventListener("click", async e => {
  const act = e.target.closest("button")?.dataset.act;
  if (!act || !menuOffer) return;
  el.menu.hidePopover?.();
  if (act === "open") window.open(menuOffer.url, "_blank", "noopener");
  else {
    const text = act === "copy" ? menuOffer.url : JSON.stringify(menuOffer, null, 2);
    try { await navigator.clipboard.writeText(text); toast(T.copied); } catch { toast(text.slice(0, 80)); }
  }
});

/* ---------- search run: a small state machine ---------- */
// idle → submitting → loading → streaming → done | empty | error | partial | cancelled
let run = null;
const PHASES = ["prepare", "search", "filter", "rank"];
const CHECK = '<svg class="check" viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>';

function setState(state) {
  run.state = state;
  el.results.dataset.state = state;
  run.busy = ["submitting", "loading", "streaming"].includes(state);
  el.results.setAttribute("aria-busy", String(run.busy));
  el.form.classList.toggle("searching", run.busy);
  el.stop.hidden = !run.busy;
  el.sortWrap.hidden = run.busy || !run.final?.results.length;
  el.results.classList.toggle("loading", run.busy && run.shown);
}

function params(q) {
  const p = new URLSearchParams({ q });
  if (scope.area) p.set("area", scope.area);
  if (scope.priority) p.set("priority", scope.priority);
  if (sortMode !== "relevance") p.set("sort", sortMode);
  return p;
}

function submit(retry = false) {
  const q = el.q.value.trim();
  if (!q) { el.q.focus(); return; }
  el.card.classList.add("pressed");
  setTimeout(() => el.card.classList.remove("pressed"), 100);
  const p = params(q);
  if (!retry) history.pushState({ q }, "", "?" + p);
  search(q, p);
}

async function search(q, p) {
  run?.controller.abort();
  history_.add(q);
  const r = run = {
    q, controller: new AbortController(), t0: performance.now(), shown: false, shownAt: 0,
    sites: 0, done: 0, failed: [], offers: 0, streamed: 0, final: null, page: 1, dealPool: [],
  };
  setState("submitting");
  resetResults();
  setView("results");  // the transition runs while the request is already in flight
  document.title = `${q} — INSTRINDER`;
  if (matchMedia("(pointer: coarse)").matches) el.q.blur();

  // Nothing flashes under 150 ms; once shown, indicators stay 400 ms.
  r.showTimer = setTimeout(() => showLoading(r), 150);
  r.tick = setInterval(() => updateStatus(r), 1000);

  const url = "/search/stream?" + new URLSearchParams({
    query: q, ...(p.get("area") && { area: p.get("area") }), ...(p.get("priority") && { priority: p.get("priority") }),
  });
  try {
    await source(url, r.controller.signal, (kind, data) => r === run && onEvent(r, kind, data));
    if (r === run && !r.final && !r.errored) throw new Error("stream ended early");
  } catch (err) {
    if (r !== run) return;
    if (err.name === "AbortError") finish(r, "cancelled");
    else finish(r, "error", err);
  }
}

function resetResults() {
  el.list.replaceChildren();
  el.banner.hidden = el.empty.hidden = el.more.hidden = el.phases.hidden = el.summary.hidden = true;
  el.deals.hidden = el.sortWrap.hidden = true;
  el.dealGrid.replaceChildren();
  el.sites.querySelectorAll(".site-dot").forEach(d => d.remove());
  el.sitesCount.textContent = "";
  el.statusText.textContent = "";
  const labels = { prepare: T.phase_prepare, search: fill(T.phase_search, { n: "…" }),
    filter: T.phase_filter, rank: T.phase_rank };
  el.phaseList.innerHTML = PHASES.map(id =>
    `<li class="phase" data-phase="${id}" data-state="pending"><span class="phase-mark"><i class="pending"></i><span class="shape-loader"></span>${CHECK}</span><span class="phase-label">${labels[id]}</span><span class="phase-detail"></span></li>`).join("");
  el.phasesToggle.setAttribute("aria-expanded", "true");
  tab = "";
  el.tabs.querySelectorAll("[role=tab]").forEach(b => { b.setAttribute("aria-selected", String(!b.dataset.tab)); $(".tab-count", b).textContent = ""; });
  el.progress.className = "progress";
  el.progress.style.removeProperty("--p");
  requestAnimationFrame(moveInk);
}

function showLoading(r) {
  if (r !== run || !r.busy) return;
  r.shown = true; r.shownAt = performance.now();
  setState(r.state === "submitting" ? "loading" : r.state);
  el.progress.hidden = false;
  el.phases.hidden = false;
  el.list.append(...skeletons(4));
  updateStatus(r);
  announce(T.searching);
}

function updateStatus(r) {
  if (r !== run || !r.busy || !r.shown) return;
  const elapsed = Math.round((performance.now() - r.t0) / 1000);
  el.statusText.innerHTML = `${T.searching} · <span class="num">${elapsed} s</span>`;
  // Long job with measurable progress: switch to the wavy determinate bar.
  if (r.sites && performance.now() - r.t0 > 5000) el.progress.classList.add("wavy");
}

function phaseRow(id) { return el.phaseList.querySelector(`[data-phase="${id}"]`); }
function setPhase(id, state, detail) {
  const row = phaseRow(id);
  if (!row) return;
  if (state) row.dataset.state = state;
  if (detail != null) $(".phase-detail", row).textContent = detail;
}

function onEvent(r, kind, data) {
  if (kind === "start") {
    r.sites = data.sites.length;
    $(".phase-label", phaseRow("search")).textContent = fill(T.phase_search, { n: r.sites });
    if (data.translated_query) setPhase("prepare", null, " · " + fill(T.phase_translate, { q: data.translated_query }));
    r.translated = data.translated_query;
  } else if (kind === "phase") {
    setPhase(data.id, data.status);
  } else if (kind === "site") {
    r.done = data.done;
    if (data.status === "error") r.failed.push(data.name);
    if (data.status !== "error") r.offers += data.relevant.length;
    addSiteDot(r, data);
    setPhase("search", null, " · " + fill(T.progress, { done: data.done, total: data.total }));
    el.progress.classList.add("determinate");
    el.progress.style.setProperty("--p", `${(data.done / data.total) * 100}%`);
    if (data.relevant.length) streamResults(r, data.relevant);
  } else if (kind === "done") {
    r.final = data;
    finish(r, data.total_results ? (r.failed.length ? "partial" : "done") : "empty");
  } else if (kind === "error") {
    r.errored = true;
    finish(r, "error", new Error(data.message));
  }
}

function addSiteDot(r, s) {
  const dot = document.createElement("span");
  dot.className = `site-dot ${s.status}`;
  dot.title = `${s.name}${s.status === "error" ? " — " + (s.error || "") : ""}`;
  dot.style.animationDelay = reduced.matches ? "0ms" : `${(el.sites.children.length % 6) * 50}ms`;
  if (s.status === "error") dot.textContent = "!";
  else {
    const img = document.createElement("img");
    img.alt = ""; img.loading = "lazy"; img.width = img.height = 14;
    img.addEventListener("error", () => { img.remove(); dot.textContent = (s.name || "?")[0]; }, { once: true });
    img.src = `/favicon/${encodeURIComponent(s.key)}`;
    dot.append(img);
  }
  el.sites.append(dot);
  el.sitesCount.textContent = fill(T.progress, { done: s.done, total: s.total });
  el.sites.scrollLeft = document.dir === "rtl" ? -el.sites.scrollWidth : el.sites.scrollWidth;
}

function streamResults(r, offers) {
  if (r.state !== "streaming") setState("streaming");
  // Deals fill the right column as shops answer (it sits beside the list, so
  // nothing moves); the final list re-checks them once accessories are known.
  const sale = offers.filter(o => o.discount_pct > 0);
  if (sale.length) { r.dealPool.push(...sale); renderDeals(r.dealPool); }
  for (const o of offers) {
    if (r.streamed >= STREAM_CAP) break;
    const sk = el.list.querySelector(".skeleton");
    const node = resultNode(o, r.streamed);
    if (sk) sk.replaceWith(node); else el.list.append(node);
    r.streamed++;
  }
}

function finish(r, state, err) {
  clearTimeout(r.showTimer);
  const wait = r.shown ? Math.max(0, 400 - (performance.now() - r.shownAt)) : 0;
  setTimeout(() => {
    if (r !== run) return;
    clearInterval(r.tick);
    el.list.querySelectorAll(".skeleton").forEach(s => s.remove());
    setState(state);
    endProgress();
    const took = r.final ? r.final.search_time_seconds * 1000 : performance.now() - r.t0;
    if (!el.phases.hidden || r.shown) collapsePhases(took, state);

    if (state === "done" || state === "partial") renderFinal(true);
    if (state === "partial") showBanner(fill(T.partial, { n: r.failed.length }), "warn");
    if (state === "empty") renderEmpty(r.q);
    if (state === "error") {
      showBanner(T.error, "error", err?.message);
      el.statusText.textContent = "";
      announce(T.error);
    }
    if (state === "cancelled") { el.statusText.textContent = T.stopped; announce(T.stopped); }
  }, wait);
}

function endProgress() {
  if (el.progress.hidden) return;
  el.progress.classList.add("determinate");
  el.progress.style.setProperty("--p", "100%");
  setTimeout(() => el.progress.classList.add("fade"), 150);
  setTimeout(() => { el.progress.hidden = true; }, 400);
}

function collapsePhases(ms, state) {
  el.phases.hidden = false;
  const ok = !["error", "cancelled"].includes(state);
  if (ok) PHASES.forEach(id => { phaseRow(id).dataset.state = "done"; });
  el.phasesSummary.textContent = ok
    ? fill(T.phases_done, { steps: PHASES.length, secs: secs(ms) })
    : `${state === "error" ? T.error : T.stopped} · ${secs(ms)} s`;
  // Collapse in the same frame the final list replaces the streamed one: an
  // animated collapse would slide every result up and count as layout shift.
  const body = $("#phases-body");
  body.style.transition = "none";
  el.phasesToggle.setAttribute("aria-expanded", "false");
  requestAnimationFrame(() => requestAnimationFrame(() => body.style.removeProperty("transition")));
}
el.phasesToggle.addEventListener("click", () => {
  const open = el.phasesToggle.getAttribute("aria-expanded") === "true";
  el.phasesToggle.setAttribute("aria-expanded", String(!open));
});

function visibleResults() {
  const all = run.final.results;
  return (tab ? all.filter(o => o.area === tab) : all.slice()).sort(SORTS[sortMode]);
}

function renderFinal(first) {
  const r = run, data = r.final, shown = visibleResults();
  const animate = first && r.streamed === 0;
  // A fresh container: the sorted list replaces the streamed one without
  // sliding existing boxes (no layout shift).
  const list = el.list.cloneNode(false);
  list.append(...shown.slice(0, PAGE * r.page).map((o, i) => resultNode(o, animate ? i : null)));
  el.list.replaceWith(list);
  el.list = list;
  el.more.hidden = shown.length <= PAGE * r.page;
  el.empty.hidden = true;
  el.sortWrap.hidden = !data.results.length;
  renderDeals(shown);
  // tab counters
  el.tabs.querySelectorAll("[role=tab]").forEach(b => {
    const n = b.dataset.tab ? data.results.filter(o => o.area === b.dataset.tab).length : data.results.length;
    $(".tab-count", b).textContent = n;
  });
  requestAnimationFrame(moveInk);
  if (!first) return;
  const shops = new Set(data.results.map(o => o.site_key)).size;
  const line = n => fill(T.results_line, { n, shops, secs: secs(data.search_time_seconds * 1000) });
  countUp(el.statusText, data.total_results, line);
  announce(line(data.total_results));
  renderSummary(r, shops);
}

el.more.addEventListener("click", () => {
  run.page++;
  const before = el.list.children.length;
  renderFinal(false);
  el.list.children[before]?.querySelector("a")?.focus();
});

function renderSummary(r, shops) {
  const d = r.final;
  const rows = [
    [T.shops_queried, d.sites_queried],
    [T.shops_offers, shops],
    [T.shops_failed, r.failed.length],
    [T.duration, secs(d.search_time_seconds * 1000) + " s"],
    [T.lowest, money(d.lowest_price, "EUR")],
    [T.average, money(d.market_average, "EUR")],
  ];
  if (d.translated_query) rows.push([T.translated, d.translated_query]);
  el.summaryList.replaceChildren(...rows.flatMap(([k, v]) => {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = k; dd.textContent = v;
    return [dt, dd];
  }));
  el.summary.hidden = false;
}

function renderEmpty(q) {
  el.statusText.textContent = "";
  el.empty.innerHTML = `<svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 5 5M8 10.5h5"/></svg><h2></h2>
    <ul><li>${T.tip_spelling}</li><li>${T.tip_fewer}</li><li>${T.tip_model}</li></ul>`;
  $("h2", el.empty).textContent = fill(T.none, { q });
  el.empty.hidden = false;
  announce(fill(T.none, { q }));
  el.q.focus();
}

function showBanner(text, kind, detail) {
  el.bannerText.textContent = text;
  el.bannerText.title = detail || "";
  el.banner.className = `banner ${kind}`;
  el.banner.hidden = false;
}
el.retry.addEventListener("click", () => submit(true));
el.stop.addEventListener("click", () => run?.controller.abort());

/* ---------- event source: the real stream, or demo data in development ---------- */
async function sse(url, signal, on) {
  const res = await fetch(url, { signal, headers: { Accept: "text/event-stream" } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buf += value;
    let cut;
    while ((cut = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, cut);
      buf = buf.slice(cut + 2);
      let kind = "message", data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event:")) kind = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) on(kind, JSON.parse(data));
    }
  }
}
const urlParams = new URLSearchParams(location.search);
const demo = urlParams.get("demo");
const devHost = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
let source = sse;
if (demo && devHost) source = (await import("/static/demo.js")).demoSource(demo);

/* ---------- routing: ?q= is shareable, back/forward work ---------- */
function fromUrl() {
  const p = new URLSearchParams(location.search);
  const q = p.get("q");
  scope.area = p.get("area") || "";
  scope.priority = p.get("priority") || "";
  sortMode = SORTS[p.get("sort")] ? p.get("sort") : "relevance";
  el.sort.value = sortMode;
  el.filters.querySelectorAll("[role=radio]").forEach(c => c.setAttribute("aria-checked", String(c.dataset.area === scope.area)));
  el.major.setAttribute("aria-pressed", String(!!scope.priority));
  if (q) {
    el.q.value = q; syncBar();
    search(q, p);
  } else {
    run?.controller.abort();
    run = null;
    el.q.value = ""; syncBar();
    document.title = document.title.replace(/^.* — INSTRINDER/, "INSTRINDER");
    setView("home");
  }
}
addEventListener("popstate", fromUrl);
$("#brand").addEventListener("click", e => {
  e.preventDefault();
  history.pushState({}, "", location.pathname + (urlParams.get("demo") ? `?demo=${demo}` : ""));
  fromUrl();
});

/* ---------- contact form (the recipient lives only in the server's config) ---------- */
$("#contact-open").addEventListener("click", () => {
  el.contactStatus.textContent = "";
  el.contactStatus.className = "form-status";
  el.contact.showModal();
  $("input[name=name]", el.contactForm).focus();
});
el.contact.addEventListener("click", e => {
  if (e.target.closest("[data-close]") || e.target === el.contact) el.contact.close();  // backdrop click
});
el.contactForm.addEventListener("submit", async e => {
  e.preventDefault();
  const form = el.contactForm, status = el.contactStatus, send = $("#contact-send");
  const say = (text, kind = "") => { status.textContent = text; status.className = `form-status ${kind}`; };
  if (!form.checkValidity()) { say(T.invalid_form, "err"); form.reportValidity(); return; }
  send.disabled = true;
  say(T.sending);
  try {
    const res = await fetch("/contact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...Object.fromEntries(new FormData(form)), lang: LOCALE }),
    });
    if (res.ok) { say(T.sent, "ok"); form.reset(); }
    else say({ 400: T.invalid_form, 422: T.invalid_form, 429: T.too_many, 503: T.contact_off }[res.status] || T.send_failed, "err");
  } catch {
    say(T.send_failed, "err");
  } finally {
    send.disabled = false;
  }
});

/* ---------- footer: backend health ---------- */
fetch("/health").then(r => r.ok ? r.json() : Promise.reject())
  .then(() => { el.health.classList.add("up"); el.healthText.textContent = T.online; })
  .catch(() => { el.health.classList.add("down"); el.healthText.textContent = T.offline; });

if (!urlParams.get("q") && matchMedia("(pointer: fine)").matches) el.q.focus();
fromUrl();
