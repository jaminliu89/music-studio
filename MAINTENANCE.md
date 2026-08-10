# ToneLab 维护文档

> 记录开发/调试过程中的关键决策、已修复的问题、当前状态和验证方法。
> 任何开发任务完成后必须更新此文档。

## 项目信息

- 项目路径: `~/Projects/music-studio/`
- 技术栈: Tauri 2 + Svelte 5 + Python sidecar (MusicGen)
- 应用名: ToneLab (音调工坊)
- Python 环境: `~/musicgen-env/`（必须 `env -i` 隔离运行）
- 模型目录: `~/models/`
- 输出目录: `~/Music/`（sidecar 内 OUTPUT_DIR）

## 架构

```
Tauri 2 (Rust) — app shell
├── engine.rs: 启动引擎（5 级降级链）+ HTTP 客户端 + SSE 转发
│   [A] bundle 内 pyinstaller 二进制 tonelab-engine（开箱即用，200M）
│   [B] config.json → [C] 环境变量 → [D] 本机 venv 探测 → [E] 引导安装报错
├── lib.rs:    8 个 tauri command（ping/list_models/download/cancel/remove/generate/read_audio/reveal）
└── App.svelte: 前端 UI（生成台/模型库/音乐库/历史/设置 五页）
        │
        ▼ HTTP (127.0.0.1:随机端口)
引擎（二选一，降级链 [A] 优先）
├── 方案一: tonelab-engine（pyinstaller onefile，torch/transformers 全打包，零 Python 依赖）
├── 方案二: server.py（需 Python 环境，setup-backends.sh 引导安装）
├── GET  /health, /ping, /models, /download/progress(SSE)
├── POST /download, /download/cancel, /models/remove, /generate
└── 模型注册表: musicgen-small(ready), musicgen-stereo-small(ready),
    musicgen-large(partial), musicgen-melody(partial), musicgen-stereo-melody(partial), audiogen-medium(partial)
```

## 关键端口/路径

- sidecar 端口: 随机分配，Rust 通过 portpicker 选
- 代理探测端口: 7897 (Clash Verge), 7890, 1080, 1082
- 下载日志: `~/models/<model>/.download.log`（aria2 日志）
- aria2 控制文件: `*.aria2`（断点续传状态）

## 已修复的问题（按时间倒序）

### 2026-08-10: urllib 本地请求走代理——专业成曲版误报 not_installed

症状: 独立进程测 ACE health 通，app 内引擎（同二进制）一直 not_installed。

根因: ToneLab app 由 Rust `env_clear` + 设置 `HTTP_PROXY/HTTPS_PROXY=127.0.0.1:7897` 启动引擎（为了 HF 下载走代理），但**没带 NO_PROXY**。urllib.request 默认读环境变量代理 → 连 127.0.0.1:8001（ACE health/release_task）走 7897 代理 → 代理连本地地址失败 → health 检测失败 → 专业成曲版误报 not_installed。独立进程（无代理变量）直连成功。

修复: server.py 顶部强制 `os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"`（+ 小写 no_proxy）。仅影响本地地址，不影响 HF 下载走代理。

教训: **本地服务请求必须显式 NO_PROXY**。Rust env_clear 启动 sidecar 时若设了代理变量，Python 侧 urllib 会被劫持——这是"进程环境"系列坑第 3 个（1. PYTHONPATH 污染 2. server.py 误匹配 3. 代理劫持）。

### 2026-08-10: 4 项 UI 体验修复（历史播放跳转/引擎未同步/模型名暴露/分发文案）

用户反馈 4 个问题（截图实锤）:
1. **历史记录不能直接播放，点播放跳转主页**——体验差。根因: `playFromHistory` 最后 `currentPage = "generate"`。修复: 去掉跳转，改为行内展开 `<audio autoplay controls>` 就地播放（最近生成 + 生成历史两处），revoke 旧 blob URL 防泄漏。
2. **模型页点"使用"跳主页但引擎变回轻快标准版**。根因: 使用按钮只 `currentPage = 'generate'` 没设引擎。修复: `selectedEngine = m.id; currentPage = 'generate'`。
3. **界面暴露底层模型名（musicgen-small / ACE-Step）**。修复: ① 新增 `ENGINE_NAMES` 内置映射表（不依赖运行时 models——模型列表加载失败/慢时也会露内部 id，这是额外抓到的 bug）；② 历史记录 meta、播放器 sub 全部走 `engineDisplayName()`；③ 专业成曲版 tagline 去 "ACE-Step ·" 前缀；④ 下载拦截/未连接文案中性化（"专业成曲引擎"）。浏览器实测: 历史页显示"轻快标准版/专业成曲版"，全页无内部 id、无 ACE 字样。
4. **分发时 ACE 怎么处理**。方案: ToneLab bundle 只含自身三件套（server.py + tonelab-engine + setup-backends.sh，203M），**不含 ACE-Step 任何文件**。专业成曲版 = 可选外部服务，ToneLab 动态检测 health，服务在就 ready、不在就"未安装"（按钮文案中性引导，不显示下载）。

