# DME Master Task

## Goal

把现有 ToneLab 演化为 Director Music Engine，同时保留旧本地生成能力，但不让旧 UI / 技术形态限制 DME 的产品上限。

Parent rule: `skill-hub/docs/PRODUCT_CONSTITUTION.md`

## P0 — Vertical Slice

- [x] 产品定义 / PRD
- [x] 架构边界
- [x] Capability Matrix
- [x] Provider Registry
- [x] Canonical Score Blueprint
- [x] Deterministic Director Pipeline
- [x] Provider Router
- [x] Compile Blueprint → current runtime payload
- [x] Smoke test fixture
- [x] npm command: `npm run dme:smoke`
- [x] Product-first UX Architecture
- [x] 独立 DME Product Surface
- [x] Runtime-connected DME Studio (`src/DMEStudio.svelte`)
- [x] DME 设为默认入口
- [x] ToneLab 保留为 Legacy / Local Surface (`?legacy=1`)
- [x] UI 接入 `Score This`
- [x] UI 显示 Story Intelligence / Emotion Arc / Score Blueprint / Provider Routing
- [x] conversational direction v0：自然语言修改 Blueprint（克制 / 去鼓 / 更电影）
- [x] `GenerationGateway` 隔离 Surface 与 Tauri/local engine
- [x] DME → Provider Router → runtime adapter → Tauri `generate_music`
- [x] runtime capability discovery (`list_models`)
- [x] 云端 Provider 不可用时回退到 ACE-Step / MusicGen，并记录 requested provider / actual engine
- [x] 真实音频读取协议已接入 (`read_audio_file` → Blob URL → `<audio>`)
- [x] 结果 provenance（requested provider / actual engine / reason / generatedAt）
- [ ] 在用户真实本机确认第一次 Story → Score 音频成功生成并播放
- [ ] 在真实本机运行 `npm run dme:smoke` + `npm run build`

## P0.5 — Product Surface Closure

目标：不是 Demo 页面，而是完成第一次可听见的 Story → Score 闭环。

- [x] 建立 `GenerationGateway`
- [x] Director Pick / Restrained / Cinematic / Raw 四种版本进入真实生成入口
- [x] 生成状态：directing / ready_to_generate / generating / ready / failed/runtime_unavailable
- [x] 音频播放器 + generation metadata
- [x] Provider fallback 对普通用户隐藏底层复杂度，同时保留 provenance
- [ ] A/B/C/D 从“prompt-level variant”升级为规范化 Blueprint variant patch
- [ ] Project persistence：保存 Project + Blueprint + routing + results
- [ ] Music Critic 插入 generation → critique → rank
- [ ] waveform / cue-level result visualization

## P1 — Provider Adapters

- [ ] MiniMax Music 3 adapter
- [ ] ElevenLabs Music adapter
- [ ] Lyria adapter
- [ ] Provider health / capability discovery v2（云端 + 本地统一）
- [ ] License Guard
- [ ] Provider result normalization

## P1 — Director Intelligence

- [ ] Story Analyzer LLM adapter
- [ ] Scene segmentation
- [ ] Emotion Graph v1
- [ ] Music Critic loop
- [ ] Director Music Library 100 → Music Genome JSON
- [ ] conversational edit → generic Blueprint patch engine

## P2 — Professional Workspace

- [ ] Video timeline scoring
- [ ] dialogue regions / ducking intelligence
- [ ] cue in/out editing
- [ ] project motifs / character themes
- [ ] My Music DNA
- [ ] Director DNA
- [ ] stems / cue sheet / export families
- [ ] realtime generative score
- [ ] feedback learning loop

## Definition of Done for current milestone

当前代码层已经具备：

`Scene / Script / Voiceover → Director Intelligence → Score Blueprint → Provider Router → GenerationGateway → Tauri local engine → Audio Result`

但当前里程碑仍不能宣称完成，直到真实设备完成以下验收：

1. 新 DME Studio 可启动。
2. `Score This` 正常生成 Blueprint。
3. `Generate Director Pick` 调用至少一个真实已安装引擎。
4. wav 返回并可在 DME Studio 内播放。
5. Provider fallback / provenance 显示正确。
6. ToneLab `?legacy=1` 仍正常可用。
7. `npm run dme:smoke` 与 `npm run build` 通过。

当前唯一主线阻塞：**真实运行环境验收，而不是继续扩写产品文档。**
