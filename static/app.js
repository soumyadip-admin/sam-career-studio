const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const STATUSES = ['Interested', 'Applied', 'Assessment', 'Interview', 'HR Round', 'Selected'];
const state = { roles: [], portals: [], liveJobs: [], liveCount: 0, shortlist: [], jobs: [], projects: [], currentProject: null, currentTab: 'excel_guide', questions: [], qIndex: 0, visibleJobs: 20, jarvisLastJobs: [], previousVisit: localStorage.getItem('samLastJobVisit') || null };
let deferredInstallPrompt = null;
let jarvisRecognition = null;
let accessGatePromise = null;
let lastWakeNotice = 0;

const ROADMAP_PHASES = [
  {title:'Analytics foundation', duration:'Weeks 1–2', tasks:[
    ['foundation-analytics','Understand descriptive, diagnostic, predictive and prescriptive analytics','Write one business example for each from your operations experience','https://roadmap.sh/data-analyst'],
    ['foundation-excel','Master Excel cleaning, lookups, pivots and Power Query','Complete one messy-data cleanup and reconciliation workbook','https://support.microsoft.com/excel'],
    ['foundation-stats','Learn statistics for analysts','Practice distributions, sampling, confidence intervals, correlation and regression','https://www.khanacademy.org/math/statistics-probability'],
    ['foundation-kpi','Define trustworthy KPI logic','Document grain, numerator, denominator, filters and limitations for five KPIs','']
  ]},
  {title:'SQL for analysis', duration:'Weeks 3–5', tasks:[
    ['sql-core','Query relational data confidently','SELECT, WHERE, GROUP BY, CASE, JOIN and date logic','https://sqlbolt.com/'],
    ['sql-advanced','Use CTEs and window functions','Practice ROW_NUMBER, RANK, LAG, LEAD and running totals','https://www.postgresql.org/docs/current/tutorial-window.html'],
    ['sql-quality','Build data-quality checks','Test nulls, duplicates, orphan keys, reconciliation totals and valid ranges',''],
    ['sql-project','Publish one SQL case study','Include schema, questions, queries, findings and limitations','']
  ]},
  {title:'Power BI & storytelling', duration:'Weeks 6–8', tasks:[
    ['bi-query','Transform data with Power Query','Use typed steps, merges, append, parameters and refresh-safe logic','https://learn.microsoft.com/training/powerplatform/power-bi'],
    ['bi-model','Build a star schema','Set fact grain, dimensions, relationships and a proper Date table','https://learn.microsoft.com/power-bi/guidance/star-schema'],
    ['bi-dax','Write reusable DAX measures','Practice CALCULATE, iterators, time intelligence and filter context','https://learn.microsoft.com/dax/'],
    ['bi-dashboard','Deliver a decision-first dashboard','Show KPI definitions, exceptions, trends, drill-through and refresh time','']
  ]},
  {title:'Python & automation', duration:'Weeks 9–10', tasks:[
    ['python-core','Use Python and Pandas','Load, clean, join, aggregate and validate tabular data','https://pandas.pydata.org/docs/getting_started/intro_tutorials/'],
    ['python-viz','Create clear analytical visuals','Use Matplotlib or Seaborn with accurate titles, units and annotations','https://seaborn.pydata.org/tutorial.html'],
    ['python-etl','Automate a repeatable ETL task','Add logging, quality assertions, idempotent output and a run summary',''],
    ['python-api','Read one public API safely','Handle pagination, timeouts, retries, schemas and provenance','']
  ]},
  {title:'Portfolio evidence', duration:'Weeks 11–13', tasks:[
    ['portfolio-ops','Complete an operations analytics project','Use transferable SLA/WFM context without targeting call-centre process work',''],
    ['portfolio-domain','Complete a non-BPO domain project','Choose finance, e-commerce, supply chain, product or revenue analytics',''],
    ['portfolio-readme','Write strong project documentation','State problem, data, method, quality checks, findings, limitations and next action','https://docs.github.com/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes'],
    ['portfolio-resume','Convert evidence into truthful resume bullets','Use action + method + business decision + verified outcome; never invent metrics','']
  ]},
  {title:'Interview & job system', duration:'Ongoing', tasks:[
    ['career-sql','Practice SQL interview questions weekly','Explain assumptions, edge cases, performance and validation—not only syntax',''],
    ['career-case','Practice analytics case studies','Clarify objective, grain, KPIs, segments, trade-offs and recommendations',''],
    ['career-star','Prepare six STAR stories','Cover ambiguity, stakeholder conflict, quality defect, automation, insight and learning',''],
    ['career-ats','Tailor every application','Use the ATS matcher against the real JD and retain only truthful evidence',''],
    ['career-apply','Run a weekly application routine','Review live roles, verify the source, apply selectively and update the CRM stage','']
  ]}
];

function esc(value = '') {
  return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
}
function safeUrl(value = '') {
  try { const u = new URL(value, location.origin); return ['http:', 'https:'].includes(u.protocol) ? u.href : '#'; }
  catch { return '#'; }
}
function requestAccessKey() {
  if (accessGatePromise) return accessGatePromise;
  const dialog = $('#accessKeyModal');
  if (!dialog) {
    const supplied = window.prompt('Enter your Sam Career Studio app access key. Do not use a Gmail or GitHub password.');
    if (!supplied) return Promise.reject(new Error('App access key required'));
    localStorage.setItem('samAppAccessKey', supplied.trim());
    return Promise.resolve(supplied.trim());
  }
  accessGatePromise = new Promise((resolve, reject) => {
    const form = $('#accessKeyForm'), input = $('#accessKeyInput'), error = $('#accessKeyError');
    const cancel = $('#accessKeyCancel'), submit = $('#accessKeySubmit');
    const cleanup = () => {
      form.removeEventListener('submit', onSubmit); cancel.removeEventListener('click', onCancel); dialog.removeEventListener('cancel', onCancel);
    };
    const onCancel = event => {
      event.preventDefault(); cleanup(); if (dialog.open) dialog.close(); reject(new Error('App access key required'));
    };
    const onSubmit = async event => {
      event.preventDefault(); const candidate = input.value.trim();
      if (!candidate) { error.textContent = 'Enter the private app access key saved in Render.'; return; }
      submit.disabled = true; submit.textContent = 'Checking…'; error.textContent = '';
      try {
        const check = await fetchWithWakeRetry('/api/auth/verify', {headers:{'X-App-Key':candidate,'Cache-Control':'no-store'}, cache:'no-store'}, 4);
        if (!check.ok) { error.textContent = 'That key was not accepted. Check capitalization and use the latest Render value.'; input.select(); return; }
        localStorage.setItem('samAppAccessKey', candidate); cleanup(); dialog.close(); resolve(candidate); toast('Private app access confirmed.');
      } catch {
        error.textContent = 'The server could not verify the key. Check your internet connection and try again.';
      } finally { submit.disabled = false; submit.textContent = 'Unlock app'; }
    };
    form.addEventListener('submit', onSubmit); cancel.addEventListener('click', onCancel); dialog.addEventListener('cancel', onCancel);
    input.value = ''; error.textContent = ''; dialog.showModal(); setTimeout(() => input.focus(), 80);
  }).finally(() => { accessGatePromise = null; });
  return accessGatePromise;
}

