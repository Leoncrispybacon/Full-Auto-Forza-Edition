/* FAFE web UI — frontend logic.
   JS→Python via pywebview.api; Python→JS via window.appendLog/setStatus.
   Full Auto + the count/option function tabs are wired; garage-block tabs
   (Unlock Wheelspins, Delete Cars) get their selector in the next pass. */

// option arrays store [value, i18n-key]; labels are translated at render via t().
function grindOptions() {
  const hasDlc = state.cfg && state.cfg.car_pass_dlc_owned === true;
  return [
    ['wheelspin', hasDlc ? 'grind_mad_mike' : 'grind_wheelspin'],
    ['money', 'grind_money'],
    ['mixed', hasDlc ? 'grind_mixed_mad_mike' : 'grind_mixed'],
  ];
}
const BRANCH = [['racing','branch_racing'],['wheelspin','branch_wheelspin']];
const WHEEL_TYPE = [['super','wheel_super'],['normal','wheel_normal']];
const CAR_SVG = '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/></svg>';
const CHECK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" width="15" height="15"><path d="M20 6 9 17l-5-5"/></svg>';
// Per-tab text (kicker/title/tagline) lives in i18n as mode_<tab>_kicker/title/
// tagline/count/hint; MODES only holds non-text behaviour (control + start fn).
const MODES = {
  race:      { control:'count', start:'start_race', value:0 },
  buy:       { control:'count', start:'start_buy',  value:0 },
  wheelspin: { control:'wheel', start:'start_wheelspin', value:0 },
  mastery:   { control:'block', start:'start_mastery' },
  delete:    { control:'block', start:'start_delete' },
  settings:  { control:'none' },
};
// Teaser gate — driven by get_init().coming_soon (backend), not a hardcoded flag,
// so a stale bundled app.js can't keep showing COMING SOON after 2.0 goes live.
let COMING_SOON = false;

const state = { grind:'wheelspin', branch:'racing', start:'race', func:'full_auto', cfg:{},
                licensed:false, fullAutoBundled:true, comingSoon:false };

// ── bridge ───────────────────────────────────────────────────
function API(name, ...args) {
  if (window.pywebview && pywebview.api && pywebview.api[name]) return pywebview.api[name](...args);
  return Promise.resolve(null);
}
let isRunning = false;
window.appendLog = (line) =>
  document.querySelectorAll('.log-body').forEach(l => { l.textContent += line + '\n'; l.scrollTop = l.scrollHeight; });
window.setStatus = (text, running) => {
  isRunning = !!running;
  document.querySelectorAll('.status').forEach(s => {
    s.classList.toggle('run', !!running);
    const t = s.querySelector('.statusText'); if (t) t.textContent = text;
  });
  // Grey the Start button(s) while a run is active (stop via F9).
  document.querySelectorAll('.start').forEach(b => b.classList.toggle('running', !!running));
  if (!running && typeof setStage === 'function') setStage(-1);   // clear the loop bar
};
// Global hotkeys routed from Python (work while the game is focused).
window.onHotkey = (name) => {
  if (name === 'f9') {
    if (isRunning) { API('stop'); }
    else {
      const btn = document.querySelector('.view:not([hidden]) .start');
      if (btn && !btn.disabled) btn.click();   // start the active view
    }
  } else if (name === 'f12') {
    const log = document.querySelector('.view:not([hidden]) .log-body');
    API('report', log ? log.textContent : '');
  }
};
function clearLog() { document.querySelectorAll('.log-body').forEach(l => l.textContent = ''); }
// The keyboard-driven automations (Unlock/Delete) inject Enter/Space. If a
// Start/Stop button holds focus, that injected key re-fires it — re-clicking
// Start wipes the log mid-run, hitting Stop kills the run. Block NATIVE keyboard
// activation of these buttons; F9 start/stop is routed via onHotkey, not here.
document.addEventListener('keydown', (e) => {
  if ((e.key === 'Enter' || e.key === ' ' || e.code === 'Space') &&
      e.target instanceof HTMLElement && e.target.matches('.start, .stop')) {
    e.preventDefault();
  }
}, true);
// In-app tutorial modal (replaces opening the browser).
function openHowto() {
  const key = state.func || 'full_auto';
  document.getElementById('howTitle').textContent = key === 'full_auto' ? t('fa_title') : t('mode_' + key + '_title');
  document.getElementById('howBody').textContent = t('howto_' + key);
  document.getElementById('howModal').classList.add('open');
}
function closeHowto() { document.getElementById('howModal').classList.remove('open'); }
function openGuide() { API('howto', state.func || 'full_auto'); }   // opens the web guide
// Report a Bug — shows the F12 tutorial (the actual capture is the global F12
// hotkey, pressed while the GAME is focused; clicking a button would screenshot
// FAFE instead). Steps are built dynamically to inject the report key.
function reportBug() {
  const key = (state.cfg.report_key || 'f12').toUpperCase();
  const ol = document.getElementById('reportSteps'); ol.innerHTML = '';
  for (let i = 1; i <= 5; i++) {
    const li = document.createElement('li'); li.style.lineHeight = '1.55';
    li.textContent = t('report_step' + i, { key }); ol.appendChild(li);
  }
  document.getElementById('reportModal').classList.add('open');
}
function closeReport() { document.getElementById('reportModal').classList.remove('open'); }
function openSupport() { document.getElementById('supportModal').classList.add('open'); }
function closeSupport() { document.getElementById('supportModal').classList.remove('open'); }
function showUpdate(tag, url) {
  const modal = document.getElementById('updateModal');
  if (!modal) return;
  modal.dataset.url = url || '';
  const title = document.getElementById('updateTitle');
  const body = document.getElementById('updateBody');
  if (title) title.textContent = t('update_available', { tag });
  if (body) body.textContent = t('update_prompt');
  modal.classList.add('open');
}
function closeUpdate() { document.getElementById('updateModal').classList.remove('open'); }
function openUpdatePage() {
  const modal = document.getElementById('updateModal');
  API('open_update_page', modal ? modal.dataset.url : '');
  closeUpdate();
}
// Reflect overlay on/off across both topbar buttons + the Settings switch.
// Global so Python (F10 hotkey) can push the state back here to stay in sync.
window.setOverlayUI = (on) => {
  on = !!on;
  state.cfg.overlay_enabled = on;
  document.querySelectorAll('.overlay-btn').forEach(b => { b.textContent = (on ? '● ' : '○ ') + t('overlay'); b.classList.toggle('on', on); });
  const sw = document.getElementById('setOverlay'); if (sw) sw.classList.toggle('on', on);
  return on;
};
function togglePanel(id) { document.getElementById(id).classList.toggle('open'); }