### 2026-08-10: AceStepEngine 接入——双引擎架构（专业成曲版）

功能: ToneLab 新增第二个引擎"专业成曲版"（acestep-v15-turbo），解决 MusicGen 三大硬伤（无结构/突然结束/单段退化）。

架构: ACE-Step 跑独立服务（:8001，MLX 后端，DiT 4.5GB 常驻），ToneLab 的 AceStepEngine 是**纯 HTTP 客户端**（release_task 提交 → 轮询 query_result → 拷产物），零本地模型驻留、不占本进程内存。对比实测: ACE-Step 48kHz 立体声自带 fade-out 和结构感，MusicGen 32kHz 单声道需后处理。RTF: ACE-Step 8 步 15s ≈ 146s（RTF 9.7），MusicGen small 15s ≈ 60s（RTF 4）。

关键实现:
1. `AceStepEngine` 类: `_health()` 探活 + `generate()` 提交/轮询 + `_finalize()` 拷产物。BPM/结构模板逻辑与 MusicGen 共用（_bpm_to_tempo）。
2. `MODEL_REGISTRY` 加 `acestep-v15-turbo`（`is_remote_service: True`），`_detect_model_status` 对远程服务查 health 不查目录，`start_download` 拦截返回"无需下载"。
3. 前端: 引擎下拉自动出现（ready 即显示），生成中文案/播放器名显示"专业成曲版"。

ACE-Step API 契约（踩坑记录）:
- `POST /release_task` body: prompt/bpm/duration/guidance_scale/inference_steps/seed/audio_format/task_type，返回 `data.task_id`
- `POST /query_result` body 必须是 **`{"task_id_list": [...]}`**（数组！单 `task_id` 返回空 data）
- status 语义: queued/running=0, **succeeded=1**, failed=2（不是常规 2=成功！）
- 结果 `result` 是 **JSON 字符串**，内含 `file` 是 **URL**（`/v1/audio?path=%2F...`），需 parse_qs + unquote 解出磁盘路径
- 产物 48kHz 立体声 WAV，read_audio_file 二进制透传前端可播（WebKit 原生支持）

进程管理: ACE-Step 与 ToneLab 独立，ToneLab 的 cleanup 脚本 `pkill -f "server.py"` 会误杀 api_server.py——已改精确匹配 `engines/musicgen/server.py`。

### 2026-08-10: 内存引爆重启两次——多 AI 模型进程叠加（事故复盘）

事故: 用户电脑重启两次。根因链: ACE-Step DiT 4.5GB 常驻 MPS（`Keeping main model on mps (persistent)`）→ 未停止就启动 ToneLab MusicGen 生成（2GB 再上 MPS）→ 16GB M2 内存爆 → 系统强制重启。

教训（三层）:
1. **同一时间只允许一个大模型进程常驻**。用 ACE-Step 对比时必须先停 ToneLab（或反之），不能同时跑。
2. **内存保护只看"自己需求 vs 系统空闲"是错的**——没算其他进程已占用。`_low_memory` 原有逻辑在 ACE-Step 常驻时依然判断"有空闲可上 MPS"，等于没有保护。
3. **裸 "server.py" 排除自己会误伤 api_server.py**——ACE-Step 进程名 `acestep/api_server.py` 含子串 "server.py"，被当成自己跳过，恰好漏掉冲突进程。必须精确匹配 `tonelab-engine` / `/engines/musicgen/` / `musicgen/server.py`。

修复（三层内存保护）:
1. **进程级**: `_low_memory()` 扫描 ps，检测其他大模型进程（api_server/acestep/whisper/llama/vllm/sd-webui/ollama/comfyui，>3% 内存），有则拒绝 MPS 强制 CPU。
2. **全局空闲率**: memory_pressure 空闲 <25% 拒绝 MPS（比 vm_stat free+inactive 真实，MPS 统一内存）。
3. **生成前看门狗**: 模型已驻留 MPS 时，generate() 每次查空闲率，<15% 拒绝生成并提示"请关闭其他 AI 应用"（不悄悄降级——模型已驻留，降级要 reload 且叠模型才是崩溃根因）。

