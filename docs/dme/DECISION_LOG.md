# Decision Log

## DME-001 — music-studio owns music intelligence
**Decision:** `music-studio` 升级为 Director Music Engine 主仓库。`ai-director-engine` 通过接口调用，不吞并音乐底层；`creator-os` 只编排工作流。

## DME-002 — Provider is replaceable
**Decision:** MiniMax Music 3、MusicGen、ACE-Step、ElevenLabs、Lyria 都是 Provider，不成为产品核心。核心资产是 Story→Score、Score Blueprint、Music Genome、Critic、Router、Memory。

## DME-003 — Additive migration, not UI preservation
**Decision:** 首轮不重写 82KB 单体 `App.svelte` 和 Python sidecar，是为了降低回归风险、先稳定协议；这不意味着未来 DME 必须沿用 ToneLab UI。历史 UI 是资产，不是产品约束。

## DME-004 — Deterministic first
**Decision:** 首版 Director Pipeline 用可测试规则而不是强依赖外部 LLM API。未来 LLM Agent 替换分析器，但必须继续输出同一 Score Blueprint。

## DME-005 — MiniMax Music 3 = NOW candidate
**Decision:** 重点吸收其长程结构和 structured caption 思路；按 remote/self-hosted adapter 设计，不假设普通 Mac 可直接本地运行；License/Attribution 信息进入 Provider Registry。

## DME-006 — Runtime compatibility
**Decision:** 新 DME Core 必须能将 Blueprint 编译回现有 `prompt + bpm + duration` 生成参数，从而复用现有 MusicGen / ACE-Step 链路。

## DME-007 — Product > Interaction > UI > Implementation
**Decision:** DME 正式采用集团 Product Constitution。产品能力决定交互，交互决定 UI。ToneLab 仅作为 Legacy / Local Surface；DME Core 必须 Headless-first，并允许 Web Studio、Desktop、Creator OS、AI Director Engine、专业剪辑插件和 API/SDK 使用同一核心协议。

## DME-008 — Progressive professional depth
**Decision:** 不在“小白工具”和“专业工具”之间二选一。通过 progressive disclosure（渐进式呈现）让普通用户从 `Score This` 开始，导演/工作室逐步进入 Scene、Emotion、Cue、Timeline、Motif、Stems、Director DNA；所有层级共享同一个 Project / Score Blueprint 模型。

## Known Risks

1. 还未在用户本机实际执行 `npm run dme:smoke`，因此目前只能确认代码已落库，不能宣称运行验收通过。
2. `App.svelte` 仍是大单体，但它不再拥有 DME 的未来 UI 定义权；新 Surface 可以并行建立。
3. MiniMax/ElevenLabs/Lyria 的授权与 API 能力会变化，必须由 Provider Registry 版本化管理。
4. 新 UI 设计必须先通过 Product-First UI Governance Gate，禁止直接照搬 Suno/Udio/旧 ToneLab 页面结构。
