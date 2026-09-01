const VARIANT_PATCHES = {
  director: (blueprint) => ({
    ...blueprint,
    variant: 'director',
    variantLabel: 'Director Pick',
  }),
  restrained: (blueprint) => ({
    ...blueprint,
    variant: 'restrained',
    variantLabel: 'Restrained',
    music: {
      ...blueprint.music,
      intensity: Math.max(0.15, (blueprint.music.intensity ?? 0.5) - 0.2),
      instrumentation: blueprint.music.instrumentation.filter((x) => !/brass|choir|big drums|epic/i.test(x)),
      dynamics: 'restrained dynamics with wider negative space',
      rhythm: /drum/i.test(blueprint.music.rhythm || '')
        ? 'minimal pulse; percussion only where structurally necessary'
        : blueprint.music.rhythm,
    },
    constraints: {
      ...blueprint.constraints,
      avoid: [...new Set([...(blueprint.constraints?.avoid || []), 'over-scoring', 'early emotional manipulation'])],
    },
  }),
  cinematic: (blueprint) => ({
    ...blueprint,
    variant: 'cinematic',
    variantLabel: 'Cinematic',
    music: {
      ...blueprint.music,
      intensity: Math.min(0.9, (blueprint.music.intensity ?? 0.5) + 0.12),
      texture: `${blueprint.music.texture}, cinematic spatial depth, controlled long-form development`,
      dynamics: 'wider cinematic dynamic arc without trailer-style excess',
    },
    constraints: {
      ...blueprint.constraints,
      avoid: [...new Set([...(blueprint.constraints?.avoid || []), 'generic trailer grammar'])],
    },
  }),
  raw: (blueprint) => ({
    ...blueprint,
    variant: 'raw',
    variantLabel: 'Raw',
    music: {
      ...blueprint.music,
      intensity: Math.max(0.2, (blueprint.music.intensity ?? 0.5) - 0.08),
      texture: `${blueprint.music.texture}, intimate room tone, human imperfection, natural decay, reduced polish`,
      dynamics: 'natural performance dynamics with restrained mastering',
    },
    constraints: {
      ...blueprint.constraints,
      avoid: [...new Set([...(blueprint.constraints?.avoid || []), 'over-polished production', 'quantized perfection'])],
    },
  }),
};

export function applyBlueprintVariant(blueprint, variant = 'director') {
  if (!blueprint) throw new Error('Blueprint is required.');
  const patch = VARIANT_PATCHES[variant] || VARIANT_PATCHES.director;
  return patch(structuredCloneSafe(blueprint));
}

export function listBlueprintVariants() {
  return [
    { id: 'director', label: 'Director Pick', zh: '导演推荐' },
    { id: 'restrained', label: 'Restrained', zh: '更克制' },
    { id: 'cinematic', label: 'Cinematic', zh: '更电影' },
    { id: 'raw', label: 'Raw', zh: '更真实' },
  ];
}

function structuredCloneSafe(value) {
  if (typeof structuredClone === 'function') return structuredClone(value);
  return JSON.parse(JSON.stringify(value));
}
