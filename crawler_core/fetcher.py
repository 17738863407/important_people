from __future__ import annotations

import atexit
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import math
import os
import random
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup, Comment
from requests.adapters import HTTPAdapter

from crawler_core.settings import get_settings


SETTINGS = get_settings()


BAD_PAGE_MARKERS = (
    "访问异常",
    "验证码",
    "请开启 JavaScript",
    "请开启javascript",
    "浏览器版本过低",
    "系统维护",
    "页面不存在",
    "Not Found",
    "Forbidden",
    "Bad Gateway",
    "Gateway Time-out",
)


DEFAULT_HEADERS = {
    "User-Agent": SETTINGS.browser_user_agent,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}

REQUESTS_USER_AGENT_POOL = (
    SETTINGS.browser_user_agent,
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
)

REQUESTS_HEADER_PROFILES = (
    {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    },
    {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "DNT": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    },
    {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.7,en;q=0.6",
        "DNT": "1",
    },
)

BLOCKED_PLAYWRIGHT_RESOURCE_TYPES = {"image", "media"}

HEADER_CHARSET_PATTERN = re.compile(r"charset\s*=\s*['\"]?([A-Za-z0-9._-]+)", re.IGNORECASE)
META_CHARSET_PATTERN = re.compile(
    rb"<meta[^>]+charset\s*=\s*['\"]?\s*([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)
META_HTTP_EQUIV_CHARSET_PATTERN = re.compile(
    rb"<meta[^>]+content\s*=\s*['\"][^'\"]*charset\s*=\s*([A-Za-z0-9._-]+)",
    re.IGNORECASE,
)

CHROME_DEBUG_PORT = SETTINGS.chrome_debug_port
CHROME_EXE_PATH = SETTINGS.chrome_exe_path
CHROME_USER_DATA_DIR = str(Path(__file__).resolve().parents[1] / SETTINGS.chrome_user_data_dir_name)
PROJECT_DIR = Path(__file__).resolve().parents[1]
REQUESTS_SESSION = requests.Session()
REQUESTS_SESSION.headers.update(DEFAULT_HEADERS)
REQUESTS_SESSION.mount("http://", HTTPAdapter(pool_connections=SETTINGS.session_pool_size, pool_maxsize=SETTINGS.session_pool_size))
REQUESTS_SESSION.mount("https://", HTTPAdapter(pool_connections=SETTINGS.session_pool_size, pool_maxsize=SETTINGS.session_pool_size))
DIRECT_REQUESTS_SESSION = requests.Session()
DIRECT_REQUESTS_SESSION.trust_env = False
DIRECT_REQUESTS_SESSION.headers.update(DEFAULT_HEADERS)
DIRECT_REQUESTS_SESSION.mount(
    "http://",
    HTTPAdapter(pool_connections=SETTINGS.session_pool_size, pool_maxsize=SETTINGS.session_pool_size),
)
DIRECT_REQUESTS_SESSION.mount(
    "https://",
    HTTPAdapter(pool_connections=SETTINGS.session_pool_size, pool_maxsize=SETTINGS.session_pool_size),
)


def shutdown_project_chrome_debug(wait_seconds: float = 5.0) -> str:
    """只关闭使用项目专属用户目录和调试端口启动的 Chrome 进程树。"""
    try:
        import psutil
    except ImportError:
        return "未清理项目 Chrome CDP：当前环境缺少 psutil。"

    expected_port_argument = f"--remote-debugging-port={CHROME_DEBUG_PORT}".casefold()
    expected_profile = str(Path(CHROME_USER_DATA_DIR).resolve()).replace("\\", "/").casefold()
    matched_roots: list[Any] = []
    for process in psutil.process_iter(["name", "cmdline"]):
        try:
            process_name = str(process.info.get("name") or "").casefold()
            command_line = [str(item) for item in process.info.get("cmdline") or []]
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        normalized_arguments = [item.replace("\\", "/").casefold() for item in command_line]
        has_expected_port = expected_port_argument in normalized_arguments
        has_expected_profile = any(
            argument.startswith("--user-data-dir=")
            and argument.partition("=")[2].strip('"') == expected_profile
            for argument in normalized_arguments
        )
        if process_name == "chrome.exe" and has_expected_port and has_expected_profile:
            matched_roots.append(process)

    if not matched_roots:
        return "项目 Chrome CDP 生命周期检查完成：未发现需要关闭的项目专属进程。"

    managed_processes: dict[int, Any] = {}
    for root_process in matched_roots:
        try:
            for child_process in root_process.children(recursive=True):
                managed_processes[child_process.pid] = child_process
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
        managed_processes[root_process.pid] = root_process

    for process in managed_processes.values():
        try:
            process.terminate()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    _, survivors = psutil.wait_procs(
        list(managed_processes.values()),
        timeout=max(0.1, float(wait_seconds or 0.1)),
    )
    for process in survivors:
        try:
            process.kill()
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    if survivors:
        psutil.wait_procs(survivors, timeout=2.0)
    return (
        "项目 Chrome CDP 生命周期清理完成："
        f"关闭 {len(managed_processes)} 个项目专属进程，其中强制终止 {len(survivors)} 个。"
    )
PLAYWRIGHT_THREAD_POOL = threading.local()
PLAYWRIGHT_POOL_LOCK = threading.Lock()
PLAYWRIGHT_POOL_STATES: list[dict[str, Any]] = []
FETCH_DEADLINE_STATE = threading.local()
DOMAIN_CIRCUIT_LOCK = threading.Lock()
DOMAIN_CIRCUIT_STATES: dict[str, dict[str, Any]] = {}
CHROME_WARMUP_CACHE_LOCK = threading.Lock()
CHROME_WARMUP_LOCKS: dict[tuple[str, int, str], threading.Lock] = {}
CHROME_WARMED_DOMAINS: set[tuple[str, int, str]] = set()
CHROME_WARMUP_BROWSER_IDENTITY = ""


class DomainCircuitOpenError(RuntimeError):
    """表示当前运行中某个域名已因确定性或连续连接失败而熔断。"""


def domain_key_from_url(url: str) -> str:
    """提取请求级域名熔断使用的主机名。"""
    return str(urlparse(str(url or "")).hostname or "").strip().casefold()


def is_name_resolution_error(error: BaseException) -> bool:
    """识别 requests 在 Windows 上包装后的 DNS 解析失败。"""
    text = str(error or "").casefold()
    markers = (
        "nameresolutionerror",
        "failed to resolve",
        "name or service not known",
        "getaddrinfo failed",
        "nodename nor servname provided",
        "temporary failure in name resolution",
    )
    return any(marker in text for marker in markers)


def reset_domain_circuit_breakers() -> None:
    """清空本次进程内域名熔断状态，供新批次和测试隔离使用。"""
    with DOMAIN_CIRCUIT_LOCK:
        DOMAIN_CIRCUIT_STATES.clear()


def ensure_domain_circuit_closed(url: str) -> None:
    """在发起请求前检查域名是否处于熔断期。"""
    domain_key = domain_key_from_url(url)
    if not domain_key:
        return
    with DOMAIN_CIRCUIT_LOCK:
        state = DOMAIN_CIRCUIT_STATES.get(domain_key)
        if not state:
            return
        open_until = float(state.get("open_until") or 0.0)
        if open_until <= 0:
            return
        if open_until <= time.monotonic():
            DOMAIN_CIRCUIT_STATES.pop(domain_key, None)
            return
        reason = str(state.get("reason") or "连续连接失败")
    raise DomainCircuitOpenError(f"域名熔断：{domain_key}；原因：{reason}")


def record_domain_request_success(url: str) -> None:
    """请求建立连接后清除该域名的连续连接失败计数。"""
    domain_key = domain_key_from_url(url)
    if not domain_key:
        return
    with DOMAIN_CIRCUIT_LOCK:
        DOMAIN_CIRCUIT_STATES.pop(domain_key, None)


def record_domain_request_failure(url: str, error: BaseException) -> None:
    """记录域名级网络失败；DNS立即熔断，连续连接或读取超时两次后冷却。"""
    domain_key = domain_key_from_url(url)
    if not domain_key:
        return
    is_dns_failure = is_name_resolution_error(error)
    is_connection_failure = isinstance(
        error,
        (requests.exceptions.ConnectionError, requests.exceptions.Timeout),
    )
    if not is_dns_failure and not is_connection_failure:
        return
    with DOMAIN_CIRCUIT_LOCK:
        previous = DOMAIN_CIRCUIT_STATES.get(domain_key, {})
        failure_count = int(previous.get("failure_count") or 0) + 1
        if is_dns_failure:
            open_until = float("inf")
            reason = f"DNS解析失败：{error}"
        elif failure_count >= 2:
            open_until = time.monotonic() + 60.0
            reason = f"连续连接或读取超时{failure_count}次：{error}"
        else:
            open_until = 0.0
            reason = str(error)
        DOMAIN_CIRCUIT_STATES[domain_key] = {
            "failure_count": failure_count,
            "open_until": open_until,
            "reason": reason,
        }


def build_requests_timeout(timeout: int | float) -> tuple[float, float]:
    """把单一超时拆分为较短的连接超时和独立读取超时。"""
    total_seconds = max(2.0, float(timeout or 2.0))
    connect_seconds = min(8.0, max(2.0, total_seconds / 3.0))
    read_seconds = max(2.0, total_seconds - connect_seconds)
    return connect_seconds, read_seconds


@contextmanager
def enforce_fetch_deadline(timeout_seconds: int | float | None):
    """在当前工作线程中设置单脚本采集总截止时间。"""
    safe_timeout = float(timeout_seconds or 0)
    if safe_timeout <= 0:
        yield
        return

    previous_deadline = getattr(FETCH_DEADLINE_STATE, "deadline", None)
    requested_deadline = time.monotonic() + safe_timeout
    effective_deadline = (
        min(float(previous_deadline), requested_deadline)
        if previous_deadline is not None
        else requested_deadline
    )
    FETCH_DEADLINE_STATE.deadline = effective_deadline
    try:
        yield
    finally:
        if previous_deadline is None:
            try:
                del FETCH_DEADLINE_STATE.deadline
            except AttributeError:
                pass
        else:
            FETCH_DEADLINE_STATE.deadline = previous_deadline


def current_fetch_deadline() -> float | None:
    """返回当前线程的绝对截止时间，供详情页工作线程继承。"""
    deadline = getattr(FETCH_DEADLINE_STATE, "deadline", None)
    return float(deadline) if deadline is not None else None


@contextmanager
def inherit_fetch_deadline(deadline: float | None):
    """让子工作线程继承调用方的单脚本截止时间。"""
    if deadline is None:
        yield
        return
    previous_deadline = getattr(FETCH_DEADLINE_STATE, "deadline", None)
    FETCH_DEADLINE_STATE.deadline = (
        min(float(previous_deadline), float(deadline))
        if previous_deadline is not None
        else float(deadline)
    )
    try:
        yield
    finally:
        if previous_deadline is None:
            try:
                del FETCH_DEADLINE_STATE.deadline
            except AttributeError:
                pass
        else:
            FETCH_DEADLINE_STATE.deadline = previous_deadline


def remaining_fetch_timeout(requested_timeout: int | float) -> int:
    """按单脚本剩余时间收紧本次网络或浏览器操作的超时。"""
    safe_requested_timeout = max(1.0, float(requested_timeout or 1))
    deadline = getattr(FETCH_DEADLINE_STATE, "deadline", None)
    if deadline is None:
        return max(1, math.ceil(safe_requested_timeout))
    remaining_seconds = float(deadline) - time.monotonic()
    if remaining_seconds <= 0:
        raise TimeoutError("单脚本总运行超时")
    return max(1, math.ceil(min(safe_requested_timeout, remaining_seconds)))


def disable_unavailable_loopback_proxies(timeout: float = 0.5) -> list[str]:
    """仅当回环代理端口不可连接时，从当前Python进程临时移除对应代理变量。"""
    proxy_variable_names = (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "WS_PROXY",
        "WSS_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "ws_proxy",
        "wss_proxy",
    )
    unavailable_endpoints: set[tuple[str, int]] = set()
    managed_proxy_active = str(os.environ.get("CODEX_NETWORK_PROXY_ACTIVE") or "").strip().lower()
    managed_proxy_ports: set[int] = set()
    if managed_proxy_active in {"1", "true", "yes", "on"}:
        for raw_port in str(os.environ.get("CODEX_WINDOWS_SANDBOX_PROXY_PORTS") or "").split(","):
            try:
                port = int(raw_port.strip())
            except ValueError:
                continue
            if port > 0:
                managed_proxy_ports.add(port)
    for variable_name in proxy_variable_names:
        proxy_value = str(os.environ.get(variable_name) or "").strip()
        if not proxy_value:
            continue
        parsed = urlparse(proxy_value if "://" in proxy_value else f"http://{proxy_value}")
        hostname = str(parsed.hostname or "").strip().lower()
        if hostname not in {"127.0.0.1", "localhost", "::1"}:
            continue
        try:
            port = int(parsed.port or 0)
        except ValueError:
            continue
        if port <= 0:
            continue
        endpoint = (hostname, port)
        # Codex Windows 沙箱代理由宿主侧转发。沙箱内对其执行普通 TCP 探测可能
        # 返回 WinError 10013，但 requests 通过该代理仍可正常联网，因此不能
        # 根据 socket.create_connection 的结果删除这些受管代理变量。
        if port in managed_proxy_ports:
            continue
        if endpoint in unavailable_endpoints:
            continue
        try:
            with socket.create_connection(endpoint, timeout=timeout):
                continue
        except OSError:
            unavailable_endpoints.add(endpoint)

    removed_variables: list[str] = []
    for variable_name in proxy_variable_names:
        proxy_value = str(os.environ.get(variable_name) or "").strip()
        if not proxy_value:
            continue
        parsed = urlparse(proxy_value if "://" in proxy_value else f"http://{proxy_value}")
        try:
            port = int(parsed.port or 0)
        except ValueError:
            continue
        endpoint = (str(parsed.hostname or "").strip().lower(), port)
        if endpoint not in unavailable_endpoints:
            continue
        os.environ.pop(variable_name, None)
        removed_variables.append(variable_name)
    return removed_variables


def is_chrome_debug_port_available(timeout: float = 2.0) -> bool:
    """检查本机 Chrome CDP 调试端口是否可直接复用。"""
    try:
        response = requests.get(f"http://127.0.0.1:{CHROME_DEBUG_PORT}/json/version", timeout=timeout)
        response.raise_for_status()
        return True
    except Exception:
        return False


def build_browser_fetchers(
    playwright_stealth_profile: int,
    browser_render_wait_ms: int = SETTINGS.browser_render_wait_ms,
) -> tuple[tuple[str, Any], ...]:
    """按 Playwright、Chrome CDP 的固定顺序生成浏览器抓取器。"""
    playwright_fetcher = lambda target_url, timeout: fetch_by_playwright(
        target_url,
        timeout=timeout,
        stealth_profile=playwright_stealth_profile,
        render_wait_ms=browser_render_wait_ms,
    )
    chrome_fetcher = lambda target_url, timeout: fetch_by_chrome_debug(
        target_url,
        timeout=timeout,
        render_wait_ms=browser_render_wait_ms,
    )
    return (
        ("playwright", playwright_fetcher),
        ("chrome_cdp", chrome_fetcher),
    )


@dataclass
class FetchResult:
    """在线采集结果，不保存本地快照。"""

    html: str
    final_url: str
    collector: str
    warnings: list[str]
    status_code: int = 0
    content_type: str = ""
    execution_mode: str = ""
    attempted_collectors: list[str] = field(default_factory=list)


def should_retry_playwright_in_subprocess(error: Exception) -> bool:
    """仅在进程、线程或浏览器上下文故障时使用 Playwright 子进程隔离重试。"""
    text = str(error or "").lower()
    page_failure_markers = (
        "timeout",
        "timed out",
        "net::err_",
        "navigation",
        "渲染结果疑似无效",
        "html 长度过短",
        "页面包含异常标记",
    )
    if any(marker in text for marker in page_failure_markers):
        return False
    runtime_failure_markers = (
        "event loop",
        "greenlet",
        "sync api",
        "target page, context or browser has been closed",
        "browser has been closed",
        "browser closed",
        "browsertype.launch",
        "failed to launch",
        "executable doesn't exist",
        "processsingleton",
        "user data directory is already in use",
        "playwright 不可用",
        "浏览器上下文",
    )
    return any(marker in text for marker in runtime_failure_markers)


def normalize_stealth_profile(stealth_profile: int = 1) -> int:
    """规范化 Playwright 伪装档位。"""
    try:
        value = int(stealth_profile)
    except Exception:
        value = 1
    return max(1, value)


def get_browser_context_options(stealth_profile: int = 1) -> dict[str, Any]:
    """返回在线抽取和快照采集共用的浏览器上下文配置。"""
    profile = normalize_stealth_profile(stealth_profile)
    user_agent = SETTINGS.browser_user_agent
    viewport_width = SETTINGS.browser_viewport_width
    viewport_height = SETTINGS.browser_viewport_height
    if profile >= 2:
        viewport_width = 1365
        viewport_height = 768
    return {
        "user_agent": user_agent,
        "locale": SETTINGS.browser_locale,
        "timezone_id": "Asia/Shanghai",
        "color_scheme": "light",
        "reduced_motion": "no-preference",
        "device_scale_factor": SETTINGS.browser_device_scale_factor,
        "is_mobile": False,
        "has_touch": False,
        "java_script_enabled": True,
        "viewport": {
            "width": viewport_width,
            "height": viewport_height,
        },
        "screen": {
            "width": SETTINGS.browser_screen_width,
            "height": SETTINGS.browser_screen_height,
        },
        "ignore_https_errors": SETTINGS.browser_ignore_https_errors,
        "extra_http_headers": {
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-CH-UA": '"Google Chrome";v="145", "Chromium";v="145", "Not A(Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"',
        },
    }


def get_playwright_launch_args(stealth_profile: int = 1) -> list[str]:
    """返回 Playwright Chromium 启动参数，降低自动化特征。"""
    args = [
        "--disable-blink-features=AutomationControlled",
        "--lang=zh-CN",
        "--disable-infobars",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-size={SETTINGS.browser_viewport_width},{SETTINGS.browser_viewport_height}",
    ]
    if normalize_stealth_profile(stealth_profile) >= 2:
        args.extend(
            [
                "--disable-features=IsolateOrigins,site-per-process",
            ]
        )
    return args


def get_playwright_proxy_options() -> dict[str, str] | None:
    """把当前进程的标准代理变量转换为 Playwright 浏览器代理配置。"""
    proxy_value = ""
    for variable_name in (
        "HTTPS_PROXY",
        "https_proxy",
        "HTTP_PROXY",
        "http_proxy",
        "ALL_PROXY",
        "all_proxy",
    ):
        proxy_value = str(os.environ.get(variable_name) or "").strip()
        if proxy_value:
            break
    if not proxy_value:
        return None

    normalized_value = proxy_value if "://" in proxy_value else f"http://{proxy_value}"
    parsed = urlparse(normalized_value)
    hostname = str(parsed.hostname or "").strip()
    if not hostname:
        return {"server": normalized_value}

    scheme = str(parsed.scheme or "http").lower()
    if scheme == "socks5h":
        scheme = "socks5"
    display_hostname = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
    server = f"{scheme}://{display_hostname}"
    if parsed.port:
        server += f":{parsed.port}"

    options = {"server": server}
    if parsed.username:
        options["username"] = unquote(parsed.username)
    if parsed.password:
        options["password"] = unquote(parsed.password)
    bypass = str(os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or "").strip()
    if bypass:
        options["bypass"] = bypass
    return options


def add_browser_stealth_scripts(context: Any, stealth_profile: int = 1) -> None:
    """为 Playwright 页面注入轻量伪装脚本。"""
    profile = normalize_stealth_profile(stealth_profile)
    context.add_init_script(
        """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
window.chrome = window.chrome || { runtime: {} };
const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
if (originalQuery) {
  window.navigator.permissions.query = (parameters) => (
    parameters && parameters.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : originalQuery(parameters)
  );
}
"""
    )
    if profile >= 2:
        context.add_init_script(
            """
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
window.chrome = window.chrome || {};
window.chrome.app = window.chrome.app || {};
window.chrome.csi = window.chrome.csi || function () { return {}; };
window.chrome.loadTimes = window.chrome.loadTimes || function () { return {}; };
Object.defineProperty(screen, 'availWidth', { get: () => window.screen.width });
Object.defineProperty(screen, 'availHeight', { get: () => window.screen.height - 40 });
"""
        )


def block_browser_heavy_resources(context: Any) -> None:
    """禁止 Playwright 加载图片、音频、视频等非正文资源。"""
    def handle_route(route: Any) -> None:
        try:
            resource_type = str(route.request.resource_type or "").lower()
            if resource_type in BLOCKED_PLAYWRIGHT_RESOURCE_TYPES:
                route.abort()
                return
            route.continue_()
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass

    context.route("**/*", handle_route)


def configure_browser_context(context: Any, stealth_profile: int = 1) -> None:
    """统一配置 Playwright 上下文，困难站点默认保留完整资源加载。"""
    add_browser_stealth_scripts(context, stealth_profile=stealth_profile)
    if SETTINGS.browser_block_heavy_resources:
        block_browser_heavy_resources(context)


def settle_rendered_page(page: Any, wait_ms: int) -> None:
    """等待页面内容趋于稳定，避免对已就绪页面执行固定时长休眠。"""
    try:
        page.wait_for_timeout(random.randint(250, 850))
        page.mouse.move(random.randint(120, 420), random.randint(120, 360), steps=random.randint(6, 14))
        page.evaluate(
            """
() => {
  const height = Math.max(document.body.scrollHeight || 0, document.documentElement.scrollHeight || 0);
  const step = Math.min(700, Math.max(120, Math.floor(height / 3)));
  window.scrollBy({ top: step, left: 0, behavior: 'instant' });
}
"""
        )
        page.wait_for_timeout(random.randint(350, 900))
        page.evaluate("() => window.scrollTo({ top: 0, left: 0, behavior: 'instant' })")
    except Exception:
        pass

    max_wait_ms = max(0, int(wait_ms or 0))
    if max_wait_ms <= 0:
        return
    poll_interval_ms = max(100, int(SETTINGS.browser_render_poll_interval_ms or 250))
    stable_target = max(1, int(SETTINGS.browser_render_stable_samples or 1))
    minimum_wait_ms = min(max_wait_ms, max(500, poll_interval_ms * (stable_target + 1)))
    started_at = time.monotonic()
    previous_signature: tuple[int, int] | None = None
    stable_count = 0
    while True:
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        remaining_ms = max_wait_ms - elapsed_ms
        if remaining_ms <= 0:
            return
        page.wait_for_timeout(min(poll_interval_ms, remaining_ms))
        try:
            signature_value = page.evaluate(
                """
() => [
  document.documentElement ? document.documentElement.outerHTML.length : 0,
  document.body ? (document.body.innerText || '').length : 0,
]
"""
            )
            signature = (int(signature_value[0]), int(signature_value[1]))
        except Exception:
            page.wait_for_timeout(max(0, remaining_ms - poll_interval_ms))
            return
        if signature == previous_signature:
            stable_count += 1
        else:
            stable_count = 0
            previous_signature = signature
        elapsed_ms = int((time.monotonic() - started_at) * 1000)
        if elapsed_ms < minimum_wait_ms or stable_count < stable_target:
            continue
        try:
            if not rendered_html_issue(page.content()):
                return
        except Exception:
            continue


def close_playwright_pool_state(state: dict[str, Any]) -> None:
    """关闭单个 Playwright 池状态。"""
    for key in ["context", "browser", "playwright"]:
        value = state.get(key)
        if value is None:
            continue
        try:
            if key in {"context", "browser"}:
                value.close()
            else:
                value.stop()
        except Exception:
            pass
        state[key] = None


def close_thread_playwright_pool() -> None:
    """关闭当前线程持有的 Playwright 浏览器池。"""
    state = getattr(PLAYWRIGHT_THREAD_POOL, "state", None)
    if isinstance(state, dict):
        close_playwright_pool_state(state)
    PLAYWRIGHT_THREAD_POOL.state = None


def close_all_playwright_pools() -> None:
    """进程退出时尽量关闭已登记的 Playwright 浏览器。"""
    with PLAYWRIGHT_POOL_LOCK:
        states = list(PLAYWRIGHT_POOL_STATES)
        PLAYWRIGHT_POOL_STATES.clear()
    for state in states:
        close_playwright_pool_state(state)


atexit.register(close_all_playwright_pools)


def get_thread_playwright_context(
    stealth_profile: int = 1,
    url: str = "",
    timeout_seconds: int = SETTINGS.browser_timeout_seconds,
) -> Any:
    """获取当前线程、当前域名复用的临时 Playwright Context。"""
    profile = normalize_stealth_profile(stealth_profile)
    hostname = urlparse(str(url or "")).hostname or "unknown_host"
    state = getattr(PLAYWRIGHT_THREAD_POOL, "state", None)
    context = state.get("context") if isinstance(state, dict) else None
    if (
        isinstance(state, dict)
        and state.get("profile") == profile
        and state.get("hostname") == hostname
        and context is not None
    ):
        return context

    from playwright.sync_api import sync_playwright

    if isinstance(state, dict):
        close_playwright_pool_state(state)

    state = {
        "profile": profile,
        "hostname": hostname,
        "playwright": None,
        "browser": None,
        "context": None,
    }
    try:
        playwright = sync_playwright().start()
        state["playwright"] = playwright
        launch_options: dict[str, Any] = {
            "headless": SETTINGS.browser_headless,
            "args": get_playwright_launch_args(stealth_profile=profile),
            "timeout": max(1000, int(remaining_fetch_timeout(timeout_seconds) * 1000)),
        }
        proxy_options = get_playwright_proxy_options()
        if proxy_options:
            launch_options["proxy"] = proxy_options
        browser = playwright.chromium.launch(**launch_options)
        state["browser"] = browser
        context = browser.new_context(**get_browser_context_options(stealth_profile=profile))
        state["context"] = context
        configure_browser_context(context, stealth_profile=profile)
    except Exception:
        close_playwright_pool_state(state)
        raise
    PLAYWRIGHT_THREAD_POOL.state = state
    with PLAYWRIGHT_POOL_LOCK:
        PLAYWRIGHT_POOL_STATES.append(state)
    return context


def connect_chrome_debug_browser(playwright: Any, timeout: int) -> Any:
    """通过 Playwright CDP 接入本机真实 Chrome 调试端口。"""
    endpoint = f"http://127.0.0.1:{CHROME_DEBUG_PORT}"
    connect_timeout = min(
        max(1, int(timeout or 1)),
        max(1, int(SETTINGS.chrome_cdp_connect_timeout_seconds or 1)),
    )
    try:
        return playwright.chromium.connect_over_cdp(
            endpoint,
            timeout=connect_timeout * 1000,
            is_local=True,
            no_defaults=True,
        )
    except TypeError:
        return playwright.chromium.connect_over_cdp(endpoint, timeout=connect_timeout * 1000)


def build_chrome_warmup_urls(url: str) -> list[str]:
    """生成 Chrome CDP 正式访问前的同域预热地址。"""
    parsed = urlparse(str(url or ""))
    if not parsed.scheme or not parsed.netloc:
        return []
    target = str(url or "").rstrip("/")
    candidates = [
        f"{parsed.scheme}://{parsed.netloc}/",
        build_auto_referer(url),
    ]
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate or "").strip().rstrip("/")
        if not normalized or normalized == target or normalized in seen:
            continue
        seen.add(normalized)
        result.append(candidate)
    return result


def warm_up_browser_context(context: Any, url: str, timeout: int) -> list[str]:
    """预热同域首页和父级目录，让站点先写入 Cookie 与访问偏好。"""
    warnings: list[str] = []
    for warmup_url in build_chrome_warmup_urls(url):
        page = None
        try:
            page = context.new_page()
            page.goto(
                warmup_url,
                wait_until="commit",
                timeout=min(timeout * 1000, SETTINGS.chrome_warmup_timeout_ms),
            )
            page.wait_for_timeout(SETTINGS.chrome_warmup_wait_ms)
            warnings.append(f"Chrome CDP 预热成功：{warmup_url}")
        except Exception as error:
            warnings.append(f"Chrome CDP 预热失败：{warmup_url}；{error}")
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
    return warnings


def reset_chrome_warmup_cache() -> None:
    """清空 Chrome CDP 同域预热状态，主要用于浏览器重启和测试隔离。"""
    global CHROME_WARMUP_BROWSER_IDENTITY
    with CHROME_WARMUP_CACHE_LOCK:
        CHROME_WARMUP_BROWSER_IDENTITY = ""
        CHROME_WARMUP_LOCKS.clear()
        CHROME_WARMED_DOMAINS.clear()


def warm_up_chrome_context_once(
    context: Any,
    url: str,
    timeout: int,
    browser_identity: str,
    context_index: int,
) -> list[str]:
    """同一 Chrome 实例、浏览器上下文和域名仅执行一次预热。"""
    global CHROME_WARMUP_BROWSER_IDENTITY
    hostname = str(urlparse(str(url or "")).hostname or "").strip().casefold()
    if not hostname:
        return warm_up_browser_context(context, url, timeout)

    normalized_identity = str(browser_identity or "unknown_chrome").strip()
    cache_key = (normalized_identity, max(0, int(context_index)), hostname)
    with CHROME_WARMUP_CACHE_LOCK:
        if CHROME_WARMUP_BROWSER_IDENTITY != normalized_identity:
            CHROME_WARMUP_BROWSER_IDENTITY = normalized_identity
            CHROME_WARMUP_LOCKS.clear()
            CHROME_WARMED_DOMAINS.clear()
        warmup_lock = CHROME_WARMUP_LOCKS.setdefault(cache_key, threading.Lock())

    with warmup_lock:
        with CHROME_WARMUP_CACHE_LOCK:
            if cache_key in CHROME_WARMED_DOMAINS:
                return []
        warnings = warm_up_browser_context(context, url, remaining_fetch_timeout(timeout))
        with CHROME_WARMUP_CACHE_LOCK:
            CHROME_WARMED_DOMAINS.add(cache_key)
        return warnings


def open_rendered_page(context: Any, url: str, timeout: int, wait_ms: int) -> tuple[Any, str, str]:
    """打开页面并返回渲染后的 HTML 与最终 URL。"""
    timeout = remaining_fetch_timeout(timeout)
    page = context.new_page()
    try:
        page.goto(
            url,
            wait_until="commit",
            timeout=min(timeout * 1000, SETTINGS.browser_commit_timeout_ms),
        )
        try:
            page.wait_for_load_state(
                "domcontentloaded",
                timeout=min(timeout * 1000, SETTINGS.browser_domcontentloaded_timeout_ms),
            )
        except Exception:
            pass
        settle_rendered_page(page, wait_ms)
        html = page.content()
        if rendered_html_issue(html):
            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=min(timeout * 1000, SETTINGS.browser_networkidle_timeout_ms),
                )
            except Exception:
                pass
            page.wait_for_timeout(min(max(0, int(wait_ms or 0)), 1000))
            html = page.content()
        return page, html, page.url
    except Exception:
        try:
            page.close()
        except Exception:
            pass
        raise


