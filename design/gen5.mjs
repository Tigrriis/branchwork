// The chosen direction: dark theme, the calm structure of J · Tint with the
// tinted columns of K · Panel. Writes Main.dc.html (tree view) and
// Login.dc.html, and reorganises canvas.json into two pages: the deliverable
// and the explorations.
import { writeFileSync, readFileSync } from 'node:fs';

const trees = [
  { name: 'Design', hue: 'green', wm: 'pencil', tiers: [
    [ { l: 'Brief & survey', p: 3, m: 3, i: 'doc' }, { l: 'Concept layouts', p: 2, m: 2, i: 'layout' }, { l: 'Detailed drawings', p: 2, m: 4, i: 'pencil' } ],
    [ { l: 'Site measure-up', p: 1, m: 1, i: 'ruler' }, { l: 'Client brief signed', p: 1, m: 1, i: 'sign' }, { l: 'Option A / B review', p: 2, m: 2, i: 'flag' } ],
    [ { l: 'Services coordination', p: 0, m: 2, i: 'wrench' }, { l: 'Issue for tender', p: 0, m: 1, i: 'list' } ] ] },
  { name: 'Approvals', hue: 'blue', wm: 'seal', tiers: [
    [ { l: 'Landlord consent', p: 1, m: 1, i: 'key' }, { l: 'Building permit', p: 2, m: 3, i: 'seal' } ],
    [ { l: 'Fire engineering report', p: 2, m: 2, i: 'fire' }, { l: 'Certifier lodgement', p: 0, m: 1, i: 'calendar' } ] ] },
  { name: 'Construction', hue: 'red', wm: 'hardhat', tiers: [
    [ { l: 'Tender & award', p: 0, m: 3, i: 'list' }, { l: 'Site works', p: 0, m: 5, i: 'hardhat' }, { l: 'Handover', p: 0, m: 2, i: 'home' } ],
    [ { l: 'Shortlist contractors', p: 0, m: 2, i: 'users' }, { l: 'Award contract', p: 0, m: 1, i: 'trophy' }, { l: 'Demolition', p: 0, m: 2, i: 'hammer' } ],
    [ { l: 'Fit-out & services', p: 0, m: 4, i: 'truck' } ] ] }
];
const GATE = 3;
const sum = (a) => a.reduce((t, n) => t + n.p, 0);
for (const t of trees) {
  t.pts = t.tiers.flat().reduce((a, n) => a + n.p, 0); t.max = t.tiers.flat().reduce((a, n) => a + n.m, 0);
  t.open = t.tiers.map((_, i) => i === 0 ? true : sum(t.tiers[i - 1]) >= GATE);
}
trees[2].open = trees[2].open.map(() => false);
const TOTAL_P = trees.reduce((a, t) => a + t.pts, 0), TOTAL_M = trees.reduce((a, t) => a + t.max, 0);
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
const fill = (n) => n.p === 0 ? 'empty' : n.p >= n.m ? 'full' : 'part';

