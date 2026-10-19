from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from crawler_core.paths import find_chrome_executable


@dataclass(frozen=True)
class CrawlerSettings:
    """当前项目的无敏感运行配置。"""

    python_exe: str = ""
    default_fetch_mode: str = "online"
    chrome_exe_path: str = ""
    chrome_user_data_dir_name: str = ".chrome_cdp_profile"
    snapshot_dir_name: str = "workspace/snapshots"
    request_timeout_seconds: int = 30
    browser_timeout_seconds: int = 30
    request_max_retries: int = 2
    suspicious_html_min_length: int = 2000
    retry_base_sleep_seconds: float = 1.2
    retry_max_sleep_seconds: float = 6.0
    browser_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
    )
    browser_locale: str = "zh-CN"
    browser_viewport_width: int = 1365
    browser_viewport_height: int = 900
    browser_screen_width: int = 1365
    browser_screen_height: int = 900
    browser_device_scale_factor: float = 1.0
    browser_headless: bool = True
    browser_ignore_https_errors: bool = True
    browser_block_heavy_resources: bool = False
    browser_render_wait_ms: int = 3000
    browser_render_poll_interval_ms: int = 250
    browser_render_stable_samples: int = 2
    browser_domcontentloaded_timeout_ms: int = 8000
    browser_networkidle_timeout_ms: int = 2000
    browser_commit_timeout_ms: int = 10000
    chrome_cdp_connect_timeout_seconds: int = 10
    chrome_warmup_timeout_ms: int = 4000
    chrome_warmup_wait_ms: int = 250
    chrome_debug_port: int = 9222
    session_pool_size: int = 64
    retryable_status_codes: tuple[int, ...] = (
        408,
        425,
        429,
        500,
        502,
        503,
        504,
        520,
        521,
        522,
        523,
        524,
    )


@lru_cache(maxsize=1)
def get_settings() -> CrawlerSettings:
    """读取当前项目运行配置。后续如需接入环境变量，可集中修改此处。"""
    python_exe = os.environ.get("IMPORTANT_PERSON_PYTHON_EXE", "").strip()
    fetch_mode = os.environ.get("IMPORTANT_PERSON_FETCH_MODE", "online").strip().lower()
    if fetch_mode not in {"snapshot", "online", "requests", "playwright", "chrome", "raw_http", "llm_vision"}:
        fetch_mode = "online"
    try:
        chrome_exe_path = str(find_chrome_executable())
    except FileNotFoundError:
        chrome_exe_path = ""
    return CrawlerSettings(
        python_exe=python_exe,
        default_fetch_mode=fetch_mode,
        chrome_exe_path=chrome_exe_path,
    )