const WAKE_RETRY_DELAYS = [2000, 4000, 7000, 10000, 15000, 20000];
const TRANSIENT_SERVER_STATUS = new Set([502, 503, 504]);
const wait = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));
function announceServerWake() {
  if (Date.now() - lastWakeNotice < 15000) return;
  lastWakeNotice = Date.now(); toast('Free server is waking up. Retrying automatically…', 'error');
}
async function fetchWithWakeRetry(url, options = {}, maxRetries = WAKE_RETRY_DELAYS.length) {
  let lastError = null;
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await fetch(url, options);
      if (!TRANSIENT_SERVER_STATUS.has(response.status) || attempt === maxRetries) return response;
      lastError = new Error(`Temporary server response ${response.status}`);
    } catch (error) {
      lastError = error;
      if (!navigator.onLine || attempt === maxRetries) throw error;
    }
    announceServerWake(); await wait(WAKE_RETRY_DELAYS[Math.min(attempt, WAKE_RETRY_DELAYS.length - 1)]);
  }
  throw lastError || new Error('Server unavailable');
}

async function api(url, options = {}, retried = false) {
  const accessKey = localStorage.getItem('samAppAccessKey') || '';
  const headers = {'Content-Type':'application/json', ...(accessKey ? {'X-App-Key': accessKey} : {}), ...(options.headers || {})};
  const response = await fetchWithWakeRetry(url, {...options, headers});
  if (response.status === 401 && !retried) {
    const latestKey = localStorage.getItem('samAppAccessKey') || '';
    if (latestKey && latestKey !== accessKey) return api(url, options, true);
    if (accessKey) localStorage.removeItem('samAppAccessKey');
    await requestAccessKey();
    return api(url, options, true);
  }
  if (!response.ok) {
    let detail = TRANSIENT_SERVER_STATUS.has(response.status)
      ? 'The free server is still waking up. Wait one minute and try again.'
      : `Request failed (${response.status})`;
    try { const body = await response.json(); detail = body.detail || detail; } catch {}
    if (response.status === 401) localStorage.removeItem('samAppAccessKey');
    throw new Error(detail);
  }
  return response.json();
}
function toast(message, type = 'success') {
  const el = document.createElement('div'); el.className = `toast ${type}`; el.textContent = message;
  $('#toastStack').append(el); setTimeout(() => el.remove(), 3800);
}
function formatDate(value) {
  if (!value) return 'Date not supplied';
  let date;
  if (/^\d{10}$/.test(String(value))) date = new Date(Number(value) * 1000);
  else date = new Date(value);
  if (Number.isNaN(date.valueOf())) return 'Date not supplied';
  return new Intl.DateTimeFormat('en-IN', { day:'2-digit', month:'short', year:'numeric' }).format(date);
}
function relativeTime(value) {
  if (!value) return 'freshness unavailable';
  const date = /^\d{10}$/.test(String(value)) ? new Date(Number(value) * 1000) : new Date(value);
  if (Number.isNaN(date.valueOf())) return 'freshness unavailable';
  const hours = Math.max(0, (Date.now() - date.valueOf()) / 36e5);
  if (hours < 1) return 'seen this hour';
  if (hours < 24) return `seen ${Math.floor(hours)}h ago`;
  return `seen ${Math.floor(hours / 24)}d ago`;
}
function initials(name = '?') { return name.split(/\s+/).filter(Boolean).slice(0,2).map(x => x[0]).join('').toUpperCase() || '?'; }
function jobObservedLabel(job) {
  if (job.source === 'Google Sheet Tracker') return `tracked ${relativeTime(job.source_observed_at).replace(/^seen /, '')}`;
  return relativeTime(job.last_seen_at);
}
function jobFreshnessLabel(job) {
  if (job.source === 'Google Sheet Tracker') return 'application event · posting date not supplied';
  return job.freshness_verified ? `posted ${relativeTime(job.posted_at).replace('seen ','')}` : 'active source result · age not supplied';
}

function updateConnectionState() {
  const online = navigator.onLine;
  const badge = $('#connectionState');
  if (!badge) return;
  badge.classList.toggle('offline', !online);
  $('span', badge).textContent = online ? 'Online' : 'Offline cache';
  $('#systemStatus').textContent = online ? ($('#systemStatus').textContent === 'OFFLINE' ? 'CONNECTING' : $('#systemStatus').textContent) : 'OFFLINE';
}
async function registerPWA() {
  updateConnectionState();
  window.addEventListener('online', () => { updateConnectionState(); toast('Back online. Refreshing current data.'); Promise.all([loadMetrics(), loadLiveJobs()]).catch(()=>{}); });
  window.addEventListener('offline', () => { updateConnectionState(); toast('Offline: showing the most recently cached data.', 'error'); });
  window.addEventListener('beforeinstallprompt', event => {
    event.preventDefault(); deferredInstallPrompt = event; $('#installApp').hidden = false;
  });
  window.addEventListener('appinstalled', () => { deferredInstallPrompt = null; $('#installApp').hidden = true; toast('Sam Career Studio installed.'); });
  if (window.matchMedia('(display-mode: standalone)').matches) $('#installApp').hidden = true;
  if ('serviceWorker' in navigator) {
    try { await navigator.serviceWorker.register('/sw.js', {scope:'/'}); }
    catch (error) { console.warn('Service worker registration failed', error); }
  }
}
async function installPWA() {
  if (deferredInstallPrompt) {
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null; $('#installApp').hidden = true;
  } else {
    toast('In Chrome, open the menu and choose “Install app” or “Add to Home screen”.');
  }
}

