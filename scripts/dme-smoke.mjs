import { directScore } from '../src/lib/dme/directorPipeline.js';
import { compileForCurrentRuntime, routeProvider } from '../src/lib/dme/providerRouter.js';

const cases = [
  {
    name: 'human-documentary',
    text: '黄昏，父亲骑着三轮车回家，儿子站在路边看着他慢慢变老。',
    options: { duration: 45, mode: 'voiceover' },
    context: { aceReady: true },
  },
  {
    name: 'ai-future',
    text: '人工智能第一次开始理解这座城市里普通人的生活。',
    options: { duration: 30, mode: 'voiceover' },
    context: { qualityPriority: 'premium' },
  },
  {
    name: 'mystery',
    text: '调查继续深入，我们终于发现事情从一开始就不对劲。',
    options: { duration: 60 },
    context: { privacyMode: 'local_only', aceReady: false },
  },
];

for (const c of cases) {
  const blueprint = directScore(c.text, c.options);
  const routing = routeProvider(blueprint, c.context);
  const runtime = compileForCurrentRuntime(blueprint);

  if (blueprint.schema !== 'dme.score-blueprint') throw new Error(`${c.name}: invalid schema`);
  if (!runtime.prompt || !runtime.duration || !runtime.bpm) throw new Error(`${c.name}: invalid runtime payload`);
  if (!routing.provider) throw new Error(`${c.name}: no provider selected`);

  console.log(`\n[${c.name}]`);
  console.log(JSON.stringify({ blueprint, routing, runtime }, null, 2));
}

console.log('\nDME smoke test: PASS');