验证: 模拟 ACE-Step 常驻 → 拒绝 MPS ✓；模拟 ToneLab 自己 → 正常排除 ✓；真实环境无冲突 → 可 MPS ✓。

### 2026-08-10: 60 秒长音频后半段杂音——MusicGen 单段生成退化（分段生成修复）

用户实测: 婚礼 60 秒，间奏之后就是杂音。

根因: **MusicGen 自回归模型单段生成 >30 秒必然退化**——长序列累积误差导致旋律崩坏、变成噪声（官方 demo/论文上限即 30 秒）。产品逻辑缺陷: 允许 duration 1-300 秒但单段硬生成，30 秒后就是垃圾。

修复: generate() 改为分段生成——
- duration ≤30 秒: 走原单段逻辑
- duration >30 秒: 拆成多个 ≤30 秒段独立生成（`_gen_single_chunk`），段间 1 秒交叉淡入淡出拼接（`_crossfade_concat`，段 A 尾 fade-out + 段 B 头 fade-in 重叠相加），每段都在模型安全区内
- 辅助方法: `_gen_single_chunk`（单段生成，注入 inputs + max_new_tokens）、`_chunk_to_float32`（tensor→numpy float32）、`_crossfade_concat`（多段交叉拼接）
- 注意: 转置/声道处理/fade-out 全部基于 audio_np 而不是 audio tensor（分段后无单一 audio 变量），actual_sec 用 `audio_np.shape[0]/sr`

实测（婚礼 60s · musicgen-small · bpm60）: 2 段 x 30s 拼接，全 6 段（每 10 秒）频谱干净——质心 640-911Hz 稳定音乐区、高频噪声 0.0%、RMS 0.06-0.09 均匀。对比旧逻辑单段 60s 后半段质心飙 3000+Hz 杂音。结尾 fade 生效（最后 0.5s RMS 0.0025）。RTF 2.4，总耗时 141s。

### 2026-08-10: 音乐突然结束根因 + fade-out/结构模板 + 行业标杆调研

用户反馈: 音乐结束太突然，没有前奏/间奏/bridge 等结构。

根因（两个独立层面）:
1. **突然结束 = MusicGen 自回归硬截断**——模型跑到 max_new_tokens（duration 对应 token 数）直接停，无 fade。官方文档承认 "abrupt or silent endings" 是已知局限。行业标杆（Suno/Stable Audio/Udio）全部做 fade-out 后处理。
2. **无结构 = 单段生成模型 + prompt 无结构指令**——MusicGen 训练数据是完整音乐片段（无段落标注），不支持 Suno 那种 [Intro][Verse][Chorus] 结构标签。Stable Audio 2.0 是唯一训练了 intro/development/outro 曲式的开源模型，但 2.0 未开源权重（3.0 才开源）。

行业标杆调研结论:
- Suno: [Intro] [Verse] [Pre-Chorus] [Chorus] [Bridge] [Interlude] [Outro] [End] 结构标签 + [Fade Out]/[Slow Fade Out]/[Cinematic Fade Out] 结尾指令
- Udio: 结构命令 + extend 分段续写 + crop 结尾裁剪
- Stable Audio 2.0: 模型级训练曲式（3 分钟完整结构）
- MusicGen: 官方承认无结构控制 + 偶发 abrupt ending

本次修复:
1. **后端 fade-out**：写 WAV 前对最后 3 秒（`fade_out` 参数可调，上限 40% 时长）做指数衰减（exp(-4.5t)），彻底解决"咔"地切断。实测：最后 0.5 秒 RMS 0.011（接近静音），倒数 4-7 秒 RMS 0.103。
2. **结构模板**：`structure` 参数拼在 prompt 尾部（前奏铺垫+主体+尾奏收束描述），前端高级参数加结构下拉（自动/三段式/渐进式/氛围单段/叙事式）。注意: 10 秒时长塞不下三段式（实测开头 RMS 反而高于中间），结构感需 30 秒+ 才明显，前端 hint 已说明。
3. 教训: numpy 需显式 import（server.py 之前只用 scipy/torch，fade 代码引入 np 报 undefined）。

### 2026-08-10: BPM 空灵感失效根因 + 合成逻辑审计完善

用户实测: 选 BPM 45（极慢）+ 民谣吉他预设，生成结果不慢也不空灵。

