#!/usr/bin/env python3
"""
ToneLab · Python 推理引擎 sidecar
HTTP API，供 Rust 端调用

路由:
  GET    /health                → 健康检查
  GET    /ping                  → pong
  GET    /models                → 列出所有模型及状态
  POST   /models/scan           → 重新扫描本地模型目录
  POST   /download              → 下载模型 {model_id}
  POST   /download/cancel       → 取消下载 {model_id}
  POST   /models/remove         → 删除本地模型 {model_id}
  GET    /download/progress     → SSE 流式推送下载进度
  POST   /generate              → 生成音乐 {engine, prompt, duration, output_path}
  POST   /cancel                → 取消当前生成

模型注册表：每个模型有 HuggingFace repo id 和本地目录名。
"""
import os
import sys

# ── HuggingFace 源站设置 ──
# 默认官方源 huggingface.co（走本地代理）；国内镜像 hf-mirror.com 可覆盖
# 设 HF_ENDPOINT 环境变量可覆盖
os.environ.setdefault("HF_ENDPOINT", "https://huggingface.co")

import json
import time
import threading
import urllib.request
import urllib.error

# 本地服务请求永远不走代理：ToneLab app 由 Rust env_clear + 设置
# HTTP_PROXY/HTTPS_PROXY=127.0.0.1:7897 启动引擎，且不带 NO_PROXY——
# urllib 连 127.0.0.1:8001（ACE-Step health/release_task）会走代理，
# 代理连本地地址失败 → health 检测失败 → 专业成曲版显示 not_installed。
# 强制 NO_PROXY 本地地址，仅影响 127.0.0.1/localhost，不影响 HF 下载走代理。
os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
os.environ["no_proxy"] = "127.0.0.1,localhost,::1"
import numpy as np
import scipy
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Queue

# ── 配置 ──
MODEL_DIR = os.environ.get("MUSICGEN_MODEL_DIR", "/Users/kimliu/models")
OUTPUT_DIR = os.environ.get("MUSICGEN_OUTPUT_DIR", "/Users/kimliu/Music")
PORT = int(os.environ.get("MUSICGEN_PORT", "8765"))

os.environ["HF_HUB_OFFLINE"] = "0"  # 下载需要联网，生成时按需切换
os.environ["TQDM_DISABLE"] = "1"   # 禁掉 tqdm，避免 stderr pipe 问题
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

# ── 模型注册表 ──
# 所有可下载的模型，统一管理
MODEL_REGISTRY = {
    "musicgen-small": {
        "name": "轻快标准版",
        "tagline": "300M · 文本生成纯音乐",
        "type": "text-to-music",
        "hf_repo": "facebook/musicgen-small",
        "estimated_size": "1.8 GB",
        "filename": "musicgen-small",
    },
    "musicgen-medium": {
        "name": "高清均衡版",
        "tagline": "1.5B · 中等规模，音质提升",
        "type": "text-to-music",
        "hf_repo": "facebook/musicgen-medium",
        "estimated_size": "5.6 GB",
        "filename": "musicgen-medium",
    },
    "musicgen-stereo-melody": {
        "name": "立体声旋律版",
        "tagline": "1.5B · 立体声 + 旋律条件",
        "type": "melody-to-music",
        "hf_repo": "facebook/musicgen-stereo-melody",
        "estimated_size": "5.9 GB",
        "filename": "musicgen-stereo-melody",
    },
    "musicgen-large": {
        "name": "旗舰无损版",
        "tagline": "3.3B · 最高音质",
        "type": "text-to-music",
        "hf_repo": "facebook/musicgen-large",
        "estimated_size": "6.5 GB",
        "filename": "musicgen-large",
    },
    "musicgen-melody": {
        "name": "旋律作曲版",
        "tagline": "1.5B · 旋律条件生成",
        "type": "melody-to-music",
        "hf_repo": "facebook/musicgen-melody",
        "estimated_size": "5.2 GB",
        "filename": "musicgen-melody",
    },
    "audiogen-medium": {
        "name": "音效生成版",
        "tagline": "1.5B · 文本生成音效",
        "type": "text-to-sound",
        "hf_repo": "facebook/audiogen-medium",
        "estimated_size": "4.8 GB",
        "filename": "audiogen-medium",
    },
    "musicgen-stereo-small": {
        "name": "轻快立体声版",
        "tagline": "300M · 立体声纯音乐",
        "type": "text-to-music",
        "hf_repo": "facebook/musicgen-stereo-small",
        "estimated_size": "2.0 GB",
        "filename": "musicgen-stereo-small",
    },
    "musicgen-stereo-large": {
        "name": "旗舰立体声版",
        "tagline": "3.3B · 立体声最高音质",
        "type": "text-to-music",
        "hf_repo": "facebook/musicgen-stereo-large",
        "estimated_size": "13.0 GB",
        "filename": "musicgen-stereo-large",
    },
    "acestep-v15-turbo": {
        "name": "专业成曲版",
        "tagline": "完整曲式结构 + 48kHz 立体声",
        "type": "text-to-music",
        "hf_repo": "ACE-Step/Ace-Step1.5",
        "estimated_size": "6.0 GB",
        "filename": "acestep-v15-turbo",
        "is_remote_service": True,  # 外部服务，不占本地模型目录
    },
}

# ── 全局状态 ──
_downloads = {}            # model_id -> {status, progress, speed, started_at}
_downloads_lock = threading.Lock()
_sse_clients = []          # SSE 推送队列列表
_sse_lock = threading.Lock()

# ── 日志监控缓冲（供 GET /logs 查询）──
from collections import deque
LOG_BUFFER = deque(maxlen=500)
_LOG_LOCK = threading.Lock()


def _log(line):
    """写日志：缓冲 + stdout + 落盘"""
    ts = time.strftime("%H:%M:%S")
    entry = f"[{ts}] {line}"
    with _LOG_LOCK:
        LOG_BUFFER.append(entry)
    print(entry, flush=True)
    try:
        with open("/tmp/tonelab_sidecar.log", "a") as f:
            f.write(entry + "\n")
    except OSError:
        pass


def _log_req(line):
    """访问日志（短格式，不带时间戳重复）"""
    try:
        with open("/tmp/tonelab_sidecar_access.log", "a") as f:
            f.write(line + "\n")
    except OSError:
        pass
