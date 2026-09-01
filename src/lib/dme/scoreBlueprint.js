export const SCORE_BLUEPRINT_VERSION = '0.1.0';

export function createScoreBlueprint(input = {}) {
  const duration = clampNumber(input.duration ?? 30, 5, 600);
  const bpmMin = clampNumber(input.bpmMin ?? 68, 40, 220);
  const bpmMax = clampNumber(input.bpmMax ?? 92, bpmMin, 240);

  return {
    schema: 'dme.score-blueprint',
    version: SCORE_BLUEPRINT_VERSION,
    projectType: input.projectType ?? 'scene',
    title: input.title ?? 'Untitled Cue',
    duration,
    source: {
      kind: input.sourceKind ?? 'scene_description',
      text: String(input.text ?? '').trim(),
    },
    narrative: {
      function: input.narrativeFunction ?? 'establish_world',
      subject: input.subject ?? null,
      pointOfView: input.pointOfView ?? 'observer',
      subtext: input.subtext ?? null,
    },
    emotion: {
      start: input.emotionStart ?? 'neutral',
      development: input.emotionDevelopment ?? 'curiosity',
      turn: input.emotionTurn ?? 'realization',
      peak: input.emotionPeak ?? 'restrained_emotion',
      resolution: input.emotionResolution ?? 'open',
      intensity: clampNumber(input.intensity ?? 0.55, 0, 1),
    },
    music: {
      bpm: { min: bpmMin, max: bpmMax },
      key: input.key ?? null,
      timeSignature: input.timeSignature ?? '4/4',
      instrumentation: input.instrumentation ?? ['soft piano', 'warm strings', 'subtle texture'],
      texture: input.texture ?? 'restrained cinematic',
      rhythm: input.rhythm ?? 'sparse pulse',
      harmony: input.harmony ?? 'simple, unresolved-to-gentle-resolution',
      dynamics: input.dynamics ?? 'controlled, dialogue-safe',
      melodyDensity: input.melodyDensity ?? 'low',
      acousticElectronicRatio: input.acousticElectronicRatio ?? 0.7,
    },
    voiceover: {
      priority: input.voiceoverPriority ?? 'high',
      midrangeSpace: input.midrangeSpace ?? 'protected',
      denseDrumsAllowed: input.denseDrumsAllowed ?? false,
    },
    structure: input.structure ?? defaultStructure(duration),
    constraints: {
      avoid: input.avoid ?? [
        'generic corporate inspirational',
        'constant trailer drums',
        'predictable four-chord pop',
        'overly sentimental scoring',
      ],
      copyrightMode: input.copyrightMode ?? 'mechanism_only',
    },
    metadata: {
      createdBy: 'dme-director-pipeline',
      createdAt: new Date().toISOString(),
    },
  };
}

function defaultStructure(duration) {
  const a = round(duration * 0.15);
  const b = round(duration * 0.42);
  const c = round(duration * 0.72);
  const d = round(duration * 0.9);
  return [
    { start: 0, end: a, function: 'hook' },
    { start: a, end: b, function: 'establish' },
    { start: b, end: c, function: 'develop' },
    { start: c, end: d, function: 'peak' },
    { start: d, end: duration, function: 'resolution' },
  ];
}

function clampNumber(value, min, max) {
  const n = Number(value);
  if (!Number.isFinite(n)) return min;
  return Math.max(min, Math.min(max, n));
}

function round(n) {
  return Math.round(n * 10) / 10;
}
