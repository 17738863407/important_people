from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from typing import Iterable, Iterator
import uuid

from crawler_core.naming import script_sequence_from_filename
from crawler_core.rule_table import normalize_script_sequence


MEMORY_HEADERS = ("脚本序号", "实际成功采集器", "执行形态", "最近成功时间")
ACTUAL_COLLECTORS = {"raw_http", "requests", "playwright", "chrome_cdp"}
PLAYWRIGHT_EXECUTION_MODES = {"in_process", "subprocess"}
MEMORY_THREAD_LOCK = threading.RLock()


@dataclass(frozen=True)
class FetchMemoryRecord:
    """单个脚本最近一次经过输出质量验收的实际采集事实。"""

    script_sequence: str
    actual_collector: str
    execution_mode: str
    updated_at: str


def clean_memory_cell(value: object) -> str:
    """清理制表符和换行，保证四列TXT结构稳定。"""
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def normalize_actual_collector(
    value: object,
    execution_mode: object = "",
) -> tuple[str, str]:
    """规范化实际采集器，并把Playwright执行形态拆分为独立维度。"""
    collector = str(value or "").strip().lower()
    normalized_execution_mode = str(execution_mode or "").strip().lower()
    if collector == "request":
        collector = "requests"
    elif collector == "chrome":
        collector = "chrome_cdp"
    elif collector == "playwright_subprocess":
        collector = "playwright"
        normalized_execution_mode = "subprocess"

    if collector not in ACTUAL_COLLECTORS:
        return "", ""
    if collector != "playwright":
        normalized_execution_mode = ""
    elif normalized_execution_mode not in PLAYWRIGHT_EXECUTION_MODES:
        normalized_execution_mode = ""
    return collector, normalized_execution_mode


def preferred_fetch_mode(record: FetchMemoryRecord | None) -> str:
    """由实际成功采集器动态计算下次批量调度方式。"""
    if record is None:
        return ""
    mapping = {
        "raw_http": "raw_http",
        "requests": "requests",
        "playwright": "playwright",
        "chrome_cdp": "chrome",
    }
    return mapping.get(record.actual_collector, "")


def is_legacy_fetch_memory(memory_path: Path) -> bool:
    """判断记忆表是否仍是包含“成功采集方式”的旧结构。"""
    if not memory_path.is_file():
        return False
    for line in memory_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "|")):
            continue
        headers = tuple(line.split("\t"))
        return headers != MEMORY_HEADERS and "成功采集方式" in headers
    return False


def _legacy_row_to_record(row: dict[str, str]) -> FetchMemoryRecord | None:
    """把能够可靠推断的旧记录转换为四列事实记录；online记录不作猜测。"""
    script_name = str(row.get("脚本名") or "")
    script_sequence = normalize_script_sequence(
        row.get("脚本序号") or script_sequence_from_filename(script_name)
    )
    old_mode = str(row.get("成功采集方式") or "").strip().lower()
    if old_mode == "online" or old_mode == "llm_vision":
        return None
    collector, execution_mode = normalize_actual_collector(old_mode)
    if not script_sequence or not collector:
        return None
    return FetchMemoryRecord(
        script_sequence=script_sequence,
        actual_collector=collector,
        execution_mode=execution_mode,
        updated_at=str(row.get("最近成功时间") or ""),
    )


def _load_fetch_memory_unlocked(memory_path: Path) -> dict[str, FetchMemoryRecord]:
    """在调用方已经处理并发控制的前提下读取新旧记忆表。"""
    records: dict[str, FetchMemoryRecord] = {}
    if not memory_path.is_file():
        return records
    lines = memory_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    headers: list[str] = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith(("#", "|")):
            continue
        cells = line.split("\t")
        if cells and cells[0] in {"脚本序号", "脚本名"}:
            headers = cells
            continue
        if not headers:
            continue
        row = dict(zip(headers, cells))
        if "实际成功采集器" in headers:
            script_sequence = normalize_script_sequence(row.get("脚本序号"))
            collector, execution_mode = normalize_actual_collector(
                row.get("实际成功采集器"),
                row.get("执行形态"),
            )
            if not script_sequence or not collector:
                continue
            record = FetchMemoryRecord(
                script_sequence=script_sequence,
                actual_collector=collector,
                execution_mode=execution_mode,
                updated_at=str(row.get("最近成功时间") or ""),
            )
        else:
            record = _legacy_row_to_record(row)
            if record is None:
                continue
        old_record = records.get(record.script_sequence)
        if old_record is None or record.updated_at >= old_record.updated_at:
            records[record.script_sequence] = record
    return records


def load_fetch_memory(memory_path: Path) -> dict[str, FetchMemoryRecord]:
    """读取四列记忆表，并兼容可可靠推断的旧记录。"""
    with MEMORY_THREAD_LOCK:
        return _load_fetch_memory_unlocked(memory_path)


def fetch_memory_lock_path(memory_path: Path) -> Path:
    """在系统临时目录中为记忆表生成稳定且不冲突的跨进程锁路径。"""
    normalized_path = str(memory_path.resolve()).casefold().encode("utf-8")
    path_digest = hashlib.sha256(normalized_path).hexdigest()[:24]
    return Path(tempfile.gettempdir()) / f"important_person_fetch_memory_{path_digest}.lock"


