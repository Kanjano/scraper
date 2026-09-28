// Development only (loaded on localhost with ?demo=fast|slow|empty|error|partial):
// fake search events with realistic timing, to try every UI state without scraping.

const SHOPS = [
  ["thomann", "Thomann", "https://www.thomann.de", "europe", "DE", "EUR"],
  ["sweetwater", "Sweetwater", "https://www.sweetwater.com", "usa", "US", "USD"],
  ["gear4music", "Gear4music", "https://www.gear4music.com", "europe", "GB", "GBP"],
  ["reverb", "Reverb", "https://reverb.com", "usa", "US", "USD"],
  ["ishibashi-music", "Ishibashi Music", "https://intl.ishibashi.co.jp", "asia", "JP", "JPY"],
  ["swee-lee", "Swee Lee", "https://www.sweelee.com.sg", "asia", "SG", "SGD"],
  ["bax-music", "Bax Music", "https://www.bax-shop.nl", "europe", "NL", "EUR"],
  ["perfect-circuit", "Perfect Circuit", "https://www.perfectcircuit.com", "usa", "US", "USD"],
  ["scan-pro-audio", "Scan Pro Audio", "https://www.scan.co.uk", "europe", "GB", "GBP"],
  ["chicago-music-exchange", "Chicago Music Exchange", "https://www.chicagomusicexchange.com", "usa", "US", "USD"],
  ["tom-lee-music", "Tom Lee Music", "https://www.tomleemusic.com.hk", "asia", "HK", "HKD"],
  ["musikhaus-kirstein", "Musikhaus Kirstein", "https://www.kirstein.de", "europe", "DE", "EUR"],
];
const RATE = { EUR: 1, USD: 0.92, GBP: 1.17, JPY: 0.0062, SGD: 0.68, HKD: 0.118 };

const sleep = (ms, signal) => new Promise((resolve, reject) => {
  const t = setTimeout(resolve, ms);
  signal.addEventListener("abort", () => { clearTimeout(t); reject(new DOMException("Aborted", "AbortError")); }, { once: true });
});

function offers(shop, query, n, seed) {
  const [key, name, url, area, country, currency] = shop;
  return Array.from({ length: n }, (_, i) => {
    const eur = Math.round(180 + ((seed * 7919 + i * 104729) % 3200));
    const price = Math.round(eur / RATE[currency]);
    return {
      site: name, site_key: key, area, country, currency,
      name: `${query} ${["Standard", "Deluxe", "Pro", "Vintage", "Limited Edition"][(seed + i) % 5]} ${2019 + ((seed + i) % 7)}`,
      price, price_eur: eur, url: `${url}/product/${encodeURIComponent(query)}-${i}`,
      data_quality: "structured", is_accessory: i === n - 1 && n > 2, rating: null,
      // Every third offer is on sale; no product photo in demo data (placeholder shown).
      discount_pct: (seed + i) % 3 === 0 ? 10 + ((seed * 7 + i * 5) % 30) : 0,
      original_price_eur: (seed + i) % 3 === 0 ? Math.round(eur / (1 - (10 + ((seed * 7 + i * 5) % 30)) / 100)) : null,
      relevance: +(0.4 + ((seed * 13 + i * 7) % 60) / 100).toFixed(2), image: null,
    };
  });
}

const PLANS = {
  fast: { shops: 5, gap: 20, empty: false, errorAt: null, failing: [] },
  slow: { shops: 12, gap: 900, empty: false, errorAt: null, failing: [] },
  empty: { shops: 8, gap: 250, empty: true, errorAt: null, failing: [] },
  error: { shops: 12, gap: 500, empty: false, errorAt: 5, failing: [] },
  partial: { shops: 12, gap: 400, empty: false, errorAt: null, failing: [2, 7, 9] },
};

export function demoSource(kind) {
  const plan = PLANS[kind] || PLANS.slow;
  return async (url, signal, on) => {
    const query = new URL(url, location.href).searchParams.get("query") || "demo";
    const shops = SHOPS.slice(0, plan.shops);
    const t0 = performance.now();
    on("phase", { id: "prepare", status: "active" });
    await sleep(plan.gap / 3, signal);
    on("start", { query, translated_query: kind === "slow" ? `${query} (en)` : null,
      sites: shops.map(([key, name, u, area]) => ({ key, name, url: u, area })) });
    on("phase", { id: "prepare", status: "done" });
    on("phase", { id: "search", status: "active" });
    const all = [];
    for (let i = 0; i < shops.length; i++) {
      await sleep(plan.gap * (0.5 + ((i * 37) % 10) / 10), signal);
      if (i === 0) on("phase", { id: "filter", status: "active" });
      if (plan.errorAt === i) { on("error", { message: "demo: backend error" }); return; }
      const failed = plan.failing.includes(i);
      const found = plan.empty || failed ? [] : offers(shops[i], query, 1 + (i % 4), i + 1);
      all.push(...found);
      on("site", { key: shops[i][0], name: shops[i][1], status: failed ? "error" : found.length ? "ok" : "empty",
        error: failed ? "HTTPError: 500 (demo)" : null, offers: found.length, relevant: found, done: i + 1, total: shops.length });
    }
    on("phase", { id: "search", status: "done" });
    on("phase", { id: "filter", status: "done" });
    on("phase", { id: "rank", status: "active" });
    await sleep(plan.gap / 2, signal);
    on("phase", { id: "rank", status: "done" });
    all.sort((a, b) => (a.is_accessory - b.is_accessory) || a.price_eur - b.price_eur);
    const main = all.filter(o => !o.is_accessory);
    on("done", {
      query, translated_query: null, sites_queried: shops.length, total_results: all.length,
      lowest_price: main[0]?.price_eur ?? null, lowest_price_site: main[0]?.site ?? null,
      market_average: main.length ? Math.round(main.reduce((s, o) => s + o.price_eur, 0) / main.length) : null,
      results: all.map((o, i) => ({ rank: i + 1, ...o })),
      search_time_seconds: (performance.now() - t0) / 1000,
    });
  };
}
