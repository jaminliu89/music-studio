import { createScoreBlueprint } from './scoreBlueprint.js';

const RULES = [
  {
    test: /父亲|母亲|家人|回家|故乡|农村|老人|memory|father|mother|home/i,
    patch: {
      narrativeFunction: 'realization',
      emotionStart: 'ordinary',
      emotionDevelopment: 'observation',
      emotionTurn: 'realization',
      emotionPeak: 'restrained_sadness',
      emotionResolution: 'warm_afterglow',
      bpmMin: 58,
      bpmMax: 78,
      instrumentation: ['felt piano', 'soft strings', 'room ambience'],
      texture: 'human documentary, intimate, imperfect',
      rhythm: 'very sparse or absent percussion',
      intensity: 0.48,
    },
  },
  {
    test: /调查|秘密|不对劲|悬疑|真相|mystery|investigation|secret|truth/i,
    patch: {
      narrativeFunction: 'suspicion',
      emotionStart: 'uncertainty',
      emotionDevelopment: 'suspicion',
      emotionTurn: 'discovery',
      emotionPeak: 'tension',
      emotionResolution: 'unresolved',
      bpmMin: 72,
      bpmMax: 102,
      instrumentation: ['low strings', 'muted piano', 'granular texture', 'sub pulse'],
      texture: 'investigative, restrained, textural',
      rhythm: 'irregular pulse',
      intensity: 0.65,
    },
  },
  {
    test: /AI|人工智能|未来|科技|机器人|future|technology|robot/i,
    patch: {
      narrativeFunction: 'discovery',
      emotionStart: 'curiosity',
      emotionDevelopment: 'wonder',
      emotionTurn: 'expansion',
      emotionPeak: 'awe',
      emotionResolution: 'forward_motion',
      bpmMin: 82,
      bpmMax: 112,
      instrumentation: ['analog synth', 'processed piano', 'hybrid percussion', 'air texture'],
      texture: 'human-meets-machine, cinematic electronic',
      rhythm: 'measured evolving pulse',
      intensity: 0.62,
    },
  },
];

export function analyzeIntent(text = '', options = {}) {
  const normalized = String(text).trim();
  let patch = {};
  for (const rule of RULES) {
    if (rule.test.test(normalized)) {
      patch = { ...patch, ...rule.patch };
      break;
    }
  }

  const voiceoverPriority = options.mode === 'voiceover' ? 'high' : (options.voiceoverPriority ?? 'high');
  return {
    text: normalized,
    sourceKind: options.mode ?? 'scene_description',
    projectType: options.projectType ?? 'scene',
    duration: options.duration ?? 30,
    voiceoverPriority,
    ...patch,
  };
}

export function directScore(text, options = {}) {
  const analysis = analyzeIntent(text, options);
  return createScoreBlueprint({
    ...analysis,
    title: options.title ?? inferCueTitle(analysis),
  });
}

function inferCueTitle(analysis) {
  const fn = String(analysis.narrativeFunction ?? 'scene').replaceAll('_', ' ');
  return fn.replace(/\b\w/g, (m) => m.toUpperCase());
}