@contextmanager
def fetch_memory_file_lock(memory_path: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
    """使用系统临时目录中的锁文件保护跨进程的记忆表读改写。"""
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        with MEMORY_THREAD_LOCK:
            yield
        return

    import msvcrt

    lock_path = fetch_memory_lock_path(memory_path)
    with MEMORY_THREAD_LOCK, lock_path.open("a+b") as lock_file:
        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"0")
            lock_file.flush()
        deadline = time.monotonic() + max(0.1, timeout_seconds)
        while True:
            try:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"等待采集方式记忆文件锁超时：{lock_path}")
                time.sleep(0.05)
        try:
            yield
        finally:
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


def _write_fetch_memory_unlocked(
    memory_path: Path,
    records: dict[str, FetchMemoryRecord],
) -> None:
    """以同目录唯一临时文件原子替换四列记忆表。"""
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(MEMORY_HEADERS)]
    for record in sorted(records.values(), key=lambda item: item.script_sequence):
        lines.append(
            "\t".join(
                [
                    clean_memory_cell(record.script_sequence),
                    clean_memory_cell(record.actual_collector),
                    clean_memory_cell(record.execution_mode),
                    clean_memory_cell(record.updated_at),
                ]
            )
        )
    temporary_path = memory_path.with_name(
        f"{memory_path.name}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp"
    )
    temporary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.replace(temporary_path, memory_path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_fetch_memory(memory_path: Path, records: dict[str, FetchMemoryRecord]) -> None:
    """加锁并原子写入四列记忆表。"""
    with fetch_memory_file_lock(memory_path):
        _write_fetch_memory_unlocked(memory_path, records)


def record_fetch_success(
    memory_path: Path,
    script_sequence: object,
    actual_collector: object,
    execution_mode: object = "",
    updated_at: str = "",
) -> FetchMemoryRecord | None:
    """在单脚本成功后安全更新一条实际采集事实。"""
    normalized_sequence = normalize_script_sequence(script_sequence)
    collector, normalized_execution_mode = normalize_actual_collector(
        actual_collector,
        execution_mode,
    )
    if not normalized_sequence or not collector:
        return None
    record = FetchMemoryRecord(
        script_sequence=normalized_sequence,
        actual_collector=collector,
        execution_mode=normalized_execution_mode,
        updated_at=updated_at or datetime.now().strftime("%Y%m%d_%H%M%S"),
    )
    if is_legacy_fetch_memory(memory_path):
        migrate_fetch_memory(
            memory_path,
            memory_path.parent.parent / "reports",
            datetime.now().strftime("%Y%m%d_%H%M%S"),
        )
    with fetch_memory_file_lock(memory_path):
        records = _load_fetch_memory_unlocked(memory_path)
        records[normalized_sequence] = record
        _write_fetch_memory_unlocked(memory_path, records)
    return record


def merge_fetch_memory_records(
    memory_path: Path,
    updates: Iterable[FetchMemoryRecord],
) -> int:
    """在同一文件锁内批量合并成功记录，只执行一次全表读写。"""
    normalized_updates: dict[str, FetchMemoryRecord] = {}
    for update in updates:
        script_sequence = normalize_script_sequence(update.script_sequence)
        collector, execution_mode = normalize_actual_collector(
            update.actual_collector,
            update.execution_mode,
        )
        if not script_sequence or not collector:
            continue
        normalized_updates[script_sequence] = FetchMemoryRecord(
            script_sequence=script_sequence,
            actual_collector=collector,
            execution_mode=execution_mode,
            updated_at=update.updated_at or datetime.now().strftime("%Y%m%d_%H%M%S"),
        )
    if not normalized_updates:
        return 0
    if is_legacy_fetch_memory(memory_path):
        migrate_fetch_memory(
            memory_path,
            memory_path.parent.parent / "reports",
            datetime.now().strftime("%Y%m%d_%H%M%S"),
        )
    with fetch_memory_file_lock(memory_path):
        records = _load_fetch_memory_unlocked(memory_path)
        records.update(normalized_updates)
        _write_fetch_memory_unlocked(memory_path, records)
    return len(normalized_updates)


def migrate_fetch_memory(
    memory_path: Path,
    backup_dir: Path,
    timestamp: str,
) -> tuple[Path | None, dict[str, FetchMemoryRecord]]:
    """备份旧表并迁移可确认记录；无法确认的online记录只保留在备份中。"""
    if not memory_path.is_file():
        records: dict[str, FetchMemoryRecord] = {}
        write_fetch_memory(memory_path, records)
        return None, records
    with fetch_memory_file_lock(memory_path):
        if not is_legacy_fetch_memory(memory_path):
            return None, _load_fetch_memory_unlocked(memory_path)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"采集方式成功记录_旧版备份_{timestamp}.txt"
        shutil.copy2(memory_path, backup_path)
        records = _load_fetch_memory_unlocked(memory_path)
        _write_fetch_memory_unlocked(memory_path, records)
        return backup_path, records