def open_chrome_page_with_fallback(
    context: Any,
    url: str,
    timeout: int,
    wait_ms: int,
    browser_identity: str,
    context_index: int,
) -> tuple[Any, str, str, list[str]]:
    """Chrome先直达目标页；仅在失败或内容无效时执行同域预热并重试。"""
    warnings: list[str] = []
    first_page = None
    try:
        first_page, html, final_url = open_rendered_page(context, url, timeout, wait_ms)
        issue = rendered_html_issue(html)
        if not issue:
            return first_page, html, final_url, warnings
        warnings.append(f"Chrome CDP 首次直达内容无效：{issue}")
    except Exception as error:
        warnings.append(f"Chrome CDP 首次直达失败：{error}")
    if first_page is not None:
        try:
            first_page.close()
        except Exception:
            pass

    warnings.extend(
        warm_up_chrome_context_once(
            context,
            url,
            timeout,
            browser_identity=browser_identity,
            context_index=context_index,
        )
    )
    page, html, final_url = open_rendered_page(context, url, timeout, wait_ms)
    issue = rendered_html_issue(html)
    if issue:
        try:
            page.close()
        except Exception:
            pass
        raise RuntimeError(f"Chrome CDP 预热后渲染结果仍无效：{issue}")
    return page, html, final_url, warnings