// ── small DOM builders ───────────────────────────────────────
function el(tag, css, text) { const e = document.createElement(tag); if (css) e.style.cssText = css; if (text != null) e.textContent = text; return e; }
function divider() { return el('div', 'height:1px;background:var(--border-soft)'); }
function countRow(tab, m) {
  const row = el('div', 'display:flex;align-items:center;gap:16px;flex-wrap:wrap');
  row.appendChild(el('label', 'font-size:15px;color:var(--text)', t('mode_' + tab + '_count')));
  const key = tab + '_count';   // race_count / buy_count / wheelspin_count — persisted
  const inp = document.createElement('input'); inp.className = 'num mode-count';
  inp.value = state.cfg[key] != null ? state.cfg[key] : (m.value ?? 0);
  const commit = () => {
    const v = Math.max(0, parseInt(inp.value, 10) || 0);
    inp.value = v; state.cfg[key] = v; API('set_cfg', key, v);
  };
  inp.oninput = commit;
  inp.onchange = commit;
  row.appendChild(inp);
  row.appendChild(el('span', 'font-size:13px;color:var(--text2)', t('mode_' + tab + '_hint')));
  return row;
}
function segRow(label, opts, cfgKey, current, onChange) {
  const row = el('div', 'display:flex;align-items:center;gap:24px;flex-wrap:wrap');
  row.appendChild(el('span', 'font-size:15px;color:var(--text);flex:1;min-width:220px', label));
  const seg = el('div', 'display:flex;gap:6px'); seg.className = 'seg';
  opts.forEach(([k, lbl]) => {
    const b = el('button', null, t(lbl)); if (k === current) b.classList.add('on');
    b.onclick = () => { state.cfg[cfgKey] = k; API('set_cfg', cfgKey, k);
                        seg.querySelectorAll('button').forEach(x => x.classList.remove('on')); b.classList.add('on');
                        if (onChange) onChange(k); };
    seg.appendChild(b);
  });
  row.appendChild(seg); return row;
}
function checkRow(label, cfgKey, checked) {
  const row = el('label', 'display:flex;align-items:center;gap:11px;cursor:pointer');
  const box = el('button', `width:20px;height:20px;flex:none;border-radius:5px;cursor:pointer;color:#fff;font-size:12px;display:flex;align-items:center;justify-content:center;border:1px solid ${checked?'var(--accent)':'#3a4658'};background:${checked?'var(--accent)':'transparent'}`, checked ? '✓' : '');
  let on = checked;
  box.onclick = () => { on = !on; state.cfg[cfgKey] = on; API('set_cfg', cfgKey, on);
    box.textContent = on ? '✓' : ''; box.style.border = `1px solid ${on?'var(--accent)':'#3a4658'}`; box.style.background = on ? 'var(--accent)' : 'transparent'; };
  row.appendChild(box); row.appendChild(el('span', 'font-size:13.5px;color:var(--row)', label));
  return row;
}
// "Keep if sell price >= X credits" (0 = off). Integer credits, saved on change.
function keepPriceRow() {
  const row = el('div', 'display:flex;align-items:center;gap:11px;flex-wrap:wrap');
  row.appendChild(el('span', 'font-size:13.5px;color:var(--row)', t('keep_price_label')));
  const inp = document.createElement('input'); inp.className = 'num';
  inp.value = parseInt(state.cfg.wheelspin_keep_above_price ?? 0, 10) || 0;
  const commit = () => {
    let v = parseInt(String(inp.value).replace(/[^0-9]/g, ''), 10); if (isNaN(v) || v < 0) v = 0;
    inp.value = v; state.cfg.wheelspin_keep_above_price = v; API('set_cfg', 'wheelspin_keep_above_price', v);
  };
  inp.onchange = commit; inp.onkeydown = (e) => { if (e.key === 'Enter') inp.blur(); };
  row.appendChild(inp);
  row.appendChild(el('span', 'font-size:13px;color:var(--text2)', t('keep_price_hint')));
  return row;
}

// ── Full Auto view ───────────────────────────────────────────
function renderSeg(id, opts, key) {
  const wrap = document.getElementById(id); wrap.innerHTML = '';
  opts.forEach(([k, label]) => {
    const b = el('button', null, t(label)); if (state[key] === k) b.classList.add('on');
    b.onclick = () => { state[key] = k; persistFA(key); renderFA(); };
    wrap.appendChild(b);
  });
}
function renderChain() {
  const last = state.branch === 'wheelspin' ? t('step_wheelspin') : t('step_race_again');
  const defs = [['1',t('step_race')],['2',t('step_buy')],['3',t('step_unlock')],['4',t('step_sell')],['5',last]];
  const wrap = document.getElementById('steps'); wrap.innerHTML = '';
  const bar = el('div'); bar.className = 'loopbar';
  defs.forEach(([n,lbl]) => {
    const seg = el('div'); seg.className = 'loopseg';
    seg.innerHTML = `<span class="fluid"></span><span class="sl"><b>${n}</b>${lbl}</span>`;
    bar.appendChild(seg);
  });
  wrap.appendChild(bar);
  wrap.appendChild(el('span', null, t('fa_repeats'))).className = 'loopnote';
  setStage(window._faStage ?? -1);   // re-apply current stage after a rebuild
}
// Loop progress: stages 0..n-1 are full, stage n fills to its real fraction
// (e.g. 16/32 cars unlocked → 50%). frac is remembered between calls so entering
// a step (setStage(n,0)) resets it and progress updates grow it.
function setStage(n, frac) {
  if (typeof n === 'number') window._faStage = n;
  if (typeof frac === 'number') window._faFrac = Math.max(0, Math.min(1, frac));
  const cur = window._faStage ?? -1, f = window._faFrac || 0;
  document.querySelectorAll('#steps .loopseg').forEach((s, i) => {
    const done = cur >= 0 && i < cur, active = i === cur;
    s.classList.toggle('done', done);
    s.classList.toggle('active', active);
    const fill = s.querySelector('.fluid');
    if (fill) fill.style.width = done ? '100%' : (active ? (f * 100).toFixed(1) + '%' : '0%');
  });
}
window.setStage = setStage;
// Full Auto pre-flight checklist — Start stays disabled until every box is ticked.
const FA_CHECKLIST = [
  { key:'chk_driving' },
  { key:'chk_map' },
  { key:'chk_favorite', cfg:'fa_check_favorite_ok' },
  { key:'chk_stock_paint', cfg:'fa_check_stock_paint_ok' },
  { key:'chk_collection_unlock', cfg:'fa_check_collection_unlock_ok' },
];
function renderChecklist() {
  const host = document.getElementById('faChecklist'); if (!host) return;
  const startBtn = document.getElementById('faStartBtn');
  host.innerHTML = '';
  const checked = FA_CHECKLIST.map(item => item.cfg ? state.cfg[item.cfg] === true : false);
  const gate = () => {
    const ok = checked.every(Boolean);
    startBtn.disabled = !ok; startBtn.style.opacity = ok ? '' : '.45';
    startBtn.style.cursor = ok ? 'pointer' : 'not-allowed';
  };
  const card = el('div'); card.className = 'fa-check';
  card.appendChild(el('div', null, t('chk_title'))).className = 'fa-check-title';
  FA_CHECKLIST.forEach((item, i) => {
    const txt = t(item.key);
    const row = el('label'); row.className = 'fa-check-row';
    const box = el('button'); box.className = 'fa-check-box';
    box.classList.toggle('on', checked[i]);
    box.textContent = checked[i] ? '\u2713' : '';
    box.onclick = () => { checked[i] = !checked[i]; box.classList.toggle('on', checked[i]);
                          box.textContent = checked[i] ? '\u2713' : '';
                          if (item.cfg) { state.cfg[item.cfg] = checked[i]; API('set_cfg', item.cfg, checked[i]); }
                          gate(); };
    row.appendChild(box);
    row.appendChild(el('span', null, txt)).className = 'fa-check-txt';
    card.appendChild(row);
  });
  host.appendChild(card);
  gate();
}
function renderFA() {
  renderSeg('grindSeg', grindOptions(), 'grind');
  renderSeg('branchSeg', BRANCH, 'branch');
  document.getElementById('branchRow').style.display = state.grind === 'money' ? 'none' : 'flex';
  renderChain();
  renderChecklist();
}
function persistFA(key) {
  if (key === 'grind')  API('set_cfg', 'full_auto_grind_type', state.grind);
  if (key === 'branch') API('set_cfg', 'full_auto_branch_mode', state.branch);
}
async function startFA() {
  if (isRunning) return;
  const inp = document.getElementById('faRaces');
  const v = Math.max(1, parseInt(inp.value, 10) || 1);
  inp.value = v; state.cfg.full_auto_races = v; API('set_cfg', 'full_auto_races', v);
  clearLog();
  API('start_full_auto', v);
}

