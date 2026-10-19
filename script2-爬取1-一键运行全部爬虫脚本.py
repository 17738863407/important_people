from __future__ import annotations

import ast
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import inspect
import multiprocessing
import os
import queue
import re
import runpy
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from crawler_core.exporter import OUTPUT_FIELDS
from crawler_core.fetch_memory import (
    FetchMemoryRecord,
    load_fetch_memory,
    merge_fetch_memory_records,
    migrate_fetch_memory,
    normalize_actual_collector,
    preferred_fetch_mode,
    write_fetch_memory,
)
from crawler_core.paths import resolve_path_argument, timestamped_output_path
from crawler_core.rule_table import normalize_script_sequence


@dataclass
class OutputQuality:
    """单页输出文件的质量摘要。"""

    output_path: str = ""
    row_count: int = 0
    complete_count: int = 0
    failure_record_count: int = 0
    issue: str = ""


@dataclass
class ScriptRunResult:
    """单个页面脚本运行结果。"""

    success: bool
    message: str
    failure_category: str
    elapsed_seconds: float
    quality: OutputQuality
    script_name: str = ""
    organization: str = ""
    url: str = ""
    round_index: int = 0
    fetch_mode: str = ""
    actual_collector: str = ""
    execution_mode: str = ""
    attempted_collectors: list[str] | None = None


@dataclass(frozen=True)
class FailureTransition:
    """一次失败后的有向降级决策。"""

    terminal: bool
    allowed_modes: tuple[str, ...]
    reason: str


@dataclass
class ScriptMetadata:
    """页面脚本的基础信息，用于日志和报告定位。"""

    script_name: str
    script_sequence: str = ""
    organization: str = ""
    url: str = ""


@dataclass
class OutputOrganizationSummary:
    """输出结果分类摘要。"""

    success_dir: Path
    failure_dir: Path
    success_count: int = 0
    failure_count: int = 0
    move_failed_count: int = 0
    recycled_stale_count: int = 0