审计发现三层问题:
1. **BPM 词拼在 prompt 尾部被稀释**——MusicGen 对 prompt 尾部注意力低，12 个预设标签+情绪+场景词之后，tempo 词几乎无效。修法: tempo 词前置（`prompt = f"{tempo_desc}, {prompt}"`）。
2. **极慢档词太弱**——原 `very slow tempo, sparse, spacious, dreamy pace, ambient` 是节奏词，压不住民谣吉他的弹拨律动。修法: 慢档（<70）改为氛围主导词（ethereal ambient atmosphere, very slow glacial tempo, sparse shimmering pads, vast open space, weightless, dreamy, floating, no percussion）。
3. **预期错位（PM 层）**——用户以为"慢 BPM = 空灵"，但空灵是音色/织体属性（pads/space），不是节奏属性。实测对比实锤:
   - 民谣吉他+BPM45 旧词: 质心 1255Hz（弹拨节奏感还在）
   - 空灵 pad+BPM45: 质心 776Hz（真空灵）
   - 民谣吉他+BPM45 新词: 质心 540Hz（氛围词生效，但吉他律动仍在）
   修法: 前端极慢档（<70）显示引导提示——推荐搭配氛围类预设（氛围长音/柔和环境音/自然音景），比节奏型预设（吉他/鼓点）效果好。

频谱验证方法（BPM 是否生效）: 帧能量 find_peaks 数 + RMS 波动（慢=波动低）+ 频谱质心（暗=质心低）+ 低频占比。全链路: 独立 sidecar 实测 → pyinstaller 重打 → make-dmg → cleanup 交付 → bundle 引擎再测。

### 2026-08-10: BPM 快慢生成 + 月球表面氛围实测

功能: 高级参数加 BPM 控件（数字输入 0-180 + 档位预设：不指定/极慢45/舒缓60/中速90/轻快120/快速150）。

设计要点: MusicGen **没有精确 BPM 控制**（无节拍器），但训练数据按速度/节奏特征标注，tempo 描述词有效。`_bpm_to_tempo()` 按音乐速度学分 6 档映射声音化描述（<50: very slow tempo, sparse, spacious... / <70: slow tempo, gentle... / <90: moderate slow... / <115: moderate tempo... / <140: upbeat... / 140+: fast, driving）。BPM 拼进 prompt 尾部（`f"{prompt}, {tempo_desc}"`）。0 = 不启用。

实测（月球表面 · musicgen-small · bpm=45 · 10s）:
- prompt: ethereal ambient, soft shimmering pads, gentle high bells, vast open space, weightless, calm, moonlight on lunar surface
- 频谱: RMS 0.13（安静区间）、质心 592Hz（暗暖空灵，快节奏 2000+）、低频占比 86%、RMS 波动 0.025（持续 pad 无突兀节奏）
- 全链路: 独立 sidecar 直测 → 重新 pyinstaller 打包 → make-dmg → cleanup-old-release.sh 交付 → bundle 引擎再测（MPS RTF 3.79 可播）→ commit a3d9ea5

### 2026-08-10: 方案一 pyinstaller 独立引擎交付（torch 打包三大坑）

交付内容: `tonelab-engine`（200M onefile 二进制，torch/transformers 全打包）进 bundle resources，Rust 降级链 [A] 优先启动，全新用户零 Python 依赖开箱即用。

坑 1: **torch 子模块不能 exclude**。`--exclude-module torch.cuda` / `torch.distributed` 都会炸——torch 的 `__init__.py` 运行时全量自依赖（dataloader → torch.distributed，torch/__init__ → torch.cuda），排除任何一个都是 `ModuleNotFoundError: Could not import module 'AutoProcessor'`（其实是 torch 内部断链，错误信息误导）。必须全量打包，体积 189M→200M 差异极小。

坑 2: **transformers 懒加载模块要 --collect-submodules**。`AutoProcessor`/`MusicgenForConditionalGeneration` 在函数内 import（server.py 678 行），PyInstaller 静态分析抓不到，必须 `--collect-submodules transformers --collect-submodules tokenizers`。

坑 3: **musicgen-env 必须 env -i 隔离**。PYTHONPATH 污染会读到 Hermes venv 的 tokenizers 0.23.1（报版本超限），env -i 下 musicgen-env 的 0.22.2 本来就正常。pip install 同理必须 env -i。

验证: 独立二进制 health/models/generate 全通（MPS + RTF 6.62 + afplay 可播）；装回 /Applications 后日志实锤 `[engine] 使用 bundle 内独立引擎`，无 Python 进程。

### 2026-08-09: 商业级升级破坏模型库/生成（交付跳验证的教训）

症状: 用户报模型库"无法连接引擎" + 生成播放失败 + 模型 0/0 可用。