// ── garage-block selector (Unlock / Delete) ──────────────────
function blockSelector(tab, startBtn) {
  const pfx = tab, isDelete = tab === 'delete';
  let first = parseInt(state.cfg[`${pfx}_block_first_row`] ?? 1);
  let mid   = parseInt(state.cfg[`${pfx}_block_middle_cols`] ?? 0);
  let last  = parseInt(state.cfg[`${pfx}_block_last_row`] ?? 3);

  const wrap = el('div'); wrap.className = 'block-wrap';
  const title = el('div'); title.className = 'block-title';
  title.innerHTML = (isDelete ? t('block_delete_title') : t('block_unlock_title')) +
    ` <span style="color:var(--text2);font-weight:500">${t('block_suffix')}</span>`;
  wrap.appendChild(title);
  wrap.appendChild(el('div', null, t('block_hint'))).className = 'block-hint';

  const grid = el('div'); grid.className = 'block-grid';
  function colPicker(kind, onPick) {
    const col = el('div'); col.className = 'block-col';
    col.appendChild(el('span', null, kind === 'first' ? t('block_first') : t('block_last'))).className = 'clbl';
    const cellsRow = el('div', 'display:flex;align-items:center;gap:8px');
    const cells = el('div'); cells.className = 'block-cells';
    const arr = [1,2,3].map(r => {
      const b = el('button'); b.className = 'block-cell ' + kind; b.innerHTML = '<span class="carico">' + CAR_SVG + '</span>';
      b.onclick = () => onPick(r); cells.appendChild(b); return b;
    });
    const arrow = el('span', `color:${kind === 'first' ? '#2f5f48' : '#2f5f7a'}`, '↓'); arrow.className = 'block-arrow';
    if (kind === 'first') cellsRow.append(cells, arrow); else cellsRow.append(arrow, cells);
    col.appendChild(cellsRow); return { col, arr };
  }
  const fp = colPicker('first', r => { first = r; commit(); });
  grid.appendChild(fp.col);

  const midWrap = el('div'); midWrap.className = 'block-mid';
  const step = el('div'); step.className = 'block-step';
  const dec = el('button', null, '−'); dec.className = 'step-btn'; dec.onclick = () => { mid = Math.max(0, mid - 1); commit(); };
  const midNum = document.createElement('input'); midNum.type = 'number'; midNum.min = 0; midNum.className = 'block-midnum';
  midNum.addEventListener('change', () => { mid = Math.max(0, parseInt(midNum.value) || 0); commit(); });
  midNum.addEventListener('blur', () => { mid = Math.max(0, parseInt(midNum.value) || 0); render(); }); // reset bad text on blur
  const inc = el('button', null, '+'); inc.className = 'step-btn'; inc.onclick = () => { mid += 1; commit(); };
  step.append(dec, midNum, inc); midWrap.appendChild(step);
  const midCols = el('div'); midCols.className = 'block-midcols'; midWrap.appendChild(midCols);
  grid.appendChild(midWrap);

  const lp = colPicker('last', r => { last = r; commit(); });
  grid.appendChild(lp.col);
  wrap.appendChild(grid);

  const bar = el('div'); bar.className = 'block-bar';
  const segF = el('div'), segM = el('div'), segL = el('div');
  segF.style.background = 'var(--ok)'; segM.style.background = '#3b82f6'; segL.style.background = '#38bdf8';
  bar.append(segF, segM, segL); wrap.appendChild(bar);

  const legend = el('div'); legend.className = 'block-legend';
  function tag(color, label) {
    const t = el('div'); t.className = 'block-tag';
    t.innerHTML = `<span class="sq" style="background:${color}"></span><span class="tl">${label}</span><span class="tv"></span>`;
    return t;
  }
  const tagF = tag('#22C55E', t('block_firstcol')), tagM = tag('#3b82f6', t('block_middle')), tagL = tag('#38bdf8', t('block_lastcol'));
  const total = el('div'); total.className = 'block-total'; total.innerHTML = `<span class="t">${t('block_total')}</span><span class="v"></span>`;
  legend.append(tagF, tagM, tagL, total); wrap.appendChild(legend);

  function gate() { /* delete's gate lives in deleteConfirm(); count is always ≥1 */ }
  function commit() {
    state.cfg[`${pfx}_block_first_row`] = first;  API('set_cfg', `${pfx}_block_first_row`, first);
    state.cfg[`${pfx}_block_middle_cols`] = mid;  API('set_cfg', `${pfx}_block_middle_cols`, mid);
    state.cfg[`${pfx}_block_last_row`] = last;    API('set_cfg', `${pfx}_block_last_row`, last);
    render();
  }
  function render() {
    fp.arr.forEach((b,i) => { const r=i+1; b.classList.toggle('sel', r===first); b.classList.toggle('inblk', r>=first); });
    lp.arr.forEach((b,i) => { const r=i+1; b.classList.toggle('sel', r===last);  b.classList.toggle('inblk', r<=last); });
    midNum.value = mid;
    midCols.innerHTML = '';
    if (mid === 0) midCols.appendChild(el('span', null, t('block_adjacent'))).className = 'adj';
    else {
      for (let i = 0; i < Math.min(mid, 5); i++) { const c = el('div'); c.className = 'block-midcol'; c.innerHTML = '<i></i><i></i><i></i>'; midCols.appendChild(c); }
      if (mid > 5) midCols.appendChild(el('span', null, '+' + (mid - 5))).className = 'adj';
    }
    const fC = 4 - first, mC = mid * 3, lC = last;
    segF.style.flex = `${fC} 1 0`; segM.style.flex = `${mC} 1 0`; segL.style.flex = `${lC} 1 0`;
    tagF.querySelector('.tv').textContent = fC; tagM.querySelector('.tv').textContent = mC; tagL.querySelector('.tv').textContent = lC;
    total.querySelector('.v').textContent = fC + mC + lC;
  }
  render(); gate();
  return wrap;
}

// ── mastery unlock-path grid editor (4x4) ───────────────────
// Faithful to the design mock: clip-path notched nodes, an animated SVG route
// "trace" (the WASD path the bot drives), S = start, and a Clear button. The
// path is a list of flat 0..15 indices; the backend stores [row, col].
const SVG_NS = 'http://www.w3.org/2000/svg';
const NOTCH  = 'polygon(20% 0, 100% 0, 100% 80%, 80% 100%, 0 100%, 0 20%)';