def fetch_online_html(url: str, timeout: int = SETTINGS.request_timeout_seconds) -> tuple[str, str]:
    """在线实时采集网页 HTML。"""
    result = fetch_online_html_with_fallback(url, timeout=timeout)
    return result.html, result.final_url


def is_suspicious_html(html: str) -> str:
    """判断静态 HTML 是否疑似不可用。"""
    text = str(html or "")
    if len(text) < SETTINGS.suspicious_html_min_length:
        return f"HTML 长度过短：{len(text)}"
    matched_markers = [marker for marker in BAD_PAGE_MARKERS if marker in text]
    if not matched_markers:
        return ""
    try:
        visible_text = extract_visible_page_text(text)
    except Exception:
        visible_text = text
    for marker in matched_markers:
        if marker in visible_text:
            return f"页面包含异常标记：{marker}"
    return ""


def extract_visible_page_text(html: str) -> str:
    """提取页面可见文本，排除注释、脚本、模板和明确隐藏节点。"""
    soup = BeautifulSoup(str(html or ""), "html.parser")
    for comment in soup.find_all(string=lambda item: isinstance(item, Comment)):
        comment.extract()
    for tag in soup.find_all(["script", "style", "template", "noscript"]):
        tag.decompose()

    hidden_tags = []
    for tag in soup.find_all(True):
        aria_hidden = str(tag.get("aria-hidden") or "").strip().lower()
        style = str(tag.get("style") or "")
        if tag.has_attr("hidden") or aria_hidden == "true" or re.search(
            r"(?:display\s*:\s*none|visibility\s*:\s*hidden)",
            style,
            flags=re.IGNORECASE,
        ):
            hidden_tags.append(tag)
    for tag in reversed(hidden_tags):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def normalize_executable_path(value: str) -> str:
    """规范化解释器路径，便于判断当前环境是否为项目指定环境。"""
    try:
        return str(Path(value).resolve()).casefold()
    except Exception:
        return str(value or "").casefold()


