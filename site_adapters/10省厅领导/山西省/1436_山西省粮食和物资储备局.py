from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def compact_text(value: str) -> str:
    """移除详情页中文职务中的纯排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or "")).strip("：:，,。. ")


def parse_leader_page(html: str, expected_name: str, detail_url: str) -> dict[str, str] | None:
    """从单个领导页的独立姓名与职务段落提取字段。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    name_node = soup.select_one(".tabsContent.right .onlineSystem span:nth-of-type(2)")
    name = compact_text(name_node.get_text(" ", strip=True) if name_node else "")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name != expected_name:
        return None
    evidence = ""
    for paragraph in soup.select(".tabsContent.right .online-font p"):
        text = compact_text(paragraph.get_text(" ", strip=True))
        if "领导分工" in text or "发布时间" in text:
            continue
        if re.search(r"局长|巡视员", text):
            evidence = text
            break
    if not evidence:
        return None
    return {"name": name, "duty": evidence, "detail_url": detail_url, "evidence": evidence,
            "confidence": "high", "parser": "page_inline_shanxi_grain_dynamic_leader_pages_v2",
            "selector_summary": "list=.leftTabs a[href]；name=.onlineSystem span:nth-of-type(2)；duty=.online-font p excluding duties/date"}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """从入口侧栏动态发现全部领导页并按侧栏顺序解析。"""
    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str]] = []
    seen_urls: set[str] = set()
    for link in soup.select(".leftTabs a[href]"):
        name = compact_text(link.get_text(" ", strip=True))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not detail_url or detail_url in seen_urls:
            continue
        seen_urls.add(detail_url)
        candidates.append((name, detail_url))

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for name, detail_url in candidates[:20]:
        detail_html = html if detail_url.rstrip("/") == final_url.rstrip("/") else fetch_html_with_strategy(detail_url, "raw_http").html
        row = parse_leader_page(detail_html, name, detail_url)
        if row is None or name in seen_names:
            continue
        seen_names.add(name)
        if detail_url.rstrip("/") == final_url.rstrip("/"):
            row["detail_url"] = ""
        rows.append(row)
    return rows


PAGE_RULE = {
    "rule_id": "1436", "page_type": "人物列表完整页", "structure_group": "shanxi_grain_dynamic_leader_pages", "reuse_scope": "same_site_structure",
    "load_mode": "静态HTML直出", "fetch_mode": "raw_http", "extract_mode": "list_to_detail", "collector": "static_http", "parser": "page_inline_shanxi_grain_dynamic_leader_pages_v2",
    "leader_region_selector": ".leftTabs a[href]", "name_selector": ".onlineSystem span:nth-of-type(2)", "duty_selector": ".online-font p", "detail_link_selector": ".leftTabs a[href]",
    "content_scope": {"start_anchor": "本局领导", "end_anchor": "领导分工", "include_selectors": [".leftTabs", ".tabsContent.right", ".onlineSystem", ".online-font"], "exclude_selectors": [".footer", ".nav", "script", "style"]},
    "detail_strategy": {"required": True, "mode": "list_to_detail", "detail_collector_type": "raw_http", "detail_link_selector": ".leftTabs a[href]", "detail_name_selector": ".onlineSystem span:nth-of-type(2)", "detail_duty_selector": ".online-font p", "detail_content_selector": ".tabsContent.right", "max_detail_links": 20},
    "risk_flag": "职务文本存在字符间排版空格；详情正文同时含领导分工和发布时间，必须只取独立职务段落", "confidence": "high", "profile_reusable": "是", "profile_judgement": "网页画像通过_可用于该网页后续更新", "filter_policy": "strong_no_wordlist", "locator_strategy": "detail_chain",
    "locator": {"css": {"leader_region_selector": ".leftTabs a[href]", "name_selector": ".onlineSystem span:nth-of-type(2)", "duty_selector": ".online-font p", "detail_link_selector": ".leftTabs a[href]", "content_scope": {"start_anchor": "本局领导", "end_anchor": "领导分工", "include_selectors": [".leftTabs", ".tabsContent.right", ".onlineSystem", ".online-font"], "exclude_selectors": [".footer", ".nav", "script", "style"]}}, "api": {"enabled": False, "reason": "静态侧栏和领导详情页已直出姓名、职务及链接"}, "migration": {"source": "legacy_page_rule", "verified_status": "verified_online", "behavior_changed": True}},
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
