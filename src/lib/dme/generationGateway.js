import { invoke } from '@tauri-apps/api/core';
import { compileForCurrentRuntime } from './providerRouter.js';
import { applyBlueprintVariant } from './blueprintVariants.js';

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

  const variantBlueprint = applyBlueprintVariant(blueprint, variant);
  const compiled = compileForCurrentRuntime(variantBlueprint);
  const effectiveRuntime = { ...(runtimePayload || {}), ...compiled };
  const engine = resolveEngine(routing?.provider, capabilities.engines);
  const filename = buildFilename(variantBlueprint, variant);

  try {
    const result = await invoke('generate_music', {
      engine,
      prompt: effectiveRuntime.prompt,
      duration: Math.max(3, Math.round(effectiveRuntime.duration)),
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
        variant,
        variantBlueprint,
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
      scoreBlueprintVersion: variantBlueprint.version,
      variant,
      variantBlueprint,
      compiledRuntime: effectiveRuntime,
      provenance: {
        requestedProvider: routing?.provider,
        actualEngine: engine,
        routeReason: routing?.reason,
        variant,
        scoreBlueprintVersion: variantBlueprint.version,
        generatedAt: new Date().toISOString(),
      },
    };
  } catch (error) {
    return {
      success: false,
      status: 'failed',
      requestedProvider: routing?.provider,
      actualEngine: engine,
      variant,
      variantBlueprint,
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

function buildFilename(blueprint, variant) {
  const safe = String(blueprint.title || 'score')
    .replace(/[^a-zA-Z0-9\u4e00-\u9fa5_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 42) || 'score';
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  return `DME-${safe}-${variant}-${stamp}.wav`;
}