async function loadMetrics() {
  try {
    const m = await api('/api/metrics');
    const active = Number(m.live_jobs?.active || 0), avg = Number(m.live_jobs?.avg_match || 0);
    const tracked = Object.values(m.pipeline || {}).reduce((a,b) => a + Number(b), 0);
    $('#heroLive').textContent = active; $('#heroMatch').textContent = avg ? `${avg}%` : '—'; $('#heroPipeline').textContent = tracked;
    $('#metricJobs').textContent = active; $('#metricPipeline').textContent = tracked; $('#metricProjects').textContent = m.projects?.total || 16;
    $('#metricSkills').textContent = m.skill_average ? `${m.skill_average}%` : '—'; $('#readinessValue').textContent = m.skill_average ? `${m.skill_average}%` : '—';
    const last = m.live_jobs?.last_refresh;
    const undated = Number(m.live_jobs?.age_unknown || 0), sheetTracked = Number(m.live_jobs?.sheet_tracked || 0);
    $('#metricJobsSub').textContent = last ? `${Number(m.live_jobs?.active_72h || 0)} in 72h · ${sheetTracked} Sheet-tracked age-unknown · ${undated} total age-unknown` : (m.scanner_running ? 'First source scan running…' : 'Waiting for first scan');
    $('#lastSync').textContent = last ? `Fetched ${formatDate(last)} · ${relativeTime(last)}` : (m.scanner_running ? 'Source refresh running…' : 'Not synced yet');
    $('#systemStatus').textContent = m.scanner_running ? 'SCANNING' : 'ONLINE';
    $$('.sync-button, #syncRadar').forEach(el => el.classList.toggle('running', m.scanner_running));
    return m;
  } catch (e) { $('#systemStatus').textContent = 'DEGRADED'; return null; }
}