const ICONS = {
  doc: '<path d="M6 3h8l5 5v13H6z"></path><path d="M14 3v5h5M9 13h7M9 17h7"></path>',
  layout: '<rect x="3" y="3" width="18" height="18" rx="1"></rect><path d="M3 10h18M10 10v11"></path>',
  pencil: '<path d="M4 20l4-1L19 8l-3-3L5 16z"></path><path d="M13 7l3 3"></path>',
  ruler: '<rect x="2" y="9" width="20" height="7" rx="1"></rect><path d="M6 9v3M10 9v3M14 9v3M18 9v3"></path>',
  sign: '<path d="M3 17c3-7 6-7 7 0s4 6 7-3"></path><path d="M3 21h18"></path>',
  flag: '<path d="M5 21V4M5 4h13l-3 4 3 4H5"></path>',
  wrench: '<path d="M14 6a4 4 0 0 0-5 5l-5 5 4 4 5-5a4 4 0 0 0 5-5l-3 3-2-2z"></path>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h1M3 12h1M3 18h1"></path>',
  key: '<circle cx="8" cy="12" r="4"></circle><path d="M12 12h9M18 12v3M15 12v2"></path>',
  seal: '<circle cx="12" cy="9" r="5"></circle><path d="M8 13l-1 8 5-3 5 3-1-8"></path>',
  fire: '<path d="M12 3c1 4 5 5 5 10a5 5 0 0 1-10 0c0-3 2-4 2-6 1 1 2 2 3 1z"></path>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="1"></rect><path d="M3 10h18M8 3v4M16 3v4"></path>',
  hardhat: '<path d="M4 15a8 8 0 0 1 16 0"></path><path d="M2 15h20M12 7v3"></path>',
  home: '<path d="M3 11l9-7 9 7M6 10v10h12V10"></path>',
  users: '<circle cx="9" cy="8" r="3"></circle><path d="M3 20a6 6 0 0 1 12 0M16 4a3 3 0 0 1 0 6M21 20a6 6 0 0 0-5-5.9"></path>',
  trophy: '<path d="M7 4h10v5a5 5 0 0 1-10 0z"></path><path d="M7 6H4v2a3 3 0 0 0 3 3M17 6h3v2a3 3 0 0 1-3 3M12 14v4M8 21h8"></path>',
  hammer: '<path d="M14 4l6 6-3 3-6-6z"></path><path d="M11 7l-7 7 3 3 7-7"></path>',
  truck: '<path d="M3 17V7h11v10M14 11h4l3 3v3"></path><circle cx="7" cy="18" r="2"></circle><circle cx="17" cy="18" r="2"></circle>'
};
const icon = (name, c, sz = 32, w = 1.7) => `<svg width="${sz}" height="${sz}" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
const lockSvg = (c, sz = 12) => `<svg width="${sz}" height="${sz}" viewBox="0 0 16 16"><rect x="3" y="7" width="10" height="7" rx="1" fill="none" stroke="${c}" stroke-width="1.6"></rect><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="${c}" stroke-width="1.6"></path></svg>`;
const userIcon = (c) => `<svg width="18" height="18" viewBox="0 0 16 16"><circle cx="8" cy="5.5" r="3" fill="none" stroke="${c}" stroke-width="1.5"></circle><path d="M2.5 14a5.5 5.5 0 0 1 11 0" fill="none" stroke="${c}" stroke-width="1.5" stroke-linecap="round"></path></svg>`;
const logo = () => `<svg width="22" height="22" viewBox="0 0 22 22"><rect x="2" y="2" width="5" height="18" rx="1.5" fill="#3fcf63"></rect><rect x="8.5" y="2" width="5" height="18" rx="1.5" fill="#5b8def"></rect><rect x="15" y="2" width="5" height="18" rx="1.5" fill="#f0684e"></rect></svg>`;

// ---------- tokens (these become static/branchwork/theme.css) ----------
const T = {
  font: "'Manrope', 'Segoe UI', system-ui, sans-serif",
  bg: '#15181d', card: '#1b1f25', card2: '#232830', fg: '#eceae2', fg2: '#d6d4cc', muted: '#8b909a', line: '#2a2f38', line2: '#3a404b',
  full: '#3fcf63', part: '#f0932b', empty: '#3a404b', accent: '#3fcf63', link: '#8fb8ff',
  tint: {
    green: { bg: '#182a1f', edge: '#2f5a3c', fg: '#7ee39a', wm: '#3fcf63' },
    blue: { bg: '#18243a', edge: '#2f4a7a', fg: '#8fb8ff', wm: '#5b8def' },
    red: { bg: '#2e1d1a', edge: '#6b3a31', fg: '#ff9a86', wm: '#f0684e' }
  }
};
const COL_W = 424, COL_GAP = 44, TREE_X = 40, TREE_Y = 132, COL_H = 648;

function header() {
  return `
<div style="display: flex; flex-direction: column; padding: 0 40px; height: 112px; box-sizing: border-box; background: ${T.card}; border-bottom: 1px solid ${T.line}">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 56px">
    <div style="display: flex; align-items: center; gap: 24px">
      <div style="display: flex; align-items: center; gap: 9px; font-family: ${T.font}; font-size: 16px; font-weight: 800; color: ${T.fg}">${logo()}Branchwork</div>
      <div style="display: flex; gap: 2px; padding: 3px; background: ${T.bg}; border-radius: 8px; font-family: ${T.font}; font-size: 13px; font-weight: 600">
        <div style="padding: 5px 12px; border-radius: 6px; color: ${T.fg}; background: ${T.card2}">Tree</div>
        <div style="padding: 5px 12px; color: ${T.muted}">List</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 12px">
      <div style="padding: 7px 12px; border-radius: 8px; background: ${T.full}; color: #101215; font-family: ${T.font}; font-size: 13px; font-weight: 700">+ New task</div>
      <div style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 999px; background: ${T.card2}">${userIcon(T.muted)}</div>
    </div>
  </div>
  <div style="display: flex; align-items: center; justify-content: space-between; flex-grow: 1; padding-bottom: 12px">
    <div style="display: flex; align-items: baseline; gap: 12px"><span style="font-family: ${T.font}; font-size: 22px; font-weight: 800; color: ${T.fg}; letter-spacing: -0.02em">Office fit-out, Level 3</span><span style="font-family: ${T.font}; font-size: 13px; color: ${T.muted}">Project 2026-014</span></div>
    <div style="display: flex; align-items: center; gap: 20px; font-family: ${T.font}; font-size: 13px; color: ${T.muted}">
      <div style="display: flex; align-items: center; gap: 8px"><span style="display: inline-block; width: 26px; height: 14px; border-radius: 4px; background: ${T.full}"></span>Complete</div>
      <div style="display: flex; align-items: center; gap: 8px"><span style="display: inline-block; width: 26px; height: 14px; border-radius: 4px; background: ${T.part}"></span>In progress</div>
      <div style="display: flex; align-items: center; gap: 8px"><span style="display: inline-block; width: 26px; height: 14px; border-radius: 4px; box-sizing: border-box; border: 1.5px solid ${T.line2}"></span>Not started</div>
      <div style="display: flex; align-items: center; gap: 10px; margin-left: 12px; font-weight: 700; color: ${T.fg}"><span>${TOTAL_P} / ${TOTAL_M} points</span><span style="display: inline-block; width: 160px; height: 8px; border-radius: 4px; background: ${T.line2}; overflow: hidden"><span style="display: block; width: ${Math.round(100 * TOTAL_P / TOTAL_M)}%; height: 100%; background: ${T.full}"></span></span></div>
    </div>
  </div>
