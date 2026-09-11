// Generates four direction artboards for the skill-tree task app from one
// shared tree + layout, so the options differ in style only.
import { writeFileSync } from 'node:fs';

// ---------- shared tree data ----------
// state: done | active | todo | locked
const tree = {
  label: 'Office fit-out, Level 3', state: 'active',
  branches: [
    { label: 'Design', done: 5, total: 8, cols: [0, 1, 2], children: [
      { label: 'Brief & survey', state: 'done', col: 0, leaves: [
        { label: 'Site measure-up', state: 'done' },
        { label: 'Client brief signed', state: 'done' } ] },
      { label: 'Concept layouts', state: 'done', col: 1, leaves: [
        { label: 'Option A / B review', state: 'done' } ] },
      { label: 'Detailed drawings', state: 'active', col: 2, leaves: [
        { label: 'Services coordination', state: 'todo' },
        { label: 'Issue for tender', state: 'todo' } ] } ] },
    { label: 'Approvals', done: 2, total: 4, cols: [3, 4], children: [
      { label: 'Landlord consent', state: 'done', col: 3, leaves: [] },
      { label: 'Building permit', state: 'active', col: 4, leaves: [
        { label: 'Fire engineering report', state: 'done' },
        { label: 'Certifier lodgement', state: 'todo' } ] } ] },
    { label: 'Construction', done: 0, total: 7, cols: [5, 6, 7], children: [
      { label: 'Tender & award', state: 'locked', col: 5, leaves: [
        { label: 'Shortlist contractors', state: 'locked' },
        { label: 'Award contract', state: 'locked' } ] },
      { label: 'Site works', state: 'locked', col: 6, leaves: [
        { label: 'Demolition', state: 'locked' },
        { label: 'Fit-out & services', state: 'locked' } ] },
      { label: 'Handover', state: 'locked', col: 7, leaves: [] } ] } ]
};

// ---------- shared layout (px inside the tree area) ----------
const PITCH = 170, COL0 = 85;
const colX = (c) => COL0 + c * PITCH;
const ROOT = { w: 300, h: 56, y: 0 };
const HEAD = { w: 250, h: 66, y: 104 };
const MID = { w: 162, h: 50, y: 218 };
const LEAF = { w: 162, h: 46, y0: 314, pitch: 58 };
const TREE_W = 1360, TREE_H = 480;
const TREE_X = 40, TREE_Y = 200;

function layout() {
  const nodes = [], edges = [];
  const rootCx = TREE_W / 2;
  nodes.push({ kind: 'root', x: rootCx - ROOT.w / 2, y: ROOT.y, w: ROOT.w, h: ROOT.h, label: tree.label, state: 'active' });
  for (const b of tree.branches) {
    const cx = (colX(b.cols[0]) + colX(b.cols[b.cols.length - 1])) / 2;
    nodes.push({ kind: 'head', x: cx - HEAD.w / 2, y: HEAD.y, w: HEAD.w, h: HEAD.h, label: b.label, done: b.done, total: b.total,
      state: b.done === b.total ? 'done' : b.done > 0 ? 'active' : 'locked' });
    edges.push({ x1: rootCx, y1: ROOT.y + ROOT.h, x2: cx, y2: HEAD.y, lit: b.done > 0, kind: 'fan' });
    for (const c of b.children) {
      const ccx = colX(c.col);
      nodes.push({ kind: 'mid', x: ccx - MID.w / 2, y: MID.y, w: MID.w, h: MID.h, label: c.label, state: c.state });
      edges.push({ x1: cx, y1: HEAD.y + HEAD.h, x2: ccx, y2: MID.y, lit: c.state === 'done' || c.state === 'active', kind: 'fan' });
      c.leaves.forEach((l, i) => {
        const ly = LEAF.y0 + i * LEAF.pitch;
        nodes.push({ kind: 'leaf', x: ccx - LEAF.w / 2, y: ly, w: LEAF.w, h: LEAF.h, label: l.label, state: l.state });
        if (i === 0) edges.push({ x1: ccx, y1: MID.y + MID.h, x2: ccx, y2: LEAF.y0 + (c.leaves.length - 1) * LEAF.pitch, lit: c.leaves.some(z => z.state === 'done'), kind: 'chain' });
      });
    }
  }
  return { nodes, edges };
}

function pathD(e, shape) {
  if (e.kind === 'chain') return `M ${e.x1} ${e.y1} V ${e.y2}`;
  const my = (e.y1 + e.y2) / 2;
  if (shape === 'elbow') return `M ${e.x1} ${e.y1} V ${my} H ${e.x2} V ${e.y2}`;
  if (shape === 'straight') return `M ${e.x1} ${e.y1} L ${e.x2} ${e.y2}`;
  return `M ${e.x1} ${e.y1} C ${e.x1} ${my} ${e.x2} ${my} ${e.x2} ${e.y2}`;
}

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