async function loadRoles() {
  state.roles = await api('/api/roles');
  const options = state.roles.map(r => `<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('');
  $('#portalRole').innerHTML = options;
  $('#roleFilter').insertAdjacentHTML('beforeend', options);
}
async function loadPortals() {
  const role = $('#portalRole').value || 'Data Analyst', locationValue = $('#portalLocation').value || 'Bangalore';
  state.portals = await api(`/api/portals?role=${encodeURIComponent(role)}&location=${encodeURIComponent(locationValue)}`);
  $('#portalGrid').innerHTML = state.portals.map((p, i) => `
    <a class="portal-card" href="${safeUrl(p.search_url)}" target="_blank" rel="noopener" title="Open ${esc(p.name)} search">
      <div class="portal-card-head"><b>${String(i+1).padStart(2,'0')} · ${esc(p.name)}</b><span class="coverage-badge ${p.live_ingestion ? 'live' : ''}">${esc(p.coverage_label)}</span></div>
      <small>${esc(p.coverage_note)} ↗</small>
    </a>`).join('');
}

async function loadLiveJobs() {
  const role = $('#roleFilter').value, source = $('#sourceFilter').value, min = $('#scoreFilter').value, sort = $('#jobSort').value;
  const freshness = $('#freshnessFilter').value, locationGroup = $('#locationFilter').value;
  const url = `/api/scraper/live?role=${encodeURIComponent(role)}&source=${encodeURIComponent(source)}&location_group=${encodeURIComponent(locationGroup)}&min_score=${min}&freshness=${freshness}&sort=${sort}&limit=500`;
  try {
    const result = await api(url); state.liveJobs = result.items; state.liveCount = Number(result.count || result.items.length); state.liveFallback = result.fallback_reason || ''; state.visibleJobs = 20;
    const sources = (result.source_counts || []).map(x => `${x.source} ${x.count}`).join(' · ');
    $('#sourceSummary').title = state.liveFallback;
    $('#sourceSummary').innerHTML = `<i class="signal-dot ${result.fallback ? 'amber' : ''}"></i>${esc(result.freshness)}${result.fallback ? ' · clearly labeled fallback' : ''}${sources ? ` · ${esc(sources)}` : ''}`;
    renderLocationSegments(result.location_counts || [], locationGroup);
    renderLiveJobs();
  } catch (e) {
    $('#jobGrid').innerHTML = `<div class="job-card"><h3>Live feed unavailable</h3><p class="company-name">${esc(e.message)}</p><button class="btn btn-secondary" onclick="loadLiveJobs()">Retry</button></div>`;
  }
}
function renderLocationSegments(counts, selected) {
  const countMap = Object.fromEntries(counts.map(x => [x.location_group, Number(x.count)]));
  const groups = [['kolkata','Kolkata'],['bengaluru','Bengaluru'],['hyderabad','Hyderabad'],['remote','Remote'],['other-india','Other India']];
  $('#locationSegments').innerHTML = groups.map(([value,label]) => `<button class="location-segment ${selected === value ? 'active' : ''}" data-location="${value}"><span>${label}</span><b>${countMap[label] || 0}</b></button>`).join('');
  $$('.location-segment').forEach(button => button.addEventListener('click', () => { $('#locationFilter').value = button.dataset.location; loadLiveJobs(); }));
}
function filteredJobs() {
  const q = $('#jobSearch').value.trim().toLowerCase();
  return !q ? state.liveJobs : state.liveJobs.filter(j => `${j.title} ${j.company} ${j.location}`.toLowerCase().includes(q));
}
function renderLiveJobs() {
  const filtered = filteredJobs(), shown = filtered.slice(0, state.visibleJobs);
  const isNew = j => !state.previousVisit || new Date(j.first_seen_at) > new Date(state.previousVisit);
  const newCount = filtered.filter(isNew).length;
  const searching = Boolean($('#jobSearch').value.trim());
  const total = searching ? filtered.length : state.liveCount;
  $('#jobCount').textContent = `${total} qualifying job${total === 1 ? '' : 's'} · showing ${shown.length} · ${newCount} new in loaded results · no salary cap`;
  $('#showMoreJobs').hidden = shown.length >= filtered.length;
  if (!shown.length) {
    $('#jobGrid').innerHTML = `<div class="job-card"><div class="company-mark">∅</div><h3>No qualifying jobs match these filters</h3><p class="company-name">Try all roles, lower the profile-match threshold, include current age-unknown listings, or use a target portal launcher. Call-centre roles remain excluded.</p></div>`;
    return;
  }
  $('#jobGrid').innerHTML = shown.map(j => `
    <article class="job-card">
      <div class="job-top"><div class="company-mark">${esc(initials(j.company || j.source))}</div><div>${isNew(j) ? '<span class="new-chip">NEW</span>' : ''}<span class="match-score" title="Profile relevance heuristic">${Number(j.match_score || 0)}% · ${esc(j.fit_tier || 'Explore')}</span></div></div>
      <h3>${esc(j.title)}</h3><div class="company-name">${esc(j.company || 'Company not supplied')}</div>
      <div class="job-meta"><span>${esc(j.location || 'Location not supplied')}</span><span class="source-chip">${esc(j.source)}</span>${j.employment_type ? `<span>${esc(j.employment_type)}</span>` : ''}${j.salary_text ? `<span class="salary-chip">${esc(j.salary_text)}</span>` : ''}</div>
      <div class="job-freshness"><span>${esc(jobObservedLabel(j))}</span><span>${esc(jobFreshnessLabel(j))}</span></div>
      <div class="job-actions"><button class="btn btn-secondary add-live" data-id="${j.id}">+ Pipeline</button><a class="btn btn-primary" href="${safeUrl(j.url)}" target="_blank" rel="noopener">Apply on portal ↗</a></div>
    </article>`).join('');
  $$('.add-live').forEach(button => button.addEventListener('click', () => openLiveJob(Number(button.dataset.id))));
}
function openLiveJob(id) {
  const j = [...state.liveJobs, ...state.shortlist].find(x => x.id === id); if (!j) return;
  $('#jobModalTitle').textContent = 'Add verified source lead'; $('#jobLiveId').value = j.id;
  $('#jobTitle').value = j.title || ''; $('#jobCompany').value = j.company || ''; $('#jobLocation').value = j.location || '';
  $('#jobPortal').value = j.source || ''; $('#jobUrl').value = j.url || ''; $('#jobNotes').value = `Imported from ${j.provenance || j.source}. Verify details before applying.`;
  $('#jobModal').showModal();
}

async function loadShortlist() {
  const locationGroup = $('#shortlistLocation').value || 'preferred';
  try {
    const result = await api(`/api/recommendations?location_group=${encodeURIComponent(locationGroup)}&limit=20`);
    state.shortlist = result.items || [];
    $('#shortlistNote').textContent = `${result.count} current roles · ${result.dated_count} source-dated · tracker events clearly labeled · refreshed from the live database`;
    renderShortlist();
  } catch (error) {
    $('#shortlistGrid').innerHTML = `<div class="empty-pipeline">Shortlist unavailable: ${esc(error.message)}</div>`;
  }
}
function renderShortlist() {
  if (!state.shortlist.length) {
    $('#shortlistGrid').innerHTML = '<div class="empty-pipeline">No transition roles match this location right now. Try All preferred locations or refresh the sources.</div>';
    return;
  }
  $('#shortlistGrid').innerHTML = state.shortlist.map(j => `
    <article class="shortlist-card">
      <div class="shortlist-meta"><span>${esc(j.location_group || 'Other India')}</span><span>${esc(j.source)}</span><span>${Number(j.match_score || 0)}% fit</span></div>
      <h4>${esc(j.title)}</h4><p>${esc(j.company || 'Company not supplied')} · ${esc(j.location || 'Location not supplied')}</p>
      <p class="transition-reason">${esc(j.transition_reason || 'Verify the description before applying.')}</p>
      <div class="job-freshness"><span>${esc(jobObservedLabel(j))}</span><span>${esc(jobFreshnessLabel(j))}</span></div>
      <div class="shortlist-actions"><button class="btn btn-secondary track-shortlist" data-id="${j.id}">+ Track job</button><a class="btn btn-primary" href="${safeUrl(j.url)}" target="_blank" rel="noopener">Apply ↗</a></div>
    </article>`).join('');
  $$('.track-shortlist').forEach(button => button.addEventListener('click', () => openLiveJob(Number(button.dataset.id))));
}

function isObsoleteDemoJob(job) {
  const key = `${job.company || ''}|${job.title || ''}`;
  const oldSeeds = new Set([
    'Amazon|Operations Intelligence & WFM Analyst', 'Concentrix|MIS & Reporting Team Lead',
    'Startek|WFM Reporting Lead & Data Specialist', 'Alorica|Senior Business Analytics Specialist',
    'Teleperformance|Lead BI Developer & Operations Analyst', 'Genpact|Power BI & DAX Specialist (Analytics Core)'
  ]);
  return job.listing_type === 'search_lead' || oldSeeds.has(key);
}
function readPipelineCache() {
  try {
    const value = JSON.parse(localStorage.getItem('samPipelineCache') || '[]');
    // Earlier builds cached permanent demo/search cards. They are not applications and
    // must not survive a build upgrade. Manual and live-imported user records remain.
    return Array.isArray(value) ? value.filter(job => !isObsoleteDemoJob(job)) : [];
  } catch { return []; }
}
function readPipelineTombstones() {
  try { const value = JSON.parse(localStorage.getItem('samPipelineDeletedUrls') || '[]'); return new Set(Array.isArray(value) ? value : []); }
  catch { return new Set(); }
}
function savePipelineCache() {
  localStorage.setItem('samPipelineCache', JSON.stringify(state.jobs));
}
async function loadPipeline() {
  const cached = readPipelineCache(), deleted = readPipelineTombstones();
  try {
    const remote = (await api('/api/jobs')).filter(job => !deleted.has(job.url) && !isObsoleteDemoJob(job));
    const merged = new Map(remote.map(job => [job.url, job]));
    cached.filter(job => !deleted.has(job.url)).forEach(job => {
      const serverJob = merged.get(job.url);
      if (!serverJob || new Date(job.updated_at || 0) > new Date(serverJob.updated_at || 0)) merged.set(job.url, job);
    });
    state.jobs = [...merged.values()]; savePipelineCache();
  } catch (error) {
    state.jobs = cached.filter(job => !deleted.has(job.url));
    if (state.jobs.length) toast('Pipeline loaded from this device; server sync is unavailable.', 'error');
  }
  renderPipeline();
}
function renderPipeline() {
  $('#kanban').innerHTML = STATUSES.map(status => {
    const jobs = state.jobs.filter(j => j.status === status);
    return `<section class="kanban-column" data-status="${status}"><div class="column-head"><b>${esc(status.toUpperCase())}</b><span>${jobs.length}</span></div><div class="column-body">${jobs.map(pipelineCard).join('')}</div></section>`;
  }).join('');
  $$('.pipeline-card').forEach(card => {
    card.addEventListener('dragstart', e => e.dataTransfer.setData('text/plain', card.dataset.id));
  });
  $$('.kanban-column').forEach(col => {
    col.addEventListener('dragover', e => { e.preventDefault(); col.classList.add('drag-over'); });
    col.addEventListener('dragleave', () => col.classList.remove('drag-over'));
    col.addEventListener('drop', async e => {
      e.preventDefault(); col.classList.remove('drag-over'); const id = Number(e.dataTransfer.getData('text/plain'));
      const job = state.jobs.find(item => Number(item.id) === id); if (!job) return;
      job.status = col.dataset.status; job.updated_at = new Date().toISOString(); job._device_cached = true;
      savePipelineCache(); renderPipeline();
      if (id < 0) return toast(`Moved to ${job.status} on this device.`);
      try { await api(`/api/jobs/${id}`, {method:'PATCH', body:JSON.stringify({status:job.status})}); toast(`Moved to ${job.status} · synced`); await loadPipeline(); await loadMetrics(); }
      catch (err) { toast(`Saved on this device; server sync failed: ${err.message}`, 'error'); }
    });
  });
  $$('.remove-lead').forEach(btn => btn.addEventListener('click', async () => {
    if (!confirm('Remove this lead from the pipeline?')) return;
    const id = Number(btn.dataset.id), job = state.jobs.find(item => Number(item.id) === id); if (!job) return;
    const deleted = readPipelineTombstones(); deleted.add(job.url); localStorage.setItem('samPipelineDeletedUrls', JSON.stringify([...deleted]));
    state.jobs = state.jobs.filter(item => Number(item.id) !== id); savePipelineCache(); renderPipeline();
    if (id < 0) return toast('Device-only lead removed.');
    try { await api(`/api/jobs/${id}`, {method:'DELETE'}); toast('Lead removed · synced'); await loadMetrics(); }
    catch (e) { toast(`Removed on this device; server sync failed: ${e.message}`, 'error'); }
  }));
  const tracked = state.jobs.length; $('#heroPipeline').textContent = tracked; $('#metricPipeline').textContent = tracked;
}
function pipelineCard(j) {
  return `<article class="pipeline-card ${j.verified ? 'verified' : ''}" draggable="true" data-id="${j.id}">
    <span class="card-label">${j._device_cached ? 'DEVICE-SAVED' : j.verified ? 'SOURCE IMPORT' : j.listing_type === 'search_lead' ? 'SEARCH LEAD' : 'MANUAL LEAD'}</span>
    <h4>${esc(j.title)}</h4><p>${esc(j.company)} · ${esc(j.location || 'Location open')}</p>
    <div class="pipeline-actions"><a href="${safeUrl(j.url)}" target="_blank" rel="noopener">🚀 Apply on portal</a><button class="remove-lead" data-id="${j.id}" title="Remove lead" aria-label="Remove ${esc(j.title)}">×</button></div>
  </article>`;
}

async function loadProjects() {
  state.projects = await api('/api/projects');
  $('#projectGrid').innerHTML = state.projects.map((p, i) => `
    <article class="project-card" tabindex="0" role="button" data-id="${p.id}" aria-label="Open ${esc(p.title)}">
      <span class="project-number">LAB / ${String(i+1).padStart(2,'0')}</span><h3>${esc(p.title)}</h3><p>${esc(p.objective)}</p>
      <div class="project-card-footer"><div><span class="category-chip">${esc(p.category)}</span><span class="source-state ${p.source_status}"> · ${sourceStatusText(p.source_status)}</span></div><span class="open-project">↗</span></div>
    </article>`).join('');
  $$('.project-card').forEach(card => {
    const open = () => openProject(Number(card.dataset.id)); card.addEventListener('click', open); card.addEventListener('keydown', e => { if (e.key === 'Enter') open(); });
  });
}
function sourceStatusText(status) {
  return ({reachable:'source reachable', access_restricted:'access restricted', unreachable:'source unavailable', not_checked:'not checked'})[status] || status.replace('http_','HTTP ');
}
function openProject(id) {
  const p = state.projects.find(x => x.id === id); if (!p) return; state.currentProject = p; state.currentTab = 'excel_guide';
  $('#projectCategory').textContent = p.category; $('#projectTitle').textContent = p.title; $('#projectObjective').textContent = p.objective;
  $('#datasetLink').href = safeUrl(p.dataset_url); $('#datasetStatus').textContent = `Source status: ${sourceStatusText(p.source_status)} · checked ${p.source_checked_at ? formatDate(p.source_checked_at) : 'not yet'}`;
  $$('.tab-list button').forEach((b,i) => b.classList.toggle('active', i === 0)); renderProjectTab(); $('#projectModal').showModal();
}
function renderProjectTab() {
  if (!state.currentProject) return; const labels = {excel_guide:'EXECUTION GUIDE',powerbi_dax:'DAX / MODEL',production_sql:'SQL',python_script:'PYTHON'};
  $('#codeLabel').textContent = labels[state.currentTab]; $('#projectCode').textContent = state.currentProject[state.currentTab] || '';
}
async function loadTrends() {
  try {
    const result = await api('/api/project-trends');
    $('#trendGrid').innerHTML = result.items.length ? result.items.map(t => `<a class="trend-card" href="${safeUrl(t.url)}" target="_blank" rel="noopener"><b>${esc(t.title)}</b><p>${esc(t.description || 'No repository description supplied.')}</p><span class="trend-meta">${esc(t.language || 'Language n/a')} · ★ ${Number(t.stars || 0)} · updated ${formatDate(t.updated_at)}</span></a>`).join('') : '<p class="company-name">Trend signal will populate after the first daily scan.</p>';
  } catch { $('#trendGrid').innerHTML = '<p class="company-name">Trend signal unavailable.</p>'; }
}

function roadmapCompleted() {
  try { return new Set(JSON.parse(localStorage.getItem('samRoadmapProgressV1') || '[]')); }
  catch { return new Set(); }
}
function renderRoadmap() {
  const completed = roadmapCompleted();
  const total = ROADMAP_PHASES.reduce((sum, phase) => sum + phase.tasks.length, 0);
  const done = [...completed].filter(id => ROADMAP_PHASES.some(phase => phase.tasks.some(task => task[0] === id))).length;
  const percent = Math.round(100 * done / total);
  $('#roadmapPercent').textContent = `${percent}%`; $('#roadmapCount').textContent = `${done} of ${total} complete`; $('#roadmapBar').style.width = `${percent}%`;
  $('#roadmapGrid').innerHTML = ROADMAP_PHASES.map((phase, index) => {
    const phaseDone = phase.tasks.filter(task => completed.has(task[0])).length;
    return `<article class="roadmap-phase"><div class="roadmap-phase-head"><div><span>PHASE ${String(index+1).padStart(2,'0')}</span><h3>${esc(phase.title)}</h3><small>${esc(phase.duration)}</small></div><b>${phaseDone}/${phase.tasks.length}</b></div>${phase.tasks.map(task => `<label class="roadmap-task ${completed.has(task[0]) ? 'done' : ''}"><input type="checkbox" data-roadmap="${esc(task[0])}" ${completed.has(task[0]) ? 'checked' : ''}><span><b>${esc(task[1])}</b><small>${esc(task[2])}</small></span>${task[3] ? `<a href="${safeUrl(task[3])}" target="_blank" rel="noopener" title="Open free resource">↗</a>` : '<i></i>'}</label>`).join('')}</article>`;
  }).join('');
  $$('[data-roadmap]').forEach(input => input.addEventListener('change', () => {
    const next = roadmapCompleted(); input.checked ? next.add(input.dataset.roadmap) : next.delete(input.dataset.roadmap);
    localStorage.setItem('samRoadmapProgressV1', JSON.stringify([...next])); renderRoadmap();
  }));
  $$('.roadmap-task a').forEach(link => link.addEventListener('click', event => event.stopPropagation()));
}

async function loadSkills() {
  const skills = await api('/api/skills');
  $('#skillGrid').innerHTML = skills.map(s => `<article class="skill-card"><div class="skill-top"><div><span class="skill-category">${esc(s.category.toUpperCase())}</span><h3>${esc(s.name)}</h3></div><span class="skill-value" id="skillValue${s.id}">${s.mastery}%</span></div><p>${esc(s.evidence)}</p><input class="skill-slider" data-id="${s.id}" type="range" min="0" max="100" value="${s.mastery}" aria-label="${esc(s.name)} mastery"></article>`).join('');
  $$('.skill-slider').forEach(slider => {
    slider.addEventListener('input', () => $(`#skillValue${slider.dataset.id}`).textContent = `${slider.value}%`);
    slider.addEventListener('change', async () => {
      try { await api(`/api/skills/${slider.dataset.id}`, {method:'PATCH', body:JSON.stringify({mastery:Number(slider.value)})}); toast('Skill assessment saved'); await loadMetrics(); }
      catch (e) { toast(e.message,'error'); }
    });
  });
}

