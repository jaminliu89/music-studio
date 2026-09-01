<script>
  import { directScore } from './lib/dme/directorPipeline.js';
  import { routeProvider, compileForCurrentRuntime } from './lib/dme/providerRouter.js';

  let mode = 'scene_description';
  let text = '父亲骑着三轮车回家，我突然发现他老了。';
  let duration = 45;
  let projectType = 'documentary';
  let qualityPriority = 'balanced';
  let privacyMode = 'hybrid';
  let requiresVocals = false;
  let requiresLongStructure = false;
  let blueprint = null;
  let routing = null;
  let runtime = null;
  let revision = '';

  const modes = [
    ['scene_description', 'Describe a Scene', '描述场景'],
    ['script', 'Script', '剧本'],
    ['voiceover', 'Voiceover', '旁白'],
    ['video', 'Video Context', '视频语境'],
  ];

  function score() {
    blueprint = directScore(text, {
      mode,
      duration: Number(duration),
      projectType,
      voiceoverPriority: mode === 'voiceover' ? 'high' : 'medium',
    });

    routing = routeProvider(blueprint, {
      privacyMode: privacyMode === 'local' ? 'local_only' : undefined,
      requiresVocals,
      requiresLongStructure,
      qualityPriority,
      videoContext: mode === 'video',
      aceReady: true,
    });

    runtime = compileForCurrentRuntime(blueprint);
  }

  function applyRevision() {
    if (!revision.trim()) return;
    const lower = revision.toLowerCase();
    if (lower.includes('克制') || lower.includes('煽情') || lower.includes('restrain')) {
      blueprint = {
        ...blueprint,
        music: {
          ...blueprint.music,
          intensity: Math.max(0.15, (blueprint.music.intensity ?? 0.5) - 0.2),
          instrumentation: blueprint.music.instrumentation.filter((x) => !/strings/i.test(x)),
        },
        revisionNote: revision,
      };
    } else {
      blueprint = { ...blueprint, revisionNote: revision };
    }
    routing = routeProvider(blueprint, {
      privacyMode: privacyMode === 'local' ? 'local_only' : undefined,
      requiresVocals,
      requiresLongStructure,
      qualityPriority,
      videoContext: mode === 'video',
      aceReady: true,
    });
    runtime = compileForCurrentRuntime(blueprint);
    revision = '';
  }

  score();
</script>

<svelte:head>
  <title>Director Music Engine</title>
  <meta name="description" content="Story to Score — AI music direction workspace" />
</svelte:head>