def resolve_python_executable() -> str:
    """优先使用显式配置，否则继承当前 uv 项目进程的解释器。"""
    configured_python = str(SETTINGS.python_exe or "").strip()
    return configured_python or sys.executable


def is_configured_python() -> bool:
    """判断当前进程是否已经运行在项目配置的 Python 环境中。"""
    configured_python = str(SETTINGS.python_exe or "").strip()
    if not configured_python:
        return True
    return normalize_executable_path(sys.executable) == normalize_executable_path(configured_python)


def looks_like_valid_rendered_html(html: str) -> bool:
    """判断浏览器渲染结果是否达到可解析的基本质量。"""
    text = str(html or "")
    if is_suspicious_html(text):
        return False
    lowered = text.lower()
    if "<html" not in lowered or "</html" not in lowered:
        return False
    return True


def rendered_html_issue(html: str) -> str:
    """返回浏览器渲染结果的质量问题描述。"""
    suspicious_reason = is_suspicious_html(html)
    if suspicious_reason:
        return suspicious_reason
    lowered = str(html or "").lower()
    if "<html" not in lowered or "</html" not in lowered:
        return "HTML 结构不完整"
    return ""


def classify_request_error(error: Exception) -> str:
    """将 requests 异常归入稳定类别，便于日志和汇总检索。"""
    if isinstance(error, requests.exceptions.Timeout):
        return "timeout"
    if isinstance(error, requests.exceptions.SSLError):
        return "ssl"
    if isinstance(error, requests.exceptions.ProxyError):
        return "proxy"
    if isinstance(error, requests.exceptions.ConnectionError):
        return "connection"
    if isinstance(error, requests.exceptions.HTTPError):
        response = getattr(error, "response", None)
        status_code = getattr(response, "status_code", "")
        return f"http_{status_code}" if status_code else "http"
    return error.__class__.__name__