</div>`;
}

function tile(n) {
  const f = fill(n), col = f === 'full' ? T.full : f === 'part' ? T.part : T.empty;
  const plateBg = f === 'empty' ? T.card : col, plateFg = f === 'empty' ? T.muted : '#101215';
  return `<div style="width: 96px; display: flex; flex-direction: column; align-items: center; gap: 5px">
  <div style="width: 80px; height: 80px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; border-radius: 12px; background: ${T.card2}; border: 2px solid ${col}">${icon(n.i, f === 'empty' ? T.muted : T.fg)}</div>
  <div style="width: 80px; box-sizing: border-box; padding: 2px 0; border-radius: 6px; background: ${plateBg}; border: 1.5px solid ${f === 'empty' ? T.line2 : col}; font-family: ${T.font}; font-size: 12px; font-weight: 800; text-align: center; color: ${plateFg}">${n.p}/${n.m}</div>
  <div style="height: 28px; font-family: ${T.font}; font-size: 11px; font-weight: 600; line-height: 1.2; text-align: center; color: ${f === 'empty' ? T.muted : T.fg2}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
</div>`;
}

function tierWrap(row, i, open, have) {
  if (open) return `<div style="position: relative">${row}</div>`;
  const reason = i === 0 ? 'Opens when Approvals is complete' : `Needs ${GATE} points in the tier above · ${have}/${GATE}`;
  return `<div style="position: relative; display: flex; flex-direction: column; gap: 8px; padding-top: 8px; border-top: 1px dashed ${T.line2}">
  <div style="display: flex; align-items: center; gap: 6px; font-family: ${T.font}; font-size: 11px; font-weight: 600; color: ${T.muted}">${lockSvg(T.muted)}${reason}</div>
  <div style="opacity: 0.45">${row}</div>
</div>`;
}

function column(t, xi) {
  const c = T.tint[t.hue], x = xi * (COL_W + COL_GAP);
  const rows = t.tiers.map((tier, i) => tierWrap(`<div style="display: flex; justify-content: center; gap: 14px">${tier.map(tile).join('')}</div>`, i, t.open[i], i === 0 ? null : sum(t.tiers[i - 1]))).join('\n');
  return `<div style="position: absolute; left: ${x}px; top: 0; width: ${COL_W}px; height: ${COL_H}px; box-sizing: border-box; display: flex; flex-direction: column; background: ${c.bg}; border-radius: 14px; border: 1px solid ${c.edge}; overflow: hidden">
  <svg width="220" height="220" viewBox="0 0 24 24" fill="none" stroke="${c.wm}" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; right: -40px; bottom: 30px; opacity: 0.07">${ICONS[t.wm]}</svg>
  <div style="display: flex; flex-direction: column; gap: 14px; padding: 16px 16px 6px">${rows}</div>
  <div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 18px 14px; margin-top: auto; border-top: 1px solid ${c.edge}">
    <span style="font-family: ${T.font}; font-size: 18px; font-weight: 800; letter-spacing: -0.01em; color: ${c.fg}">${esc(t.name)}</span>
    <span style="font-family: ${T.font}; font-size: 13px; font-weight: 700; color: ${c.fg}">${t.pts} / ${t.max} pts</span>
  </div>
