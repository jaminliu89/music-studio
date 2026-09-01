<script>
  import { directScore } from './lib/dme/directorPipeline.js';
  import { routeProvider, compileForCurrentRuntime } from './lib/dme/providerRouter.js';
  import { generateFromBlueprint, getRuntimeCapabilities } from './lib/dme/generationGateway.js';

  let mode = 'scene_description';
  let text = '父亲骑着三轮车回家，我突然发现他老了。';
  let duration = 30;
  let projectType = 'documentary';
  let qualityPriority = 'balanced';
  let privacyMode = 'hybrid';
  let blueprint;
  let routing;
  let runtime;
  let revision = '';
  let generationState = 'idle';
  let generationError = '';
  let result = null;
  let selectedVariant = 'director';
  let capabilities = null;

  const modes = [
    ['scene_description', 'Describe', '描述场景'],
    ['script', 'Script', '剧本'],
    ['voiceover', 'Voiceover', '旁白'],
    ['video', 'Video', '视频语境'],
  ];

  const variants = [
    ['director', 'Director Pick', '导演推荐'],
    ['restrained', 'Restrained', '更克制'],
    ['cinematic', 'Cinematic', '更电影'],
    ['raw', 'Raw', '更真实'],
  ];

  function buildScore() {
    revokeAudio();
    result = null;
    generationError = '';
    generationState = 'directing';

    blueprint = directScore(text, {
      mode,
      duration: Number(duration),
      projectType,
      voiceoverPriority: mode === 'voiceover' ? 'high' : 'medium',
    });

    routing = routeProvider(blueprint, {
      privacyMode: privacyMode === 'local' ? 'local_only' : undefined,
      qualityPriority,
      videoContext: mode === 'video',
      aceReady: true,
    });
    runtime = compileForCurrentRuntime(blueprint);
    generationState = 'ready_to_generate';
  }

  async function generateVersion(variant = selectedVariant) {
    if (!blueprint) buildScore();
    selectedVariant = variant;
    generationError = '';
    generationState = 'generating';

    const generated = await generateFromBlueprint({
      blueprint,
      routing,
      runtimePayload: runtime,
      variant,
    });

    if (generated.success) {
      revokeAudio();
      result = generated;
      generationState = 'ready';
    } else {
      result = generated;
      generationError = generated.error || 'Generation failed';
      generationState = generated.status || 'failed';
    }
  }

  function applyRevision() {
    const note = revision.trim();
    if (!note || !blueprint) return;
    const lower = note.toLowerCase();
    let music = { ...blueprint.music };

    if (lower.includes('克制') || lower.includes('煽情') || lower.includes('restrain')) {
      music.intensity = Math.max(0.15, (music.intensity ?? 0.5) - 0.2);
      music.instrumentation = music.instrumentation.filter((x) => !/strings/i.test(x));
    }
    if (lower.includes('不要鼓') || lower.includes('no drums')) {
      music.rhythm = 'no drums; sparse pulse only if structurally necessary';
    }
    if (lower.includes('更电影') || lower.includes('cinematic')) {
      music.intensity = Math.min(0.9, (music.intensity ?? 0.5) + 0.12);
      music.texture = `${music.texture}, cinematic depth and spatial development`;
    }

    blueprint = { ...blueprint, music, revisionNote: note };
    runtime = compileForCurrentRuntime(blueprint);
    routing = routeProvider(blueprint, {
      privacyMode: privacyMode === 'local' ? 'local_only' : undefined,
      qualityPriority,
      videoContext: mode === 'video',
      aceReady: true,
    });
    revision = '';
    revokeAudio();
    result = null;
    generationState = 'ready_to_generate';
  }

  function revokeAudio() {
    if (result?.audioUrl) URL.revokeObjectURL(result.audioUrl);
  }

  async function inspectRuntime() {
    capabilities = await getRuntimeCapabilities();
  }

  buildScore();
  inspectRuntime();
</script>

<svelte:head><title>Director Music Engine — Story to Score</title></svelte:head>