async function loadQuestions() {
  const cat = $('#interviewCategory').value, diff = $('#interviewDifficulty').value;
  state.questions = await api(`/api/interview?category=${encodeURIComponent(cat)}&difficulty=${encodeURIComponent(diff)}`); state.qIndex = 0; renderQuestion();
}
function renderQuestion() {
  const q = state.questions[state.qIndex]; $('#answerBox').hidden = true; $('#revealAnswer').textContent = 'Reveal answer';
  if (!q) { $('#qCategory').textContent = 'NO MATCH'; $('#qDifficulty').textContent = '—'; $('#qText').textContent = 'No question matches those filters.'; return; }
  $('#qCategory').textContent = q.category; $('#qDifficulty').textContent = q.difficulty; $('#qText').textContent = q.question; $('#qAnswer').textContent = q.answer;
}

async function runATS() {
  const job_description = $('#atsText').value.trim(), job_title = $('#atsTitle').value.trim() || 'Target role';
  if (job_description.length < 30) return toast('Paste at least 30 characters from a real job description.', 'error');
  const button = $('#runAts'); button.disabled = true; button.textContent = 'Analyzing…';
  try {
    const r = await api('/api/ats_match', {method:'POST', body:JSON.stringify({job_description, job_title})});
    $('#atsResult').hidden = false; $('#atsResult').innerHTML = `<div class="ats-score"><strong>${r.score}%</strong><div><b>JD-specific profile comparison</b><p>Analysis ${esc(r.analysis_id)} · ${r.required_detected.length} skill groups detected</p></div></div>${r.eligibility_warning ? `<p class="ats-warning">${esc(r.eligibility_warning)}</p>` : ''}<div class="ats-breakdown"><span>Skills <b>${r.breakdown.skill_coverage}%</b></span><span>Role <b>${r.breakdown.role_alignment}%</b></span><span>Experience <b>${r.breakdown.experience_alignment}%</b></span></div><p class="ats-method">${esc(r.formula || '')} · ${esc(r.scoring_version || 'profile-JD scoring')}${r.required_years != null ? ` · JD minimum detected: ${Number(r.required_years)} year(s)` : ' · no explicit experience minimum detected'}</p><h4>MATCHED WITH PROFILE EVIDENCE</h4><div class="chip-list">${r.matched.map(x=>`<span class="match">${esc(x)}</span>`).join('') || '<span>None detected</span>'}</div>${r.partial.length ? `<h4>PARTIAL EVIDENCE</h4><div class="chip-list">${r.partial.map(x=>`<span>${esc(x)}</span>`).join('')}</div>` : ''}<h4>GAPS / NOT STATED IN PROFILE</h4><div class="chip-list">${r.missing.map(x=>`<span class="missing">${esc(x)}</span>`).join('') || '<span>No detected taxonomy gaps</span>'}</div><h4>TRUTH-SAFE BULLET STARTERS</h4><ul>${r.tailored_bullets.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p class="disclaimer">${esc(r.disclaimer)}</p>`;
  } catch (e) { toast(e.message,'error'); }
  finally { button.disabled = false; button.textContent = 'Analyze description'; }
}

