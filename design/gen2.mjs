// Three tiered "skill tree" takes (columns + tier gates + point pips), from
// professional to stylised. Appends to the canvas.json written by gen.mjs.
import { writeFileSync, readFileSync } from 'node:fs';

// ---------- data: three trees, each with tiers of skills ----------
// state: done | active | todo | locked   pts/max: points allocated
const trees = [
  { name: 'Design', tiers: [
    [ { l: 'Brief & survey', s: 'done', p: 3, m: 3 }, { l: 'Concept layouts', s: 'done', p: 2, m: 2 }, { l: 'Detailed drawings', s: 'active', p: 2, m: 4 } ],
    [ { l: 'Site measure-up', s: 'done', p: 1, m: 1 }, { l: 'Client brief signed', s: 'done', p: 1, m: 1 }, { l: 'Option A / B review', s: 'done', p: 2, m: 2 } ],
    [ { l: 'Services coordination', s: 'todo', p: 0, m: 2 }, { l: 'Issue for tender', s: 'todo', p: 0, m: 1 } ] ] },
  { name: 'Approvals', tiers: [
    [ { l: 'Landlord consent', s: 'done', p: 1, m: 1 }, { l: 'Building permit', s: 'active', p: 2, m: 3 } ],
    [ { l: 'Fire engineering report', s: 'done', p: 2, m: 2 }, { l: 'Certifier lodgement', s: 'todo', p: 0, m: 1 } ] ] },
  { name: 'Construction', tiers: [
    [ { l: 'Tender & award', s: 'locked', p: 0, m: 3 }, { l: 'Site works', s: 'locked', p: 0, m: 5 }, { l: 'Handover', s: 'locked', p: 0, m: 2 } ],
    [ { l: 'Shortlist contractors', s: 'locked', p: 0, m: 2 }, { l: 'Award contract', s: 'locked', p: 0, m: 1 }, { l: 'Demolition', s: 'locked', p: 0, m: 2 } ],
    [ { l: 'Fit-out & services', s: 'locked', p: 0, m: 4 } ] ] }
];
const GATE = 3; // points needed in a tier to open the next
const sum = (a, k) => a.reduce((t, n) => t + n[k], 0);
for (const t of trees) { t.pts = t.tiers.flat().reduce((a, n) => a + n.p, 0); t.max = t.tiers.flat().reduce((a, n) => a + n.m, 0); }
const TOTAL_P = trees.reduce((a, t) => a + t.pts, 0), TOTAL_M = trees.reduce((a, t) => a + t.max, 0);

// ---------- shared geometry ----------
const COL_W = 424, COL_GAP = 44, TILE_W = 128, TILE_H = 100, TILE_GAP = 12, HEAD_H = 60, GATE_H = 34, ROW_GAP = 14;
const TREE_X = 40, TREE_Y = 196;
const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

const lockSvg = (c, sz = 18) => `<svg width="${sz}" height="${sz}" viewBox="0 0 16 16"><rect x="3" y="7" width="10" height="7" rx="1.5" fill="none" stroke="${c}" stroke-width="1.6"></rect><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="${c}" stroke-width="1.6"></path></svg>`;
const userIcon = (c) => `<svg width="18" height="18" viewBox="0 0 16 16"><circle cx="8" cy="5.5" r="3" fill="none" stroke="${c}" stroke-width="1.5"></circle><path d="M2.5 14a5.5 5.5 0 0 1 11 0" fill="none" stroke="${c}" stroke-width="1.5" stroke-linecap="round"></path></svg>`;
const plusIcon = (c) => `<svg width="14" height="14" viewBox="0 0 16 16"><path d="M8 3v10M3 8h10" fill="none" stroke="${c}" stroke-width="1.8" stroke-linecap="round"></path></svg>`;
// state glyphs on a 24px grid: tick, half diamond, outline diamond, lock
const glyph = (st, s) => {
  const c = st === 'done' ? s.gDone : st === 'active' ? s.gActive : st === 'todo' ? s.gTodo : s.gLocked;
  if (st === 'locked') return lockSvg(c, 22);
  if (st === 'done') return `<svg width="22" height="22" viewBox="0 0 24 24"><path d="M12 2l10 10-10 10L2 12z" fill="${c}"></path><path d="M7.5 12.5l3 3 6-7" fill="none" stroke="${s.gTick}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"></path></svg>`;
  if (st === 'active') return `<svg width="22" height="22" viewBox="0 0 24 24"><path d="M12 2l10 10-10 10L2 12z" fill="none" stroke="${c}" stroke-width="2"></path><path d="M12 2L2 12l10 10z" fill="${c}"></path></svg>`;
  return `<svg width="22" height="22" viewBox="0 0 24 24"><path d="M12 2l10 10-10 10L2 12z" fill="none" stroke="${c}" stroke-width="2"></path></svg>`;
};