<div class="app-shell">
  <header>
    <div class="brand"><small>DIRECTOR MUSIC ENGINE</small><strong>Story → Score</strong></div>
    <nav><span class="live" class:offline={capabilities && !capabilities.ready}>● {capabilities?.ready ? 'Runtime Ready' : 'Runtime Check'}</span><a href="?legacy=1">ToneLab Local</a></nav>
  </header>

  <main>
    <section class="input-stage">
      <p class="serif overline">What are you making? / 你正在制作什么？</p>
      <h1>不要先想音乐。<br/>先把作品告诉导演。</h1>
      <p class="intro">场景、人物、旁白、冲突和情绪先进入导演层；音乐模型只是最后负责演奏。</p>

      <div class="mode-row">
        {#each modes as item}<button class:active={mode === item[0]} on:click={() => mode = item[0]}><b>{item[1]}</b><span>{item[2]}</span></button>{/each}
      </div>

      <textarea bind:value={text} rows="5" placeholder="描述场景、粘贴剧本或旁白……"></textarea>

      <div class="settings-row">
        <label>PROJECT<select bind:value={projectType}><option value="documentary">纪录片</option><option value="youtube">YouTube</option><option value="short">短视频</option><option value="film">电影 / 短片</option><option value="brand">品牌片</option></select></label>
        <label>DURATION<input type="number" min="3" max="600" bind:value={duration}/></label>
        <label>QUALITY<select bind:value={qualityPriority}><option value="balanced">Balanced</option><option value="premium">Premium</option></select></label>
        <label>RUNTIME<select bind:value={privacyMode}><option value="hybrid">Auto</option><option value="local">Local only</option></select></label>
      </div>
      <button class="primary" on:click={buildScore}>Score This <span>为作品配乐</span></button>
    </section>

    {#if blueprint}
      <section class="intelligence">
        <aside>
          <small class="label">STORY INTELLIGENCE</small>
          <h2>{blueprint.title}</h2>
          <div class="facts"><div><span>叙事功能</span><b>{blueprint.narrative.function}</b></div><div><span>Voiceover</span><b>{blueprint.voiceover.priority}</b></div><div><span>Duration</span><b>{blueprint.duration}s</b></div></div>
          <div class="emotion">
            <span>{blueprint.emotion.start}</span><i>↓</i><span>{blueprint.emotion.development}</span><i>↓</i><span>{blueprint.emotion.turn}</span><i>↓</i><strong>{blueprint.emotion.peak}</strong><i>↓</i><span>{blueprint.emotion.resolution}</span>
          </div>
        </aside>

        <div class="blueprint">
          <div class="blueprint-head"><div><small class="label">SCORE BLUEPRINT</small><h3>音乐不是风格选择，是叙事决策。</h3></div><div class="route"><small>ROUTED TO</small><b>{routing?.provider}</b><span>{routing?.reason}</span></div></div>
          <div class="metrics"><div><small>BPM</small><b>{blueprint.music.bpm.min}–{blueprint.music.bpm.max}</b></div><div><small>INTENSITY</small><b>{Math.round((blueprint.music.intensity ?? .5)*100)}%</b></div><div><small>TEXTURE</small><b>{blueprint.music.texture}</b></div></div>
          <div class="timeline">{#each blueprint.structure as cue}<div class="cue" style={`flex:${Math.max(1,cue.end-cue.start)}`}><b>{cue.function}</b><span>{cue.start}–{cue.end}s</span></div>{/each}</div>
          <div class="chips">{#each blueprint.music.instrumentation as item}<span>{item}</span>{/each}</div>
        </div>
      </section>

      <section class="versions-section">
        <div class="section-title"><small class="label">DIRECTOR VERSIONS</small><h2>同一个故事，四种导演判断。</h2></div>
        <div class="versions">
          {#each variants as item}
            <button class:selected={selectedVariant===item[0]} on:click={() => { selectedVariant=item[0]; generateVersion(item[0]); }} disabled={generationState==='generating'}>
              <small>{item[0][0].toUpperCase()}</small><b>{item[1]}</b><span>{item[2]}</span>
            </button>
          {/each}
        </div>

        <div class="player-stage">
          {#if generationState === 'generating'}
            <div class="status"><span class="pulse"></span><div><b>正在生成 {selectedVariant}</b><small>Blueprint → Gateway → {routing?.provider}</small></div></div>
          {:else if result?.success}
            <div class="audio-result">
              <div><small class="label">GENERATED SCORE</small><h3>{selectedVariant} · {result.actualEngine}</h3><p>{result.fallbackUsed ? `导演请求 ${result.requestedProvider}，当前运行环境自动回退到 ${result.actualEngine}` : `由 ${result.actualEngine} 执行`}</p></div>
              <audio controls src={result.audioUrl}></audio>
              <div class="provenance"><span>{result.duration ?? blueprint.duration}s</span><span>{result.generationTime ? `${result.generationTime}s generation` : ''}</span><span>{result.path?.split('/').pop()}</span></div>
            </div>
          {:else if generationError}
            <div class="error"><b>当前还没有可用的真实生成结果</b><p>{generationError}</p><a href="?legacy=1">打开 ToneLab Local 检查模型环境 →</a></div>
          {:else}
            <button class="generate" on:click={() => generateVersion(selectedVariant)}>Generate Director Pick <span>生成并试听真实音乐</span></button>
          {/if}
        </div>
      </section>

      <section class="direction">
        <div><small class="label">DIRECT THE MUSIC</small><h2>不用重新写 Prompt。<br/>直接告诉音乐导演。</h2></div>
        <div><div class="command"><input bind:value={revision} on:keydown={(e)=>e.key==='Enter'&&applyRevision()} placeholder="这里太煽情，把弦乐拿掉；中间我要说话；最后别大团圆……"/><button on:click={applyRevision}>Apply</button></div>{#if blueprint.revisionNote}<p>Last direction: {blueprint.revisionNote}</p>{/if}</div>
      </section>
    {/if}
  </main>
</div>

<style>
  :global(*){box-sizing:border-box}:global(body){margin:0;background:#f1ece2;color:#191814;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}:global(button),:global(input),:global(select),:global(textarea){font:inherit;color:inherit}.app-shell{min-height:100vh}header{height:88px;padding:0 4vw;border-bottom:1px solid #19181422;display:flex;align-items:center;justify-content:space-between}.brand small,.brand strong{display:block}.brand small,.label{font-size:9px;letter-spacing:.2em;font-weight:700;opacity:.5}.brand strong{font-family:Georgia,serif;font-weight:400;font-size:20px;margin-top:4px}nav{display:flex;gap:24px;font-size:11px;align-items:center}nav a{color:inherit;text-decoration:none;opacity:.6}.live{font-size:10px;opacity:.55}.live.offline{opacity:.3}main{width:min(1400px,92vw);margin:auto;padding:8vh 0 12vh}.input-stage{max-width:1000px;margin:auto}.serif{font-family:Georgia,serif;font-style:italic}.overline{opacity:.55}.input-stage h1{font-family:Georgia,serif;font-weight:400;font-size:clamp(44px,6.3vw,88px);line-height:.97;letter-spacing:-.045em;margin:14px 0 24px}.intro{max-width:650px;line-height:1.8;font-size:14px;opacity:.58;margin-bottom:44px}.mode-row{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.mode-row button{background:transparent;border:1px solid #19181422;text-align:left;padding:13px 14px}.mode-row b,.mode-row span{display:block}.mode-row span{font-size:10px;opacity:.5;margin-top:5px}.mode-row button.active{background:#191814;color:#f4efe5}textarea{margin-top:7px;width:100%;background:#ffffff2b;border:1px solid #19181428;padding:22px;font-family:Georgia,serif;font-size:21px;line-height:1.5;resize:vertical}.settings-row{display:grid;grid-template-columns:1.2fr .7fr 1fr 1fr;gap:6px;margin-top:6px}.settings-row label{border:1px solid #1918141c;padding:9px 11px;font-size:8px;letter-spacing:.13em;opacity:.72}.settings-row select,.settings-row input{display:block;width:100%;border:0;background:transparent;padding-top:7px;font-size:12px;letter-spacing:0}.primary,.generate{margin-top:14px;border:0;background:#191814;color:#f4efe5;padding:15px 20px;font-weight:650}.primary span,.generate span{margin-left:10px;opacity:.5;font-weight:400}.intelligence{display:grid;grid-template-columns:300px 1fr;margin-top:12vh;border-top:1px solid #19181433;border-bottom:1px solid #19181433}.intelligence aside{padding:28px 30px 28px 0;border-right:1px solid #1918141f}.intelligence h2,.section-title h2,.direction h2{font-family:Georgia,serif;font-weight:400;font-size:28px;margin:15px 0 26px}.facts div{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #19181414;font-size:11px}.facts span{opacity:.45}.emotion{margin-top:28px;display:flex;flex-direction:column;gap:6px;font-family:Georgia,serif;font-size:14px}.emotion i{font-style:normal;opacity:.25}.emotion strong{font-size:20px;font-weight:400}.blueprint{padding:28px 0 28px 30px}.blueprint-head{display:flex;justify-content:space-between;gap:30px}.blueprint h3{font-family:Georgia,serif;font-weight:400;font-size:24px;margin:12px 0}.route{text-align:right;max-width:300px}.route small,.route b,.route span{display:block}.route small{font-size:8px;letter-spacing:.15em;opacity:.4}.route b{font-family:Georgia,serif;font-size:20px;font-weight:400;margin:5px 0}.route span{font-size:10px;opacity:.45}.metrics{display:grid;grid-template-columns:.7fr .7fr 2fr;margin:25px 0}.metrics div{border-left:1px solid #19181424;padding-left:12px}.metrics small,.metrics b{display:block}.metrics small{font-size:8px;opacity:.4}.metrics b{font-family:Georgia,serif;font-weight:400;font-size:17px;margin-top:5px}.timeline{display:flex;height:115px;gap:2px;border-top:1px solid #19181425;border-bottom:1px solid #19181425;padding:9px 0}.cue{background:#1918140d;padding:9px;display:flex;flex-direction:column;justify-content:space-between;min-width:65px}.cue b{font-family:Georgia,serif;font-weight:400;font-size:12px}.cue span{font-size:8px;opacity:.4}.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:18px}.chips span{border:1px solid #1918141f;padding:6px 8px;font-size:9px}.versions-section{margin-top:10vh}.section-title h2{font-size:34px}.versions{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.versions button{min-height:104px;background:transparent;border:1px solid #19181425;padding:13px;text-align:left;display:flex;flex-direction:column;justify-content:space-between}.versions button.selected{background:#191814;color:#f4efe5}.versions small{opacity:.4}.versions b{font-family:Georgia,serif;font-size:17px;font-weight:400}.versions span{font-size:9px;opacity:.45}.versions button:disabled{cursor:wait}.player-stage{min-height:170px;border-bottom:1px solid #19181428;display:flex;align-items:center}.status{display:flex;gap:15px;align-items:center}.status b,.status small{display:block}.status small{opacity:.45;margin-top:4px}.pulse{width:11px;height:11px;border-radius:50%;background:#191814;animation:pulse 1.2s infinite}.audio-result{width:100%;padding:24px 0}.audio-result h3{font-family:Georgia,serif;font-weight:400;font-size:23px;margin:7px 0}.audio-result p{font-size:10px;opacity:.5}.audio-result audio{width:100%;margin:14px 0}.provenance{display:flex;gap:16px;font-size:9px;opacity:.45}.error b{font-family:Georgia,serif;font-weight:400;font-size:19px}.error p{font-size:11px;opacity:.55}.error a{color:inherit;font-size:10px}.direction{display:grid;grid-template-columns:330px 1fr;gap:50px;margin-top:10vh;align-items:end}.command{display:flex;border-bottom:1px solid #19181455}.command input{flex:1;border:0;background:transparent;padding:15px 0;font-family:Georgia,serif;font-size:17px}.command button{border:0;background:transparent;font-weight:650}.direction p{font-size:9px;opacity:.45}@keyframes pulse{50%{opacity:.25;transform:scale(.75)}}@media(max-width:850px){header nav{gap:10px}.mode-row,.versions{grid-template-columns:1fr 1fr}.settings-row{grid-template-columns:1fr 1fr}.intelligence,.direction{grid-template-columns:1fr}.intelligence aside{border-right:0;border-bottom:1px solid #1918141f;padding-right:0}.blueprint{padding-left:0}.blueprint-head{display:block}.route{text-align:left}.metrics{grid-template-columns:1fr}.metrics div{margin-bottom:10px}.direction{gap:10px}}
</style>