function toggleJarvis(force) {
  const panel = $('#jarvisPanel');
  const open = typeof force === 'boolean' ? force : !panel.classList.contains('open');
  panel.classList.toggle('open', open); panel.setAttribute('aria-hidden', String(!open)); $('#jarvisFab').setAttribute('aria-expanded', String(open));
  if (open) setTimeout(() => $('#jarvisText').focus(), 100);
}
function jarvisMessage(text, type = 'assistant', jobs = []) {
  const node = document.createElement('div'); node.className = `jarvis-message ${type}`;
  node.innerHTML = `<span>${esc(text)}</span>${jobs.slice(0,5).map(job => `<div class="jarvis-job"><a href="${safeUrl(job.url)}" target="_blank" rel="noopener">Apply ↗</a><b>${esc(job.title)}</b><span>${esc(job.company || '')} · ${esc(job.location_group || job.location || '')}</span>${job.transition_reason ? `<small>${esc(job.transition_reason)}</small>` : ''}</div>`).join('')}`;
  $('#jarvisMessages').append(node); $('#jarvisMessages').scrollTop = $('#jarvisMessages').scrollHeight; return node;
}
function speakJarvis(text) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel(); const utterance = new SpeechSynthesisUtterance(text); utterance.lang = 'en-IN'; utterance.rate = 1; speechSynthesis.speak(utterance);
}
async function trackJarvisJobs(jobs, button) {
  if (!jobs.length) return;
  button.disabled = true; button.textContent = 'Saving…'; let saved = 0;
  for (const job of jobs) {
    try {
      await api('/api/jobs', {method:'POST', body:JSON.stringify({title:job.title,company:job.company,location:job.location || '',portal:job.source || 'Direct',url:job.url,status:'Interested',notes:'Added by Jarvis after user confirmation.',live_job_id:job.id})}); saved++;
    } catch (error) { jarvisMessage(`Could not save ${job.title}: ${error.message}`, 'assistant'); }
  }
  button.remove(); await Promise.all([loadPipeline(), loadMetrics()]);
  jarvisMessage(`${saved} job${saved === 1 ? '' : 's'} saved to Interested. No application was submitted.`, 'assistant');
}
async function askJarvis(command, spoken = false) {
  const query = String(command || '').trim(); if (query.length < 2) return;
  toggleJarvis(true); jarvisMessage(query, 'user'); $('#jarvisText').value = '';
  const waiting = document.createElement('div'); waiting.className = 'jarvis-message assistant'; waiting.textContent = 'Checking the live career database…'; $('#jarvisMessages').append(waiting);
  try {
    const context_job_ids = state.jarvisLastJobs.map(job => Number(job.id)).filter(Boolean).slice(0,20);
    const result = await api('/api/jarvis', {method:'POST', body:JSON.stringify({query, context_job_ids})}); waiting.remove();
    const resultJobs = result.jobs || []; const responseNode = jarvisMessage(result.message, 'assistant', resultJobs);
    if (resultJobs.length && result.action !== 'explain_job') state.jarvisLastJobs = resultJobs;
    if (result.action === 'confirm_track_jobs' && resultJobs.length) {
      const confirm = document.createElement('button'); confirm.className = 'jarvis-confirm'; confirm.textContent = `Confirm: save ${resultJobs.length} to Interested`;
      confirm.addEventListener('click', () => trackJarvisJobs(resultJobs, confirm)); responseNode.append(confirm);
    }
    if (spoken) speakJarvis(result.message);
    if (result.action === 'show_roadmap') $('#roadmap').scrollIntoView({behavior:'smooth'});
    if (result.action === 'show_pipeline') $('#pipeline').scrollIntoView({behavior:'smooth'});
    if (result.action === 'show_ats') $('#ats').scrollIntoView({behavior:'smooth'});
    if (result.action === 'refresh_jobs') startSync();
    if (result.action === 'filter_jobs') {
      $('#locationFilter').value = result.location_group || 'preferred';
      const matchingRole = [...$('#roleFilter').options].find(option => result.role && option.value.toLowerCase().includes(result.role.toLowerCase()));
      $('#roleFilter').value = matchingRole ? matchingRole.value : '';
      $('#freshnessFilter').value = 'verified'; $('#jobSearch').value = '';
      await loadLiveJobs(); $('#radar').scrollIntoView({behavior:'smooth'});
    }
  } catch (error) { waiting.remove(); jarvisMessage(`I could not complete that command: ${error.message}`, 'assistant'); }
}
function startJarvisVoice() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return jarvisMessage('Voice recognition is unavailable in this browser. Use Chrome on Android or type your command.', 'assistant');
  if (jarvisRecognition) { jarvisRecognition.stop(); return; }
  jarvisRecognition = new SpeechRecognition(); jarvisRecognition.lang = 'en-IN'; jarvisRecognition.interimResults = false; jarvisRecognition.maxAlternatives = 1;
  $('#jarvisMic').classList.add('listening');
  jarvisRecognition.onresult = event => askJarvis(event.results[0][0].transcript, true);
  jarvisRecognition.onerror = event => jarvisMessage(`Voice recognition issue: ${event.error}. You can type the command instead.`, 'assistant');
  jarvisRecognition.onend = () => { jarvisRecognition = null; $('#jarvisMic').classList.remove('listening'); };
  jarvisRecognition.start();
}