根因链（三个独立问题叠加）:
1. **旧 sidecar 死进程**: 22:18 启动的 sidecar 在 22:58 后无响应（空 reply），
   新应用连上后 Rust reqwest 解析空 body → "error decoding response body" → 前端显示无法连接。
2. **构建后未重装 /Applications**: build-release.sh 门禁 S 收尾清掉 target 的 .app 后，
   没有把新构建装回 /Applications，用户跑的是旧版 + 死 sidecar。
3. **_low_memory 阈值 4GB 误触发**: 固定 4GB 阈值把 small 模型（fp16 只需 ~2GB）打成 CPU。
   且模型目录里 safetensors + pytorch_model.bin + state_dict.bin 三份重复（5.4GB），
   扫描全算导致需求虚高到 4.2GB。

修复:
1. 杀干净所有残留进程重装最新版（含 resources 打包）
2. _low_memory 改为按模型动态算需求：
   - 只算主权重（safetensors 优先，否则 bin，排除 state_dict）
   - 系数 0.5 + 1GB 生成余量
3. 部署流程铁律: 构建后必须 ditto 回 /Applications + 实测生成（device 字段确认）才算交付

验证: small 生成 device=mps RTF=4.93；模型列表 8 个真实返回；loadModels done 无重试。

### 2026-08-09: 商业级门禁全面升级（对照 commercial-dmg-packaging skill）

发现并修复的差距：
1. engine.rs 硬编码 Python/脚本路径 → config 化（~/.config/tonelab/config.json > env > bundle resources > 探测 fallback）+ 缺失报错引导
2. server.py 打进 bundle resources（sync-resources.sh + tauri.conf.json resources + package.json build 前置）
3. tauri.conf.json: csp null → 非 null；targets all → ["app"]（禁 Tauri 自带 DMG 防混淆）
4. 缺 release-push.sh（Stage 3 双端发布）→ 已补
5. 缺 rollback.sh（回滚）→ 已补
6. 门禁 S 升级：加 mdfind 全盘 Spotlight 扫描
7. 门禁 S2 升级：三件套（resources 残留 + 硬编码路径 + otool brew）
8. 门禁 G 升级：三层（.app 资源 + src 源码 CDN + 二进制 brew）
9. 新增门禁 D：DMG 布局元数据验证（ds_store 库读 .DS_Store 确认三图标坐标，无 GUI 环境 vision_analyze 替代）
10. Cargo.lock 提交（可复现构建）

验证：完整流水线全绿（S/S2/T/G/L/C/D 全过），DMG 布局验证打印三坐标，resources 打进 .app 实测确认。

### 2026-08-09: 情绪/场景融合标签系统

需求: 参照 Epidemic Sound / Musicbed 三轴标签（情绪/风格/场景），但不破坏现有 24 预设 + 9 分类。

方案: 融合（叠加而非替换）——
- 保留原 presetCategories（9 分类）和 24 预设不动
- 新增情绪轴（10 项：轻松/欢快/悲伤/紧张/史诗/黑暗/宁静/浪漫/怀旧/无）
- 新增场景轴（8 项：通用/Vlog/广告/电影/播客/开场/片尾/婚礼）
- 点击预设时 prompt = 原预设 + 情绪 prompt + 场景 prompt（逗号拼接）
- 增强按钮组在分类 tabs 和预设 chips 之间，小 pill 样式

验证: 史诗管弦乐 + 紧张情绪 + 电影场景 融合 prompt 生成成功（RTF 8.39）。

### 2026-08-09: 免费音乐库调研结论（Pixabay/AudioLibrary）

调研: Pixabay Music 全站 Cloudflare 挑战（搜索页/曲目页/下载端点 403），无公开音乐 API，
程序化集成不可行；Audio Library 无 API 无直链不可靠；Epidemic/Musicbed 付费不可集成。
结论: 抄三轴标签进 AI 生成（已实现），不集成免费库；设置页可加外链入口。

### 2026-08-09: stereo 模型 MPS 加速修复（推翻" MPS bug"误判）

症状: stereo 模型生成报错/崩溃，曾强制 CPU（1.5B 生成 8 秒要 10 分钟+）。

根因复盘: 之前 "torch MPS 对 stereo 模型 Abort trap 6" 是**误判**——真因是当时多个 aria2 下载 + 残留 sidecar 占满内存，OOM 硬崩。内存充足时 fp16 加载 + MPS 完全正常。

修复:
1. 删除 "stereo 强制 CPU" fallback。
2. 全部模型统一 fp16 加载 + MPS。
3. 加 _low_memory() 内存保护（vm_stat 检查 <4GB 才退 CPU）。

