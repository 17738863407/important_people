from __future__ import annotations

import queue
import re
import sys
import threading
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0588",
    "page_type": "人物目录详情页",
    "structure_group": "gansu_ndrc_chrome_leader_directory_details",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "chrome",
    "extract_mode": "list_to_detail",
    "collector": "chrome_cdp",
    "leader_region_selector": ".zfld.tab-brief",
    "name_selector": "a[href]",
    "detail_link_selector": "a[href]",
    "risk_flag": "requests返回412且Playwright返回无效短页；详情右侧含简历和分工，只能取左侧目录职务节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").replace("\u3000", " ").split())


def _fetch_chrome_in_thread(url: str, timeout_seconds: int):
    """在线程内调用Chrome CDP，避免同步Playwright与运行器事件循环冲突。"""
    result_queue: queue.Queue[object] = queue.Queue(maxsize=1)

    def worker() -> None:
        from crawler_core.fetcher import fetch_by_chrome_debug

        try:
            result_queue.put(fetch_by_chrome_debug(url, timeout=timeout_seconds))
        except BaseException as error:
            result_queue.put(error)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=max(1, timeout_seconds) + 15)
    if thread.is_alive():
        raise TimeoutError("Chrome CDP抓取领导详情页超时")
    result = result_queue.get_nowait()
    if isinstance(result, BaseException):
        raise result
    return result


def _entry_candidates(html: str, final_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    for link in soup.select(".zfld.tab-brief a[href]"):
        name = re.sub(r"\s+", "", link.get_text(" ", strip=True))
        href = str(link.get("href") or "").strip()
        if not re.fullmatch(r"[一-鿿·]{2,4}", name) or href.lower().startswith("javascript:"):
            continue
        candidates.append((name, urljoin(final_url, href)))
    return candidates


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """用首个详情页的完整左侧目录核对全部人物职务与详情链接。"""
    from crawler_core.settings import get_settings

    candidates = _entry_candidates(html, final_url)
    if not candidates:
        raise RuntimeError("入口未发现领导人物详情链接")
    detail_result = _fetch_chrome_in_thread(
        candidates[0][1],
        get_settings().browser_timeout_seconds,
    )
    detail_soup = BeautifulSoup(detail_result.html, "html.parser")
    directory: list[tuple[str, str, str]] = []
    for link in detail_soup.select("div.lingdao_name > a[href]"):
        name_node = link.select_one(":scope > span")
        duty_node = link.select_one(":scope > p")
        name = re.sub(r"\s+", "", name_node.get_text(" ", strip=True) if name_node else "")
        evidence = _clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        detail_url = urljoin(detail_result.final_url, str(link.get("href") or ""))
        if re.fullmatch(r"[一-鿿·]{2,4}", name) and evidence and detail_url:
            directory.append((name, evidence, detail_url))

    if [name for name, _ in candidates] != [name for name, _, _ in directory]:
        raise RuntimeError("入口领导顺序与详情页目录不一致")
    if [url for _, url in candidates] != [url for _, _, url in directory]:
        raise RuntimeError("入口详情链接与详情页目录链接不一致")

    rows: list[dict[str, str]] = []
    for name, evidence, detail_url in directory:
        rows.append(
            {
                "order": str(len(rows) + 1),
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "confidence": str(page_rule.get("confidence") or "high"),
                "parser": "inline_gansu_ndrc_chrome_leader_directory_details_v1",
            }
        )
    return rows


def main(output_dir: Path | None = None) -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.naming import build_output_name
    from crawler_core.runner import make_failure_record, normalize_inline_rows, prepare_records_for_export
    from crawler_core.settings import get_settings

    rule = apply_business_source(PAGE_RULE)
    target_dir = output_dir or (project_dir / "outputs")
    output_path = target_dir / build_output_name(rule["rule_id"], rule["organization"])
    try:
        entry_result = _fetch_chrome_in_thread(rule["url"], get_settings().browser_timeout_seconds)
        rows = normalize_inline_rows(rule, parse_page(entry_result.html, entry_result.final_url, rule))
        if not rows:
            raise RuntimeError("甘肃省发展改革委领导目录解析结果为空")
        prepare_records_for_export(rows)
    except Exception as exc:
        failure = make_failure_record(rule, str(exc))
        failure.script_sequence = str(rule["rule_id"])
        rows = [failure]
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
