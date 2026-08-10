<script>
  import { onMount, onDestroy } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { listen } from "@tauri-apps/api/event";
  import {
    AudioLines, Puzzle, Clock, Settings, Globe,
    Search, Music, Play, Pause, Download, Trash2,
    FolderOpen, MoreHorizontal, Loader2, Check, X,
    Sparkles, Headphones, Volume2, Zap, CloudDownload,
    Disc3, Radio, Waves, Terminal
  } from "lucide-svelte";

  // ── 调试：转发前端 console + JS 错误到 Rust 日志 ──
  (function wireConsole() {
    if (window.__consoleWired) return;
    window.__consoleWired = true;
    window.addEventListener("error", (e) => {
      try { invoke("log_debug", { msg: `[JS-ERROR] ${e.message} @ ${e.filename}:${e.lineno}` }).catch(() => {}); } catch {}
    });
    window.addEventListener("unhandledrejection", (e) => {
      try { invoke("log_debug", { msg: `[UNHANDLED] ${String(e.reason)}` }).catch(() => {}); } catch {}
    });
    const send = (level, args) => {
      try {
        invoke("log_debug", { msg: `[${level}] ${args.map(a => {
          try { return typeof a === "object" ? JSON.stringify(a) : String(a); }
          catch { return String(a); }
        }).join(" ")}` }).catch(() => {});
      } catch { /* 非 Tauri 环境 */ }
    };
    const origLog = console.log, origWarn = console.warn, origErr = console.error;
    console.log = (...a) => { send("log", a); origLog(...a); };
    console.warn = (...a) => { send("warn", a); origWarn(...a); };
    console.error = (...a) => { send("error", a); origErr(...a); };
  })();

  // ── 导航 ──
  const navItems = [
    { id: "generate", label: "生成台", icon: AudioLines },
    { id: "models", label: "模型库", icon: Puzzle },
    { id: "library", label: "音乐库", icon: Globe },
    { id: "history", label: "历史", icon: Clock },
    { id: "settings", label: "设置", icon: Settings },
  ];
  let currentPage = "generate";

  // ── 模型数据（从后端拉取）──
  let models = [];
  let modelsLoading = true;
  let modelsError = "";
  // ── 首次启动向导（环境检测）──
  let envReady = true;       // 环境就绪与否
  let envChecking = true;    // 检测中
  let envSetupLog = "";
  let envSetupRunning = false;
  let envSetupDone = false;

  async function checkEnv() {
    envChecking = true;
    try {
      const st = await invoke("env_status");
      envReady = st.ready;
      console.log("[app] env_status:", JSON.stringify(st));
    } catch (e) {
      console.error("[app] env_status 失败:", e);
      envReady = true; // 未知视为就绪，避免卡死
    }
    envChecking = false;
  }

  // 运行引导安装脚本（setup-backends.sh）
  async function runEnvSetup() {
    envSetupRunning = true;
    envSetupLog = "";
    const script = "setup-backends.sh";
    const resourceDir = await invoke("env_setup_path").catch(() => "");
    try {
      // 用 Tauri shell 插件或直接跑；这里走 Rust 命令异步执行
      const result = await invoke("env_setup_run", {});
      envSetupLog = result || "安装完成";
      envSetupDone = true;
      envReady = true;
      location.reload(); // 环境就绪后重载进入主界面
    } catch (e) {
      envSetupLog = `安装失败: ${e}`;
      envSetupRunning = false;
    }
  }

  // ── 开发者模式（日志监控默认隐藏，普通用户不打扰）──
  const DEV_MODE_KEY = "tonelab_devmode";
  let devMode = localStorage.getItem(DEV_MODE_KEY) === "1";
  function toggleDevMode() {
    devMode = !devMode;
    localStorage.setItem(DEV_MODE_KEY, devMode ? "1" : "0");
    if (devMode) { loadLogs(); startLogsAutoRefresh(); }
    else { stopLogsAutoRefresh(); }
  }
  // ── 日志监控 ──
  let logs = [];
  let logsAutoRefresh = true;
  let logsTimer = null;


  const presets = [
    // 钢琴 / 独奏
    { name: "忧郁钢琴", prompt: "melancholic solo piano, soft reverb, rain", icon: "piano", tag: "独奏" },
    { name: "清冷极简", prompt: "cold minimal piano, sparse, quiet, melancholic", icon: "piano", tag: "独奏" },
    { name: "温暖钢琴", prompt: "warm acoustic piano, gentle, intimate, cozy", icon: "piano", tag: "独奏" },
    { name: "爵士钢琴", prompt: "smooth jazz piano trio, mellow, evening", icon: "piano", tag: "独奏" },
    // 氛围 / 环境
    { name: "柔和环境音", prompt: "soft ambient pad, warm, dreamy, minimal", icon: "sparkles", tag: "氛围" },
    { name: "氛围长音", prompt: "ambient drone with slow piano, cinematic", icon: "waves", tag: "氛围" },
    { name: "暗黑氛围", prompt: "dark ambient drone, tense, cinematic, slow", icon: "volume2", tag: "氛围" },
    { name: "梦幻冥想", prompt: "meditative ambient, ethereal, floating, peaceful", icon: "sparkles", tag: "氛围" },
    { name: "自然音景", prompt: "forest ambient, gentle birds, wind, distant water", icon: "waves", tag: "氛围" },
    // 节拍 / 节奏
    { name: "放松低保真", prompt: "chill lo-fi hip hop beat, jazzy piano", icon: "headphones", tag: "节拍" },
    { name: "欢快电子", prompt: "upbeat electronic dance music, synth, energetic", icon: "zap", tag: "节拍" },
    { name: "舒缓Synthwave", prompt: "dreamy synthwave, retro, nostalgic, warm pads", icon: "zap", tag: "节拍" },
    { name: "轻拍鼓点", prompt: "soft house beat, deep, minimal, late night", icon: "headphones", tag: "节拍" },
    { name: "TripHop慢摇", prompt: "triphop, downtempo, smoky, bass, mellow", icon: "headphones", tag: "节拍" },
    // 电影 / 管弦
    { name: "史诗管弦乐", prompt: "epic orchestral soundtrack, strings and brass", icon: "disc3", tag: "电影" },
    { name: "感伤弦乐", prompt: "sad string quartet, emotional, cinematic, slow", icon: "disc3", tag: "电影" },
    { name: "希望主题", prompt: "hopeful cinematic piano with strings, building", icon: "sparkles", tag: "电影" },
    { name: "悬疑氛围", prompt: "mysterious cinematic, tension, piano, strings", icon: "volume2", tag: "电影" },
    // 民谣 / 世界
    { name: "民谣吉他", prompt: "acoustic folk guitar, warm, gentle, storytelling", icon: "music", tag: "民谣" },
    { name: "日式禅意", prompt: "japanese koto, zen, meditative, quiet garden", icon: "sparkles", tag: "世界" },
    { name: "凯尔特民谣", prompt: "celtic folk, harp and flute, pastoral, gentle", icon: "music", tag: "世界" },
    { name: "波萨诺瓦", prompt: "bossa nova, soft guitar, latin, warm breeze", icon: "headphones", tag: "世界" },
    // 其他
    { name: "复古8bit", prompt: "chiptune, 8-bit video game, pixel art, nostalgic", icon: "zap", tag: "复古" },
    { name: "古典巴洛克", prompt: "baroque strings, harpsichord, elegant, courtly", icon: "disc3", tag: "古典" },
  ];

  // ── 预设风格分类（原有）──
  const presetCategories = ["全部", "独奏", "氛围", "节拍", "电影", "民谣", "世界", "复古", "古典"];
  let activeCategory = "全部";
  let filteredPresets = presets;

  function switchCategory(cat) {
    activeCategory = cat;
    filteredPresets = cat === "全部" ? presets : presets.filter(p => p.tag === cat);
  }

  // ── 情绪轴（叠加增强 prompt）──
  // 声音化描述：MusicGen 按风格/乐器/声音特征理解，抽象情绪词（"wedding music, elegant"）几乎无效
  // 实测（2026-08-09 A/B）：抽象词 vs 声音化词，频谱质心变化 63Hz vs 470Hz
  const moodOptions = [
    { name: "无", prompt: "" },
    { name: "轻松", prompt: "light acoustic, airy, gentle rhythm, relaxed tempo" },
    { name: "欢快", prompt: "bright major key, fast tempo, bouncy rhythm, cheerful melody" },
    { name: "悲伤", prompt: "slow tempo, minor key, soft piano, mournful strings" },
    { name: "紧张", prompt: "driving percussion, dissonant tones, fast pulse, dark strings" },
    { name: "史诗", prompt: "huge orchestral, powerful brass, rising crescendo, choir" },
    { name: "黑暗", prompt: "low drones, minor key, heavy bass, ominous textures" },
    { name: "宁静", prompt: "slow ambient, soft pads, gentle piano, sparse" },
    { name: "浪漫", prompt: "warm strings, soft piano, gentle melody, intimate" },
    { name: "怀旧", prompt: "vintage sounds, warm analog, old film feel, nostalgic melody" },
  ];

  // ── 场景轴（叠加增强 prompt）──
  // 同样声音化：场景 = 该用途的音乐声音特征，不是用途名词
  const sceneOptions = [
    { name: "通用", prompt: "" },
    { name: "Vlog", prompt: "upbeat, modern, catchy hooks, light production" },
    { name: "广告", prompt: "polished production, bright, punchy, clean mix" },
    { name: "电影", prompt: "dynamic range, cinematic build, orchestral, emotional arc" },
    { name: "播客", prompt: "minimal, clear, understated, no distracting elements" },
    { name: "开场", prompt: "impactful, building intro, attention-grabbing" },
    { name: "片尾", prompt: "resolving, gentle fade, conclusive ending, warm" },
    { name: "婚礼", prompt: "soft piano, warm strings, romantic, gentle tempo, emotional" },
  ];

  // 情绪/场景：多选集合（可自由组合，点选中的再次点击 = 取消）
  let activeMoods = [];
  let activeScenes = [];

  // 基底 prompt：预设点击或手写时的原始值，情绪/场景叠加在其上
  let basePrompt = "";
  // 当前 prompt 是否是预设生成的（预设覆盖手写；手写后预设不自动覆盖）
  let promptSource = "manual";
  // 当前选中的预设（可点击取消）
  let activePreset = null;

  function getEnhancedPrompt(base) {
    const parts = [base];
    for (const m of moodOptions) {
      if (activeMoods.includes(m.name) && m.prompt) parts.push(m.prompt);
    }
    for (const s of sceneOptions) {
      if (activeScenes.includes(s.name) && s.prompt) parts.push(s.prompt);
    }
    return parts.join(", ");
  }

  function toggleMood(name) {
    activeMoods = activeMoods.includes(name)
      ? activeMoods.filter(m => m !== name)
      : [...activeMoods, name];
    recompose();
  }

  function toggleScene(name) {
    activeScenes = activeScenes.includes(name)
      ? activeScenes.filter(s => s !== name)
      : [...activeScenes, name];
    recompose();
  }

  function recompose() {
    prompt = getEnhancedPrompt(basePrompt);
  }

  function usePresetWithEnhance(p) {
    if (activePreset === p.name) {
      // 再次点击 = 取消预设，保留手写内容或清空
      activePreset = null;
      basePrompt = "";
      promptSource = "manual";
      recompose();
      return;
    }
    activePreset = p.name;
    basePrompt = p.prompt;
    promptSource = "preset";
    recompose();
  }

  function onPromptInput(e) {
    promptSource = "manual";
    activePreset = null;  // 手写覆盖预设选中态
    basePrompt = e.target.value;
  }

  // 图标映射
  const iconMap = {
    piano: Music,
    sparkles: Sparkles,
    waves: Waves,
    headphones: Headphones,
    zap: Zap,
    disc3: Disc3,
    volume2: Volume2,
    music: Music,
    radio: Radio,
  };
  const PresetIcon = ({ name, size = 12 }) => {
    const Cmp = iconMap[name] || Music;
    return Cmp;
  };

  // ── 生成参数 ──
  let prompt = "";
  let duration = 8;
    let fileName = "";
    // ── 高级生成参数 ──
    let genGuidance = 3.0;
    let genTemperature = 1.0;
    let genTopK = 250;
    let genTopP = 0;
    let genBpm = 0;   // 0 = 不启用（自由节奏），40-180 = 指定快慢
    // 结构模板：给 MusicGen 一个整体框架描述，避免"一上来就是主体、戛然而止"
    let genStructure = "";
    const structureOptions = [
      { label: "自动（默认）", value: "" },
      { label: "前奏-主体-尾奏（三段式）", value: "intro with soft build-up, main section, gentle outro resolution" },
      { label: "渐进式（铺垫到高潮）", value: "gradual build from quiet intro to full climax, then resolved ending" },
      { label: "氛围单段（循环感）", value: "continuous ambient loop, no distinct sections, seamless" },
      { label: "叙事式（起伏）", value: "emotional arc: calm opening, rising tension, peak, settling close" },
    ];
    // BPM 档位预设（声音化节奏标签，普通用户看得懂）
    const bpmPresets = [
      { label: "不指定", value: 0 },
      { label: "极慢 45", value: 45 },
      { label: "舒缓 60", value: 60 },
      { label: "中速 90", value: 90 },
      { label: "轻快 120", value: 120 },
      { label: "快速 150", value: 150 },
    ];
    let showAdvanced = false;
  let selectedEngine = "musicgen-small";
  let isGenerating = false;
  let audioUrl = null;
  let outputPath = "";
  let errorMsg = "";
  let generateTime = null;
  // 历史记录就地播放状态（不跳转主页）
  let historyPlaying = null; // { path, url }
  let generateRtf = null;
  let genDevice = null;

  // ── 历史记录（持久化到 localStorage）──
  const HISTORY_KEY = "tonelab_history";
  let history = [];

  function loadHistory() {
    try {
      const raw = localStorage.getItem(HISTORY_KEY);
      if (raw) history = JSON.parse(raw);
    } catch (e) { console.warn("加载历史失败:", e); }
  }

  function saveHistory() {
    try {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, 100)));
    } catch (e) { console.warn("保存历史失败:", e); }
  }

  function addHistory(item) {
    history.unshift(item);
    saveHistory();
  }

  function playFromHistory(item) {
    invoke("read_audio_file", { path: item.path })
      .then(bytes => {
        const blob = new Blob([new Uint8Array(bytes)], { type: "audio/wav" });
        // 就地播放，不跳转主页
        if (historyPlaying) URL.revokeObjectURL(historyPlaying.url);
        historyPlaying = { path: item.path, url: URL.createObjectURL(blob) };
        audioUrl = historyPlaying.url;
        outputPath = item.path;
        generateTime = item.generation_time || null;
        generateRtf = item.rtf || null;
      })
      .catch(e => console.error("读取失败:", e));
  }

  // 引擎内部 id → 中文名（UI 不暴露底层模型名）
  // 内置映射表：不依赖运行时 models（模型列表加载失败/慢时也能正确显示）
  const ENGINE_NAMES = {
    "musicgen-small": "轻快标准版",
    "musicgen-medium": "高清均衡版",
    "musicgen-stereo-melody": "立体声旋律版",
    "musicgen-large": "旗舰无损版",
    "musicgen-melody": "旋律作曲版",
    "audiogen-medium": "音效生成版",
    "musicgen-stereo-small": "轻快立体声版",
    "musicgen-stereo-large": "旗舰立体声版",
    "acestep-v15-turbo": "专业成曲版",
  };
  function engineDisplayName(id) {
    return ENGINE_NAMES[id] || id;
  }

  function downloadHistory(item) {
    // 通过创建下载链接触发保存
    invoke("read_audio_file", { path: item.path })
      .then(bytes => {
        const blob = new Blob([new Uint8Array(bytes)], { type: "audio/wav" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = item.name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      })
      .catch(e => console.error("下载失败:", e));
  }

  function revealHistory(item) {
    invoke("reveal_in_finder", { path: item.path }).catch(() => {});
  }

  // 音乐库：四站入口（外链打开）
  const librarySites = [
    {
      name: "Pixabay Music",
      url: "https://pixabay.com/music/",
      desc: "免费可商用 · 27 万+ 曲目 · 按情绪/风格/场景筛选",
      badge: "免费",
      accent: "green",
    },
    {
      name: "Audio Library",
      url: "https://audiolibrary.com.co/",
      desc: "免费无版权 · YouTube 创作者常用 · 电子/氛围/节拍",
      badge: "免费",
      accent: "blue",
    },
    {
      name: "Epidemic Sound",
      url: "https://www.epidemicsound.com/",
      desc: "订阅制 · 商用授权 · 电影级配乐/情绪标签最全",
      badge: "付费",
      accent: "dark",
    },
    {
      name: "Musicbed",
      url: "https://www.musicbed.com/songs",
      desc: "订阅制 · 电影/广告级授权 · 专业片库",
      badge: "付费",
      accent: "dark",
    },
  ];

  function openSite(url) {
    invoke("open_external", { url }).catch(e => {
      // Tauri 命令不可用时回退 window.open
      window.open(url, "_blank");
    });
  }

  function deleteHistory(item) {
    if (!confirm(`删除 ${item.name} 的记录？（文件不会被删除）`)) return;
    history = history.filter(h => h.path !== item.path);
    saveHistory();
  }

  // ── 计算属性 ──
  $: readyModels = models.filter(m => m.status === "ready").length;
  $: totalModels = models.length;
  $: readyEngineOptions = models.filter(m => m.status === "ready");
  $: canGenerate = selectedEngine && prompt.trim().length > 0 && duration > 0 && !isGenerating && readyModels > 0;

  // 今日统计
  $: todayStats = {
    total: history.length,
    totalDuration: formatTotalDuration(history),
    saved: history.length,
  };

  function formatTotalDuration(list) {
    if (!list.length) return "0";
    const total = list.reduce((s, i) => s + (i.duration || 0), 0);
    if (total < 60) return `${total.toFixed(0)} 秒`;
    const m = Math.floor(total / 60);
    const s = Math.round(total % 60);
    return s ? `${m} 分 ${s} 秒` : `${m} 分`;
  }

  function usePreset(p) {
    prompt = p.prompt;
  }
  // 模型清单：与 sidecar MODEL_REGISTRY 保持一致（真实数据来源）
  // 仅用于浏览器开发预览兜底；Tauri 应用内一律走 invoke("list_models") 真实接口
  const MOCK_MODELS = [
    { id: "musicgen-small", name: "轻快标准版", author: "Meta", type: "text-to-music", params: "300M", size_mb: 2400, status: "ready", progress: 100, description: "轻量级文生音乐模型，速度快，适合快速迭代灵感。" },
    { id: "musicgen-medium", name: "高清均衡版", author: "Meta", type: "text-to-music", params: "1.5B", size_mb: 5600, status: "not_installed", progress: 0, description: "中等规模模型，音质和音乐性显著提升。" },
    { id: "musicgen-large", name: "旗舰无损版", author: "Meta", type: "text-to-music", params: "3.3B", size_mb: 12000, status: "not_installed", progress: 0, description: "大规模模型，专业级音质和复杂编曲能力。" },
    { id: "musicgen-stereo-melody", name: "立体声旋律版", author: "Meta", type: "melody-to-music", params: "1.5B", size_mb: 6800, status: "not_installed", progress: 0, description: "立体声 + 旋律条件，可输入参考旋律进行风格迁移。" },
    { id: "musicgen-stereo-large", name: "旗舰立体声版", author: "Meta", type: "text-to-music", params: "3.3B", size_mb: 13000, status: "not_installed", progress: 0, description: "大规模立体声版本，空间感和音质最佳。" },
    { id: "audiogen-medium", name: "音效生成版", author: "Meta", type: "text-to-sound", params: "1.5B", size_mb: 5200, status: "not_installed", progress: 0, description: "音效生成模型，生成环境音、动物声、机械声等。" },
    { id: "acestep-v15-turbo", name: "专业成曲版", author: "", type: "text-to-music", params: "6B", size_mb: 6000, status: "ready", progress: 100, description: "完整曲式结构 + 48kHz 立体声。" },
  ];

  async function loadLogs() {
    try {
      logs = await invoke("get_logs", { n: 200 });
      // 只保留最近 200 条
      if (logs.length > 200) logs = logs.slice(-200);
    } catch (e) {
      // 忽略，下次再试
    }
  }

  function startLogsAutoRefresh() {
    if (logsTimer) return;
    logsTimer = setInterval(async () => {
      if (logsAutoRefresh) {
        const before = logs.length;
        await loadLogs();
        // 有新增时自动滚动到底部
        if (logs.length > before) {
          // 交给 DOM 处理
        }
      }
    }, 2000);
  }

  function stopLogsAutoRefresh() {
    if (logsTimer) {
      clearInterval(logsTimer);
      logsTimer = null;
    }
  }

  async function loadModels() {
    try {
      models = await invoke("list_models");
      modelsLoading = false;
      // 如果当前选中的引擎不在可用列表，换第一个可用的
      if (!models.find(m => m.id === selectedEngine && m.status === "ready")) {
        const firstReady = models.find(m => m.status === "ready");
        if (firstReady) selectedEngine = firstReady.id;
      }
    } catch (e) {
      // 可能是 sidecar 还在启动，重试 5 次（每次 1 秒）
      console.warn("加载模型列表失败，重试中:", e);
      for (let i = 0; i < 5; i++) {
        await new Promise(r => setTimeout(r, 1000));
        try {
          models = await invoke("list_models");
          modelsLoading = false;
          const firstReady = models.find(m => m.status === "ready");
          if (firstReady) selectedEngine = firstReady.id;
          return;
        } catch (e2) {
          console.warn(`重试 ${i + 1}/5 失败:`, e2);
        }
      }
      // 最终失败：不显示 mock 假数据，明确报错
      console.error("加载模型列表最终失败");
      models = [];
      modelsLoading = false;
      modelsError = "无法连接引擎，请重启应用或检查 sidecar";
    }
  }

  let downloadError = {};

  async function handleDownload(m) {
    const id = m.id;
    console.log(`[app] handleDownload: ${id} status=${m.status}`);
    downloadError[id] = "";

    if (m.status === "not_installed" || m.status === "partial" || m.status === "error" || m.status === "paused") {
      // 乐观更新：立刻 UI 切到下载中
      const idx = models.findIndex(x => x.id === id);
      if (idx >= 0) {
        models[idx].status = "downloading";
        models = [...models];
      }
      try {
        await invoke("download_model", { modelId: id });
      } catch (e) {
        console.error("启动下载失败:", e);
        downloadError[id] = String(e);
        // 失败了回滚状态
        if (idx >= 0) {
          models[idx].status = m.status;
          models = [...models];
        }
      }
    } else if (m.status === "downloading") {
      try {
        await invoke("cancel_download", { modelId: id });
        const idx = models.findIndex(x => x.id === id);
        if (idx >= 0) {
          models[idx].status = "paused";
          models = [...models];
        }
      } catch (e) {
        console.error("暂停失败:", e);
        downloadError[id] = String(e);
      }
    }
  }

  async function handleRemove(m) {
    if (!confirm(`确定要删除 ${m.name} 吗？`)) return;
    try {
      await invoke("remove_model", { modelId: m.id });
      // 刷新列表
      setTimeout(loadModels, 500);
    } catch (e) {
      console.error("删除失败:", e);
    }
  }

  async function generate() {
    if (!canGenerate) return;
    isGenerating = true;
    errorMsg = "";
    audioUrl = null;
    generateTime = null;
    generateRtf = null;

    try {
      const result = await invoke("generate_music", {
        engine: selectedEngine,
        prompt: prompt.trim(),
        duration,
        filename: fileName.trim() || null,
        guidanceScale: genGuidance,
        temperature: genTemperature,
        topK: genTopK,
        topP: genTopP,
        bpm: genBpm > 0 ? genBpm : null,
        structure: genStructure || null,
      });

      if (result.success) {
        outputPath = result.path;
        generateTime = result.generation_time;
        generateRtf = result.rtf;
        genDevice = result.device || null;

        // 读取音频文件转 blob 播放
        const bytes = await invoke("read_audio_file", { path: result.path });
        const blob = new Blob([new Uint8Array(bytes)], { type: "audio/wav" });
        audioUrl = URL.createObjectURL(blob);

        // 加入历史
        addHistory({
          name: result.path.split("/").pop(),
          path: result.path,
          prompt: prompt.trim(),
          duration: result.duration,
          date: new Date().toLocaleString("zh-CN"),
          engine: selectedEngine,
          size: "—",
          generation_time: result.generation_time,
          rtf: result.rtf,
        });
      } else {
        errorMsg = result.error || "生成失败";
      }
    } catch (e) {
      errorMsg = String(e);
    } finally {
      isGenerating = false;
    }
  }

  function openInFinder() {
    if (outputPath) invoke("reveal_in_finder", { path: outputPath });
  }

  // SSE 事件订阅
  let unsubscribes = [];

  onMount(async () => {
    console.log("[app] mounted, starting");
    // 环境检测（首次启动向导）
    await checkEnv();
    if (!envReady) {
      console.log("[app] 环境未就绪，进入引导页");
      return; // 不加载模型，等用户装好环境
    }
    loadHistory();
    // 先拉一次模型列表
    console.log("[app] calling loadModels");
    await loadModels();
    console.log("[app] loadModels done");
    // 日志自动刷新仅在开发者模式下启动（普通用户不打扰）
    if (devMode) {
      loadLogs();
      startLogsAutoRefresh();
    }

    // 订阅下载进度事件
    const events = [
      "model:models_state",
      "model:download_progress",
      "model:download_complete",
      "model:download_paused",
      "model:download_error",
      "model:model_removed",
    ];

    for (const evt of events) {
      try {
        const unsub = await listen(evt, (event) => {
          handleModelEvent(evt, event.payload);
        });
        unsubscribes.push(unsub);
        console.log("[app] subscribed:", evt);
      } catch (e) {
        console.error("[app] listen 失败:", evt, String(e));
      }
    }
  });

  onDestroy(() => {
    unsubscribes.forEach(u => u());
    stopLogsAutoRefresh();
  });

  function handleModelEvent(eventName, data) {
    console.log("model event:", eventName, data);

    if (eventName === "model:models_state" && data.models) {
      models = data.models;
      return;
    }

    if (eventName === "model:download_progress" && data.model_id) {
      const idx = models.findIndex(m => m.id === data.model_id);
      if (idx >= 0) {
        models[idx].status = "downloading";
        models[idx].progress = data.progress ?? models[idx].progress;
        models[idx].speed = data.speed ?? "";
        models[idx].eta = data.eta ?? "";
        models[idx].downloaded_label = data.downloaded_label ?? "";
        models = [...models];
      }
      return;
    }

    if (eventName === "model:download_complete" && data.model_id) {
      const idx = models.findIndex(m => m.id === data.model_id);
      if (idx >= 0) {
        models[idx].status = "ready";
        models[idx].progress = 100;
        models[idx].speed = "";
        models = [...models];
      }
      return;
    }

    if (eventName === "model:download_paused" && data.model_id) {
      const idx = models.findIndex(m => m.id === data.model_id);
      if (idx >= 0) {
        models[idx].status = "paused";
        models[idx].speed = "";
        models = [...models];
      }
      return;
    }

    if (eventName === "model:download_error" && data.model_id) {
      const idx = models.findIndex(m => m.id === data.model_id);
      if (idx >= 0) {
        models[idx].status = "error";
        models[idx].speed = "";
        models = [...models];
      }
      return;
    }

    if (eventName === "model:model_removed") {
      loadModels();
      return;
    }
  }
</script>

<div class="app">
  {#if !envReady && !envChecking}
    <!-- ═══ 首次启动向导（环境未就绪）═══ -->
    <div class="onboard">
      <div class="onboard-card">
        <div class="onboard-brand">♪</div>
        <h1 class="onboard-title">欢迎使用 ToneLab</h1>
        <p class="onboard-sub">首次使用需要安装 AI 推理环境（约 5-15 分钟），之后即可生成音乐。</p>

        {#if envSetupRunning}
          <div class="onboard-installing">
            <Loader2 class="spin" size={24} />
            <p>正在安装运行环境…</p>
            <pre class="onboard-log">{envSetupLog}</pre>
          </div>
        {:else if envSetupDone}
          <p class="onboard-ok">✓ 安装完成，正在进入…</p>
        {:else}
          <button class="btn-primary onboard-btn" on:click={runEnvSetup}>
            <Download size={16} /> 一键安装运行环境
          </button>
          <p class="onboard-hint">需要 macOS 10.15+ 与 Python 3.10+（自动检测，缺什么装什么）</p>
          {#if envSetupLog}
            <pre class="onboard-log">{envSetupLog}</pre>
          {/if}
        {/if}
      </div>
    </div>
  {:else}
  <!-- ═══ 左侧边栏 ═══ -->
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-icon">♪</div>
      <div class="brand-name">ToneLab</div>
      <div class="brand-sub">音乐工坊</div>
    </div>

    <nav class="nav">
      {#each navItems as item}
        <button
          class="nav-item {currentPage === item.id ? 'active' : ''}"
          on:click={() => currentPage = item.id}
          title={item.label}
        >
          {#if item.id === "generate"}<AudioLines class="nav-icon" size={20} />
          {:else if item.id === "models"}<Puzzle class="nav-icon" size={20} />
          {:else if item.id === "library"}<Globe class="nav-icon" size={20} />
          {:else if item.id === "history"}<Clock class="nav-icon" size={20} />
          {:else if item.id === "settings"}<Settings class="nav-icon" size={20} />
          {/if}
        </button>
      {/each}
    </nav>

    <div class="sidebar-bottom">
      <div class="user-avatar">柳</div>
    </div>
  </aside>

  <!-- ═══ 主内容区 ═══ -->
  <main class="main">
    <!-- 顶部 -->
    <header class="header">
      <div>
        <h1 class="greeting">晚上好，创作者</h1>
        <p class="greeting-sub">今天来做点什么样的声音呢</p>
      </div>
      <div class="header-right">
        <div class="search-box">
          <Search class="search-icon" size={14} />
          <input type="text" placeholder="搜索生成记录、模型..." />
        </div>
        <button class="btn-dark pill">升级 Pro</button>
      </div>
    </header>

    <!-- ── 页面：生成台 ── -->
    {#if currentPage === "generate"}
      <div class="content generate-layout">
        <!-- 左列：概览 + 播放 + 最近生成 -->
        <div class="gen-col gen-col-left">
          <div class="card card-taupe card-stat">
            <div class="card-header">
              <h3>今日生成概览</h3>
              <button class="icon-btn-sm" title="锁定"><Check size={14} /></button>
            </div>

            <div class="bubble-chart">
              <div class="bubble bubble-large">
                <span class="bubble-value">{todayStats.total}</span>
                <span class="bubble-label">首歌</span>
              </div>
              <div class="bubble bubble-medium">
                <span class="bubble-value">{todayStats.totalDuration}</span>
                <span class="bubble-label">总时长</span>
              </div>
              <div class="bubble bubble-small">
                <span class="bubble-value">{readyModels}/{totalModels}</span>
                <span class="bubble-label">模型</span>
              </div>
            </div>

            <div class="legend">
              <div class="legend-item">
                <span class="legend-dot amber"></span>
                <span>生成数量</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot coral"></span>
                <span>累计时长</span>
              </div>
              <div class="legend-item">
                <span class="legend-dot ink"></span>
                <span>可用模型</span>
              </div>
            </div>
          </div>
          <div class="card">
              <div class="card-header">
                <h3>当前播放</h3>
              </div>

              {#if audioUrl}
                <div class="player">
                  <div class="player-art">
                    <AudioLines class="note-icon" size={48} />
                  </div>
                  <div class="player-info">
                    <div class="player-title">{outputPath.split('/').pop()}</div>
                    <div class="player-sub">{engineDisplayName(selectedEngine)} · {duration}秒</div>
                    {#if generateTime}
                      <div class="player-stats">
                        生成时间 {generateTime}s · RTF {generateRtf}x
                      </div>
                    {/if}
                  </div>
                  <audio controls src={audioUrl} class="audio-player"></audio>
                  <button class="btn-ghost pill" on:click={openInFinder}><FolderOpen size={12} /> 在访达中显示</button>
                </div>
              {:else if isGenerating}
                <div class="placeholder">
                  <div class="loading-ring"></div>
                  <p>正在生成你的音乐...</p>
                  <p class="placeholder-sub">
                    {#if selectedEngine.includes('acestep')}
                      专业成曲引擎 · 完整曲式结构（较慢，约 2-3 分钟）
                    {:else if selectedEngine.includes('stereo')}
                      Stereo 模型 · {genDevice ? (genDevice === 'cpu' ? 'CPU 模式（较慢）' : 'MPS 加速中') : 'MPS 加速中'}
                    {:else}
                      {genDevice ? (genDevice === 'cpu' ? 'CPU 模式' : 'MPS 加速中') : 'MPS 加速中'}
                    {/if}
                  </p>
                </div>
              {:else}
                <div class="placeholder">
                  <Music class="placeholder-icon" size={36} />
                  <p>选择一个预设，开始你的声音</p>
                  <p class="placeholder-sub">生成的音乐将在这里播放</p>
                </div>
              {/if}
            </div>
          <div class="card card-history">
              <div class="card-header">
                <h3>最近生成</h3>
                <button class="text-btn" on:click={() => currentPage = 'history'}>查看全部 →</button>
              </div>

              <div class="history-list">
                {#each history.slice(0, 4) as item, i}
                  <div class="history-item">
                    <div class="history-avatar">
                      <Music size={18} />
                    </div>
                    <div class="history-info">
                      <div class="history-name">{item.name}</div>
                      <div class="history-meta">{engineDisplayName(item.engine)} · {item.duration} · {item.date}</div>
                      {#if historyPlaying && historyPlaying.path === item.path}
                        <audio autoplay controls src={historyPlaying.url} class="history-audio"></audio>
                      {/if}
                    </div>
                    <div class="history-actions">
                      <button class="icon-btn-xs" title="播放" on:click={() => playFromHistory(item)}>
                        <Play size={12} />
                      </button>
                      <button class="icon-btn-xs" title="更多">
                        <MoreHorizontal size={12} />
                      </button>
                    </div>
                  </div>
                {/each}
              </div>
            </div>
        </div>
        <!-- 右列：快速生成 -->
        <div class="gen-col gen-col-right">
          <div class="card card-dark">
            <div class="card-header">
              <h3>快速生成</h3>
              <select class="engine-select" bind:value={selectedEngine}>
                {#each readyEngineOptions as m}
                  <option value={m.id}>{m.name}</option>
                {/each}
              </select>
            </div>

            <textarea
              class="prompt-input"
              bind:value={prompt}
              on:input={onPromptInput}
              placeholder="描述你想生成的音乐，例如：soft piano melody, gentle ambient..."
              rows="4"
            />

            <div class="preset-cats">
              {#each presetCategories as cat}
                <button
                  class="cat-btn"
                  class:cat-active={activeCategory === cat}
                  on:click={() => switchCategory(cat)}
                >
                  {cat}
                </button>
              {/each}
            </div>

            <div class="enhance-row">
              <div class="enhance-group">
                <span class="enhance-label">情绪</span>
                {#each moodOptions as m}
                  <button
                    class="enhance-btn"
                    class:enhance-active={activeMoods.includes(m.name)}
                    on:click={() => toggleMood(m.name)}
                  >
                    {m.name}
                  </button>
                {/each}
              </div>
              <div class="enhance-group">
                <span class="enhance-label">场景</span>
                {#each sceneOptions as s}
                  <button
                    class="enhance-btn"
                    class:enhance-active={activeScenes.includes(s.name)}
                    on:click={() => toggleScene(s.name)}
                  >
                    {s.name}
                  </button>
                {/each}
              </div>
            </div>

            <div class="preset-chips">
              {#each filteredPresets as p}
                <button class="chip" class:chip-active={activePreset === p.name} on:click={() => usePresetWithEnhance(p)}>
                  {#if p.icon === 'sparkles'}<Sparkles size={12} />
                  {:else if p.icon === 'waves'}<Waves size={12} />
                  {:else if p.icon === 'headphones'}<Headphones size={12} />
                  {:else if p.icon === 'zap'}<Zap size={12} />
                  {:else if p.icon === 'disc3'}<Disc3 size={12} />
                  {:else if p.icon === 'volume2'}<Volume2 size={12} />
                  {:else if p.icon === 'radio'}<Radio size={12} />
                  {:else}<Music size={12} />
                  {/if}
                  {p.name}
                </button>
              {/each}
            </div>

            <div class="gen-params">
              <div class="param">
                <label>时长（秒）</label>
                <input type="number" bind:value={duration} min="1" max="300" class="param-input" />
              </div>
              <div class="param flex-2">
                <label>文件名</label>
                <input type="text" bind:value={fileName} placeholder="留空自动命名" class="param-input" />
              </div>
              <button
                class="btn-accent pill generate-btn"
                on:click={generate}
                disabled={!canGenerate}
              >
                {#if isGenerating}
                  <Loader2 class="spin" size={14} /> 生成中...
                {:else}
                  <Play size={14} /> 生成
                {/if}
              </button>
            </div>
            <div class="advanced-toggle" on:click={() => (showAdvanced = !showAdvanced)}>
              <span>{showAdvanced ? "收起高级参数" : "高级参数"}</span>
              <span class="adv-caret">{showAdvanced ? "▾" : "▸"}</span>
            </div>
            {#if showAdvanced}
              <div class="advanced-panel">
                <div class="param">
                  <label title="文本贴合度，越高越严格">Guidance</label>
                  <input type="number" bind:value={genGuidance} min="0" max="10" step="0.5" class="param-input" />
                </div>
                <div class="param">
                  <label title="采样随机性，越高越自由">温度</label>
                  <input type="number" bind:value={genTemperature} min="0.1" max="2" step="0.1" class="param-input" />
                </div>
                <div class="param">
                  <label title="候选词数量">Top-K</label>
                  <input type="number" bind:value={genTopK} min="1" max="500" class="param-input" />
                </div>
                <div class="param">
                  <label title="累积概率截断，0=关闭">Top-P</label>
                  <input type="number" bind:value={genTopP} min="0" max="1" step="0.05" class="param-input" />
                </div>
                <div class="param param-structure">
                  <label title="整体结构框架，避免突然开始/结束">结构</label>
                  <select bind:value={genStructure} class="param-input">
                    {#each structureOptions as s}
                      <option value={s.value}>{s.label}</option>
                    {/each}
                  </select>
                </div>
                <div class="param param-bpm">
                  <label title="节奏快慢，0=不指定">BPM</label>
                  <input type="number" bind:value={genBpm} min="0" max="180" step="5" class="param-input" />
                </div>
                <div class="param-bpm-presets">
                  {#each bpmPresets as p}
                    <button
                      class="bpm-chip {genBpm === p.value ? 'active' : ''}"
                      on:click={() => (genBpm = p.value)}
                    >{p.label}</button>
                  {/each}
                </div>
                {#if genBpm > 0 && genBpm < 70}
                  <div class="bpm-hint">
                    极慢速度自动注入空灵氛围词；想更空灵建议搭配「氛围长音」「柔和环境音」「自然音景」类预设，比节奏型预设（吉他/鼓点）效果好。
                  </div>
                {/if}
              </div>
            {/if}

            {#if errorMsg}
              <div class="error-text">{errorMsg}</div>
            {/if}
          </div>
        </div>
      </div>

    <!-- ── 页面：模型库 ── -->
    {:else if currentPage === "models"}
      <div class="content">
        <div class="page-header">
          <div>
            <h2 class="page-title">模型库</h2>
            <p class="page-sub">管理本地模型，下载新的引擎或删除不需要的</p>
          </div>
          <div class="model-summary">
            <Check size={14} class="summary-icon ready" />
            <span>{readyModels} 个可用</span>
            <span class="summary-sep">·</span>
            <CloudDownload size={14} class="summary-icon pending" />
            <span>{totalModels - readyModels} 个待下载</span>
          </div>
        </div>

        <div class="model-grid">
          {#if modelsError}
            <div class="models-error">
              {modelsError}
              <button class="btn-ghost pill" on:click={() => { modelsError = ""; loadModels(); }}>重试</button>
            </div>
          {:else}
          {#each models as m}
            <div class="card model-card status-{m.status}">
              <div class="model-header">
                <div class="model-icon">
                  {#if m.type === 'text-to-music'}<Music size={22} />
                  {:else if m.type === 'melody-to-music'}<Disc3 size={22} />
                  {:else if m.type === 'style-transfer'}<Sparkles size={22} />
                  {:else if m.type === 'text-to-sound'}<Volume2 size={22} />
                  {:else}<Music size={22} />
                  {/if}
                </div>
                <div class="model-status-badge status-{m.status}">
                  {#if m.status === 'ready'}已就绪
                  {:else if m.status === 'downloading'}下载中
                  {:else if m.status === 'paused'}已暂停
                  {:else if m.status === 'partial'}部分下载
                  {:else if m.status === 'error'}下载失败
                  {:else}未安装
                  {/if}
                </div>
              </div>

              <h4 class="model-name">{m.name}</h4>
              <p class="model-tagline">{m.tagline}</p>

              <div class="model-meta">
                <span class="meta-item">📦 {m.size}</span>
                <span class="meta-tag">{m.type}</span>
              </div>

              {#if m.status === 'downloading' || m.status === 'paused' || m.status === 'partial'}
                <div class="progress-section">
                  <div class="progress-bar">
                    <div class="progress-fill" style="width: {m.progress}%"></div>
                  </div>
                  <div class="progress-meta">
                    <span class="progress-pct">{m.progress}%</span>
                    {#if m.downloaded_label && m.status === 'downloading'}
                      <span class="progress-size-label">{m.downloaded_label}</span>
                    {/if}
                    <span class="progress-stats">
                      {#if m.speed && m.status === 'downloading'}
                        <span class="speed" class:speed-fast={parseFloat(m.speed) > 1} class:speed-slow={parseFloat(m.speed) < 0.5}>
                          {m.speed}
                        </span>
                      {/if}
                      {#if m.eta && m.status === 'downloading'}
                        <span class="eta">剩余 {m.eta}</span>
                      {/if}
                    </span>
                  </div>
                </div>
              {/if}

              <div class="model-actions">
                {#if m.status === 'ready'}
                  <button class="btn-ghost pill" on:click={() => handleRemove(m)}><Trash2 size={12} /> 删除</button>
                  <button class="btn-accent pill" on:click={() => { selectedEngine = m.id; currentPage = 'generate'; }}><Play size={12} /> 使用</button>
                {:else if m.status === 'downloading'}
                  <button class="btn-ghost pill" on:click={() => handleDownload(m)}><Pause size={12} /> 暂停</button>
                {:else if m.status === 'paused'}
                  <button class="btn-accent pill" on:click={() => handleDownload(m)}><Play size={12} /> 继续</button>
                {:else if m.status === 'partial'}
                  <button class="btn-accent pill" on:click={() => handleDownload(m)}><CloudDownload size={12} /> 继续下载</button>
                {:else if m.status === 'error'}
                  <button class="btn-accent pill" on:click={() => handleDownload(m)}><Zap size={12} /> 重试</button>
                {:else if m.id === 'acestep-v15-turbo'}
                  <!-- 远程成曲引擎：不进本地下载，服务未连接时给安装引导 -->
                  <button class="btn-dark pill" on:click={() => { downloadError[m.id] = "专业成曲引擎为独立运行环境，未随本应用分发。需单独安装启动服务后自动可用。"; }}><Info size={12} /> 未安装</button>
                {:else}
                  <button class="btn-dark pill" on:click={() => handleDownload(m)}><CloudDownload size={12} /> 下载</button>
                {/if}
              </div>
            </div>
          {/each}
          {/if}
        </div>
      </div>

    <!-- ── 页面：音乐库 ── -->
    {:else if currentPage === "library"}
      <div class="content">
        <div class="page-header">
          <div>
            <h2 class="page-title">音乐库</h2>
            <p class="page-sub">免费/商用音乐网站入口，按需取用</p>
          </div>
        </div>

        <div class="library-grid">
          {#each librarySites as site}
            <div class="card library-card">
              <div class="library-card-head">
                <span class="badge badge-{site.accent}">{site.badge}</span>
                <h3 class="library-name">{site.name}</h3>
              </div>
              <p class="library-desc">{site.desc}</p>
              <button class="btn-primary pill" on:click={() => openSite(site.url)}>
                <Globe size={14} /> 打开网站
              </button>
            </div>
          {/each}
        </div>

        <div class="card">
          <h3 class="settings-title">提示</h3>
          <p class="page-sub">这些网站的标签体系（情绪/风格/场景）已融入生成台的预设与增强轴——站内挑选风格 → 回到 ToneLab 用 AI 生成专属版本。</p>
        </div>
      </div>

    <!-- ── 页面：历史 ── -->
    {:else if currentPage === "history"}
      <div class="content">
        <div class="page-header">
          <div>
            <h2 class="page-title">生成历史</h2>
            <p class="page-sub">所有你生成过的音乐，随时回放和管理</p>
          </div>
        </div>

        <div class="card">
          {#if history.length === 0}
            <div class="placeholder">
              <Clock class="placeholder-icon" size={36} />
              <p>还没有生成记录</p>
              <p class="placeholder-sub">去生成台创作你的第一首音乐吧</p>
            </div>
          {:else}
          <div class="history-list history-list-large">
            {#each history as item}
              <div class="history-item history-item-lg">
                <div class="history-avatar">
                  <Music size={20} />
                </div>
                <div class="history-info">
                  <div class="history-name">{item.name}</div>
                  <div class="history-desc">{item.prompt}</div>
                  <div class="history-meta">
                    {engineDisplayName(item.engine)} · {item.duration}s · {item.date}
                    {#if item.rtf} · RTF {item.rtf}x{/if}
                  </div>
                  {#if historyPlaying && historyPlaying.path === item.path}
                    <audio autoplay controls src={historyPlaying.url} class="history-audio"></audio>
                  {/if}
                </div>
                <div class="history-actions history-actions-lg">
                  <button class="btn-ghost pill" on:click={() => playFromHistory(item)}>
                    <Play size={12} /> 播放
                  </button>
                  <button class="btn-ghost pill" on:click={() => downloadHistory(item)} title="下载">
                    <Download size={12} /> 下载
                  </button>
                  <button class="btn-ghost pill" on:click={() => revealHistory(item)} title="在访达中显示">
                    <FolderOpen size={12} />
                  </button>
                  <button class="btn-ghost pill" on:click={() => deleteHistory(item)} title="删除记录">
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            {/each}
          </div>
          {/if}
        </div>
      </div>

    <!-- ── 页面：设置 ── -->
    {:else if currentPage === "settings"}
      <div class="content">
        <div class="page-header">
          <div>
            <h2 class="page-title">设置</h2>
            <p class="page-sub">自定义 ToneLab 的工作方式</p>
          </div>
        </div>

        <div class="settings-grid">
          <div class="card">
            <h3 class="settings-title">输出</h3>
            <div class="settings-item">
              <div>
                <div class="settings-label">输出目录</div>
                <div class="settings-desc">生成的音频文件保存位置</div>
              </div>
              <button class="btn-ghost pill">/Users/kimliu/Music</button>
            </div>
            <div class="settings-item">
              <div>
                <div class="settings-label">默认格式</div>
                <div class="settings-desc">生成音频的输出格式</div>
              </div>
              <select class="pill select-sm">
                <option>WAV</option>
                <option>MP3</option>
                <option>FLAC</option>
              </select>
            </div>
          </div>

          <div class="card">
            <h3 class="settings-title">引擎</h3>
            <div class="settings-item">
              <div>
                <div class="settings-label">Python 解释器路径</div>
                <div class="settings-desc">运行推理引擎的 Python 环境</div>
              </div>
              <button class="btn-ghost pill">~/musicgen-env/bin/python</button>
            </div>
            <div class="settings-item">
              <div>
                <div class="settings-label">模型目录</div>
                <div class="settings-desc">本地模型权重文件存放位置</div>
              </div>
              <button class="btn-ghost pill">~/models</button>
            </div>
          </div>

          <div class="card">
            <h3 class="settings-title">生成参数</h3>
            <div class="settings-item">
              <div>
                <div class="settings-label">默认时长</div>
                <div class="settings-desc">新建生成任务时的默认时长</div>
              </div>
              <span class="pill value-pill">8 秒</span>
            </div>
            <div class="settings-item">
              <div>
                <div class="settings-label">采样率</div>
                <div class="settings-desc">输出音频采样率</div>
              </div>
              <select class="pill select-sm">
                <option>32000 Hz</option>
                <option>44100 Hz</option>
                <option>48000 Hz</option>
              </select>
            </div>
            <div class="settings-item">
              <div>
                <div class="settings-label">Guidance Scale</div>
                <div class="settings-desc">文本贴合度，越高越严格</div>
              </div>
              <span class="pill value-pill">3.0</span>
            </div>
          </div>

          <div class="card">
            <h3 class="settings-title">关于</h3>
            <div class="settings-item">
              <div>
                <div class="settings-label">版本</div>
                <div class="settings-desc">ToneLab 桌面版</div>
              </div>
              <span class="pill value-pill">v0.1.0</span>
            </div>
          </div>

          <div class="card">
            <h3 class="settings-title">高级</h3>
            <div class="settings-item">
              <div>
                <div class="settings-label">开发者模式</div>
                <div class="settings-desc">显示引擎日志与调试信息（普通用户无需开启）</div>
              </div>
              <button class="btn-ghost pill" on:click={toggleDevMode}>
                {devMode ? "已开启" : "已关闭"}
              </button>
            </div>
          </div>

          {#if devMode}
          <div class="card log-card">
            <div class="log-header">
              <h3 class="settings-title">日志监控</h3>
              <div class="log-controls">
                <label class="log-toggle">
                  <input type="checkbox" bind:checked={logsAutoRefresh} />
                  <span>自动刷新</span>
                </label>
                <button class="btn-ghost pill" on:click={() => loadLogs()}>刷新</button>
              </div>
            </div>
            <div class="log-body">
              {#if logs.length === 0}
                <div class="log-empty">暂无日志，点击刷新或等待自动刷新</div>
              {:else}
                {#each logs as log, i}
                  <div class="log-line">
                    <span class="log-num">{i + 1}</span>
                    <span class="log-text">{log}</span>
                  </div>
                {/each}
              {/if}
            </div>
            <div class="log-footer">
              <span>日志文件: /tmp/tonelab_sidecar.log</span>
              <button class="btn-ghost pill" on:click={() => { logs = []; loadLogs(); }}>清空视图</button>
            </div>
          </div>
          {/if}
        </div>
      </div>
    {/if}
  </main>
  {/if}
</div>

<style>
  /* ═══════ 全局布局 ═══════ */
  /* ═══ 首次启动向导 ═══ */
  .onboard {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    background: var(--bg);
  }
  .onboard-card {
    max-width: 460px;
    padding: 48px 40px;
    background: var(--surface);
    border-radius: 20px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.08);
    text-align: center;
  }
  .onboard-brand {
    font-size: 40px;
    color: var(--accent);
    margin-bottom: 12px;
  }
  .onboard-title { font-size: 24px; font-weight: 700; margin: 0 0 8px; }
  .onboard-sub { color: var(--text-secondary); font-size: 14px; line-height: 1.7; margin: 0 0 28px; }
  .onboard-btn { width: 100%; padding: 12px; font-size: 15px; }
  .onboard-hint { color: var(--text-tertiary); font-size: 12px; margin-top: 12px; }
  .onboard-log {
    margin-top: 16px; padding: 12px; background: #f6f4ef; border-radius: 8px;
    font-size: 11px; font-family: monospace; text-align: left; white-space: pre-wrap;
    max-height: 160px; overflow-y: auto; color: #555;
  }
  .onboard-installing { display: flex; flex-direction: column; align-items: center; gap: 12px; }
  .onboard-installing p { color: var(--text-secondary); font-size: 14px; }
  .onboard-ok { color: var(--accent); font-weight: 600; }
  .spin { animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .app {
    display: flex;
    width: 100vw;
    height: 100vh;
    padding: 12px;
    gap: 12px;
  }

  /* ═══════ 侧边栏 ═══════ */
  .sidebar {
    width: 72px;
    background: var(--surface);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 20px 0;
    flex-shrink: 0;
  }

  .brand {
    text-align: center;
    margin-bottom: 24px;
  }
  .brand-icon {
    width: 40px;
    height: 40px;
    background: var(--ink);
    color: var(--amber);
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    font-weight: 700;
    margin: 0 auto 6px;
  }
  .brand-name {
    font-size: 13px;
    font-weight: 700;
    letter-spacing: -0.3px;
  }
  .brand-sub {
    font-size: 10px;
    color: var(--text-tertiary);
    margin-top: 1px;
  }

  .nav {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 6px;
    align-items: center;
  }

  .nav-item {
    width: 44px;
    height: 44px;
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    transition: all 0.2s ease;
  }
  .nav-item:hover {
    background: var(--bg-elevated);
  }
  .nav-item.active {
    background: var(--ink);
    color: #fff;
  }

  .sidebar-bottom {
    margin-top: auto;
  }
  .user-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--accent), var(--amber));
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    font-weight: 600;
  }

  /* ═══════ 主区域 ═══════ */
  .main {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    overflow: hidden;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 20px 16px;
    flex-shrink: 0;
  }

  .greeting {
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }
  .greeting-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 2px;
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .search-box {
    display: flex;
    align-items: center;
    gap: 8px;
    background: var(--surface);
    border-radius: var(--radius-pill);
    padding: 8px 16px;
    width: 280px;
    box-shadow: var(--shadow-sm);
  }
  .search-icon {
    font-size: 13px;
    opacity: 0.5;
  }
  .search-box input {
    flex: 1;
    font-size: 13px;
    color: var(--text-primary);
  }
  .search-box input::placeholder {
    color: var(--text-tertiary);
  }

  /* ═══════ 按钮 ═══════ */
  .btn-dark {
    background: var(--ink);
    color: #fff;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s ease;
  }
  .btn-dark:hover { opacity: 0.9; }

  .btn-accent {
    background: var(--accent);
    color: #fff;
    padding: 10px 20px;
    font-weight: 600;
    font-size: 13px;
    transition: all 0.2s ease;
  }
  .btn-accent:hover:not(:disabled) {
    background: #e86555;
  }
  .btn-accent:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-ghost {
    background: var(--bg-elevated);
    color: var(--text-primary);
    padding: 8px 16px;
    font-weight: 500;
    font-size: 12px;
  }
  .btn-ghost:hover {
    background: var(--border-light);
  }

  .pill { border-radius: var(--radius-pill); }
  /* 按钮内 SVG 图标对齐 */
  .btn-accent, .btn-dark, .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    justify-content: center;
  }
  .btn-accent :global(svg),
  .btn-dark :global(svg),
  .btn-ghost :global(svg) {
    flex-shrink: 0;
  }

  .icon-btn-sm {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    background: rgba(0,0,0,0.05);
  }
  .icon-btn-xs {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    color: var(--text-tertiary);
  }
  .icon-btn-xs:hover { background: var(--bg-elevated); color: var(--text-primary); }

  .text-btn {
    font-size: 12px;
    color: var(--text-secondary);
    font-weight: 500;
  }
  .text-btn:hover { color: var(--text-primary); }

  .spin {
    display: inline-block;
    animation: spin 1s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  /* ═══════ 卡片 ═══════ */
  .content {
    flex: 1;
    overflow-y: auto;
    padding: 0 20px 20px;
  }

  /* 生成台两列布局 */
  .generate-layout {
    display: grid;
    grid-template-columns: 360px 1fr;
    gap: 16px;
    align-items: start;
  }
  .gen-col-left {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .gen-col-right {
    min-height: 500px;
  }

  /* 旧 row 类兼容（模型库等其他页面仍用） */
  .row-top {
    display: grid;
    grid-template-columns: 3fr 2fr;
    gap: 16px;
    margin-bottom: 16px;
  }
  .row-bottom {
    display: grid;
    grid-template-columns: 2fr 3fr;
    gap: 16px;
  }

  .card {
    background: var(--surface);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-md);
    padding: 20px;
  }

  .card-taupe {
    background: var(--surface-taupe);
    color: var(--text-primary);
  }

  .card-dark {
    background: var(--surface-dark);
    color: var(--text-on-dark);
    box-shadow: var(--shadow-dark);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
  }
  .card-header h3 {
    font-size: 15px;
    font-weight: 600;
  }

  /* 顶部两行布局 */
  .row-top {
    display: grid;
    grid-template-columns: 3fr 2fr;
    gap: 16px;
    margin-bottom: 16px;
  }

  .row-bottom {
    display: grid;
    grid-template-columns: 2fr 3fr;
    gap: 16px;
  }

  /* ═══════ 概览气泡图 ═══════ */
  .card-stat {
    min-height: 280px;
    position: relative;
  }

  .bubble-chart {
    position: relative;
    height: 180px;
    margin: 20px 0;
  }

  .bubble {
    position: absolute;
    border-radius: 50%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    box-shadow: var(--shadow-soft);
  }
  .bubble-large {
    width: 140px;
    height: 140px;
    background: radial-gradient(circle at 30% 30%, var(--amber-light), var(--amber));
    right: 40px;
    top: 10px;
  }
  .bubble-medium {
    width: 100px;
    height: 100px;
    background: radial-gradient(circle at 30% 30%, var(--accent-light), var(--accent));
    right: 140px;
    bottom: 0;
    color: #fff;
  }
  .bubble-small {
    width: 72px;
    height: 72px;
    background: radial-gradient(circle at 30% 30%, #4a4f5a, var(--ink));
    right: 20px;
    bottom: 30px;
    color: #fff;
  }

  .bubble-value {
    font-size: 20px;
    font-weight: 700;
    line-height: 1.2;
  }
  .bubble-large .bubble-value { font-size: 26px; }
  .bubble-label {
    font-size: 10px;
    opacity: 0.8;
    margin-top: 2px;
  }

  .legend {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: auto;
    position: absolute;
    left: 20px;
    bottom: 20px;
  }
  .legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  .legend-dot {
    width: 24px;
    height: 6px;
    border-radius: var(--radius-pill);
  }
  .legend-dot.amber { background: var(--amber); }
  .legend-dot.coral { background: var(--accent); }
  .legend-dot.ink { background: var(--ink); }

  /* ═══════ 快速生成 ═══════ */
  .card-dark .card-header h3 { color: #fff; }

  .engine-select {
    background: rgba(255,255,255,0.1);
    color: #fff;
    padding: 6px 12px;
    border-radius: var(--radius-pill);
    font-size: 12px;
    border: none;
    outline: none;
  }
  .engine-select option {
    color: var(--text-primary);
    background: #fff;
  }

  .prompt-input {
    width: 100%;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: var(--radius-md);
    padding: 12px 14px;
    color: #fff;
    font-size: 13px;
    resize: none;
    margin-bottom: 12px;
    font-family: inherit;
  }
  .prompt-input::placeholder {
    color: rgba(255,255,255,0.3);
  }
  .prompt-input:focus {
    border-color: rgba(255,255,255,0.2);
    background: rgba(255,255,255,0.08);
  }

  .preset-cats {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-bottom: 8px;
  }
  .enhance-row {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 8px;
    padding: 6px 0;
  }
  .enhance-group {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px;
  }
  .enhance-label {
    font-size: 11px;
    color: var(--text-tertiary);
    margin-right: 4px;
  }
  .enhance-btn {
    background: transparent;
    border: 1px solid var(--border);
    color: var(--text-tertiary);
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    font-size: 11px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .enhance-btn:hover {
    color: var(--text-secondary);
    border-color: var(--text-tertiary);
  }
  .enhance-active {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
  }
  .cat-btn {
    background: transparent;
    color: var(--text-tertiary);
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    font-size: 11px;
    transition: all 0.2s ease;
  }
  .cat-btn:hover {
    color: var(--text-secondary);
    background: var(--bg-elevated);
  }
  .cat-active {
    color: var(--text-primary) !important;
    background: var(--bg-elevated) !important;
    font-weight: 600;
  }

  .preset-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 14px;
  }
  .chip {
    background: rgba(255,255,255,0.06);
    color: rgba(255,255,255,0.7);
    padding: 5px 10px;
    border-radius: var(--radius-pill);
    font-size: 11px;
    display: flex;
    align-items: center;
    gap: 4px;
    transition: all 0.2s ease;
  }
  .chip:hover {
    background: rgba(255,255,255,0.12);
    color: #fff;
  }
  .chip-active {
    background: var(--accent) !important;
    color: #fff !important;
  }

  .gen-params {
    display: flex;
    gap: 10px;
    align-items: flex-end;
  }

  .advanced-toggle {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    margin-top: 8px;
    border-radius: 8px;
    background: var(--bg-elevated);
    cursor: pointer;
    font-size: 12px;
    color: var(--text-secondary);
    user-select: none;
  }

  .advanced-toggle:hover {
    background: var(--border);
  }

  .adv-caret {
    font-size: 10px;
    opacity: 0.7;
  }

  .advanced-panel {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    padding: 12px;
    margin-top: 8px;
    border-radius: 8px;
    background: var(--bg-elevated);
  }
  /* 高级参数在浅色悬浮层上，输入框必须深色字，否则白字白底看不见 */
  .advanced-panel .param-input {
    background: #fff;
    border: 1px solid #e2ded4;
    color: #1a1a1a;
  }
  .param-bpm { grid-column: 1 / -1; }
  .param-bpm-presets {
    grid-column: 1 / -1;
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .bpm-chip {
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid #e2ded4;
    background: #fff;
    color: #555;
    font-size: 12px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .bpm-chip:hover { border-color: var(--accent); color: var(--accent); }
  .bpm-chip.active {
    background: var(--accent);
    border-color: var(--accent);
    color: #fff;
    font-weight: 600;
  }
  .bpm-hint {
    grid-column: 1 / -1;
    font-size: 11px;
    color: #8a8578;
    line-height: 1.6;
    padding: 8px 10px;
    background: #faf8f3;
    border-radius: 8px;
    border: 1px solid #eee9df;
  }
  .advanced-panel .param label {
    color: #6b6b6b;
  }

  .advanced-panel .param label {
    font-size: 11px;
  }
  .param {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .param.flex-2 { flex: 1; }
  .param label {
    font-size: 11px;
    color: rgba(255,255,255,0.4);
  }
  .param-input {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: var(--radius-md);
    padding: 8px 10px;
    color: #fff;
    font-size: 13px;
    width: 100px;
  }
  .param.flex-2 .param-input { width: 100%; }

  .generate-btn {
    height: 40px;
    padding: 0 20px;
  }

  .error-text {
    color: #ff6b6b;
    font-size: 12px;
    margin-top: 10px;
  }

  /* ═══════ 播放面板 ═══════ */
  .player {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .player-art {
    width: 100%;
    height: 120px;
    border-radius: var(--radius-md);
    background: linear-gradient(135deg, var(--accent-soft), var(--amber-soft));
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .note-icon :global(svg) {
    color: var(--accent);
    opacity: 0.6;
  }
  .player-info { text-align: center; }
  .player-title { font-size: 15px; font-weight: 600; }
  .player-sub { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
  .audio-player { width: 100%; margin-top: 4px; }

  .placeholder {
    text-align: center;
    padding: 30px 20px;
    color: var(--text-tertiary);
  }
  .placeholder-icon :global(svg) {
    margin-bottom: 10px;
    opacity: 0.4;
    color: var(--text-tertiary);
  }
  .placeholder p { font-size: 13px; }
  .placeholder-sub {
    font-size: 11px;
    color: var(--text-tertiary);
    margin-top: 4px;
    opacity: 0.7;
  }

  .loading-ring {
    width: 32px;
    height: 32px;
    border: 3px solid var(--accent-soft);
    border-top-color: var(--accent);
    border-radius: 50%;
    margin: 0 auto 12px;
    animation: spin 1s linear infinite;
  }

  /* ═══════ 历史列表 ═══════ */
  .history-list {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .history-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 10px 12px;
    border-radius: var(--radius-md);
    transition: background 0.2s ease;
  }
  .history-item:hover {
    background: var(--bg-elevated);
  }
  .history-avatar {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-md);
    background: var(--bg-elevated);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
  }
  .history-info { flex: 1; min-width: 0; }
  .history-name {
    font-size: 13px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .history-audio {
    width: 100%;
    height: 32px;
    margin-top: 6px;
    border-radius: 8px;
    background: var(--card);
  }
  .history-meta {
    font-size: 11px;
    color: var(--text-tertiary);
    margin-top: 2px;
  }
  .history-actions {
    display: flex;
    gap: 4px;
    flex-shrink: 0;
  }

  /* ═══════ 页面通用 ═══════ */
  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    margin-bottom: 20px;
  }
  .page-title {
    font-size: 22px;
    font-weight: 700;
  }
  .page-sub {
    font-size: 13px;
    color: var(--text-secondary);
    margin-top: 4px;
  }
  .player-stats {
    font-size: 11px;
    color: var(--text-tertiary);
    margin-top: 6px;
    font-family: "SF Mono", monospace;
  }

  .model-summary {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  .summary-icon :global(svg) {
    width: 14px;
    height: 14px;
  }
  .summary-icon.ready { color: var(--accent); }
  .summary-icon.pending { color: var(--text-tertiary); }
  .summary-sep { color: var(--text-tertiary); }

  /* ═══════ 模型网格 ═══════ */
  .model-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 16px;
  }

  .models-error {
    grid-column: 1 / -1;
    padding: 24px;
    border-radius: 12px;
    background: var(--bg-elevated);
    color: var(--text-secondary);
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
  }

  /* ═══ 日志监控 ═══ */
  .log-card {
    grid-column: 1 / -1;
  }

  .log-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .log-controls {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .log-toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary);
    cursor: pointer;
  }

  .log-toggle input {
    accent-color: var(--accent);
  }

  .log-body {
    height: 320px;
    overflow-y: auto;
    background: #1a1c21;
    border-radius: 10px;
    padding: 10px;
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
    font-size: 11px;
    line-height: 1.6;
  }

  .log-line {
    display: flex;
    gap: 8px;
    padding: 1px 0;
    white-space: pre-wrap;
    word-break: break-all;
  }

  .log-num {
    color: #666;
    flex-shrink: 0;
    min-width: 32px;
    text-align: right;
    user-select: none;
  }

  .log-text {
    color: #cfd3dc;
  }

  .log-empty {
    color: #888;
    text-align: center;
    padding: 40px 0;
  }

  .log-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 10px;
    font-size: 11px;
    color: var(--text-tertiary);
  }

  .model-card {
    display: flex;
    flex-direction: column;
    gap: 12px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
  }
  .model-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
  }

  .model-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
  }
  .model-icon {
    width: 44px;
    height: 44px;
    border-radius: var(--radius-md);
    background: linear-gradient(135deg, var(--accent-soft), var(--amber-soft));
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
  }
  .model-status-badge {
    font-size: 10px;
    padding: 4px 10px;
    border-radius: var(--radius-pill);
    font-weight: 600;
  }
  .status-ready { background: var(--accent-soft); color: var(--accent); }
  .status-downloading { background: var(--amber-soft); color: #c9a010; }
  .status-paused { background: var(--bg-elevated); color: var(--text-secondary); }
  .status-partial { background: var(--amber-soft); color: #c9a010; }
  .status-not_installed { background: var(--bg-elevated); color: var(--text-tertiary); }
  .status-error { background: #ffe5e5; color: #e53935; }

  .model-name {
    font-size: 15px;
    font-weight: 600;
  }
  .model-tagline {
    font-size: 12px;
    color: var(--text-secondary);
    line-height: 1.4;
  }

  .model-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .meta-item {
    font-size: 11px;
    color: var(--text-tertiary);
  }
  .meta-tag {
    font-size: 10px;
    padding: 3px 8px;
    border-radius: var(--radius-pill);
    background: var(--bg-elevated);
    color: var(--text-secondary);
  }

  .progress-section { margin-top: 10px; }
  .progress-bar {
    height: 12px;
    background: var(--bg-elevated);
    border-radius: var(--radius-pill);
    overflow: hidden;
  }
  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--amber));
    border-radius: var(--radius-pill);
    transition: width 0.5s ease;
  }
  .progress-meta {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 8px;
    font-size: 11px;
  }
  .progress-pct {
    font-weight: 700;
    color: var(--text-primary);
    font-size: 13px;
    font-variant-numeric: tabular-nums;
  }
  .progress-size-label {
    color: var(--text-secondary);
    font-size: 11px;
  }
  .progress-stats {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .speed { font-weight: 600; font-size: 11px; font-variant-numeric: tabular-nums; }
  .speed.speed-fast { color: var(--accent); }
  .speed.speed-slow { color: var(--amber); }
  .eta { color: var(--text-tertiary); font-size: 11px; font-variant-numeric: tabular-nums; }

  .model-actions {
    display: flex;
    gap: 8px;
    margin-top: auto;
    padding-top: 4px;
  }
  .model-actions button { flex: 1; }

  /* ═══════ 设置页 ═══════ */
  .settings-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }
  .settings-title {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 12px;
  }
  .settings-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 0;
    border-top: 1px solid var(--border-light);
  }
  .settings-item:first-of-type { border-top: none; }
  .settings-label {
    font-size: 13px;
    font-weight: 500;
  }
  .settings-desc {
    font-size: 11px;
    color: var(--text-tertiary);
    margin-top: 2px;
  }
  .value-pill {
    background: var(--bg-elevated);
    padding: 6px 12px;
    font-size: 12px;
    font-weight: 500;
  }
  .select-sm {
    padding: 6px 12px;
    font-size: 12px;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text-primary);
  }

  /* 大历史列表 */
  .history-list-large .history-item {
    padding: 14px;
    border-bottom: 1px solid var(--border-light);
  }
  .history-list-large .history-item:last-child { border-bottom: none; }
  .history-item-lg .history-avatar { width: 44px; height: 44px; }
  .history-item-lg .history-name { font-size: 14px; }
  .history-actions-lg {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }
  .history-actions-lg .btn-ghost {
    padding: 6px 10px;
    font-size: 11px;
  }
  .history-desc {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 2px;
  }

  /* 响应式 */
  @media (max-width: 1100px) {
    .row-top, .row-bottom {
      grid-template-columns: 1fr;
    }
    .settings-grid {
      grid-template-columns: 1fr;
    }
  }

  /* ═══ 音乐库 ═══ */
  .library-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 16px;
  }
  .library-card {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .library-card-head {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .library-name {
    font-size: 16px;
    font-weight: 700;
    margin: 0;
  }
  .library-desc {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0;
    line-height: 1.6;
  }
  .badge {
    padding: 2px 8px;
    border-radius: var(--radius-pill);
    font-size: 11px;
    font-weight: 600;
  }
  .badge-green { background: #e3f2e5; color: #2e7d32; }
  .badge-blue { background: #e3f0fa; color: #1565c0; }
  .badge-dark { background: #ececec; color: #424242; }
  @media (max-width: 1100px) {
    .library-grid { grid-template-columns: 1fr; }
  }
</style>
