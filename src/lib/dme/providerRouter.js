export function routeProvider(blueprint, context = {}) {
  const localOnly = context.privacyMode === 'local_only';
  const wantsVocals = Boolean(context.requiresVocals);
  const longForm = blueprint.duration > 90 || Boolean(context.requiresLongStructure);
  const premium = context.qualityPriority === 'premium';

  if (localOnly) {
    if (context.aceReady) return decision('ace-step', 'local_only + professional local engine available');
    return decision('musicgen', 'local_only + fallback to bundled/local draft engine');
  }

  if (wantsVocals || longForm) {
    return decision('minimax-music3', 'long-form structure or vocals requested');
  }

  if (context.videoContext && premium) {
    return decision('elevenlabs-music', 'premium video-scoring path');
  }

  if (premium) {
    return decision('lyria', 'premium quality path');
  }

  if (context.aceReady) return decision('ace-step', 'balanced local professional path');
  return decision('musicgen', 'fast local draft path');
}

export function compileForCurrentRuntime(blueprint) {
  const m = blueprint.music;
  const bpm = Math.round((m.bpm.min + m.bpm.max) / 2);
  const prompt = [
    `Narrative function: ${blueprint.narrative.function}.`,
    `Emotional arc: ${blueprint.emotion.start} -> ${blueprint.emotion.development} -> ${blueprint.emotion.turn} -> ${blueprint.emotion.peak} -> ${blueprint.emotion.resolution}.`,
    `Instrumentation: ${m.instrumentation.join(', ')}.`,
    `Texture: ${m.texture}. Rhythm: ${m.rhythm}.`,
    `Harmony: ${m.harmony}. Dynamics: ${m.dynamics}.`,
    `Voiceover priority: ${blueprint.voiceover.priority}; keep midrange ${blueprint.voiceover.midrangeSpace}.`,
    `Structure: ${blueprint.structure.map((s) => `${s.function} ${s.start}-${s.end}s`).join('; ')}.`,
    `Avoid: ${blueprint.constraints.avoid.join(', ')}.`,
  ].join(' ');

  return {
    prompt,
    bpm,
    duration: blueprint.duration,
    instrumental: true,
    scoreBlueprintVersion: blueprint.version,
  };
}

function decision(provider, reason) {
  return { provider, reason };
}
