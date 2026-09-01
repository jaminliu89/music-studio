# DME UX Architecture｜体验架构

Status: ACTIVE
Parent rule: skill-hub/docs/PRODUCT_CONSTITUTION.md

## Product Essence
Director Music Engine is not a prompt-to-music page and not a lightweight DAW. It understands a creative work and directs music for the work.

> Story → Understanding → Score Blueprint → Music → Critique → Adaptation

## UX Principle
Do not begin from ToneLab's existing pages. Begin from creator intent.

### Four primary intents
1. Describe a Scene｜描述一个场景
2. Paste Script / Voiceover｜粘贴剧本或旁白
3. Upload Video｜上传视频
4. Explore Music Genome｜从导演音乐范式寻找方向

All four converge into one project model and one Score Blueprint protocol.

## Progressive Workspace

### Level 1 — Instant Director
For ordinary creators.
- Input material
- Score This
- Director Pick / Restrained / Cinematic / Emotional variants
- Natural-language revision

No musical expertise required.

### Level 2 — Scene Director
For serious creators.
- Scene segmentation
- Narrative function
- Emotion curve
- Cue in/out
- Dialogue priority
- Music role
- Version comparison

### Level 3 — Scoring Workspace
For directors/studios.
- Video timeline
- Dialogue regions
- Emotion graph
- Music sections
- Character motifs
- Cue sheet
- Stems
- Project DNA
- Director DNA

Progressive disclosure: professional depth appears when needed; it must not burden first-time users.

## Product Surfaces
DME Core must support multiple replaceable surfaces:
- Web Studio
- Mac/Desktop Studio
- Creator OS embedded module
- AI Director Engine plugin
- Future Premiere / Resolve / Final Cut integrations
- API / SDK

ToneLab becomes a legacy/local surface, not the product definition.

## Headless Boundary
The following MUST remain usable without UI:
- Story analysis
- Scene analysis
- Emotion graph
- Narrative function inference
- Score Blueprint
- Music Genome lookup
- Prompt Compiler
- Provider Router
- Music Critic
- Copyright/License Guard
- Music DNA / feedback memory

## Canonical Workspace Concept
Main workspace should prioritize the creative work, not the prompt:

- Center: film/video/story context
- Left: scenes / narrative / emotion
- Bottom: dialogue + emotion + music timeline
- Right or contextual panel: Director conversation and controls
- Version rail: Director Pick / Restrained / Cinematic / Emotional

Natural-language direction is first-class: “这里太煽情，把弦乐拿掉，晚 8 秒进入。” should mutate Score Blueprint rather than merely append text to a prompt.

## Anti-Patterns
- Giant prompt box as product homepage
- Genre grid as primary IA
- Copying Suno/Udio layouts
- Forcing every capability into current App.svelte
- Building a full DAW before validating Story→Score
- Exposing provider/model complexity to ordinary users
- Treating component library constraints as product requirements

## MVP Surface
First new DME surface validates:

Scene/Script input → Director interpretation → visible Score Blueprint summary → 3–4 directed variants → Provider Router → generation → compare → natural-language revision.

It may coexist with ToneLab instead of replacing it immediately.

## DoD
UX architecture is accepted when:
- Core flow can be described without screen names.
- Current ToneLab UI is not required by the DME domain model.
- Same Score Blueprint can serve at least desktop + web/API conceptually.
- Beginner and professional modes share one project model.
- Provider selection remains behind Router.
- UI can be redesigned without rewriting Director Intelligence.