验证: stereo-small 3秒 RTF 2.37；stereo-melody 1.5B 5秒 46 秒完成（含加载）RTF 9.37，双声道。
对比 CPU: 8 秒生成 10 分钟+ → MPS 快 13 倍。

### 2026-08-09: 高级生成参数全链路

修复: guidance_scale / temperature / top_k / top_p 透传（Python kwargs → HTTP → Rust → 前端折叠面板），
时长上限 120→300 秒，None 值用 `or 默认值` 兜底（float(None) 报错）。
stereo 模型结论: MPS bug（Abort trap 6）+ CPU 太慢（1.5B 8s 需 10min+），不可用；配乐用 small/medium（MPS）。
验证: medium + guidance 5.0 电影配乐 RTF 7.60（含加载）。

### 2026-08-09: 生成缺 tiktoken/sentencepiece/protobuf + 日志监控模式

症状: MusicGen Medium 生成报 `'tiktoken' is required to read a 'tiktoken' file`，深层是 SentencePieceExtractor 需要 protobuf。

根因: musicgen-env 缺 tiktoken、sentencepiece、protobuf。medium 的 tokenizer 是 spiece.model（SentencePiece 格式），transformers 尝试用 tiktoken 解析因 protobuf 缺失 fallback 失败。

修复: `pip install tiktoken sentencepiece protobuf`（装到 ~/musicgen-env）。medium 加载成功（fp16 MPS 87.6s 含加载），生成正常。

日志监控模式（用户要求软件内可见日志）:
- sidecar: LOG_BUFFER 环形缓冲（deque 500 条）+ `_log()`（缓冲+stdout+落盘 /tmp/tonelab_sidecar.log）+ 关键 print 全部改 _log
- HTTP: `GET /logs?n=200` 返回缓冲日志
- Rust: `get_logs` 命令（lib.rs + engine.rs）
- 前端: 设置页新增"日志监控"卡片，自动刷新（2s）+ 手动刷新 + 清空视图，显示最近 200 条

验证: GET /logs 返回 6 条请求日志（health/models/download 全部可见）。

### 2026-08-09: 生成报"未知引擎" + stereo 模型 MPS 崩溃（两个根因）

症状: 界面点生成报 `未知引擎: musicgen-stereo-small`；修完引擎后 stereo 生成 Abort trap 6。

根因:
1. ENGINE_CLASSES 只注册了 musicgen-small，其余 7 个模型没引擎类 → get_engine 抛 ValueError。
2. torch MPS 后端对 stereo 模型 `model.to("mps")` 直接 Abort trap 6（硬崩，无 traceback，fp16 也崩）——MPS 后端 bug，非内存问题（CPU 同模型 11.7s 正常，输出 (2, 94080) 双声道）。

修复:
1. MusicgenSmallEngine 泛化为 MusicgenEngine（model_id 实例属性），ENGINE_CLASSES 注册全部 7 个 musicgen-*。
2. stereo 模型检测到自动 fallback CPU（MPS 只给单声道模型用），MPS 加载用 fp16 省内存。
3. 声道处理: audio[0] 保留全部声道（单声道 (1,T)/(T,)，立体声 (2,T)→(T,2)），MPS float16 输出转 float32 再写 wav。

验证: stereo-small CPU 生成成功 RTF 3.74，2 声道 (94080,2) float32，可播放。

### 2026-08-09: 下载加速三项优化（实测数据驱动）

症状: 下载 1-5 KB/s 极慢，或速度显示失真。

实测对比（musicgen-melody 4.6GB 文件，12 秒采样）:
- hf-mirror 直连 8 连接: 0（连不上/被限）
- huggingface.co+1082 代理 8 连接: 780 KB/s
- huggingface.co+7897 代理 8 连接: 0（7897 是死代理）
- hf-mirror 16 连接: 632 KB/s
- **huggingface.co+1082 代理 16 连接: 1.9 MB/s（最快）**

修复:
1. **连接数 8 → 16**（server.py aria2 参数）: 16 连接实测比 8 连接快 2.4 倍，单文件 16 连接不触发 xet-bridge 限流（之前 208 连接是 13 文件×16 才限流）。
2. **代理探测真实连通性验证**（engine.rs）: 原来只检查端口 LISTEN，死代理 7897（Clash 没开节点）也被选中注入 → 下载全走死代理。现在发 CONNECT huggingface.co:443 实测，200 才算可用。当前自动选中 1082。
3. **速度显示失真修复**（server.py _dir_size）: 原用 os.path.getsize 统计稀疏文件返回逻辑大小（4.6G），速度乱跳。改用 st_blocks*512（实际磁盘占用），排除 .download.log 和 .aria2 控制文件。