async function startSync() {
  try {
    const result = await api('/api/scraper/scan', {method:'POST'}); toast(result.status === 'already_running' ? 'A source refresh is already running.' : 'Source refresh started. Public portals may take a few minutes.');
    $$('.sync-button, #syncRadar').forEach(el => el.classList.add('running'));
    let checks = 0;
    const timer = setInterval(async () => {
      checks++; const status = await api('/api/scraper/status').catch(() => ({running:false})); await loadMetrics();
      if (!status.running || checks > 80) { clearInterval(timer); await Promise.all([loadLiveJobs(), loadShortlist(), loadMetrics(), loadPortals(), loadTrends()]); toast('Source refresh complete. Live jobs and the 20-job shortlist are updated.'); $$('.sync-button, #syncRadar').forEach(el => el.classList.remove('running')); }
    }, 3000);
  } catch (e) { toast(e.message,'error'); }
}

function bindEvents() {
  $('#portalRole').addEventListener('change', loadPortals); $('#portalLocation').addEventListener('change', loadPortals);
  $('#roleFilter').addEventListener('change', loadLiveJobs); $('#locationFilter').addEventListener('change', loadLiveJobs); $('#sourceFilter').addEventListener('change', loadLiveJobs); $('#freshnessFilter').addEventListener('change', loadLiveJobs); $('#jobSort').addEventListener('change', loadLiveJobs);
  $('#shortlistLocation').addEventListener('change', loadShortlist);
  $('#scoreFilter').addEventListener('input', e => $('#scoreOutput').textContent = `${e.target.value}%+`); $('#scoreFilter').addEventListener('change', loadLiveJobs);
  $('#jobSearch').addEventListener('input', renderLiveJobs); $('#showMoreJobs').addEventListener('click', () => { state.visibleJobs += 20; renderLiveJobs(); });
  $('#syncTop').addEventListener('click', startSync); $('#syncRadar').addEventListener('click', startSync);
  $('#installApp').addEventListener('click', installPWA);
  $('#addJobButton').addEventListener('click', () => { $('#jobForm').reset(); $('#jobLiveId').value=''; $('#jobModalTitle').textContent='Add a lead'; $('#jobPortal').value='Direct'; $('#jobModal').showModal(); });
  $('#jobForm').addEventListener('submit', async e => {
    e.preventDefault(); const payload = {title:$('#jobTitle').value,company:$('#jobCompany').value,location:$('#jobLocation').value,portal:$('#jobPortal').value,url:$('#jobUrl').value,status:'Interested',notes:$('#jobNotes').value,live_job_id:Number($('#jobLiveId').value)||null};
    const deleted = readPipelineTombstones(); deleted.delete(payload.url); localStorage.setItem('samPipelineDeletedUrls', JSON.stringify([...deleted]));
    try { await api('/api/jobs',{method:'POST',body:JSON.stringify(payload)}); $('#jobModal').close(); toast('Lead saved to Interested · synced'); await loadPipeline(); await loadMetrics(); }
    catch(err){
      const stamp = new Date().toISOString();
      const localJob = {...payload,id:-Date.now(),listing_type:'manual_local',verified:0,created_at:stamp,updated_at:stamp,_device_cached:true};
      state.jobs = state.jobs.filter(job => job.url !== payload.url).concat(localJob); savePipelineCache(); renderPipeline(); $('#jobModal').close();
      toast(`Saved on this device; server sync failed: ${err.message}`, 'error');
    }
  });
  $$('.modal-close,[data-close]').forEach(b => b.addEventListener('click', () => document.getElementById(b.dataset.close || b.closest('dialog').id).close()));
  $$('.tab-list button').forEach(b => b.addEventListener('click', () => { state.currentTab=b.dataset.tab; $$('.tab-list button').forEach(x=>x.classList.toggle('active',x===b)); renderProjectTab(); }));
  $('#copyProjectCode').addEventListener('click', async () => { await navigator.clipboard.writeText($('#projectCode').textContent); toast('Project content copied'); });
  $('#interviewCategory').addEventListener('change', loadQuestions); $('#interviewDifficulty').addEventListener('change', loadQuestions);
  $('#revealAnswer').addEventListener('click', () => { const box=$('#answerBox'); box.hidden=!box.hidden; $('#revealAnswer').textContent=box.hidden?'Reveal answer':'Hide answer'; });
  $('#nextQuestion').addEventListener('click', () => { if(!state.questions.length)return; state.qIndex=(state.qIndex+1)%state.questions.length; renderQuestion(); });
  $('#runAts').addEventListener('click', runATS);
  $('#menuButton').addEventListener('click', () => { const open=$('#nav').classList.toggle('open'); $('#menuButton').setAttribute('aria-expanded', String(open)); });
  $$('#nav a').forEach(a=>a.addEventListener('click',()=>$('#nav').classList.remove('open')));
  $('#themePulse').addEventListener('click', () => { const canvas=$('#webgl-bg'); const off=canvas.style.opacity==='0'; canvas.style.opacity=off?'.45':'0'; toast(off?'Ambient orbit enabled':'Ambient orbit paused'); });
  $('#jarvisFab').addEventListener('click', () => toggleJarvis()); $('#jarvisClose').addEventListener('click', () => toggleJarvis(false));
  $('#jarvisMic').addEventListener('click', startJarvisVoice); $('#jarvisForm').addEventListener('submit', event => { event.preventDefault(); askJarvis($('#jarvisText').value); });
  $$('.jarvis-suggestions button').forEach(button => button.addEventListener('click', () => askJarvis(button.dataset.command)));
  $('#showAccessKey')?.addEventListener('change', event => { $('#accessKeyInput').type = event.target.checked ? 'text' : 'password'; });
  $('#changeAccessKey')?.addEventListener('click', async () => {
    localStorage.removeItem('samAppAccessKey');
    try { await requestAccessKey(); location.reload(); } catch (error) { toast(error.message, 'error'); }
  });
  $$('dialog').forEach(d => d.addEventListener('click', e => { if (e.target === d && d.id !== 'accessKeyModal') d.close(); }));
  const observer = new IntersectionObserver(entries => entries.forEach(entry => { if(entry.isIntersecting) $$('#nav a').forEach(a=>a.classList.toggle('active',a.getAttribute('href')===`#${entry.target.id}`)); }), {rootMargin:'-30% 0px -60%'});
  $$('main section[id]').forEach(s=>observer.observe(s));
}

