from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0052",
    "domain": "www.119.gov.cn",
    "page_type": "人物列表转详情页",
    "structure_group": "",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "extract_mode": "list_detail",
    "collector": "chrome_cdp",
    "parser": "page_verified_chrome_link_map_v2",
    "leader_region_selector": ".mod-block-1 .mod-l ul.list_dotted",
    "name_selector": "li > a[ct2_id]",
    "duty_selector": "人物简历区域内以“现任”开头的段落",
    "detail_link_selector": "li > a[ct2_id]",
    "content_scope": {
        "start_anchor": "领导信息",
        "end_anchor": "主要职责",
        "include_selectors": [".mod-block-1 .mod-l"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": True,
        "mode": "custom_verified_chrome_session",
        "detail_link_selector": "li > a[ct2_id]",
        "detail_content_selector": "人物简历标题所在内容区域",
        "max_detail_links": 20,
    },
    "risk_flag": "入口存在WAF，需复用项目Chrome中已经人工验证的会话",
    "confidence": "high",
    "profile_reusable": "仅限国家消防救援局当前页面结构",
    "profile_judgement": "列表和详情页均由浏览器当前响应动态解析",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".mod-block-1 .mod-l ul.list_dotted",
            "name_selector": "li > a[ct2_id]",
            "duty_selector": "人物简历区域内以“现任”开头的段落",
            "detail_link_selector": "li > a[ct2_id]",
        },
        "api": {
            "enabled": False,
            "reason": "官网通过浏览器页面会话提供列表、链接映射和详情内容",
        },
        "migration": {
            "source": "live_verified_chrome_response",
            "verified_status": "online",
            "behavior_changed": True,
        },
    },
}


def normalize_text(value: str) -> str:
    """清理网页排版空白，保留原有职务语义和标点。"""
    return re.sub(r"\s+", "", str(value or "")).strip()


def is_verification_page(html: str) -> bool:
    """识别站点验证页，避免把验证提示误当成领导信息。"""
    text = str(html or "")
    markers = ("ctctCheckbox", "safeSplider", "正在验证您是否是真人", "请稍候…")
    return any(marker in text for marker in markers)


def decode_link_map(page: Any) -> dict[str, str]:
    """调用官网页面自身的解码函数，取得本次响应对应的真实链接映射。"""
    page.wait_for_function(
        """typeof a_98xjmzx === 'function'
        && typeof ct2aObVar1 === 'string'
        && typeof ct2aObVar2 === 'string'""",
        timeout=5000,
    )
    decoded = page.evaluate("a_98xjmzx(ct2aObVar1, ct2aObVar2)")
    link_map = json.loads(str(decoded or "{}"))
    if not isinstance(link_map, dict):
        raise RuntimeError("官网真实链接映射格式异常")
    return {
        str(key): str(value).strip()
        for key, value in link_map.items()
        if str(key).strip() and str(value).strip()
    }


def open_verified_page(page: Any, url: str) -> tuple[str, str, dict[str, str]]:
    """在已经人工验证的项目Chrome中打开页面，并保留原始主文档响应。"""
    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    if response is None:
        raise RuntimeError(f"页面没有返回主文档响应：{url}")
    html = response.text()
    if is_verification_page(html):
        raise RuntimeError("国家消防救援局网站要求重新进行人机验证")
    link_map = decode_link_map(page)
    return html, str(page.url or url), link_map


def extract_leader_links(
    html: str,
    final_url: str,
    link_map: dict[str, str],
) -> list[tuple[str, str]]:
    """按官网列表DOM顺序提取姓名，并用同次响应的链接映射恢复详情地址。"""
    soup = BeautifulSoup(html or "", "html.parser")
    links = soup.select(".mod-block-1 .mod-l ul.list_dotted li > a[ct2_id]")
    leaders: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in links:
        name = normalize_text(link.get_text(" ", strip=True))
        link_id = str(link.get("ct2_id") or "").strip()
        mapped_url = str(link_map.get(link_id) or "").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name) or name in seen:
            continue
        if not mapped_url or mapped_url.lower().startswith(("javascript:", "mailto:")):
            raise RuntimeError(f"未能恢复{name}的真实详情页链接")
        detail_url = urljoin(final_url, mapped_url)
        if "/jg/ldxx/" not in detail_url:
            raise RuntimeError(f"{name}的链接不是官网领导详情页：{detail_url}")
        seen.add(name)
        leaders.append((name, detail_url))
    if not leaders:
        raise RuntimeError("官网领导信息列表未提取到有效人物")
    return leaders


def find_profile_scope(soup: BeautifulSoup, name: str) -> Tag:
    """以当前人物的简历标题为锚点，限定职务证据的检索范围。"""
    expected_heading = f"{name}同志简历"
    heading: Tag | None = None
    for node in soup.find_all(True):
        if normalize_text(node.get_text(" ", strip=True)) == expected_heading:
            heading = node
            break
    if heading is None:
        raise RuntimeError(f"{name}详情页未找到人物简历标题")

    scope: Tag | None = heading
    while scope is not None and scope.name not in {"body", "html"}:
        current_paragraphs = [
            paragraph
            for paragraph in scope.find_all("p")
            if normalize_text(paragraph.get_text(" ", strip=True)).startswith("现任")
        ]
        if current_paragraphs:
            return scope
        scope = scope.parent if isinstance(scope.parent, Tag) else None
    raise RuntimeError(f"{name}详情页的人物区域未找到现任职务段落")


