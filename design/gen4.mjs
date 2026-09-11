// Three takes on the classic three-column skill screen: each tree is a tinted
// column, tiles carry a points plate underneath coloured by fill state
// (complete / partial / empty), tree names sit at the bottom, and tiers that
// are not yet available are dimmed. J · Tint (professional), K · Panel
// (middle), L · Vault (stylised).
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
  // a tier is open if it is the first, or the previous tier holds GATE points
  t.open = t.tiers.map((_, i) => i === 0 ? true : sum(t.tiers[i - 1]) >= GATE);
  // the first tree with no points is gated on the previous tree
  t.rootLocked = t.pts === 0;
}
trees[2].open = trees[2].open.map(() => false); // construction waits on approvals
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
const icon = (name, c, sz = 34, w = 1.8) => `<svg width="${sz}" height="${sz}" viewBox="0 0 24 24" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round">${ICONS[name]}</svg>`;
const lockSvg = (c, sz = 14) => `<svg width="${sz}" height="${sz}" viewBox="0 0 16 16"><rect x="3" y="7" width="10" height="7" rx="1" fill="none" stroke="${c}" stroke-width="1.6"></rect><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="${c}" stroke-width="1.6"></path></svg>`;
const userIcon = (c) => `<svg width="18" height="18" viewBox="0 0 16 16"><circle cx="8" cy="5.5" r="3" fill="none" stroke="${c}" stroke-width="1.5"></circle><path d="M2.5 14a5.5 5.5 0 0 1 11 0" fill="none" stroke="${c}" stroke-width="1.5" stroke-linecap="round"></path></svg>`;
const cut = (n) => `clip-path: polygon(0 0, calc(100% - ${n}px) 0, 100% ${n}px, 100% 100%, ${n}px 100%, 0 calc(100% - ${n}px));`;

const COL_W = 424, COL_GAP = 44, TREE_X = 40;

// Generic column builder: styles supply tile(), plate(), tierWrap(), colTop(), colFoot(), colShell()
function column(s, t, xi) {
  const x = xi * (COL_W + COL_GAP);
  const rows = t.tiers.map((tier, i) => {
    const open = t.open[i];
    const have = i === 0 ? null : sum(t.tiers[i - 1]);
    const row = `<div style="display: flex; justify-content: center; gap: ${s.GAP}px">${tier.map((n) => s.tile(n, t, open)).join('')}</div>`;
    return s.tierWrap(row, t, i, open, have);
  }).join('\n');
  return s.colShell(t, `${s.colTop ? s.colTop(t) : ''}\n<div style="display: flex; flex-direction: column; gap: ${s.ROW_GAP}px; padding: ${s.PAD}">${rows}</div>\n${s.colFoot(t)}`, x);
}

