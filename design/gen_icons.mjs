// Rasterise static/branchwork/img/logo.svg into the icon files browsers ask
// for. Outputs are committed, so this only runs when the logo changes:
//
//   npm install          (once; @resvg/resvg-js + png-to-ico, dev only)
//   node design/gen_icons.mjs
//
// resvg rather than cairo: it ships a prebuilt binary per platform, so this
// works on Windows without hunting for libcairo.
import { Resvg } from '@resvg/resvg-js';
import pngToIco from 'png-to-ico';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const IMG = join(ROOT, 'static', 'branchwork', 'img');
const LOGO = join(IMG, 'logo.svg');

// iOS composites its own rounded mask over the square and renders a
// transparent touch icon on black, so that one gets an opaque plate.
const APP_BG = '#15181d';
const TOUCH_SIZE = 180;
const TOUCH_INSET = 0.68;   // share of the square the mark occupies

const source = readFileSync(LOGO, 'utf8');

/** The logo's own viewBox, so the nested wrapper below scales correctly. */
function viewBox(svg) {
  const m = svg.match(/viewBox\s*=\s*"([^"]+)"/i);
  if (!m) throw new Error('logo.svg has no viewBox');
  return m[1];
}

/** Everything inside the outer <svg> element, prologue and doctype stripped. */
function innerMarkup(svg) {
  const open = svg.indexOf('<svg');
  const gt = svg.indexOf('>', open);
  const close = svg.lastIndexOf('</svg>');
  if (open < 0 || close < 0) throw new Error('logo.svg is not an svg');
  return svg.slice(gt + 1, close);
}

function render(svg, size) {
  return new Resvg(svg, { fitTo: { mode: 'width', value: size } }).render().asPng();
}

/** The mark centred on an opaque plate, as a fresh SVG for resvg to draw. */
function plated(size, inset) {
  const span = Math.round(size * inset);
  const offset = Math.round((size - span) / 2);
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
  <rect width="${size}" height="${size}" fill="${APP_BG}"/>
  <svg x="${offset}" y="${offset}" width="${span}" height="${span}" viewBox="${viewBox(source)}">${innerMarkup(source)}</svg>
</svg>`;
}

const written = [];
for (const size of [16, 32]) {
  const file = join(IMG, `favicon-${size}.png`);
  writeFileSync(file, render(source, size));
  written.push(`favicon-${size}.png`);
}

writeFileSync(join(IMG, 'apple-touch-icon.png'), render(plated(TOUCH_SIZE, TOUCH_INSET), TOUCH_SIZE));
written.push('apple-touch-icon.png');

// One .ico carrying the small sizes, for browsers and Windows pinned sites
// that still ignore the SVG.
const ico = await pngToIco([16, 32, 48].map((s) => render(source, s)));
writeFileSync(join(IMG, 'favicon.ico'), ico);
written.push('favicon.ico');

console.log('wrote', written.join(', '), 'from logo.svg');