def extract_current_duty(html: str, name: str) -> tuple[str, str]:
    """只在当前人物简介区域提取完整现任句，并执行确定性基本清洗。"""
    soup = BeautifulSoup(html or "", "html.parser")
    scope = find_profile_scope(soup, name)
    candidates = [
        normalize_text(paragraph.get_text(" ", strip=True))
        for paragraph in scope.find_all("p")
        if normalize_text(paragraph.get_text(" ", strip=True)).startswith("现任")
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"{name}详情页现任职务段落数量异常：{len(candidates)}")
    original = candidates[0]
    matched = re.fullmatch(r"现任(.+?)[。；;]?$", original)
    if not matched:
        raise RuntimeError(f"{name}详情页现任职务句式无法可靠解析")
    duty = matched.group(1).strip(" ，,；;")
    if not duty:
        raise RuntimeError(f"{name}详情页现任职务清洗后为空")
    return original, duty


def collect_verified_rows(entry_url: str, page_rule: dict[str, Any]) -> list[dict[str, str]]:
    """复用项目Chrome验证状态，逐页采集当前领导名单和现任职务。"""
    try:
        from playwright.sync_api import sync_playwright
    except Exception as error:
        raise RuntimeError(f"当前Python环境无法使用Playwright：{error}") from error

    rows: list[dict[str, str]] = []
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.connect_over_cdp(
                "http://127.0.0.1:9222",
                timeout=10000,
            )
        except Exception as error:
            raise RuntimeError(
                "未连接到项目Chrome调试端口，请先打开项目专用Chrome并完成官网验证"
            ) from error
        if not browser.contexts:
            raise RuntimeError("项目Chrome中没有可复用的浏览器会话")
        page = browser.contexts[0].new_page()
        try:
            index_html, index_url, link_map = open_verified_page(page, entry_url)
            leaders = extract_leader_links(index_html, index_url, link_map)
            for name, detail_url in leaders:
                detail_html, resolved_detail_url, _ = open_verified_page(page, detail_url)
                original, duty = extract_current_duty(detail_html, name)
                rows.append(
                    {
                        "name": name,
                        "duty": duty,
                        "detail_url": resolved_detail_url,
                        "evidence": duty,
                        "original_evidence": original,
                        "parser": str(page_rule.get("parser", "")),
                        "selector_summary": (
                            ".mod-block-1 .mod-l ul.list_dotted li > a[ct2_id]；"
                            "人物简历标题所在区域内以“现任”开头的p"
                        ),
                    }
                )
        finally:
            page.close()
    return rows


def collect_rows_in_subprocess(entry_url: str) -> list[dict[str, str]]:
    """在隔离子进程中执行同步Playwright，兼容公共运行器的异步事件循环。"""
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--collect-json",
        entry_url,
    ]
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUTF8"] = "1"
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=120,
        check=False,
    )
    marker = "__0052_ROWS_JSON__="
    payload = ""
    for line in completed.stdout.splitlines():
        if line.startswith(marker):
            payload = line.removeprefix(marker)
    if completed.returncode != 0 or not payload:
        detail = "；".join(
            part.strip()
            for part in (completed.stderr, completed.stdout)
            if part.strip()
        )
        raise RuntimeError(f"国家消防救援局Chrome隔离采集失败：{detail[:2000]}")
    rows = json.loads(payload)
    if not isinstance(rows, list):
        raise RuntimeError("国家消防救援局Chrome隔离采集结果格式异常")
    return [dict(row) for row in rows if isinstance(row, dict)]


def parse_page(html: str, final_url: str, page_rule: dict[str, Any]) -> list[dict[str, str]]:
    """从已验证Chrome会话中的官网实时响应提取领导信息。"""
    entry_url = str(page_rule.get("url") or final_url).strip()
    if not entry_url:
        raise RuntimeError("缺少国家消防救援局领导信息入口地址")
    return collect_rows_in_subprocess(entry_url)


def main() -> None:
    """运行当前页面级在线爬虫。"""
    if len(sys.argv) >= 3 and sys.argv[1] == "--collect-json":
        rows = collect_verified_rows(sys.argv[2], PAGE_RULE)
        print("__0052_ROWS_JSON__=" + json.dumps(rows, ensure_ascii=False))
        return

    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.fetch_memory import record_fetch_success
    from crawler_core.runner import run_page_adapter

    runtime_context: dict[str, Any] = {}
    output_path = run_page_adapter(
        PAGE_RULE,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    if runtime_context.get("extraction_succeeded"):
        record_fetch_success(
            project_dir / "workspace" / "module" / "采集方式成功记录.txt",
            str(PAGE_RULE["rule_id"]),
            "chrome_cdp",
        )
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
