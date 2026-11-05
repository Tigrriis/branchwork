const {chromium}=require('playwright');
const S={land:[1200,628],sq:[1080,1080],tall:[1080,1350]};
(async()=>{const b=await chromium.launch();
for(const ad of [1,2,3,4])for(const f in S){const [w,h]=S[f];
const p=await b.newPage({viewport:{width:w,height:h}});
await p.goto(`file://${process.cwd()}/ad.html?ad=${ad}&fmt=${f}`);await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(200);
await p.screenshot({path:`out/villainy-ad${ad}-${f}-${w}x${h}.png`});await p.close();}
await b.close();})();