def sleep_before_retry(
    attempt: int,
    base_seconds: float = SETTINGS.retry_base_sleep_seconds,
    max_seconds: float = SETTINGS.retry_max_sleep_seconds,
) -> None:
    """按指数退避和随机抖动等待，降低短时封控或瞬时网络波动影响。"""
    delay = min(max_seconds, base_seconds * (2 ** max(0, attempt - 1)))
    time.sleep(delay + random.uniform(0, 0.8))


def build_auto_referer(url: str) -> str:
    """根据目标 URL 自动生成保守 Referer。"""
    parsed = urlparse(str(url or ""))
    if not parsed.scheme or not parsed.netloc:
        return ""
    origin = f"{parsed.scheme}://{parsed.netloc}/"
    path = parsed.path or "/"
    if path == "/":
        return origin
    parent_path = path.rsplit("/", 1)[0].strip("/")
    if not parent_path:
        return origin
    return f"{parsed.scheme}://{parsed.netloc}/{parent_path}/"


def select_requests_user_agent(url: str, attempt: int = 1) -> str:
    """为 requests 选择桌面浏览器 UA，重试时稳定轮换。"""
    pool = REQUESTS_USER_AGENT_POOL or (SETTINGS.browser_user_agent,)
    parsed = urlparse(str(url or ""))
    domain_seed = sum(ord(char) for char in parsed.netloc)
    index = (domain_seed + max(0, attempt - 1)) % len(pool)
    return pool[index]


def build_requests_headers(url: str, attempt: int = 1, referer: str = "") -> dict[str, str]:
    """构造单次 requests 请求头。"""
    headers = dict(DEFAULT_HEADERS)
    profile = REQUESTS_HEADER_PROFILES[(max(1, attempt) - 1) % len(REQUESTS_HEADER_PROFILES)]
    headers.update(profile)
    headers["User-Agent"] = select_requests_user_agent(url, attempt)
    effective_referer = str(referer or "").strip() or build_auto_referer(url)
    if effective_referer:
        headers["Referer"] = effective_referer
    return headers


def normalize_encoding_label(value: str) -> str:
    """规范化常见中文网页编码名称。"""
    encoding = str(value or "").strip().strip("\"'").lower()
    if encoding in {"gb2312", "gbk", "gb_2312", "gb-2312"}:
        return "gb18030"
    if encoding in {"utf8", "utf_8"}:
        return "utf-8"
    return encoding


def extract_header_charset(response: requests.Response) -> str:
    """从 Content-Type 中读取 charset。"""
    content_type = str(response.headers.get("Content-Type", ""))
    match = HEADER_CHARSET_PATTERN.search(content_type)
    if not match:
        return ""
    return normalize_encoding_label(match.group(1))


def extract_meta_charset(content: bytes) -> str:
    """从 HTML meta 标签中读取 charset。"""
    head = bytes(content or b"")[:8192]
    for pattern in (META_CHARSET_PATTERN, META_HTTP_EQUIV_CHARSET_PATTERN):
        match = pattern.search(head)
        if match:
            try:
                return normalize_encoding_label(match.group(1).decode("ascii", errors="ignore"))
            except Exception:
                return ""
    return ""


def iter_response_encoding_candidates(response: requests.Response) -> list[str]:
    """按可信度返回响应编码候选。"""
    candidates = [
        extract_header_charset(response),
        extract_meta_charset(response.content),
        normalize_encoding_label(response.apparent_encoding or ""),
        normalize_encoding_label(response.encoding or ""),
        "utf-8",
        "gb18030",
    ]
    result: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        result.append(candidate)
    return result


def decode_response_text(response: requests.Response) -> str:
    """统一响应编码处理，兼容旧站 GBK/GB2312/UTF-8 混乱。"""
    content = response.content
    for encoding in iter_response_encoding_candidates(response):
        try:
            text = content.decode(encoding, errors="replace")
        except LookupError:
            continue
        if "\ufffd" not in text:
            response.encoding = encoding
            return text
    fallback_encoding = iter_response_encoding_candidates(response)[0] if iter_response_encoding_candidates(response) else "utf-8"
    response.encoding = fallback_encoding
    return content.decode(fallback_encoding, errors="replace")


