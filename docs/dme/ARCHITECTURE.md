# DME Architecture

```text
FE: Svelte / Tauri
  ↓
DME API Facade
  ↓
Director Intelligence
  ├─ Story Analyzer
  ├─ Scene Analyzer
  ├─ Emotion Graph
  ├─ Music Director
  ├─ Copyright Guard
  └─ Music Critic
  ↓
Canonical Score Blueprint
  ↓
Provider Router
  ├─ MusicGen Adapter
  ├─ ACE-Step Adapter
  ├─ MiniMax Music 3 Adapter
  ├─ ElevenLabs Adapter
  └─ Lyria Adapter
  ↓
Existing Generation Runtime
  ↓
Audio + score.json + provider metadata
```

## Architecture Principles

1. Provider capability != product capability.
2. No provider-specific fields above the adapter boundary.
3. UI talks to DME intent/schema, not directly to provider prompts.
4. Existing MusicGen/ACE-Step runtime remains operational during migration.
5. Canonical `ScoreBlueprint` is the contract between Director Intelligence and model execution.
6. New intelligence can start deterministic and later move to LLM/Agent without breaking clients.

## State Machine

S0 INPUT
→ S1 INTENT
→ S2 STORY_ANALYSIS
→ S3 SCENE_SEGMENTATION
→ S4 EMOTION_GRAPH
→ S5 MUSIC_FUNCTION
→ S6 MUSIC_DNA
→ S7 SCORE_BLUEPRINT
→ S8 MODEL_ROUTING
→ S9 GENERATION
→ S10 MUSIC_CRITIC
→ S11 EDIT_ADAPTATION
→ S12 EXPORT
→ S13 FEEDBACK
→ S14 MEMORY

Moat: S2–S7 + S10 + S13–S14. S9 is replaceable infrastructure.

## Migration Strategy

Phase 0 is additive only: create `src/lib/dme/*` and docs, compile Blueprint into current generate parameters. Do not rewrite `App.svelte` or Python sidecar until the contract is stable.

Phase 1 adds one new UI entry: “Score This / 为场景配乐”, displaying analysis, Blueprint and router recommendation before generation.

Phase 2 adds MiniMax/Eleven/Lyria adapters behind the same interface.