</div>`;
}

const shell = (inner) => `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap">
  <style>
    body { margin: 0; }
    a { color: ${T.link}; } a:hover { color: ${T.fg}; }
  </style>
</helmet>
<div style="position: relative; width: 1440px; height: 820px; overflow: hidden; background-color: ${T.bg}">
${inner}
</div>
</x-dc>
</body>
</html>
`;

const main = shell(`${header()}
<div style="position: absolute; left: ${TREE_X}px; top: ${TREE_Y}px; width: ${3 * COL_W + 2 * COL_GAP}px; height: ${COL_H}px">
${trees.map(column).join('\n')}
</div>`);

const field = (label, placeholder) => `<div style="display: flex; flex-direction: column; gap: 6px">
  <label style="font-family: ${T.font}; font-size: 12px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: ${T.muted}">${label}</label>
  <div style="height: 44px; box-sizing: border-box; display: flex; align-items: center; padding: 0 14px; border-radius: 8px; background: ${T.bg}; border: 1px solid ${T.line2}; font-family: ${T.font}; font-size: 14px; color: ${T.muted}">${placeholder}</div>
</div>`;

const login = shell(`
<div style="position: absolute; inset: 0; display: flex; align-items: center; justify-content: center">
  <div style="width: 400px; box-sizing: border-box; display: flex; flex-direction: column; gap: 22px; padding: 32px; border-radius: 16px; background: ${T.card}; border: 1px solid ${T.line}">
    <div style="display: flex; flex-direction: column; gap: 14px">
      <div style="display: flex; align-items: center; gap: 9px; font-family: ${T.font}; font-size: 16px; font-weight: 800; color: ${T.fg}">${logo()}Branchwork</div>
      <div style="display: flex; flex-direction: column; gap: 4px">
        <div style="font-family: ${T.font}; font-size: 24px; font-weight: 800; letter-spacing: -0.02em; color: ${T.fg}">Sign in</div>
        <div style="font-family: ${T.font}; font-size: 14px; color: ${T.muted}">Plan the tree, tick the branches.</div>
      </div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 14px">
      ${field('Email', 'you@example.com')}
      ${field('Password', '••••••••••')}
    </div>
    <div style="height: 44px; display: flex; align-items: center; justify-content: center; border-radius: 8px; background: ${T.full}; color: #101215; font-family: ${T.font}; font-size: 14px; font-weight: 800">Sign in</div>
    <div style="display: flex; justify-content: space-between; font-family: ${T.font}; font-size: 13px; color: ${T.muted}"><span>New here? <a href="#" style="color: ${T.link}; text-decoration: none; font-weight: 600">Create an account</a></span><a href="#" style="color: ${T.link}; text-decoration: none; font-weight: 600">Forgot password</a></div>
  </div>
</div>`);

writeFileSync(new URL('./Main.dc.html', import.meta.url), main);
writeFileSync(new URL('./Login.dc.html', import.meta.url), login);

// canvas: page 1 = the deliverable, page 2 = explorations
const cpath = new URL('./canvas.json', import.meta.url);
const canvas = JSON.parse(readFileSync(cpath, 'utf8'));
const mine = ['Main.dc.html', 'Login.dc.html'];
canvas.artboards = canvas.artboards.filter((a) => !mine.includes(a.file)).map((a) => ({ ...a, page: 'page-2' }));
canvas.annotations = (canvas.annotations || []).filter((a) => !['final', 'login-note'].includes(a.id)).map((a) => ({ ...a, page: 'page-2' }));
canvas.pages = [{ id: 'page-1', name: 'Branchwork' }, { id: 'page-2', name: 'Explorations' }];
canvas.artboards.unshift(
  { file: 'Main.dc.html', title: 'Tree view', x: 0, y: 0, w: 1440, h: 820, page: 'page-1' },
  { file: 'Login.dc.html', title: 'Sign in', x: 1560, y: 0, w: 1440, h: 820, page: 'page-1' }
);
canvas.annotations.unshift(
  { id: 'final', x: -420, y: 0, w: 360, page: 'page-1', text: 'Chosen direction: dark theme, between J · Tint and K · Panel.\n\nTint’s calm structure (rounded columns, one sans, dashed rules and a plain reason line for locked tiers, legend + points bar in the header) on Panel’s dark ground with muted per-tree tints. Complete = green, in progress = orange, not started = grey.\n\nThese tokens are the app’s theme.css. Explorations A–L are on the second page.' }
);
canvas.launch = { view: 'canvas', page: 'page-1' };
writeFileSync(cpath, JSON.stringify(canvas, null, 2));
console.log('wrote Main.dc.html, Login.dc.html; canvas.json now has 2 pages');