验证: 下载 audiogen-medium 73% speed=2.0 MB/s（稳定显示），aria2 16 连接 + 1082 代理。

### 2026-08-09: 前端收不到进度事件 —— capabilities 缺失 ACL 拒绝

症状: 下载在跑（sidecar 日志有事件、Python 直连 SSE 正常），但界面进度数字不走。

根因: Tauri v2 缺 `src-tauri/capabilities/` 目录，前端 `listen()` 被 ACL 拒绝。日志铁证: `Command plugin:event|listen not allowed by ACL`。invoke 命令不受影响（自定义命令不需要 ACL），所以下载能触发、暂停能生效，唯独进度事件收不到。

修复: 创建 `src-tauri/capabilities/default.json`，windows=["main"]，permissions=["core:default", "core:event:default"]。

验证: 前端日志 `subscribed: model:download_progress` 全部成功，每秒收到 download_progress 事件（progress/speed/eta/downloaded_label 全字段）。

### 2026-08-09: 下载无速度 + 状态误判 ready（UA 403 + .aria2 检测）

症状: 继续下载后看不到速度（0% 不动），暂停后状态误判 ready。

根因:
1. urllib 默认 UA（Python-urllib/3.11）被 hf-mirror 返回 403 Forbidden，文件列表拿不到 → aria2 无文件可下 → 0% 不动。aria2 自己的 UA 不受影响（实测 4.3 MB/s）。
2. 状态检测: `pytorch_model.bin > 10MB` 就判 ready，没检查 `.aria2` 控制文件（aria2 没下完会留这个）。

修复:
1. `urllib.request.Request` 加浏览器 UA header（Mozilla/5.0 Chrome）。
2. `_detect_model_status`: 单文件有 `.aria2` 控制文件时按 aria2 控制文件尾部记录的总大小算进度，返回 partial 而非 ready。

验证: 下载 60% speed=5-20 KB/s → 暂停 partial 1% aria2 归零 → 继续 60% 断点续传 aria2 重启。全链路通过。

### 2026-08-09: Tauri invoke 参数名必须 camelCase（modelId 而非 model_id）

症状: 点下载/暂停无反应，前端日志 `invalid args modelId for command download_model: missing required key modelId`。

根因: **实测** Tauri v2 invoke 参数 key 必须和 Rust 端参数名完全一致，Rust 端 `model_id: String` 编译后运行时期望 `modelId`。之前记忆"Tauri v2 不转换 camelCase"是错的，实测证据优先。前端传 `{ model_id: id }` 报错，`remove_model` 传 `{ modelId }` 一直正常。

修复: 前端 download_model/cancel_download 全部改 `{ modelId: id }`。

验证: 暂停/继续按钮真实调用后端（sidecar 日志 POST /download/cancel 200）。

### 2026-08-09: 暂停按钮失效 —— cancel_download 函数不存在

症状: 点暂停按钮无反应，接口返回空。

根因: server.py 路由和 do_POST 都引用了 `cancel_download`，但函数从未定义。点暂停 → NameError → 连接崩 → 前端收到异常无反应。

修复: 补上 cancel_download 实现（设置 cancel event → _download_worker 检测到后 terminate aria2）。

验证: 下载→暂停(aria2 进程归零)→恢复(断点续传 67% 继续) 全链路通过。

### 2026-08-09: 下载链路完整修复

症状: 界面显示 mock 数据（Medium/Stereo Large 等不存在的模型），下载点了没反应，无法暂停。

根因（三层）:
1. **reqwest 走系统代理** — macOS 上 Clash Verge 开系统代理注入环境变量，reqwest 默认读取后把到本地 sidecar 的请求也走代理（127.0.0.1:7897），SSE 连不上。修复: `Client::builder().no_proxy()`。
2. **前端 fallback mock** — invoke 失败后静默显示 MOCK_MODELS 假数据。修复: 删掉 mock 数据，失败显示错误提示 + 重试按钮，retry 5 次。
3. **下载状态机卡死** — aria2 被外部杀掉后 `_downloads` 字典状态没清理，一直显示"已在下载中"。修复: start_download 检查线程存活，死了清理重启。

验证方法:
- GUI 启动后 `lsof -nP -p <app_pid> | grep <sidecar_port>` 应有 ESTABLISHED
- `/models` 返回真实 6 模型（非 mock）
- 点下载后 SSE 事件 `model:download_progress` 持续推送

### 2026-08-09: aria2 连接数优化