<div class="shell">
  <header class="topbar">
    <div>
      <div class="eyebrow">DIRECTOR MUSIC ENGINE</div>
      <h1>Story → Score</h1>
    </div>
    <nav>
      <a href="?legacy=1">ToneLab Local</a>
      <span>Project DNA</span>
      <span>Music Genome</span>
    </nav>
  </header>

  <main>
    <section class="hero">
      <div class="statement">
        <p class="kicker">你正在制作什么？</p>
        <h2>不要写音乐提示词。<br />先把故事告诉导演。</h2>
        <p class="lede">DME 先理解人物、场景、情绪和叙事功能，再决定音乐应该何时出现、做到什么程度、由哪个模型完成。</p>
      </div>

      <div class="mode-grid">
        {#each modes as item}
          <button class:active={mode === item[0]} on:click={() => (mode = item[0])}>
            <span>{item[1]}</span>
            <small>{item[2]}</small>
          </button>
        {/each}
      </div>

      <textarea bind:value={text} placeholder="描述一个场景、粘贴旁白或剧本……" rows="6"></textarea>

      <div class="controls">
        <label>类型
          <select bind:value={projectType}>
            <option value="documentary">纪录片</option>
            <option value="youtube">YouTube</option>
            <option value="short">短视频</option>
            <option value="film">电影 / 短片</option>
            <option value="brand">品牌片</option>
          </select>
        </label>
        <label>时长
          <input type="number" min="3" max="600" bind:value={duration} />
        </label>
        <label>质量优先级
          <select bind:value={qualityPriority}>
            <option value="balanced">平衡</option>
            <option value="premium">Premium</option>
          </select>
        </label>
        <label>运行方式
          <select bind:value={privacyMode}>
            <option value="hybrid">自动选择</option>
            <option value="local">只用本地</option>
          </select>
        </label>
      </div>

      <div class="toggles">
        <label><input type="checkbox" bind:checked={requiresVocals} /> 需要人声</label>
        <label><input type="checkbox" bind:checked={requiresLongStructure} /> 长程结构</label>
      </div>

      <button class="score" on:click={score}>Score This <span>为作品配乐</span></button>
    </section>

    {#if blueprint}
      <section class="workspace">
        <aside class="story-panel">
          <div class="section-label">STORY INTELLIGENCE</div>
          <h3>{blueprint.title}</h3>

          <dl>
            <div><dt>叙事功能</dt><dd>{blueprint.narrative.function}</dd></div>
            <div><dt>项目</dt><dd>{blueprint.projectType}</dd></div>
            <div><dt>时长</dt><dd>{blueprint.duration}s</dd></div>
          </dl>

          <div class="arc">
            <span>{blueprint.emotion.start}</span>
            <i>→</i>
            <span>{blueprint.emotion.development}</span>
            <i>→</i>
            <span>{blueprint.emotion.turn}</span>
            <i>→</i>
            <strong>{blueprint.emotion.peak}</strong>
            <i>→</i>
            <span>{blueprint.emotion.resolution}</span>
          </div>
        </aside>

        <section class="score-panel">
          <div class="section-label">SCORE BLUEPRINT</div>
          <div class="score-meta">
            <div><small>BPM</small><strong>{blueprint.music.bpm.min}–{blueprint.music.bpm.max}</strong></div>
            <div><small>VOICE</small><strong>{blueprint.voiceover.priority}</strong></div>
            <div><small>INTENSITY</small><strong>{Math.round((blueprint.music.intensity ?? 0.5) * 100)}%</strong></div>
          </div>

          <div class="timeline">
            {#each blueprint.structure as section}
              <div class="cue" style={`flex:${Math.max(1, section.end - section.start)}`}>
                <span>{section.function}</span>
                <small>{section.start}s–{section.end}s</small>
              </div>
            {/each}
          </div>

          <div class="instrumentation">
            {#each blueprint.music.instrumentation as instrument}
              <span>{instrument}</span>
            {/each}
          </div>

          <div class="director-note">
            <div>
              <small>DIRECTOR ROUTING</small>
              <strong>{routing?.provider}</strong>
              <p>{routing?.reason}</p>
            </div>
            <button>Generate Versions</button>
          </div>
        </section>
      </section>

      <section class="versions">
        <div class="version featured"><small>A</small><strong>Director Pick</strong><span>导演推荐</span></div>
        <div class="version"><small>B</small><strong>Restrained</strong><span>更克制</span></div>
        <div class="version"><small>C</small><strong>Cinematic</strong><span>更电影</span></div>
        <div class="version"><small>D</small><strong>Raw</strong><span>更真实</span></div>
      </section>

      <section class="revision">
        <div>
          <div class="section-label">DIRECT THE MUSIC</div>
          <h3>像跟音乐导演说话一样修改。</h3>
        </div>
        <div class="revision-box">
          <input bind:value={revision} on:keydown={(e) => e.key === 'Enter' && applyRevision()} placeholder="例如：这里太煽情，把弦乐拿掉，晚一点进入……" />
          <button on:click={applyRevision}>Apply</button>
        </div>
        {#if blueprint.revisionNote}<p class="applied">Last direction: {blueprint.revisionNote}</p>{/if}
      </section>

      <details class="runtime-debug">
        <summary>Runtime Contract</summary>
        <pre>{JSON.stringify(runtime, null, 2)}</pre>
      </details>
    {/if}
  </main>
</div>

<style>
  :global(*) { box-sizing: border-box; }
  :global(body) { margin: 0; background: #f3efe6; color: #181714; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  :global(button), :global(input), :global(select), :global(textarea) { font: inherit; }
  .shell { min-height: 100vh; }
  .topbar { min-height: 92px; padding: 24px 4vw; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(24,23,20,.16); }
  .topbar h1 { margin: 3px 0 0; font-size: 21px; letter-spacing: -.03em; font-weight: 560; }
  .eyebrow, .section-label { font-size: 10px; letter-spacing: .18em; font-weight: 700; opacity: .54; }
  nav { display: flex; gap: 24px; font-size: 12px; align-items: center; }
  nav a, nav span { color: inherit; text-decoration: none; opacity: .58; }
  main { width: min(1400px, 92vw); margin: 0 auto; padding: 7vh 0 12vh; }
  .hero { max-width: 1040px; margin: 0 auto; }
  .statement { max-width: 760px; }
  .kicker { font-family: Georgia, serif; font-style: italic; margin: 0 0 12px; opacity: .58; }
  h2 { font-family: Georgia, "Times New Roman", serif; font-size: clamp(40px, 6vw, 82px); line-height: .98; font-weight: 400; letter-spacing: -.045em; margin: 0; }
  .lede { max-width: 680px; margin: 24px 0 46px; font-size: 15px; line-height: 1.8; opacity: .62; }
  .mode-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-bottom: 10px; }
  .mode-grid button { min-height: 68px; text-align: left; border: 1px solid rgba(24,23,20,.14); background: transparent; padding: 14px 16px; cursor: pointer; }
  .mode-grid button.active { background: #1a1916; color: #f6f1e7; border-color: #1a1916; }
  .mode-grid span, .mode-grid small { display: block; }
  .mode-grid small { opacity: .56; margin-top: 6px; }
  textarea { width: 100%; resize: vertical; border: 1px solid rgba(24,23,20,.18); background: rgba(255,255,255,.2); padding: 24px; font-family: Georgia, serif; font-size: 23px; line-height: 1.55; outline: none; }
  textarea:focus, input:focus, select:focus { border-color: rgba(24,23,20,.55); outline: none; }
  .controls { display: grid; grid-template-columns: 1.2fr .7fr 1fr 1fr; gap: 8px; margin-top: 8px; }
  .controls label { font-size: 10px; letter-spacing: .08em; opacity: .7; border: 1px solid rgba(24,23,20,.12); padding: 10px 12px; }
  .controls select, .controls input { display: block; width: 100%; border: none; background: transparent; padding: 6px 0 0; color: inherit; }
  .toggles { display: flex; gap: 24px; margin: 16px 0; font-size: 12px; opacity: .72; }
  .score { border: none; background: #1a1916; color: #f6f1e7; padding: 16px 22px; cursor: pointer; font-weight: 650; }
  .score span { opacity: .55; margin-left: 10px; font-weight: 400; }
  .workspace { margin-top: 12vh; display: grid; grid-template-columns: 320px 1fr; border-top: 1px solid rgba(24,23,20,.2); border-bottom: 1px solid rgba(24,23,20,.2); }
  .story-panel, .score-panel { padding: 30px 0; }
  .story-panel { padding-right: 32px; border-right: 1px solid rgba(24,23,20,.14); }
  .score-panel { padding-left: 32px; }
  .story-panel h3, .revision h3 { font-family: Georgia, serif; font-size: 28px; font-weight: 400; margin: 16px 0 26px; }
  dl { margin: 0 0 34px; }
  dl div { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid rgba(24,23,20,.09); font-size: 12px; }
  dt { opacity: .5; } dd { margin: 0; }
  .arc { display: flex; flex-direction: column; gap: 7px; font-family: Georgia, serif; font-size: 15px; }
  .arc i { opacity: .3; font-style: normal; }
  .arc strong { font-size: 20px; font-weight: 400; }
  .score-meta { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin: 22px 0 34px; }
  .score-meta div { border-left: 1px solid rgba(24,23,20,.18); padding-left: 12px; }
  .score-meta small, .score-meta strong { display: block; }
  .score-meta small { font-size: 9px; opacity: .45; letter-spacing: .1em; }
  .score-meta strong { margin-top: 5px; font-family: Georgia, serif; font-size: 22px; font-weight: 400; }
  .timeline { height: 120px; display: flex; align-items: stretch; gap: 2px; border-top: 1px solid rgba(24,23,20,.18); border-bottom: 1px solid rgba(24,23,20,.18); padding: 10px 0; }
  .cue { min-width: 74px; background: rgba(24,23,20,.06); padding: 10px; display: flex; flex-direction: column; justify-content: space-between; }
  .cue span { font-family: Georgia, serif; font-size: 13px; } .cue small { opacity: .4; font-size: 9px; }
  .instrumentation { display: flex; flex-wrap: wrap; gap: 7px; margin: 20px 0; }
  .instrumentation span { border: 1px solid rgba(24,23,20,.13); padding: 7px 9px; font-size: 10px; }
  .director-note { margin-top: 28px; padding-top: 22px; border-top: 1px solid rgba(24,23,20,.12); display: flex; justify-content: space-between; gap: 24px; align-items: end; }
  .director-note small, .director-note strong { display:block; }.director-note strong { margin-top: 5px; font-family: Georgia,serif; font-size: 22px; font-weight:400; }.director-note p { opacity:.55; font-size:11px; margin-bottom:0; }
  .director-note button { border: 1px solid #1a1916; background: transparent; padding: 12px 14px; }
  .versions { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-top:8px; }
  .version { min-height: 105px; border:1px solid rgba(24,23,20,.14); padding:14px; display:flex; flex-direction:column; justify-content:space-between; }.version.featured{background:#1a1916;color:#f6f1e7}.version small{opacity:.45}.version strong{font-family:Georgia,serif;font-size:18px;font-weight:400}.version span{font-size:10px;opacity:.5}
  .revision { margin-top: 10vh; display:grid; grid-template-columns: 300px 1fr; gap:40px; align-items:end; }
  .revision h3 { margin-bottom:0; }
  .revision-box { display:flex; border-bottom:1px solid rgba(24,23,20,.4); }
  .revision-box input { flex:1; border:none; background:transparent; padding:16px 0; font-family:Georgia,serif; font-size:18px; }.revision-box button{border:none;background:transparent;font-weight:650;cursor:pointer}.applied{grid-column:2;font-size:11px;opacity:.5}
  .runtime-debug { margin-top:60px; opacity:.55; font-size:11px; }.runtime-debug pre{overflow:auto;background:rgba(24,23,20,.04);padding:18px;}
  @media (max-width: 820px) { .topbar nav{display:none}.mode-grid,.versions{grid-template-columns:1fr 1fr}.controls{grid-template-columns:1fr 1fr}.workspace,.revision{grid-template-columns:1fr}.story-panel{border-right:none;border-bottom:1px solid rgba(24,23,20,.14);padding-right:0}.score-panel{padding-left:0}.applied{grid-column:auto} }
</style>
