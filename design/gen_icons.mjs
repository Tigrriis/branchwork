// Build the icon files browsers ask for from static/branchwork/img/logo.svg.
// Outputs are committed, so this only runs when the logo changes:
//
//   npm install          (once; @resvg/resvg-js + png-to-ico, dev only)
//   node design/gen_icons.mjs
//
// resvg rather than cairo: it ships a prebuilt binary per platform, so this
// works on Windows without hunting for libcairo.
//
// logo.svg itself stays bare: the app's header draws it on the dark top bar.
// Every icon that lands in a browser tab or on a home screen gets the app's
// dark ground behind the mark instead, because the mark is drawn in white and
// vanishes on a light tab strip.
import { Resvg } from '@resvg/resvg-js';
import pngToIco from 'png-to-ico';
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const IMG = join(ROOT, 'static', 'branchwork', 'img');
const LOGO = join(IMG, 'logo.svg');

const APP_BG = '#15181d';

// Tab icons: a rounded plate with the mark filling most of it, since at
// 16px every pixel of mark counts.
const FAVICON_UNITS = 64;
const FAVICON_INSET = 0.86;     // share of the plate the mark occupies
const FAVICON_RADIUS = 14;      // in FAVICON_UNITS

// iOS applies its own rounded mask, so the touch icon is a plain square with
// more room around the mark.
const TOUCH_SIZE = 180;
const TOUCH_INSET = 0.68;

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

/** The mark centred on the app's ground, as a standalone SVG. */
function plated(units, inset, radius = 0) {
  const span = units * inset;
  const offset = (units - span) / 2;
  // xlink declared too: Affinity exports reference embedded images through it.
  return `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${units}" height="${units}" viewBox="0 0 ${units} ${units}">
  <rect width="${units}" height="${units}" rx="${radius}" fill="${APP_BG}"/>
  <svg x="${offset}" y="${offset}" width="${span}" height="${span}" viewBox="${viewBox(source)}">${innerMarkup(source)}</svg>
</svg>
`;
}

const favicon = plated(FAVICON_UNITS, FAVICON_INSET, FAVICON_RADIUS);
const written = [];

// The vector tab icon most browsers now prefer.
writeFileSync(join(IMG, 'favicon.svg'), favicon);
written.push('favicon.svg');

for (const size of [16, 32]) {
  writeFileSync(join(IMG, `favicon-${size}.png`), render(favicon, size));
  written.push(`favicon-${size}.png`);
}

writeFileSync(join(IMG, 'apple-touch-icon.png'), render(plated(TOUCH_SIZE, TOUCH_INSET), TOUCH_SIZE));
written.push('apple-touch-icon.png');

// One .ico carrying the small sizes, for browsers and Windows pinned sites
// that still ignore the SVG.
const ico = await pngToIco([16, 32, 48].map((s) => render(favicon, s)));
writeFileSync(join(IMG, 'favicon.ico'), ico);
written.push('favicon.ico');

console.log('wrote', written.join(', '), 'from logo.svg');