def requests_get_html(url: str, timeout: int, verify: bool, attempt: int = 1, referer: str = "") -> requests.Response:
    """统一执行HTML请求；环境代理连接失败时自动改用不读取代理变量的直连会话。"""
    ensure_domain_circuit_closed(url)
    request_kwargs = {
        "timeout": build_requests_timeout(timeout),
        "verify": verify,
        "headers": build_requests_headers(url, attempt=attempt, referer=referer),
    }
    try:
        try:
            response = REQUESTS_SESSION.get(url, **request_kwargs)
        except requests.exceptions.ProxyError:
            response = DIRECT_REQUESTS_SESSION.get(url, **request_kwargs)
    except requests.exceptions.RequestException as error:
        record_domain_request_failure(url, error)
        raise
    record_domain_request_success(url)
    return response


def should_retry_request_error(error: requests.exceptions.RequestException, attempt: int, max_retries: int) -> bool:
    """只重试可能恢复的HTTP异常，确定性状态码和DNS错误立即结束。"""
    if attempt >= max_retries or is_name_resolution_error(error):
        return False
    if isinstance(error, requests.exceptions.HTTPError):
        response = getattr(error, "response", None)
        status_code = int(getattr(response, "status_code", 0) or 0)
        return status_code in SETTINGS.retryable_status_codes
    return isinstance(
        error,
        (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.ChunkedEncodingError,
        ),
    )