// ---------- icons (stroke SVG, 16px grid) ----------
const tick = (c, w = 2) => `<path d="M4 8.5l2.8 2.8L12 5.5" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"></path>`;
const lock = (c) => `<svg width="12" height="12" viewBox="0 0 16 16" style="flex-shrink: 0"><rect x="3" y="7" width="10" height="7" rx="1.5" fill="none" stroke="${c}" stroke-width="1.5"></rect><path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" fill="none" stroke="${c}" stroke-width="1.5"></path></svg>`;
const userIcon = (c) => `<svg width="18" height="18" viewBox="0 0 16 16"><circle cx="8" cy="5.5" r="3" fill="none" stroke="${c}" stroke-width="1.5"></circle><path d="M2.5 14a5.5 5.5 0 0 1 11 0" fill="none" stroke="${c}" stroke-width="1.5" stroke-linecap="round"></path></svg>`;
const plusIcon = (c) => `<svg width="14" height="14" viewBox="0 0 16 16"><path d="M8 3v10M3 8h10" fill="none" stroke="${c}" stroke-width="1.8" stroke-linecap="round"></path></svg>`;

// ---------- style definitions ----------
const styles = {
  // A · Blueprint: drafting-sheet dark navy, grid paper, cyan ink, mono labels.
  Main: {
    title: 'Branchwork · Blueprint',
    fonts: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600&display=swap',
    body: "'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif",
    mono: "'IBM Plex Mono', Consolas, monospace",
    bg: '#0b1626', fg: '#d9e6f2', muted: '#6f86a0', line: '#2a4a6b', ink: '#3ec6f0', warn: '#f0b13e', link: '#3ec6f0',
    frameStyle: `background-color: #0b1626; background-image: linear-gradient(rgba(62, 198, 240, 0.07) 1px, transparent 1px), linear-gradient(90deg, rgba(62, 198, 240, 0.07) 1px, transparent 1px), linear-gradient(rgba(62, 198, 240, 0.035) 1px, transparent 1px), linear-gradient(90deg, rgba(62, 198, 240, 0.035) 1px, transparent 1px); background-size: 120px 120px, 120px 120px, 24px 24px, 24px 24px;`,
    connector: 'elbow', strokeLit: '#3ec6f0', strokeDim: '#2a4a6b', strokeW: 1.5, dash: '6 5',
    header(s) {
      return `
<div style="display: flex; flex-direction: column; gap: 0; padding: 0 40px; height: 168px; box-sizing: border-box; border-bottom: 1px solid ${s.line}">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 56px; border-bottom: 1px solid ${s.line}">
    <div style="display: flex; align-items: center; gap: 24px">
      <div style="display: flex; align-items: center; gap: 10px; font-family: ${s.mono}; font-size: 14px; font-weight: 600; letter-spacing: 0.08em; color: ${s.ink}">
        <svg width="22" height="22" viewBox="0 0 22 22"><path d="M11 3v5M11 8H5v4M11 8h6v4M5 12v4M17 12v4" fill="none" stroke="${s.ink}" stroke-width="1.6" stroke-linecap="square"></path><rect x="8.5" y="1" width="5" height="4" fill="${s.ink}"></rect><rect x="2.5" y="16" width="5" height="4" fill="none" stroke="${s.ink}" stroke-width="1.4"></rect><rect x="14.5" y="16" width="5" height="4" fill="none" stroke="${s.ink}" stroke-width="1.4"></rect></svg>
        BRANCHWORK
      </div>
      <div style="display: flex; gap: 4px; font-family: ${s.mono}; font-size: 12px; letter-spacing: 0.06em">
        <div style="padding: 6px 12px; color: ${s.bg}; background: ${s.ink}">TREE</div>
        <div style="padding: 6px 12px; color: ${s.muted}; border: 1px solid ${s.line}">LIST</div>
        <div style="padding: 6px 12px; color: ${s.muted}; border: 1px solid ${s.line}">TIMELINE</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 16px; font-family: ${s.mono}; font-size: 12px; color: ${s.muted}; letter-spacing: 0.06em">
      <div style="display: flex; align-items: center; gap: 6px; padding: 6px 12px; border: 1px solid ${s.ink}; color: ${s.ink}">${plusIcon(s.ink)} NEW TASK</div>
      <div style="display: flex; align-items: center; gap: 8px">${userIcon(s.muted)} R. MOON</div>
    </div>
  </div>
  <div style="display: flex; align-items: flex-end; justify-content: space-between; flex-grow: 1; padding: 16px 0 18px">
    <div style="display: flex; flex-direction: column; gap: 6px">
      <div style="font-family: ${s.mono}; font-size: 11px; letter-spacing: 0.14em; color: ${s.muted}">PROJECT 2026-014 &nbsp;·&nbsp; SHEET 01 OF 01 &nbsp;·&nbsp; REV C</div>
      <div style="font-family: ${s.body}; font-size: 26px; font-weight: 500; color: ${s.fg}; letter-spacing: -0.01em">Office fit-out, Level 3</div>
    </div>
    <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px">
      <div style="font-family: ${s.mono}; font-size: 12px; letter-spacing: 0.1em; color: ${s.muted}">7 / 19 TASKS &nbsp;·&nbsp; <span style="color: ${s.ink}">37%</span></div>
      <div style="display: flex; gap: 3px">${Array.from({ length: 19 }, (_, i) => `<div style="width: 14px; height: 10px; background: ${i < 7 ? s.ink : 'transparent'}; border: 1px solid ${i < 7 ? s.ink : s.line}"></div>`).join('')}</div>
    </div>
  </div>
</div>`;
    },
    node(n, s) {
      const st = n.state;
      const border = st === 'done' ? s.ink : st === 'active' ? s.warn : st === 'locked' ? s.line : s.muted;
      const color = st === 'locked' ? s.muted : s.fg;
      const borderStyle = st === 'active' ? 'dashed' : 'solid';
      const box = `<svg width="16" height="16" viewBox="0 0 16 16" style="flex-shrink: 0"><rect x="1" y="1" width="14" height="14" fill="${st === 'done' ? s.ink : 'none'}" stroke="${st === 'done' ? s.ink : st === 'locked' ? s.line : st === 'active' ? s.warn : s.muted}" stroke-width="1.4"></rect>${st === 'done' ? tick(s.bg, 2) : ''}</svg>`;
      if (n.kind === 'root') {
        return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; gap: 12px; background: ${s.bg}; border: 2px solid ${s.ink}; font-family: ${s.mono}; font-size: 13px; font-weight: 600; letter-spacing: 0.1em; color: ${s.ink}">ROOT &nbsp;·&nbsp; ${esc(n.label).toUpperCase()}</div>`;
      }
      if (n.kind === 'head') {
        const segs = Array.from({ length: n.total }, (_, i) => `<div style="flex-grow: 1; height: 6px; background: ${i < n.done ? s.ink : 'transparent'}; border: 1px solid ${i < n.done ? s.ink : s.line}"></div>`).join('');
        return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; gap: 8px; padding: 10px 14px; background: ${s.bg}; border: 1.5px solid ${border}; border-style: ${borderStyle}">
  <div style="display: flex; align-items: center; justify-content: space-between; font-family: ${s.mono}; font-size: 13px; font-weight: 600; letter-spacing: 0.1em; color: ${color}"><span>${esc(n.label).toUpperCase()}</span><span style="color: ${s.muted}; font-weight: 400">${n.done}/${n.total}</span></div>
  <div style="display: flex; gap: 3px">${segs}</div>
</div>`;
      }
      return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; align-items: center; gap: 8px; padding: 0 10px; background: ${s.bg}; border: 1px solid ${border}; border-style: ${borderStyle}; font-family: ${s.body}; font-size: ${n.kind === 'mid' ? 13 : 12}px; font-weight: ${n.kind === 'mid' ? 500 : 400}; color: ${color}">${box}<span style="flex-grow: 1; line-height: 1.15; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.label)}</span>${st === 'locked' ? lock(s.line) : ''}</div>`;
    }
  },

  // B · Constellation: game skill-tree, near-black, glowing lit paths.
  Constellation: {
    title: 'Branchwork · Constellation',
    fonts: 'https://fonts.googleapis.com/css2?family=Chakra+Petch:wght@500;600;700&family=Space+Grotesk:wght@400;500;600&display=swap',
    body: "'Space Grotesk', 'Segoe UI', system-ui, sans-serif",
    display: "'Chakra Petch', 'Segoe UI', system-ui, sans-serif",
    bg: '#0a0a14', fg: '#ecebf5', muted: '#6d6b86', line: '#23223a', ink: '#7c6cf0', ink2: '#3ee6c1', warn: '#f5a43e', link: '#3ee6c1',
    frameStyle: `background-color: #0a0a14; background-image: radial-gradient(ellipse 60% 50% at 50% 30%, rgba(124, 108, 240, 0.16), transparent 70%), radial-gradient(circle at 20% 90%, rgba(62, 230, 193, 0.08), transparent 45%), radial-gradient(rgba(236, 235, 245, 0.07) 1px, transparent 1px); background-size: 100% 100%, 100% 100%, 28px 28px;`,
    connector: 'curve', strokeLit: '#3ee6c1', strokeDim: '#23223a', strokeW: 2.5, glow: true,
    header(s) {
      const R = 34, C = 2 * Math.PI * R, pct = 7 / 19;
      return `
<div style="display: flex; align-items: center; justify-content: space-between; padding: 0 40px; height: 168px; box-sizing: border-box">
  <div style="display: flex; flex-direction: column; gap: 22px">
    <div style="display: flex; align-items: center; gap: 28px">
      <div style="display: flex; align-items: center; gap: 10px; font-family: ${s.display}; font-size: 17px; font-weight: 700; letter-spacing: 0.12em; color: ${s.fg}">
        <svg width="24" height="24" viewBox="0 0 24 24"><circle cx="12" cy="4" r="2.5" fill="${s.ink2}"></circle><circle cx="5" cy="19" r="2.5" fill="${s.ink}"></circle><circle cx="19" cy="19" r="2.5" fill="none" stroke="${s.muted}" stroke-width="1.5"></circle><path d="M12 6.5L5 16.5M12 6.5l7 10" stroke="${s.ink}" stroke-width="1.5"></path></svg>
        BRANCHWORK
      </div>
      <div style="display: flex; gap: 2px; padding: 3px; background: rgba(236, 235, 245, 0.05); border-radius: 999px; font-family: ${s.body}; font-size: 13px; font-weight: 500">
        <div style="padding: 6px 16px; border-radius: 999px; color: ${s.bg}; background: ${s.fg}">Tree</div>
        <div style="padding: 6px 16px; border-radius: 999px; color: ${s.muted}">List</div>
        <div style="padding: 6px 16px; border-radius: 999px; color: ${s.muted}">Timeline</div>
      </div>
    </div>
    <div style="display: flex; flex-direction: column; gap: 4px">
      <div style="font-family: ${s.body}; font-size: 13px; color: ${s.muted}">Projects &nbsp;/&nbsp; <span style="color: ${s.ink2}">Level 3 branch unlocked</span></div>
      <div style="font-family: ${s.display}; font-size: 30px; font-weight: 600; color: ${s.fg}; letter-spacing: 0.01em">Office fit-out, Level 3</div>
    </div>
  </div>
  <div style="display: flex; align-items: center; gap: 28px">
    <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 6px; font-family: ${s.body}; font-size: 13px; color: ${s.muted}">
      <div style="font-family: ${s.display}; font-size: 15px; font-weight: 600; letter-spacing: 0.1em; color: ${s.fg}">7 OF 19 CLEARED</div>
      <div>Next unlock: <span style="color: ${s.fg}">Construction</span> after 2 more</div>
    </div>
    <svg width="88" height="88" viewBox="0 0 88 88" style="filter: drop-shadow(0 0 10px rgba(62, 230, 193, 0.45))"><circle cx="44" cy="44" r="${R}" fill="none" stroke="${s.line}" stroke-width="7"></circle><circle cx="44" cy="44" r="${R}" fill="none" stroke="${s.ink2}" stroke-width="7" stroke-linecap="round" stroke-dasharray="${(C * pct).toFixed(1)} ${C.toFixed(1)}" transform="rotate(-90 44 44)"></circle><text x="44" y="49" text-anchor="middle" font-family="${s.display}" font-size="18" font-weight="700" fill="${s.fg}">37%</text></svg>
    <div style="display: flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 999px; background: ${s.line}">${userIcon(s.fg)}</div>
  </div>
</div>`;
    },
    node(n, s) {
      const st = n.state;
      const lit = st === 'done', act = st === 'active', lk = st === 'locked';
      const glowCss = lit ? `box-shadow: 0 0 0 1px ${s.ink2}, 0 0 18px rgba(62, 230, 193, 0.35);` : act ? `box-shadow: 0 0 0 1px ${s.warn}, 0 0 22px rgba(245, 164, 62, 0.35);` : `box-shadow: 0 0 0 1px ${lk ? s.line : '#3c3a5a'};`;
      const bgCss = lit ? `background: linear-gradient(135deg, rgba(62, 230, 193, 0.22), rgba(124, 108, 240, 0.18));` : act ? `background: rgba(245, 164, 62, 0.1);` : `background: ${lk ? 'rgba(10, 10, 20, 0.85)' : 'rgba(30, 29, 48, 0.9)'};`;
      const color = lk ? s.muted : s.fg;
      const orb = `<svg width="20" height="20" viewBox="0 0 20 20" style="flex-shrink: 0"><circle cx="10" cy="10" r="8" fill="${lit ? s.ink2 : 'none'}" stroke="${lit ? s.ink2 : act ? s.warn : lk ? s.line : '#57557a'}" stroke-width="${act ? 2 : 1.5}" stroke-dasharray="${act ? '3 2.5' : 'none'}"></circle>${lit ? `<path d="M6 10.5l2.6 2.6L14 7.5" fill="none" stroke="${s.bg}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>` : act ? `<circle cx="10" cy="10" r="3" fill="${s.warn}"></circle>` : ''}</svg>`;
      if (n.kind === 'root') {
        return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; gap: 12px; border-radius: 999px; background: linear-gradient(90deg, ${s.ink}, ${s.ink2}); box-shadow: 0 0 30px rgba(124, 108, 240, 0.45); font-family: ${s.display}; font-size: 15px; font-weight: 700; letter-spacing: 0.1em; color: ${s.bg}">${esc(n.label).toUpperCase()}</div>`;
      }
      if (n.kind === 'head') {
        const pct = Math.round(100 * n.done / n.total);
        return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; gap: 8px; padding: 10px 16px; border-radius: 14px; ${bgCss} ${glowCss}">
  <div style="display: flex; align-items: center; justify-content: space-between; font-family: ${s.display}; font-size: 15px; font-weight: 600; letter-spacing: 0.08em; color: ${color}"><span style="display: flex; align-items: center; gap: 8px">${lk ? lock(s.muted) : ''}${esc(n.label).toUpperCase()}</span><span style="font-family: ${s.body}; font-size: 12px; font-weight: 500; color: ${lit || act ? s.ink2 : s.muted}">${pct}%</span></div>
  <div style="height: 5px; border-radius: 999px; background: rgba(236, 235, 245, 0.1); overflow: hidden"><div style="width: ${pct}%; height: 100%; border-radius: 999px; background: ${s.ink2}"></div></div>
</div>`;
      }
      return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; align-items: center; gap: 8px; padding: 0 12px; border-radius: 999px; ${bgCss} ${glowCss} font-family: ${s.body}; font-size: ${n.kind === 'mid' ? 13 : 12}px; font-weight: ${n.kind === 'mid' ? 600 : 500}; color: ${color}">${lk ? lock(s.muted) : orb}<span style="flex-grow: 1; line-height: 1.15; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.label)}</span></div>`;
    }
  },

  // C · Ledger: paper, ink, serif — a printed checklist that happens to branch.
  Ledger: {
    title: 'Branchwork · Ledger',
    fonts: 'https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;1,6..72,400&family=Karla:wght@400;500;600&display=swap',
    body: "'Karla', 'Segoe UI', system-ui, sans-serif",
    display: "'Newsreader', Georgia, 'Times New Roman', serif",
    bg: '#f4efe4', fg: '#1e1a15', muted: '#8a8073', line: '#cfc5b3', ink: '#1e1a15', red: '#b5442a', link: '#b5442a',
    frameStyle: `background-color: #f4efe4; background-image: radial-gradient(rgba(30, 26, 21, 0.06) 0.6px, transparent 0.6px); background-size: 6px 6px;`,
    connector: 'straight', strokeLit: '#1e1a15', strokeDim: '#cfc5b3', strokeW: 1,
    header(s) {
      return `
<div style="display: flex; flex-direction: column; gap: 0; padding: 0 40px; height: 168px; box-sizing: border-box">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 54px; border-bottom: 1px solid ${s.fg}">
    <div style="display: flex; align-items: baseline; gap: 32px">
      <div style="font-family: ${s.display}; font-size: 22px; font-weight: 500; color: ${s.fg}; letter-spacing: -0.01em">Branchwork</div>
      <div style="display: flex; gap: 22px; font-family: ${s.body}; font-size: 13px; font-weight: 500; letter-spacing: 0.04em; text-transform: uppercase">
        <div style="color: ${s.fg}; border-bottom: 2px solid ${s.red}; padding-bottom: 2px">Tree</div>
        <div style="color: ${s.muted}">List</div>
        <div style="color: ${s.muted}">Timeline</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 22px; font-family: ${s.body}; font-size: 13px; color: ${s.muted}">
      <div style="display: flex; align-items: center; gap: 6px; color: ${s.fg}; font-weight: 500">${plusIcon(s.fg)} New task</div>
      <div style="display: flex; align-items: center; gap: 8px">${userIcon(s.muted)} Ruben</div>
    </div>
  </div>
  <div style="display: flex; align-items: flex-end; justify-content: space-between; flex-grow: 1; padding: 14px 0 16px; border-bottom: 1px solid ${s.line}">
    <div style="display: flex; flex-direction: column; gap: 4px">
      <div style="font-family: ${s.body}; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: ${s.muted}">Project ledger &nbsp;·&nbsp; opened 3 March 2026</div>
      <div style="font-family: ${s.display}; font-size: 38px; font-weight: 400; line-height: 1.05; color: ${s.fg}; letter-spacing: -0.01em">Office fit-out, <em style="font-style: italic">Level 3</em></div>
    </div>
    <div style="display: flex; align-items: baseline; gap: 10px; font-family: ${s.display}; color: ${s.fg}">
      <span style="font-size: 44px; line-height: 1">7</span><span style="font-size: 20px; color: ${s.muted}">of 19 tasks done</span>
    </div>
  </div>
</div>`;
    },
    node(n, s) {
      const st = n.state;
      const lit = st === 'done', act = st === 'active', lk = st === 'locked';
      const color = lk ? s.muted : s.fg;
      const ring = `<svg width="18" height="18" viewBox="0 0 18 18" style="flex-shrink: 0"><circle cx="9" cy="9" r="7.5" fill="${lit ? s.ink : s.bg}" stroke="${lk ? s.line : act ? s.red : s.ink}" stroke-width="${act ? 1.8 : 1.2}"></circle>${lit ? `<path d="M5.5 9.5l2.4 2.4L12.8 6.5" fill="none" stroke="${s.bg}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path>` : act ? `<circle cx="9" cy="9" r="2.5" fill="${s.red}"></circle>` : ''}</svg>`;
      if (n.kind === 'root') {
        return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; background: ${s.bg}; border-top: 1px solid ${s.ink}; border-bottom: 1px solid ${s.ink}; font-family: ${s.display}; font-size: 20px; font-style: italic; color: ${s.fg}">${esc(n.label)}</div>`;
      }
      if (n.kind === 'head') {
        return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 4px; background: ${s.bg}; border: 1px solid ${lk ? s.line : s.ink}">
  <div style="font-family: ${s.display}; font-size: 22px; font-weight: 500; color: ${color}; line-height: 1.1">${esc(n.label)}</div>
  <div style="font-family: ${s.body}; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: ${act ? s.red : s.muted}">${n.done} of ${n.total} ${lit ? '· complete' : act ? '· in hand' : '· not started'}</div>
</div>`;
      }
      return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; align-items: center; gap: 8px; padding: 0 8px; background: ${s.bg}; font-family: ${s.body}; font-size: ${n.kind === 'mid' ? 14 : 13}px; font-weight: ${n.kind === 'mid' ? 600 : 400}; color: ${color}; ${act ? `text-decoration: underline; text-decoration-color: ${s.red}; text-underline-offset: 3px;` : ''}">${ring}<span style="flex-grow: 1; line-height: 1.15; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.label)}</span>${lk ? lock(s.line) : ""}</div>`;
    }
  },

  // D · Studio: light, calm product UI with cards and one green accent.
  Studio: {
    title: 'Branchwork · Studio',
    fonts: 'https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,600;9..40,700&family=JetBrains+Mono:wght@500&display=swap',
    body: "'DM Sans', 'Segoe UI', system-ui, sans-serif",
    mono: "'JetBrains Mono', Consolas, monospace",
    bg: '#f6f6f4', card: '#ffffff', fg: '#17191c', muted: '#737880', line: '#dedfdb', ink: '#1f8f62', inkSoft: '#e4f3ea', warn: '#d98a1c', warnSoft: '#fbf0dc', link: '#1f8f62',
    frameStyle: `background-color: #f6f6f4;`,
    connector: 'elbow', strokeLit: '#1f8f62', strokeDim: '#d3d5d0', strokeW: 2, round: true,
    header(s) {
      return `
<div style="display: flex; flex-direction: column; padding: 0 40px; height: 168px; box-sizing: border-box; background: ${s.card}; border-bottom: 1px solid ${s.line}">
  <div style="display: flex; align-items: center; justify-content: space-between; height: 60px">
    <div style="display: flex; align-items: center; gap: 24px">
      <div style="display: flex; align-items: center; gap: 9px; font-family: ${s.body}; font-size: 16px; font-weight: 700; color: ${s.fg}; letter-spacing: -0.01em">
        <div style="display: flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 8px; background: ${s.ink}"><svg width="16" height="16" viewBox="0 0 16 16"><path d="M8 2v4M8 6H4v4M8 6h4v4" fill="none" stroke="#ffffff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"></path><circle cx="4" cy="12" r="1.8" fill="#ffffff"></circle><circle cx="12" cy="12" r="1.8" fill="#ffffff"></circle></svg></div>
        Branchwork
      </div>
      <div style="display: flex; gap: 2px; padding: 3px; background: ${s.bg}; border-radius: 8px; font-family: ${s.body}; font-size: 13px; font-weight: 500">
        <div style="padding: 5px 12px; border-radius: 6px; color: ${s.fg}; background: ${s.card}; box-shadow: 0 1px 2px rgba(23, 25, 28, 0.08)">Tree</div>
        <div style="padding: 5px 12px; border-radius: 6px; color: ${s.muted}">List</div>
        <div style="padding: 5px 12px; border-radius: 6px; color: ${s.muted}">Timeline</div>
      </div>
    </div>
    <div style="display: flex; align-items: center; gap: 12px">
      <div style="display: flex; align-items: center; gap: 6px; padding: 7px 12px; border-radius: 8px; background: ${s.fg}; color: #ffffff; font-family: ${s.body}; font-size: 13px; font-weight: 500">${plusIcon('#ffffff')} New task</div>
      <div style="display: flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 999px; background: ${s.inkSoft}">${userIcon(s.ink)}</div>
    </div>
  </div>
  <div style="display: flex; align-items: center; justify-content: space-between; flex-grow: 1; padding: 6px 0 14px">
    <div style="display: flex; flex-direction: column; gap: 6px">
      <div style="display: flex; align-items: center; gap: 8px; font-family: ${s.body}; font-size: 13px; color: ${s.muted}"><span>Projects</span><span>/</span><span style="color: ${s.fg}">Office fit-out</span></div>
      <div style="font-family: ${s.body}; font-size: 28px; font-weight: 600; color: ${s.fg}; letter-spacing: -0.02em">Office fit-out, Level 3</div>
    </div>
    <div style="display: flex; align-items: center; gap: 28px">
      <div style="display: flex; flex-direction: column; gap: 6px; width: 260px">
        <div style="display: flex; justify-content: space-between; font-family: ${s.body}; font-size: 13px; color: ${s.muted}"><span>Overall progress</span><span style="font-family: ${s.mono}; color: ${s.fg}; font-weight: 500">7 / 19</span></div>
        <div style="height: 8px; border-radius: 999px; background: ${s.line}; overflow: hidden"><div style="width: 37%; height: 100%; border-radius: 999px; background: ${s.ink}"></div></div>
      </div>
      <div style="display: flex; gap: 6px; font-family: ${s.body}; font-size: 12px; font-weight: 500">
        <div style="display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px; background: ${s.inkSoft}; color: ${s.ink}"><span style="width: 7px; height: 7px; border-radius: 999px; background: ${s.ink}"></span>7 done</div>
        <div style="display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px; background: ${s.warnSoft}; color: ${s.warn}"><span style="width: 7px; height: 7px; border-radius: 999px; background: ${s.warn}"></span>2 in progress</div>
        <div style="display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px; background: ${s.card}; color: ${s.muted}; border: 1px solid ${s.line}"><span style="width: 7px; height: 7px; border-radius: 999px; border: 1.5px solid #b8bcc2; box-sizing: border-box"></span>3 not started</div>
        <div style="display: flex; align-items: center; gap: 6px; padding: 5px 10px; border-radius: 999px; background: ${s.bg}; color: ${s.muted}; border: 1px solid ${s.line}"><span style="width: 7px; height: 7px; border-radius: 999px; background: ${s.line}"></span>7 blocked</div>
      </div>
    </div>
  </div>
</div>`;
    },
    node(n, s) {
      const st = n.state;
      const lit = st === 'done', act = st === 'active', lk = st === 'locked';
      const color = lk ? s.muted : s.fg;
      const border = lit ? s.ink : act ? s.warn : s.line;
      const bg = lit ? s.inkSoft : act ? s.warnSoft : lk ? s.bg : s.card;
      const shadow = lk ? '' : 'box-shadow: 0 1px 2px rgba(23, 25, 28, 0.06), 0 4px 12px rgba(23, 25, 28, 0.04);';
      const box = `<svg width="18" height="18" viewBox="0 0 18 18" style="flex-shrink: 0"><rect x="1" y="1" width="16" height="16" rx="5" fill="${lit ? s.ink : s.card}" stroke="${lit ? s.ink : act ? s.warn : lk ? s.line : '#b8bcc2'}" stroke-width="1.5"></rect>${lit ? `<path d="M5.5 9.5l2.4 2.4L12.8 6.5" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>` : ''}</svg>`;
      if (n.kind === 'root') {
        return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; gap: 10px; border-radius: 12px; background: ${s.fg}; color: #ffffff; font-family: ${s.body}; font-size: 15px; font-weight: 600; letter-spacing: -0.01em; box-shadow: 0 6px 18px rgba(23, 25, 28, 0.18)">${esc(n.label)}</div>`;
      }
      if (n.kind === 'head') {
        const pct = Math.round(100 * n.done / n.total);
        return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: center; gap: 8px; padding: 10px 14px; border-radius: 12px; background: ${s.card}; border: 1px solid ${lk ? s.line : border}; ${shadow}">
  <div style="display: flex; align-items: center; justify-content: space-between; font-family: ${s.body}; font-size: 15px; font-weight: 600; color: ${color}; letter-spacing: -0.01em"><span style="display: flex; align-items: center; gap: 8px">${esc(n.label)}${lk ? lock(s.muted) : ''}</span><span style="font-family: ${s.mono}; font-size: 12px; font-weight: 500; color: ${s.muted}">${n.done}/${n.total}</span></div>
  <div style="height: 6px; border-radius: 999px; background: ${s.line}; overflow: hidden"><div style="width: ${pct}%; height: 100%; border-radius: 999px; background: ${lit || act ? s.ink : s.line}"></div></div>
</div>`;
      }
      return `<div style="position: absolute; left: ${n.x}px; top: ${n.y}px; width: ${n.w}px; height: ${n.h}px; box-sizing: border-box; display: flex; align-items: center; gap: 8px; padding: 0 10px; border-radius: 10px; background: ${bg}; border: 1px solid ${border}; ${shadow} font-family: ${s.body}; font-size: ${n.kind === 'mid' ? 13 : 12.5}px; font-weight: ${n.kind === 'mid' ? 600 : 500}; color: ${color}">${lk ? lock(s.muted) : box}<span style="flex-grow: 1; line-height: 1.15; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden">${esc(n.label)}</span></div>`;
    }
  }
};

// ---------- assemble one artboard ----------
function artboard(name, s) {
  const { nodes, edges } = layout();
  const paths = edges.map((e) => {
    const stroke = e.lit ? s.strokeLit : s.strokeDim;
    const extra = s.glow && e.lit ? ` style="filter: drop-shadow(0 0 6px rgba(62, 230, 193, 0.7))"` : '';
    const dash = s.dash && !e.lit ? ` stroke-dasharray="${s.dash}"` : '';
    return `<path d="${pathD(e, s.connector)}" fill="none" stroke="${stroke}" stroke-width="${s.strokeW}" stroke-linejoin="round" stroke-linecap="round"${dash}${extra}></path>`;
  }).join('\n    ');
  const nodeHtml = nodes.map((n) => s.node(n, s)).join('\n  ');
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
<div style="position: absolute; left: ${TREE_X}px; top: ${TREE_Y}px; width: ${TREE_W}px; height: ${TREE_H}px">
  <svg width="${TREE_W}" height="${TREE_H}" viewBox="0 0 ${TREE_W} ${TREE_H}" style="position: absolute; left: 0; top: 0">
    ${paths}
  </svg>
  ${nodeHtml}
</div>
</div>
</x-dc>
</body>
</html>
`;
}

for (const [name, s] of Object.entries(styles)) {
  writeFileSync(new URL(`./${name === 'Main' ? 'Blueprint' : name}.dc.html`, import.meta.url), artboard(name, s));
}

const canvas = {
  artboards: [
    { file: 'Blueprint.dc.html', title: 'A · Blueprint', x: 0, y: 0, w: 1440, h: 820 },
    { file: 'Constellation.dc.html', title: 'B · Constellation', x: 1560, y: 0, w: 1440, h: 820 },
    { file: 'Ledger.dc.html', title: 'C · Ledger', x: 0, y: 1080, w: 1440, h: 820 },
    { file: 'Studio.dc.html', title: 'D · Studio', x: 1560, y: 1080, w: 1440, h: 820 }
  ],
  annotations: [
    { id: 'brief', x: -420, y: 0, w: 360, text: 'Branchwork: four directions for the skill-tree task view.\n\nSame project, same tree, same data on every board so only the visual language differs. Root task at top, three branches, tasks cascading down each branch. States shown: done, in progress (amber / red), not started, and locked (blocked by an unfinished parent).\n\nPick one and the login screen, task drawer and empty states get built in that direction.' },
    { id: 'a-note', x: 0, y: -150, w: 520, text: 'A · Blueprint. Drafting sheet on grid paper, cyan ink, mono labels, dashed outlines for work in hand.\nFor: an engineer’s planning tool that feels like a drawing set. Progress reads as a segmented ink bar.\nTrade-off: dark and technical; less warm for non-engineering users.' },
    { id: 'b-note', x: 1560, y: -150, w: 520, text: 'B · Constellation. Game skill tree: lit paths, glowing orbs, locked branches, a level-up ring.\nFor: motivation. Completed paths visibly light up and the next unlock is always named.\nTrade-off: the strongest personality, so the least neutral; can feel playful for client-facing use.' },
    { id: 'c-note', x: 0, y: 930, w: 520, text: 'C · Ledger. Paper and ink, serif headings, hairline connectors, a printed checklist that branches.\nFor: calm and readable; prints beautifully. Red ink marks what is in hand.\nTrade-off: least “visual progress” pop; relies on typography rather than colour.' },
    { id: 'd-note', x: 1560, y: 930, w: 520, text: 'D · Studio. Light product UI: soft cards, one green accent, progress bars in every branch head.\nFor: the safest, most familiar SaaS feel; easiest to extend with drawers, filters and settings.\nTrade-off: the most generic of the four.' }
  ],
  launch: { view: 'canvas' }
};
writeFileSync(new URL('./canvas.json', import.meta.url), JSON.stringify(canvas, null, 2));
console.log('wrote', Object.keys(styles).map((k) => `${k}.dc.html`).join(', '), 'and canvas.json');