function routeSeg(a, b) {
  const step = 62, cell = 46, hg = 8;
  const cc = i => { const c = i % 4, r = Math.floor(i / 4); return { c, r, cx: c*step+cell/2, cy: r*step+cell/2 }; };
  const A = cc(a), B = cc(b);
  const aL=A.c*step, aR=aL+cell, aT=A.r*step, aB=aT+cell;
  const bL=B.c*step, bR=bL+cell, bT=B.r*step, bB=bT+cell;
  if (A.r===B.r && Math.abs(A.c-B.c)===1) return A.c<B.c ? [[aR,A.cy],[bL,B.cy]] : [[aL,A.cy],[bR,B.cy]];
  if (A.c===B.c && Math.abs(A.r-B.r)===1) return A.r<B.r ? [[A.cx,aB],[B.cx,bT]] : [[A.cx,aT],[B.cx,bB]];
  const goRight=B.c>A.c, goDown=B.r>A.r;
  if (A.c===B.c) { const side=A.c<3?1:-1, Xs=side>0?aR+hg:aL-hg, aEx=side>0?aR:aL, bEn=side>0?bR:bL; return [[aEx,A.cy],[Xs,A.cy],[Xs,B.cy],[bEn,B.cy]]; }
  if (A.r===B.r) { const side=A.r<3?1:-1, Ys=side>0?aB+hg:aT-hg, aEy=side>0?aB:aT, bEn=side>0?bB:bT; return [[A.cx,aEy],[A.cx,Ys],[B.cx,Ys],[B.cx,bEn]]; }
  const aEx=goRight?aR:aL, Xa=goRight?aR+hg:aL-hg, Yb=goDown?bT-hg:bB+hg, bEn=goDown?bT:bB;
  return [[aEx,A.cy],[Xa,A.cy],[Xa,Yb],[B.cx,Yb],[B.cx,bEn]];
}