def extract_javascript_location_redirect(html: str) -> str:
    """提取政府站常见的 location.href 短页跳转地址。"""
    match = re.search(
        r"(?:window\.)?location(?:\.href)?\s*=\s*['\"](?P<url>[^'\"]+)['\"]",
        str(html or ""),
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return match.group("url").strip()


def fetch_by_requests(
    url: str,
    timeout: int = SETTINGS.request_timeout_seconds,
    max_retries: int = SETTINGS.request_max_retries,
    attempt_offset: int = 0,
    referer: str = "",
) -> FetchResult:
    """使用 requests 在线采集，包含会话复用、可控重试和 SSL 降级。"""
    warnings: list[str] = []
    verify = True
    last_error: Exception | None = None
    safe_attempt_offset = max(0, int(attempt_offset or 0))
    for attempt in range(1, max_retries + 1):
        effective_attempt = safe_attempt_offset + attempt
        try:
            response = requests_get_html(
                url,
                timeout=remaining_fetch_timeout(timeout),
                verify=verify,
                attempt=effective_attempt,
                referer=referer,
            )
            if response.status_code in SETTINGS.retryable_status_codes and attempt < max_retries:
                warnings.append(f"requests 第 {attempt} 次响应状态码 {response.status_code}，切换请求头后重试")
                sleep_before_retry(attempt)
                continue
            response.raise_for_status()
            html = decode_response_text(response)
            for redirect_index in range(3):
                redirect_href = extract_javascript_location_redirect(html)
                if not redirect_href:
                    break
                redirect_url = urljoin(response.url, redirect_href)
                if redirect_url == response.url:
                    break
                warnings.append(f"requests 跟随脚本跳转 {redirect_index + 1}：{redirect_url}")
                response = requests_get_html(
                    redirect_url,
                    timeout=remaining_fetch_timeout(timeout),
                    verify=verify,
                    attempt=effective_attempt,
                    referer=response.url,
                )
                response.raise_for_status()
                html = decode_response_text(response)
            return FetchResult(
                html=html,
                final_url=response.url,
                collector="requests",
                warnings=warnings,
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                attempted_collectors=["requests:成功"],
            )
        except requests.exceptions.SSLError as error:
            last_error = error
            if verify:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                verify = False
                warnings.append(f"requests SSL 证书校验失败，改用 verify=False 重试：{error}")
                sleep_before_retry(attempt)
                continue
            warnings.append(f"requests 第 {attempt} 次失败[{classify_request_error(error)}]：{error}")
            if not should_retry_request_error(error, attempt, max_retries):
                break
        except requests.exceptions.RequestException as error:
            last_error = error
            warnings.append(f"requests 第 {attempt} 次失败[{classify_request_error(error)}]：{error}")
            if not should_retry_request_error(error, attempt, max_retries):
                break
        if attempt < max_retries:
            sleep_before_retry(attempt)
    if last_error:
        raise RuntimeError("；".join(warnings)) from last_error
    raise RuntimeError("requests 采集失败")


def fetch_by_raw_requests(
    url: str,
    timeout: int = SETTINGS.request_timeout_seconds,
    max_retries: int = SETTINGS.request_max_retries,
    attempt_offset: int = 0,
    referer: str = "",
) -> FetchResult:
    """仅使用 requests 采集原始 HTML，不跟随脚本跳转、不降级浏览器。"""
    warnings: list[str] = []
    verify = True
    last_error: Exception | None = None
    safe_attempt_offset = max(0, int(attempt_offset or 0))
    for attempt in range(1, max_retries + 1):
        effective_attempt = safe_attempt_offset + attempt
        try:
            response = requests_get_html(
                url,
                timeout=remaining_fetch_timeout(timeout),
                verify=verify,
                attempt=effective_attempt,
                referer=referer,
            )
            if response.status_code in SETTINGS.retryable_status_codes and attempt < max_retries:
                warnings.append(f"raw_http 第 {attempt} 次响应状态码 {response.status_code}，切换请求头后重试")
                sleep_before_retry(attempt)
                continue
            response.raise_for_status()
            html = decode_response_text(response)
            return FetchResult(
                html=html,
                final_url=response.url,
                collector="raw_http",
                warnings=warnings,
                status_code=response.status_code,
                content_type=response.headers.get("Content-Type", ""),
                attempted_collectors=["raw_http:成功"],
            )
        except requests.exceptions.SSLError as error:
            last_error = error
            if verify:
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                verify = False
                warnings.append(f"raw_http SSL 证书校验失败，改用 verify=False 重试：{error}")
                sleep_before_retry(attempt)
                continue
            warnings.append(f"raw_http 第 {attempt} 次失败[{classify_request_error(error)}]：{error}")
            if not should_retry_request_error(error, attempt, max_retries):
                break
        except requests.exceptions.RequestException as error:
            last_error = error
            warnings.append(f"raw_http 第 {attempt} 次失败[{classify_request_error(error)}]：{error}")
            if not should_retry_request_error(error, attempt, max_retries):
                break
        if attempt < max_retries:
            sleep_before_retry(attempt)
    if last_error:
        raise RuntimeError("；".join(warnings)) from last_error
    raise RuntimeError("raw_http 采集失败")


def fetch_by_playwright(
    url: str,
    timeout: int = SETTINGS.browser_timeout_seconds,
    stealth_profile: int = 1,
    render_wait_ms: int = SETTINGS.browser_render_wait_ms,
) -> FetchResult:
    """使用 Playwright 临时浏览器上下文在线采集。"""
    timeout = remaining_fetch_timeout(timeout)
    direct_errors: list[str] = []
    direct_attempts: list[str] = []
    if not is_configured_python():
        return fetch_by_playwright_subprocess(
            url,
            timeout=timeout,
            prior_errors=direct_errors,
            prior_attempts=direct_attempts,
            stealth_profile=stealth_profile,
            render_wait_ms=render_wait_ms,
        )
    try:
        __import__("playwright.sync_api")
    except Exception as error:
        direct_errors.append(f"Playwright 不可用：{error}")
        direct_attempts.append("playwright(in_process):环境不可用")
        return fetch_by_playwright_subprocess(
            url,
            timeout=timeout,
            prior_errors=direct_errors,
            prior_attempts=direct_attempts,
            stealth_profile=stealth_profile,
            render_wait_ms=render_wait_ms,
        )
    try:
        context = get_thread_playwright_context(
            stealth_profile=stealth_profile,
            url=url,
            timeout_seconds=timeout,
        )
        page = None
        try:
            page, html, final_url = open_rendered_page(context, url, timeout, render_wait_ms)
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
        issue = rendered_html_issue(html)
        if issue:
            raise RuntimeError(f"Playwright 渲染结果疑似无效：{issue}")
        return FetchResult(
            html,
            final_url,
            "playwright",
            [],
            execution_mode="in_process",
            attempted_collectors=["playwright(in_process):成功"],
        )
    except Exception as error:
        close_thread_playwright_pool()
        direct_errors.append(f"Playwright 直接抓取失败：{error}")
        direct_attempts.append("playwright(in_process):失败")
        if not should_retry_playwright_in_subprocess(error):
            raise RuntimeError("；".join(direct_errors)) from error
        return fetch_by_playwright_subprocess(
            url,
            timeout=timeout,
            prior_errors=direct_errors,
            prior_attempts=direct_attempts,
            stealth_profile=stealth_profile,
            render_wait_ms=render_wait_ms,
        )


def fetch_by_playwright_subprocess(
    url: str,
    timeout: int = SETTINGS.browser_timeout_seconds,
    prior_errors: list[str] | None = None,
    prior_attempts: list[str] | None = None,
    stealth_profile: int = 1,
    render_wait_ms: int = SETTINGS.browser_render_wait_ms,
) -> FetchResult:
    """使用当前 uv 项目环境隔离执行 Playwright 抓取。"""
    timeout = remaining_fetch_timeout(timeout)
    python_exe = resolve_python_executable()
    warnings = list(prior_errors or [])
    attempts = list(prior_attempts or [])
    if not Path(python_exe).is_file():
        raise RuntimeError(f"Playwright 子进程不可用：解释器不存在 {python_exe}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_DIR)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    command = [
        python_exe,
        "-m",
        "crawler_core.playwright_fetch_helper",
        "--url",
        url,
        "--timeout",
        str(timeout),
        "--wait-ms",
        str(max(0, int(render_wait_ms))),
        "--stealth-profile",
        str(normalize_stealth_profile(stealth_profile)),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(PROJECT_DIR),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=remaining_fetch_timeout(timeout + 20),
            env=env,
        )
    except Exception as error:
        raise RuntimeError(f"Playwright 子进程启动失败：{error}") from error
    stdout = str(result.stdout or "").strip()
    stderr = str(result.stderr or "").strip()
    if result.returncode != 0:
        detail = "；".join(part for part in [*warnings, stderr, stdout] if part)
        raise RuntimeError(f"Playwright 子进程失败：{detail or result.returncode}")
    try:
        payload = json.loads(stdout)
    except Exception as error:
        detail = "；".join(part for part in [*warnings, stderr, stdout[:500]] if part)
        raise RuntimeError(f"Playwright 子进程输出无法解析：{detail}") from error
    html = str(payload.get("html", ""))
    final_url = str(payload.get("final_url") or url)
    child_warnings = [str(item) for item in payload.get("warnings", []) if str(item)]
    issue = rendered_html_issue(html)
    if issue:
        raise RuntimeError(f"Playwright 子进程渲染结果疑似无效：{issue}")
    attempts.append("playwright(subprocess):成功")
    return FetchResult(
        html,
        final_url,
        "playwright",
        warnings + child_warnings,
        execution_mode="subprocess",
        attempted_collectors=attempts,
    )


def fetch_by_chrome_debug(
    url: str,
    timeout: int = SETTINGS.browser_timeout_seconds,
    render_wait_ms: int = SETTINGS.browser_render_wait_ms,
) -> FetchResult:
    """通过本机 Chrome 调试端口在线采集，优先复用人工 Chrome 状态。"""
    timeout = remaining_fetch_timeout(timeout)
    warnings: list[str] = []

    def read_chrome_debug_identity(response: requests.Response) -> str:
        """读取本次 Chrome 实例的稳定标识，浏览器重启后会随之变化。"""
        try:
            payload = response.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return str(payload.get("webSocketDebuggerUrl") or f"127.0.0.1:{CHROME_DEBUG_PORT}")

    def ensure_chrome_debug_server() -> tuple[str, str]:
        """确保本机 Chrome 调试端口可用。"""
        try:
            response = requests.get(f"http://127.0.0.1:{CHROME_DEBUG_PORT}/json/version", timeout=3)
            response.raise_for_status()
            return "existing_debug_port", read_chrome_debug_identity(response)
        except Exception:
            pass
        creation_flags = 0
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            creation_flags |= subprocess.CREATE_NO_WINDOW
        if hasattr(subprocess, "DETACHED_PROCESS"):
            creation_flags |= subprocess.DETACHED_PROCESS
        subprocess.Popen(
            [
                CHROME_EXE_PATH,
                f"--remote-debugging-port={CHROME_DEBUG_PORT}",
                f"--user-data-dir={CHROME_USER_DATA_DIR}",
                "--lang=zh-CN",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check",
                f"--window-size={SETTINGS.browser_viewport_width},{SETTINGS.browser_viewport_height}",
                f"--user-agent={SETTINGS.browser_user_agent}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        deadline = time.time() + min(timeout, 30)
        while time.time() < deadline:
            try:
                response = requests.get(f"http://127.0.0.1:{CHROME_DEBUG_PORT}/json/version", timeout=3)
                response.raise_for_status()
                return "launched_project_profile", read_chrome_debug_identity(response)
            except Exception:
                time.sleep(0.5)
        raise RuntimeError(f"Chrome 调试端口启动超时：{CHROME_DEBUG_PORT}")

    try:
        chrome_debug_source, browser_identity = ensure_chrome_debug_server()
        warnings.append(f"Chrome CDP 来源：{chrome_debug_source}")
    except Exception as error:
        raise RuntimeError(f"Chrome 调试端口不可用：{error}") from error

    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        raise RuntimeError(f"Playwright CDP 不可用：{error}") from error

    with sync_playwright() as playwright:
        browser = connect_chrome_debug_browser(playwright, timeout=timeout)
        page = None
        try:
            if browser.contexts:
                context = browser.contexts[0]
                context_index = 0
            else:
                context = browser.new_context(**get_browser_context_options(stealth_profile=1))
                configure_browser_context(context, stealth_profile=1)
                context_index = len(browser.contexts) - 1
            page, html, final_url, page_warnings = open_chrome_page_with_fallback(
                context,
                url,
                timeout,
                render_wait_ms,
                browser_identity=browser_identity,
                context_index=context_index,
            )
            warnings.extend(page_warnings)
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass
    issue = rendered_html_issue(html)
    if issue:
        raise RuntimeError(f"Chrome 调试端口渲染结果疑似无效：{issue}")
    return FetchResult(
        html,
        final_url,
        "chrome_cdp",
        warnings,
        attempted_collectors=["chrome_cdp:成功"],
    )


def fetch_many_by_chrome_debug(
    urls: list[str],
    timeout: int = SETTINGS.browser_timeout_seconds,
    max_workers: int = 2,
) -> list[FetchResult]:
    """以受控线程数并发采集同域详情页，并严格保持输入顺序。"""
    normalized_urls = [str(url or "").strip() for url in urls]
    if not normalized_urls or any(not url for url in normalized_urls):
        raise ValueError("Chrome CDP 批量采集网址不能为空")
    worker_count = min(len(normalized_urls), max(1, min(int(max_workers or 1), 4)))
    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="chrome-detail",
    ) as executor:
        return list(
            executor.map(
                lambda target_url: fetch_by_chrome_debug(target_url, timeout=timeout),
                normalized_urls,
            )
        )


def fetch_by_chrome_debug_subprocess(
    url: str,
    timeout: int = SETTINGS.browser_timeout_seconds,
) -> FetchResult:
    """在隔离子进程中使用 Chrome CDP，避免嵌套同步 Playwright 冲突。"""
    timeout = remaining_fetch_timeout(timeout)
    python_exe = resolve_python_executable()
    if not Path(python_exe).is_file():
        raise RuntimeError(f"Chrome CDP 子进程不可用：解释器不存在 {python_exe}")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_DIR)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    command = [
        python_exe,
        "-m",
        "crawler_core.chrome_fetch_helper",
        "--url",
        url,
        "--timeout",
        str(timeout),
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(PROJECT_DIR),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=remaining_fetch_timeout(timeout + 20),
            env=env,
        )
    except Exception as error:
        raise RuntimeError(f"Chrome CDP 子进程启动失败：{error}") from error

    stdout = str(result.stdout or "").strip()
    stderr = str(result.stderr or "").strip()
    if result.returncode != 0:
        detail = "；".join(part for part in [stderr, stdout] if part)
        raise RuntimeError(f"Chrome CDP 子进程失败：{detail or result.returncode}")
    try:
        payload = json.loads(stdout)
    except Exception as error:
        detail = "；".join(part for part in [stderr, stdout[:500]] if part)
        raise RuntimeError(f"Chrome CDP 子进程输出无法解析：{detail}") from error

    html = str(payload.get("html", ""))
    final_url = str(payload.get("final_url") or url)
    warnings = [str(item) for item in payload.get("warnings", []) if str(item)]
    issue = rendered_html_issue(html)
    if issue:
        raise RuntimeError(f"Chrome CDP 子进程渲染结果疑似无效：{issue}")
    return FetchResult(
        html,
        final_url,
        "chrome_cdp",
        warnings,
        execution_mode="subprocess",
        attempted_collectors=["chrome_cdp(subprocess):成功"],
    )


def fetch_online_html_with_fallback(
    url: str,
    timeout: int = SETTINGS.request_timeout_seconds,
    force_browser: bool = False,
    request_attempt_offset: int = 0,
    playwright_stealth_profile: int = 1,
    browser_render_wait_ms: int = SETTINGS.browser_render_wait_ms,
) -> FetchResult:
    """在线采集 HTML；按 requests -> Playwright -> Chrome 调试端口依次降级。"""
    warnings: list[str] = []
    attempted_collectors: list[str] = []
    try:
        result = fetch_by_requests(url, timeout=timeout, attempt_offset=request_attempt_offset)
        suspicious_reason = is_suspicious_html(result.html)
        if not force_browser and not suspicious_reason:
            return result
        if suspicious_reason:
            warnings.append(f"requests 疑似无效：{suspicious_reason}")
            attempted_collectors.append("requests:疑似无效")
        if force_browser:
            warnings.append("规则要求浏览器复核：force_browser=True")
            if not attempted_collectors:
                attempted_collectors.append("requests:需浏览器复核")
    except Exception as error:
        warnings.append(f"requests 失败：{error}")
        attempted_collectors.append("requests:失败")
    browser_fetchers = build_browser_fetchers(
        playwright_stealth_profile,
        browser_render_wait_ms=browser_render_wait_ms,
    )
    for collector_name, fetcher in browser_fetchers:
        try:
            result = fetcher(url, timeout=timeout)
            issue = rendered_html_issue(result.html)
            if issue:
                warnings.append(f"{result.collector} 疑似无效：{issue}")
                attempted_collectors.append(f"{collector_name}:疑似无效")
                continue
            result.warnings = warnings + result.warnings
            result.attempted_collectors = attempted_collectors + result.attempted_collectors
            return result
        except Exception as error:
            warnings.append(str(error))
            attempted_collectors.append(f"{collector_name}:失败")
    raise RuntimeError("；".join(warnings) or "在线采集失败")


def fetch_browser_html_with_fallback(
    url: str,
    timeout: int = SETTINGS.browser_timeout_seconds,
    playwright_stealth_profile: int = 1,
    browser_render_wait_ms: int = SETTINGS.browser_render_wait_ms,
) -> FetchResult:
    """在线采集渲染后 HTML；按 Playwright -> Chrome 调试端口依次降级。"""
    warnings: list[str] = []
    attempted_collectors: list[str] = []
    browser_fetchers = build_browser_fetchers(
        playwright_stealth_profile,
        browser_render_wait_ms=browser_render_wait_ms,
    )
    for collector_name, fetcher in browser_fetchers:
        try:
            result = fetcher(url, timeout=timeout)
            issue = rendered_html_issue(result.html)
            if issue:
                warnings.append(f"{result.collector} 疑似无效：{issue}")
                attempted_collectors.append(f"{collector_name}:疑似无效")
                continue
            result.warnings = warnings + result.warnings
            result.attempted_collectors = attempted_collectors + result.attempted_collectors
            return result
        except Exception as error:
            warnings.append(str(error))
            attempted_collectors.append(f"{collector_name}:失败")
    raise RuntimeError("；".join(warnings) or "浏览器采集失败")


def fetch_html_with_strategy(
    url: str,
    strategy: str,
    force_browser: bool = False,
    timeout: int | None = None,
    request_attempt_offset: int = 0,
    playwright_stealth_profile: int = 1,
    referer: str = "",
    browser_render_wait_ms: int = SETTINGS.browser_render_wait_ms,
) -> FetchResult:
    """按统一网络配置执行指定采集策略。"""
    mode = str(strategy or "extract").strip().lower()
    if mode in {"extract", "online"}:
        timeout_seconds = SETTINGS.request_timeout_seconds if timeout is None else timeout
        return fetch_online_html_with_fallback(
            url,
            timeout=timeout_seconds,
            force_browser=force_browser,
            request_attempt_offset=request_attempt_offset,
            playwright_stealth_profile=playwright_stealth_profile,
            browser_render_wait_ms=browser_render_wait_ms,
        )
    if mode in {"snapshot", "browser"}:
        timeout_seconds = SETTINGS.browser_timeout_seconds if timeout is None else timeout
        return fetch_browser_html_with_fallback(
            url,
            timeout=timeout_seconds,
            playwright_stealth_profile=playwright_stealth_profile,
            browser_render_wait_ms=browser_render_wait_ms,
        )
    if mode in {"requests", "request"}:
        timeout_seconds = SETTINGS.request_timeout_seconds if timeout is None else timeout
        return fetch_by_requests(
            url,
            timeout=timeout_seconds,
            attempt_offset=request_attempt_offset,
            referer=referer,
        )
    if mode == "playwright":
        timeout_seconds = SETTINGS.browser_timeout_seconds if timeout is None else timeout
        return fetch_by_playwright(
            url,
            timeout=timeout_seconds,
            stealth_profile=playwright_stealth_profile,
            render_wait_ms=browser_render_wait_ms,
        )
    if mode in {"chrome", "chrome_cdp"}:
        timeout_seconds = SETTINGS.browser_timeout_seconds if timeout is None else timeout
        return fetch_by_chrome_debug(
            url,
            timeout=timeout_seconds,
            render_wait_ms=browser_render_wait_ms,
        )
    if mode == "raw_http":
        timeout_seconds = SETTINGS.request_timeout_seconds if timeout is None else timeout
        return fetch_by_raw_requests(
            url,
            timeout=timeout_seconds,
            attempt_offset=request_attempt_offset,
            referer=referer,
        )
    raise ValueError(f"未知采集策略：{strategy}")


def fetch_html_with_preferred_fallback(
    url: str,
    preferred_strategy: str,
    timeout: int | None = None,
    request_attempt_offset: int = 0,
    playwright_stealth_profile: int = 1,
    browser_render_wait_ms: int = SETTINGS.browser_render_wait_ms,
) -> FetchResult:
    """先尝试历史成功采集器，失败后继续其余在线降级链路。"""
    normalized_preference = str(preferred_strategy or "").strip().lower()
    aliases = {"request": "requests", "chrome_cdp": "chrome"}
    normalized_preference = aliases.get(normalized_preference, normalized_preference)
    supported_modes = ("raw_http", "requests", "playwright", "chrome")
    ordered_modes = [normalized_preference] if normalized_preference in supported_modes else []
    ordered_modes.extend(mode for mode in supported_modes if mode not in ordered_modes)

    warnings: list[str] = []
    attempted_collectors: list[str] = []
    for mode in ordered_modes:
        collector_label = "chrome_cdp" if mode == "chrome" else mode
        try:
            result = fetch_html_with_strategy(
                url,
                strategy=mode,
                timeout=timeout,
                request_attempt_offset=request_attempt_offset,
                playwright_stealth_profile=playwright_stealth_profile,
                browser_render_wait_ms=browser_render_wait_ms,
            )
            if mode in {"playwright", "chrome"}:
                issue = rendered_html_issue(result.html)
            else:
                issue = is_suspicious_html(result.html)
            if issue:
                warnings.append(f"{collector_label} 疑似无效：{issue}")
                attempted_collectors.append(f"{collector_label}:疑似无效")
                continue
            result.warnings = warnings + result.warnings
            result.attempted_collectors = attempted_collectors + result.attempted_collectors
            return result
        except Exception as error:
            warnings.append(f"{collector_label} 失败：{error}")
            attempted_collectors.append(f"{collector_label}:失败")
    raise RuntimeError("；".join(warnings) or "在线采集失败")
