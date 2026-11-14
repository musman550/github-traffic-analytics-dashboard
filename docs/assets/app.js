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
var PAGE = 25, PAL = ['#0b5fff', '#12a150', '#e5484d', '#f5a524', '#8e4ec6', '#0aa5a5'];

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
  mk('#c-trend', { type: daily ? 'line' : 'bar', data: { labels: lab, datasets: [
    { label: 'Views', data: v, borderColor: css('--ac'), backgroundColor: css('--ac'), pointRadius: 0, tension: .2 },
    { label: 'Clones', data: c, borderColor: '#12a150', backgroundColor: '#12a150', pointRadius: 0, tension: .2, yAxisID: 'y1' }] },
    options: { interaction: { mode: 'index', intersect: false }, scales: { y: { beginAtZero: true, title: { display: true, text: 'Views' } }, y1: { position: 'right', beginAtZero: true, grid: { drawOnChartArea: false }, title: { display: true, text: 'Clones' } }, x: { ticks: { maxTicksLimit: 12 } } } } });
  var names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  mk('#c-weekday', { type: 'bar', data: { labels: names, datasets: [{ label: 'Views', data: S.weekday, backgroundColor: css('--ac') }] }, options: { plugins: { legend: { display: false } } } });
  var h = S.history;
  mk('#c-stars', { type: 'line', data: { labels: h.map(function (r) { return r[0]; }), datasets: [
    { label: 'Stars', data: h.map(function (r) { return r[2]; }), borderColor: css('--ac'), pointRadius: h.length < 3 ? 4 : 0 },
    { label: 'Forks', data: h.map(function (r) { return r[3]; }), borderColor: '#12a150', pointRadius: h.length < 3 ? 4 : 0 }] }, options: { scales: { y: { beginAtZero: true } } } });
  $('#stars-note').textContent = h.length < 7 ? 'Star and fork history started on ' + h[0][0] + ' and grows with every daily update.' : '';
  mk('#c-created', { type: 'bar', data: { labels: S.created_daily.map(function (r) { return r[0].slice(5); }), datasets: [{ label: 'New repositories', data: S.created_daily.map(function (r) { return r[1]; }), backgroundColor: css('--ac') }] }, options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } }, x: { ticks: { maxTicksLimit: 10 } } } } });
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
var COLS = [['name', 'Repository'], ['v7', '7d'], ['v30', '30d'], ['vall', 'All'], ['c30', 'Clones 30d'], ['vu14', 'Uniq 14d'], ['stars', '★'], ['trend', 'Trend'], ['score', 'Score']];
function repoTable() {
  var list = filtered(), pages = Math.max(1, Math.ceil(list.length / PAGE));
  if (state.page > pages) state.page = pages;
  var rows = list.slice((state.page - 1) * PAGE, state.page * PAGE);
  $('#cnt').textContent = fmt(list.length) + ' repositories';
  $('#t-repos').innerHTML = '<thead><tr><th></th>' + COLS.map(function (c) { return '<th data-k="' + c[0] + '">' + c[1] + (state.sortK === c[0] ? (state.sortD > 0 ? ' ▲' : ' ▼') : '') + '</th>'; }).join('') + '<th>14d</th></tr></thead><tbody>' +
    (rows.length ? rows.map(function (r) {
      return '<tr class="clk" data-n="' + esc(r.name) + '"><td><input type="checkbox" class="sel" aria-label="Select ' + esc(r.name) + '"' + (state.sel.indexOf(r.name) > -1 ? ' checked' : '') + '></td><td><a href="#repo/' + encodeURIComponent(r.name) + '">' + esc(r.name) + '</a>' +
        (r.tier !== 'mid' && !r.fork && !r.archived ? '<span class="tag ' + r.tier + '">' + r.tier + '</span>' : '') + (r.lang ? '<span class="tag">' + esc(r.lang) + '</span>' : '') +
        '</td><td>' + r.v7 + '</td><td>' + r.v30 + '</td><td>' + fmt(r.vall) + '</td><td>' + r.c30 + '</td><td>' + r.vu14 + '</td><td>' + r.stars + '</td><td class="' + (r.trend > 0 ? 'up' : r.trend < 0 ? 'down' : '') + '">' + (r.trend == null ? '–' : r.trend + '%') + '</td><td>' + r.score + '</td><td class="spark">' + spark(r.spark) + '</td></tr>';
    }).join('') : '<tr><td colspan="12" class="empty">No repositories match.</td></tr>') + '</tbody>';
  var p = '<button data-pg="' + (state.page - 1) + '"' + (state.page <= 1 ? ' disabled' : '') + '>Previous</button>';
  var from = Math.max(1, state.page - 2), to = Math.min(pages, from + 4);
  for (var i = from; i <= to; i++) p += '<button data-pg="' + i + '" class="' + (i === state.page ? 'on' : '') + '">' + i + '</button>';
  p += '<button data-pg="' + (state.page + 1) + '"' + (state.page >= pages ? ' disabled' : '') + '>Next</button><span class="mut">Page ' + state.page + ' of ' + pages + '</span>';
  $('#pager').innerHTML = p;
  var b = $('#b-compare'); b.textContent = 'Compare (' + state.sel.length + ')'; b.disabled = state.sel.length < 2;
}
function csv() {
  var head = ['name', 'url', 'views_7d', 'views_30d', 'views_all', 'clones_30d', 'unique_visitors_14d', 'stars', 'forks', 'language', 'license', 'last_push', 'score'];
  var q = function (v) { v = String(v == null ? '' : v); if (/^[=+\-@]/.test(v)) v = "'" + v; return '"' + v.replace(/"/g, '""') + '"'; };
  var lines = [head.join(',')].concat(filtered().map(function (r) { return [r.name, r.url, r.v7, r.v30, r.vall, r.c30, r.vu14, r.stars, r.forks, r.lang, r.license, r.pushed, r.score].map(q).join(','); }));
  var a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([lines.join('\n')], { type: 'text/csv' })); a.download = 'github-repo-traffic.csv'; document.body.appendChild(a); a.click(); a.remove();
}

/* ---------- Insights ---------- */
function insights() {
  $('#insights').innerHTML = S.insights.length ? S.insights.map(function (i) { return '<div class="ins"><small>' + esc(i.kind) + '</small><b>' + esc(i.title) + '</b><span>' + esc(i.text) + '</span></div>'; }).join('') : '<p class="empty">Insights appear once enough data has been collected.</p>';
  var L = S.languages;
  mk('#c-lang', { type: 'bar', data: { labels: L.map(function (x) { return x[0]; }), datasets: [{ label: 'Repositories', data: L.map(function (x) { return x[1]; }), backgroundColor: css('--ac') }, { label: 'Views (30d)', data: L.map(function (x) { return x[2]; }), backgroundColor: '#12a150' }] }, options: { scales: { y: { beginAtZero: true } } } });
  var T = S.topics.slice(0, 15);
  mk('#c-topics', { type: 'bar', data: { labels: T.map(function (x) { return x[0]; }), datasets: [{ label: 'Repositories', data: T.map(function (x) { return x[1]; }), backgroundColor: css('--ac') }] }, options: { indexAxis: 'y', plugins: { legend: { display: false } } } });
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
    '<div class="chips">' + (r.lang ? '<span class="chip">' + esc(r.lang) + '</span>' : '') + (r.license ? '<span class="chip">' + esc(r.license) + '</span>' : '') + r.topics.map(function (t) { return '<span class="chip">' + esc(t) + '</span>'; }).join('') + '</div>' +
    '<div class="mini"><div><b>' + fmt(r.v7) + '</b><span>views, 7d</span></div><div><b>' + fmt(r.v30) + '</b><span>views, 30d</span></div><div><b>' + fmt(r.vall) + '</b><span>views, all time</span></div><div><b>' + fmt(r.c30) + '</b><span>clones, 30d</span></div><div><b>' + fmt(r.vu14) + '</b><span>unique, 14d</span></div><div><b>' + fmt(r.stars) + '</b><span>stars</span></div><div><b>' + fmt(r.forks) + '</b><span>forks</span></div><div><b>' + r.score + '</b><span>score (' + esc(r.tier) + ')</span></div></div>' +
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
  var h = decodeURIComponent((location.hash || '#overview').slice(1)), m = h.match(/^repo\/(.+)$/);
  if (m) {
    if (!$('.tab.active')) { state.tab = state.lastTab = 'repos'; $$('.tab').forEach(function (s) { s.classList.toggle('active', s.id === 'tab-repos'); }); if (S) renderTab('repos'); }
    if (S) openRepo(m[1]);
    return;
  }
  closeDialog();
  var t = TABS.indexOf(h.split('?')[0]) > -1 ? h.split('?')[0] : 'overview';
  state.tab = t; state.lastTab = t;
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
function rerender() { rendered = {}; charts = {}; if (S) renderTab(state.tab); }

/* ---------- Init ---------- */
function bind() {
  $('#theme').addEventListener('click', function () {
    var d = document.documentElement, c = d.getAttribute('data-theme') || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'), n = c === 'dark' ? 'light' : 'dark';
    d.setAttribute('data-theme', n); try { localStorage.setItem('theme', n); } catch (e) {} rerender();
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
  $('#repo-dialog').addEventListener('close', function () { if (/^#repo\//.test(location.hash)) history.replaceState(null, '', '#' + (state.lastTab === 'overview' ? 'repos' : state.lastTab)); });
  window.addEventListener('hashchange', route);
  document.addEventListener('keydown', function (e) {
    if (e.key === '/' && !/^(INPUT|SELECT|TEXTAREA)$/.test(document.activeElement.tagName)) { e.preventDefault(); location.hash = '#repos'; setTimeout(function () { $('#q').focus(); }, 30); }
  });
  var up = $('#totop'); window.addEventListener('scroll', function () { up.hidden = window.scrollY < 600; }, { passive: true });
  up.addEventListener('click', function () { window.scrollTo({ top: 0 }); });
}
function init(data) {
  S = data;
  var langs = {}; S.repos.forEach(function (r) { langs[r.lang || 'Unspecified'] = 1; });
  $('#f-lang').innerHTML += Object.keys(langs).sort().map(function (l) { return '<option>' + esc(l) + '</option>'; }).join('');
  $('#fresh-text').textContent = 'Data through ' + S.last_data_day + ' · updated ' + S.generated.slice(0, 10);
  var sf = $('#static-facts'); if (sf) sf.hidden = false;
  rendered = {}; route();
}
bind(); route();
$('#kpis').innerHTML = '<div class="card skel"></div><div class="card skel"></div><div class="card skel"></div><div class="card skel"></div>';
fetch('data/summary.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(init).catch(function () { $('#kpis').innerHTML = '<div class="card empty">Data could not be loaded. Please refresh in a moment.</div>'; });
})();
