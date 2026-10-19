from __future__ import annotations

import html as html_module
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0704",
    "page_type": "多人物详情合并页",
    "structure_group": "tianjin_gfdy_embedded_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "inline_structured_data",
    "collector": "static_http",
    "parser": "custom_tianjin_gfdy_embedded_leaders_v1",
    "leader_region_selector": "script",
    "name_selector": "leader.name",
    "duty_selector": "leader.role",
    "detail_link_selector": "leader.url",
    "content_scope": {
        "start_anchor": "leader = {",
        "end_anchor": "console.log(leaders)",
        "include_selectors": ["script"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "embedded_wrapper_redirect",
        "detail_collector_type": "static_http",
        "detail_link_selector": "leader.url",
        "detail_name_selector": "title",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 50,
    },
    "risk_flag": "页面同时含人物活动新闻；仅解析内嵌leaders对象，人物URL为跳转包装页，须在线解析target_url后验证标题归属",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "embedded_data": {
            "object_start": "leader = {",
            "object_end": "leaders.push(leader)",
            "name_field": "name",
            "duty_field": "role",
            "detail_field": "url",
        },
        "api": {
            "enabled": False,
            "reason": "当前入口静态HTML内嵌leaders结构化对象直接提供姓名、职务和人物链接",
        },
    },
}


def _clean_text(value: str) -> str:
    """解码HTML实体并清理排版空白。"""
    text = html_module.unescape(str(value or ""))
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = text.replace("\u200b", "").replace("\ufeff", "").replace("\u3000", " ")
    return " ".join(text.split())


def _clean_name(value: str) -> str:
    """清理姓名中的网页排版空格。"""
    return re.sub(r"\s+", "", _clean_text(value))


def _extract_object_value(block: str, key: str) -> str:
    """只从当前leader对象字面量提取字段，避免活动新闻字段干扰。"""
    object_match = re.search(
        r"leader\s*=\s*\{(?P<body>.*?)\};\s*leaders\.push\(leader\)",
        block,
        flags=re.DOTALL,
    )
    if not object_match:
        return ""
    match = re.search(
        rf"{re.escape(key)}\s*:\s*'(?P<value>(?:\\'|[^'])*)'",
        object_match.group("body"),
        flags=re.DOTALL,
    )
    return match.group("value").replace("\\'", "'").strip() if match else ""


def _extract_js_value(block: str, key: str) -> str:
    """从当前leader脚本块提取对象字段或后续赋值字段。"""
    pattern = rf"(?:{re.escape(key)}\s*:|leader\.{re.escape(key)}\s*=)\s*'(?P<value>(?:\\'|[^'])*)'"
    match = re.search(pattern, block, flags=re.DOTALL)
    return match.group("value").replace("\\'", "'").strip() if match else ""


def _iter_leader_blocks(html: str) -> list[str]:
    """按页面源顺序切分每个有效leader对象脚本块。"""
    markers = list(re.finditer(r"leader\s*=\s*\{", html))
    blocks: list[str] = []
    for index, marker in enumerate(markers):
        start = marker.start()
        end = markers[index + 1].start() if index + 1 < len(markers) else html.find("console.log(leaders)", start)
        if end < 0:
            end = len(html)
        block = html[start:end]
        if "leaders.push(leader)" in block:
            blocks.append(block)
    return blocks


def _resolve_detail_url(wrapper_url: str, expected_name: str) -> str:
    """在线解析人物包装页target_url，并以最终页标题验证人物归属。"""
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/html,application/xhtml+xml"}
    wrapper = requests.get(wrapper_url, headers=headers, timeout=30)
    wrapper.raise_for_status()
    wrapper.encoding = wrapper.apparent_encoding or wrapper.encoding
    match = re.search(r"target_url\s*=\s*['\"](?P<url>[^'\"]+)['\"]", wrapper.text)
    if match is None:
        return ""

    target_url = urljoin(wrapper.url, match.group("url"))
    detail = requests.get(target_url, headers=headers, timeout=30)
    detail.raise_for_status()
    detail.encoding = detail.apparent_encoding or detail.encoding
    soup = BeautifulSoup(detail.text, "html.parser")
    title = _clean_name(soup.title.get_text(" ", strip=True) if soup.title else "")
    return detail.url if expected_name in title else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析内嵌leaders对象并继承脚本数组顺序。"""
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for block in _iter_leader_blocks(html):
        name = _clean_name(_extract_object_value(block, "name") or _extract_object_value(block, "title"))
        duty = _clean_text(_extract_js_value(block, "role"))
        wrapper_path = _extract_object_value(block, "url")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue

        detail_url = _resolve_detail_url(urljoin(base_url, wrapper_path), name) if wrapper_path else ""
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": "custom_tianjin_gfdy_embedded_leaders_v1",
                "selector_summary": "内嵌leaders对象name/role/url；包装页target_url在线验证",
            }
        )

    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
