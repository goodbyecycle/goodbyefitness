const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const OUT = '/home/user/goodbyefitness/posts';
fs.mkdirSync(OUT, { recursive: true });

// *word* = underlined emphasis
const poems = [
  `I spent too much time explaining the same hurt to people who already understood. Eventually I learned— when someone knows what hurts you and keeps doing it, the problem isn't understanding. It's *caring.*`,
  `Be careful who you show your deepest wounds to. The right people will protect them. The wrong ones will remember *exactly* where they are.`,
  `Some of the hardest battles I ever fought were in rooms where nobody knew I was fighting. So I learned to be *gentle* with people. You never know what happens after they close the door.`,
  `There were people I lost before I became the man I was trying to become. For a long time, I wished they could see me now. Eventually I realized— becoming someone they'd be proud of was *enough.*`,
  `Forgive yourself for what you didn't know when you didn't know it. Wisdom has a *cruel* habit of arriving after we needed it most.`,
  `I once mistook my willingness to keep trying for a reason someone should stay. It took me years to learn— you can love someone deeply and still have to *let* *them* *go.*`,
  `I spent years believing I was running late. Then life taught me there is no schedule for becoming who you are. Some things simply take the *time* they take.`,
  `For years I thought feeling deeply was something I needed to fix. Age taught me differently. A soft heart isn't weakness. Just learn who *deserves* to hold it.`,
  `I spent too much of my life trying to convince people to choose me. It took me years to learn— the right people don't make you *compete* for your place in their life.`,
  `People will sometimes call you weak while you're carrying things that would break them. Don't waste your strength trying to prove how heavy the load was. Just keep *walking.*`,
  `Not every person standing still has stopped trying. Some people are using every bit of strength they have just to remain standing. I learned to *ask* before I judged.`,
  `I used to think love meant someone seeing the best parts of me. I was wrong. Love is being fully seen— the beautiful, the broken, and everything between— and finding they haven't *loosened* their arms.`,
];

const fontB64 = fs.readFileSync(process.env.FONT || path.join(DIR, 'fonts/CaveatBrush.ttf')).toString('base64');

const html = `<!doctype html><html><head><style>
@font-face{font-family:B;src:url(data:font/ttf;base64,${fontB64});}
html,body{margin:0;background:#fff;}
#c{width:1080px;height:1920px;position:relative;overflow:hidden;background:#fff;}
.l{position:absolute;left:0;white-space:nowrap;font-family:B;color:#FF1493;line-height:1;transform-origin:left center;}
.u{position:relative;display:inline-block;}
.u svg{position:absolute;left:-4%;width:108%;bottom:-0.06em;height:0.16em;overflow:visible;}
#m{position:absolute;visibility:hidden;white-space:nowrap;font-family:B;font-size:100px;line-height:1;}
</style></head><body><div id="c"></div><span id="m"></span></body></html>`;

const layoutFn = (text, seed) => {
  let s = seed * 9301 + 49297;
  const rnd = () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  const W = 1080, H = 1920, PADX = 50, PADY = 70, LH = 0.86;
  const words = text.split(/\s+/);
  const m = document.getElementById('m');
  const plain = w => w.replace(/\*/g, '');
  const measure = str => { m.textContent = str; return m.getBoundingClientRect().width / 100; };
  const breakLines = c => {
    const lines = []; let cur = [];
    for (const w of words) {
      const t = [...cur, w].map(plain).join(' ');
      if (cur.length && t.length > c) { lines.push(cur); cur = [w]; } else cur.push(w);
    }
    if (cur.length) lines.push(cur);
    return lines;
  };
  const avail = W - 2 * PADX;
  let best = null;
  for (let c = 6; c <= 40; c++) {
    const lines = breakLines(c);
    const sizes = lines.map(l => Math.min(avail / measure(l.map(plain).join(' ')), 260));
    const total = sizes.reduce((a, b) => a + b * LH, 0);
    if (total <= H - 2 * PADY) { best = { lines, sizes, total }; break; }
  }
  const c = document.getElementById('c');
    const extra = 0;
  c.innerHTML = '<div id="w" style="position:absolute;left:0;top:0;width:1080px;height:1920px;transform-origin:0 0"></div>';
  const wrap = document.getElementById('w');
  let y = 0;
  best.lines.forEach((l, i) => {
    const jitter = 0.9 + rnd() * 0.1;
    const fs = best.sizes[i] * jitter;
    const div = document.createElement('div');
    div.className = 'l';
    div.style.fontSize = fs + 'px';
    div.style.top = (y - fs * 0.08) + 'px';
    const usedW = measure(l.map(plain).join(' ')) * fs;
    div.style.left = (PADX + rnd() * (avail - usedW)) + 'px';
    div.style.transform = `rotate(${(rnd() - 0.5) * 3.2}deg)`;
    div.innerHTML = l.map(w => {
      if (w.startsWith('*')) {
        const inner = w.replace(/\*/g, '');
        return `<span class="u">${inner}<svg viewBox="0 0 100 10" preserveAspectRatio="none"><path d="M2 6 Q 30 ${3 + rnd()*3}, 60 5 T 98 ${4 + rnd()*3}" stroke="#FF1493" stroke-width="3.2" fill="none" stroke-linecap="round"/></svg></span>`;
      }
      return w;
    }).join(' ');
    wrap.appendChild(div);
    y += best.sizes[i] * LH + extra;
  });
  const els = [...wrap.querySelectorAll('.l, .u svg')];
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  for (const e of els) { const r=e.getBoundingClientRect(); x0=Math.min(x0,r.left); y0=Math.min(y0,r.top); x1=Math.max(x1,r.right); y1=Math.max(y1,r.bottom); }
  const bw=x1-x0, bh=y1-y0;
  const sc=Math.min((W-2*PADX)/bw,(H-2*PADY)/bh);
  const tx=(W-bw*sc)/2 - x0*sc, ty=(H-bh*sc)/2 - y0*sc;
  wrap.style.transform=`translate(${tx}px,${ty}px) scale(${sc})`;
};

(async () => {
  const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' }).catch(() => chromium.launch());
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.setContent(html);
  await page.evaluate(() => document.fonts.load('100px B'));
  await page.evaluate(() => document.fonts.ready);
  for (let i = 0; i < poems.length; i++) {
    await page.evaluate(`(${layoutFn.toString()})(${JSON.stringify(poems[i])}, ${i + 3})`);
    const f = path.join(OUT, `post-${String(i + 1).padStart(2, '0')}.png`);
    await page.locator('#c').screenshot({ path: f });
    console.log(f);
  }
  await browser.close();
})();
