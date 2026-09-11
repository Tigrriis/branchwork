// Two takes modelled on looter-shooter skill-tree screens: square skill tiles
// with a corner points counter, tree header plates, tier lines with unlock
// requirements. H · Plate (middle) and I · Grit (stylised, with a project card rail).
import { writeFileSync, readFileSync } from 'node:fs';

const trees = [
  { name: 'Design', tiers: [
    [ { l: 'Brief & survey', s: 'done', p: 3, m: 3, i: 'doc' }, { l: 'Concept layouts', s: 'done', p: 2, m: 2, i: 'layout' }, { l: 'Detailed drawings', s: 'active', p: 2, m: 4, i: 'pencil' } ],
    [ { l: 'Site measure-up', s: 'done', p: 1, m: 1, i: 'ruler' }, { l: 'Client brief signed', s: 'done', p: 1, m: 1, i: 'sign' }, { l: 'Option A / B review', s: 'done', p: 2, m: 2, i: 'flag' } ],
    [ { l: 'Services coordination', s: 'todo', p: 0, m: 2, i: 'wrench' }, { l: 'Issue for tender', s: 'todo', p: 0, m: 1, i: 'list' } ] ] },
  { name: 'Approvals', tiers: [
    [ { l: 'Landlord consent', s: 'done', p: 1, m: 1, i: 'key' }, { l: 'Building permit', s: 'active', p: 2, m: 3, i: 'seal' } ],
    [ { l: 'Fire engineering report', s: 'done', p: 2, m: 2, i: 'fire' }, { l: 'Certifier lodgement', s: 'todo', p: 0, m: 1, i: 'calendar' } ] ] },
  { name: 'Construction', tiers: [
    [ { l: 'Tender & award', s: 'locked', p: 0, m: 3, i: 'list' }, { l: 'Site works', s: 'locked', p: 0, m: 5, i: 'hardhat' }, { l: 'Handover', s: 'locked', p: 0, m: 2, i: 'home' } ],
    [ { l: 'Shortlist contractors', s: 'locked', p: 0, m: 2, i: 'users' }, { l: 'Award contract', s: 'locked', p: 0, m: 1, i: 'trophy' }, { l: 'Demolition', s: 'locked', p: 0, m: 2, i: 'hammer' } ],
    [ { l: 'Fit-out & services', s: 'locked', p: 0, m: 4, i: 'truck' } ] ] }
];
const GATE = 3;
const sum = (a) => a.reduce((t, n) => t + n.p, 0);
for (const t of trees) { t.pts = t.tiers.flat().reduce((a, n) => a + n.p, 0); t.max = t.tiers.flat().reduce((a, n) => a + n.m, 0); }
const TOTAL_P = trees.reduce((a, t) => a + t.pts, 0), TOTAL_M = trees.reduce((a, t) => a + t.max, 0);
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

// ---------- icon set (24px stroke grid) ----------
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

