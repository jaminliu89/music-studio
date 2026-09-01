# Director Music Engine（DME）PRD

## 1. 产品定义

ToneLab / music-studio 从“本地音乐生成器”升级为 **Director Music Engine（导演音乐引擎）**：不是另一个 Prompt→Music 包装器，而是先理解故事、镜头、旁白和情绪，再决定此刻应该出现什么音乐。

核心主张：**Story → Score / 先理解作品，再生成音乐。**

## 2. 产品边界

- `music-studio`：拥有音乐智能、Score Blueprint、Music Genome、Provider Runtime、Music Critic。
- `ai-director-engine`：拥有导演决策，可通过 API 调用 DME。
- `creator-os`：拥有创作者工作流，不直接绑定某个音乐模型。

底层模型永远可替换；上层 Director Intelligence 必须属于我们。

## 3. 用户入口

P0 输入：
1. Describe a Scene / 描述场景
2. Paste Voiceover / 粘贴旁白
3. Paste Script / 粘贴剧本
4. 现有 Text→Music

P1：Upload Video / 上传视频，自动切场景、识别对白与节奏。

## 4. 核心纵向闭环

Input → Intent → Story Analysis → Emotion Graph → Music Function → Music DNA → Score Blueprint → Provider Router → Generation → Music Critic → Result

首版不要求外部 LLM API：先用确定性 Director Heuristics 生成可验证的 Score Blueprint；以后替换为 LLM Agent 不改变协议。

## 5. 核心能力层

### Parity Layer｜竞品对齐
Text→Music、Instrumental、Lyrics/Song、Duration、BPM、Structure、Variation/Extend、History、Library、Export、Provider switching。

### Director Intelligence Layer｜导演智能
Script→Score、Voiceover→Score、Scene→Score、Narrative Function、Emotion Graph、Score Blueprint、VO-aware arrangement、Music Critic、Copyright Guard。

### Memory & Evolution Layer｜记忆进化
Music Genome、100 Music Archetypes、User Music DNA、Project Motif、Character Theme、A/B preference feedback。

## 6. Provider Strategy

- MusicGen：Fast/Local 草稿
- ACE-Step：Local Professional（保留现有外部服务方案）
- MiniMax Music 3：NOW 候选；长结构/歌曲/人声/完整编曲，作为 Provider，不成为产品本身
- ElevenLabs Music：Premium Video / API Provider
- Google Lyria：Premium / Multimodal / Future realtime

统一通过 Canonical Provider Adapter 接入。

## 7. MVP DoD

必须可验证：
- 输入一句场景描述；
- 自动得到 Story Analysis + Emotion Arc + Narrative Function；
- 输出合法 Score Blueprint JSON；
- Router 给出 provider + reason；
- 能把 Blueprint 编译成现有 `/generate` 可消费的 prompt/BPM/duration 参数；
- 不破坏现有 ToneLab 生成流程；
- 所有新 Provider 不得直接侵入 UI 业务逻辑。

## 8. 不做

首版不做 DAW、全轨道编辑器、社区、音乐分发、模型训练、完整影视后期工作站。