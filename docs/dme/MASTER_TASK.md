# DME Master Task

## Goal

把现有 ToneLab 升级为 Director Music Engine，同时保持现有生成能力可用。

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
- [ ] UI 接入 “Score This”
- [ ] 将 compiled payload 接到现有生成按钮
- [ ] 在真实本机运行 smoke + build

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
- [ ] conversational edit → Blueprint patch

## P2

- [ ] Video timeline scoring
- [ ] project motifs / character themes
- [ ] My Music DNA
- [ ] realtime generative score
- [ ] feedback learning loop

## Definition of Done for current milestone

当前里程碑完成条件：场景文本输入可生成 Blueprint、Provider recommendation、现有 runtime payload；代码有独立 smoke case；现有 ToneLab 文件未被侵入式重写。

当前唯一未闭环：本机实际运行 `npm run dme:smoke` 与 UI/现有 `/generate` 的真实连接。