// ---------- H · Plate ----------
const H = {
  fonts: 'https://fonts.googleapis.com/css2?family=Anton&family=Barlow+Condensed:wght@500;600;700&display=swap',
  disp: "'Anton', Impact, 'Arial Narrow', sans-serif", body: "'Barlow Condensed', 'Arial Narrow', sans-serif",
  bg: '#14161a', panel: '#1c1f24', panel2: '#23262c', fg: '#e9e6dd', muted: '#8b909a', line: '#3a3f48', black: '#0a0b0d', yellow: '#f3b23a', link: '#f3b23a',
  frame: 'background-color: #14161a; background-image: radial-gradient(rgba(233, 230, 221, 0.06) 1px, transparent 1.2px); background-size: 22px 22px;',
  TILE: 100, GAP: 14, COL_W: 424, COL_GAP: 44, TREE_X: 40, TREE_Y: 176,
  header() {
    const s = this;
    return `
<div style="display: flex; flex-direction: column; padding: 0 40px; height: 150px; box-sizing: border-box">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 52px; border-bottom: 1px solid ${s.line}">
    <div style="display: flex; align-items: center; gap: 26px">
      <div style="font-family: ${s.disp}; font-size: 22px; letter-spacing: 0.08em; color: ${s.yellow}; text-transform: uppercase">Branchwork</div>
      <div style="display: flex; gap: 2px; font-family: ${s.body}; font-size: 15px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase">
        <div style="padding: 6px 16px; background: ${s.yellow}; color: ${s.black}; ${cut(6)}">Tree</div>
        <div style="padding: 6px 16px; color: ${s.muted}">List</div>
        <div style="padding: 6px 16px; color: ${s.muted}">Timeline</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 18px; font-family: ${s.body}; font-size: 14px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: ${s.muted}">
      <div style="padding: 6px 14px; border: 1px solid ${s.yellow}; color: ${s.yellow}; ${cut(6)}">+ New task</div>
      <div style="display: flex; align-items: center; gap: 8px">${userIcon(s.muted)} Ruben</div>
    </div>
  </div>
  <div style="display: flex; align-items: flex-end; justify-content: space-between; flex-grow: 1; padding: 12px 0 14px">
    <div style="display: flex; flex-direction: column; gap: 2px">
      <div style="font-family: ${s.body}; font-size: 13px; font-weight: 600; letter-spacing: 0.16em; text-transform: uppercase; color: ${s.muted}">Project 2026-014 &nbsp;·&nbsp; Level 3</div>
      <div style="font-family: ${s.disp}; font-size: 36px; line-height: 1; letter-spacing: 0.04em; text-transform: uppercase; color: ${s.fg}">Office fit-out</div>
    </div>
    <div style="display: flex; align-items: stretch; gap: 2px">
      <div style="display: flex; flex-direction: column; justify-content: center; padding: 6px 18px; background: ${s.panel2}; ${cut(8)}">
        <div style="font-family: ${s.body}; font-size: 12px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: ${s.muted}">Points earned</div>
        <div style="font-family: ${s.disp}; font-size: 30px; line-height: 1; color: ${s.fg}">${TOTAL_P}<span style="color: ${s.muted}; font-size: 18px"> / ${TOTAL_M}</span></div>
      </div>
      <div style="display: flex; flex-direction: column; justify-content: center; padding: 6px 18px; background: ${s.yellow}; ${cut(8)}">
        <div style="font-family: ${s.body}; font-size: 12px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: ${s.black}">Remaining</div>
        <div style="font-family: ${s.disp}; font-size: 30px; line-height: 1; color: ${s.black}">${TOTAL_M - TOTAL_P}</div>
      </div>
    </div>
  </div>
</div>`;
  },
  colHead(t) {
    const s = this, lit = t.pts > 0;
    return `<div style="display: flex; align-items: center; justify-content: space-between; height: 48px; box-sizing: border-box; padding: 0 14px 0 16px; background: ${s.panel2}; border-bottom: 2px solid ${lit ? s.yellow : s.line}; ${cut(10)}">
  <span style="font-family: ${s.disp}; font-size: 22px; letter-spacing: 0.06em; text-transform: uppercase; color: ${lit ? s.yellow : s.muted}">${esc(t.name)}</span>
  <span style="padding: 2px 8px; background: ${s.black}; font-family: ${s.body}; font-size: 15px; font-weight: 700; letter-spacing: 0.06em; color: ${lit ? s.fg : s.muted}">${t.pts} / ${t.max}</span>
</div>`;
  },
  tile(n) {
    const s = this, st = n.s, done = st === 'done', act = st === 'active', lk = st === 'locked';
    const border = done ? s.yellow : act ? s.fg : lk ? '#23262c' : s.line;
    const ic = done ? s.yellow : act ? s.fg : lk ? '#3a3f48' : s.muted;
    const boxBg = done ? s.yellow : s.black, boxFg = done ? s.black : act ? s.yellow : lk ? '#3a3f48' : s.muted;
    return `<div style="width: ${s.TILE}px; display: flex; flex-direction: column; align-items: center; gap: 6px">
  <div style="position: relative; width: ${s.TILE}px; height: ${s.TILE}px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; background: ${lk ? '#101215' : s.panel}; border: 2px solid ${border}; outline: 1px solid ${s.black}; outline-offset: -4px">
    ${icon(n.i, ic)}
    ${lk ? `<div style="position: absolute; left: 6px; top: 6px">${lockSvg('#3a3f48', 13)}</div>` : ''}
    <div style="position: absolute; right: -2px; bottom: -2px; min-width: 30px; box-sizing: border-box; padding: 1px 5px; background: ${boxBg}; border: 1px solid ${done ? s.yellow : s.line}; font-family: ${s.body}; font-size: 13px; font-weight: 700; text-align: center; color: ${boxFg}">${n.p}/${n.m}</div>
  </div>
  <div style="height: 28px; font-family: ${s.body}; font-size: 12px; font-weight: 600; line-height: 1.15; letter-spacing: 0.06em; text-align: center; text-transform: uppercase; color: ${lk ? '#4a4f58' : done || act ? s.fg : s.muted}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
</div>`;
  },
  gate(no, open, have) {
    const s = this;
    return `<div style="display: flex; align-items: center; gap: 10px; height: 20px; font-family: ${s.body}; font-size: 12px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; color: ${open ? s.yellow : s.muted}">
  <span style="display: flex; align-items: center; gap: 6px">${open ? '' : lockSvg(s.muted, 12)}Tier ${no}</span><div style="flex-grow: 1; height: 1px; background: ${open ? s.yellow : s.line}; opacity: ${open ? 0.6 : 1}"></div><span>${open ? 'Open' : `${have} / ${GATE} pts to unlock`}</span>
</div>`;
  },
  column(t, xi) {
    const s = this, x = xi * (s.COL_W + s.COL_GAP), parts = [s.colHead(t)];
    t.tiers.forEach((tier, i) => {
      if (i > 0) { const have = sum(t.tiers[i - 1]); parts.push(s.gate(i + 1, have >= GATE, have)); }
      parts.push(`<div style="display: flex; justify-content: center; gap: ${s.GAP}px">${tier.map((n) => s.tile(n)).join('')}</div>`);
    });
    return `<div style="position: absolute; left: ${x}px; top: 0; width: ${s.COL_W}px; display: flex; flex-direction: column; gap: 12px">\n${parts.join('\n')}\n</div>`;
  },
  body_() {
    const s = this;
    return `<div style="position: absolute; left: ${s.TREE_X}px; top: ${s.TREE_Y}px; width: ${3 * s.COL_W + 2 * s.COL_GAP}px; height: 620px">\n${trees.map((t, i) => s.column(t, i)).join('\n')}\n</div>`;
  }
};

