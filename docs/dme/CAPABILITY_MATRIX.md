# Capability Matrix

状态：`P0` 当前必须；`P1` 下一阶段；`P2` 长期；`Provider` 依赖底层模型。

| Capability | DME | MusicGen | ACE-Step | MiniMax Music 3 | ElevenLabs | Lyria |
|---|---|---|---|---|---|---|
| Text → Music | P0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| Instrumental | P0 | ✓ | ✓ | ✓ | ✓ | ✓ |
| Lyrics → Song | P1 | - | ✓ | ✓ | ✓ | ✓ |
| Long-form structure | P0 | weak | good | strong | strong | strong |
| BPM / duration | P0 | partial | ✓ | ✓ | ✓ | ✓ |
| Script → Score | **CORE** | - | - | - | - | - |
| Voiceover → Score | **CORE** | - | - | - | - | - |
| Narrative Function | **CORE** | - | - | - | - | - |
| Emotion Graph | **CORE** | - | - | - | - | - |
| Score Blueprint | **CORE** | - | - | - | - | - |
| Music Critic | **CORE** | - | - | - | - | - |
| Music DNA memory | P1 CORE | - | - | - | - | - |
| Video → Score | P1 CORE | - | - | partial via DME | ✓ | ✓ |
| Realtime scoring | P2 | - | - | - | - | candidate |

## Product Principle

**他们有、用户需要的，我们至少有；他们没有、导演真正需要的，我们提前做；交互可学习，底层产品模型必须属于我们自己。**

Provider 新功能进入产品前必须经过：Competitor Capture → Capability Registry → NOW/LATER/IGNORE → Canonical Capability → Adapter。