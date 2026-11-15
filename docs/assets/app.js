(function () {
'use strict';
var $ = function (s, r) { return (r || document).querySelector(s); };
var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
var esc = function (v) { return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); };
var fmt = function (n) { return n == null ? '–' : Number(n).toLocaleString('en-US'); };
var safeUrl = function (u) { return /^https?:\/\//i.test(u || '') ? u : ''; };
var css = function (n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };
var TABS = ['overview', 'trends', 'sources', 'repos', 'insights', 'about', 'comments'];
var S, SER, charts = {}, state = { period: 'daily', range: 90, sortK: 'score', sortD: -1, page: 1, sel: [], tab: 'overview', lastTab: 'overview' };
var PAL = ['#0b5fff', '#12a150', '#e5484d', '#f5a524', '#8e4ec6', '#0aa5a5'];
var DEF = { theme: 'system', tab: 'overview', rows: 25, compact: false, hideForks: false, motion: false };
var prefs = (function () { var p = {}; try { p = JSON.parse(localStorage.getItem('prefs') || '{}'); } catch (e) {} var o = {}; Object.keys(DEF).forEach(function (k) { o[k] = (k in p && typeof p[k] === typeof DEF[k]) ? p[k] : DEF[k]; }); return o; })();
function savePrefs() { try { localStorage.setItem('prefs', JSON.stringify(prefs)); } catch (e) {} }
function applyPrefs() {
  var d = document.documentElement;
  if (prefs.theme === 'system') { d.removeAttribute('data-theme'); try { localStorage.removeItem('theme'); } catch (e) {} }
  else { d.setAttribute('data-theme', prefs.theme); try { localStorage.setItem('theme', prefs.theme); } catch (e) {} }
  d.classList.toggle('compact', prefs.compact); d.classList.toggle('calm', prefs.motion);
}

function mk(id, cfg) {
  if (typeof Chart === 'undefined') return;
  var el = $(id); if (!el) return;
  if (charts[id]) charts[id].destroy();
  Chart.defaults.color = css('--mut'); Chart.defaults.borderColor = css('--bd');
  Chart.defaults.font.family = 'system-ui,-apple-system,Segoe UI,Roboto,sans-serif';
  cfg.options = cfg.options || {}; cfg.options.maintainAspectRatio = false;
  charts[id] = new Chart(el, cfg);
}
function pctHtml(a, b) {
  if (!b) return '';
  var p = Math.round((a - b) * 100 / b);
  return '<div class="d ' + (p >= 0 ? 'up' : 'down') + '">' + (p >= 0 ? '▲ ' : '▼ ') + Math.abs(p) + '% vs previous 7 days</div>';
}
function spark(a) { var m = Math.max(1, Math.max.apply(null, a)); return a.map(function (x) { return '▁▂▃▄▅▆▇█'[Math.min(7, Math.floor(x * 7 / m))]; }).join(''); }

/* ---------- Overview ---------- */
function kpis() {
  var t = S.totals;
  var k = [
    ['Views, last 7 days', t.views_7d, pctHtml(t.views_7d, t.views_prev7)],
    ['Views, last 30 days', t.views_30d, ''],
    ['Clones, last 30 days', t.clones_30d, '<div class="d mut">includes bots and CI</div>'],
    ['Unique visitors, 14 days*', t.vu14, '<div class="d mut">summed per repository</div>'],
    ['Stars', t.stars, ''], ['Forks', t.forks, ''],
    ['Public repositories', t.repos, '<div class="d mut">' + fmt(t.active_30d) + ' with views in 30 days</div>'],
    ['Google referrals, 14 days', t.google_14d, '']
  ];
  $('#kpis').innerHTML = k.map(function (x) { return '<div class="card kpi"><div class="l">' + esc(x[0]) + '</div><div class="v">' + fmt(x[1]) + '</div>' + x[2] + '</div>'; }).join('');
}
function overviewChart() {
  var d = S.daily.slice(-30);
  mk('#c-overview', { type: 'line', data: { labels: d.map(function (r) { return r[0].slice(5); }), datasets: [
    { label: 'Views', data: d.map(function (r) { return r[1]; }), borderColor: css('--ac'), backgroundColor: css('--ac'), pointRadius: 0, tension: .25 },
    { label: 'Clones', data: d.map(function (r) { return r[3]; }), borderColor: '#12a150', backgroundColor: '#12a150', pointRadius: 0, tension: .25, yAxisID: 'y1' }] },
    options: { interaction: { mode: 'index', intersect: false }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Views' } }, y1: { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: 'Clones' } }, x: { ticks: { maxTicksLimit: 8 } } } } });
}
function repoLink(r) { return '<a href="#repo/' + encodeURIComponent(r.name) + '">' + esc(r.name) + '</a>'; }
function miniTable(id, list) {
  var el = $(id);
  if (!list.length) { el.innerHTML = '<tr><td class="empty">No data yet.</td></tr>'; return; }
  el.innerHTML = '<thead><tr><th>Repository</th><th>Views 30d</th><th>Clones 30d</th><th>★</th></tr></thead><tbody>' +
    list.map(function (r) { return '<tr><td>' + repoLink(r) + '</td><td>' + fmt(r.v30) + '</td><td>' + fmt(r.c30) + '</td><td>' + r.stars + '</td></tr>'; }).join('') + '</tbody>';
}
function overview() {
  kpis(); overviewChart();
  var el = S.repos.filter(function (r) { return !r.fork && !r.archived; });
  miniTable('#t-top', el.filter(function (r) { return r.tier === 'top'; }).slice(0, 8));
  miniTable('#t-low', el.filter(function (r) { return r.tier === 'low'; }).slice(-8).reverse());
  $('#highlights').innerHTML = S.insights.length ? S.insights.slice(0, 4).map(function (i) { return '<p><b>' + esc(i.title) + '.</b> ' + esc(i.text) + '</p>'; }).join('') : '<p class="mut">Insights appear once enough data has been collected.</p>';
}

/* ---------- Trends ---------- */
function trends() {
  var rows = S[state.period], daily = state.period === 'daily';
  if (daily && state.range) rows = rows.slice(-state.range);
  var lab = rows.map(function (r) { return r[0]; });
  var v = rows.map(function (r) { return r[1]; }), c = rows.map(function (r) { return daily ? r[3] : r[2]; });
  var ma = null;
  if (daily) { var all = S.daily.map(function (r) { return r[1]; }), off = all.length - rows.length; ma = rows.map(function (_, i) { var a = Math.max(0, off + i - 6), sl = all.slice(a, off + i + 1); return Math.round(sl.reduce(function (x, y) { return x + y; }, 0) / sl.length * 10) / 10; }); }
  mk('#c-trend', { type: daily ? 'line' : 'bar', data: { labels: lab, datasets: [
    { label: 'Views', data: v, borderColor: css('--ac'), backgroundColor: css('--ac'), pointRadius: 0, tension: .2 },
    { label: 'Clones', data: c, borderColor: '#12a150', backgroundColor: '#12a150', pointRadius: 0, tension: .2, yAxisID: 'y1' }].concat(ma ? [{ label: 'Views, 7-day average', data: ma, borderColor: '#f5a524', backgroundColor: '#f5a524', borderDash: [5, 4], pointRadius: 0, tension: .3 }] : []) },
    options: { interaction: { mode: 'index', intersect: false }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Views' } }, y1: { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: 'Clones' } }, x: { ticks: { maxTicksLimit: 12 } } } } });
  trendTable(rows, daily);
  heat();
  var names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  mk('#c-weekday', { type: 'bar', data: { labels: names, datasets: [{ label: 'Views', data: S.weekday, backgroundColor: css('--ac') }] }, options: { plugins: { legend: { display: false } } } });
  var h = S.history;
  mk('#c-stars', { type: 'line', data: { labels: h.map(function (r) { return r[0]; }), datasets: [
    { label: 'Stars', data: h.map(function (r) { return r[2]; }), borderColor: css('--ac'), pointRadius: h.length < 3 ? 4 : 0 },
    { label: 'Forks', data: h.map(function (r) { return r[3]; }), borderColor: '#12a150', pointRadius: h.length < 3 ? 4 : 0 }] }, options: { scales: { y: { beginAtZero: true } } } });
  $('#stars-note').textContent = h.length < 7 ? 'Star and fork history started on ' + h[0][0] + ' and grows with every daily update.' : '';
  mk('#c-created', { type: 'bar', data: { labels: S.created_daily.map(function (r) { return r[0].slice(5); }), datasets: [{ label: 'New repositories', data: S.created_daily.map(function (r) { return r[1]; }), backgroundColor: css('--ac') }] }, options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { ticks: { maxTicksLimit: 10 } } } } });
}

function heat() {
  var el = $('#heat'); if (!el) return;
  var first = new Date(S.first_data_day + 'T00:00:00Z'), last = new Date(S.last_data_day + 'T00:00:00Z');
  var start = new Date(Math.max(first.getTime(), last.getTime() - 181 * 864e5)), map = {}, vals = [];
  S.daily.forEach(function (r) { map[r[0]] = r[1]; });
  for (var d = new Date(start); d <= last; d = new Date(d.getTime() + 864e5)) { var v = map[d.toISOString().slice(0, 10)] || 0; if (v > 0) vals.push(v); }
  vals.sort(function (a, b) { return a - b; });
  var q = function (p) { return vals.length ? vals[Math.min(vals.length - 1, Math.floor(p * vals.length))] : 0; }, t1 = q(.25), t2 = q(.5), t3 = q(.75);
  var h = '', lead = (start.getUTCDay() + 6) % 7, i;
  for (i = 0; i < lead; i++) h += '<i class="e"></i>';
  for (var d2 = new Date(start); d2 <= last; d2 = new Date(d2.getTime() + 864e5)) { var iso = d2.toISOString().slice(0, 10), n = map[iso] || 0, l = n === 0 ? 0 : n <= t1 ? 1 : n <= t2 ? 2 : n <= t3 ? 3 : 4; h += '<i class="l' + l + '" title="' + iso + ': ' + n + ' views"></i>'; }
  el.innerHTML = h;
  $('#heat-note').textContent = 'Each square is one day; columns are weeks (Monday at the top). Darker means more views. Showing ' + S.first_data_day.slice(0, 10) + ' onward, up to 26 weeks.';
}

function trendTable(rows, daily) {
  var take = rows.slice(-60);
  $('#t-trend').innerHTML = '<thead><tr><th>' + (daily ? 'Date' : 'Period') + '</th><th>Views</th><th>Clones</th></tr></thead><tbody>' + take.map(function (r) { return '<tr><td>' + esc(r[0]) + '</td><td>' + fmt(r[1]) + '</td><td>' + fmt(daily ? r[3] : r[2]) + '</td></tr>'; }).join('') + '</tbody>';
}

/* ---------- Sources ---------- */
function sources() {
  var s = S.sources;
  if (!s.length) { $('#c-sources').parentNode.innerHTML = '<p class="empty">No referrer data yet.</p>'; }
  else mk('#c-sources', { type: 'bar', data: { labels: s.map(function (x) { return x[0]; }), datasets: [{ label: 'Visits', data: s.map(function (x) { return x[1]; }), backgroundColor: css('--ac') }] }, options: { indexAxis: 'y', plugins: { legend: { display: false } } } });
  var g = S.sources_trend;
  mk('#c-google', { type: 'line', data: { labels: g.map(function (x) { return x[0].slice(5); }), datasets: [
    { label: 'All referrals', data: g.map(function (x) { return x[1]; }), borderColor: css('--ac'), pointRadius: g.length < 3 ? 4 : 0 },
    { label: 'Google', data: g.map(function (x) { return x[2]; }), borderColor: '#e5484d', pointRadius: g.length < 3 ? 4 : 0 }] }, options: { scales: { y: { beginAtZero: true } } } });
  var tot = S.totals.referrals_14d;
  $('#google-note').textContent = tot ? 'Google sent ' + fmt(S.totals.google_14d) + ' of ' + fmt(tot) + ' referred visits (' + Math.round(S.totals.google_14d * 100 / tot) + '%) in the latest window. Each point is a 14-day window.' : '';
  var paths = {};
  Object.keys(S.repo_sources || {}).forEach(function (n) { (S.repo_sources[n].paths || []).forEach(function (p) { var k = p[0]; paths[k] = paths[k] || { path: k, title: p[1], c: 0, u: 0 }; paths[k].c += p[2]; paths[k].u += p[3]; }); });
  var list = Object.keys(paths).map(function (k) { return paths[k]; }).sort(function (a, b) { return b.c - a.c; }).slice(0, 10);
  $('#t-paths').innerHTML = list.length ? '<thead><tr><th>Page</th><th>Views</th><th>Unique</th></tr></thead><tbody>' + list.map(function (p) { return '<tr><td>' + esc(p.title || p.path) + '</td><td>' + fmt(p.c) + '</td><td>' + fmt(p.u) + '</td></tr>'; }).join('') + '</tbody>' : '<tr><td class="empty">No page data yet.</td></tr>';
}

/* ---------- Repositories ---------- */
function filtered() {
  var q = $('#q').value.trim().toLowerCase(), t = $('#f-tier').value, l = $('#f-lang').value;
  var list = S.repos.filter(function (r) {
    if (prefs.hideForks && (r.fork || r.archived)) return false;
    if (t !== 'all' && r.tier !== t) return false;
    if (l && (r.lang || 'Unspecified') !== l) return false;
    if (!q) return true;
    return (r.name + ' ' + r.desc + ' ' + r.topics.join(' ')).toLowerCase().indexOf(q) > -1;
  });
  var k = state.sortK, d = state.sortD;
  list.sort(function (a, b) {
    var x = k === 'audit' ? a.audit.score : a[k], y = k === 'audit' ? b.audit.score : b[k];
    if (x == null) x = -1e9; if (y == null) y = -1e9;
    return (x > y ? 1 : x < y ? -1 : 0) * d;
  });
  return list;
}
var COLS = [['name', 'Repository'], ['v7', '7d'], ['v30', '30d'], ['vall', 'Since start'], ['c30', 'Clones 30d'], ['vu14', 'Uniq 14d'], ['stars', '★'], ['trend', 'Trend'], ['score', 'Score']];
function repoTable() {
  var list = filtered(), pages = Math.max(1, Math.ceil(list.length / prefs.rows));
  if (state.page > pages) state.page = pages;
  var rows = list.slice((state.page - 1) * prefs.rows, state.page * prefs.rows);
  $('#cnt').textContent = fmt(list.length) + ' repositories';
  var HS = { vall: 1, vu14: 1, trend: 1 }, hs = function (k) { return HS[k] ? ' class="hs"' : ''; };
  $('#t-repos').innerHTML = '<thead><tr><th></th>' + COLS.map(function (c) { return '<th data-k="' + c[0] + '"' + hs(c[0]) + '>' + c[1] + (state.sortK === c[0] ? (state.sortD > 0 ? ' ▲' : ' ▼') : '') + '</th>'; }).join('') + '<th class="hs">14d</th></tr></thead><tbody>' +
    (rows.length ? rows.map(function (r) {
      return '<tr class="clk" data-n="' + esc(r.name) + '"><td><input type="checkbox" class="sel" aria-label="Select ' + esc(r.name) + '"' + (state.sel.indexOf(r.name) > -1 ? ' checked' : '') + '></td><td><a href="#repo/' + encodeURIComponent(r.name) + '">' + esc(r.name) + '</a>' +
        (r.tier !== 'mid' && !r.fork && !r.archived ? '<span class="tag ' + r.tier + '">' + r.tier + '</span>' : '') + (r.lang ? '<span class="tag">' + esc(r.lang) + '</span>' : '') +
        '</td><td>' + r.v7 + '</td><td>' + r.v30 + '</td><td class="hs">' + fmt(r.vall) + '</td><td>' + r.c30 + '</td><td class="hs">' + r.vu14 + '</td><td>' + r.stars + '</td><td class="hs ' + (r.trend > 0 ? 'up' : r.trend < 0 ? 'down' : '') + '">' + (r.trend == null ? '–' : r.trend + '%') + '</td><td>' + r.score + '</td><td class="spark hs">' + spark(r.spark) + '</td></tr>';
    }).join('') : '<tr><td colspan="12" class="empty">No repositories match.</td></tr>') + '</tbody>';
  var p = '<button data-pg="' + (state.page - 1) + '"' + (state.page <= 1 ? ' disabled' : '') + '>Previous</button>';
  var from = Math.max(1, state.page - 2), to = Math.min(pages, from + 4);
  for (var i = from; i <= to; i++) p += '<button data-pg="' + i + '" class="' + (i === state.page ? 'on' : '') + '">' + i + '</button>';
  p += '<button data-pg="' + (state.page + 1) + '"' + (state.page >= pages ? ' disabled' : '') + '>Next</button><span class="mut">Page ' + state.page + ' of ' + pages + '</span>';
  $('#pager').innerHTML = p;
  var b = $('#b-compare'); b.textContent = 'Compare (' + state.sel.length + ')'; b.disabled = state.sel.length < 2;
  syncHash();
}
function csv() {
  var head = ['name', 'url', 'views_7d', 'views_30d', 'views_since_tracking', 'clones_30d', 'unique_visitors_14d', 'stars', 'forks', 'language', 'license', 'last_push', 'score'];
  var q = function (v) { v = String(v == null ? '' : v); if (/^[=+\-@]/.test(v)) v = "'" + v; return '"' + v.replace(/"/g, '""') + '"'; };
  var lines = [head.join(',')].concat(filtered().map(function (r) { return [r.name, r.url, r.v7, r.v30, r.vall, r.c30, r.vu14, r.stars, r.forks, r.lang, r.license, r.pushed, r.score].map(q).join(','); }));
  var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' })); a.download = 'github-repo-traffic.csv'; document.body.appendChild(a); a.click(); a.remove();
}

function readQuery(h) { var i = h.indexOf('?'), q = {}; if (i > -1) new URLSearchParams(h.slice(i + 1)).forEach(function (v, k) { q[k] = v; }); return q; }
function syncHash() {
  if (state.tab !== 'repos' || /^#repo\//.test(location.hash)) return;
  var p = new URLSearchParams(), q = $('#q').value.trim(), tier = $('#f-tier').value, l = $('#f-lang').value;
  if (q) p.set('q', q); if (tier !== 'all') p.set('tier', tier); if (l) p.set('lang', l);
  if (state.sortK !== 'score' || state.sortD !== -1) p.set('sort', state.sortK + (state.sortD > 0 ? '.asc' : ''));
  if (state.page > 1) p.set('page', state.page);
  var s = p.toString(); history.replaceState(null, '', '#repos' + (s ? '?' + s : ''));
}
function applyQuery(q) {
  $('#q').value = q.q || ''; $('#f-tier').value = ['all', 'top', 'mid', 'low'].indexOf(q.tier) > -1 ? q.tier : 'all';
  var langOk = $$('#f-lang option').some(function (o) { return o.value === q.lang; }); $('#f-lang').value = langOk ? q.lang : '';
  var s = (q.sort || 'score').split('.'); state.sortK = s[0]; state.sortD = s[1] === 'asc' ? 1 : -1;
  var sel = $$('#f-sort option').some(function (o) { return o.value === state.sortK; }); if (sel) $('#f-sort').value = state.sortK;
  state.page = Math.max(1, +q.page || 1);
}
function hashFor(t) { return '#' + t; }

/* ---------- Insights ---------- */
function insights() {
  $('#insights').innerHTML = S.insights.length ? S.insights.map(function (i) { return '<div class="ins"><small>' + esc(i.kind) + '</small><b>' + esc(i.title) + '</b><span>' + esc(i.text) + '</span></div>'; }).join('') : '<p class="empty">Insights appear once enough data has been collected.</p>';
  var L = S.languages;
  mk('#c-lang', { type: 'bar', data: { labels: L.map(function (x) { return x[0]; }), datasets: [{ label: 'Repositories', data: L.map(function (x) { return x[1]; }), backgroundColor: css('--ac') }, { label: 'Views (30d)', data: L.map(function (x) { return x[2]; }), backgroundColor: '#12a150' }] }, options: { scales: { y: { beginAtZero: true } } } });
  var T = S.topics.slice(0, 15);
  mk('#c-topics', { type: 'bar', data: { labels: T.map(function (x) { return x[0]; }), datasets: [{ label: 'Repositories', data: T.map(function (x) { return x[1]; }), backgroundColor: css('--ac') }] }, options: { indexAxis: 'y', plugins: { legend: { display: false } } } });
  var base = S.repos.filter(function (r) { return !r.fork && !r.archived; }), mv = base.map(function (r) { return { r: r, d: r.v7 - r.pv7 }; });
  var mt = function (list) { return list.length ? '<thead><tr><th>Repository</th><th>7d</th><th>Prev 7d</th><th>Change</th></tr></thead><tbody>' + list.map(function (x) { return '<tr><td>' + repoLink(x.r) + '</td><td>' + x.r.v7 + '</td><td>' + x.r.pv7 + '</td><td class="' + (x.d > 0 ? 'up' : 'down') + '">' + (x.d > 0 ? '+' : '') + x.d + '</td></tr>'; }).join('') + '</tbody>' : '<tr><td class="empty">No changes to show.</td></tr>'; };
  $('#t-up').innerHTML = mt(mv.filter(function (x) { return x.d > 0; }).sort(function (a, b) { return b.d - a.d; }).slice(0, 6));
  $('#t-down').innerHTML = mt(mv.filter(function (x) { return x.d < 0; }).sort(function (a, b) { return a.d - b.d; }).slice(0, 6));
  $('#audit-avg').textContent = S.totals.audit_avg;
  var a = S.repos.filter(function (r) { return !r.fork && !r.archived; }).sort(function (x, y) { return x.audit.score - y.audit.score; }).slice(0, 25);
  $('#t-audit').innerHTML = '<thead><tr><th>Repository</th><th>Score</th><th>To improve</th></tr></thead><tbody>' + a.map(function (r) { return '<tr><td>' + repoLink(r) + '</td><td>' + r.audit.score + '</td><td style="text-align:left;white-space:normal">' + esc(r.audit.missing.join('; ') || 'Nothing missing') + '</td></tr>'; }).join('') + '</tbody>';
}

/* ---------- Repo dialog ---------- */
function loadSeries() {
  if (SER) return Promise.resolve(SER);
  return fetch('data/series.json', { cache: 'no-cache' }).then(function (r) { return r.json(); }).then(function (j) { SER = j.repos || {}; return SER; });
}
function lastDays(n) {
  var out = [], d = new Date(S.last_data_day + 'T00:00:00Z');
  for (var i = n - 1; i >= 0; i--) { var x = new Date(d.getTime() - i * 864e5); out.push(x.toISOString().slice(0, 10)); }
  return out;
}
function openRepo(name) {
  var r = S.repos.filter(function (x) { return x.name === name; })[0], dlg = $('#repo-dialog');
  if (!r) { $('#rd').innerHTML = '<div class="rd-h"><h2 id="rd-title">Repository not found</h2><button class="rd-x" data-close aria-label="Close">×</button></div><p>This repository is not tracked (it may be private, new or renamed).</p>'; if (!dlg.open) dlg.showModal(); return; }
  var rs = (S.repo_sources || {})[name] || {}, hp = safeUrl(r.homepage);
  var refs = (rs.ref || []).map(function (x) { return '<tr><td>' + esc(x[0]) + '</td><td>' + x[1] + '</td><td>' + x[2] + '</td></tr>'; }).join('');
  var paths = (rs.paths || []).map(function (x) { return '<tr><td>' + esc(x[1] || x[0]) + '</td><td>' + x[2] + '</td><td>' + x[3] + '</td></tr>'; }).join('');
  $('#rd').innerHTML = '<div class="rd-h"><div><h2 id="rd-title">' + esc(r.name) + '</h2><p class="mut">' + esc(r.desc || 'No description set.') + '</p></div><button class="rd-x" data-close aria-label="Close">×</button></div>' +
    '<div class="chips">' + (r.lang ? '<span class="chip">' + esc(r.lang) + '</span>' : '') + (r.license ? '<span class="chip">' + esc(r.license) + '</span>' : '') + r.topics.map(function (t) { return '<a class="chip" href="#repos?q=' + encodeURIComponent(t) + '">' + esc(t) + '</a>'; }).join('') + '</div>' +
    '<div class="mini"><div><b>' + fmt(r.v7) + '</b><span>views, 7d</span></div><div><b>' + fmt(r.v30) + '</b><span>views, 30d</span></div><div><b>' + fmt(r.vall) + '</b><span>views since tracking began</span></div><div><b>' + fmt(r.c30) + '</b><span>clones, 30d</span></div><div><b>' + fmt(r.vu14) + '</b><span>unique, 14d</span></div><div><b>' + fmt(r.stars) + '</b><span>stars</span></div><div><b>' + fmt(r.forks) + '</b><span>forks</span></div><div><b>' + r.score + '</b><span>score (' + esc(r.tier) + ')</span></div></div>' +
    '<div class="chartbox"><canvas id="c-repo" role="img" aria-label="Daily views and clones for ' + esc(r.name) + '"></canvas></div><p class="note" id="rd-note">Loading history…</p>' +
    (refs ? '<h3>Traffic sources (14 days)</h3><div class="wrapx"><table><thead><tr><th>Referrer</th><th>Views</th><th>Unique</th></tr></thead><tbody>' + refs + '</tbody></table></div>' : '') +
    (paths ? '<h3>Popular pages (14 days)</h3><div class="wrapx"><table><thead><tr><th>Page</th><th>Views</th><th>Unique</th></tr></thead><tbody>' + paths + '</tbody></table></div>' : '') +
    '<h3>Metadata audit: ' + r.audit.score + '/100</h3>' + (r.audit.missing.length ? '<ul class="audit">' + r.audit.missing.map(function (m) { return '<li>' + esc(m) + '</li>'; }).join('') + '</ul>' : '<p class="mut">Nothing missing.</p>') +
    '<p class="note">Created ' + esc(r.created) + ' · last push ' + esc(r.pushed) + '</p>' +
    '<div class="bar"><a class="btn small" href="' + esc(r.url) + '" rel="noopener">Open on GitHub</a>' + (hp ? '<a class="btn small ghost" href="' + esc(hp) + '" rel="noopener">Homepage</a>' : '') + '<button class="btn small ghost" type="button" data-copy>Copy link</button>' + (navigator.share ? '<button class="btn small ghost" type="button" data-share>Share</button>' : '') + '</div>';
  if (!dlg.open) dlg.showModal();
  loadSeries().then(function (all) {
    var s = all[name] || { views: {}, clones: {} }, days = lastDays(90);
    mk('#c-repo', { type: 'line', data: { labels: days.map(function (d) { return d.slice(5); }), datasets: [
      { label: 'Views', data: days.map(function (d) { return (s.views[d] || [0])[0]; }), borderColor: css('--ac'), pointRadius: 0, tension: .2 },
      { label: 'Clones', data: days.map(function (d) { return (s.clones[d] || [0])[0]; }), borderColor: '#12a150', pointRadius: 0, tension: .2, yAxisID: 'y1' }] },
      options: { interaction: { mode: 'index', intersect: false }, scales: { y: { beginAtZero: true }, y1: { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false } }, x: { ticks: { maxTicksLimit: 8 } } } } });
    $('#rd-note').textContent = 'Daily views and clones, last 90 days. History for this repository starts when collection began (' + S.first_data_day + ').';
  }).catch(function () { var n = $('#rd-note'); if (n) n.textContent = 'History could not be loaded.'; });
}
function openCompare() {
  var names = state.sel.slice(0, 4), dlg = $('#repo-dialog');
  $('#rd').innerHTML = '<div class="rd-h"><h2 id="rd-title">Compare repositories</h2><button class="rd-x" data-close aria-label="Close">×</button></div><div class="chartbox tall"><canvas id="c-repo" role="img" aria-label="Views comparison"></canvas></div><p class="note" id="rd-note">Loading history…</p>' +
    '<div class="wrapx"><table><thead><tr><th>Repository</th><th>7d</th><th>30d</th><th>All</th><th>Clones 30d</th><th>★</th><th>Score</th></tr></thead><tbody>' + names.map(function (n) { var r = S.repos.filter(function (x) { return x.name === n; })[0]; return r ? '<tr><td>' + esc(r.name) + '</td><td>' + r.v7 + '</td><td>' + r.v30 + '</td><td>' + fmt(r.vall) + '</td><td>' + r.c30 + '</td><td>' + r.stars + '</td><td>' + r.score + '</td></tr>' : ''; }).join('') + '</tbody></table></div>';
  if (!dlg.open) dlg.showModal();
  loadSeries().then(function (all) {
    var days = lastDays(90);
    mk('#c-repo', { type: 'line', data: { labels: days.map(function (d) { return d.slice(5); }), datasets: names.map(function (n, i) { var s = all[n] || { views: {} }; return { label: n, data: days.map(function (d) { return (s.views[d] || [0])[0]; }), borderColor: PAL[i], pointRadius: 0, tension: .2 }; }) }, options: { interaction: { mode: 'index', intersect: false }, scales: { y: { beginAtZero: true }, x: { ticks: { maxTicksLimit: 8 } } } } });
    $('#rd-note').textContent = 'Daily views, last 90 days.';
  });
}
function closeDialog() { var d = $('#repo-dialog'); if (d.open) d.close(); }

/* ---------- Command palette ---------- */
var PAGES = [['Overview', '#overview'], ['Trends', '#trends'], ['Sources', '#sources'], ['Repositories (interactive)', '#repos'], ['Insights', '#insights'], ['About & links', '#about'], ['Comments', '#comments'],
  ['FAQ', 'faq/'], ['Guides', 'guides/'], ['Weekly reports', 'reports/'], ['All repositories (list)', 'repositories/'], ['Open data', 'data/'], ['Status', 'status/'], ['Methodology', 'methodology/'], ['Changelog', 'changelog/'], ['About', 'about/'], ['Privacy', 'privacy/']];
var palIdx = 0, palItems = [];
function palRender() {
  var q = $('#pal-q').value.trim().toLowerCase();
  var items = PAGES.filter(function (p) { return !q || p[0].toLowerCase().indexOf(q) > -1; }).map(function (p) { return { label: p[0], kind: p[1].charAt(0) === '#' ? 'tab' : 'page', href: p[1] }; });
  if (q && S) S.repos.filter(function (r) { return r.name.toLowerCase().indexOf(q) > -1 || r.topics.join(' ').toLowerCase().indexOf(q) > -1; }).slice(0, 8).forEach(function (r) { items.push({ label: r.name, kind: 'repo', href: '#repo/' + encodeURIComponent(r.name) }); });
  palItems = items.slice(0, 14); palIdx = Math.min(palIdx, Math.max(0, palItems.length - 1));
  $('#pal-list').innerHTML = palItems.length ? palItems.map(function (i, n) { return '<li data-i="' + n + '" class="' + (n === palIdx ? 'on' : '') + '"><span>' + esc(i.label) + '</span><small>' + i.kind + '</small></li>'; }).join('') : '<li class="mut">No matches</li>';
}
function palGo(n) { var i = palItems[n]; if (!i) return; $('#palette').close(); if (i.href.charAt(0) === '#') location.hash = i.href; else location.href = i.href; }
function openPalette() { var d = $('#palette'); if (!d.open) d.showModal(); $('#pal-q').value = ''; palIdx = 0; palRender(); $('#pal-q').focus(); }
function bindPalette() {
  $('#palette-btn').addEventListener('click', openPalette);
  $('#pal-q').addEventListener('input', function () { palIdx = 0; palRender(); });
  $('#pal-q').addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown') { e.preventDefault(); palIdx = Math.min(palItems.length - 1, palIdx + 1); palRender(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); palIdx = Math.max(0, palIdx - 1); palRender(); }
    else if (e.key === 'Enter') { e.preventDefault(); palGo(palIdx); }
  });
  $('#pal-list').addEventListener('click', function (e) { var li = e.target.closest('li[data-i]'); if (li) palGo(+li.getAttribute('data-i')); });
  $('#palette').addEventListener('click', function (e) { if (e.target === this) this.close(); });
}

/* ---------- Comments (lazy) ---------- */
var giscusLoaded = false;
function loadComments() {
  if (giscusLoaded) return; giscusLoaded = true;
  var box = $('#comments'), s = document.createElement('script');
  s.src = 'https://giscus.app/client.js';
  var a = { 'data-repo': box.getAttribute('data-repo'), 'data-repo-id': 'R_kgDOVt29OQ', 'data-category': 'General', 'data-category-id': 'DIC_kwDOVt29Oc4DLGFM', 'data-mapping': 'specific', 'data-term': 'dashboard-comments', 'data-strict': '0', 'data-reactions-enabled': '1', 'data-emit-metadata': '0', 'data-input-position': 'top', 'data-theme': 'preferred_color_scheme', 'data-lang': 'en', 'data-loading': 'lazy' };
  Object.keys(a).forEach(function (k) { s.setAttribute(k, a[k]); });
  s.crossOrigin = 'anonymous'; s.async = true; box.appendChild(s);
}

/* ---------- Routing ---------- */
function route() {
  var raw = (location.hash || '').slice(1), h = raw.split('?')[0], q = readQuery(raw);
  try { h = decodeURIComponent(h); } catch (e) {}
  if (!h) h = prefs.tab;
  var m = h.match(/^repo\/(.+)$/);
  if (m) {
    if (!$('.tab.active')) { state.tab = state.lastTab = 'repos'; $$('.tab').forEach(function (s) { s.classList.toggle('active', s.id === 'tab-repos'); }); if (S) renderTab('repos'); }
    if (S) openRepo(m[1]);
    return;
  }
  closeDialog();
  var t = TABS.indexOf(h) > -1 ? h : 'overview';
  state.tab = t; state.lastTab = t;
  if (t === 'repos' && S && raw.indexOf('?') > -1) applyQuery(q);
  $$('.tab').forEach(function (s) { s.classList.toggle('active', s.id === 'tab-' + t); });
  $$('#tabs a').forEach(function (a) { var on = a.getAttribute('data-tab') === t; a.classList.toggle('on', on); if (on) { a.setAttribute('aria-current', 'page'); if (a.scrollIntoView) a.scrollIntoView({ inline: 'center', block: 'nearest' }); } else a.removeAttribute('aria-current'); });
  var title = $('#tab-' + t) ? $('#tab-' + t).getAttribute('data-title') : '';
  document.title = (title && t !== 'overview' ? title + ' | ' : '') + 'GitHub Traffic Analytics Dashboard';
  if (S) renderTab(t);
  window.scrollTo(0, 0);
}
var rendered = {};
function renderTab(t) {
  var fn = { overview: overview, trends: trends, sources: sources, repos: repoTable, insights: insights, comments: loadComments }[t];
  if (fn && (t !== 'comments' || !rendered[t])) fn();
  rendered[t] = true;
}
function rerender() { Object.keys(charts).forEach(function (k) { try { charts[k].destroy(); } catch (e) {} }); rendered = {}; charts = {}; if (S) renderTab(state.tab); }

function syncSettings() { $('#p-theme').value = prefs.theme; $('#p-tab').value = prefs.tab; $('#p-rows').value = String(prefs.rows); $('#p-compact').checked = prefs.compact; $('#p-forks').checked = prefs.hideForks; $('#p-motion').checked = prefs.motion; }
function openSettings() { syncSettings(); var d = $('#settings-dialog'); if (!d.open) d.showModal(); }

/* ---------- Init ---------- */
function bind() {
  $('#theme').addEventListener('click', function () {
    var d = document.documentElement, c = d.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    prefs.theme = c === 'dark' ? 'light' : 'dark'; savePrefs(); applyPrefs(); syncSettings(); rerender();
  });
  $('#seg-period').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; state.period = b.getAttribute('data-p'); $$('#seg-period button').forEach(function (x) { x.classList.toggle('on', x === b); }); $('#seg-range').style.display = state.period === 'daily' ? '' : 'none'; trends(); });
  $('#seg-range').addEventListener('click', function (e) { var b = e.target.closest('button'); if (!b) return; state.range = +b.getAttribute('data-r'); $$('#seg-range button').forEach(function (x) { x.classList.toggle('on', x === b); }); trends(); });
  ['#q', '#f-tier', '#f-lang', '#f-sort'].forEach(function (id) {
    $(id).addEventListener(id === '#q' ? 'input' : 'change', function () { if (id === '#f-sort') { state.sortK = $('#f-sort').value; state.sortD = state.sortK === 'name' ? 1 : -1; } state.page = 1; repoTable(); });
  });
  $('#t-repos').addEventListener('click', function (e) {
    var th = e.target.closest('th[data-k]');
    if (th) { var k = th.getAttribute('data-k'); state.sortD = state.sortK === k ? -state.sortD : (k === 'name' ? 1 : -1); state.sortK = k; repoTable(); return; }
    var cb = e.target.closest('.sel');
    if (cb) { var n = cb.closest('tr').getAttribute('data-n'), i = state.sel.indexOf(n); if (cb.checked) { if (i < 0) { if (state.sel.length >= 4) { cb.checked = false; return; } state.sel.push(n); } } else if (i > -1) state.sel.splice(i, 1); var b = $('#b-compare'); b.textContent = 'Compare (' + state.sel.length + ')'; b.disabled = state.sel.length < 2; return; }
    var tr = e.target.closest('tr.clk'); if (tr && !e.target.closest('a')) location.hash = '#repo/' + encodeURIComponent(tr.getAttribute('data-n'));
  });
  $('#pager').addEventListener('click', function (e) { var b = e.target.closest('button[data-pg]'); if (!b || b.disabled) return; state.page = +b.getAttribute('data-pg'); repoTable(); var c = $('#t-repos'); if (c.scrollIntoView) c.scrollIntoView({ block: 'start' }); });
  $('#b-compare').addEventListener('click', openCompare);
  $('#b-csv').addEventListener('click', csv);
  $('#repo-dialog').addEventListener('click', function (e) {
    if (e.target === this || e.target.closest('[data-close]')) closeDialog();
    var cp = e.target.closest('[data-copy]'); if (cp) { try { navigator.clipboard.writeText(location.href); cp.textContent = 'Copied'; } catch (x) { cp.textContent = location.href; } }
    var sh = e.target.closest('[data-share]'); if (sh) navigator.share({ title: document.title, url: location.href }).catch(function () {});
  });
  $('#repo-dialog').addEventListener('close', function () { if (/^#repo\//.test(location.hash)) history.replaceState(null, '', state.tab === 'repos' ? '#repos' : hashFor(state.tab)); });
  window.addEventListener('hashchange', route);
  document.addEventListener('keydown', function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); return; }
    if (e.key === '?' && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) { e.preventDefault(); openSettings(); return; }
    if (e.key === '/' && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) { e.preventDefault(); location.hash = '#repos'; setTimeout(function () { $('#q').focus(); }, 30); }
  });
  $('#settings-btn').addEventListener('click', openSettings);
  bindPalette();
  $('#b-png').addEventListener('click', function () { var c = charts['#c-trend']; if (!c || !c.toBase64Image) return; var a = document.createElement('a'); a.href = c.toBase64Image('image/png', 1); a.download = 'github-traffic-' + state.period + '.png'; document.body.appendChild(a); a.click(); a.remove(); });
  $('#settings-dialog').addEventListener('click', function (e) { if (e.target === this || e.target.closest('[data-close]')) this.close(); });
  [['#p-theme', 'theme', 's'], ['#p-tab', 'tab', 's'], ['#p-rows', 'rows', 'n'], ['#p-compact', 'compact', 'b'], ['#p-forks', 'hideForks', 'b'], ['#p-motion', 'motion', 'b']].forEach(function (x) {
    $(x[0]).addEventListener('change', function () { prefs[x[1]] = x[2] === 'b' ? this.checked : x[2] === 'n' ? +this.value : this.value; savePrefs(); applyPrefs(); if (x[1] === 'theme') rerender(); if (x[1] === 'rows' || x[1] === 'hideForks') { state.page = 1; if (S && state.tab === 'repos') repoTable(); } });
  });
  $('#p-reset').addEventListener('click', function () { Object.keys(DEF).forEach(function (k) { prefs[k] = DEF[k]; }); savePrefs(); applyPrefs(); syncSettings(); rerender(); });
  var up = $('#totop'); window.addEventListener('scroll', function () { up.hidden = window.scrollY < 600; }, { passive: true });
  up.addEventListener('click', function () { window.scrollTo({ top: 0 }); });
}
function init(data) {
  S = data;
  var langs = {}; S.repos.forEach(function (r) { langs[r.lang || 'Unspecified'] = 1; });
  $('#f-lang').innerHTML += Object.keys(langs).sort().map(function (l) { return '<option>' + esc(l) + '</option>'; }).join('');
  $('#fresh-text').textContent = 'Data through ' + S.last_data_day + ' · updated ' + S.generated.slice(0, 10);
  var sf = $('#static-facts'); if (sf) sf.hidden = false;
  if (Date.now() - Date.parse(S.generated) > 72 * 3600e3) $('#stale').hidden = false;
  rendered = {}; route();
}
applyPrefs(); bind(); route();
if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('sw.js').catch(function () {});
$('#kpis').innerHTML = '<div class="card skel"></div><div class="card skel"></div><div class="card skel"></div><div class="card skel"></div>';
fetch('data/summary.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(init).catch(function () { $('#kpis').innerHTML = '<div class="card empty">Data could not be loaded. Please refresh in a moment.</div>'; });
})();