function artboard(s) {
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="${s.fonts}">
  <style>
    body { margin: 0; }
    a { color: ${s.link}; } a:hover { color: ${s.fg}; }
  </style>
</helmet>
<div style="position: relative; width: 1440px; height: 820px; overflow: hidden; ${s.frame}">
${s.header()}
<div style="position: absolute; left: ${TREE_X}px; top: ${s.TREE_Y}px; width: ${3 * COL_W + 2 * COL_GAP}px; height: ${820 - s.TREE_Y - 30}px">
${trees.map((t, i) => column(s, t, i)).join('\n')}
</div>
</div>
</x-dc>
</body>
</html>
`;
}

// ---------- J · Tint (professional) ----------
const J = {
  fonts: 'https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap',
  body: "'Manrope', 'Segoe UI', system-ui, sans-serif",
  bg: '#f4f5f7', card: '#ffffff', fg: '#191c21', muted: '#6f7580', line: '#dcdfe5', link: '#2563c9',
  full: '#1f9d55', part: '#e07b1a', empty: '#a4a9b3',
  tint: { green: { bg: '#e9f5ec', fg: '#1f7a43', wm: '#1f9d55' }, blue: { bg: '#e8eff9', fg: '#2453a6', wm: '#3b74d1' }, red: { bg: '#f9ebe8', fg: '#a8382a', wm: '#d1493a' } },
  frame: 'background-color: #f4f5f7;',
  TREE_Y: 132, COL_H: 648, GAP: 14, ROW_GAP: 14, PAD: '16px 16px 6px',
  header() {
    const s = this;
    return `
<div style="display: flex; flex-direction: column; padding: 0 40px; height: 112px; box-sizing: border-box; background: ${s.card}; border-bottom: 1px solid ${s.line}">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 56px">
    <div style="display: flex; align-items: center; gap: 24px">
      <div style="display: flex; align-items: center; gap: 9px; font-family: ${s.body}; font-size: 16px; font-weight: 800; color: ${s.fg}"><svg width="22" height="22" viewBox="0 0 22 22"><rect x="2" y="2" width="5" height="18" rx="1.5" fill="#1f9d55"></rect><rect x="8.5" y="2" width="5" height="18" rx="1.5" fill="#3b74d1"></rect><rect x="15" y="2" width="5" height="18" rx="1.5" fill="#d1493a"></rect></svg>Branchwork</div>
      <div style="display: flex; gap: 2px; padding: 3px; background: ${s.bg}; border-radius: 8px; font-family: ${s.body}; font-size: 13px; font-weight: 600">
        <div style="padding: 5px 12px; border-radius: 6px; color: ${s.fg}; background: ${s.card}; box-shadow: 0 1px 2px rgba(25, 28, 33, 0.08)">Tree</div>
        <div style="padding: 5px 12px; color: ${s.muted}">List</div>
        <div style="padding: 5px 12px; color: ${s.muted}">Timeline</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 12px">
      <div style="padding: 7px 12px; border-radius: 8px; background: ${s.fg}; color: #ffffff; font-family: ${s.body}; font-size: 13px; font-weight: 600">+ New task</div>
      <div style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 999px; background: ${s.bg}">${userIcon(s.muted)}</div>
    </div>
  </div>
  <div style="display: flex; align-items: center; justify-content: space-between; flex-grow: 1; padding-bottom: 12px">
    <div style="font-family: ${s.body}; font-size: 22px; font-weight: 800; color: ${s.fg}; letter-spacing: -0.02em">Office fit-out, Level 3</div>
    <div style="display: flex; align-items: center; gap: 20px; font-family: ${s.body}; font-size: 13px; color: ${s.muted}">
      <div style="display: flex; align-items: center; gap: 8px"><span style="display: inline-block; width: 26px; height: 14px; border-radius: 4px; background: ${s.full}"></span>Complete</div>
      <div style="display: flex; align-items: center; gap: 8px"><span style="display: inline-block; width: 26px; height: 14px; border-radius: 4px; background: ${s.part}"></span>In progress</div>
      <div style="display: flex; align-items: center; gap: 8px"><span style="display: inline-block; width: 26px; height: 14px; border-radius: 4px; box-sizing: border-box; border: 1.5px solid ${s.empty}"></span>Not started</div>
      <div style="display: flex; align-items: center; gap: 10px; margin-left: 12px; font-weight: 700; color: ${s.fg}"><span>${TOTAL_P} / ${TOTAL_M} points</span><span style="display: inline-block; width: 160px; height: 8px; border-radius: 4px; background: ${s.line}; overflow: hidden"><span style="display: block; width: ${Math.round(100 * TOTAL_P / TOTAL_M)}%; height: 100%; background: ${s.full}"></span></span></div>
    </div>
  </div>
</div>`;
  },
  colShell(t, inner, x) {
    const s = this, c = s.tint[t.hue];
    return `<div style="position: absolute; left: ${x}px; top: 0; width: ${COL_W}px; height: ${s.COL_H}px; box-sizing: border-box; display: flex; flex-direction: column; background: ${c.bg}; border-radius: 14px; border: 1px solid ${s.line}; overflow: hidden">
  <svg width="220" height="220" viewBox="0 0 24 24" fill="none" stroke="${c.wm}" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; right: -40px; bottom: 30px; opacity: 0.08">${ICONS[t.wm]}</svg>
  ${inner}
</div>`;
  },
  tierWrap(row, t, i, open, have) {
    const s = this;
    if (open) return `<div style="position: relative">${row}</div>`;
    const reason = i === 0 ? 'Opens when Approvals is complete' : `Needs ${GATE} points in the tier above · ${have}/${GATE}`;
    return `<div style="position: relative; display: flex; flex-direction: column; gap: 8px; padding-top: 8px; border-top: 1px dashed ${s.empty}">
  <div style="display: flex; align-items: center; gap: 6px; font-family: ${s.body}; font-size: 11px; font-weight: 600; color: ${s.muted}">${lockSvg(s.muted, 12)}${reason}</div>
  <div style="opacity: 0.55">${row}</div>
</div>`;
  },
  tile(n, t, open) {
    const s = this, f = fill(n), col = f === 'full' ? s.full : f === 'part' ? s.part : s.empty;
    const plateBg = f === 'empty' ? s.card : col, plateFg = f === 'empty' ? s.muted : '#ffffff';
    return `<div style="width: 96px; display: flex; flex-direction: column; align-items: center; gap: 5px">
  <div style="width: 80px; height: 80px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; border-radius: 12px; background: ${s.card}; border: 2px solid ${f === 'empty' ? s.line : col}; box-shadow: 0 1px 2px rgba(25, 28, 33, 0.06)">${icon(n.i, f === 'empty' ? s.muted : s.fg, 32, 1.7)}</div>
  <div style="width: 80px; box-sizing: border-box; padding: 2px 0; border-radius: 6px; background: ${plateBg}; border: 1.5px solid ${f === 'empty' ? s.line : col}; font-family: ${s.body}; font-size: 12px; font-weight: 800; text-align: center; color: ${plateFg}">${n.p}/${n.m}</div>
  <div style="height: 28px; font-family: ${s.body}; font-size: 11px; font-weight: 600; line-height: 1.2; text-align: center; color: ${s.fg}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
</div>`;
  },
  colFoot(t) {
    const s = this, c = s.tint[t.hue];
    return `<div style="display: flex; align-items: center; justify-content: space-between; padding: 12px 18px 14px; margin-top: auto; border-top: 1px solid rgba(25, 28, 33, 0.08)">
  <span style="font-family: ${s.body}; font-size: 18px; font-weight: 800; letter-spacing: -0.01em; color: ${c.fg}">${esc(t.name)}</span>
  <span style="font-family: ${s.body}; font-size: 13px; font-weight: 700; color: ${c.fg}">${t.pts} / ${t.max} pts</span>
</div>`;
  }
};

// ---------- K · Panel (middle) ----------
const K = {
  fonts: 'https://fonts.googleapis.com/css2?family=Fjalla+One&family=Barlow+Semi+Condensed:wght@500;600;700&display=swap',
  disp: "'Fjalla One', Impact, 'Arial Narrow', sans-serif", body: "'Barlow Semi Condensed', 'Arial Narrow', sans-serif",
  bg: '#101216', fg: '#eceae3', muted: '#8d919b', line: '#2b2f37', black: '#000000', link: '#f0a93a',
  full: '#4ad35f', part: '#f28a1f', empty: '#5a5f6a', tileBg: '#22252b',
  tint: { green: { bg: '#15301c', edge: '#2f7a42', fg: '#5ee36f' }, blue: { bg: '#132542', edge: '#2d5ea3', fg: '#6fa8ff' }, red: { bg: '#3d1612', edge: '#9a3a2c', fg: '#ff6f57' } },
  frame: 'background-color: #101216; background-image: radial-gradient(rgba(236, 234, 227, 0.05) 1px, transparent 1.2px); background-size: 18px 18px;',
  TREE_Y: 118, COL_H: 662, GAP: 12, ROW_GAP: 12, PAD: '14px 14px 4px',
  header() {
    const s = this;
    return `
<div style="display: flex; flex-direction: column; padding: 0 40px; height: 100px; box-sizing: border-box; border-bottom: 2px solid ${s.line}">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 52px">
    <div style="display: flex; align-items: center; gap: 24px">
      <div style="font-family: ${s.disp}; font-size: 22px; letter-spacing: 0.08em; text-transform: uppercase; color: ${s.fg}">Branchwork</div>
      <div style="display: flex; gap: 2px; font-family: ${s.body}; font-size: 15px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase">
        <div style="padding: 5px 14px; background: ${s.fg}; color: ${s.bg}; ${cut(6)}">Tree</div>
        <div style="padding: 5px 14px; color: ${s.muted}">List</div>
        <div style="padding: 5px 14px; color: ${s.muted}">Timeline</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 16px; font-family: ${s.body}; font-size: 14px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: ${s.muted}">
      <div style="padding: 5px 14px; border: 1px solid ${s.fg}; color: ${s.fg}; ${cut(6)}">+ New task</div>
      <div style="display: flex; align-items: center; gap: 8px">${userIcon(s.muted)} Ruben</div>
    </div>
  </div>
  <div style="display: flex; align-items: center; justify-content: space-between; flex-grow: 1; padding-bottom: 8px">
    <div style="font-family: ${s.disp}; font-size: 26px; letter-spacing: 0.04em; text-transform: uppercase; color: ${s.fg}">Office fit-out <span style="color: ${s.muted}">· Level 3</span></div>
    <div style="display: flex; align-items: center; gap: 18px; font-family: ${s.body}; font-size: 13px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: ${s.muted}">
      <span style="display: flex; align-items: center; gap: 6px"><span style="width: 22px; height: 12px; background: ${s.full}"></span>Complete</span>
      <span style="display: flex; align-items: center; gap: 6px"><span style="width: 22px; height: 12px; background: ${s.part}"></span>In progress</span>
      <span style="display: flex; align-items: center; gap: 6px"><span style="width: 22px; height: 12px; box-sizing: border-box; border: 1.5px solid ${s.empty}"></span>Not started</span>
      <span style="margin-left: 8px; font-family: ${s.disp}; font-size: 22px; letter-spacing: 0.04em; color: ${s.fg}">${TOTAL_P}<span style="color: ${s.muted}">/${TOTAL_M}</span></span>
    </div>
  </div>
</div>`;
  },
  colShell(t, inner, x) {
    const s = this, c = s.tint[t.hue];
    return `<div style="position: absolute; left: ${x}px; top: 0; width: ${COL_W}px; height: ${s.COL_H}px; box-sizing: border-box; display: flex; flex-direction: column; background: linear-gradient(180deg, ${c.bg} 0%, #0c0e12 100%); border: 2px solid ${c.edge}; outline: 2px solid ${s.black}; overflow: hidden; ${cut(16)}">
  <svg width="300" height="300" viewBox="0 0 24 24" fill="none" stroke="${c.fg}" stroke-width="0.8" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; right: -60px; top: 40px; opacity: 0.10">${ICONS[t.wm]}</svg>
  ${inner}
</div>`;
  },
  tierWrap(row, t, i, open, have) {
    const s = this;
    if (open) return `<div style="position: relative">${row}</div>`;
    const reason = i === 0 ? 'Locked · finish Approvals' : `Locked · ${have}/${GATE} pts in tier ${i}`;
    return `<div style="position: relative; display: flex; flex-direction: column; gap: 6px; padding: 8px 0 0; border-top: 1px solid rgba(0, 0, 0, 0.6); box-shadow: 0 1px 0 rgba(236, 234, 227, 0.06) inset">
  <div style="display: flex; align-items: center; gap: 6px; font-family: ${s.body}; font-size: 12px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: ${s.muted}">${lockSvg(s.muted, 12)}${reason}</div>
  <div style="opacity: 0.45; filter: saturate(0.2)">${row}</div>
</div>`;
  },
  tile(n, t, open) {
    const s = this, f = fill(n), col = f === 'full' ? s.full : f === 'part' ? s.part : s.empty;
    return `<div style="width: 96px; display: flex; flex-direction: column; align-items: center; gap: 4px">
  <div style="width: 82px; height: 82px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; background: ${s.tileBg}; border: 2px solid ${col}; outline: 2px solid ${s.black}; ${cut(8)}">${icon(n.i, f === 'empty' ? s.muted : s.fg, 36, 1.8)}</div>
  <div style="width: 82px; box-sizing: border-box; padding: 1px 0; background: ${f === 'empty' ? s.black : col}; border: 1.5px solid ${f === 'empty' ? s.empty : s.black}; font-family: ${s.disp}; font-size: 14px; letter-spacing: 0.06em; text-align: center; color: ${f === 'empty' ? s.muted : s.black}; ${cut(5)}">${n.p}/${n.m}</div>
  <div style="height: 28px; margin-top: 2px; font-family: ${s.body}; font-size: 11.5px; font-weight: 600; line-height: 1.15; letter-spacing: 0.04em; text-align: center; text-transform: uppercase; color: ${f === 'empty' ? s.muted : s.fg}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
</div>`;
  },
  colFoot(t) {
    const s = this, c = s.tint[t.hue];
    return `<div style="display: flex; align-items: baseline; justify-content: space-between; padding: 10px 18px 12px; margin-top: auto; background: rgba(0, 0, 0, 0.55); border-top: 2px solid ${c.edge}">
  <span style="font-family: ${s.disp}; font-size: 30px; letter-spacing: 0.08em; text-transform: uppercase; color: ${c.fg}">${esc(t.name)}</span>
  <span style="font-family: ${s.disp}; font-size: 18px; letter-spacing: 0.06em; color: ${s.fg}">${t.pts}<span style="color: ${s.muted}">/${t.max}</span></span>
</div>`;
  }
};

// ---------- L · Vault (stylised) ----------
const L = {
  fonts: 'https://fonts.googleapis.com/css2?family=Russo+One&family=Barlow+Semi+Condensed:wght@600;700&display=swap',
  disp: "'Russo One', Impact, 'Arial Black', sans-serif", body: "'Barlow Semi Condensed', 'Arial Narrow', sans-serif",
  bg: '#0a0b0d', fg: '#f4f1e8', muted: '#8a8e97', black: '#000000', link: '#ffb000',
  full: '#3ee05a', part: '#ff8c1a', empty: '#4c5058', tileBg: '#17191d',
  tint: { green: { bg: '#1d6a2c', bg2: '#0d2e14', edge: '#4be36a', fg: '#5cff7a' }, blue: { bg: '#1c4c9e', bg2: '#0b1f44', edge: '#5aa2ff', fg: '#7dc0ff' }, red: { bg: '#8c2a1c', bg2: '#3a100a', edge: '#ff6a4d', fg: '#ff7a5c' } },
  frame: 'background-color: #0a0b0d; background-image: radial-gradient(rgba(244, 241, 232, 0.09) 1.2px, transparent 1.4px), repeating-linear-gradient(115deg, rgba(0, 0, 0, 0.5) 0 3px, transparent 3px 27px), radial-gradient(ellipse 90% 50% at 50% 110%, rgba(255, 176, 0, 0.12), transparent 70%); background-size: 8px 8px, 100% 100%, 100% 100%;',
  TREE_Y: 118, COL_H: 662, GAP: 10, ROW_GAP: 12, PAD: '14px 12px 4px',
  header() {
    const s = this;
    return `
<div style="display: flex; align-items: center; justify-content: space-between; padding: 0 40px; height: 96px; box-sizing: border-box">
  <div style="display: flex; align-items: center; gap: 26px">
    <div style="font-family: ${s.disp}; font-size: 30px; letter-spacing: 0.04em; text-transform: uppercase; color: ${s.fg}; text-shadow: 3px 3px 0 ${s.black}, 0 0 14px rgba(255, 176, 0, 0.35)">Branchwork</div>
    <div style="display: flex; gap: 6px; font-family: ${s.disp}; font-size: 15px; letter-spacing: 0.08em; text-transform: uppercase">
      <div style="padding: 7px 16px; background: #ffb000; color: ${s.black}; border: 2px solid ${s.black}; box-shadow: 3px 3px 0 ${s.black}; ${cut(7)}">Tree</div>
      <div style="padding: 7px 16px; background: ${s.tileBg}; color: ${s.muted}; border: 2px solid #2b2f37; ${cut(7)}">List</div>
      <div style="padding: 7px 16px; background: ${s.tileBg}; color: ${s.muted}; border: 2px solid #2b2f37; ${cut(7)}">Timeline</div>
    </div>
  </div>
  <div style="display: flex; align-items: center; gap: 22px">
    <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px">
      <div style="font-family: ${s.body}; font-size: 13px; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: ${s.muted}">Office fit-out · Level 3</div>
      <div style="display: flex; align-items: center; gap: 10px"><span style="font-family: ${s.disp}; font-size: 30px; line-height: 1; color: #ffb000; text-shadow: 2px 2px 0 ${s.black}">${TOTAL_P}<span style="font-size: 18px; color: ${s.fg}">/${TOTAL_M} PTS</span></span><span style="display: flex; gap: 2px; padding: 3px; background: ${s.black}; border: 2px solid #2b2f37">${Array.from({ length: 21 }, (_, i) => `<span style="display: block; width: 6px; height: 14px; background: ${i < Math.round(21 * TOTAL_P / TOTAL_M) ? '#ffb000' : '#22252b'}"></span>`).join('')}</span></div>
    </div>
    <div style="padding: 8px 16px; background: ${s.tileBg}; color: ${s.fg}; border: 2px solid ${s.fg}; box-shadow: 3px 3px 0 ${s.black}; font-family: ${s.disp}; font-size: 15px; letter-spacing: 0.08em; text-transform: uppercase; ${cut(7)}">+ New task</div>
  </div>
</div>`;
  },
  colShell(t, inner, x) {
    const s = this, c = s.tint[t.hue];
    return `<div style="position: absolute; left: ${x}px; top: 0; width: ${COL_W}px; height: ${s.COL_H}px; box-sizing: border-box; display: flex; flex-direction: column; background: linear-gradient(180deg, ${c.bg} 0%, ${c.bg2} 55%, #070809 100%); border: 3px solid ${s.black}; box-shadow: 0 0 0 2px ${c.edge}, 6px 6px 0 ${s.black}; overflow: hidden; ${cut(18)}">
  <div style="position: absolute; inset: 0; background-image: repeating-linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0 2px, transparent 2px 12px)"></div>
  <svg width="340" height="340" viewBox="0 0 24 24" fill="none" stroke="${s.fg}" stroke-width="0.9" stroke-linecap="round" stroke-linejoin="round" style="position: absolute; left: -70px; top: 20px; opacity: 0.12; transform: rotate(-12deg)">${ICONS[t.wm]}</svg>
  ${inner}
</div>`;
  },
  tierWrap(row, t, i, open, have) {
    const s = this;
    if (open) return `<div style="position: relative">${row}</div>`;
    const reason = i === 0 ? 'Locked · finish Approvals' : `Locked · ${have}/${GATE} pts`;
    return `<div style="position: relative; display: flex; flex-direction: column; gap: 6px; padding: 8px 0 0; background: linear-gradient(180deg, rgba(0, 0, 0, 0.55), rgba(0, 0, 0, 0.75)); border-top: 3px solid ${s.black}; margin: 0 -12px; padding-left: 12px; padding-right: 12px">
  <div style="display: flex; align-items: center; justify-content: center; gap: 8px; font-family: ${s.disp}; font-size: 13px; letter-spacing: 0.16em; text-transform: uppercase; color: ${s.muted}">${lockSvg(s.muted, 13)}${reason}</div>
  <div style="opacity: 0.4; filter: saturate(0)">${row}</div>
</div>`;
  },
  tile(n, t, open) {
    const s = this, f = fill(n), col = f === 'full' ? s.full : f === 'part' ? s.part : s.empty;
    const glow = f === 'full' ? `box-shadow: 0 0 0 2px ${s.black}, 0 0 14px rgba(62, 224, 90, 0.55);` : f === 'part' ? `box-shadow: 0 0 0 2px ${s.black}, 0 0 14px rgba(255, 140, 26, 0.55);` : `box-shadow: 0 0 0 2px ${s.black};`;
    return `<div style="width: 96px; display: flex; flex-direction: column; align-items: center; gap: 0">
  <div style="width: 84px; height: 84px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle at 50% 35%, #2a2e35, ${s.tileBg} 70%); border: 3px solid ${col}; ${glow} ${cut(10)}">${icon(n.i, f === 'empty' ? s.muted : s.fg, 40, 2.2)}</div>
  <div style="width: 66px; margin-top: -3px; box-sizing: border-box; padding: 2px 0 1px; background: ${f === 'empty' ? s.tileBg : col}; border: 2px solid ${s.black}; font-family: ${s.disp}; font-size: 13px; letter-spacing: 0.06em; text-align: center; color: ${f === 'empty' ? s.muted : s.black}; ${cut(5)}">${n.p}/${n.m}</div>
  <div style="height: 28px; margin-top: 5px; font-family: ${s.body}; font-size: 11.5px; font-weight: 700; line-height: 1.15; letter-spacing: 0.05em; text-align: center; text-transform: uppercase; color: ${f === 'empty' ? s.muted : s.fg}; text-shadow: 1px 1px 0 ${s.black}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
</div>`;
  },
  colFoot(t) {
    const s = this, c = s.tint[t.hue];
    return `<div style="position: relative; display: flex; align-items: center; justify-content: space-between; padding: 10px 18px 12px; margin-top: auto; background: ${s.black}; border-top: 3px solid ${c.edge}">
  <span style="font-family: ${s.disp}; font-size: 34px; line-height: 1; letter-spacing: 0.06em; text-transform: uppercase; color: ${c.fg}; text-shadow: 0 0 16px ${c.edge}">${esc(t.name)}</span>
  <span style="padding: 4px 10px; background: ${c.edge}; color: ${s.black}; font-family: ${s.disp}; font-size: 16px; letter-spacing: 0.06em; ${cut(5)}">${t.pts}/${t.max}</span>
</div>`;
  }
};

writeFileSync(new URL('./Tint.dc.html', import.meta.url), artboard(J));
writeFileSync(new URL('./Panel.dc.html', import.meta.url), artboard(K));
writeFileSync(new URL('./Vault.dc.html', import.meta.url), artboard(L));

const cpath = new URL('./canvas.json', import.meta.url);
const canvas = JSON.parse(readFileSync(cpath, 'utf8'));
const mine = ['Tint.dc.html', 'Panel.dc.html', 'Vault.dc.html'];
canvas.artboards = canvas.artboards.filter((a) => !mine.includes(a.file));
canvas.annotations = (canvas.annotations || []).filter((a) => !['j-note', 'k-note', 'l-note', 'row5'].includes(a.id));
const Y = 4320;
canvas.artboards.push(
  { file: 'Tint.dc.html', title: 'J · Tint', x: 0, y: Y, w: 1440, h: 820 },
  { file: 'Panel.dc.html', title: 'K · Panel', x: 1560, y: Y, w: 1440, h: 820 },
  { file: 'Vault.dc.html', title: 'L · Vault', x: 3120, y: Y, w: 1440, h: 820 }
);
canvas.annotations.push(
  { id: 'row5', x: -420, y: Y, w: 360, text: 'Row 5: three levels built on the three-column skill screen from the reference.\n\nWhat carries over: one tinted column per tree (green, blue, red), icon tiles with a points plate underneath coloured by fill (green complete, orange partial, grey empty), tree names along the bottom, and tiers that are not yet available dimmed inside the column. Tiles, icons and panels are drawn fresh.' },
  { id: 'j-note', x: 0, y: Y - 150, w: 520, text: 'J · Tint (professional). Light UI; each tree is a softly tinted rounded column with a faint watermark, white icon tiles, colour-coded points plates, a dashed rule and a plain reason line where a tier is locked.\nFor: the reference’s reading order in a calm product skin.\nTrade-off: the tints are subtle, so the three trees rely on the footer label to tell apart.' },
  { id: 'k-note', x: 1560, y: Y - 150, w: 520, text: 'K · Panel (middle). Dark, cut-corner columns in deep green / blue / red with a black outline, dark tiles with a black inner ring, chunky points plates, big condensed tree names at the foot, locked tiers greyed and desaturated.\nFor: closest to the reference’s feel while staying legible with labels.\nTrade-off: dark-only; three saturated hues plus two state colours is a lot of colour to manage.' },
  { id: 'l-note', x: 3120, y: Y - 150, w: 520, text: 'L · Vault (stylised). Saturated tinted columns with hard black frames and offset shadows, halftone and scratch overlays, glowing tile borders, footer names lit in their tree colour, locked tiers sunk into a dark band.\nFor: the loudest, most game-like take of the set.\nTrade-off: the glow and textures fight small labels; best with fewer, chunkier tasks per tier.' }
);
writeFileSync(cpath, JSON.stringify(canvas, null, 2));
console.log('wrote Tint.dc.html, Panel.dc.html, Vault.dc.html; canvas.json updated');