_generation_lock = threading.Lock()
_cancel_flag = threading.Event()


# ═══════════════════════════════════════════
# 模型状态检测
# ═══════════════════════════════════════════
def _model_local_path(model_id):
    info = MODEL_REGISTRY.get(model_id)
    if not info:
        return None
    return os.path.join(MODEL_DIR, info["filename"])


def _detect_model_status(model_id):
    """检测本地模型的安装状态：ready / partial / not_installed"""
    # 远程服务引擎（ACE-Step）：状态 = 服务健康，不查本地目录
    info = MODEL_REGISTRY.get(model_id, {})
    if info.get("is_remote_service"):
        try:
            req = urllib.request.Request(
                f"{os.environ.get('ACESTEP_API_URL', 'http://127.0.0.1:8001')}/health",
                method="GET", headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                body = json.loads(r.read().decode())
                if body.get("data", {}).get("status") == "ok":
                    return "ready", 100
            return "not_installed", 0  # 服务在但模型没加载
        except Exception:
            return "not_installed", 0  # 服务没起
    path = _model_local_path(model_id)
    if not path or not os.path.isdir(path):
        return "not_installed", 0

    # 检查关键文件是否存在且完整
    safetensors_files = []
    total_expected = 0
    total_actual = 0

    index_file = os.path.join(path, "model.safetensors.index.json")
    single_file = os.path.join(path, "model.safetensors")
    pytorch_file = os.path.join(path, "pytorch_model.bin")

    # 有 model.safetensors 单文件且 > 10MB → 就绪（注意：有 .aria2 控制文件说明没下完）
    if os.path.exists(single_file) and os.path.getsize(single_file) > 10 * 1024 * 1024:
        if not os.path.exists(single_file + ".aria2"):
            return "ready", 100
        # 没下完，按已下载比例算进度
        aria = single_file + ".aria2"
        try:
            with open(aria, "rb") as f:
                f.seek(-8, 2)
                total = int.from_bytes(f.read(8), "big")
            cur = os.path.getsize(single_file)
            p = min(99, int(cur / total * 100)) if total > 0 else 5
            return "partial", max(1, p)
        except Exception:
            return "partial", 5
    if os.path.exists(pytorch_file) and os.path.getsize(pytorch_file) > 10 * 1024 * 1024:
        if not os.path.exists(pytorch_file + ".aria2"):
            return "ready", 100
        # 没下完，按已下载比例算进度
        aria = pytorch_file + ".aria2"
        try:
            with open(aria, "rb") as f:
                f.seek(-8, 2)
                total = int.from_bytes(f.read(8), "big")
            cur = os.path.getsize(pytorch_file)
            p = min(99, int(cur / total * 100)) if total > 0 else 5
            return "partial", max(1, p)
        except Exception:
            return "partial", 5

    # 分片模型：检查 index 文件和各分片
    if os.path.exists(index_file):
        try:
            with open(index_file) as f:
                data = json.load(f)
            weight_map = data.get("weight_map", {})
            shards = set(weight_map.values())
            total_shards = len(shards)
            ready_shards = 0
            total_size_expected = 0
            total_size_actual = 0

            for shard in shards:
                shard_path = os.path.join(path, shard)
                if os.path.exists(shard_path):
                    # 检查 .aria2 控制文件是否存在（aria2 没下完会留这个）
                    aria_file = shard_path + ".aria2"
                    if not os.path.exists(aria_file):
                        ready_shards += 1
                    total_size_actual += os.path.getsize(shard_path)

            if total_shards == 0:
                return "ready", 100

            progress = int((ready_shards / total_shards) * 100)
            if ready_shards == total_shards:
                return "ready", 100
            elif ready_shards > 0:
                return "partial", progress
            else:
                return "partial", 0
        except Exception:
            pass

    # 目录存在但找不到模型文件 → 部分
    files = os.listdir(path)
    if len(files) > 3:  # 至少有 config.json 等配置
        return "partial", 10
    return "partial", 5


def get_models_info():
    """获取所有模型的状态信息"""
    result = []
    for mid, info in MODEL_REGISTRY.items():
        status, progress = _detect_model_status(mid)

        with _downloads_lock:
            dl = _downloads.get(mid)
            if dl:
                if dl["status"] in ("downloading", "paused"):
                    status = dl["status"]
                    progress = dl["progress"]

        result.append({
            "id": mid,
            "name": info["name"],
            "tagline": info["tagline"],
            "type": info["type"],
            "size": info["estimated_size"],
            "status": status,
            "progress": progress,
            "speed": dl.get("speed", "") if dl else "",
        })
    return result


def _broadcast_event(event_type, data):
    """向所有 SSE 客户端推送事件"""
    msg = {"event": event_type, "data": data, "timestamp": time.time()}
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except Exception:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


# ═══════════════════════════════════════════
# 下载模型
# ═══════════════════════════════════════════
def cancel_download(model_id):
    """取消/暂停下载"""
    if model_id not in MODEL_REGISTRY:
        raise ValueError(f"未知模型: {model_id}")

    with _downloads_lock:
        dl = _downloads.get(model_id)
        if not dl:
            return False, "没有正在进行的下载"
        if dl["status"] != "downloading":
            return False, "当前状态不是下载中"

        # 设置取消标记，_download_worker 的循环会检测到并终止 aria2
        dl["cancel"].set()

    return True, "已暂停"


def start_download(model_id):
    """启动模型下载（后台线程）"""
    if model_id not in MODEL_REGISTRY:
        raise ValueError(f"未知模型: {model_id}")

    # 远程服务引擎：模型由外部服务管理，不下载
    if MODEL_REGISTRY[model_id].get("is_remote_service"):
        return False, "专业成曲引擎为独立运行环境，无需下载。请先启动专业成曲服务。"

    # 已就绪的模型不用下
    status, _ = _detect_model_status(model_id)
    if status == "ready":
        return False, "模型已就绪，无需下载"

    with _downloads_lock:
        dl = _downloads.get(model_id)
        if dl and dl["status"] == "downloading":
            # 检查下载线程是否还活着（防止进程被杀后状态卡住）
            if dl.get("thread") and dl["thread"].is_alive():
                return False, "已在下载中"
            # 线程死了，清理状态重新下
            del _downloads[model_id]

        cancel_event = threading.Event()
        _downloads[model_id] = {
            "status": "downloading",
            "progress": 0,
            "speed": "0 MB/s",
            "started_at": time.time(),
            "cancel": cancel_event,
            "thread": None,
        }

    # 后台线程下载
    t = threading.Thread(target=_download_worker, args=(model_id,), daemon=True)
    with _downloads_lock:
        if model_id in _downloads:
            _downloads[model_id]["thread"] = t
    t.start()
    return True, "下载已启动"


def _download_worker(model_id):
    """下载工作线程（aria2 多线程 + 文件系统轮询进度）"""
    import subprocess
    import threading

    info = MODEL_REGISTRY[model_id]
    local_dir = _model_local_path(model_id)
    os.makedirs(local_dir, exist_ok=True)

    cancel_event = _downloads[model_id]["cancel"]
    hf_endpoint = os.environ.get("HF_ENDPOINT", "https://huggingface.co")

    # ── 从 HF API 获取真实文件列表 ──
    import json as _json
    import urllib.request
    import urllib.error
    repo = info["hf_repo"]
    api_url = f"{hf_endpoint}/api/models/{repo}/tree/main"
    try:
        req = urllib.request.Request(api_url)
        # hf-mirror 对 Python-urllib 默认 UA 返回 403，必须带浏览器 UA
        req.add_header("User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
        # 加上代理（如果有）
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("ALL_PROXY") or ""
        if proxy:
            proxy_handler = urllib.request.ProxyHandler({"https": proxy, "http": proxy})
            opener = urllib.request.build_opener(proxy_handler)
            urllib.request.install_opener(opener)
        with urllib.request.urlopen(req, timeout=30) as resp:
            api_files = _json.loads(resp.read().decode())
    except Exception as e:
        raise RuntimeError(f"获取文件列表失败: {e}")

    # 构建 URL + 目标路径
    base_url = f"{hf_endpoint}/{repo}/resolve/main"
    download_items = []  # (url, target_path, size)
    total_size = 0
    for f in api_files:
        if f.get("type") == "directory":
            continue
        path = f.get("path", "")
        if not path or path.startswith(".git") or "xet" in path.lower():
            continue
        size = f.get("size", 0)
        total_size += size
        url = f"{base_url}/{path}"
        target = os.path.join(local_dir, path)
        download_items.append((url, target, size))

    # 兜底总大小
    if total_size == 0:
        total_size = info.get("size_mb", 2000) * 1024 * 1024

    def _dir_size(path):
        total = 0
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    # 排除日志和控制文件（不是模型数据）
                    if f in (".download.log",) or f.endswith(".aria2"):
                        continue
                    fp = os.path.join(root, f)
                    # 用 st_blocks 统计实际磁盘占用（稀疏文件 getsize 返回逻辑大小，速度会失真）
                    st = os.stat(fp)
                    total += st.st_blocks * 512
                except OSError:
                    pass
        return total

    last_size = [_dir_size(local_dir)]
    last_time = [time.time()]
    running = [True]

    def _progress_monitor():
        """监控线程：每秒扫目录大小，计算速度/ETA/进度"""
        while running[0] and not cancel_event.is_set():
            time.sleep(1)
            cur_size = _dir_size(local_dir)
            now = time.time()
            dt = now - last_time[0]
            if dt <= 0:
                continue

            ds = cur_size - last_size[0]
            speed = ds / dt  # B/s

            # 格式化速度
            speed_mb = speed / 1024 / 1024
            if speed_mb >= 1:
                speed_str = f"{speed_mb:.1f} MB/s"
            elif speed > 0:
                speed_str = f"{speed/1024:.0f} KB/s"
            else:
                speed_str = "连接中..."

            # ETA
            remaining = total_size - cur_size
            if speed > 0 and remaining > 0:
                eta_sec = int(remaining / speed)
                if eta_sec > 3600:
                    eta_str = f"{eta_sec//3600}h{eta_sec%3600//60}m"
                elif eta_sec > 60:
                    eta_str = f"{eta_sec//60}m{eta_sec%60}s"
                else:
                    eta_str = f"{eta_sec}s"
            else:
                eta_str = "计算中..."

            progress = min(99, int(cur_size / total_size * 100)) if total_size > 0 else 0

            total_gb = total_size / 1024 / 1024 / 1024
            cur_gb = cur_size / 1024 / 1024 / 1024
            if total_gb >= 1:
                downloaded_label = f"{cur_gb:.1f} / {total_gb:.1f} GB"
            else:
                downloaded_label = f"{cur_size/1024/1024:.0f} / {total_size/1024/1024:.0f} MB"

            # 更新内存状态（/models 接口读取）
            with _downloads_lock:
                if model_id in _downloads:
                    _downloads[model_id]["progress"] = progress
                    _downloads[model_id]["speed"] = speed_str
                    _downloads[model_id]["eta"] = eta_str
                    _downloads[model_id]["downloaded_label"] = downloaded_label

            _broadcast_event("download_progress", {
                "model_id": model_id,
                "status": "downloading",
                "progress": progress,
                "speed": speed_str,
                "eta": eta_str,
                "downloaded_label": downloaded_label,
            })

            last_size[0] = cur_size
            last_time[0] = now

    # 启动监控线程
    monitor_thread = threading.Thread(target=_progress_monitor, daemon=True)
    monitor_thread.start()

    try:
        # 准备 aria2 参数
        # 生成临时文件列表
        import tempfile
        list_file = tempfile.NamedTemporaryFile(mode='w', suffix='_urls.txt', delete=False)
        for url, target, size in download_items:
            # 确保目标目录存在
            os.makedirs(os.path.dirname(target), exist_ok=True)
            list_file.write(f"{url}\n")
            list_file.write(f"  out={os.path.basename(target)}\n")
            list_file.write(f"  dir={os.path.dirname(target)}\n")
        list_file.close()

        # 代理参数（从环境变量读）
        # 国内镜像站(hf-mirror.com)直连更快，不走代理（代理绕路反而慢）
        proxy = ""
        if "hf-mirror.com" not in hf_endpoint.lower():
            proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("ALL_PROXY") or ""

        # 构建 aria2 命令
        log_file = os.path.join(local_dir, ".download.log")
        cmd = [
            "aria2c",
            "--enable-rpc=false",
            "--no-conf=true",
            "--input-file", list_file.name,
            "--max-connection-per-server=16",
            "--max-concurrent-downloads=1",
            "--split=16",
            "--min-split-size=1M",
            "--file-allocation=none",
            "--continue=true",
            "--auto-file-renaming=false",
            "--allow-overwrite=true",
            "--check-certificate=true",
            "--max-tries=5",
            "--retry-wait=2",
            "--timeout=30",
            "--connect-timeout=15",
            "-l", log_file,
            "--log-level=info",
        ]
        if proxy:
            cmd.append(f"--all-proxy={proxy}")

        _log(f"[download] 启动 aria2: {len(download_items)} 个文件，代理: {'是' if proxy else '否'}")

        # 启动 aria2
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        # 后台等待 aria2 完成，同时检查取消
        def _wait_aria2():
            proc.wait()

        wait_thread = threading.Thread(target=_wait_aria2, daemon=True)
        wait_thread.start()

        while wait_thread.is_alive():
            if cancel_event.is_set():
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break
            time.sleep(0.5)

        running[0] = False

        if cancel_event.is_set():
            # 用户取消
            cur_size = _dir_size(local_dir)
            progress = min(99, int(cur_size / total_size * 100)) if total_size > 0 else 0
            _broadcast_event("download_progress", {
                "model_id": model_id,
                "status": "paused",
                "progress": max(1, progress),
                "speed": "",
                "eta": "已暂停",
            })
            _log(f"[download] {model_id} 已暂停")
        elif proc.returncode == 0:
            # 完成
            final_size = _dir_size(local_dir)
            total_gb = final_size / 1024 / 1024 / 1024
            _broadcast_event("download_progress", {
                "model_id": model_id,
                "status": "ready",
                "progress": 100,
                "speed": "",
                "eta": "",
                "downloaded_label": f"{total_gb:.1f} GB",
            })
            _log(f"[download] {model_id} 完成")
            _scan_all_models()
        else:
            # 失败
            cur_size = _dir_size(local_dir)
            progress = min(99, int(cur_size / total_size * 100)) if total_size > 0 else 0
            _broadcast_event("download_progress", {
                "model_id": model_id,
                "status": "error",
                "progress": max(1, progress),
                "speed": "",
                "eta": f"错误: aria2 返回码 {proc.returncode}",
            })
            _log(f"[download] {model_id} 失败: aria2 返回 {proc.returncode}")

        # 清理临时文件
        try:
            os.unlink(list_file.name)
        except OSError:
            pass

        _downloads.pop(model_id, None)

    except Exception as e:
        running[0] = False
        cur_size = _dir_size(local_dir)
        progress = min(99, int(cur_size / total_size * 100)) if total_size > 0 else 0
        _broadcast_event("download_progress", {
            "model_id": model_id,
            "status": "error",
            "progress": max(1, progress),
            "speed": "",
            "eta": f"错误: {str(e)[:50]}",
        })
        _log(f"[download] {model_id} 异常: {e}")
        _downloads.pop(model_id, None)
# ═══════════════════════════════════════════
# 引擎注册表（生成用）
# ═══════════════════════════════════════════
_engines = {}
_engine_lock = threading.Lock()


class MusicgenEngine:
    """通用 MusicGen 引擎（small/medium/large/melody/stereo 全家族共用）"""
    token_per_sec = 50

    def __init__(self, model_id):
        self.model_id = model_id
        self.model = None
        self.processor = None

    def _low_memory(self):
        """检查可用内存是否低于模型需求（macOS 用 vm_stat）
        按模型大小动态算需求：模型磁盘大小 × 0.6（fp16）+ 生成中间张量 1GB
        small/medium 走 MPS 只需 1-2GB，stereo 大模型才需要更多

        2026-08-10 内存保护升级（事故：ACE-Step DiT 常驻 + MusicGen 同跑 → 16GB M2 重启）:
        1. 进程级：检测系统里是否已有其他大模型进程（ace-step/api_server/其他 python
           推理进程），有则直接拒绝上 MPS——同一时间只允许一个大模型常驻。
        2. 全局内存：不只是 free+inactive，还要求系统空闲率 >25% 才上 MPS。
        3. 调用时机：load() 和 generate() 各查一次（加载后内存膨胀双保险）。
        """
        try:
            import subprocess
            # ── 1. 进程级检查：其他大模型进程是否常驻 ──
            # 事故根因：ACE-Step DiT 4.5GB 常驻 MPS，未检测直接叠加 MusicGen
            ps = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            ).stdout
            big_procs = []
            for line in ps.splitlines():
                low = line.lower()
                # 排除自己（musicgen/server.py 或 tonelab-engine）——
                # 注意：不能匹配裸 "server.py"，会误伤 api_server.py（ACE-Step 的进程名！）
                if "tonelab-engine" in low or "/engines/musicgen/" in low or "musicgen/server.py" in low:
                    continue
                # 大模型推理进程特征：api_server/acestep/whisper/llama/vllm/sd-webui/ollama
                if any(k in low for k in [
                    "api_server", "acestep", "whisper", "llama.cpp", "llama-cli",
                    "vllm", "sd-webui", "ollama", "stable-diffusion", "comfyui",
                ]):
                    # 提取内存占比
                    parts = line.split()
                    if len(parts) > 5:
                        mem_pct = parts[3]
                        try:
                            if float(mem_pct.rstrip('%')) > 3.0:  # >3% 内存的大推理进程
                                big_procs.append(f"{parts[10] if len(parts)>10 else '?'} ({mem_pct})")
                        except ValueError:
                            pass
            if big_procs:
                _log(f"[memory] 检测到其他大模型进程常驻，拒绝 MPS 加速: {big_procs}")
                return True  # low memory → 强制 CPU

            # ── 2. 全局内存：系统空闲率 >25% 才允许 MPS ──
            # MPS 用统一内存，free+inactive 偏乐观；memory_pressure 更真实
            mem_pressure = subprocess.run(
                ["memory_pressure", "-Q"], capture_output=True, text=True, timeout=5
            ).stdout
            free_pct = 0
            for line in mem_pressure.splitlines():
                if "free percentage" in line:
                    free_pct = int(line.split(":")[-1].strip().rstrip("%"))
            if free_pct > 0 and free_pct < 25:
                _log(f"[memory] 系统空闲内存仅 {free_pct}%，拒绝 MPS 加速（强制 CPU）")
                return True

            # ── 3. 模型自身需求 vs 空闲内存（原有逻辑兜底）──
            # 模型大小（磁盘）——safetensors 与 pytorch_model.bin 是同一权重两种格式，只取一份
            path = _model_local_path(self.model_id)
            model_bytes = 0
            safetensors_total = 0
            for root, dirs, files in os.walk(path):
                for f in files:
                    fp = os.path.join(root, f)
                    if f.endswith(".safetensors"):
                        try:
                            safetensors_total += os.path.getsize(fp)
                        except OSError:
                            pass
                    elif f.endswith(".bin") and "state_dict" not in f:
                        try:
                            model_bytes += os.path.getsize(fp)
                        except OSError:
                            pass
            # 有 safetensors 用 safetensors（现代格式），否则用 bin
            if safetensors_total > 0:
                model_bytes = safetensors_total
            need_gb = model_bytes / 1024 / 1024 / 1024 * 0.5 + 1.0
            out = subprocess.run(
                ["vm_stat"], capture_output=True, text=True, timeout=5
            ).stdout
            free_pages = 0
            for line in out.splitlines():
                if line.startswith("Pages free:"):
                    free_pages = int(line.split(":")[1].strip().rstrip("."))
                elif line.startswith("Pages inactive:"):
                    free_pages += int(line.split(":")[1].strip().rstrip("."))
            page_size = 16384  # macOS 默认
            free_gb = free_pages * page_size / 1024 / 1024 / 1024
            return free_gb < need_gb
        except Exception:
            return False

    def load(self):
        if self.model is not None:
            return
        from transformers import AutoProcessor, MusicgenForConditionalGeneration
        import torch
        
        path = _model_local_path(self.model_id)
        self.processor = AutoProcessor.from_pretrained(path)

        # 自动选择设备：MPS > CPU，支持 TONELAB_DEVICE 环境变量覆盖
        device_override = os.environ.get("TONELAB_DEVICE", "").lower()
        if device_override in ("mps", "cpu", "cuda"):
            self.device = device_override
        elif torch.backends.mps.is_available():
            self.device = "mps"
        else:
            self.device = "cpu"

        # 内存保护：MPS 需要模型驻留显存+生成中间张量，内存紧张时退回 CPU
        if self.device == "mps" and self._low_memory():
            print(f"[tonelab-engine] 内存不足（<4GB 空闲），退回 CPU", flush=True)
            self.device = "cpu"

        # MPS 上加载 fp16 省一半内存（stereo 模型 fp32 + MPS 会 OOM）
        load_dtype = torch.float16 if self.device == "mps" else None
        self.model = MusicgenForConditionalGeneration.from_pretrained(
            path,
            torch_dtype=load_dtype,
        )

        if self.device != "cpu":
            try:
                self.model = self.model.to(self.device)
                _log(f"[tonelab-engine] model moved to {self.device}" + (" (fp16)" if load_dtype else ""))
            except Exception as e:
                _log(f"[tonelab-engine] 切换到 {self.device} 失败，退回 CPU: {e}")
                self.device = "cpu"
                self.model = self.model.float().to("cpu")
        else:
            _log("[tonelab-engine] using CPU")

    def generate(self, prompt, duration, output_path=None, **kwargs):
        # 内存看门狗（驻留后双保险）：模型已驻留 MPS 时，生成前再查系统空闲率，
        # 若其他大模型进程新出现导致内存紧张，拒绝本次生成而不是悄悄降级——
        # 模型已驻留 MPS，降级需 reload 开销大，且叠模型才是崩溃根因。
        if self.model is not None and self.device == "mps":
            try:
                import subprocess
                mem_pressure = subprocess.run(
                    ["memory_pressure", "-Q"], capture_output=True, text=True, timeout=5
                ).stdout
                free_pct = 0
                for line in mem_pressure.splitlines():
                    if "free percentage" in line:
                        free_pct = int(line.split(":")[-1].strip().rstrip("%"))
                if 0 < free_pct < 15:  # 15% 红线：继续生成会触发系统内存压缩/杀进程
                    _log(f"[memory] 生成前检测空闲内存仅 {free_pct}%，拒绝生成（请关闭其他 AI 应用）")
                    raise RuntimeError(f"内存不足（空闲 {free_pct}%）。请关闭其他 AI 生成应用后重试。")
            except RuntimeError:
                raise
            except Exception:
                pass  # 检测失败不阻塞生成
        self.load()
        # BPM → 声音化 tempo 描述（MusicGen 听不懂"bpm 60"，但懂"very slow tempo"）
        # 铁律：tempo 词必须前置——MusicGen 对 prompt 尾部注意力低，拼尾部会被
        # 预设标签稀释成无效（实测：用户选极慢 45 但生成的音乐不慢不空灵）。
        bpm = kwargs.get("bpm")
        if bpm:
            tempo_desc = _bpm_to_tempo(bpm)
            prompt = f"{tempo_desc}, {prompt}"
        # 结构模板：MusicGen 单段生成无真结构控制，但训练数据含结构感音乐，
        # 结构描述词能让开头/结尾更完整（前奏铺垫 + 尾奏收束），避免"一上来就是
        # 主体、戛然而止"的听感。结构词拼在尾部作为整体框架。
        structure = kwargs.get("structure")
        if structure:
            prompt = f"{prompt}, {structure}"

        # 自由参数（全部可选，默认值与 MusicGen 官方一致）
        guidance = float(kwargs.get("guidance_scale") or 3.0)
        temperature = float(kwargs.get("temperature") or 1.0)
        top_k = int(kwargs.get("top_k") or 250)
        top_p = float(kwargs.get("top_p") or 0.0)  # 0 = 不启用

        gen_kwargs = dict(
            do_sample=True,
            guidance_scale=guidance,
            temperature=temperature,
            top_k=top_k,
        )
        if top_p > 0:
            gen_kwargs["top_p"] = top_p

        sr = self.model.config.audio_encoder.sampling_rate
        if not output_path:
            output_path = os.path.join(OUTPUT_DIR, f"mg_{int(time.time())}.wav")

        # ── 分段生成（核心）：MusicGen 单段生成 >30 秒必然退化 ──
        # 自回归模型长序列累积误差 → 30 秒后旋律崩坏、变成噪声（用户实测：
        # 婚礼 60 秒，间奏后就是杂音）。官方 demo/论文上限即 30 秒。
        # 修法：>30 秒拆成多个 30 秒段独立生成，段间 1 秒交叉淡入淡出拼接，
        # 每段都在模型安全区内，长音频不再出杂音。
        CHUNK_SEC = 30
        if duration <= CHUNK_SEC:
            audio = self._gen_single_chunk(prompt, duration, gen_kwargs)
            audio_np = self._chunk_to_float32(audio)
        else:
            chunks = []
            remaining = duration
            while remaining > 0:
                cur = min(CHUNK_SEC, remaining)
                a = self._gen_single_chunk(prompt, cur, gen_kwargs)
                chunks.append(self._chunk_to_float32(a))
                remaining -= cur
            audio_np = self._crossfade_concat(chunks, sr)
            _log(f"[generate] 分段生成 {len(chunks)} 段 x ≤{CHUNK_SEC}s 拼接完成 ({duration}s)")

        # stereo 模型输出 (1, 2, T)，单声道输出 (1, 1, T)；保留全部声道
        # 转 (channels, T) → 需保留声道数信息
        n_channels = audio_np.shape[0] if audio_np.ndim == 2 else 1
        # scipy 写 wav 需要 (N, channels) 或 (N,)，转置
        if audio_np.ndim == 2 and audio_np.shape[0] > 1:
            audio_np = audio_np.T  # (T, channels)
        else:
            audio_np = audio_np[0] if audio_np.ndim == 2 else audio_np  # (T,)
        # WebKit/AVFoundation 的 <audio> 不支持 IEEE float WAV，只认 PCM int16。
        # float32 → int16（clip 防溢出），否则生成成功但无法播放（Error 状态）。
        # 结尾 fade-out：MusicGen 自回归生成到 max_new_tokens 会硬截断（官方承认的
        # "abrupt endings"缺陷），不做 fade 就是"咔"地切断。行业标杆（Suno/Stable Audio）
        # 全部做淡出。默认最后 3 秒指数衰减到 0，避免突然结束。
        actual_dur = audio_np.shape[0] / sr
        fade_sec = float(kwargs.get("fade_out") or 3.0)
        fade_sec = min(fade_sec, max(0.5, actual_dur * 0.4))
        if fade_sec > 0 and audio_np.shape[-1] > 1:
            fade_samples = int(fade_sec * sr)
            # 指数曲线：1.0 → 0，斜率平缓开始加速衰减，听感自然
            t = np.linspace(0, 1, fade_samples)
            curve = np.exp(-4.5 * t)
            if audio_np.ndim == 1:
                audio_np[-fade_samples:] *= curve
            else:
                audio_np[-fade_samples:, :] *= curve[:, None]
        audio_np = (audio_np * 32767).clip(-32768, 32767).astype("int16")
        scipy.io.wavfile.write(output_path, rate=sr, data=audio_np)

        actual_sec = audio_np.shape[0] / sr
        n_channels = 2 if audio_np.ndim == 2 else 1
        return {
            "path": output_path,
            "sample_rate": sr,
            "duration": round(actual_sec, 2),
            "channels": n_channels,
            "device": self.device,  # mps / cpu，前端显示加速状态
        }

    # ── 分段生成辅助 ──

    def _gen_single_chunk(self, prompt, chunk_sec, gen_kwargs):
        """生成单段（≤30 秒，模型安全区）。返回 torch tensor (1, channels, T)"""
        max_tokens = int(chunk_sec * self.token_per_sec)
        inputs = self.processor(text=[prompt], padding=True, return_tensors="pt")
        if self.device != "cpu":
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
        gk = dict(gen_kwargs)
        gk.update(inputs)
        gk["max_new_tokens"] = max_tokens
        return self.model.generate(**gk)

    def _chunk_to_float32(self, audio):
        """torch tensor (1, channels, T) → numpy (channels, T) float32"""
        audio_np = audio[0].cpu().numpy()  # (channels, T)
        if audio_np.ndim == 1:
            audio_np = audio_np[None, :]
        if audio_np.dtype != "float32":
            audio_np = audio_np.astype("float32")
        return audio_np

    def _crossfade_concat(self, chunks, sr, cross_sec=1.0):
        """多段 (channels, T) 交叉淡入淡出拼接。
        段 A 尾 cross_sec 秒线性 fade-out，段 B 头 cross_sec 秒线性 fade-in，
        重叠区相加——节拍不完全同步但过渡平滑无咔哒，比硬拼或留缝强。
        """
        if len(chunks) == 1:
            return chunks[0]
        cross = int(cross_sec * sr)
        out = chunks[0]
        for nxt in chunks[1:]:
            tail = out[..., -cross:]
            head = nxt[..., :cross]
            fade_out = np.linspace(1.0, 0.0, cross)
            fade_in = np.linspace(0.0, 1.0, cross)
            if out.ndim == 2:
                merged = tail * fade_out[None, :] + head * fade_in[None, :]
                out = np.concatenate([out[..., :-cross], merged, nxt[..., cross:]], axis=-1)
            else:
                merged = tail * fade_out + head * fade_in
                out = np.concatenate([out[:-cross], merged, nxt[cross:]])
        return out


class AceStepEngine:
    """ACE-Step 1.5 引擎（HTTP 客户端模式，零本地模型驻留）。

    与 MusicgenEngine 不同：ACE-Step 跑在独立服务（~/.acestep/ 或 ~/Projects/ACE-Step-portable/，
    默认 http://127.0.0.1:8001），本类只做 HTTP 客户端——release_task 提交任务 → 轮询
    query_result 拿结果。不占本进程内存，不冲突 MusicGen 常驻模型。

    产物: 48kHz 立体声 WAV（比 MusicGen 32kHz 单声道规格高），自带结构感 + fade-out。
    对比实测（2026-08-10）: ACE-Step turbo 8 步 30s ≈ 2.5 分钟（MLX），MusicGen small 30s ≈ 2 分钟（MPS）。
    """

    token_per_sec = 50  # 接口兼容占位（ACE-Step 走 duration 秒数，不走 token）

    def __init__(self, model_id="acestep-v15-turbo"):
        self.model_id = model_id
        self.device = "ace"  # 外部服务，无本地设备
        self.base_url = os.environ.get("ACESTEP_API_URL", "http://127.0.0.1:8001")

    def _health(self):
        """ACE-Step 服务是否存活"""
        try:
            req = urllib.request.Request(
                f"{self.base_url}/health", method="GET",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            with urllib.request.urlopen(req, timeout=3) as r:
                body = json.loads(r.read().decode())
                return body.get("data", {}).get("status") == "ok"
        except Exception:
            return False

    def load(self):
        """无本地加载；但检查 ACE-Step 服务是否存活，死了抛可读错误"""
        if not self._health():
            raise RuntimeError(
                "未检测到专业成曲引擎服务（127.0.0.1:8001）。\n"
                "请先启动专业成曲引擎，或配置 ACESTEP_API_URL 指向你的服务"
            )
        _log(f"[acestep] 服务已连接: {self.base_url}")

    def generate(self, prompt, duration, output_path=None, **kwargs):
        """调 ACE-Step release_task + 轮询 query_result。
        返回结构对齐 MusicgenEngine（path/sample_rate/duration/channels/device）。
        """
        self.load()

        bpm = kwargs.get("bpm")
        structure = kwargs.get("structure")
        # BPM 前置（同 MusicGen 逻辑：tempo 词开头权重最高）
        if bpm:
            from server import _bpm_to_tempo  # noqa: 同文件直接调用
            prompt = f"{_bpm_to_tempo(bpm)}, {prompt}"
        # 结构模板拼尾部
        if structure:
            prompt = f"{prompt}, {structure}"

        # 组装 release_task 参数（对齐 ACE-Step API 契约）
        payload = {
            "prompt": prompt,
            "bpm": int(bpm) if bpm else 0,
            "duration": int(duration),
            "guidance_scale": float(kwargs.get("guidance_scale") or 7.0),
            "inference_steps": int(kwargs.get("inference_steps") or 8),
            "seed": int(kwargs.get("seed") or -1),
            "audio_format": "wav",
            "task_type": "text2music",
        }
        _log(f"[acestep] 提交生成任务: prompt={prompt[:60]}... duration={duration}s")

        # ── 1. release_task ──
        try:
            req = urllib.request.Request(
                f"{self.base_url}/release_task",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read().decode())
            task_id = resp.get("data", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"ACE-Step 提交失败: {resp}")
            _log(f"[acestep] 任务已排队: {task_id}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"ACE-Step 提交失败（服务未启动？）: {e}")

        # ── 2. 轮询 query_result（task_id_list 数组！单 task_id 会返回空）──
        import time as _time
        deadline = _time.time() + 600  # 10 分钟上限
        last_err = None
        while _time.time() < deadline:
            _time.sleep(5)
            try:
                qreq = urllib.request.Request(
                    f"{self.base_url}/query_result",
                    data=json.dumps({"task_id_list": [task_id]}).encode(),
                    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                    method="POST",
                )
                with urllib.request.urlopen(qreq, timeout=15) as r:
                    qresp = json.loads(r.read().decode())
                items = qresp.get("data", [])
                if not items:
                    continue
                item = items[0]
                status = item.get("status")
                # ACE-Step status 语义（server_utils.STATUS_MAP）:
                #   queued/running=0, succeeded=1, failed=2
                # result 是 JSON 字符串，内含 file URL（/v1/audio?path=...）
                if status == 1:
                    try:
                        result_str = item.get("result", "")
                        result_list = json.loads(result_str) if result_str else []
                        if result_list:
                            fpath = result_list[0].get("file", "")
                            # file 是 URL: /v1/audio?path=%2FUsers%2F... —— 解出 path 参数
                            from urllib.parse import urlparse, parse_qs
                            if fpath.startswith("/v1/audio"):
                                qs = parse_qs(urlparse(fpath).query)
                                fpath = qs.get("path", [""])[0]
                            import urllib.parse as _up
                            fpath = _up.unquote(fpath)
                            if fpath and os.path.exists(fpath):
                                _log(f"[acestep] 生成完成: {fpath}")
                                return self._finalize(fpath, output_path, duration)
                    except Exception as e:
                        last_err = f"ACE-Step 结果解析失败: {e}"
                        break
                elif status == 2:
                    last_err = f"ACE-Step 任务失败 (status=2)"
                    break
            except Exception as e:
                last_err = str(e)
                _time.sleep(3)

        raise RuntimeError(last_err or "ACE-Step 生成超时（10 分钟）")

    def _finalize(self, src_path, output_path, duration):
        """把 ACE-Step 产物拷到输出目录，返回对齐 MusicgenEngine 的 dict"""
        if not output_path:
            output_path = os.path.join(OUTPUT_DIR, f"acestep_{int(time.time())}.wav")
        # 拷贝（保留 48kHz 立体声原始规格）
        import shutil
        shutil.copy2(src_path, output_path)
        # 探测时长/声道（用 wave 模块读头）
        try:
            import wave
            with wave.open(output_path, "rb") as w:
                sr = w.getframerate()
                n_ch = w.getnchannels()
                frames = w.getnframes()
                dur = frames / sr
        except Exception:
            sr, n_ch, dur = 48000, 2, float(duration)
        return {
            "path": output_path,
            "sample_rate": sr,
            "duration": round(dur, 2),
            "channels": n_ch,
            "device": "ace-step",  # 前端显示"专业成曲引擎"
        }


ENGINE_CLASSES = {
    "musicgen-small": MusicgenEngine,
    "musicgen-medium": MusicgenEngine,
    "musicgen-large": MusicgenEngine,
    "musicgen-melody": MusicgenEngine,
    "musicgen-stereo-small": MusicgenEngine,
    "musicgen-stereo-melody": MusicgenEngine,
    "musicgen-stereo-large": MusicgenEngine,
    "acestep-v15-turbo": AceStepEngine,
}


def get_engine(engine_id):
    with _engine_lock:
        if engine_id not in _engines:
            if engine_id not in ENGINE_CLASSES:
                raise ValueError(f"未知引擎: {engine_id}")
            _engines[engine_id] = ENGINE_CLASSES[engine_id](engine_id)
        return _engines[engine_id]


# ═══════════════════════════════════════════
# HTTP 服务
# ═══════════════════════════════════════════
class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 访问日志：缓冲 + stdout + 落盘（GUI 启动时 stdout 不可见，落盘才能看到）
        line = f"{self.address_string()} {format % args}"
        _log(f"[req] {line}")
        _log_req(line)

    def _send_json(self, code, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
        elif self.path == "/ping":
            self._send_json(200, {"pong": True})
        elif self.path == "/models":
            self._send_json(200, {"models": get_models_info()})
        elif self.path == "/download/progress":
            self._handle_sse()
        elif self.path.startswith("/logs"):
            # 日志监控：/logs 返回全部，/logs?n=50 返回最近 50 条
            n = 200
            if "n=" in self.path:
                try:
                    n = int(self.path.split("n=")[1].split("&")[0])
                except ValueError:
                    pass
            with _LOG_LOCK:
                lines = list(LOG_BUFFER)[-n:]
            self._send_json(200, {"logs": lines, "count": len(lines)})
        else:
            self._send_json(404, {"error": "not found"})

    def do_POST(self):
        if self.path == "/generate":
            self._handle_generate()
        elif self.path == "/cancel":
            _cancel_flag.set()
            self._send_json(200, {"cancelled": True})
        elif self.path == "/models/scan":
            self._send_json(200, {"models": get_models_info()})
        elif self.path == "/download":
            params = self._read_json()
            mid = params.get("model_id", "")
            try:
                ok, msg = start_download(mid)
                self._send_json(200 if ok else 400, {"success": ok, "message": msg})
            except ValueError as e:
                self._send_json(400, {"success": False, "error": str(e)})
        elif self.path == "/download/cancel":
            params = self._read_json()
            mid = params.get("model_id", "")
            try:
                ok, msg = cancel_download(mid)
                self._send_json(200 if ok else 400, {"success": ok, "message": msg})
            except ValueError as e:
                self._send_json(400, {"success": False, "error": str(e)})
        elif self.path == "/models/remove":
            params = self._read_json()
            mid = params.get("model_id", "")
            try:
                ok, msg = remove_model(mid)
                self._send_json(200 if ok else 400, {"success": ok, "message": msg})
            except ValueError as e:
                self._send_json(400, {"success": False, "error": str(e)})
        else:
            self._send_json(404, {"error": "not found"})

    def _handle_sse(self):
        """SSE 流式推送下载进度"""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        q = Queue()
        with _sse_lock:
            _sse_clients.append(q)

        try:
            # 先发一次当前全部状态
            initial = {"event": "models_state", "data": {"models": get_models_info()}}
            self.wfile.write(f"data: {json.dumps(initial, ensure_ascii=False)}\n\n".encode())
            self.wfile.flush()

            while True:
                msg = q.get()  # 阻塞等待
                self.wfile.write(f"data: {json.dumps(msg, ensure_ascii=False)}\n\n".encode())
                self.wfile.flush()
        except Exception:
            pass
        finally:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    def _handle_generate(self):
        params = self._read_json()
        engine_id = params.get("engine", "musicgen-small")
        prompt = params.get("prompt", "").strip()
        duration = int(params.get("duration", 8))
        filename = params.get("filename")
        bpm = params.get("bpm")

        if not prompt:
            self._send_json(400, {"error": "prompt 不能为空"})
            return
        if duration <= 0 or duration > 300:
            self._send_json(400, {"error": "duration 必须在 1-300 秒之间"})
            return

        # 检查模型是否就绪
        status, _ = _detect_model_status(engine_id)
        if status != "ready":
            self._send_json(400, {"error": f"模型 {engine_id} 未就绪，当前状态: {status}"})
            return

        if not _generation_lock.acquire(blocking=False):
            self._send_json(409, {"error": "当前正在生成，请稍后再试"})
            return

        try:
            if filename:
                if not filename.endswith(".wav"):
                    filename += ".wav"
                output_path = os.path.join(OUTPUT_DIR, filename)
            else:
                output_path = os.path.join(
                    OUTPUT_DIR, f"tonelab_{int(time.time())}.wav"
                )

            engine = get_engine(engine_id)
            t0 = time.time()
            result = engine.generate(
                prompt=prompt,
                duration=duration,
                output_path=output_path,
                guidance_scale=params.get("guidance_scale"),
                temperature=params.get("temperature"),
                top_k=params.get("top_k"),
                top_p=params.get("top_p"),
                bpm=params.get("bpm"),
                structure=params.get("structure"),
            )
            result["generation_time"] = round(time.time() - t0, 2)
            result["rtf"] = round(result["generation_time"] / result["duration"], 2) if result["duration"] > 0 else 0
            self._send_json(200, {"success": True, **result})
        except NotImplementedError as e:
            self._send_json(501, {"success": False, "error": str(e)})
        except Exception as e:
            import traceback
            self._send_json(500, {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
            })
        finally:
            _generation_lock.release()


def _bpm_to_tempo(bpm):
    """BPM → 声音化 tempo 描述词（MusicGen 可感知）。

    MusicGen 没有精确 BPM 控制（无节拍器），但训练数据按速度/节奏特征标注，
    tempo 描述词有效。档位映射按音乐速度学划分：
    - 极慢/舒缓档（<70）氛围主导：用户选慢 BPM 的意图通常是"空灵/氛围"，
      而空灵是氛围属性（pads/space/reverb）不是节奏属性。
      实测对比（ToneLab 2026-08-10）：
      民谣吉他+BPM45 → 慢民谣（质心 1255Hz，仍有弹拨节奏感）
      空灵 pad+BPM45  → 真空灵（质心 776Hz，持续织体）
      所以慢档必须注入氛围主导词，否则弹拨/节奏型乐器的律动压过慢速感。
    """
    bpm = float(bpm)
    if bpm < 50:
        return "ethereal ambient atmosphere, very slow glacial tempo, sparse shimmering pads, vast open space, weightless, dreamy, floating, no percussion"
    elif bpm < 70:
        return "ambient atmosphere, slow gentle tempo, soft pads, airy, spacious, calm, dreamy"
    elif bpm < 90:
        return "moderate slow tempo, steady, mellow, relaxed groove"
    elif bpm < 115:
        return "moderate tempo, steady beat"
    elif bpm < 140:
        return "upbeat tempo, lively rhythm"
    else:
        return "fast tempo, energetic, driving rhythm"


def main():
    port = PORT
    if len(sys.argv) > 1:
        port = int(sys.argv[1])

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"ENGINE_READY port={port}", flush=True)  # Rust 端识别启动标记
    server.serve_forever()


if __name__ == "__main__":
    main()
