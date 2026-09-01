# Provider Capability Registry

## Canonical Provider Contract

每个 Provider 只负责把 `ScoreBlueprint` 转换成自身 API / 本地推理参数，并返回统一 `GenerationResult`。上层不得依赖 provider-specific 字段。

### MusicGen
- role: local_fast
- status: active
- strengths: 本地、轻量、快速草稿
- limits: 长程结构弱；>30s 依赖分段生成
- license/deployment: 保持现有实现

### ACE-Step
- role: local_pro
- status: active_external_service
- strengths: 结构感、48kHz 立体声、比 MusicGen 更完整
- limits: 本机资源重；与其他大模型并发需内存保护
- integration: 现有 HTTP 外部服务，继续保留

### MiniMax Music 3
- role: long_form_song / structured_music
- status: NOW_CANDIDATE
- strengths: 长结构、歌曲、人声、结构化 caption、完整编曲
- integration rule: 仅作为 Provider；优先吸收其 caption-rewriter 思路到我们的 Prompt Compiler，不复制产品模型
- deployment: 高 GPU 需求，首版按 remote/self-hosted provider adapter 设计
- compliance: Registry 必须保存 license、attribution、commercial threshold、model version

### ElevenLabs Music
- role: premium_video_music
- status: P1
- strengths: composition plan、video-to-music、结构化 API、stems/metadata 能力
- compliance: film/TV 商业授权范围必须由 License Guard 判断

### Google Lyria
- role: premium_multimodal / future_realtime
- status: P1/P2
- strengths: 高质量音乐、多模态、生态、实时方向
- constraint: closed provider / API black box

## Router Dimensions

- project_type
- target_duration
- requires_vocals
- requires_long_structure
- privacy_mode
- latency_priority
- quality_priority
- video_context
- realtime_required
- local_compute_budget
- commercial_license_scope

任何新增 Provider 必须先实现 `supports(blueprint, context)` 与 `compile(blueprint)`，禁止在 UI 中硬编码模型名。