// ---------- styles ----------
const styles = {
  // E · Tiered: the structure only, in a sober light product UI.
  Tiered: {
    fonts: 'https://fonts.googleapis.com/css2?family=Archivo:wght@500;600;700&family=Archivo+Narrow:wght@500;600&display=swap',
    body: "'Archivo', 'Segoe UI', system-ui, sans-serif", cond: "'Archivo Narrow', 'Arial Narrow', sans-serif",
    bg: '#f2f3f5', card: '#ffffff', fg: '#1b1e24', muted: '#6c7280', line: '#d6d9df', ink: '#2f5bd6', inkSoft: '#e6ecfb', warn: '#c9791a', warnSoft: '#fbefdc', link: '#2f5bd6',
    gDone: '#2f5bd6', gActive: '#c9791a', gTodo: '#9aa0ab', gLocked: '#b3b8c2', gTick: '#ffffff',
    frameStyle: 'background-color: #f2f3f5;',
    header(s) {
      return `
<div style="display: flex; flex-direction: column; padding: 0 40px; height: 160px; box-sizing: border-box; background: ${s.card}; border-bottom: 1px solid ${s.line}">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 58px; border-bottom: 1px solid ${s.line}">
    <div style="display: flex; align-items: center; gap: 24px">
      <div style="display: flex; align-items: center; gap: 9px; font-family: ${s.body}; font-size: 16px; font-weight: 700; color: ${s.fg}"><svg width="22" height="22" viewBox="0 0 22 22"><rect x="2" y="2" width="8" height="8" rx="2" fill="${s.ink}"></rect><rect x="12" y="2" width="8" height="8" rx="2" fill="${s.ink}"></rect><rect x="2" y="12" width="8" height="8" rx="2" fill="${s.ink}"></rect><rect x="12" y="12" width="8" height="8" rx="2" fill="none" stroke="${s.ink}" stroke-width="1.6"></rect></svg>Branchwork</div>
      <div style="display: flex; gap: 20px; font-family: ${s.body}; font-size: 13px; font-weight: 500; color: ${s.muted}"><span style="color: ${s.fg}; border-bottom: 2px solid ${s.ink}; padding: 19px 0">Tree</span><span style="padding: 19px 0">List</span><span style="padding: 19px 0">Timeline</span></div>
    </div>
    <div style="display: flex; align-items: center; gap: 12px">
      <div style="display: flex; align-items: center; gap: 6px; padding: 7px 12px; border-radius: 6px; background: ${s.ink}; color: #ffffff; font-family: ${s.body}; font-size: 13px; font-weight: 600">${plusIcon('#ffffff')} New task</div>
      <div style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 999px; background: ${s.inkSoft}">${userIcon(s.ink)}</div>
    </div>
  </div>
  <div style="display: flex; align-items: center; justify-content: space-between; flex-grow: 1; padding: 4px 0 12px">
    <div style="display: flex; flex-direction: column; gap: 4px">
      <div style="font-family: ${s.body}; font-size: 12px; color: ${s.muted}">Projects &nbsp;/&nbsp; Office fit-out</div>
      <div style="font-family: ${s.body}; font-size: 26px; font-weight: 700; color: ${s.fg}; letter-spacing: -0.02em">Office fit-out, Level 3</div>
    </div>
    <div style="display: flex; align-items: center; gap: 32px">
      <div style="display: flex; flex-direction: column; gap: 6px; width: 260px">
        <div style="display: flex; justify-content: space-between; font-family: ${s.body}; font-size: 12px; color: ${s.muted}"><span>Points earned</span><span style="font-family: ${s.cond}; font-size: 14px; font-weight: 600; color: ${s.fg}">${TOTAL_P} / ${TOTAL_M}</span></div>
        <div style="height: 8px; border-radius: 4px; background: ${s.line}; overflow: hidden"><div style="width: ${Math.round(100 * TOTAL_P / TOTAL_M)}%; height: 100%; background: ${s.ink}"></div></div>
      </div>
      <div style="display: flex; gap: 6px; font-family: ${s.body}; font-size: 12px; font-weight: 500">
        <div style="display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 6px; background: ${s.inkSoft}; color: ${s.ink}">Done</div>
        <div style="display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 6px; background: ${s.warnSoft}; color: ${s.warn}">In progress</div>
        <div style="display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 6px; background: ${s.card}; color: ${s.muted}; border: 1px solid ${s.line}">Open</div>
        <div style="display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 6px; background: ${s.bg}; color: ${s.muted}">${lockSvg(s.muted, 12)} Gated</div>
      </div>
    </div>
  </div>
</div>`;
    },
    colHead(t, s) {
      const pct = Math.round(100 * t.pts / t.max);
      return `<div style="display: flex; flex-direction: column; justify-content: center; gap: 8px; height: ${HEAD_H}px; box-sizing: border-box; padding: 0 4px">
  <div style="display: flex; align-items: baseline; justify-content: space-between"><span style="font-family: ${s.body}; font-size: 17px; font-weight: 700; color: ${s.fg}; letter-spacing: -0.01em">${esc(t.name)}</span><span style="font-family: ${s.cond}; font-size: 14px; font-weight: 600; color: ${s.muted}">${t.pts} / ${t.max} pts</span></div>
  <div style="height: 5px; border-radius: 3px; background: ${s.line}; overflow: hidden"><div style="width: ${pct}%; height: 100%; background: ${s.ink}"></div></div>
</div>`;
    },
    tile(n, s) {
      const st = n.s, lk = st === 'locked';
      const border = st === 'done' ? s.ink : st === 'active' ? s.warn : s.line;
      const pips = Array.from({ length: n.m }, (_, i) => `<div style="width: 14px; height: 6px; border-radius: 2px; background: ${i < n.p ? (st === 'done' ? s.ink : s.warn) : s.line}"></div>`).join('');
      return `<div style="width: ${TILE_W}px; height: ${TILE_H}px; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 10px 8px 9px; border-radius: 8px; background: ${lk ? s.bg : s.card}; border: 1px ${lk ? 'dashed' : 'solid'} ${border}; ${lk ? '' : 'box-shadow: 0 1px 2px rgba(27, 30, 36, 0.06);'}">
  ${glyph(st, s)}
  <div style="font-family: ${s.body}; font-size: 12px; font-weight: 600; line-height: 1.15; text-align: center; color: ${lk ? s.muted : s.fg}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
  <div style="display: flex; gap: 3px">${pips}</div>
</div>`;
    },
    gate(tierNo, open, have, s) {
      return `<div style="display: flex; align-items: center; justify-content: space-between; height: ${GATE_H}px; box-sizing: border-box; padding: 0 12px; border-radius: 6px; background: ${open ? s.inkSoft : s.bg}; border: 1px solid ${open ? s.ink : s.line}; font-family: ${s.cond}; font-size: 13px; font-weight: 600; color: ${open ? s.ink : s.muted}">
  <span style="display: flex; align-items: center; gap: 6px">${open ? '' : lockSvg(s.muted, 13)}Tier ${tierNo}</span><span>${open ? 'Unlocked' : `${have} of ${GATE} pts in tier ${tierNo - 1}`}</span>
</div>`;
    }
  },

  // F · Inked: charcoal, chamfered panels, off-white ink outlines, one hot orange.
  Inked: {
    fonts: 'https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@600;700;800&family=Barlow:wght@400;500;600&display=swap',
    body: "'Barlow', 'Segoe UI', system-ui, sans-serif", disp: "'Big Shoulders Display', 'Arial Narrow', Impact, sans-serif",
    bg: '#15161a', panel: '#1f2025', fg: '#ebe8df', muted: '#8a8a90', line: '#3a3b42', ink: '#ff7a1a', warn: '#ff7a1a', link: '#ff7a1a',
    gDone: '#15161a', gActive: '#ff7a1a', gTodo: '#ebe8df', gLocked: '#55565e', gTick: '#ff7a1a',
    frameStyle: 'background-color: #15161a; background-image: repeating-linear-gradient(135deg, rgba(235, 232, 223, 0.035) 0 1px, transparent 1px 14px);',
    chamfer: 'clip-path: polygon(8px 0, 100% 0, 100% calc(100% - 8px), calc(100% - 8px) 100%, 0 100%, 0 8px);',
    header(s) {
      return `
<div style="display: flex; flex-direction: column; padding: 0 40px; height: 160px; box-sizing: border-box; border-bottom: 2px solid ${s.fg}">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 56px; border-bottom: 1px solid ${s.line}">
    <div style="display: flex; align-items: center; gap: 28px">
      <div style="font-family: ${s.disp}; font-size: 24px; font-weight: 800; letter-spacing: 0.06em; color: ${s.fg}; text-transform: uppercase; display: flex; align-items: center; gap: 10px"><span style="display: inline-block; width: 14px; height: 24px; background: ${s.ink}; ${s.chamferSmall || 'clip-path: polygon(4px 0, 100% 0, 100% calc(100% - 4px), calc(100% - 4px) 100%, 0 100%, 0 4px);'}"></span>Branchwork</div>
      <div style="display: flex; gap: 6px; font-family: ${s.disp}; font-size: 16px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase">
        <div style="padding: 5px 14px; background: ${s.fg}; color: ${s.bg}; clip-path: polygon(6px 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%, 0 6px)">Tree</div>
        <div style="padding: 5px 14px; color: ${s.muted}">List</div>
        <div style="padding: 5px 14px; color: ${s.muted}">Timeline</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 16px">
      <div style="display: flex; align-items: center; gap: 6px; padding: 6px 14px; background: ${s.ink}; color: ${s.bg}; font-family: ${s.disp}; font-size: 16px; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; clip-path: polygon(6px 0, 100% 0, 100% calc(100% - 6px), calc(100% - 6px) 100%, 0 100%, 0 6px)">${plusIcon(s.bg)} New task</div>
      <div style="display: flex; align-items: center; gap: 8px; font-family: ${s.body}; font-size: 13px; color: ${s.muted}">${userIcon(s.muted)} Ruben</div>
    </div>
  </div>
  <div style="display: flex; align-items: flex-end; justify-content: space-between; flex-grow: 1; padding: 10px 0 14px">
    <div style="display: flex; flex-direction: column; gap: 2px">
      <div style="font-family: ${s.body}; font-size: 12px; font-weight: 500; letter-spacing: 0.14em; text-transform: uppercase; color: ${s.ink}">Project 2026-014</div>
      <div style="font-family: ${s.disp}; font-size: 40px; font-weight: 800; line-height: 1; letter-spacing: 0.02em; text-transform: uppercase; color: ${s.fg}">Office fit-out, Level 3</div>
    </div>
    <div style="display: flex; align-items: flex-end; gap: 20px">
      <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 6px">
        <div style="font-family: ${s.body}; font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase; color: ${s.muted}">Points earned</div>
        <div style="display: flex; gap: 3px">${Array.from({ length: TOTAL_M }, (_, i) => `<div style="width: 7px; height: 16px; background: ${i < TOTAL_P ? s.ink : 'transparent'}; border: 1px solid ${i < TOTAL_P ? s.ink : s.line}"></div>`).join('')}</div>
      </div>
      <div style="font-family: ${s.disp}; font-size: 44px; font-weight: 800; line-height: 1; color: ${s.fg}">${TOTAL_P}<span style="font-size: 22px; color: ${s.muted}">/${TOTAL_M}</span></div>
    </div>
  </div>
</div>`;
    },
    colHead(t, s) {
      const lit = t.pts > 0;
      return `<div style="display: flex; align-items: center; justify-content: space-between; height: ${HEAD_H}px; box-sizing: border-box; padding: 0 16px; background: ${lit ? s.fg : s.panel}; color: ${lit ? s.bg : s.muted}; ${s.chamfer}">
  <span style="font-family: ${s.disp}; font-size: 26px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase">${esc(t.name)}</span>
  <span style="font-family: ${s.disp}; font-size: 22px; font-weight: 700; letter-spacing: 0.04em; color: ${lit ? s.ink : s.muted}">${String(t.pts).padStart(2, '0')}<span style="opacity: 0.6">/${String(t.max).padStart(2, '0')}</span></span>
</div>`;
    },
    tile(n, s) {
      const st = n.s, lk = st === 'locked', done = st === 'done', act = st === 'active';
      const bg = done ? s.ink : s.panel;
      const outline = done ? s.ink : act ? s.ink : lk ? s.line : s.fg;
      const fgc = done ? s.bg : lk ? s.muted : s.fg;
      const pips = Array.from({ length: n.m }, (_, i) => `<div style="width: 12px; height: 8px; background: ${i < n.p ? (done ? s.bg : s.ink) : 'transparent'}; border: 1.5px solid ${done ? s.bg : lk ? s.line : s.ink}; clip-path: polygon(3px 0, 100% 0, 100% calc(100% - 3px), calc(100% - 3px) 100%, 0 100%, 0 3px)"></div>`).join('');
      return `<div style="width: ${TILE_W}px; height: ${TILE_H}px; box-sizing: border-box; padding: 2px; background: ${outline}; ${s.chamfer}">
  <div style="width: 100%; height: 100%; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 9px 8px 8px; background: ${bg}; ${s.chamfer}">
    ${glyph(st, s)}
    <div style="font-family: ${s.body}; font-size: 12.5px; font-weight: 600; line-height: 1.12; text-align: center; text-transform: uppercase; letter-spacing: 0.02em; color: ${fgc}; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
    <div style="display: flex; gap: 3px">${pips}</div>
  </div>
</div>`;
    },
    gate(tierNo, open, have, s) {
      const pct = Math.min(100, Math.round(100 * have / GATE));
      return `<div style="position: relative; display: flex; align-items: center; justify-content: space-between; height: ${GATE_H}px; box-sizing: border-box; padding: 0 14px; background: ${s.panel}; border: 1px solid ${open ? s.ink : s.line}; ${s.chamfer} font-family: ${s.disp}; font-size: 17px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: ${open ? s.fg : s.muted}; overflow: hidden">
  <div style="position: absolute; left: 0; top: 0; bottom: 0; width: ${pct}%; background: rgba(255, 122, 26, ${open ? 0.28 : 0.14})"></div>
  <span style="position: relative; display: flex; align-items: center; gap: 8px">${open ? '' : lockSvg(s.muted, 14)}Tier ${tierNo}</span><span style="position: relative; color: ${open ? s.ink : s.muted}">${open ? 'Open' : `${have}/${GATE} pts`}</span>
</div>`;
    }
  },

  // G · Cel: comic cel-shading — thick black ink, halftone, skewed slabs, hard shadows.
  Cel: {
    fonts: 'https://fonts.googleapis.com/css2?family=Bangers&family=Oswald:wght@500;600;700&display=swap',
    body: "'Oswald', 'Arial Narrow', Impact, sans-serif", disp: "'Bangers', Impact, 'Arial Black', sans-serif",
    bg: '#1c1712', paper: '#f6efdc', fg: '#f6efdc', ink: '#111111', muted: '#9c948a', yellow: '#ffc928', orange: '#ff5e2e', teal: '#2ec4b6', grey: '#6d665e', link: '#ffc928',
    gDone: '#111111', gActive: '#111111', gTodo: '#111111', gLocked: '#2a2622', gTick: '#ffc928',
    frameStyle: 'background-color: #1c1712; background-image: radial-gradient(rgba(246, 239, 220, 0.10) 1.2px, transparent 1.3px), radial-gradient(ellipse 70% 40% at 50% 0%, rgba(255, 201, 40, 0.10), transparent 70%); background-size: 9px 9px, 100% 100%;',
    skew: 'transform: skewX(-6deg);', unskew: 'transform: skewX(6deg);',
    header(s) {
      const stripes = `repeating-linear-gradient(135deg, ${s.ink} 0 10px, ${s.yellow} 10px 20px)`;
      return `
<div style="position: relative; display: flex; flex-direction: column; padding: 0 40px; height: 160px; box-sizing: border-box">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 58px">
    <div style="display: flex; align-items: center; gap: 24px">
      <div style="font-family: ${s.disp}; font-size: 30px; letter-spacing: 0.06em; color: ${s.yellow}; text-shadow: 3px 3px 0 ${s.ink}; -webkit-text-stroke: 1px ${s.ink}">BRANCHWORK</div>
      <div style="display: flex; gap: 8px; font-family: ${s.body}; font-size: 15px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em">
        <div style="padding: 4px 14px; background: ${s.paper}; color: ${s.ink}; border: 3px solid ${s.ink}; box-shadow: 3px 3px 0 ${s.ink}; ${s.skew}"><span style="display: inline-block; ${s.unskew}">Tree</span></div>
        <div style="padding: 4px 14px; color: ${s.paper}; border: 3px solid ${s.paper}; ${s.skew}"><span style="display: inline-block; ${s.unskew}">List</span></div>
        <div style="padding: 4px 14px; color: ${s.paper}; border: 3px solid ${s.paper}; ${s.skew}"><span style="display: inline-block; ${s.unskew}">Timeline</span></div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 14px">
      <div style="padding: 5px 16px; background: ${s.orange}; color: ${s.ink}; border: 3px solid ${s.ink}; box-shadow: 3px 3px 0 ${s.ink}; font-family: ${s.disp}; font-size: 18px; letter-spacing: 0.08em; ${s.skew}"><span style="display: inline-block; ${s.unskew}">+ NEW TASK</span></div>
      <div style="display: flex; align-items: center; justify-content: center; width: 38px; height: 38px; background: ${s.teal}; border: 3px solid ${s.ink}; box-shadow: 3px 3px 0 ${s.ink}">${userIcon(s.ink)}</div>
    </div>
  </div>
  <div style="display: flex; align-items: flex-end; justify-content: space-between; flex-grow: 1; padding: 6px 0 16px">
    <div style="display: flex; flex-direction: column; gap: 6px">
      <div style="display: inline-flex; align-self: flex-start; padding: 2px 10px; background: ${s.ink}; color: ${s.yellow}; font-family: ${s.body}; font-size: 12px; font-weight: 700; letter-spacing: 0.16em; text-transform: uppercase; ${s.skew}"><span style="display: inline-block; ${s.unskew}">Project 2026-014 · Level 3</span></div>
      <div style="font-family: ${s.disp}; font-size: 48px; line-height: 1; letter-spacing: 0.04em; color: ${s.paper}; text-shadow: 4px 4px 0 ${s.ink}; -webkit-text-stroke: 1.5px ${s.ink}">OFFICE FIT-OUT</div>
    </div>
    <div style="display: flex; align-items: center; gap: 16px">
      <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 6px">
        <div style="font-family: ${s.body}; font-size: 13px; font-weight: 700; letter-spacing: 0.14em; text-transform: uppercase; color: ${s.paper}">Skill points</div>
        <div style="display: flex; width: 300px; height: 22px; box-sizing: border-box; border: 3px solid ${s.ink}; background: ${s.paper}; box-shadow: 4px 4px 0 ${s.ink}; ${s.skew}"><div style="width: ${Math.round(100 * TOTAL_P / TOTAL_M)}%; height: 100%; background-image: ${stripes}"></div></div>
      </div>
      <div style="font-family: ${s.disp}; font-size: 52px; line-height: 1; color: ${s.yellow}; text-shadow: 4px 4px 0 ${s.ink}; -webkit-text-stroke: 1.5px ${s.ink}">${TOTAL_P}<span style="font-size: 26px; color: ${s.paper}">/${TOTAL_M}</span></div>
    </div>
  </div>
</div>`;
    },
    colHead(t, s) {
      const lit = t.pts > 0;
      return `<div style="display: flex; align-items: center; justify-content: space-between; height: ${HEAD_H}px; box-sizing: border-box; padding: 0 20px; background: ${lit ? s.yellow : s.grey}; border: 3px solid ${s.ink}; box-shadow: 5px 5px 0 ${s.ink}; ${s.skew}">
  <span style="display: inline-block; font-family: ${s.disp}; font-size: 30px; letter-spacing: 0.06em; color: ${s.ink}; ${s.unskew}">${esc(t.name).toUpperCase()}</span>
  <span style="display: inline-block; font-family: ${s.disp}; font-size: 24px; letter-spacing: 0.04em; color: ${s.ink}; ${s.unskew}">${t.pts}/${t.max}</span>
</div>`;
    },
    tile(n, s) {
      const st = n.s, lk = st === 'locked', done = st === 'done', act = st === 'active';
      const bg = done ? s.yellow : act ? s.orange : lk ? s.grey : s.paper;
      const hatch = lk ? `background-image: repeating-linear-gradient(135deg, rgba(17, 17, 17, 0.35) 0 4px, transparent 4px 10px);` : '';
      const pips = Array.from({ length: n.m }, (_, i) => `<div style="width: 12px; height: 12px; box-sizing: border-box; background: ${i < n.p ? s.ink : 'transparent'}; border: 2px solid ${s.ink}"></div>`).join('');
      return `<div style="width: ${TILE_W}px; height: ${TILE_H}px; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 8px 6px 8px; background: ${bg}; ${hatch} border: 3px solid ${s.ink}; box-shadow: 5px 5px 0 ${s.ink}; ${s.skew}">
  <div style="display: flex; ${s.unskew}">${glyph(st, s)}</div>
  <div style="font-family: ${s.body}; font-size: 13px; font-weight: 700; line-height: 1.1; text-align: center; text-transform: uppercase; letter-spacing: 0.02em; color: ${lk ? '#2a2622' : s.ink}; ${s.unskew} display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.l)}</div>
  <div style="display: flex; gap: 3px; ${s.unskew}">${pips}</div>
</div>`;
    },
    gate(tierNo, open, have, s) {
      const stripes = open ? `repeating-linear-gradient(135deg, ${s.ink} 0 10px, ${s.yellow} 10px 20px)` : `repeating-linear-gradient(135deg, ${s.ink} 0 10px, ${s.grey} 10px 20px)`;
      return `<div style="position: relative; display: flex; align-items: center; justify-content: center; height: ${GATE_H}px; box-sizing: border-box; background-image: ${stripes}; border: 3px solid ${s.ink}; ${s.skew}">
  <div style="display: flex; align-items: center; gap: 8px; padding: 1px 12px; background: ${s.ink}; color: ${open ? s.yellow : s.paper}; font-family: ${s.disp}; font-size: 17px; letter-spacing: 0.1em; ${s.unskew}">${open ? '' : lockSvg(s.paper, 14)}TIER ${tierNo} ${open ? 'UNLOCKED!' : `· ${have}/${GATE} PTS`}</div>
</div>`;
    }
  }
};

