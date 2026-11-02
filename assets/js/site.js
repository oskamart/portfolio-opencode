/* ============================================================================
   osys.one — site behaviour (opencode agent)

   Three jobs:
     1. Read assets/manifest.json and write the measured figures into the page.
     2. Draw the hero scope — a live oscilloscope trace driven by the real
        benchmark numbers rather than by noise.
     3. Wire the small interactions: the mobile nav and the section markers.
   ========================================================================= */

/* ── 1. measured figures ─────────────────────────────────────────────────── */

const fmt = new Intl.NumberFormat("en-GB");

/** Resolve a dotted path such as "systems.uvmstack.code_loc" against an object. */
function dig(obj, path) {
  return path.split(".").reduce((acc, key) => (acc == null ? acc : acc[key]), obj);
}

async function loadManifest() {
  try {
    const res = await fetch("assets/manifest.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(String(res.status));
    return await res.json();
  } catch {
    return null;
  }
}

function renderMetrics(manifest) {
  if (!manifest) return;

  for (const el of document.querySelectorAll("[data-metric]")) {
    const raw = dig(manifest, el.dataset.metric);
    if (raw === undefined || raw === null) continue;

    if (el.dataset.metric === "generated") {
      const d = new Date(raw);
      el.textContent = Number.isNaN(d.valueOf())
        ? raw
        : d.toISOString().slice(0, 10);
    } else if (typeof raw === "number") {
      el.textContent = fmt.format(raw);
    } else {
      el.textContent = String(raw);
    }
  }

  const stamp = document.getElementById("foot-stamp");
  if (stamp && manifest.generated) {
    stamp.textContent =
      `Manifest generated ${manifest.generated.replace("T", " ").slice(0, 19)} UTC`;
  }

  const status = document.getElementById("metrics-status");
  if (status && manifest.totals) {
    status.textContent =
      `Figures loaded from source: ${fmt.format(manifest.totals.local_code_loc)} lines, ` +
      `${fmt.format(manifest.totals.files)} files, ${fmt.format(manifest.totals.commits)} commits.`;
  }
}

/* ── 2. the hero scope ──────────────────────────────────────────────────── */

/**
 * A two-channel oscilloscope trace. The two channels carry the real
 * per-suite pass rates of the leading model and the seven-model oracle, so
 * the shape of the trace is the benchmark rather than random noise.
 */
function initScope() {
  const canvas = document.getElementById("scope");
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  const reduceQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  let reduced = reduceQuery.matches;

  let w = 0;
  let h = 0;
  let dpr = 1;
  let raf = 0;
  let t = 0;
  let paused = false;
  let series = [];

  // The eight suites and the leading model's rate on each, plus the oracle.
  const RATES = [73.0, 72.0, 66.4, 48.9, 46.6, 45.8, 44.8, 42.3];
  const ORACLE = 68.8;

  function buildSeries() {
    // The trace is the rate per suite, resampled into a smooth sweep, with a
    // second channel showing where the oracle ceiling sits.
    const pts = RATES.map((r, i) => ({
      x: i / (RATES.length - 1),
      y: (r - 30) / 50,
    }));
    series = [];
    for (let i = 0; i <= 400; i++) {
      const u = i / 400;
      const f = u * (pts.length - 1);
      const i0 = Math.floor(f);
      const i1 = Math.min(i0 + 1, pts.length - 1);
      const k = f - i0;
      const smooth = k * k * (3 - 2 * k);
      const y = pts[i0].y * (1 - smooth) + pts[i1].y * smooth;
      series.push({ x: u, y });
    }
  }
  buildSeries();

  function resize() {
    const rect = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = Math.max(1, Math.round(rect.width));
    h = Math.max(1, Math.round(rect.height));
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function drawGraticule(top) {
    ctx.save();
    ctx.strokeStyle = "rgba(23, 21, 15, 0.07)";
    ctx.lineWidth = 1;
    const step = Math.max(40, Math.round(w / 16));
    ctx.beginPath();
    for (let x = step / 2; x < w; x += step) {
      ctx.moveTo(Math.round(x) + 0.5, top);
      ctx.lineTo(Math.round(x) + 0.5, h);
    }
    for (let y = top; y < h; y += step) {
      ctx.moveTo(0, Math.round(y) + 0.5);
      ctx.lineTo(w, Math.round(y) + 0.5);
    }
    ctx.stroke();
    ctx.restore();
  }

  // The plot area sits below a caption strip so the labels never touch a trace.
  const CAPTION = 30;

  function trace(offset, amp, colour, alpha, width) {
    const base = h * (0.58 + offset);
    ctx.save();
    ctx.beginPath();
    for (let i = 0; i < series.length; i++) {
      const p = series[i];
      const x = p.x * w;
      const y = base - p.y * h * amp;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = colour;
    ctx.globalAlpha = alpha;
    ctx.lineWidth = width;
    ctx.lineJoin = "round";
    ctx.stroke();
    ctx.restore();
  }

  function render() {
    ctx.clearRect(0, 0, w, h);
    drawGraticule(CAPTION);

    // Channel 1: the model's per-suite rate.
    trace(0.06, 0.5, "#17150f", 0.82, 1.6);

    // Channel 2: the seven-model oracle, as a ceiling line.
    const oy = h * (0.58 + 0.06) - ((ORACLE - 30) / 50) * h * 0.5;
    ctx.save();
    ctx.strokeStyle = "#a8321e";
    ctx.globalAlpha = 0.5;
    ctx.setLineDash([5, 5]);
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(0, Math.round(oy) + 0.5);
    ctx.lineTo(w, Math.round(oy) + 0.5);
    ctx.stroke();
    ctx.restore();

    // The sweep: a bright dot travelling the trace.
    const u = (t * 0.055) % 1;
    const idx = Math.min(series.length - 1, Math.floor(u * (series.length - 1)));
    const p = series[idx];
    const cx = p.x * w;
    const cy = h * 0.64 - p.y * h * 0.5;

    ctx.save();
    ctx.strokeStyle = "rgba(168, 50, 30, 0.3)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(Math.round(cx) + 0.5, CAPTION);
    ctx.lineTo(Math.round(cx) + 0.5, h);
    ctx.stroke();
    ctx.fillStyle = "#a8321e";
    ctx.beginPath();
    ctx.arc(cx, cy, 3.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // A caption strip above the plot, so nothing overlaps the trace.
    ctx.save();
    ctx.font = '10px "Plex Mono", monospace';
    ctx.fillStyle = "rgba(23, 21, 15, 0.45)";
    ctx.fillText("CH1  pass rate by suite", 12, 13);
    if (w > 380) {
      ctx.fillStyle = "rgba(168, 50, 30, 0.75)";
      ctx.fillText("CH2  seven-model oracle, 68.8%", 190, 13);
    } else {
      ctx.fillStyle = "rgba(168, 50, 30, 0.75)";
      ctx.fillText("CH2  oracle 68.8%", 12, 25);
    }
    ctx.restore();
  }

  function loop() {
    t += 0.006;
    render();
    raf = requestAnimationFrame(loop);
  }

  function start() {
    if (reduced || paused) {
      render();
      return;
    }
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(loop);
  }

  resize();
  render();
  if (!reduced) start();

  window.addEventListener("resize", () => { resize(); render(); });

  reduceQuery.addEventListener("change", (e) => {
    reduced = e.matches;
    if (reduced) { cancelAnimationFrame(raf); render(); }
    else start();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) cancelAnimationFrame(raf);
    else start();
  });

  // Stop drawing when the hero has scrolled away.
  if ("IntersectionObserver" in window) {
    new IntersectionObserver((entries) => {
      for (const e of entries) {
        if (e.isIntersecting) start();
        else cancelAnimationFrame(raf);
      }
    }, { threshold: 0 }).observe(canvas);
  }
}

/* ── 3. interactions ─────────────────────────────────────────────────────── */

function initMobileNav() {
  const btn = document.querySelector(".head__menu");
  const panel = document.getElementById("mobnav");
  if (!btn || !panel) return;

  function set(open) {
    btn.setAttribute("aria-expanded", String(open));
    panel.hidden = !open;
  }

  btn.addEventListener("click", () => {
    set(btn.getAttribute("aria-expanded") !== "true");
  });

  panel.addEventListener("click", (e) => {
    if (e.target.tagName === "A") set(false);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && btn.getAttribute("aria-expanded") === "true") {
      set(false);
      btn.focus();
    }
  });

  const wide = window.matchMedia("(min-width: 46.0625rem)");
  wide.addEventListener("change", (e) => { if (e.matches) set(false); });
}

/** Mark the nav entry for the section currently in view. */
function initScrollSpy() {
  const links = [...document.querySelectorAll(".head__nav a")];
  if (!links.length || !("IntersectionObserver" in window)) return;

  const targets = links
    .map((a) => document.querySelector(a.getAttribute("href")))
    .filter(Boolean);

  const spy = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        for (const a of links) {
          const active = a.getAttribute("href") === `#${entry.target.id}`;
          a.style.color = active ? "var(--red)" : "";
          a.style.borderBottomColor = active ? "var(--red)" : "transparent";
        }
      }
    },
    { rootMargin: "-45% 0px -50% 0px" }
  );

  targets.forEach((t) => spy.observe(t));
}

/* ── boot ───────────────────────────────────────────────────────────────── */

async function boot() {
  initMobileNav();
  initScrollSpy();
  initScope();

  const manifest = await loadManifest();
  renderMetrics(manifest);

  document.documentElement.dataset.metrics = manifest ? "loaded" : "missing";
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot, { once: true });
} else {
  boot();
}