function gridEditor(startBtn) {
  let path = [];   // flat indices 0..15, in unlock order
  let presets = [];

  const wrap = el('div', 'background:var(--card);border:1px solid var(--border);border-radius:12px;padding:22px 24px');
  const head = el('div', 'display:flex;align-items:center;gap:10px;margin-bottom:4px');
  const count = el('span', 'font-family:var(--mono);font-size:12px;color:var(--accent-light)', '· 0');
  head.append(el('span', 'font-size:14px;font-weight:600;color:var(--text)', t('grid_title')), count);
  wrap.appendChild(head);
  wrap.appendChild(el('div', 'font-size:12px;color:var(--text2);line-height:1.5;max-width:520px;margin-bottom:18px',
    t('grid_hint')));

  const presetRow = el('div', 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:18px');
  presetRow.appendChild(el('span', 'font-size:12px;color:var(--text2);font-weight:600', t('grid_preset_label')));
  const presetSelect = document.createElement('select');
  presetSelect.style.cssText = 'min-width:230px;background:#0b1422;border:1px solid var(--border);color:var(--text);border-radius:8px;padding:8px 10px;font-size:13px';
  presetRow.appendChild(presetSelect);
  wrap.appendChild(presetRow);

  const board = el('div', 'position:relative;width:232px;height:232px;background-image:radial-gradient(#15293c 1px,transparent 1px);background-size:24.6px 24.6px;background-position:11px 11px');
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('width','232'); svg.setAttribute('height','232'); svg.setAttribute('viewBox','0 0 232 232');
  svg.style.cssText = 'position:absolute;inset:0;pointer-events:none;overflow:visible';
  const cells = el('div', 'position:absolute;inset:0;display:grid;grid-template-columns:repeat(4,46px);grid-auto-rows:46px;gap:16px');
  board.append(svg, cells); wrap.appendChild(board);

  const actions = el('div', 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:16px');
  const clear = el('button', 'background:var(--danger);border:none;color:#fff;border-radius:7px;padding:9px 22px;font-size:13px;font-weight:600;cursor:pointer', t('grid_clear'));
  clear.onclick = () => { path = []; commit(); };
  const savePreset = el('button', 'background:rgba(56,189,248,.14);border:1px solid rgba(56,189,248,.35);color:#7dd3fc;border-radius:7px;padding:9px 16px;font-size:13px;font-weight:600;cursor:pointer', t('grid_save_preset'));
  savePreset.onclick = async () => {
    if (!path.length) { alert(t('grid_preset_empty')); return; }
    const name = (prompt(t('grid_preset_name_prompt')) || '').trim();
    if (!name) return;
    const existing = presets.find(p => (p.name || '').toLowerCase() === name.toLowerCase());
    if (existing && existing.builtin) { alert(t('grid_preset_builtin_name')); return; }
    if (existing && !confirm(t('grid_preset_replace', { name }))) return;
    const result = await API('save_mastery_preset', name, orderOfPath());
    if (!result || result.ok === false) {
      alert((result && result.error) || t('grid_preset_save_failed'));
      return;
    }
    await loadPresets();
  };
  actions.append(clear, savePreset);
  wrap.appendChild(actions);

  function gate() {
    const ok = path.length > 0;
    startBtn.disabled = !ok;
    startBtn.style.opacity = ok ? '' : '.45';
    startBtn.style.cursor = ok ? 'pointer' : 'not-allowed';
  }
  function orderOfPath() { return path.map(i => [Math.floor(i/4), i%4]); }
  function sameOrder(a, b) {
    if (!a || !b || a.length !== b.length) return false;
    for (let i = 0; i < a.length; i++) {
      if (a[i][0] !== b[i][0] || a[i][1] !== b[i][1]) return false;
    }
    return true;
  }
  function setPresetSelection() {
    const cur = orderOfPath();
    const idx = presets.findIndex(p => sameOrder(p.order || [], cur));
    presetSelect.value = idx >= 0 ? String(idx) : '';
  }
  function renderPresets() {
    presetSelect.innerHTML = '';
    const custom = document.createElement('option');
    custom.value = '';
    custom.textContent = t('grid_preset_custom');
    presetSelect.appendChild(custom);
    presets.forEach((preset, i) => {
      const opt = document.createElement('option');
      opt.value = String(i);
      opt.textContent = preset.name || t('grid_preset_unnamed');
      presetSelect.appendChild(opt);
    });
    setPresetSelection();
  }
  async function loadPresets() {
    const data = (await API('get_mastery_presets')) || {};
    presets = Array.isArray(data.presets) ? data.presets : [];
    renderPresets();
  }
  presetSelect.onchange = () => {
    const preset = presets[parseInt(presetSelect.value, 10)];
    if (!preset || !Array.isArray(preset.order)) return;
    path = preset.order.map(([r, c]) => r*4 + c);
    commit();
  };
  function commit() { API('save_grid', orderOfPath()); render(); gate(); setPresetSelection(); }
  function render() {
    count.textContent = '· ' + path.length;
    svg.replaceChildren();
    for (let k = 0; k < path.length - 1; k++) {
      const pl = document.createElementNS(SVG_NS, 'polyline');
      pl.setAttribute('points', routeSeg(path[k], path[k+1]).map(p => p.join(',')).join(' '));
      pl.setAttribute('fill','none'); pl.setAttribute('stroke','#38bdf8'); pl.setAttribute('stroke-width','2');
      pl.setAttribute('stroke-linejoin','round'); pl.setAttribute('stroke-linecap','round'); pl.setAttribute('stroke-dasharray','4 6');
      pl.style.cssText = 'filter:drop-shadow(0 0 5px rgba(56,189,248,.9));animation:dashmove 1s linear infinite';
      svg.appendChild(pl);
    }
    cells.replaceChildren();
    for (let i = 0; i < 16; i++) {
      const order = path.indexOf(i), sel = order !== -1, start = order === 0, last = sel && order === path.length - 1;
      const accent = start ? '#22C55E' : '#38bdf8';
      const b = el('button', null, start ? 'S' : (sel ? String(order + 1) : ''));
      b.style.cssText = 'width:46px;height:46px;cursor:pointer;display:flex;align-items:center;justify-content:center;' +
        'font-family:var(--mono);font-size:13px;font-weight:700;transition:all .15s;clip-path:' + NOTCH + ';border:none;' +
        'background:' + (sel ? (start ? 'rgba(34,197,94,.16)' : 'rgba(56,189,248,.16)') : '#0b1422') + ';' +
        'box-shadow:' + (sel ? 'inset 0 0 0 1.5px ' + accent : 'inset 0 0 0 1px #173043') + ';' +
        'filter:' + (last ? 'drop-shadow(0 0 7px rgba(56,189,248,.85))' : 'none') + ';' +
        'color:' + (sel ? (start ? '#4ade80' : '#7dd3fc') : '#27425e');
      b.onclick = () => { const j = path.indexOf(i); if (j !== -1) path.splice(j, 1); else path.push(i); commit(); };
      cells.appendChild(b);
    }
  }

  Promise.all([API('get_grid'), API('get_mastery_presets')]).then(([g, p]) => {
    if (g && g.order) path = g.order.map(([r, c]) => r*4 + c);
    presets = (p && Array.isArray(p.presets)) ? p.presets : [];
    renderPresets(); render(); gate();
  });
  render(); gate();
  return wrap;
}

// Delete confirmation — lives OUTSIDE the setup panel (between Setup and Start)
// and gates the Start button until checked.
function deleteConfirm(startBtn) {
  let confirmed = false;
  const row = el('label'); row.className = 'confirm-row';
  const box = el('button'); box.className = 'confirm-box';
  const gate = () => { startBtn.disabled = !confirmed; startBtn.style.opacity = confirmed ? '' : '.45';
                       startBtn.style.cursor = confirmed ? 'pointer' : 'not-allowed'; };
  box.onclick = () => { confirmed = !confirmed; box.classList.toggle('on', confirmed);
                        box.textContent = confirmed ? '✓' : ''; gate(); };
  row.appendChild(box);
  const span = el('span', null, t('confirm_delete'));
  span.className = 'ct'; row.appendChild(span);
  gate();
  return row;
}

// ── mode (function-tab) view ─────────────────────────────────
function renderMode(tab) {
  const m = MODES[tab]; if (!m) return;
  document.getElementById('modeKicker').textContent = t('mode_' + tab + '_kicker');
  document.getElementById('modeTitle').textContent = t('mode_' + tab + '_title');
  document.getElementById('modeTagline').textContent = t('mode_' + tab + '_tagline');
  const body = document.getElementById('modeSetupBody'); body.innerHTML = '';
  const startBtn = document.getElementById('modeStart');
  startBtn.disabled = false; startBtn.style.opacity = ''; startBtn.style.cursor = 'pointer';

  if (m.control === 'count' || m.control === 'wheel') body.appendChild(countRow(tab, m));
  if (m.control === 'wheel') {
    body.appendChild(divider());
    body.appendChild(segRow(t('wheel_type_label'), WHEEL_TYPE, 'wheelspin_type', state.cfg.wheelspin_type || 'super'));
    // Duplicates are SOLD by default; two independent keep-exceptions:
    body.appendChild(el('div', 'font-size:13px;color:var(--text2);line-height:1.5', t('dup_sell_note')));
    body.appendChild(checkRow(t('keep_fe'), 'wheelspin_keep_fe', state.cfg.wheelspin_keep_fe !== false));
    body.appendChild(keepPriceRow());
  }
  if (m.control === 'block') body.appendChild(blockSelector(tab, startBtn));
  if (tab === 'mastery') body.appendChild(gridEditor(startBtn));
  const confirmHost = document.getElementById('modeConfirm');
  confirmHost.innerHTML = '';
  if (tab === 'delete') confirmHost.appendChild(deleteConfirm(startBtn));
  if (m.control === 'none') {
    body.appendChild(el('div', 'color:var(--muted);font-size:13px;line-height:1.6', t('coming_soon')));
    startBtn.disabled = true; startBtn.style.opacity = '.45'; startBtn.style.cursor = 'not-allowed';
  }
  startBtn.onclick = async () => {
    if (startBtn.disabled || isRunning) return;
    clearLog();
    if (m.control === 'count' || m.control === 'wheel') {
      const cnt = body.querySelector('.mode-count');
      const v = Math.max(0, parseInt(cnt ? cnt.value : 0, 10) || 0);
      if (cnt) {
        const key = tab + '_count';
        cnt.value = v; state.cfg[key] = v; API('set_cfg', key, v);
      }
      API(m.start, v);
    } else {
      API(m.start);   // block tabs read the count from config
    }
  };
  renderTemplates('modeTplBody', tab);
}

// ── Setup & Templates panel ──────────────────────────────────
function updateTemplatePill(body, tpls) {
  const ready = body.closest('.panel')?.querySelector('.ready-pill');
  if (!ready) return;
  const missing = (tpls || []).some(tpl => tpl.exists === false);
  ready.classList.toggle('missing', missing);
  const label = ready.querySelector('[data-i18n]');
  if (label) label.textContent = t(missing ? 'tpl_missing_pill' : 'ready_pill');
}

async function renderTemplates(bodyId, tab) {
  const body = document.getElementById(bodyId); if (!body) return;
  body.innerHTML = '';
  const tpls = (await API('get_templates', tab)) || [];
  updateTemplatePill(body, tpls);
  if (!tpls.length) {
    body.appendChild(el('div', 'font-size:12px;color:var(--text2);line-height:1.5;max-width:560px;padding-top:14px',
      t('tpl_none')));
    return;
  }
  body.appendChild(el('div', 'font-size:12px;color:var(--text2);margin:14px 0 12px;line-height:1.5;max-width:560px',
    t('tpl_intro')));
  const list = el('div', 'display:flex;flex-direction:column;gap:8px');
  tpls.forEach(tpl => {
    const chip = el('div'); chip.className = 'tpl-chip';
    if (tpl.exists === false) chip.classList.add('missing');
    const dot = el('span'); dot.className = 'dot';
    const name = el('span', null, tpl.name); name.className = 'name';
    const thr = el('span', null, t('tpl_threshold')); thr.className = 'thr';
    const slider = el('input'); slider.className = 'tpl-slider'; slider.type = 'range';
    slider.min = '0.67'; slider.max = '0.95'; slider.step = '0.01'; slider.value = String(tpl.threshold);
    const val = el('span', null, Number(tpl.threshold).toFixed(2)); val.className = 'val';
    slider.oninput = () => { val.textContent = Number(slider.value).toFixed(2); };
    slider.onchange = () => API('set_cfg', 'thresh_' + tpl.name, Number(slider.value));
    chip.append(dot, name, thr, slider, val);
    if (state.dev) {   // recapture is a developer-only action (Settings → Developer)
      const cap = el('button', null, t('tpl_recapture')); cap.className = 'tpl-cap';
      cap.onclick = () => { chip.classList.add('capturing'); cap.textContent = t('tpl_capturing'); API('capture_template', tab, tpl.name); };
      chip.append(cap);
    }
    list.appendChild(chip);
  });
  body.appendChild(list);
}

// Python calls this after a CAPS-LOCK capture finishes/cancels → refresh chips.
window.onCaptureDone = (tab) => {
  if (tab === 'full_auto') renderTemplates('faTplBody', 'full_auto');
  else renderTemplates('modeTplBody', tab);
};

// ── locked / paywall view ────────────────────────────────────
function renderLocked() {
  const grid = document.getElementById('lockedFeatures');
  if (grid) {
    grid.innerHTML = '';
    ['points', 'progress', 'branch', 'bulk', 'license'].forEach(key => {
      const d = el('div', 'display:flex;align-items:flex-start;gap:9px');
      d.innerHTML = `<span style="display:flex;color:#34D778;flex:none;margin-top:1px">${CHECK_SVG}</span>` +
        `<span style="font-size:13.5px;color:#cdd9e5;line-height:1.45">${t('locked_feat_' + key)}</span>`;
      grid.appendChild(d);
    });
  }
  const modes = document.getElementById('lockedModes');
  if (modes) {
    modes.innerHTML = '';
    ['wheelspin', 'money'].forEach(key => {
      const card = el('div', 'locked-mode');
      card.innerHTML = `<div class="locked-mode-title">${t('locked_mode_' + key)}</div>` +
        `<div class="locked-mode-body">${t('locked_mode_' + key + '_body')}</div>`;
      modes.appendChild(card);
    });
  }
  const price = document.getElementById('lockedPrice');
  if (price) {
    price.innerHTML = `<div class="locked-price-main">${t('locked_price')}</div>` +
      `<div class="locked-price-note">${t('locked_price_note')}</div>`;
  }
  const mid = document.getElementById('lockedMachineId');
  if (mid) mid.textContent = t('machine_id') + (state.machineId || '—');
}

// ── settings ─────────────────────────────────────────────────
function makeSwitch(on, onToggle) {
  const b = el('button'); b.className = 'switch' + (on ? ' on' : ''); b.innerHTML = '<span class="knob"></span>';
  b.onclick = () => { const now = !b.classList.contains('on'); b.classList.toggle('on', now); onToggle(now); };
  return b;
}
const SYSTEM_TOGGLES = [
  ['update_check',         'Check for updates',       'Checks GitHub releases at startup. Opens the releases page; never downloads.'],
  ['game_relaunch_enabled','Launch game when needed', 'Starts the game for Race/Full Auto if no game window is detected.'],
  ['car_pass_dlc_owned',   'Own Car Pass DLC',        'Uses the #123 Mad Mike wheelspin route in Full Auto.'],
  ['mute_game',           'Mute game while running', 'Silences the game audio during automation.'],
];  // OCR/debug_detection live under Settings -> Developer (gated by dev mode)
const LAUNCH_PLATFORMS = [
  ['steam', 'launch_path_steam'],
  ['xbox', 'launch_path_xbox'],
  ['custom', 'launch_path_custom'],
];
// (Letterbox auto-crop is decided per-run in GameIO — on only for main-menu-start
//  functions; no user toggle. See gameio.GameIO(crop_letterbox=…).)
// [key, label, hint, lo, hi, step] — per-function timing controls.
// race_check_interval is intentionally absent: fixed at 0.5s default, config-only.
const TIMING = [
  ['race_post_key_wait',       'AFK Races — key interval',           'Pause after each keypress in race nav.',                            0.75, 3.0, 0.05],
  ['mastery_cutscene_wait',    'Driving new car cutscene duration',  'How long the "ride this car" cutscene runs before unlocking.',       0.0, 13.0, 0.5],
  ['mastery_grid_unlock_wait', 'Unlock — per-node interval',         'Pause after each mastery-tree node unlock.',                        1.0, 2.0, 0.25],
  ['menu_tap_wait',            'Menu cursor tap interval',           'Interval after each Up/Down menu tap. Higher helps weak hardware.', 0.1, 0.5, 0.05],
  ['buy_post_key_wait',        'Buy — key interval',                 'Pause between Buy macro keys.',                                     0.4, 3.0, 0.1],
  ['delete_post_key_wait',     'Delete — key interval',              'Pause between Delete macro keys.',                                  0.2, 3.0, 0.1],
  ['wheelspin_post_key_wait',  'Wheelspin — key interval',           'Pause between Wheelspin keys.',                                     0.4, 3.0, 0.1],
];
async function refreshLicense() {
  const s = (await API('license_status')) || {};
  const colors = { licensed:'#34D778', grace_expired:'#F59E0B', invalid:'#FF7A7A', unlicensed:'var(--text2)' };
  const labels = { licensed:t('lic_licensed'), grace_expired:t('lic_grace'), invalid:t('lic_invalid'), unlicensed:t('lic_unlicensed') };
  const c = colors[s.state] || 'var(--text2)';
  const dot = document.getElementById('licDot'), st = document.getElementById('licState');
  dot.style.background = c; st.style.color = c; st.textContent = labels[s.state] || t('lic_unlicensed');
  document.getElementById('licKey').textContent = s.key || '';
  document.getElementById('licMachine').textContent = t('machine_id') + (s.machine_id || '—');
  state.licensed = !!s.allowed;
  syncLicensedChrome();
}
function syncLicensedChrome() {
  const pill = document.getElementById('licPill');
  if (pill) pill.style.display = (state.licensed && !state.comingSoon) ? '' : 'none';
  const active = document.querySelector('#nav a.active[data-view="full_auto"]');
  if (active) showView('full_auto');
}
// [which, configKey, labelKey] — which maps to a backend shortcut on set_shortcut
const SHORTCUTS = [
  ['toggle',  'toggle_key',  'sc_toggle'],
  ['capture', 'capture_key', 'sc_capture'],
  ['report',  'report_key',  'sc_report'],
  ['overlay', 'overlay_key', 'sc_overlay'],
];
// Map a KeyboardEvent to a `keyboard`-lib key name. Esc cancels (returns null).
function keyName(e) {
  const k = e.key;
  if (k === 'Escape') return null;
  if (k === 'CapsLock') return 'caps lock';
  if (k === ' ') return 'space';
  if (/^F\d{1,2}$/.test(k)) return k.toLowerCase();
  return k.toLowerCase();
}
function renderShortcuts() {
  const host = document.getElementById('shortcutGroup'); if (!host) return;
  host.innerHTML = '';
  SHORTCUTS.forEach(([which, cfgKey, lblKey]) => {
    if (which === 'capture' && !state.dev) return;   // capture only used during dev recapture
    const row = el('div'); row.className = 'set-row';
    row.appendChild(el('span', 'font-size:15px;color:var(--text)', t(lblKey)));
    const btn = el('button'); btn.className = 'key-btn';
    const show = () => { btn.textContent = (state.cfg[cfgKey] || '').toUpperCase() || '—'; };
    show();
    btn.onclick = () => {
      btn.classList.add('listening'); btn.textContent = t('sc_press');
      const onKey = (e) => {
        e.preventDefault(); e.stopPropagation();
        window.removeEventListener('keydown', onKey, true);
        btn.classList.remove('listening');
        const name = keyName(e);
        if (name) { state.cfg[cfgKey] = name; API('set_shortcut', which, name); }
        show();
      };
      window.addEventListener('keydown', onKey, true);
    };
    row.appendChild(btn); host.appendChild(row);
  });
}
function renderLaunchPathSettings(host) {
  const row = el('div'); row.className = 'set-row';
  const sub = el('div', 'display:flex;flex-direction:column;gap:3px');
  sub.appendChild(el('span', 'font-size:15px;color:var(--text)', t('launch_path_label')));
  sub.appendChild(el('span', 'font-size:12px;color:var(--text2)', t('launch_path_hint')));
  const sel = document.createElement('select');
  sel.className = 'dropdown accent launch-select';
  LAUNCH_PLATFORMS.forEach(([value, key]) => {
    const opt = document.createElement('option');
    opt.value = value;
    opt.textContent = t(key);
    sel.appendChild(opt);
  });
  const current = ['steam', 'xbox', 'custom'].includes(state.cfg.game_platform)
    ? state.cfg.game_platform : 'steam';
  if (state.cfg.game_platform !== current) {
    state.cfg.game_platform = current;
    API('set_cfg', 'game_platform', current);
  }
  sel.value = current;
  sel.onchange = () => {
    state.cfg.game_platform = sel.value;
    API('set_cfg', 'game_platform', sel.value);
    customRow.style.display = sel.value === 'custom' ? '' : 'none';
  };
  row.append(sub, sel);
  host.appendChild(row);

  const customRow = el('div'); customRow.className = 'set-row launch-custom-row';
  const label = el('div', 'display:flex;flex-direction:column;gap:3px;min-width:180px');
  label.appendChild(el('span', 'font-size:15px;color:var(--text)', t('launch_custom_label')));
  label.appendChild(el('span', 'font-size:12px;color:var(--text2)', t('launch_custom_hint')));
  const pick = el('div'); pick.className = 'launch-pick';
  const input = document.createElement('input');
  input.className = 'lic-input launch-path-input';
  input.value = state.cfg.game_custom_launch || '';
  input.placeholder = t('launch_custom_placeholder');
  input.onchange = () => {
    state.cfg.game_custom_launch = input.value.trim();
    API('set_cfg', 'game_custom_launch', state.cfg.game_custom_launch);
  };
  const browse = document.createElement('button');
  browse.className = 'lic-btn ghost';
  browse.textContent = t('launch_custom_browse');
  browse.onclick = async () => {
    const path = await API('browse_game_custom_launch');
    if (path) {
      input.value = path;
      state.cfg.game_custom_launch = path;
    }
  };
  pick.append(input, browse);
  customRow.append(label, pick);
  customRow.style.display = current === 'custom' ? '' : 'none';
  host.appendChild(customRow);
}
function renderSettings() {
  const lang = document.getElementById('setLang'); lang.value = state.cfg.lang || 'en';
  lang.onchange = async () => { await API('set_cfg', 'lang', lang.value); location.reload(); };  // reload re-renders in the new language
  const tpl = document.getElementById('setTplLang'); tpl.value = state.cfg.template_lang || 'auto';
  tpl.onchange = () => { state.cfg.template_lang = tpl.value; API('set_cfg', 'template_lang', tpl.value); };
  const ov = document.getElementById('setOverlay');
  ov.classList.toggle('on', state.cfg.overlay_enabled !== false);
  ov.onclick = () => { const now = !ov.classList.contains('on'); ov.classList.toggle('on', now); state.cfg.overlay_enabled = now; API('set_overlay_enabled', now); };

  const dev = document.getElementById('setDevMode');
  dev.classList.toggle('on', state.dev);
  const devExtras = document.getElementById('devExtras');
  const syncDevExtras = () => { if (devExtras) devExtras.style.display = state.dev ? '' : 'none'; };
  dev.onclick = () => {
    state.dev = !dev.classList.contains('on'); dev.classList.toggle('on', state.dev);
    state.cfg.dev_mode = state.dev; API('set_cfg', 'dev_mode', state.dev);
    renderShortcuts();                                    // show/hide the Capture row
    renderTemplates('faTplBody', 'full_auto');            // show/hide recapture buttons
    if (state.func && MODES[state.func]) renderTemplates('modeTplBody', state.func);
    syncDevExtras();                                      // show/hide debug-snapshots row
  };
  const dbg = document.getElementById('setDebugSnap');
  if (dbg) {
    dbg.classList.toggle('on', !!state.cfg.debug_detection);
    dbg.onclick = () => { const now = !dbg.classList.contains('on'); dbg.classList.toggle('on', now);
      state.cfg.debug_detection = now; API('set_cfg', 'debug_detection', now); };
  }
  const ocr = document.getElementById('setDevOcr');
  if (ocr) {
    ocr.classList.toggle('on', !!state.cfg.detector_enable_ocr);
    ocr.onclick = () => { const now = !ocr.classList.contains('on'); ocr.classList.toggle('on', now);
      state.cfg.detector_enable_ocr = now; API('set_cfg', 'detector_enable_ocr', now); };
  }
  syncDevExtras();

  const sys = document.getElementById('systemToggles'); sys.innerHTML = '';
  SYSTEM_TOGGLES.forEach(([key]) => {
    const row = el('div'); row.className = 'set-row';
    const sub = el('div', 'display:flex;flex-direction:column;gap:3px');
    sub.appendChild(el('span', 'font-size:15px;color:var(--text)', t('sys_' + key)));
    sub.appendChild(el('span', 'font-size:12px;color:var(--text2)', t('sys_' + key + '_h')));
    row.append(sub, makeSwitch(!!state.cfg[key], (on) => {
      state.cfg[key] = on;
      API('set_cfg', key, on);
      if (key === 'car_pass_dlc_owned') {
        state.cfg.car_pass_dlc_answered = true;
        API('set_cfg', 'car_pass_dlc_answered', true);
        renderFA();
      }
    }));
    sys.appendChild(row);
  });
  renderLaunchPathSettings(sys);

  renderShortcuts();

  const tg = document.getElementById('timingGroup'); tg.innerHTML = '';
  TIMING.forEach(([key, label, hint, lo, hi, step]) => {
    const cur = state.cfg[key] != null ? Number(state.cfg[key]) : lo;
    const row = el('div'); row.className = 'slider-row';
    const head = el('div'); head.className = 'slider-head';
    head.appendChild(el('span', null, t('tm_' + key))).className = 'lbl';
    // editable value — type a number directly; clamped to the slider's floor/ceiling
    const valWrap = el('div'); valWrap.className = 'val';
    const valInp = document.createElement('input');
    valInp.className = 'val-input'; valInp.type = 'text'; valInp.inputMode = 'decimal';
    valInp.value = cur.toFixed(2);
    valWrap.append(valInp, el('span', null, 's'));
    head.appendChild(valWrap); row.appendChild(head);
    row.appendChild(el('span', null, t('tm_' + key + '_h'))).className = 'shint';
    // cutscene: below 11s needs the skip-cutscene mod — warn in red when lowered.
    let warn = null;
    if (key === 'mastery_cutscene_wait') {
      warn = el('div', 'font-size:12px;color:#F87171;font-weight:500;line-height:1.45;margin-top:4px', t('cutscene_warn'));
      row.appendChild(warn);
    }
    const sl = document.createElement('input');
    sl.type = 'range'; sl.className = 'slider'; sl.min = lo; sl.max = hi; sl.step = step; sl.value = cur;
    const syncWarn = () => { if (warn) warn.style.display = Number(sl.value) < 11 ? 'block' : 'none'; };
    const commit = (v) => {
      if (isNaN(v)) v = Number(sl.value);
      v = Math.max(lo, Math.min(hi, v));          // never below the floor (or above the cap)
      sl.value = v; valInp.value = Number(sl.value).toFixed(2);
      state.cfg[key] = Number(sl.value); API('set_cfg', key, Number(sl.value)); syncWarn();
    };
    sl.oninput = () => { valInp.value = Number(sl.value).toFixed(2); syncWarn(); };
    sl.onchange = () => commit(Number(sl.value));
    valInp.onchange = () => commit(parseFloat(valInp.value));     // typed value (blur/Enter)
    valInp.onkeydown = (e) => { if (e.key === 'Enter') valInp.blur(); };
    row.appendChild(sl); tg.appendChild(row); syncWarn();
  });

  const msg = document.getElementById('licMsg'); msg.textContent = '';
  document.getElementById('licActivate').onclick = async () => {
    const k = document.getElementById('licInput').value.trim(); if (!k) return;
    msg.style.color = 'var(--text2)'; msg.textContent = 'Activating…';
    const r = (await API('activate_license', k)) || {};
    msg.style.color = r.ok ? 'var(--ok-text)' : 'var(--warn)'; msg.textContent = r.message || (r.ok ? 'Activated.' : 'Failed.');
    refreshLicense();
  };
  refreshLicense();
}

// ── coming-soon gate (1.9.x teaser — off in 2.0; backend sets coming_soon) ──
function applyComingSoon() {
  const banner = document.getElementById('comingSoonBanner');
  if (!COMING_SOON) {
    if (banner) { banner.hidden = true; banner.style.display = 'none'; }
    return;
  }
  const hide = (id) => { const e = document.getElementById(id); if (e) e.style.display = 'none'; };
  const show = (id) => { const e = document.getElementById(id); if (e) { e.hidden = false; e.style.display = ''; } };
  ['lockedPurchase', 'lockedKeyrow', 'licSection', 'licGroup', 'licPill'].forEach(hide);
  show('comingSoonBanner');
  const desc = document.querySelector('#view-locked [data-i18n="locked_desc"]');
  if (desc) desc.textContent = (t('locked_desc') || '').split('\n\n')[0];
}

// ── routing ──────────────────────────────────────────────────
function showView(view) {
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('active', a.dataset.view === view));
  ['view-full_auto', 'view-mode', 'view-locked', 'view-settings'].forEach(id => { document.getElementById(id).hidden = true; });
  if (view === 'settings') { document.getElementById('view-settings').hidden = false; renderSettings(); }
  else if (view === 'full_auto') {
    const unlocked = state.licensed && !COMING_SOON;
    document.getElementById(unlocked ? 'view-full_auto' : 'view-locked').hidden = false;
  }
  else { document.getElementById('view-mode').hidden = false; renderMode(view); }
  if (view !== 'settings') state.func = view;   // for the How-it-works modal
  API('set_func', view);   // keep the overlay header's function in sync
}

// ── monitors ─────────────────────────────────────────────────
function fillMonitors(sel, monitors, current) {
  if (!sel) return; sel.innerHTML = '';
  (monitors || []).forEach(m => {
    const o = document.createElement('option'); o.value = m.index; o.textContent = `${m.index} — ${m.width}×${m.height}`;
    sel.appendChild(o);
  });
  sel.value = current || 1;
  sel.onchange = () => API('set_cfg', 'monitor_index', parseInt(sel.value, 10));
}

// ── init ─────────────────────────────────────────────────────
let _initData = {};
async function init() {
  _initData = (await API('get_init')) || {};
  state.cfg = _initData.config || {};
  state.dev = state.cfg.dev_mode === true;   // gates template recapture + capture shortcut
  if (_initData.frozen) document.addEventListener('contextmenu', e => e.preventDefault());  // no right-click inspect in release
  // First launch (no config existed) → ask the UI language before anything
  // renders, so a fresh install never silently defaults to English.
  if (_initData.first_run) { showLangPicker(); return; }
  finishInit();
}

// First-run language picker → save the choice, then render. No reload (the
// Python process keeps first_run=true until config exists; applying live avoids
// re-showing the picker), so we apply the language in place.
function showLangPicker() {
  const m = document.getElementById('langPicker');
  setLang(state.cfg.lang || 'en');
  applyI18n(m);
  m.classList.add('open');
  m.querySelectorAll('[data-lang]').forEach(b => b.onclick = async () => {
    const l = b.dataset.lang;
    state.cfg.lang = l;
    await API('set_cfg', 'lang', l);
    await API('set_cfg', 'lang_chosen', true);
    m.classList.remove('open');
    finishInit();
  });
}

function showCarPassPicker() {
  const m = document.getElementById('carPassPicker');
  if (!m) return;
  applyI18n(m);
  m.classList.add('open');
  m.querySelectorAll('[data-car-pass]').forEach(b => b.onclick = async () => {
    const owned = b.dataset.carPass === 'yes';
    state.cfg.car_pass_dlc_owned = owned;
    state.cfg.car_pass_dlc_answered = true;
    await API('set_cfg', 'car_pass_dlc_owned', owned);
    await API('set_cfg', 'car_pass_dlc_answered', true);
    m.classList.remove('open');
    renderFA();
    if (state.func === 'settings') renderSettings();
    runPostSetupStartupTasks();
  });
}

function showLaunchPathPicker() {
  const m = document.getElementById('launchPathPicker');
  if (!m) return false;
  applyI18n(m);
  m.classList.add('open');
  m.querySelectorAll('[data-launch-platform]').forEach(b => b.onclick = async () => {
    const platform = b.dataset.launchPlatform;
    if (platform === 'custom') {
      const path = await API('browse_game_custom_launch');
      if (!path) return;
      state.cfg.game_custom_launch = path;
    }
    state.cfg.game_platform = platform;
    state.cfg.game_launch_path_answered = true;
    await API('set_cfg', 'game_platform', platform);
    await API('set_cfg', 'game_launch_path_answered', true);
    m.classList.remove('open');
    if (showPendingFirstTimePrompt()) return;
    if (state.func === 'settings') renderSettings();
    runPostSetupStartupTasks();
  });
  return true;
}

function showPendingFirstTimePrompt() {
  if (state.cfg.game_launch_path_answered !== true) return showLaunchPathPicker();
  if (state.cfg.car_pass_dlc_answered !== true) { showCarPassPicker(); return true; }
  return false;
}

function runPostSetupStartupTasks() {
  if (state.cfg.update_check !== false) API('check_updates');
}

function finishInit() {
  const data = _initData;
  setLang(state.cfg.lang || 'en');     // pick the UI language before rendering
  applyI18n();                          // translate the static index.html chrome
  state.comingSoon = data.coming_soon === true;
  COMING_SOON = state.comingSoon;
  state.fullAutoBundled = data.full_auto_bundled !== false;
  state.licensed = !!data.licensed;
  state.machineId = data.machine_id || '';
  state.grind  = state.cfg.full_auto_grind_type || 'wheelspin';
  state.branch = state.cfg.full_auto_branch_mode || 'racing';
  state.start  = state.cfg.full_auto_start_from  || 'race';
  document.getElementById('faStart').value = state.start;
  syncLicensedChrome();
  fillMonitors(document.getElementById('monitor'),     data.monitors, state.cfg.monitor_index);
  fillMonitors(document.getElementById('modeMonitor'), data.monitors, state.cfg.monitor_index);
  document.getElementById('faStart').onchange = (e) => API('set_cfg', 'full_auto_start_from', e.target.value);
  const faR = document.getElementById('faRaces');
  faR.value = state.cfg.full_auto_races || 2;
  const commitFARaces = () => {
    const v = Math.max(1, parseInt(faR.value, 10) || 1);
    faR.value = v; state.cfg.full_auto_races = v; API('set_cfg', 'full_auto_races', v);
  };
  faR.oninput = commitFARaces;
  faR.onchange = commitFARaces;
  document.getElementById('nav').addEventListener('click', (e) => {
    const a = e.target.closest('a[data-view]'); if (a) showView(a.dataset.view);
  });
  document.querySelectorAll('.side-btn[data-view]').forEach(b =>
    b.addEventListener('click', () => showView(b.dataset.view)));
  setOverlayUI(state.cfg.overlay_enabled === true);
  document.querySelectorAll('.overlay-btn').forEach(b =>
    b.onclick = async () => setOverlayUI(await API('toggle_overlay')));
  renderFA();
  renderTemplates('faTplBody', 'full_auto');
  renderLocked();
  applyComingSoon();
  showView('full_auto');   // routes to the locked view if unlicensed
  if (showPendingFirstTimePrompt()) return;
  runPostSetupStartupTasks();
}

if (window.pywebview && window.pywebview.api) init();
else window.addEventListener('pywebviewready', init);
