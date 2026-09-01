import { invoke } from '@tauri-apps/api/core';

const LOCAL_PROVIDER_TO_ENGINE = {
  'musicgen': 'musicgen-small',
  'ace-step': 'acestep-v15-turbo',
};

export async function getRuntimeCapabilities() {
  try {
    const models = await invoke('list_models');
    const ready = Array.isArray(models) ? models.filter((m) => m.status === 'ready') : [];
    return {
      environment: 'tauri',
      ready: ready.length > 0,
      models: ready,
      engines: ready.map((m) => m.id),
    };
  } catch (error) {
    return {
      environment: 'browser',
      ready: false,
      models: [],
      engines: [],
      error: String(error),
    };
  }
}

export async function generateFromBlueprint({ blueprint, routing, runtimePayload, variant = 'director' }) {
  const capabilities = await getRuntimeCapabilities();
  if (!capabilities.ready) {
    return {
      success: false,
      status: 'runtime_unavailable',
      requestedProvider: routing?.provider,
      error: capabilities.error || 'No ready local generation engine.',
      capabilities,
    };
  }

  const engine = resolveEngine(routing?.provider, capabilities.engines);
  const filename = buildFilename(blueprint, variant);
  const prompt = applyVariantPrompt(runtimePayload.prompt, variant);

  try {
    const result = await invoke('generate_music', {
      engine,
      prompt,
      duration: Math.max(3, Math.round(runtimePayload.duration)),
      filename,
      guidanceScale: 3.0,
      temperature: variant === 'raw' ? 1.08 : 1.0,
      topK: 250,
      topP: 0,
    });

    if (!result?.success) {
      return {
        success: false,
        status: 'failed',
        requestedProvider: routing?.provider,
        actualEngine: engine,
        error: result?.error || 'Generation failed.',
      };
    }

    const bytes = await invoke('read_audio_file', { path: result.path });
    const blob = new Blob([new Uint8Array(bytes)], { type: 'audio/wav' });

    return {
      success: true,
      status: 'ready',
      requestedProvider: routing?.provider,
      actualEngine: engine,
      fallbackUsed: !providerMatchesEngine(routing?.provider, engine),
      path: result.path,
      audioUrl: URL.createObjectURL(blob),
      duration: result.duration,
      generationTime: result.generation_time,
      rtf: result.rtf,
      scoreBlueprintVersion: blueprint.version,
      variant,
      provenance: {
        requestedProvider: routing?.provider,
        actualEngine: engine,
        routeReason: routing?.reason,
        generatedAt: new Date().toISOString(),
      },
    };
  } catch (error) {
    return {
      success: false,
      status: 'failed',
      requestedProvider: routing?.provider,
      actualEngine: engine,
      error: String(error),
    };
  }
}

function resolveEngine(provider, readyEngines) {
  const direct = LOCAL_PROVIDER_TO_ENGINE[provider];
  if (direct && readyEngines.includes(direct)) return direct;
  if (readyEngines.includes('acestep-v15-turbo')) return 'acestep-v15-turbo';
  if (readyEngines.includes('musicgen-small')) return 'musicgen-small';
  return readyEngines[0];
}

function providerMatchesEngine(provider, engine) {
  return LOCAL_PROVIDER_TO_ENGINE[provider] === engine;
}

function applyVariantPrompt(prompt, variant) {
  const additions = {
    director: 'Follow the director blueprint faithfully.',
    restrained: 'Use less instrumentation, more negative space, lower emotional manipulation, restrained dynamics.',
    cinematic: 'Increase cinematic depth, spatial scale and long-form development without becoming generic trailer music.',
    raw: 'Favor human imperfection, intimate room texture, natural performance variation and reduced polish.',
  };
  return `${prompt} ${additions[variant] || additions.director}`;
}

function buildFilename(blueprint, variant) {
  const safe = String(blueprint.title || 'score')
    .replace(/[^a-zA-Z0-9\u4e00-\u9fa5_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 42) || 'score';
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  return `DME-${safe}-${variant}-${stamp}.wav`;
}