class DomainThrottle:
    """控制同一域名脚本串行运行，并在相邻任务之间保留间隔。"""

    def __init__(self, interval_seconds: float, backoff_seconds: dict[str, float] | None = None) -> None:
        self.interval_seconds = max(0.0, float(interval_seconds or 0.0))
        self.backoff_seconds = {
            str(key).strip().lower(): max(0.0, float(value or 0.0))
            for key, value in (backoff_seconds or {}).items()
        }
        self._global_lock = threading.Lock()
        self._domain_locks: dict[str, threading.Lock] = {}
        self._last_finished_at: dict[str, float] = {}
        self._next_interval_seconds: dict[str, float] = {}

    def _get_domain_lock(self, domain_key: str) -> threading.Lock:
        with self._global_lock:
            if domain_key not in self._domain_locks:
                self._domain_locks[domain_key] = threading.Lock()
            return self._domain_locks[domain_key]

    def _resolve_next_interval(self, result: object, base_interval_seconds: float) -> float:
        """根据本次失败特征计算同域名下一次请求前的动态冷却时间。"""
        run_result = result[0] if isinstance(result, tuple) and result else result
        if bool(getattr(run_result, "success", False)):
            return base_interval_seconds
        message = str(getattr(run_result, "message", "") or "").lower()
        if "429" in message or "too many requests" in message:
            return max(base_interval_seconds, self.backoff_seconds.get("429", 30.0))
        if "403" in message or "forbidden" in message:
            return max(base_interval_seconds, self.backoff_seconds.get("403", 15.0))
        connection_markers = (
            "connection reset",
            "connection aborted",
            "远程主机强迫关闭",
            "连接被重置",
        )
        if any(marker in message for marker in connection_markers):
            return max(base_interval_seconds, self.backoff_seconds.get("connection", 8.0))
        return base_interval_seconds

    def run(
        self,
        domain_key: str,
        action: Callable[[], object],
        interval_seconds: float | None = None,
    ) -> object:
        """在域名互斥锁内执行采集动作，并按结果动态调整冷却时间。"""
        base_interval_seconds = (
            self.interval_seconds
            if interval_seconds is None
            else max(0.0, float(interval_seconds or 0.0))
        )
        lock = self._get_domain_lock(domain_key)
        with lock:
            last_finished_at = self._last_finished_at.get(domain_key, 0.0)
            required_interval = max(
                base_interval_seconds,
                self._next_interval_seconds.get(domain_key, 0.0),
            )
            wait_seconds = required_interval - (time.monotonic() - last_finished_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            result: object | None = None
            try:
                result = action()
                return result
            finally:
                self._last_finished_at[domain_key] = time.monotonic()
                self._next_interval_seconds[domain_key] = self._resolve_next_interval(
                    result,
                    base_interval_seconds,
                )


def domain_key_for_url(url: str, fallback: str = "") -> str:
    """提取用于同域名限流的稳定键。"""
    parsed = urlparse(str(url or ""))
    hostname = str(parsed.hostname or "").strip().lower()
    if hostname:
        return hostname
    return f"unknown:{fallback or 'script'}"


def interleave_scripts_by_domain(
    scripts: list[Path],
    metadata_by_script: dict[Path, ScriptMetadata],
) -> list[Path]:
    """按域名轮换任务，避免连续同域名任务占满工作线程。"""
    queues_by_domain: dict[str, deque[Path]] = {}
    for script_path in scripts:
        metadata = metadata_by_script[script_path]
        domain_key = domain_key_for_url(metadata.url, fallback=script_path.stem)
        queues_by_domain.setdefault(domain_key, deque()).append(script_path)

    ordered_scripts: list[Path] = []
    active_domains = deque(queues_by_domain)
    while active_domains:
        domain_key = active_domains.popleft()
        domain_queue = queues_by_domain[domain_key]
        ordered_scripts.append(domain_queue.popleft())
        if domain_queue:
            active_domains.append(domain_key)
    return ordered_scripts


def resolve_project_dir_from_path(path: Path) -> Path:
    """从任意脚本或目录向上查找包含 crawler_core 的项目根目录。"""
    start_path = path.resolve()
    current_dir = start_path if start_path.is_dir() else start_path.parent
    for candidate in [current_dir, *current_dir.parents]:
        if (candidate / "crawler_core").is_dir():
            return candidate
    raise RuntimeError(f"未找到包含 crawler_core 的项目根目录：{path}")


def write_log(log_path: Path, message: str, organization: str = "", url: str = "") -> None:
    """同时输出到控制台和日志文件，每行包含时间、机构和网址。"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp}\t{organization}\t{url}\t{message}"
    print(line)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not log_path.exists()
    with log_path.open("a", encoding="utf-8") as file:
        if should_write_header:
            file.write("时间\t机构\t网址\t日志\n")
        file.write(line + "\n")


def script_sequence_from_path(script_path: Path) -> str:
    """从V3脚本文件名前缀读取四位脚本序号。"""
    match = re.match(r"^(\d{4})_", script_path.name)
    return match.group(1) if match else ""


def read_guard_page_rule(script_path: Path, module_globals: dict[str, object]) -> dict[str, object]:
    """读取迁移期脚本仅在__main__保护块中定义的规则字典，不执行业务流程。"""
    source_text = script_path.read_text(encoding="utf-8-sig")
    syntax_tree = ast.parse(source_text, filename=str(script_path))
    main_guards = [
        node
        for node in syntax_tree.body
        if isinstance(node, ast.If)
        and any(isinstance(child, ast.Name) and child.id == "__name__" for child in ast.walk(node.test))
    ]
    for main_guard in main_guards:
        for node in ast.walk(main_guard):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if not any(
                isinstance(target, ast.Name) and target.id in {"page_rule", "rule"}
                for target in targets
            ):
                continue
            value_node = node.value
            if not isinstance(value_node, ast.Dict):
                continue
            compiled_value = compile(ast.Expression(value_node), str(script_path), "eval")
            page_rule = eval(compiled_value, {"__builtins__": {}}, module_globals)
            if isinstance(page_rule, dict):
                return dict(page_rule)
    return {}


@lru_cache(maxsize=1)
def load_default_business_sources() -> dict[str, object]:
    """一次性读取默认规则主表，供批量启动阶段复用。"""
    from crawler_core.business_sources import load_business_sources

    return load_business_sources()


@lru_cache(maxsize=None)
def load_script_module_and_rule(script_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    """加载页面脚本，并兼容V3的build_page_rule与现行分类脚本的PAGE_RULE。"""
    module_globals = runpy.run_path(str(script_path))
    page_rule = module_globals.get("PAGE_RULE")
    if not isinstance(page_rule, dict):
        rule_builder = module_globals.get("build_page_rule")
        rule_id = script_sequence_from_path(script_path)
        if callable(rule_builder) and rule_id:
            from crawler_core.business_sources import get_business_source

            business_source = get_business_source(rule_id)
            available_arguments = {
                "rule_id": rule_id,
                "organization": business_source.organization,
                "url": business_source.source_url,
            }
            required_parameters = inspect.signature(rule_builder).parameters
            unsupported_parameters = [
                name
                for name, parameter in required_parameters.items()
                if parameter.default is inspect.Parameter.empty and name not in available_arguments
            ]
            if unsupported_parameters:
                raise ValueError(f"build_page_rule存在不支持的必填参数：{'、'.join(unsupported_parameters)}")
            builder_arguments = {
                name: available_arguments[name]
                for name in required_parameters
                if name in available_arguments
            }
            page_rule = rule_builder(**builder_arguments)
        else:
            page_rule = read_guard_page_rule(script_path, module_globals)
    if not isinstance(page_rule, dict):
        raise ValueError("脚本未提供可读取的V3页面规则字典")
    return module_globals, dict(page_rule)


def read_script_metadata(script_path: Path) -> ScriptMetadata:
    """优先从权威规则主表读取元数据，避免启动时预执行全部页面脚本。"""
    rule_id = script_sequence_from_path(script_path)
    metadata = ScriptMetadata(script_name=script_path.name, script_sequence=rule_id)
    if rule_id:
        try:
            business_source = load_default_business_sources().get(rule_id)
            if business_source is None:
                raise KeyError(f"规则主表未登记脚本序号：{rule_id}")
            metadata.organization = business_source.organization
            metadata.url = business_source.source_url
            return metadata
        except Exception:
            pass
    # 仅对无有效四位序号或规则主表缺失的异常脚本保留兼容性回退。
    try:
        from crawler_core.business_sources import apply_business_source

        _, page_rule = load_script_module_and_rule(script_path)
        resolved_rule = apply_business_source(page_rule)
        resolved_organization = str(resolved_rule.get("organization") or "")
        resolved_url = str(resolved_rule.get("url") or "")
        if resolved_organization:
            metadata.organization = resolved_organization
        if resolved_url:
            metadata.url = resolved_url
    except Exception:
        pass
    return metadata


def normalize_fetch_mode(value: object) -> str:
    """规范化批量运行支持的采集方式。"""
    mode = str(value or "").strip().lower()
    aliases = {
        "request": "requests",
        "chrome_cdp": "chrome",
    }
    mode = aliases.get(mode, mode)
    return mode if mode in {"online", "raw_http", "requests", "playwright", "chrome", "llm_vision"} else ""


def fetch_mode_execution_priority(fetch_mode: str) -> tuple[int, str]:
    """返回采集阶段的固定执行优先级，避免顺序受脚本序号影响。"""
    normalized_mode = normalize_fetch_mode(fetch_mode)
    priority_by_mode = {
        "raw_http": 0,
        "requests": 1,
        "playwright": 2,
        "chrome": 3,
        "llm_vision": 4,
        "online": 5,
    }
    return priority_by_mode.get(normalized_mode, len(priority_by_mode)), normalized_mode


def read_script_page_rule(script_path: Path) -> dict[str, object]:
    """读取V3页面规则，失败时返回空字典。"""
    try:
        _, page_rule = load_script_module_and_rule(script_path)
    except Exception:
        return {}
    return dict(page_rule)


def read_preferred_fetch_mode(
    script_path: Path,
    metadata: ScriptMetadata,
    fetch_mode_memory: dict[str, FetchMemoryRecord],
    respect_fetch_mode_memory: bool,
    respect_script_fetch_mode: bool,
) -> str:
    """只读取成功记忆；页面脚本中的历史采集方式永久不参与调度。"""
    _ = script_path, respect_script_fetch_mode
    if respect_fetch_mode_memory:
        record = fetch_mode_memory.get(normalize_script_sequence(metadata.script_sequence))
        remembered_mode = preferred_fetch_mode(record)
        if remembered_mode:
            return remembered_mode
    return ""


def build_script_fetch_mode_chain(
    script_path: Path,
    metadata: ScriptMetadata,
    fetch_mode_chain: tuple[str, ...],
    fetch_mode_memory: dict[str, FetchMemoryRecord],
    respect_fetch_mode_memory: bool,
    respect_script_fetch_mode: bool,
) -> tuple[str, ...]:
    """为单个脚本生成采集链路；成功记忆优先，失败后继续全局降级。"""
    modes = tuple(normalize_fetch_mode(mode) for mode in fetch_mode_chain)
    modes = tuple(mode for mode in modes if mode)
    if not modes:
        modes = ("raw_http", "requests", "playwright", "chrome", "llm_vision")
    preferred_mode = read_preferred_fetch_mode(
        script_path,
        metadata=metadata,
        fetch_mode_memory=fetch_mode_memory,
        respect_fetch_mode_memory=respect_fetch_mode_memory,
        respect_script_fetch_mode=respect_script_fetch_mode,
    )
    if not preferred_mode or preferred_mode not in modes:
        return modes
    return (preferred_mode, *(mode for mode in modes if mode != preferred_mode))


def update_fetch_mode_memory_record(
    fetch_mode_memory: dict[str, FetchMemoryRecord],
    metadata: ScriptMetadata,
    run_result: ScriptRunResult,
    run_timestamp: str,
) -> bool:
    """只把已经通过质量验收的实际采集事实写入内存表。"""
    collector, execution_mode = normalize_actual_collector(
        run_result.actual_collector,
        run_result.execution_mode,
    )
    script_sequence = normalize_script_sequence(metadata.script_sequence)
    if not script_sequence or not collector:
        return False
    fetch_mode_memory[script_sequence] = FetchMemoryRecord(
        script_sequence=script_sequence,
        actual_collector=collector,
        execution_mode=execution_mode,
        updated_at=run_timestamp,
    )
    return True


def apply_result_metadata(run_result: ScriptRunResult, metadata: ScriptMetadata) -> ScriptRunResult:
    """将脚本基础信息补入运行结果，便于后续统一汇总。"""
    run_result.script_name = metadata.script_name
    run_result.organization = metadata.organization
    run_result.url = metadata.url
    return run_result


def safe_report_cell(value: object) -> str:
    """清理制表符和换行，保证 TXT 表格结构稳定。"""
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def format_elapsed_seconds(elapsed_seconds: float) -> str:
    """把总秒数格式化为便于阅读和复核的采集耗时。"""
    safe_seconds = max(0.0, float(elapsed_seconds or 0.0))
    hours = int(safe_seconds // 3600)
    minutes = int((safe_seconds % 3600) // 60)
    seconds = safe_seconds % 60
    return f"{hours}小时{minutes}分{seconds:.1f}秒（{safe_seconds:.1f}秒）"


def build_failure_reason(run_result: ScriptRunResult) -> str:
    """生成适合四列失败报告的简明、可执行原因。"""
    failure_code, suggestion = diagnose_failure_detail(run_result)
    detail = str(run_result.quality.issue or "").strip()
    if not detail:
        message_lines = [line.strip() for line in str(run_result.message or "").splitlines() if line.strip()]
        detail = message_lines[-1] if message_lines else "未记录具体失败信息"
    detail = re.sub(r"\s+", " ", detail)
    if len(detail) > 1000:
        detail = f"{detail[:997]}..."
    return f"{detail}；分类：{failure_code}；建议：{suggestion}"


def recycle_failed_output(run_result: ScriptRunResult, output_dir: Path) -> str:
    """把最终失败脚本生成的 TXT 移入回收站，保证输出目录只保留成功结果。"""
    output_path_text = str(run_result.quality.output_path or "").strip()
    if not output_path_text:
        return "失败脚本未生成 TXT，无需清理。"

    output_path = Path(output_path_text)
    if not output_path.exists():
        return "失败脚本未留下 TXT，无需清理。"

    try:
        resolved_output_dir = output_dir.resolve()
        resolved_output_path = output_path.resolve()
        if not resolved_output_path.is_relative_to(resolved_output_dir):
            message = f"拒绝清理输出目录之外的文件：{resolved_output_path}"
            run_result.message = f"{run_result.message}\n{message}"
            run_result.quality.issue = f"{run_result.quality.issue}；{message}".strip("；")
            return message

        from send2trash import send2trash

        send2trash(str(resolved_output_path))
        message = f"失败输出已移入回收站：{resolved_output_path}"
        run_result.message = f"{run_result.message}\n{message}"
        return message
    except Exception as error:
        message = f"失败输出清理失败：{error}"
        run_result.message = f"{run_result.message}\n{message}"
        run_result.quality.issue = f"{run_result.quality.issue}；{message}".strip("；")
        return message


def build_fetch_context_message(rule: dict[str, object], original_url: str) -> str:
    """生成抓取上下文摘要，用于失败报告快速判断跳转和状态码。"""
    parts: list[str] = []
    collector = str(rule.get("actual_collector") or rule.get("fetch_collector") or "").strip()
    execution_mode = str(rule.get("execution_mode") or "").strip()
    status_code = str(rule.get("status_code") or rule.get("fetch_status_code") or "").strip()
    content_type = str(rule.get("content_type") or rule.get("fetch_content_type") or "").strip()
    final_url = str(rule.get("final_url") or "").strip()
    if collector:
        parts.append(f"collector={collector}")
    if execution_mode:
        parts.append(f"execution={execution_mode}")
    if status_code and status_code != "0":
        parts.append(f"status={status_code}")
    if content_type:
        parts.append(f"content_type={content_type}")
    if bool(rule.get("has_javascript_redirect")):
        parts.append("js_redirect=true")
    page_issue = str(rule.get("page_issue") or "").strip()
    if page_issue:
        parts.append(f"page_issue={page_issue}")
    if final_url:
        parts.append(f"final_url={final_url}")
        if original_url and final_url.rstrip("/") != original_url.rstrip("/"):
            parts.append(f"redirected_from={original_url}")
    return "；".join(parts)


def diagnose_failure_detail(run_result: ScriptRunResult) -> tuple[str, str]:
    """把原始失败文本归纳为便于人工排查的具体原因和建议。"""
    message = str(run_result.message or "")
    final_message = message.rsplit("\n--- 重试链路 ---\n", maxsplit=1)[-1]
    quality_issue = str(run_result.quality.issue or "").strip()
    diagnostic_text = quality_issue or final_message
    text = diagnostic_text.lower()
    failure_category = str(run_result.failure_category or "").strip().lower()
    final_url_match = re.search(r"final_url=([^；\s]+)", final_message)
    final_url = final_url_match.group(1).lower() if final_url_match else ""
    if failure_category in {"http_404", "http_410"} or "/404" in final_url:
        return "http_404_or_404_redirect", "检查网址是否已失效，或在浏览器中查找新的领导信息页面。"
    if failure_category == "http_403":
        return "http_403_forbidden", "补充请求头、Referer、Cookie，或直接走 Playwright/Chrome。"
    if failure_category == "page_validation":
        return "page_validation_failed", "当前页面内容未通过人物范围、数量或证据校验；检查页面结构和页面专属规则。"
    if failure_category in {"empty_parse", "page_failed_record"}:
        return "parse_empty_after_successful_fetch", "网页可抓取但未形成有效人物记录，优先检查人物区域、选择器和解析器规则。"
    if failure_category == "ssl" or "ssl" in text or "证书" in diagnostic_text:
        return "ssl_certificate_error", "确认已忽略证书；若仍失败，改用浏览器采集。"
    if failure_category == "timeout" or "timeout" in text or "运行超时" in diagnostic_text or "超时" in diagnostic_text:
        return "timeout", "提高超时时间，或检查该站点是否加载慢、接口阻塞。"
    if "searchresult" in final_url or "/search" in final_url or "搜索结果" in diagnostic_text or "站内搜索" in diagnostic_text:
        return "redirect_search_page", "程序被跳到搜索页，需改原始入口、Referer、请求方式或选择 Playwright/Chrome。"
    if "login" in final_url or "sso" in final_url or "一网通办" in diagnostic_text or "登录页" in diagnostic_text:
        return "redirect_login_page", "程序被跳到登录/统一认证页，优先使用浏览器上下文或寻找公开静态入口。"
    if "wza" in final_url or "无障碍" in diagnostic_text or "适老" in diagnostic_text:
        return "redirect_accessibility_page", "程序拿到无障碍/适老页面，需禁用该跳转或改用 Playwright 渲染后的真实页面。"
    if "抽取失败记录" in diagnostic_text or "解析结果为空" in diagnostic_text or "有效人物记录为 0" in diagnostic_text:
        return "parse_empty_after_successful_fetch", "网页可抓取但未抽到姓名和职务，优先检查人物区域选择器和解析器规则。"
    if "最终失败，已删除失败输出 txt" in final_message:
        return "final_failed_output_deleted", "三轮采集均未形成有效人物记录；失败 TXT 已删除，应结合完整失败原因继续排查。"
    if failure_category == "missing_output" or "输出文件不存在" in final_message or "未识别到输出文件路径" in final_message:
        return "missing_output_file", "脚本未正常生成输出路径，检查脚本启动异常或输出文件名规则。"
    if failure_category == "browser" or "playwright" in text or "chrome" in text or "浏览器" in diagnostic_text:
        return "browser_render_error", "浏览器渲染阶段失败，检查 Playwright/Chrome 调试端口和页面加载状态。"
    if failure_category in {"http", "fetch"} or "http" in text or "状态码" in diagnostic_text:
        return "http_error", "检查响应状态码、跳转地址、请求头和站点防护。"
    return "other", "查看完整失败原因，按网页结构、选择器、解析器和采集方式逐项排查。"


def worker_count_for_fetch_mode(fetch_mode: str, max_workers: int, task_count: int) -> int:
    """按采集方式自适应并发；只有本机 Chrome 调试端口需要低并发保护。"""
    normalized_mode = str(fetch_mode or "").strip().lower()
    safe_task_count = max(1, task_count)
    configured_workers = max(1, max_workers)
    if normalized_mode in {"chrome", "chrome_cdp"}:
        return min(1, configured_workers, safe_task_count)
    if normalized_mode == "playwright":
        cpu_count = os.cpu_count() or 8
        playwright_workers = max(8, min(configured_workers, cpu_count))
        return min(playwright_workers, safe_task_count)
    if normalized_mode == "online":
        cpu_count = os.cpu_count() or 8
        online_workers = max(8, min(configured_workers, cpu_count))
        return min(online_workers, safe_task_count)
    return min(configured_workers, safe_task_count)


def iter_adapter_scripts(adapter_dir: Path) -> list[Path]:
    """递归获取指定目录中的Python脚本，排除缓存和当前一键运行脚本。"""
    if not adapter_dir.exists():
        return []
    current_script = Path(__file__).resolve()
    return sorted(
        [
            path
            for path in adapter_dir.rglob("*.py")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.resolve() != current_script
        ],
        key=lambda path: (script_sequence_from_path(path) or "9999", str(path.relative_to(adapter_dir)).lower()),
    )


def classify_failure(message: str) -> str:
    """将失败原因归类，便于批量筛选。"""
    text = str(message or "").lower()
    if any(marker in text for marker in ("nameresolutionerror", "failed to resolve", "getaddrinfo failed")):
        return "dns"
    if "域名熔断" in message:
        return "domain_circuit_open"
    validation_markers = (
        "无法核对",
        "数量异常",
        "人数异常",
        "缺少可靠",
        "未找到目标",
        "未找到市委领导",
        "未通过人物",
        "未得到经视觉核验",
    )
    if any(marker in message for marker in validation_markers):
        return "page_validation"
    if "运行超时" in message or "timeout" in text:
        return "timeout"
    if "ssl" in text or "证书" in message:
        return "ssl"
    if "403" in text or "forbidden" in text:
        return "http_403"
    if "404" in text or "not found" in text:
        return "http_404"
    if "410" in text or "gone" in text:
        return "http_410"
    if "http" in text or "状态码" in message:
        return "http"
    if "playwright" in text or "chrome" in text or "浏览器" in message:
        return "browser"
    if "解析结果为空" in message:
        return "empty_parse"
    if "输出文件不存在" in message or "未识别到输出文件路径" in message:
        return "missing_output"
    if "抽取失败" in message:
        return "page_failed_record"
    if "有效人物记录为 0" in message:
        return "empty_parse"
    if "在线采集失败" in message or "requests" in text:
        return "fetch"
    return "other"


def decide_failure_transition(
    run_result: ScriptRunResult,
    script_path: Path,
    fetch_mode: str,
) -> FailureTransition:
    """按失败证据决定是否继续，以及只允许进入哪些后续采集器。"""
    message = str(run_result.message or "")
    text = message.casefold()
    normalized_mode = normalize_fetch_mode(fetch_mode)
    terminal_markers = (
        "nameresolutionerror",
        "failed to resolve",
        "getaddrinfo failed",
        "域名熔断",
        "invalid url",
        "no scheme supplied",
        "404 client error",
        "410 client error",
        "status=404",
        "status=410",
        "/404",
    )
    if any(marker in text for marker in terminal_markers):
        return FailureTransition(True, (), "确定性网址、DNS或页面不存在错误")
    if run_result.failure_category in {"missing_output"}:
        return FailureTransition(True, (), "脚本执行或输出契约错误，切换采集器无意义")

    if "403" in text or "412" in text or "forbidden" in text:
        return FailureTransition(False, ("playwright", "chrome"), "站点拒绝HTTP请求，直接进入浏览器链路")

    if re.search(r"\b5\d\d\b", text):
        if normalized_mode == "raw_http":
            return FailureTransition(
                False,
                ("requests", "playwright", "chrome"),
                "服务端错误可能因请求形态而异，继续增强HTTP及浏览器链路",
            )
        if normalized_mode == "requests":
            return FailureTransition(
                False,
                ("playwright", "chrome"),
                "增强HTTP仍遇到服务端错误，继续浏览器链路",
            )
        if normalized_mode == "playwright":
            return FailureTransition(False, ("chrome",), "Playwright仍遇到服务端错误，继续Chrome CDP")
        return FailureTransition(True, (), "最后浏览器采集器仍返回服务端错误")
    network_markers = (
        "timed out",
        "timeout",
        "连接超时",
        "连接被重置",
        "connection reset",
        "connection aborted",
        "max retries exceeded",
        "ssl",
        "证书",
    )
    if run_result.failure_category in {"timeout", "ssl", "fetch", "http"} or any(
        marker in text for marker in network_markers
    ):
        if normalized_mode in {"raw_http", "requests"}:
            return FailureTransition(False, ("playwright", "chrome"), "HTTP网络链路失败，允许一次浏览器降级")
        if normalized_mode == "playwright":
            return FailureTransition(False, ("chrome",), "Playwright失败，允许最后一次Chrome CDP降级")
        return FailureTransition(True, (), "最后浏览器采集器已经失败")

    parse_failure = run_result.failure_category in {"empty_parse", "page_failed_record"} or any(
        marker in message
        for marker in ("解析结果为空", "有效人物记录为 0", "抽取失败", "数量异常", "缺少可靠")
    )
    if parse_failure:
        page_rule = read_script_page_rule(script_path)
        load_mode = str(page_rule.get("load_mode") or "")
        is_dynamic_page = bool(page_rule.get("force_browser")) or load_mode in {
            "动态DOM渲染",
            "iframe嵌入",
            "接口数据加载",
            "动态XHR返回HTML片段",
            "动态JSON接口",
        }
        if normalized_mode == "raw_http" and "js_redirect=true" in text:
            return FailureTransition(
                False,
                ("requests", "playwright", "chrome"),
                "原始HTML包含脚本跳转，先由requests跟随跳转",
            )
        if "page_issue=" in text and normalized_mode in {"raw_http", "requests"}:
            return FailureTransition(False, ("playwright", "chrome"), "HTTP页面疑似防护页或无效响应")
        if is_dynamic_page and normalized_mode in {"raw_http", "requests"}:
            return FailureTransition(False, ("playwright", "chrome"), "页面规则明确要求动态渲染")
        return FailureTransition(True, (), "已成功取得静态页面，但确定性解析未通过")

    if normalized_mode == "raw_http":
        return FailureTransition(False, ("requests", "playwright", "chrome"), "原始HTTP失败，保留增强HTTP及浏览器兜底")
    if normalized_mode == "requests":
        return FailureTransition(False, ("playwright", "chrome"), "增强HTTP失败，保留浏览器兜底")
    if normalized_mode == "playwright":
        return FailureTransition(False, ("chrome",), "Playwright失败，保留Chrome CDP兜底")
    return FailureTransition(True, (), "采集链路已无有意义的后续阶段")


def resolve_attempt_timeout_seconds(
    fetch_mode: str,
    total_timeout_seconds: int,
    elapsed_seconds: float,
    collector_timeout_seconds_by_mode: dict[str, int],
) -> int:
    """在单脚本总预算内，为当前采集器分配独立的阶段超时。"""
    remaining_total_seconds = max(1, int(total_timeout_seconds - elapsed_seconds))
    normalized_mode = normalize_fetch_mode(fetch_mode)
    collector_timeout_seconds = max(
        1,
        int(collector_timeout_seconds_by_mode.get(normalized_mode, total_timeout_seconds)),
    )
    return min(remaining_total_seconds, collector_timeout_seconds)


def describe_extraction_channel(run_result: ScriptRunResult) -> str:
    """区分确定性解析与DeepSeek视觉解析，避免把视觉处理误写成采集器。"""
    attempted_collectors = [str(item).lower() for item in run_result.attempted_collectors or []]
    if normalize_fetch_mode(run_result.fetch_mode) == "llm_vision" or any(
        "llm_vision" in item for item in attempted_collectors
    ):
        return "deepseek_vision"
    return "deterministic_parser"


def parse_output_path(message: str) -> Path | None:
    """从脚本标准输出中提取输出文件路径。"""
    match = re.search(r"输出文件[:：]\s*(.+?)(?:\r?\n|$)", str(message or ""))
    if not match:
        return None
    return Path(match.group(1).strip().strip('"'))


def analyze_output_quality(output_path: Path | None) -> OutputQuality:
    """按V3十二列契约检查单页输出是否形成可验证人物记录。"""
    if output_path is None:
        return OutputQuality(issue="未识别到输出文件路径")
    quality = OutputQuality(output_path=str(output_path))
    if not output_path.is_file():
        quality.issue = "输出文件不存在"
        return quality
    lines = output_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) <= 1:
        quality.issue = "输出文件无数据行"
        return quality
    headers = [header.strip() for header in lines[0].split("\t")]
    missing_fields = [field for field in OUTPUT_FIELDS if field not in headers]
    if missing_fields:
        quality.issue = f"输出不是V3十二列，缺少字段：{'、'.join(missing_fields)}"
        return quality
    name_index = headers.index("姓名*")
    evidence_index = headers.index("依据说明")
    failure_details: list[str] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = line.split("\t")
        quality.row_count += 1
        name = cells[name_index].strip() if 0 <= name_index < len(cells) else ""
        evidence = cells[evidence_index].strip() if 0 <= evidence_index < len(cells) else ""
        if name and evidence:
            quality.complete_count += 1
        if "抽取失败" in evidence:
            quality.failure_record_count += 1
            failure_detail = re.sub(r"^抽取失败\s*[:：]?\s*", "", evidence).strip()
            if failure_detail and failure_detail not in failure_details:
                failure_details.append(failure_detail)
    if quality.failure_record_count > 0:
        if failure_details:
            quality.issue = f"抽取失败：{'；'.join(failure_details[:5])}"
            if len(failure_details) > 5:
                quality.issue = f"{quality.issue}；另有 {len(failure_details) - 5} 种失败原因"
        else:
            quality.issue = f"存在 {quality.failure_record_count} 条抽取失败记录"
    elif quality.complete_count == 0:
        quality.issue = "有效人物记录为 0"
    return quality


def resolve_output_category_dir(output_dir: Path, folder_name: str) -> Path:
    """解析并校验输出分类目录，确保目标始终位于outputs根目录内。"""
    normalized_name = str(folder_name or "").strip()
    relative_path = Path(normalized_name)
    if (
        not normalized_name
        or relative_path.is_absolute()
        or len(relative_path.parts) != 1
        or normalized_name in {".", ".."}
    ):
        raise ValueError(f"输出分类目录名称无效：{folder_name}")

    resolved_output_dir = output_dir.resolve()
    category_dir = (resolved_output_dir / relative_path).resolve()
    if category_dir.parent != resolved_output_dir:
        raise ValueError(f"输出分类目录超出outputs根目录：{category_dir}")
    return category_dir


def iter_root_result_files(output_dir: Path) -> list[Path]:
    """只获取outputs根目录中的单脚本结果，不包含合并文件和子目录。"""
    return sorted(
        [
            path
            for path in output_dir.glob("*.txt")
            if path.is_file() and re.match(r"^\d{4}_", path.name)
        ],
        key=lambda path: (script_sequence_from_path(path), path.name.lower()),
    )


def index_classified_result_files(category_dirs: tuple[Path, Path]) -> dict[str, list[Path]]:
    """一次建立分类目录中的脚本序号索引，避免逐文件重复扫描目录。"""
    indexed_files: dict[str, list[Path]] = {}
    for category_dir in category_dirs:
        for file_path in category_dir.glob("*.txt"):
            script_sequence = script_sequence_from_path(file_path)
            if script_sequence:
                indexed_files.setdefault(script_sequence, []).append(file_path)
    return indexed_files


def recycle_stale_classified_files(stale_files: list[Path], current_target: Path) -> int:
    """把同序号旧分类结果移入回收站，避免成功和失败目录并存旧状态。"""
    from send2trash import send2trash

    recycled_count = 0
    candidates = list(stale_files)
    if current_target.exists() and all(
        candidate.resolve() != current_target.resolve() for candidate in candidates
    ):
        candidates.append(current_target)
    for candidate in candidates:
        if not candidate.exists():
            continue
        send2trash(str(candidate))
        recycled_count += 1
    return recycled_count


def organize_output_files(
    output_dir: Path,
    success_folder_name: str,
    failure_folder_name: str,
    log_path: Path,
) -> OutputOrganizationSummary:
    """检查outputs根目录的单脚本TXT，并分别移入成功、失败目录。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    success_dir = resolve_output_category_dir(output_dir, success_folder_name)
    failure_dir = resolve_output_category_dir(output_dir, failure_folder_name)
    if success_dir == failure_dir:
        raise ValueError("成功目录和失败目录不能相同")
    success_dir.mkdir(parents=True, exist_ok=True)
    failure_dir.mkdir(parents=True, exist_ok=True)

    summary = OutputOrganizationSummary(success_dir=success_dir, failure_dir=failure_dir)
    result_files = iter_root_result_files(output_dir)
    classified_files_by_sequence = index_classified_result_files((success_dir, failure_dir))
    write_log(log_path, f"待分类单脚本TXT：{len(result_files)} 个")

    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None
    iterator = tqdm(result_files, desc="分类输出结果", unit="个文件") if tqdm else result_files

    for file_path in iterator:
        try:
            quality = analyze_output_quality(file_path)
            is_success = not quality.issue
            target_dir = success_dir if is_success else failure_dir
            target_path = target_dir / file_path.name
            script_sequence = script_sequence_from_path(file_path)
            summary.recycled_stale_count += recycle_stale_classified_files(
                classified_files_by_sequence.pop(script_sequence, []),
                current_target=target_path,
            )
            file_path.replace(target_path)
            classified_files_by_sequence[script_sequence] = [target_path]
            if is_success:
                summary.success_count += 1
            else:
                summary.failure_count += 1
        except Exception as error:
            summary.move_failed_count += 1
            write_log(log_path, f"分类失败：{file_path.name}，原因：{error}")

    write_log(
        log_path,
        "输出分类完成："
        f"成功 {summary.success_count} 个，失败 {summary.failure_count} 个，"
        f"分类异常 {summary.move_failed_count} 个，回收旧分类文件 {summary.recycled_stale_count} 个。",
    )
    write_log(log_path, f"成功目录：{success_dir}")
    write_log(log_path, f"失败目录：{failure_dir}")
    return summary


def run_one_script(python_exe: str, script_path: Path, timeout_seconds: int) -> ScriptRunResult:
    """运行单个爬虫脚本，返回是否成功和摘要信息。"""
    started_at = time.perf_counter()
    empty_quality = OutputQuality()
    try:
        result = subprocess.run(
            [python_exe, str(script_path)],
            cwd=str(resolve_project_dir_from_path(script_path)),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        message = f"运行超时：{error}"
        return ScriptRunResult(False, message, classify_failure(message), time.perf_counter() - started_at, empty_quality)
    except Exception as error:
        message = f"启动失败：{error}"
        return ScriptRunResult(False, message, classify_failure(message), time.perf_counter() - started_at, empty_quality)
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    elapsed_seconds = time.perf_counter() - started_at
    message = output or "运行完成"
    if result.returncode != 0:
        message = output or f"退出码：{result.returncode}"
        return ScriptRunResult(False, message, classify_failure(message), elapsed_seconds, empty_quality)
    quality = analyze_output_quality(parse_output_path(message))
    if quality.issue:
        message = f"{message}\n输出质量问题：{quality.issue}"
        return ScriptRunResult(False, message, classify_failure(quality.issue), elapsed_seconds, quality)
    return ScriptRunResult(True, message, "", elapsed_seconds, quality)


def run_page_rule_once(
    script_path: Path,
    output_dir: Path,
    fetch_mode: str,
    retry_round_index: int = 1,
) -> tuple[ScriptRunResult, dict[str, object] | None]:
    """按指定采集模式运行一次页面规则。"""
    attempt_started_at = time.perf_counter()
    empty_quality = OutputQuality()
    project_dir = resolve_project_dir_from_path(script_path)
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    runtime_context: dict[str, object] = {}
    try:
        from crawler_core.business_sources import apply_business_source

        module_globals, page_rule = load_script_module_and_rule(script_path)
        rule = apply_business_source(deepcopy(page_rule))
        if fetch_mode:
            rule["fetch_mode"] = fetch_mode
            rule["_fetch_mode_override"] = True
        safe_retry_round = max(1, int(retry_round_index or 1))
        rule["fetch_retry_round"] = safe_retry_round
        rule["requests_attempt_offset"] = (safe_retry_round - 1) * 10
        rule["playwright_stealth_profile"] = safe_retry_round
        from crawler_core.runner import run_page_adapter

        output_path = run_page_adapter(
            rule,
            module_globals,
            output_dir,
            runtime_context=runtime_context,
            update_fetch_memory=False,
        )
    except Exception as error:
        message = f"进程内运行失败：{error}"
        return (
            ScriptRunResult(False, message, classify_failure(message), time.perf_counter() - attempt_started_at, empty_quality),
            None,
        )

    elapsed_seconds = time.perf_counter() - attempt_started_at
    quality = analyze_output_quality(output_path)
    fetch_context = build_fetch_context_message(runtime_context, str(page_rule.get("url") or ""))
    message = f"[{fetch_mode or 'PAGE_RULE'}] 输出文件：{output_path}"
    if fetch_context:
        message = f"{message}\n抓取上下文：{fetch_context}"
    actual_collector = str(runtime_context.get("actual_collector") or "")
    execution_mode = str(runtime_context.get("execution_mode") or "")
    attempted_collectors = [
        str(item) for item in runtime_context.get("attempted_collectors", []) if str(item)
    ]
    if quality.issue:
        message = f"{message}\n输出质量问题：{quality.issue}"
        attempted_collectors.append(f"{fetch_mode}:解析失败")
        return (
            ScriptRunResult(
                False,
                message,
                classify_failure(quality.issue),
                elapsed_seconds,
                quality,
                actual_collector=actual_collector,
                execution_mode=execution_mode,
                attempted_collectors=attempted_collectors,
            ),
            module_globals,
        )
    if not attempted_collectors:
        attempted_collectors = [f"{fetch_mode}:成功"]
    return (
        ScriptRunResult(
            True,
            message,
            "",
            elapsed_seconds,
            quality,
            actual_collector=actual_collector,
            execution_mode=execution_mode,
            attempted_collectors=attempted_collectors,
        ),
        module_globals,
    )


def script_requires_llm_vision(script_path: Path) -> bool:
    """判断脚本是否标注为大模型视觉解析任务，普通脚本不执行预加载。"""
    try:
        source_text = script_path.read_text(encoding="utf-8-sig", errors="replace").lower()
    except OSError:
        return False
    if "llm_strategy" not in source_text and "llm_vision" not in source_text:
        return False
    try:
        _, page_rule = load_script_module_and_rule(script_path)
    except Exception:
        return False
    llm_strategy = page_rule.get("llm_strategy")
    if isinstance(llm_strategy, dict) and llm_strategy.get("required"):
        return True
    return str(page_rule.get("locator_strategy") or "").strip().lower() == "llm_vision"


def run_page_rule_once_with_timeout(
    script_path: Path,
    output_dir: Path,
    fetch_mode: str,
    retry_round_index: int,
    timeout_seconds: int,
    hard_timeout: bool = False,
) -> tuple[ScriptRunResult, dict[str, object] | None]:
    """按单脚本截止时间运行；浏览器阶段可启用可终止的进程硬隔离。"""
    if hard_timeout:
        return run_page_rule_once_with_hard_timeout(
            script_path,
            output_dir,
            fetch_mode,
            retry_round_index,
            timeout_seconds,
        )
    from crawler_core.fetcher import enforce_fetch_deadline

    with enforce_fetch_deadline(timeout_seconds):
        return run_page_rule_once(
            script_path,
            output_dir,
            fetch_mode,
            retry_round_index,
        )


def run_page_rule_process_worker(
    result_queue: object,
    script_path: Path,
    output_dir: Path,
    fetch_mode: str,
    retry_round_index: int,
    timeout_seconds: int,
) -> None:
    """在独立进程中执行浏览器采集，并把可序列化结果返回父进程。"""
    from crawler_core.fetcher import enforce_fetch_deadline

    try:
        with enforce_fetch_deadline(timeout_seconds):
            run_result, _ = run_page_rule_once(
                script_path,
                output_dir,
                fetch_mode,
                retry_round_index,
            )
        result_queue.put(run_result)
    except BaseException as error:
        message = f"隔离进程异常：{error}"
        result_queue.put(
            ScriptRunResult(False, message, classify_failure(message), 0.0, OutputQuality())
        )


def ensure_failure_output(
    run_result: ScriptRunResult,
    script_path: Path,
    output_dir: Path,
) -> None:
    """由父进程补写失败 TXT，覆盖隔离进程被强制终止等无输出场景。"""
    if run_result.success:
        return
    existing_path_text = str(run_result.quality.output_path or "").strip()
    if existing_path_text and Path(existing_path_text).is_file():
        return

    try:
        from crawler_core.business_sources import apply_business_source
        from crawler_core.exporter import export_records
        from crawler_core.naming import build_output_name
        from crawler_core.runner import (
            apply_business_location,
            make_failure_record,
            prepare_records_for_export,
        )

        _, page_rule = load_script_module_and_rule(script_path)
        rule = apply_business_source(deepcopy(page_rule))
        rule_id = normalize_script_sequence(
            rule.get("rule_id") or rule.get("sequence") or script_sequence_from_path(script_path)
        )
        organization = str(rule.get("organization") or "").strip()
        failure_reason = str(run_result.quality.issue or run_result.message or "未知失败").strip()
        rows = [make_failure_record(rule, failure_reason)]
        apply_business_location(rule, rows)
        prepare_records_for_export(rows)
        for row in rows:
            row.script_sequence = rule_id

        output_path = output_dir / build_output_name(rule_id, organization)
        export_records(output_path, rows)
        run_result.quality = analyze_output_quality(output_path)
        run_result.message = f"{run_result.message}\n父进程已补写失败输出：{output_path}"
    except Exception as error:
        run_result.message = f"{run_result.message}\n父进程补写失败输出失败：{error}"


def run_page_rule_once_with_hard_timeout(
    script_path: Path,
    output_dir: Path,
    fetch_mode: str,
    retry_round_index: int,
    timeout_seconds: int,
) -> tuple[ScriptRunResult, dict[str, object] | None]:
    """以可强制终止的独立进程执行可能卡死的浏览器采集。"""
    started_at = time.perf_counter()
    safe_timeout = max(1, int(timeout_seconds or 1))
    process_context = multiprocessing.get_context("spawn")
    result_queue = process_context.Queue(maxsize=1)
    process = process_context.Process(
        target=run_page_rule_process_worker,
        args=(
            result_queue,
            script_path,
            output_dir,
            fetch_mode,
            retry_round_index,
            safe_timeout,
        ),
        name=f"crawler-{fetch_mode}-{script_path.stem}",
    )
    try:
        process.start()
        process.join(safe_timeout)
        if process.is_alive():
            process.terminate()
            process.join(5)
            elapsed_seconds = time.perf_counter() - started_at
            message = f"运行硬超时：{fetch_mode} 阶段超过 {safe_timeout} 秒，隔离进程已终止"
            run_result = ScriptRunResult(
                False,
                message,
                "timeout",
                elapsed_seconds,
                OutputQuality(),
            )
            ensure_failure_output(run_result, script_path, output_dir)
            return run_result, None
        try:
            run_result = result_queue.get(timeout=2)
        except queue.Empty:
            elapsed_seconds = time.perf_counter() - started_at
            message = f"隔离进程未返回结果，退出码：{process.exitcode}"
            run_result = ScriptRunResult(
                False,
                message,
                classify_failure(message),
                elapsed_seconds,
                OutputQuality(),
            )
        if not run_result.success:
            ensure_failure_output(run_result, script_path, output_dir)
        return run_result, None
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
        result_queue.close()
        result_queue.join_thread()


def merge_attempt_results(attempt_results: list[ScriptRunResult]) -> ScriptRunResult:
    """合并多次尝试结果，保留最终状态和完整原因。"""
    final_result = attempt_results[-1]
    elapsed_seconds = sum(result.elapsed_seconds for result in attempt_results)
    message = "\n--- 重试链路 ---\n".join(result.message for result in attempt_results)
    return ScriptRunResult(
        success=final_result.success,
        message=message,
        failure_category=final_result.failure_category,
        elapsed_seconds=elapsed_seconds,
        quality=final_result.quality,
        round_index=final_result.round_index,
        fetch_mode=final_result.fetch_mode,
        actual_collector=final_result.actual_collector,
        execution_mode=final_result.execution_mode,
        attempted_collectors=merge_attempted_collectors(attempt_results),
    )


def merge_attempted_collectors(attempt_results: list[ScriptRunResult]) -> list[str]:
    """按真实运行顺序合并各采集阶段的结构化尝试记录。"""
    merged: list[str] = []
    for result in attempt_results:
        current_attempts = list(result.attempted_collectors or [])
        if not current_attempts:
            status = "成功" if result.success else "失败"
            current_attempts = [f"{result.fetch_mode or 'unknown'}:{status}"]
        merged.extend(current_attempts)
    return merged


def run_one_script_in_process(
    script_path: Path,
    output_dir: Path,
    fetch_mode_chain: tuple[str, ...],
    delete_failed_output: bool,
) -> ScriptRunResult:
    """运行单个页面脚本；保留给诊断场景使用的单脚本链式重试。"""
    attempt_results: list[ScriptRunResult] = []
    requires_llm_vision = script_requires_llm_vision(script_path)
    modes = tuple(mode for mode in fetch_mode_chain if str(mode or "").strip())
    if not modes:
        modes = ("raw_http", "requests", "playwright", "chrome")
    if requires_llm_vision:
        modes = ("llm_vision",)

    for fetch_mode in modes:
        run_result, _ = run_page_rule_once(
            script_path,
            output_dir,
            fetch_mode,
            retry_round_index=len(attempt_results) + 1,
        )
        run_result.round_index = len(attempt_results) + 1
        run_result.fetch_mode = fetch_mode
        attempt_results.append(run_result)
        if run_result.success:
            run_result.attempted_collectors = merge_attempted_collectors(attempt_results)
            return run_result

    merged_result = merge_attempt_results(attempt_results)
    if delete_failed_output:
        recycle_failed_output(merged_result, output_dir)
    return merged_result


def run_scripts_sequential(
    scripts: list[Path],
    output_dir: Path,
    log_path: Path,
    python_exe: str,
    timeout_seconds: int,
    stop_on_error: bool,
    delete_failed_output: bool,
) -> tuple[list[ScriptRunResult], list[tuple[str, ScriptRunResult]]]:
    """按旧方式顺序启动子进程运行，用于需要强隔离的诊断场景。"""
    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None

    success_rows: list[ScriptRunResult] = []
    failed_rows: list[tuple[str, ScriptRunResult]] = []
    iterator = tqdm(scripts, desc="运行爬虫脚本") if tqdm else scripts
    for index, script_path in enumerate(iterator, start=1):
        metadata = read_script_metadata(script_path)
        write_log(log_path, f"[{index}/{len(scripts)}] 开始：{script_path.name}", metadata.organization, metadata.url)
        run_result = apply_result_metadata(run_one_script(python_exe, script_path, timeout_seconds), metadata)
        if run_result.success:
            success_rows.append(run_result)
            write_log(
                log_path,
                f"[成功] {script_path.name}，有效记录 {run_result.quality.complete_count} 条，耗时 {run_result.elapsed_seconds:.1f} 秒",
                metadata.organization,
                metadata.url,
            )
        else:
            if delete_failed_output:
                cleanup_message = recycle_failed_output(run_result, output_dir)
                write_log(log_path, cleanup_message, metadata.organization, metadata.url)
            failed_rows.append((script_path.name, run_result))
            write_log(
                log_path,
                f"[失败] {script_path.name}，类别 {run_result.failure_category}，耗时 {run_result.elapsed_seconds:.1f} 秒：{run_result.message}",
                metadata.organization,
                metadata.url,
            )
            if stop_on_error:
                break
    return success_rows, failed_rows


def run_scripts_parallel_in_process(
    scripts: list[Path],
    output_dir: Path,
    log_path: Path,
    run_timestamp: str,
    max_workers: int,
    timeout_seconds: int,
    stop_on_error: bool,
    fetch_mode_chain: tuple[str, ...],
    delete_failed_output: bool,
    retry_worker_plan: tuple[dict[str, int], ...] | None = None,
    fetch_mode_memory_path: Path | None = None,
    respect_fetch_mode_memory: bool = True,
    respect_script_fetch_mode: bool = True,
    update_fetch_mode_memory: bool = True,
    same_domain_interval_seconds: float = 0.0,
    same_domain_interval_by_mode: dict[str, float] | None = None,
    domain_backoff_seconds: dict[str, float] | None = None,
    fetch_memory_flush_batch_size: int = 50,
    hard_timeout_fetch_modes: tuple[str, ...] = ("chrome",),
    collector_timeout_seconds_by_mode: dict[str, int] | None = None,
) -> tuple[list[ScriptRunResult], list[tuple[str, ScriptRunResult]]]:
    """进程内并发运行页面脚本，按失败证据执行有向降级。"""
    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None

    success_rows: list[ScriptRunResult] = []
    failed_rows: list[tuple[str, ScriptRunResult]] = []
    modes = tuple(mode for mode in fetch_mode_chain if str(mode or "").strip())
    if not modes:
        modes = ("raw_http", "requests", "playwright", "chrome", "llm_vision")
    has_explicit_retry_plan = retry_worker_plan is not None
    worker_plan_rounds = retry_worker_plan or tuple({mode: max_workers for mode in modes} for _ in range(1))

    attempts_by_script: dict[Path, list[ScriptRunResult]] = {script_path: [] for script_path in scripts}
    success_by_script: dict[Path, ScriptRunResult] = {}
    metadata_by_script = {script_path: read_script_metadata(script_path) for script_path in scripts}
    llm_required_by_script = {script_path: script_requires_llm_vision(script_path) for script_path in scripts}
    normalized_interval_by_mode = {
        normalize_fetch_mode(mode): max(0.0, float(interval or 0.0))
        for mode, interval in (same_domain_interval_by_mode or {}).items()
        if normalize_fetch_mode(mode)
    }
    normalized_hard_timeout_modes = {
        normalize_fetch_mode(mode)
        for mode in hard_timeout_fetch_modes
        if normalize_fetch_mode(mode)
    }
    normalized_collector_timeouts = {
        normalize_fetch_mode(mode): max(1, int(seconds or 1))
        for mode, seconds in (collector_timeout_seconds_by_mode or {}).items()
        if normalize_fetch_mode(mode)
    }
    from crawler_core.fetcher import reset_domain_circuit_breakers

    reset_domain_circuit_breakers()
    domain_throttle = DomainThrottle(
        same_domain_interval_seconds,
        backoff_seconds=domain_backoff_seconds,
    )
    resolved_memory_path = fetch_mode_memory_path or (
        Path(__file__).resolve().parent / "workspace" / "module" / "采集方式成功记录.txt"
    )
    fetch_mode_memory = load_fetch_memory(resolved_memory_path)
    pending_memory_updates: dict[str, FetchMemoryRecord] = {}
    safe_memory_flush_batch_size = max(1, int(fetch_memory_flush_batch_size or 1))
    write_log(log_path, f"采集方式记忆文档：{resolved_memory_path}，已读取 {len(fetch_mode_memory)} 条记录。")
    if update_fetch_mode_memory and not resolved_memory_path.exists():
        write_fetch_memory(resolved_memory_path, fetch_mode_memory)
    write_log(log_path, f"同域名最小间隔秒：{same_domain_interval_seconds}")
    write_log(log_path, f"分采集器同域名间隔秒：{normalized_interval_by_mode}")
    write_log(log_path, f"动态退避秒：{domain_backoff_seconds or {}}")
    write_log(log_path, f"成功记录批量落盘阈值：{safe_memory_flush_batch_size}")
    write_log(log_path, f"硬超时隔离采集器：{sorted(normalized_hard_timeout_modes)}")
    write_log(log_path, f"分采集器阶段超时秒：{normalized_collector_timeouts}")
    mode_chain_by_script = {
        script_path: build_script_fetch_mode_chain(
            script_path,
            metadata_by_script[script_path],
            modes,
            fetch_mode_memory=fetch_mode_memory,
            respect_fetch_mode_memory=respect_fetch_mode_memory,
            respect_script_fetch_mode=respect_script_fetch_mode,
        )
        for script_path in scripts
    }
    for script_path, requires_llm_vision in llm_required_by_script.items():
        script_chain = mode_chain_by_script.get(script_path, modes)
        if not requires_llm_vision:
            mode_chain_by_script[script_path] = tuple(
                mode for mode in script_chain if mode != "llm_vision"
            )
            continue
        filtered_chain = tuple(
            mode for mode in script_chain
            if mode in {"requests", "llm_vision"}
        )
        mode_chain_by_script[script_path] = filtered_chain or ("requests", "llm_vision")
    remaining_scripts = list(scripts)
    terminal_failed_scripts: set[Path] = set()
    scheduler_decision_counts: dict[str, int] = {}
    aborted = False

    for retry_round_index, worker_plan in enumerate(worker_plan_rounds, start=1):
        max_stage_count = max(
            (len(mode_chain_by_script.get(script_path, modes)) for script_path in remaining_scripts),
            default=0,
        )
        for stage_index in range(max_stage_count):
            stage_modes: list[str] = []
            for script_path in remaining_scripts:
                script_chain = mode_chain_by_script.get(script_path, modes)
                if stage_index >= len(script_chain):
                    continue
                stage_mode = script_chain[stage_index]
                if stage_mode not in stage_modes:
                    stage_modes.append(stage_mode)
            stage_modes.sort(key=fetch_mode_execution_priority)

            for fetch_mode in stage_modes:
                current_scripts = [
                    script_path
                    for script_path in remaining_scripts
                    if stage_index < len(mode_chain_by_script.get(script_path, modes))
                    and mode_chain_by_script.get(script_path, modes)[stage_index] == fetch_mode
                ]
                if not current_scripts:
                    continue
                current_scripts = interleave_scripts_by_domain(
                    current_scripts,
                    metadata_by_script,
                )
                current_script_set = set(current_scripts)
                skipped_scripts = [
                    script_path for script_path in remaining_scripts
                    if script_path not in current_script_set
                ]

                configured_workers = max(1, int(worker_plan.get(fetch_mode, max_workers)))
                if has_explicit_retry_plan:
                    worker_count = min(configured_workers, len(current_scripts))
                else:
                    worker_count = worker_count_for_fetch_mode(fetch_mode, configured_workers, len(current_scripts))
                if normalize_fetch_mode(fetch_mode) in {"chrome", "chrome_cdp"}:
                    worker_count = 1
                write_log(
                    log_path,
                    f"第 {retry_round_index}/{len(worker_plan_rounds)} 执行轮，链路位置 {stage_index + 1}/{max_stage_count}："
                    f"统一使用 {fetch_mode} 通道，待运行 {len(current_scripts)} 个脚本，并发 {worker_count}。",
                )
                remaining_timeout_by_script = {
                    script_path: resolve_attempt_timeout_seconds(
                        fetch_mode=fetch_mode,
                        total_timeout_seconds=timeout_seconds,
                        elapsed_seconds=sum(
                            item.elapsed_seconds
                            for item in attempts_by_script[script_path]
                        ),
                        collector_timeout_seconds_by_mode=normalized_collector_timeouts,
                    )
                    for script_path in current_scripts
                }
                longest_stage_timeout = max(remaining_timeout_by_script.values(), default=0)
                estimated_upper_bound = (
                    len(current_scripts) * longest_stage_timeout / max(1, worker_count)
                )
                write_log(
                    log_path,
                    f"{fetch_mode} 通道阶段超时上限 {longest_stage_timeout} 秒/脚本，"
                    f"按当前并发估算本阶段最坏耗时约 {format_elapsed_seconds(estimated_upper_bound)}。",
                )
                next_remaining_scripts: list[Path] = []
                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    future_to_script = {
                        executor.submit(
                            domain_throttle.run,
                            domain_key_for_url(
                                metadata_by_script[script_path].url,
                                fallback=script_path.stem,
                            ),
                            lambda current_script_path=script_path,
                            current_fetch_mode=fetch_mode,
                            current_retry_round_index=retry_round_index,
                            current_timeout_seconds=remaining_timeout_by_script[script_path]: run_page_rule_once_with_timeout(
                                current_script_path,
                                output_dir,
                                current_fetch_mode,
                                current_retry_round_index,
                                current_timeout_seconds,
                                hard_timeout=(
                                    normalize_fetch_mode(current_fetch_mode)
                                    in normalized_hard_timeout_modes
                                ),
                            ),
                            normalized_interval_by_mode.get(
                                fetch_mode,
                                same_domain_interval_seconds,
                            ),
                        ): script_path
                        for script_path in current_scripts
                    }
                    completed_iterable = as_completed(future_to_script)
                    if tqdm:
                        completed_iterable = tqdm(
                            completed_iterable,
                            total=len(future_to_script),
                            desc=f"第{retry_round_index}轮 {fetch_mode}",
                        )
                    for completed_count, future in enumerate(completed_iterable, start=1):
                        script_path = future_to_script[future]
                        metadata = metadata_by_script[script_path]
                        try:
                            run_result, _ = future.result()
                        except Exception as error:
                            message = f"并发任务异常：{error}"
                            run_result = ScriptRunResult(False, message, classify_failure(message), 0.0, OutputQuality())
                        run_result.round_index = retry_round_index
                        run_result.fetch_mode = fetch_mode
                        run_result = apply_result_metadata(run_result, metadata)
                        attempts_by_script[script_path].append(run_result)
                        if run_result.success:
                            run_result.attempted_collectors = merge_attempted_collectors(
                                attempts_by_script[script_path]
                            )
                            success_by_script[script_path] = run_result
                            success_rows.append(run_result)
                            if update_fetch_mode_memory:
                                memory_updated = update_fetch_mode_memory_record(
                                    fetch_mode_memory=fetch_mode_memory,
                                    metadata=metadata,
                                    run_result=run_result,
                                    run_timestamp=run_timestamp,
                                )
                                if memory_updated:
                                    script_sequence = normalize_script_sequence(metadata.script_sequence)
                                    memory_record = fetch_mode_memory.get(script_sequence)
                                    if memory_record is not None:
                                        pending_memory_updates[script_sequence] = memory_record
                                    if len(pending_memory_updates) >= safe_memory_flush_batch_size:
                                        written_count = merge_fetch_memory_records(
                                            resolved_memory_path,
                                            pending_memory_updates.values(),
                                        )
                                        pending_memory_updates.clear()
                                        write_log(log_path, f"成功采集记录已批量落盘：{written_count} 条。")
                                    collector_text = run_result.actual_collector
                                    if run_result.execution_mode:
                                        collector_text = f"{collector_text}({run_result.execution_mode})"
                                    write_log(
                                        log_path,
                                        f"已更新实际成功采集器={collector_text}：{script_path.name}",
                                        metadata.organization,
                                        metadata.url,
                                    )
                                else:
                                    write_log(
                                        log_path,
                                        f"成功但未取得实际采集器，未更新记忆：{script_path.name}",
                                        metadata.organization,
                                        metadata.url,
                                    )
                            write_log(
                                log_path,
                                f"[第{retry_round_index}轮 {fetch_mode} {completed_count}/{len(current_scripts)}] [成功] {script_path.name}，有效记录 {run_result.quality.complete_count} 条，耗时 {run_result.elapsed_seconds:.1f} 秒",
                                metadata.organization,
                                metadata.url,
                            )
                        else:
                            script_chain = mode_chain_by_script.get(script_path, modes)
                            transition = decide_failure_transition(
                                run_result,
                                script_path,
                                fetch_mode,
                            )
                            is_parse_failure = run_result.failure_category in {
                                "empty_parse",
                                "page_failed_record",
                            }
                            if (
                                llm_required_by_script.get(script_path, False)
                                and is_parse_failure
                                and "llm_vision" in script_chain[stage_index + 1 :]
                                and transition.reason == "已成功取得静态页面，但确定性解析未通过"
                            ):
                                transition = FailureTransition(
                                    False,
                                    ("llm_vision",),
                                    "页面规则明确要求大模型视觉解析",
                                )
                            elif (
                                stage_index == 0
                                and script_chain[0] != modes[0]
                                and transition.reason
                                in {
                                    "最后浏览器采集器已经失败",
                                    "采集链路已无有意义的后续阶段",
                                }
                            ):
                                transition = FailureTransition(
                                    False,
                                    tuple(script_chain[1:]),
                                    "成功采集器记忆已失效，继续全局降级链路",
                                )
                            cumulative_elapsed = sum(
                                item.elapsed_seconds for item in attempts_by_script[script_path]
                            )
                            allowed_suffix = tuple(
                                mode
                                for mode in script_chain[stage_index + 1 :]
                                if normalize_fetch_mode(mode) in transition.allowed_modes
                            )
                            is_terminal_failure = (
                                transition.terminal
                                or cumulative_elapsed >= timeout_seconds
                                or not allowed_suffix
                            )
                            if is_terminal_failure:
                                terminal_failed_scripts.add(script_path)
                            else:
                                mode_chain_by_script[script_path] = (
                                    *script_chain[: stage_index + 1],
                                    *allowed_suffix,
                                )
                                next_remaining_scripts.append(script_path)
                            transition_reason = transition.reason
                            if cumulative_elapsed >= timeout_seconds:
                                transition_reason = (
                                    f"单脚本累计预算已耗尽：{cumulative_elapsed:.1f}/{timeout_seconds}秒"
                                )
                            elif not transition.terminal and not allowed_suffix:
                                transition_reason = f"{transition.reason}；配置链路中无可用后续采集器"
                            scheduler_decision_counts[transition_reason] = (
                                scheduler_decision_counts.get(transition_reason, 0) + 1
                            )
                            write_log(
                                log_path,
                                f"[第{retry_round_index}轮 {fetch_mode} {completed_count}/{len(current_scripts)}] [失败] {script_path.name}，类别 {run_result.failure_category}，耗时 {run_result.elapsed_seconds:.1f} 秒，调度决策：{transition_reason}：{run_result.message}",
                                metadata.organization,
                                metadata.url,
                            )
                            if stop_on_error:
                                for pending_future in future_to_script:
                                    pending_future.cancel()
                                aborted = True
                                break
                if fetch_mode == "playwright":
                    try:
                        from crawler_core.fetcher import close_all_playwright_pools

                        close_all_playwright_pools()
                        write_log(log_path, "已关闭本轮 Playwright 浏览器池。")
                    except Exception as error:
                        write_log(log_path, f"关闭 Playwright 浏览器池失败：{error}")
                remaining_scripts = skipped_scripts + next_remaining_scripts
                if aborted or not remaining_scripts:
                    break
            if aborted or not remaining_scripts:
                break
        if aborted or not remaining_scripts:
            break

    if update_fetch_mode_memory and pending_memory_updates:
        written_count = merge_fetch_memory_records(
            resolved_memory_path,
            pending_memory_updates.values(),
        )
        pending_memory_updates.clear()
        write_log(log_path, f"剩余成功采集记录已批量落盘：{written_count} 条。")

    total_attempt_count = sum(len(items) for items in attempts_by_script.values())
    write_log(log_path, f"实际采集尝试总数：{total_attempt_count}")
    for decision_reason, decision_count in sorted(
        scheduler_decision_counts.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        write_log(log_path, f"调度决策统计：{decision_reason}={decision_count}")

    for script_path in scripts:
        if script_path in success_by_script:
            continue
        attempt_results = attempts_by_script.get(script_path, [])
        if not attempt_results:
            continue
        metadata = metadata_by_script[script_path]
        merged_result = merge_attempt_results(attempt_results)
        merged_result = apply_result_metadata(merged_result, metadata)
        if delete_failed_output:
            cleanup_message = recycle_failed_output(merged_result, output_dir)
            write_log(log_path, cleanup_message, metadata.organization, metadata.url)
        if script_path in terminal_failed_scripts or not aborted:
            failed_rows.append((script_path.name, merged_result))
    return success_rows, failed_rows


def main(
    adapter_dir: str | Path,
    script_sequence_filter: tuple[str, ...],
    output_dir: str | Path,
    report_dir: str | Path,
    log_path: str | Path,
    python_exe: str,
    timeout_seconds: int,
    stop_on_error: bool,
    execution_mode: str,
    max_workers: int,
    fetch_mode_chain: tuple[str, ...],
    retry_worker_plan: tuple[dict[str, int], ...],
    delete_failed_output: bool,
    fetch_mode_memory_path: str | Path,
    respect_fetch_mode_memory: bool,
    respect_script_fetch_mode: bool,
    update_fetch_mode_memory: bool,
    same_domain_interval_seconds: float,
    same_domain_interval_by_mode: dict[str, float],
    domain_backoff_seconds: dict[str, float],
    fetch_memory_flush_batch_size: int,
    hard_timeout_fetch_modes: tuple[str, ...],
    collector_timeout_seconds_by_mode: dict[str, int],
    success_folder_name: str = "成功",
    failure_folder_name: str = "失败",
) -> None:
    """一键运行全部页面级爬虫脚本。"""
    adapter_dir = resolve_path_argument(adapter_dir, anchor=__file__, must_exist=True)
    output_dir = resolve_path_argument(output_dir, anchor=__file__)
    report_dir = resolve_path_argument(report_dir, anchor=__file__)
    log_path = resolve_path_argument(log_path, anchor=__file__)
    fetch_mode_memory_path = resolve_path_argument(
        fetch_mode_memory_path, anchor=__file__
    )
    run_started_at = datetime.now()
    run_timestamp = run_started_at.strftime("%Y%m%d_%H%M%S")
    log_path = timestamped_output_path(log_path, run_timestamp)
    scripts = iter_adapter_scripts(adapter_dir)
    normalized_filter = {
        normalize_script_sequence(item)
        for item in script_sequence_filter
        if normalize_script_sequence(item)
    }
    if normalized_filter:
        scripts = [
            script_path
            for script_path in scripts
            if script_sequence_from_path(script_path) in normalized_filter
        ]
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    success_output_dir = resolve_output_category_dir(output_dir, success_folder_name)
    failure_output_dir = resolve_output_category_dir(output_dir, failure_folder_name)
    if success_output_dir == failure_output_dir:
        raise ValueError("成功目录和失败目录不能相同")
    success_output_dir.mkdir(parents=True, exist_ok=True)
    failure_output_dir.mkdir(parents=True, exist_ok=True)
    if log_path.exists():
        log_path.unlink()
    write_log(log_path, f"运行时间戳：{run_timestamp}")
    write_log(log_path, f"开始时间：{run_started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    write_log(log_path, f"爬虫目录：{adapter_dir}")
    write_log(
        log_path,
        f"脚本序号筛选：{','.join(sorted(normalized_filter)) if normalized_filter else '未启用'}",
    )
    write_log(log_path, f"输出目录：{output_dir}")
    write_log(log_path, f"成功结果目录：{success_output_dir}")
    write_log(log_path, f"失败结果目录：{failure_output_dir}")
    write_log(log_path, f"脚本数量：{len(scripts)}")
    write_log(log_path, f"运行模式：{execution_mode}")
    write_log(log_path, f"并发数：{max_workers}")
    write_log(log_path, f"单脚本总超时秒：{timeout_seconds}")
    write_log(log_path, f"采集链路：{' -> '.join(fetch_mode_chain)}")
    write_log(log_path, f"递减并发计划：{retry_worker_plan}")
    write_log(log_path, f"最终失败TXT移入回收站：{delete_failed_output}")
    write_log(log_path, f"采集方式记忆文档：{fetch_mode_memory_path}")
    write_log(log_path, f"优先使用采集方式记忆：{respect_fetch_mode_memory}")
    write_log(log_path, "页面脚本 fetch_mode：永久忽略")
    write_log(log_path, f"成功后更新采集方式记忆：{update_fetch_mode_memory}")
    write_log(log_path, f"同域名最小间隔秒：{same_domain_interval_seconds}")
    write_log(log_path, f"分采集器同域名间隔秒：{same_domain_interval_by_mode}")
    write_log(log_path, f"动态退避秒：{domain_backoff_seconds}")
    write_log(log_path, f"成功记录批量落盘阈值：{fetch_memory_flush_batch_size}")
    write_log(log_path, f"硬超时隔离采集器：{hard_timeout_fetch_modes}")
    write_log(log_path, f"分采集器阶段超时秒：{collector_timeout_seconds_by_mode}")
    from crawler_core.fetcher import disable_unavailable_loopback_proxies
    import urllib3

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    write_log(log_path, "已抑制 verify=False 产生的重复 InsecureRequestWarning；SSL降级事实仍保留在采集上下文。")

    disabled_proxy_variables = disable_unavailable_loopback_proxies()
    if disabled_proxy_variables:
        write_log(
            log_path,
            "检测到回环代理端口不可用；仅对本次Python进程停用代理变量："
            + ",".join(disabled_proxy_variables),
        )
    if update_fetch_mode_memory:
        backup_path, migrated_records = migrate_fetch_memory(
            fetch_mode_memory_path,
            report_dir,
            run_timestamp,
        )
        if backup_path is not None:
            write_log(log_path, f"旧版采集方式记忆已备份：{backup_path}")
            write_log(
                log_path,
                f"已迁移 {len(migrated_records)} 条可确认实际采集器记录；旧online记录等待重新校准。",
            )
    if not scripts:
        write_log(log_path, "没有发现可运行的爬虫脚本。")
        success_rows: list[ScriptRunResult] = []
        failed_rows: list[tuple[str, ScriptRunResult]] = []
    else:
        normalized_mode = str(execution_mode or "").strip().lower()
        if normalized_mode == "subprocess":
            success_rows, failed_rows = run_scripts_sequential(
                scripts=scripts,
                output_dir=output_dir,
                log_path=log_path,
                python_exe=python_exe,
                timeout_seconds=timeout_seconds,
                stop_on_error=stop_on_error,
                delete_failed_output=delete_failed_output,
            )
        else:
            project_dir = resolve_project_dir_from_path(adapter_dir)
            if str(project_dir) not in sys.path:
                sys.path.insert(0, str(project_dir))
            worker_count = max(1, min(max_workers, len(scripts)))
            success_rows, failed_rows = run_scripts_parallel_in_process(
                scripts=scripts,
                output_dir=output_dir,
                log_path=log_path,
                run_timestamp=run_timestamp,
                max_workers=worker_count,
                timeout_seconds=timeout_seconds,
                stop_on_error=stop_on_error,
                fetch_mode_chain=fetch_mode_chain,
                delete_failed_output=delete_failed_output,
                retry_worker_plan=retry_worker_plan,
                fetch_mode_memory_path=fetch_mode_memory_path,
                respect_fetch_mode_memory=respect_fetch_mode_memory,
                respect_script_fetch_mode=respect_script_fetch_mode,
                update_fetch_mode_memory=update_fetch_mode_memory,
                same_domain_interval_seconds=same_domain_interval_seconds,
                same_domain_interval_by_mode=same_domain_interval_by_mode,
                domain_backoff_seconds=domain_backoff_seconds,
                fetch_memory_flush_batch_size=fetch_memory_flush_batch_size,
                hard_timeout_fetch_modes=hard_timeout_fetch_modes,
                collector_timeout_seconds_by_mode=collector_timeout_seconds_by_mode,
            )

    from crawler_core.fetcher import shutdown_project_chrome_debug

    chrome_cleanup_message = shutdown_project_chrome_debug()
    write_log(log_path, chrome_cleanup_message)

    run_finished_at = datetime.now()
    collection_elapsed_seconds = (run_finished_at - run_started_at).total_seconds()
    collection_elapsed_text = format_elapsed_seconds(collection_elapsed_seconds)
    summary_path = report_dir / f"一键运行全部爬虫脚本_失败报告_{run_timestamp}.txt"
    summary_lines = ["脚本序号\t机构名\t网址\t失败原因"]
    for script_name, run_result in failed_rows:
        summary_lines.append(
            "\t".join(
                [
                    safe_report_cell(script_sequence_from_path(Path(script_name))),
                    safe_report_cell(run_result.organization),
                    safe_report_cell(run_result.url),
                    safe_report_cell(build_failure_reason(run_result)),
                ]
            )
        )
    summary_lines.extend(
        [
            "",
            "采集统计\t值",
            f"开始时间\t{run_started_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"结束时间\t{run_finished_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"整个爬虫采集耗时\t{collection_elapsed_text}",
        ]
    )
    report_text = "\n".join(summary_lines) + "\n"
    summary_path.write_text(report_text, encoding="utf-8")
    success_report_path = report_dir / f"一键运行全部爬虫脚本_成功采集报告_{run_timestamp}.txt"
    success_report_lines = [
        "脚本序号\t机构\t实际成功采集器\t执行形态\t抽取通道\t实际尝试链路\t有效记录数\t耗时秒"
    ]
    collector_counts: dict[str, int] = {}
    for run_result in sorted(
        success_rows,
        key=lambda item: normalize_script_sequence(script_sequence_from_path(Path(item.script_name))),
    ):
        collector = str(run_result.actual_collector or "unknown")
        collector_key = collector
        if collector == "playwright" and run_result.execution_mode:
            collector_key = f"playwright({run_result.execution_mode})"
        collector_counts[collector_key] = collector_counts.get(collector_key, 0) + 1
        success_report_lines.append(
            "\t".join(
                [
                    safe_report_cell(script_sequence_from_path(Path(run_result.script_name))),
                    safe_report_cell(run_result.organization),
                    safe_report_cell(collector),
                    safe_report_cell(run_result.execution_mode),
                    safe_report_cell(describe_extraction_channel(run_result)),
                    safe_report_cell(" → ".join(run_result.attempted_collectors or [])),
                    str(run_result.quality.complete_count),
                    f"{run_result.elapsed_seconds:.1f}",
                ]
            )
        )
    success_report_path.write_text("\n".join(success_report_lines) + "\n", encoding="utf-8")
    write_log(log_path, f"失败报告：{summary_path}")
    write_log(log_path, f"成功采集报告：{success_report_path}")
    organize_output_files(
        output_dir=output_dir,
        success_folder_name=success_folder_name,
        failure_folder_name=failure_folder_name,
        log_path=log_path,
    )
    for collector_key, count in sorted(collector_counts.items()):
        write_log(log_path, f"实际成功采集器统计：{collector_key}={count}")
    write_log(log_path, f"运行统计：脚本 {len(scripts)} 个，成功 {len(success_rows)} 个，失败 {len(failed_rows)} 个。")
    write_log(log_path, f"整个爬虫采集耗时：{collection_elapsed_text}")
    write_log(log_path, f"结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    adapter_dir_value = r"important_people/site_adapters"
    script_sequence_filter_value: tuple[str, ...] = ()
    output_dir_value = r"important_people/outputs"
    report_dir_value = r"important_people/workspace/reports"
    log_path_value = r"important_people/workspace/log/一键运行全部爬虫脚本.log"
    python_exe_value = sys.executable
    timeout_seconds_value = 480
    stop_on_error_value = False
    execution_mode_value = "in_process"
    fetch_mode_chain_value = ("raw_http", "requests", "playwright", "chrome", "llm_vision")
    max_workers_value = 50
    retry_worker_plan_value = (
        {"raw_http": 30, "requests": 30, "llm_vision": 4, "playwright": 12, "chrome": 1},
    )
    delete_failed_output_value = False
    fetch_mode_memory_path_value = r"important_people/workspace/module/采集方式成功记录.txt"
    respect_fetch_mode_memory_value = True
    respect_script_fetch_mode_value = False
    update_fetch_mode_memory_value = True
    same_domain_interval_seconds_value = 1.5
    same_domain_interval_by_mode_value = {
        "raw_http": 1.5,
        "requests": 1.5,
        "llm_vision": 2.0,
        "playwright": 2.5,
        "chrome": 4.0,
    }
    domain_backoff_seconds_value = {"403": 15.0, "429": 30.0, "connection": 8.0}
    fetch_memory_flush_batch_size_value = 50
    hard_timeout_fetch_modes_value = ("chrome",)
    collector_timeout_seconds_by_mode_value = {
        "raw_http": 90,
        "requests": 90,
        "playwright": 150,
        "chrome": 180,
        "llm_vision": 180,
    }
    success_folder_name_value = "成功"
    failure_folder_name_value = "失败"
    main(
        adapter_dir=adapter_dir_value,
        script_sequence_filter=script_sequence_filter_value,
        output_dir=output_dir_value,
        report_dir=report_dir_value,
        log_path=log_path_value,
        python_exe=python_exe_value,
        timeout_seconds=timeout_seconds_value,
        stop_on_error=stop_on_error_value,
        execution_mode=execution_mode_value,
        max_workers=max_workers_value,
        fetch_mode_chain=fetch_mode_chain_value,
        retry_worker_plan=retry_worker_plan_value,
        delete_failed_output=delete_failed_output_value,
        fetch_mode_memory_path=fetch_mode_memory_path_value,
        respect_fetch_mode_memory=respect_fetch_mode_memory_value,
        respect_script_fetch_mode=respect_script_fetch_mode_value,
        update_fetch_mode_memory=update_fetch_mode_memory_value,
        same_domain_interval_seconds=same_domain_interval_seconds_value,
        same_domain_interval_by_mode=same_domain_interval_by_mode_value,
        domain_backoff_seconds=domain_backoff_seconds_value,
        fetch_memory_flush_batch_size=fetch_memory_flush_batch_size_value,
        hard_timeout_fetch_modes=hard_timeout_fetch_modes_value,
        collector_timeout_seconds_by_mode=collector_timeout_seconds_by_mode_value,
        success_folder_name=success_folder_name_value,
        failure_folder_name=failure_folder_name_value,
    )
