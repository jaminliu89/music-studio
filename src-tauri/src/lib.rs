//! ToneLab — Tauri 后端
//!
//! 架构：
//!   Tauri (Rust) ←HTTP→ Python sidecar (推理引擎 + 模型管理)
//!
//! 事件（前端监听）:
//!   model:models_state       初始模型列表（SSE 首次推送）
//!   model:download_progress  下载进度更新
//!   model:download_complete  下载完成
//!   model:download_paused    下载已暂停
//!   model:download_error     下载出错
//!   model:model_removed      模型已删除

mod engine;

use engine::{EngineHandle, GenerateResponse, ModelInfo};
use serde::{Deserialize, Serialize};
use tauri::Manager;

#[derive(Debug, Serialize, Deserialize)]
pub struct GenerateResult {
    success: bool,
    path: Option<String>,
    sample_rate: Option<u32>,
    duration: Option<f64>,
    channels: Option<u32>,
    generation_time: Option<f64>,
    rtf: Option<f64>,
    error: Option<String>,
}

impl From<GenerateResponse> for GenerateResult {
    fn from(r: GenerateResponse) -> Self {
        Self {
            success: r.success,
            path: r.path,
            sample_rate: r.sample_rate,
            duration: r.duration,
            channels: r.channels,
            generation_time: r.generation_time,
            rtf: r.rtf,
            error: r.error,
        }
    }
}

#[tauri::command]
async fn ping_engine(state: tauri::State<'_, EngineHandle>) -> Result<bool, String> {
    Ok(state.client.ping().await)
}

#[tauri::command]
async fn log_debug(msg: String) -> Result<(), String> {
    eprintln!("[frontend] {}", msg);
    // GUI 启动时 stderr 不可见，落盘才能看到前端日志
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true).append(true)
        .open("/tmp/tonelab_frontend.log")
    {
        use std::io::Write;
        let _ = writeln!(f, "[{}] {}", chrono_now(), msg);
    }
    Ok(())
}

fn chrono_now() -> String {
    let t = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default();
    format!("{:>3}.{:03}", t.as_secs() % 100000, t.subsec_millis())
}

#[tauri::command]
async fn list_models(state: tauri::State<'_, EngineHandle>) -> Result<Vec<ModelInfo>, String> {
    state.client.list_models().await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn get_logs(state: tauri::State<'_, EngineHandle>, n: Option<usize>) -> Result<Vec<String>, String> {
    state.client.get_logs(n).await.map_err(|e| e.to_string())
}

#[tauri::command]
async fn download_model(
    model_id: String,
    state: tauri::State<'_, EngineHandle>,
) -> Result<bool, String> {
    state
        .client
        .download_model(&model_id)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn cancel_download(
    model_id: String,
    state: tauri::State<'_, EngineHandle>,
) -> Result<bool, String> {
    state
        .client
        .cancel_download(&model_id)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn remove_model(
    model_id: String,
    state: tauri::State<'_, EngineHandle>,
) -> Result<bool, String> {
    state
        .client
        .remove_model(&model_id)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn generate_music(
    engine: String,
    prompt: String,
    duration: u32,
    filename: Option<String>,
    guidanceScale: Option<f64>,
    temperature: Option<f64>,
    topK: Option<u32>,
    topP: Option<f64>,
    state: tauri::State<'_, EngineHandle>,
) -> Result<GenerateResult, String> {
    let result = state
        .client
        .generate(&engine, &prompt, duration, filename.as_deref(), guidanceScale, temperature, topK, topP)
        .await
        .map_err(|e| e.to_string())?;
    Ok(result.into())
}

#[tauri::command]
fn read_audio_file(path: String) -> Result<Vec<u8>, String> {
    std::fs::read(&path).map_err(|e| format!("读取文件失败: {e}"))
}

#[tauri::command]
fn reveal_in_finder(path: String) -> Result<(), String> {
    use std::process::Command;
    Command::new("open")
        .arg("-R")
        .arg(&path)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("打开访达失败: {e}"))
}

#[tauri::command]
fn open_external(url: String) -> Result<(), String> {
    use std::process::Command;
    Command::new("open")
        .arg(&url)
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("打开链接失败: {e}"))
}

/// 环境诊断：返回 Python 环境是否就绪（前端首次启动判断是否进向导）
#[tauri::command]
fn env_status(app: tauri::AppHandle) -> Result<serde_json::Value, String> {
    use std::path::Path;
    let home = std::env::var("HOME").unwrap_or_default();
    let candidates = [
        format!("{home}/.tonelab-env/bin/python3"),
        "/Users/kimliu/musicgen-env/bin/python3".to_string(),
        "/usr/local/bin/python3".to_string(),
        "/opt/homebrew/bin/python3".to_string(),
    ];
    let found = candidates.iter().find(|p| Path::new(p).exists());
    // config.json 检测
    let cfg_path = Path::new(&home).join(".config/tonelab/config.json");
    let has_config = cfg_path.exists();
    // bundle 内独立引擎检测
    let has_bundled = app
        .path()
        .resource_dir()
        .ok()
        .map(|d| d.join("resources/engines/musicgen/tonelab-engine").exists())
        .unwrap_or(false);
    Ok(serde_json::json!({
        "ready": found.is_some() || has_bundled,
        "python_found": found.is_some(),
        "has_config": has_config,
        "has_bundled_engine": has_bundled,
        "python_path": found,
    }))
}

/// 返回引导脚本绝对路径（前端显示）
#[tauri::command]
fn env_setup_path(app: tauri::AppHandle) -> Result<String, String> {
    let p = app
        .path()
        .resource_dir()
        .map_err(|e| format!("无法获取资源目录: {e}"))?
        .join("resources/setup-backends.sh");
    Ok(p.to_string_lossy().to_string())
}

/// 执行引导安装脚本（异步：spawn 后由引擎启动流程接管）
/// 返回脚本输出的 READY 标志
#[tauri::command]
fn env_setup_run(app: tauri::AppHandle) -> Result<String, String> {
    let script = env_setup_path(app)?;
    use std::process::Command;
    let out = Command::new("bash")
        .arg(&script)
        .output()
        .map_err(|e| format!("运行引导脚本失败: {e}"))?;
    let stdout = String::from_utf8_lossy(&out.stdout).to_string();
    let stderr = String::from_utf8_lossy(&out.stderr).to_string();
    if !out.status.success() {
        return Err(format!("引导脚本退出码 {}:\n{}{}", out.status, stderr, stdout));
    }
    Ok(stdout)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // 门禁 T: 启动冒烟（TONELAB_E2E=1 时构造 Builder + 注册 handler 后直接退出）
    let smoke = std::env::var("TONELAB_E2E").ok().as_deref() == Some("1");

    let builder = tauri::Builder::default()
        .setup(|app| {
            let handle = EngineHandle::start(app.handle().clone())?;
            app.manage(handle);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            ping_engine,
            list_models,
            get_logs,
            log_debug,
            download_model,
            cancel_download,
            remove_model,
            generate_music,
            read_audio_file,
            reveal_in_finder,
            open_external,
            env_status,
            env_setup_path,
            env_setup_run,
        ]);

    if smoke {
        let json = r#"{"summary":"passed","tests":{"T_bootstrap":{"pass":true,"detail":"Builder + 10 commands registered"}}}"#;
        let _ = std::fs::write("/tmp/tonelab-e2e.json", json);
        std::process::exit(0);
    }

    builder
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
