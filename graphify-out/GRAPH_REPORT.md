# Graph Report - .  (2026-08-10)

## Corpus Check
- Corpus is ~49,556 words - fits in a single context window. You may not need a graph.

## Summary
- 397 nodes · 550 edges · 29 communities (18 shown, 11 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS · INFERRED: 2 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Python 引擎 server.py
- bundle 内 server.py
- Tauri 桌面 schema
- Tauri macOS schema
- macOS 能力配置
- Rust 内部符号
- Tauri 桌面 schema 2
- 应用资源与图标
- Rust 引擎桥接
- 前端依赖
- Tauri 能力声明
- Svelte 入口
- 交付验证脚本
- 使用说明 PDF 脚本
- pyinstaller 构建脚本
- 发布构建脚本
- 旧版清理脚本
- DMG 制作脚本
- 发布推送脚本
- 回滚脚本
- 资源同步脚本
- 环境安装脚本

## God Nodes (most connected - your core abstractions)
1. `EngineHandle` - 14 edges
2. `EngineClient` - 12 edges
3. `MusicgenEngine` - 9 edges
4. `Handler` - 9 edges
5. `MusicgenEngine` - 9 edges
6. `Handler` - 9 edges
7. `_log()` - 8 edges
8. `definitions` - 8 edges
9. `definitions` - 8 edges
10. `_log()` - 8 edges

## Surprising Connections (you probably didn't know these)
- `list_models()` --references--> `ModelInfo`  [EXTRACTED]
  src-tauri/src/lib.rs → src-tauri/src/engine.rs
- `GenerateResult` --references--> `GenerateResponse`  [EXTRACTED]
  src-tauri/src/lib.rs → src-tauri/src/engine.rs
- `cancel_download()` --references--> `EngineHandle`  [EXTRACTED]
  src-tauri/src/lib.rs → src-tauri/src/engine.rs
- `download_model()` --references--> `EngineHandle`  [EXTRACTED]
  src-tauri/src/lib.rs → src-tauri/src/engine.rs
- `generate_music()` --references--> `EngineHandle`  [EXTRACTED]
  src-tauri/src/lib.rs → src-tauri/src/engine.rs

## Import Cycles
- None detected.

## Communities (29 total, 11 thin omitted)

### Community 0 - "Python 引擎 server.py"
Cohesion: 0.08
Nodes (27): AceStepEngine, _bpm_to_tempo(), _broadcast_event(), cancel_download(), _detect_model_status(), _download_worker(), get_engine(), get_models_info() (+19 more)

### Community 1 - "bundle 内 server.py"
Cohesion: 0.08
Nodes (27): AceStepEngine, _bpm_to_tempo(), _broadcast_event(), cancel_download(), _detect_model_status(), _download_worker(), get_engine(), get_models_info() (+19 more)

### Community 2 - "Tauri 桌面 schema"
Cohesion: 0.06
Nodes (38): properties, Identifier, default, description, type, description, oneOf, type (+30 more)

### Community 3 - "Tauri macOS schema"
Cohesion: 0.06
Nodes (37): properties, default, description, type, description, type, $ref, type (+29 more)

### Community 4 - "macOS 能力配置"
Cohesion: 0.06
Nodes (34): anyOf, description, required, type, description, properties, required, type (+26 more)

### Community 5 - "Rust 内部符号"
Cohesion: 0.11
Nodes (21): Arc, Child, Client, Command, Mutex, R, EngineClient, EngineInner (+13 more)

### Community 6 - "Tauri 桌面 schema 2"
Cohesion: 0.06
Nodes (33): anyOf, description, required, type, description, properties, required, type (+25 more)

### Community 7 - "应用资源与图标"
Cohesion: 0.07
Nodes (27): app, icons/128x128@2x.png, icons/128x128.png, icons/32x32.png, icons/icon.icns, resources/engines/musicgen/server.py, resources/engines/musicgen/tonelab-engine, resources/setup-backends.sh (+19 more)

### Community 8 - "Rust 引擎桥接"
Cohesion: 0.21
Nodes (25): From, EngineHandle, cancel_download(), chrono_now(), download_model(), env_setup_path(), env_setup_run(), env_status() (+17 more)

### Community 9 - "前端依赖"
Cohesion: 0.08
Nodes (23): dependencies, lucide-svelte, @tauri-apps/api, devDependencies, svelte, @sveltejs/vite-plugin-svelte, @tauri-apps/cli, vite (+15 more)

### Community 10 - "Tauri 能力声明"
Cohesion: 0.22
Nodes (8): core:default, core:event:default, main, description, identifier, permissions, $schema, windows

## Knowledge Gaps
- **132 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+127 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `properties` connect `Tauri 桌面 schema` to `Tauri 桌面 schema 2`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `properties` connect `Tauri macOS schema` to `macOS 能力配置`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `definitions` connect `Tauri 桌面 schema 2` to `Tauri 桌面 schema`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _132 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Python 引擎 server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0797872340425532 - nodes in this community are weakly interconnected._
- **Should `bundle 内 server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.0797872340425532 - nodes in this community are weakly interconnected._
- **Should `Tauri 桌面 schema` be split into smaller, more focused modules?**
  _Cohesion score 0.05547652916073969 - nodes in this community are weakly interconnected._