async function preparePrivateAccess() {
  try {
    const health = await fetchWithWakeRetry('/api/health', {cache:'no-store'}).then(response => response.json());
    if (!health.access_key_required) return;
    const saved = localStorage.getItem('samAppAccessKey') || '';
    if (saved) {
      const check = await fetchWithWakeRetry('/api/auth/verify', {headers:{'X-App-Key':saved,'Cache-Control':'no-store'}, cache:'no-store'}, 4);
      if (check.ok) return;
      localStorage.removeItem('samAppAccessKey');
    }
    await requestAccessKey();
  } catch (error) {
    if (navigator.onLine) throw error;
  }
}

async function initialize() {
  bindEvents(); renderRoadmap();
  await registerPWA();
  try {
    await preparePrivateAccess();
    await Promise.all([loadRoles(), loadMetrics(), loadPipeline(), loadProjects(), loadSkills(), loadQuestions(), loadTrends(), loadShortlist()]);
    await Promise.all([loadPortals(), loadLiveJobs()]);
    const status = await api('/api/scraper/status');
    if (status.running) {
      const watcher = setInterval(async () => { const s=await api('/api/scraper/status').catch(()=>({running:false})); await loadMetrics(); if(!s.running){clearInterval(watcher);await Promise.all([loadLiveJobs(),loadShortlist(),loadMetrics(),loadTrends(),loadProjects()]);toast('Initial source scan complete. Live jobs and shortlist updated.');}},4000);
    }
    setTimeout(() => localStorage.setItem('samLastJobVisit', new Date().toISOString()), 5000);
  } catch (e) { toast(`Initialization issue: ${e.message}`,'error'); }
}
initialize();

// Reflect backend changes while the app stays open. This polls the already-collected
// database every five minutes; source discovery itself remains hourly or manual to
// respect public-site rate limits and the free-host budget.
setInterval(() => {
  if (navigator.onLine && !document.hidden) Promise.all([loadMetrics(), loadLiveJobs(), loadShortlist()]).catch(()=>{});
}, 5 * 60 * 1000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && navigator.onLine) Promise.all([loadMetrics(), loadLiveJobs(), loadShortlist()]).catch(()=>{});
});
