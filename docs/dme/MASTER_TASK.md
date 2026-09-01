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
- [x] 独立 DME Product Surface (`src/DMEApp.svelte`)
- [x] DME 设为默认入口
- [x] ToneLab 保留为 Legacy / Local Surface (`?legacy=1`)
- [x] UI 接入 `Score This`
- [x] UI 显示 Story Intelligence / Emotion Arc / Score Blueprint / Provider Routing
- [x] conversational direction v0：自然语言修改 Blueprint（首个“更克制/去弦乐”规则）
- [x] 编译后的 current runtime payload 可在 DME Surface 查看
- [ ] 将 Generate Versions 真正接入现有 `/generate` / Tauri command
- [ ] 真实音频结果回到 DME versions rail
- [ ] 在真实本机运行 `npm run dme:smoke` + `npm run build`

## P0.5 — Product Surface Closure

目标：不是 Demo 页面，而是完成第一次可听见的 Story → Score 闭环。

- [ ] 建立 `GenerationGateway`，隔离 Surface 与 Tauri/local engine
- [ ] `Generate Versions` → Provider Router → current runtime adapter → generation gateway
- [ ] A/B/C/D 版本定义从静态卡片升级为 Blueprint variant patch
- [ ] 生成状态：directing / queued / generating / critiquing / ready / failed
- [ ] 音频播放器 + waveform placeholder/metadata
- [ ] 保存 Project + Blueprint + routing decision + result provenance
- [ ] Local / Cloud provider unavailable 时明确 fallback，不暴露内部复杂度

## P1 — Provider Adapters

- [ ] MiniMax Music 3 adapter
- [ ] ElevenLabs Music adapter
- [ ] Lyria adapter
- [ ] Provider health / capability discovery
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

当前里程碑只有在下面全部成立时才完成：

1. 用户在新的 DME Surface 输入场景/剧本/旁白。
2. DME 生成可见的 Story Intelligence + Score Blueprint。
3. Provider Router 做出真实路由决定。
4. 点击 Generate Versions 能调用当前至少一个真实可用引擎。
5. 至少一个真实音频结果返回并可播放。
6. Blueprint、provider、生成结果元数据保持可追踪。
7. ToneLab legacy surface 仍可进入。
8. `npm run dme:smoke` 与 `npm run build` 在真实环境通过。

因此当前阶段不宣称“闭环完成”。当前唯一主线是：**把新的 DME Surface 接到真实生成 Gateway，并让第一段 Story → Score 音频真正播放出来。**