// ---------- assemble ----------
function column(t, s, xi) {
  const x = xi * (COL_W + COL_GAP);
  const parts = [s.colHead(t, s)];
  t.tiers.forEach((tier, i) => {
    if (i > 0) {
      const have = sum(t.tiers[i - 1], 'p');
      parts.push(s.gate(i + 1, have >= GATE, have, s));
    }
    parts.push(`<div style="display: flex; justify-content: center; gap: ${TILE_GAP}px">${tier.map((n) => s.tile(n, s)).join('')}</div>`);
  });
  return `<div style="position: absolute; left: ${x}px; top: 0; width: ${COL_W}px; display: flex; flex-direction: column; gap: ${ROW_GAP}px">\n${parts.join('\n')}\n</div>`;
}

function artboard(s) {
  const cols = trees.map((t, i) => column(t, s, i)).join('\n');
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
<div style="position: relative; width: 1440px; height: 820px; overflow: hidden; ${s.frameStyle}">
${s.header(s)}
<div style="position: absolute; left: ${TREE_X}px; top: ${TREE_Y}px; width: ${3 * COL_W + 2 * COL_GAP}px; height: 560px">
${cols}
</div>
</div>
</x-dc>
</body>
</html>
`;
}

for (const [name, s] of Object.entries(styles)) {
  writeFileSync(new URL(`./${name}.dc.html`, import.meta.url), artboard(s));
}

// merge into canvas.json (third row)
const cpath = new URL('./canvas.json', import.meta.url);
const canvas = JSON.parse(readFileSync(cpath, 'utf8'));
const mine = ['Tiered.dc.html', 'Inked.dc.html', 'Cel.dc.html'];
canvas.artboards = canvas.artboards.filter((a) => !mine.includes(a.file));
canvas.annotations = (canvas.annotations || []).filter((a) => !['e-note', 'f-note', 'g-note', 'row3'].includes(a.id));
const Y = 2160;
canvas.artboards.push(
  { file: 'Tiered.dc.html', title: 'E · Tiered', x: 0, y: Y, w: 1440, h: 820 },
  { file: 'Inked.dc.html', title: 'F · Inked', x: 1560, y: Y, w: 1440, h: 820 },
  { file: 'Cel.dc.html', title: 'G · Cel', x: 3120, y: Y, w: 1440, h: 820 }
);
canvas.annotations.push(
  { id: 'row3', x: -420, y: Y, w: 360, text: 'Row 3: three takes on a tiered skill tree, professional to stylised.\n\nStructure borrowed from that genre: each branch is a vertical tree, skills sit in tiers, every task carries point pips (subtasks or effort), and the next tier only opens once the tier above has 3 points. Same project data as rows 1 and 2, so E, F and G compare directly with A to D.' },
  { id: 'e-note', x: 0, y: Y - 150, w: 520, text: 'E · Tiered. The tiered structure and point pips in a sober, light product UI.\nFor: teams who want the game mechanics (tiers, gates, points) without the game look.\nTrade-off: gates and pips carry the whole idea; if you strip them it becomes Studio.' },
  { id: 'f-note', x: 1560, y: Y - 150, w: 520, text: 'F · Inked. Charcoal, chamfered panels, off-white ink outlines, one hot orange, condensed display type.\nFor: a game-adjacent feel that still reads as a serious tool; completed tiles fill solid.\nTrade-off: dark-only; the orange has to stay the one accent or it turns garish.' },
  { id: 'g-note', x: 3120, y: Y - 150, w: 520, text: 'G · Cel. Full cel-shaded comic treatment: thick ink outlines, halftone, skewed slabs, hard offset shadows, hazard-stripe gates.\nFor: maximum motivation and personality; unlocking a tier feels like an event.\nTrade-off: loud. Hard to keep readable with many tasks and not for client-facing use.' }
);
writeFileSync(cpath, JSON.stringify(canvas, null, 2));
console.log('wrote', mine.join(', '), 'and updated canvas.json; points', TOTAL_P, '/', TOTAL_M);