// ---------- I · Grit ----------
const I = {
  fonts: 'https://fonts.googleapis.com/css2?family=Teko:wght@500;600;700&family=Saira+Condensed:wght@500;600;700&display=swap',
  disp: "'Teko', Impact, 'Arial Narrow', sans-serif", body: "'Saira Condensed', 'Arial Narrow', sans-serif",
  bg: '#0e0f12', panel: '#181a1f', bevel: '#5d626c', fg: '#f1eee6', muted: '#8f939c', line: '#2e323a', black: '#000000', yellow: '#f5b623', orange: '#f07a12', ice: '#9fe8ff', link: '#f5b623',
  frame: 'background-color: #0e0f12; background-image: radial-gradient(ellipse 80% 60% at 50% 100%, rgba(240, 122, 18, 0.10), transparent 70%), repeating-linear-gradient(115deg, rgba(241, 238, 230, 0.045) 0 1px, transparent 1px 9px), repeating-linear-gradient(25deg, rgba(0, 0, 0, 0.35) 0 2px, transparent 2px 31px); background-size: 100% 100%, 100% 100%, 100% 100%;',
  TILE: 96, GAP: 12, RAIL_W: 300, COL_W: 330, COL_GAP: 20, TREE_X: 372, TREE_Y: 96,
  header() {
    const s = this;
    return `
<div style="display: flex; align-items: center; justify-content: space-between; padding: 0 40px; height: 64px; box-sizing: border-box; border-bottom: 2px solid ${s.line}">
  <div style="display: flex; align-items: center; gap: 28px">
    <div style="font-family: ${s.disp}; font-size: 32px; font-weight: 700; line-height: 1; letter-spacing: 0.06em; text-transform: uppercase; color: ${s.yellow}; text-shadow: 0 0 12px rgba(245, 182, 35, 0.45)">Branchwork</div>
    <div style="display: flex; gap: 6px; font-family: ${s.disp}; font-size: 24px; font-weight: 600; line-height: 1; letter-spacing: 0.1em; text-transform: uppercase">
      <div style="padding: 8px 18px 4px; background: ${s.yellow}; color: ${s.black}; ${cut(7)}">Tree</div>
      <div style="padding: 8px 18px 4px; color: ${s.muted}; border: 1px solid ${s.line}; ${cut(7)}">List</div>
      <div style="padding: 8px 18px 4px; color: ${s.muted}; border: 1px solid ${s.line}; ${cut(7)}">Timeline</div>
    </div>
  </div>
  <div style="display: flex; align-items: center; gap: 16px">
    <div style="padding: 8px 18px 4px; background: ${s.orange}; color: ${s.black}; font-family: ${s.disp}; font-size: 24px; font-weight: 600; line-height: 1; letter-spacing: 0.1em; text-transform: uppercase; ${cut(7)}">+ New task</div>
    <div style="display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; background: ${s.panel}; border: 2px solid ${s.bevel}; ${cut(6)}">${userIcon(s.fg)}</div>
  </div>
</div>`;
  },
  rail() {
    const s = this;
    const rows = trees.map((t) => `<div style="display: flex; flex-direction: column; gap: 5px">
      <div style="display: flex; justify-content: space-between; font-family: ${s.body}; font-size: 14px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: ${t.pts > 0 ? s.fg : s.muted}"><span>${esc(t.name)}</span><span style="color: ${t.pts > 0 ? s.yellow : s.muted}">${t.pts}/${t.max}</span></div>
      <div style="display: flex; gap: 2px">${Array.from({ length: t.max }, (_, i) => `<div style="flex-grow: 1; height: 8px; background: ${i < t.pts ? s.yellow : s.line}; box-sizing: border-box; border: 1px solid ${s.black}"></div>`).join('')}</div>
    </div>`).join('');
    return `<div style="position: absolute; left: 40px; top: ${s.TREE_Y}px; width: ${s.RAIL_W}px; box-sizing: border-box; display: flex; flex-direction: column; background: ${s.panel}; border: 2px solid ${s.bevel}; outline: 2px solid ${s.black}; ${cut(14)}">
  <div style="display: flex; align-items: center; justify-content: space-between; padding: 10px 16px 6px; background: ${s.yellow}; ${cut(12)}">
    <div style="display: flex; flex-direction: column">
      <div style="font-family: ${s.body}; font-size: 12px; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: ${s.black}">Project 2026-014</div>
      <div style="font-family: ${s.disp}; font-size: 34px; font-weight: 700; line-height: 0.95; letter-spacing: 0.03em; text-transform: uppercase; color: ${s.black}">Office fit-out</div>
    </div>
    <div style="display: flex; flex-direction: column; align-items: center; padding: 4px 10px 0; background: ${s.black}; color: ${s.yellow}; font-family: ${s.disp}; line-height: 0.9"><span style="font-size: 12px; letter-spacing: 0.2em">LVL</span><span style="font-size: 30px; font-weight: 700">3</span></div>
  </div>
  <div style="display: flex; flex-direction: column; gap: 6px; padding: 16px 16px 12px; border-bottom: 1px solid ${s.line}">
    <div style="font-family: ${s.body}; font-size: 13px; font-weight: 700; letter-spacing: 0.18em; text-transform: uppercase; color: ${s.muted}">Points available</div>
    <div style="display: flex; align-items: baseline; gap: 10px"><span style="font-family: ${s.disp}; font-size: 64px; font-weight: 700; line-height: 0.85; color: ${s.yellow}; text-shadow: 0 0 18px rgba(245, 182, 35, 0.5)">${TOTAL_M - TOTAL_P}</span><span style="font-family: ${s.body}; font-size: 15px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: ${s.muted}">${TOTAL_P} of ${TOTAL_M} earned</span></div>
    <div style="display: flex; height: 16px; box-sizing: border-box; border: 2px solid ${s.bevel}; background: ${s.black}; padding: 2px; margin-top: 4px"><div style="width: ${Math.round(100 * TOTAL_P / TOTAL_M)}%; background: linear-gradient(90deg, ${s.orange}, ${s.yellow})"></div></div>
  </div>
  <div style="display: flex; flex-direction: column; gap: 14px; padding: 14px 16px 16px">${rows}</div>
  <div style="display: flex; flex-direction: column; gap: 4px; padding: 12px 16px 14px; border-top: 1px solid ${s.line}; font-family: ${s.body}; font-size: 13px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: ${s.muted}">
    <div style="display: flex; justify-content: space-between"><span>Next unlock</span><span style="color: ${s.ice}">Construction · Tier 1</span></div>
    <div style="display: flex; justify-content: space-between"><span>Needs</span><span style="color: ${s.fg}">Detailed drawings 4/4</span></div>
  </div>
</div>`;
  },
  colHead(t) {
    const s = this, lit = t.pts > 0;
    return `<div style="display: flex; align-items: center; justify-content: space-between; height: 46px; box-sizing: border-box; padding: 4px 12px 0 14px; background: ${lit ? s.yellow : s.panel}; border: 2px solid ${lit ? s.black : s.bevel}; ${cut(10)}">
  <span style="font-family: ${s.disp}; font-size: 30px; font-weight: 700; line-height: 1; letter-spacing: 0.05em; text-transform: uppercase; color: ${lit ? s.black : s.muted}">${esc(t.name)}</span>
  <span style="padding: 3px 8px 0; background: ${s.black}; font-family: ${s.disp}; font-size: 22px; font-weight: 600; line-height: 1; letter-spacing: 0.06em; color: ${lit ? s.yellow : s.muted}">${t.pts}/${t.max}</span>
</div>`;
  },
  tile(n) {
    const s = this, st = n.s, done = st === 'done', act = st === 'active', lk = st === 'locked';
    const bg = done ? `radial-gradient(circle at 50% 40%, ${s.yellow}, ${s.orange})` : lk ? '#0b0c0f' : s.panel;
    const outer = done ? s.yellow : act ? s.ice : lk ? '#2a2d34' : s.bevel;
    const glow = done ? `box-shadow: 0 0 16px rgba(245, 182, 35, 0.55);` : act ? `box-shadow: 0 0 14px rgba(159, 232, 255, 0.45);` : '';
    const ic = done ? s.black : act ? s.fg : lk ? '#2e323a' : s.muted;
    const hatch = lk ? `background-image: repeating-linear-gradient(45deg, rgba(255, 255, 255, 0.05) 0 2px, transparent 2px 8px);` : '';
    return `<div style="width: ${s.TILE}px; display: flex; flex-direction: column; align-items: center; gap: 6px">
  <div style="position: relative; width: ${s.TILE}px; height: ${s.TILE}px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; background: ${bg}; ${hatch} border: 3px solid ${outer}; outline: 2px solid ${s.black}; outline-offset: -5px; ${glow}">
    ${icon(n.i, ic, 36, 2)}
    ${lk ? `<div style="position: absolute; left: 7px; top: 7px">${lockSvg('#4a4f58', 13)}</div>` : ''}
    <div style="position: absolute; right: -4px; bottom: -6px; min-width: 32px; box-sizing: border-box; padding: 3px 6px 0; background: ${done || act ? s.yellow : s.black}; border: 2px solid ${s.black}; font-family: ${s.disp}; font-size: 18px; font-weight: 700; line-height: 1; text-align: center; color: ${done || act ? s.black : lk ? '#4a4f58' : s.muted}; ${cut(4)}">${n.p}/${n.m}</div>
  </div>
  <div style="height: 30px; margin-top: 4px; font-family: ${s.body}; font-size: 12.5px; font-weight: 700; line-height: 1.15; letter-spacing: 0.06em; text-align: center; text-transform: uppercase; color: ${lk ? '#4a4f58' : done ? s.yellow : act ? s.ice : s.muted}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
</div>`;
  },
  gate(no, open, have) {
    const s = this, c = open ? s.yellow : s.muted;
    return `<div style="display: flex; align-items: center; gap: 10px; height: 22px; font-family: ${s.disp}; font-size: 19px; font-weight: 600; line-height: 1; letter-spacing: 0.12em; text-transform: uppercase; color: ${c}">
  <svg width="12" height="12" viewBox="0 0 12 12"><path d="M6 0l6 6-6 6-6-6z" fill="${c}"></path></svg><span style="padding-top: 3px; display: flex; align-items: center; gap: 6px">${open ? '' : lockSvg(s.muted, 13)}Tier ${no}</span>
  <div style="flex-grow: 1; display: flex; flex-direction: column; gap: 2px"><div style="height: 1px; background: ${c}; opacity: 0.8"></div><div style="height: 1px; background: ${c}; opacity: 0.35"></div></div>
  <span style="padding-top: 3px">${open ? 'Unlocked' : `Requires ${GATE} pts · ${have}/${GATE}`}</span>
</div>`;
  },
  column(t, xi) {
    const s = this, x = xi * (s.COL_W + s.COL_GAP), parts = [s.colHead(t)];
    t.tiers.forEach((tier, i) => {
      if (i > 0) { const have = sum(t.tiers[i - 1]); parts.push(s.gate(i + 1, have >= GATE, have)); }
      parts.push(`<div style="display: flex; justify-content: center; gap: ${s.GAP}px">${tier.map((n) => s.tile(n)).join('')}</div>`);
    });
    return `<div style="position: absolute; left: ${x}px; top: 0; width: ${s.COL_W}px; display: flex; flex-direction: column; gap: 14px">\n${parts.join('\n')}\n</div>`;
  },
  body_() {
    const s = this;
    return `${s.rail()}\n<div style="position: absolute; left: ${s.TREE_X}px; top: ${s.TREE_Y}px; width: ${3 * s.COL_W + 2 * s.COL_GAP}px; height: 700px">\n${trees.map((t, i) => s.column(t, i)).join('\n')}\n</div>`;
  }
};

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
${s.body_()}
</div>
</x-dc>
</body>
</html>
`;
}

writeFileSync(new URL('./Plate.dc.html', import.meta.url), artboard(H));
writeFileSync(new URL('./Grit.dc.html', import.meta.url), artboard(I));

const cpath = new URL('./canvas.json', import.meta.url);
const canvas = JSON.parse(readFileSync(cpath, 'utf8'));
const mine = ['Plate.dc.html', 'Grit.dc.html'];
canvas.artboards = canvas.artboards.filter((a) => !mine.includes(a.file));
canvas.annotations = (canvas.annotations || []).filter((a) => !['h-note', 'i-note', 'row4'].includes(a.id));
const Y = 3240;
canvas.artboards.push(
  { file: 'Plate.dc.html', title: 'H · Plate', x: 0, y: Y, w: 1440, h: 820 },
  { file: 'Grit.dc.html', title: 'I · Grit', x: 1560, y: Y, w: 1440, h: 820 }
);
canvas.annotations.push(
  { id: 'row4', x: -420, y: Y, w: 360, text: 'Row 4: two takes modelled more closely on looter-shooter skill screens.\n\nSquare skill tiles with a points counter in the corner, a header plate per tree, tier lines that state the unlock requirement, and (in I) a character-style project card with points available. Icons and panels are drawn fresh; the structure is the homage.' },
  { id: 'h-note', x: 0, y: Y - 150, w: 520, text: 'H · Plate (middle). Dark plate UI, cut-corner panels, amber accent, square icon tiles with a corner points box, hairline tier rules. Anton headings.\nFor: unmistakably that genre, but calm enough for daily use; icons carry recognition at a glance.\nTrade-off: needs an icon per task type in the real app (a picker or auto-assign).' },
  { id: 'i-note', x: 1560, y: Y - 150, w: 520, text: 'I · Grit (stylised). Scratched black ground, bevelled double-frame tiles, glowing amber for done and ice-blue for in progress, yellow header plates, and a project card rail with points available and next unlock.\nFor: the full screen-in-a-game feel; the rail turns the project into a character sheet.\nTrade-off: the rail costs width, so tiles are 96px and long labels wrap tight.' }
);
writeFileSync(cpath, JSON.stringify(canvas, null, 2));
console.log('wrote Plate.dc.html, Grit.dc.html; canvas.json updated');