症状: 下载 0% 不动（应用内），手动 aria2 正常。

根因: 16 连接 × 13 文件 = 208 并发连接触发 xet-bridge (CloudFront) 限流，连接建立但 0 字节。

修复: `--max-connection-per-server=8 --max-concurrent-downloads=1 --split=8 --min-split-size=5M`。单文件 8 连接 hf-mirror 约 5 MB/s。

### 2026-08-09: MPS 加速

MusicGen Small 热启动 RTF 3.2x，比 CPU 快 1.8 倍。`TONELAB_DEVICE` 环境变量可覆盖，默认自动检测 MPS，失败 fallback CPU。

## 当前状态 (2026-08-09)

- [x] 下载链路: aria2 16连接 + 代理真实探测 + 断点续传 + 进度显示（st_blocks 真实速度）
- [x] SSE 转发: Rust → Tauri 事件 → 前端（capabilities 已配）
- [x] 真实数据: 无 mock，失败显示错误 + 重试
- [x] MPS 加速: 单声道模型 fp16 MPS；stereo 模型自动 fallback CPU（MPS 后端 bug）
- [x] 暂停/恢复: cancel_download 已实现，全链路日志验证通过
- [x] 引擎泛化: 7 个 musicgen-* 全部注册 MusicgenEngine
- [x] stereo-small 生成验证: CPU 生成成功 RTF 3.74，2 声道 (94080,2) float32
- [x] medium 生成验证: tiktoken/sentencepiece/protobuf 已装，fp16 MPS 87.6s 生成成功
- [x] 日志监控: sidecar LOG_BUFFER + GET /logs + Rust get_logs + 前端设置页日志卡片（自动刷新 2s）
- [x] 模型库真实数据: 8 个真实模型，前端 GET /models 200 实锤
- [ ] 打包: bundle_dmg.sh 报 "Not enough arguments"（create-dmg fork 参数问题），
      .app 已手动组装（release 二进制 + Info.plist + 签名），应用逻辑验证通过，
      DMG 待修复（疑似 tauri 构建环境问题，重启或重新构建可解）
- [ ] 下载速度: xet-bridge CDN 网络波动（代理节点质量决定上限），代码侧已最优

## 测试方法论（宪法级）

所有测试必须用 DevTools + 日志，禁止猜：

1. **DevTools 视角**: 前端 console（已接入 log_debug 转发到 Rust stderr）
   - `console.log/warn/error` 全部转发，Rust 端 `[frontend]` 前缀
2. **QA 视角**: 每次改动后验证 UI 状态、错误处理、边界条件
3. **UX 视角**: 加载中/空数据/错误状态都有可见反馈
4. **DEVOPS 视角**: 
   - 进程存活: `pgrep -f "musicgen.*server.py"`
   - SSE 连接: `lsof -nP -p <app_pid> | grep <sidecar_port>`
   - aria2 状态: `ps aux | grep aria2c` + 下载日志
   - 端口健康: `curl -s http://127.0.0.1:<port>/health`

验证清单（每次交付前）:
- [ ] GUI 启动 12 秒后 SSE 有 ESTABLISHED 连接
- [ ] /models 返回真实 6 模型
- [ ] 下载进度四要素（百分比/速度/ETA/大小）可见
- [ ] 暂停后 aria2 进程退出，状态变 paused
- [ ] 恢复下载走断点续传
- [ ] 前端无 mock 数据

## 常用命令

```bash
# 启动 sidecar 单独测试
env -i HOME="$HOME" PATH="/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin" \
  HF_ENDPOINT=https://hf-mirror.com TQDM_DISABLE=1 \
  ~/musicgen-env/bin/python3 engines/musicgen/server.py 8899

# 健康检查
curl -s http://127.0.0.1:<port>/health
curl -s http://127.0.0.1:<port>/models

# 触发下载
curl -s -X POST http://127.0.0.1:<port>/download \
  -H "Content-Type: application/json" -d '{"model_id":"musicgen-melody"}'

# SSE 采样
curl -s -m 5 http://127.0.0.1:<port>/download/progress | head -20

# GUI 启动后验证 SSE 连接
lsof -nP -p $(pgrep -f "ToneLab.app" | head -1) | grep -E "localhost:<port>"
```

## 模型下载速度参考

- hf-mirror 直连（不走代理）: ~5 MB/s（单文件 8 连接）
- hf-mirror 走代理: ~0.5 MB/s（绕路，禁用）
- huggingface.co 走代理: 取决于节点到 CloudFront 的带宽
- 大文件最终都走 xet-bridge (CloudFront)，镜像站也重定向过去
