//! Python 推理引擎 sidecar 管理
//!
//! 职责：
//! - 启动 / 停止 Python 子进程
//! - 分配空闲端口
//! - 封装 HTTP 客户端调用
//! - SSE 下载进度 → Tauri 事件转发
//!
//! 扩展新引擎不需要改这里 —— 所有引擎共享同一套 HTTP API。

use std::process::{Child, Stdio};
use std::sync::Arc;
use anyhow::{anyhow, Result};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use serde_json::json;
use tokio::sync::Mutex;
use tauri::{AppHandle, Runtime, Emitter, Manager};

const STARTUP_MARKER: &str = "ENGINE_READY";

#[derive(Clone)]
pub struct EngineHandle {
    pub client: EngineClient,
    inner: Arc<Mutex<EngineInner>>,
}

struct EngineInner {
    _child: Option<Child>,
}

#[derive(Clone)]
pub struct EngineClient {
    port: u16,
    http: Client,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct ModelInfo {
    pub id: String,
    pub name: String,
    pub tagline: String,
    #[serde(rename = "type")]
    pub model_type: String,
    pub size: String,
    pub status: String,
    pub progress: u32,
    #[serde(default)]
    pub speed: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct ModelsResponse {
    models: Vec<ModelInfo>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct GenerateResponse {
    pub success: bool,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(default)]
    pub sample_rate: Option<u32>,
    #[serde(default)]
    pub duration: Option<f64>,
    #[serde(default)]
    pub channels: Option<u32>,
    #[serde(default)]
    pub generation_time: Option<f64>,
    #[serde(default)]
    pub rtf: Option<f64>,
    #[serde(default)]
    pub device: Option<String>,
    #[serde(default)]
    pub error: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
struct SimpleResponse {
    success: bool,
    #[serde(default)]
    message: String,
}

// SSE 事件结构
#[derive(Debug, Serialize, Deserialize)]
struct SseMessage {
    event: String,
    data: serde_json::Value,
    #[serde(default)]
    timestamp: f64,
}

impl EngineHandle {
    pub fn start<R: Runtime>(app: AppHandle<R>) -> Result<Self> {
        let port = portpicker::pick_unused_port()
            .ok_or_else(|| anyhow!("找不到空闲端口"))?;

        // 运行时路径解析（分发降级链，优先级从高到低）：
        //   [A] bundle 内 pyinstaller 二进制（tonelab-engine，方案一：开箱即用）
        //   [B] config.json（~/.config/tonelab/config.json，方案二引导脚本写入）
        //   [C] 环境变量 TONELAB_PYTHON / TONELAB_SERVER_SCRIPT（开发调试）
        //   [D] 探测本机常见 venv（开发环境）
        //   [E] 全部缺失 → 报错引导运行 setup-backends.sh
        let resource_dir = app.path().resource_dir().ok();
        let resource = |name: &str| {
            resource_dir
                .as_ref()
                .map(|d| d.join(name))
                .filter(|p| p.exists())
                .map(|p| p.to_string_lossy().to_string())
        };

        // [A] pyinstaller 打包的独立引擎二进制（若存在，方案一开箱即用）
        let bundled_engine = resource("resources/engines/musicgen/tonelab-engine");
        if let Some(ref bin) = bundled_engine {
            // 直接跑二进制，不需要 Python（args 为 [port]，pyinstaller 二进制读 argv[1] 作端口）
            eprintln!("[engine] 使用 bundle 内独立引擎: {bin}");
            let mut cmd = std::process::Command::new(bin);
            cmd.arg(port.to_string());
            cmd.env_clear();
            cmd.env("HOME", std::env::var("HOME").unwrap_or_default());
            cmd.env("PATH", "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin");
            cmd.env("TMPDIR", std::env::var("TMPDIR").unwrap_or_default());
            cmd.env("HF_ENDPOINT", std::env::var("HF_ENDPOINT").unwrap_or_else(|_| "https://huggingface.co".into()));
            cmd.env("TQDM_DISABLE", "1");
            return Self::finish_start(cmd, port, &app);
        }

        // [B] config.json（引导脚本写入）
        let mut config_python: Option<String> = None;
        let mut config_script: Option<String> = None;
        if let Ok(home) = std::env::var("HOME") {
            let cfg_path = std::path::Path::new(&home).join(".config/tonelab/config.json");
            if let Ok(content) = std::fs::read_to_string(&cfg_path) {
                if let Ok(cfg) = serde_json::from_str::<serde_json::Value>(&content) {
                    config_python = cfg.get("python_path").and_then(|v| v.as_str()).map(String::from);
                    config_script = cfg.get("server_script").and_then(|v| v.as_str()).map(String::from);
                }
            }
        }

        // 引擎脚本：config → env → bundle resources → 开发目录
        let server_script = config_script
            .or_else(|| std::env::var("TONELAB_SERVER_SCRIPT").ok())
            .or_else(|| resource("resources/engines/musicgen/server.py"))
            .unwrap_or_else(|| "/Users/kimliu/Projects/music-studio/engines/musicgen/server.py".to_string());

        // Python：config → env → 探测常见 venv（含引导脚本安装的 ~/.tonelab-env）
        let python = config_python
            .or_else(|| std::env::var("TONELAB_PYTHON").ok())
            .or_else(|| {
                let home = std::env::var("HOME").unwrap_or_default();
                let candidates = [
                    format!("{home}/.tonelab-env/bin/python3"),
                    "/Users/kimliu/musicgen-env/bin/python3".to_string(),
                    "/usr/local/bin/python3".to_string(),
                    "/opt/homebrew/bin/python3".to_string(),
                ];
                candidates.iter().find(|p| std::path::Path::new(p).exists()).map(|s| s.clone())
            });

        let python = match python {
            Some(p) if std::path::Path::new(&p).exists() => p,
            _ => {
                // [E] 全部缺失：引导安装
                let setup_script = resource("resources/setup-backends.sh");
                eprintln!("[engine] 未找到 Python 推理环境");
                eprintln!("[engine] 引导脚本: {}", setup_script.as_deref().unwrap_or("(未打包)"));
                return Err(anyhow!(
                    "缺少运行环境：未找到 Python 推理环境。\n\
                     请运行引导脚本安装：\n  \
                     {}\n  \
                     或手动配置 ~/.config/tonelab/config.json 的 python_path",
                    setup_script.as_deref().unwrap_or("bash <bundle>/setup-backends.sh")
                ));
            }
        };
        if !std::path::Path::new(&server_script).exists() {
            return Err(anyhow!("引擎脚本不存在: {server_script}"));
        }

        let mut args = vec![server_script.clone(), port.to_string()];
        let mut cmd = std::process::Command::new(&python);
        cmd.args(&args);
        cmd.env_clear();
        cmd.env("HOME", std::env::var("HOME").unwrap_or_default());
        cmd.env("PATH", "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin");
        cmd.env("TMPDIR", std::env::var("TMPDIR").unwrap_or_default());
        cmd.env("HF_ENDPOINT", std::env::var("HF_ENDPOINT").unwrap_or_else(|_| "https://huggingface.co".into()));
        cmd.env("TQDM_DISABLE", "1");
        Self::finish_start(cmd, port, &app)
    }

    /// 启动子进程并完成初始化（等待就绪 + SSE 转发）
    /// 同时被 [A] bundle 二进制 和 [B-E] Python 路径调用
    fn finish_start<R: Runtime>(
        mut cmd: std::process::Command,
        port: u16,
        app: &AppHandle<R>,
    ) -> Result<Self> {
        // 代理透传
        // 1) 优先继承环境变量
        let mut proxy_url: Option<String> = None;
        for var in &["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"] {
            if let Ok(v) = std::env::var(var) {
                proxy_url = Some(v);
                break;
            }
        }
        // 2) 环境变量没设置时，探测本地 Clash/V2Ray 常用端口（只选真实可用的）
        if proxy_url.is_none() {
            for port in &[7897, 7890, 1080, 1082] {
                if !std::net::TcpStream::connect(("127.0.0.1", *port)).is_ok() {
                    continue;
                }
                // 端口在监听不代表能出网（Clash 可能没开节点），做真实请求验证
                let proxy_ok = std::net::TcpStream::connect_timeout(
                    &format!("127.0.0.1:{}", port).parse().unwrap_or_else(|_| "127.0.0.1:1".parse().unwrap()),
                    std::time::Duration::from_millis(800),
                ).is_ok();
                if proxy_ok {
                    // 通过代理发一个 HTTP CONNECT 验证能到 huggingface.co
                    let mut stream = match std::net::TcpStream::connect_timeout(
                        &format!("127.0.0.1:{}", port).parse().unwrap_or_else(|_| "127.0.0.1:1".parse().unwrap()),
                        std::time::Duration::from_millis(800),
                    ) {
                        Ok(s) => s,
                        Err(_) => continue,
                    };
                    use std::io::Write;
                    let _ = stream.set_read_timeout(Some(std::time::Duration::from_millis(1500)));
                    let _ = stream.write_all(b"CONNECT huggingface.co:443 HTTP/1.1
Host: huggingface.co:443

");
                    let mut buf = [0u8; 64];
                    let mut resp_ok = false;
                    if let Ok(n) = std::io::Read::read(&mut stream, &mut buf) {
                        if n >= 12 && &buf[..12] == b"HTTP/1.1 200" {
                            resp_ok = true;
                        }
                    }
                    if resp_ok {
                        proxy_url = Some(format!("http://127.0.0.1:{}", port));
                        println!("[tonelab-engine] 代理 {} 验证可用（CONNECT huggingface.co 200），自动启用", port);
                        break;
                    } else {
                        println!("[tonelab-engine] 端口 {} 在监听但代理不可用（CONNECT 未通过），跳过", port);
                    }
                }
            }
        }
        if let Some(ref url) = proxy_url {
            cmd.env("HTTP_PROXY", url);
            cmd.env("HTTPS_PROXY", url);
            cmd.env("ALL_PROXY", url);
            cmd.env("http_proxy", url);
            cmd.env("https_proxy", url);
            cmd.env("all_proxy", url);
            // huggingface_hub 也读这个
            cmd.env("HF_HUB_ENABLE_HF_TRANSFER", "0");
        }
        cmd.stdout(Stdio::piped());
        cmd.stderr(Stdio::piped());

        let mut child = cmd.spawn()?;

        // 异步读 stdout
        let stdout = child.stdout.take().ok_or_else(|| anyhow!("无法获取子进程 stdout"))?;
        let app_clone = app.clone();
        std::thread::spawn(move || {
            use std::io::{BufRead, BufReader, Write};
            let reader = BufReader::new(stdout);
            let log_path = std::env::var("TONELAB_LOG_FILE").unwrap_or_default();
            let mut log_file = if !log_path.is_empty() {
                std::fs::OpenOptions::new().create(true).append(true).open(&log_path).ok()
            } else { None };
            for line in reader.lines() {
                if let Ok(line) = line {
                    println!("[tonelab-engine] {}", line);
                    let _ = app_clone.emit("engine-log", line.as_str());
                    if let Some(f) = log_file.as_mut() {
                        let _ = writeln!(f, "[sidecar] {}", line);
                    }
                }
            }
        });

        // 异步读 stderr
        let stderr = child.stderr.take().ok_or_else(|| anyhow!("无法获取子进程 stderr"))?;
        std::thread::spawn(move || {
            use std::io::{BufRead, BufReader};
            let reader = BufReader::new(stderr);
            for line in reader.lines() {
                if let Ok(line) = line {
                    eprintln!("[tonelab-engine:err] {}", line);
                }
            }
        });

        // 等待端口可连（最多 30 秒，Python 加载 torch 需要时间）
        let mut ready = false;
        for _ in 0..300 {
            std::thread::sleep(std::time::Duration::from_millis(100));
            if std::net::TcpStream::connect(("127.0.0.1", port)).is_ok() {
                ready = true;
                break;
            }
        }
        if !ready {
            return Err(anyhow!("sidecar 启动超时（端口 {} 30 秒内未就绪）", port));
        }
        // 再等一下让 HTTP server 完全初始化
        std::thread::sleep(std::time::Duration::from_millis(300));

        let http = Client::builder()
            .timeout(std::time::Duration::from_secs(600))
            // 关键：禁用环境变量代理。macOS 上 Clash Verge 开系统代理会注入
            // HTTP_PROXY/HTTPS_PROXY 环境变量，reqwest 默认读取后会把所有请求
            // （包括到本地 sidecar 的）走代理，导致 SSE 连不上 sidecar。
            .no_proxy()
            .build()?;

        let client = EngineClient { port, http };

        // 启动 SSE 转发线程（用 tauri 的 async runtime，后台运行不追踪）
        let client_clone = client.clone();
        let app_clone = app.clone();
        tauri::async_runtime::spawn(async move {
            client_clone.forward_sse_events(app_clone).await;
        });

        let handle = Self {
            client,
            inner: Arc::new(Mutex::new(EngineInner {
                _child: Some(child),
            })),
        };

        Ok(handle)
    }
}

impl EngineClient {
    fn base_url(&self) -> String {
        format!("http://127.0.0.1:{}", self.port)
    }

    pub async fn ping(&self) -> bool {
        let url = format!("{}/health", self.base_url());
        match self.http.get(&url).send().await {
            Ok(resp) => resp.status().is_success(),
            Err(_) => false,
        }
    }

    pub async fn list_models(&self) -> Result<Vec<ModelInfo>> {
        let url = format!("{}/models", self.base_url());
        let resp = self.http.get(&url).send().await
            .map_err(|e| anyhow!("请求失败: {e}"))?;
        let data: ModelsResponse = resp.json().await
            .map_err(|e| anyhow!("解析失败: {e}"))?;
        Ok(data.models)
    }

    pub async fn get_logs(&self, n: Option<usize>) -> Result<Vec<String>> {
        let n = n.unwrap_or(200).min(500);
        let url = format!("{}/logs?n={}", self.base_url(), n);
        let resp = self.http.get(&url).send().await
            .map_err(|e| anyhow!("请求失败: {e}"))?;
        let data: serde_json::Value = resp.json().await
            .map_err(|e| anyhow!("解析失败: {e}"))?;
        Ok(data.get("logs").and_then(|l| l.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_str().map(String::from)).collect())
            .unwrap_or_default())
    }

    pub async fn download_model(&self, model_id: &str) -> Result<bool> {
        let url = format!("{}/download", self.base_url());
        let body = serde_json::json!({ "model_id": model_id });
        let resp = self.http.post(&url).json(&body).send().await
            .map_err(|e| anyhow!("请求失败: {e}"))?;
        let data: SimpleResponse = resp.json().await
            .map_err(|e| anyhow!("解析失败: {e}"))?;
        if !data.success {
            return Err(anyhow!("{}", data.message));
        }
        Ok(true)
    }

    pub async fn cancel_download(&self, model_id: &str) -> Result<bool> {
        let url = format!("{}/download/cancel", self.base_url());
        let body = serde_json::json!({ "model_id": model_id });
        let resp = self.http.post(&url).json(&body).send().await
            .map_err(|e| anyhow!("请求失败: {e}"))?;
        let data: SimpleResponse = resp.json().await
            .map_err(|e| anyhow!("解析失败: {e}"))?;
        Ok(data.success)
    }

    pub async fn remove_model(&self, model_id: &str) -> Result<bool> {
        let url = format!("{}/models/remove", self.base_url());
        let body = serde_json::json!({ "model_id": model_id });
        let resp = self.http.post(&url).json(&body).send().await
            .map_err(|e| anyhow!("请求失败: {e}"))?;
        let data: SimpleResponse = resp.json().await
            .map_err(|e| anyhow!("解析失败: {e}"))?;
        if !data.success {
            return Err(anyhow!("{}", data.message));
        }
        Ok(true)
    }

    pub async fn generate(
        &self,
        engine: &str,
        prompt: &str,
        duration: u32,
        filename: Option<&str>,
        guidance_scale: Option<f64>,
        temperature: Option<f64>,
        top_k: Option<u32>,
        top_p: Option<f64>,
    ) -> Result<GenerateResponse> {
        let url = format!("{}/generate", self.base_url());
        let mut body = serde_json::json!({
            "engine": engine,
            "prompt": prompt,
            "duration": duration,
            "filename": filename,
        });
        if let Some(v) = guidance_scale { body["guidance_scale"] = json!(v); }
        if let Some(v) = temperature { body["temperature"] = json!(v); }
        if let Some(v) = top_k { body["top_k"] = json!(v); }
        if let Some(v) = top_p { body["top_p"] = json!(v); }

        let resp = self.http.post(&url).json(&body).send().await
            .map_err(|e| anyhow!("请求引擎失败: {e}"))?;

        let status = resp.status();
        if !status.is_success() {
            let err_text = resp.text().await.unwrap_or_default();
            return Err(anyhow!("引擎返回错误 ({}): {}", status, err_text));
        }

        let result: GenerateResponse = resp.json().await?;
        Ok(result)
    }

    /// SSE 进度事件 → Tauri event 转发
    async fn forward_sse_events<R: Runtime>(&self, app: AppHandle<R>) {
        let url = format!("{}/download/progress", self.base_url());
        loop {
            match self.http.get(&url).send().await {
                Ok(resp) => {
                    use futures_util::StreamExt;
                    let mut stream = resp.bytes_stream();
                    let mut buffer = String::new();

                    while let Some(chunk) = stream.next().await {
                        let chunk = match chunk {
                            Ok(c) => c,
                            Err(_) => break,
                        };
                        buffer.push_str(&String::from_utf8_lossy(&chunk));

                        // 按 "data: ...\n\n" 切分
                        while let Some(idx) = buffer.find("\n\n") {
                            let event_str = buffer.drain(..idx + 2).collect::<String>();
                            let data_line = event_str
                                .lines()
                                .find(|l| l.starts_with("data: "))
                                .map(|l| &l[6..]);

                            if let Some(data) = data_line {
                                if let Ok(msg) = serde_json::from_str::<SseMessage>(data) {
                                    // 转发给前端
                                    let _ = app.emit(&format!("model:{}", msg.event), &msg.data);
                                }
                            }
                        }
                    }
                }
                Err(_) => {
                    // 连接失败，等会儿重试
                    tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                    continue;
                }
            }
            // 连接断了，重连
            tokio::time::sleep(std::time::Duration::from_secs(1)).await;
        }
    }
}
