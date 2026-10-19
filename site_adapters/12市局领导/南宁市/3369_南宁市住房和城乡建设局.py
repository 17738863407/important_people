from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3369",
    "page_type": "人物目录详情页",
    "structure_group": "nanning_housing_leader_list_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_http",
    "parser": "page_nanning_housing_leader_list_detail_v2",
    "leader_region_selector": ".main a[href*='/ldfg/t'], .main a[href^='./t']",
    "name_selector": "领导目录人物链接文本",
    "duty_selector": "详情页#contentText内完整现任句",
    "detail_link_selector": ".main a[href*='/ldfg/t'], .main a[href^='./t']",
    "detail_strategy": {"required": True, "mode": "online_detail", "max_detail_links": 50},
    "risk_flag": "列表页仅提供姓名；必须在线抓取每个独立详情页，并在正文边界内提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".main a[href*='/ldfg/t'], .main a[href^='./t']",
            "name_selector": "人物链接文本",
            "duty_selector": "#contentText内完整现任句",
            "detail_link_selector": "同一人物链接href",
        },
        "api": {"enabled": False, "reason": "领导目录和详情正文均由静态HTML直接提供"},
    },
}


def normalize_layout(text: str) -> str:
    value = re.sub(r"[\s\u3000\u00a0\u2002-\u200b]+", " ", str(text or "")).strip()
    return re.sub(r"\s*([、，。；：（）])\s*", r"\1", value)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.select(".main a[href*='/ldfg/t'], .main a[href^='./t']")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in anchors:
        name = re.sub(r"[\s\u3000\u00a0]+", "", anchor.get_text(" ", strip=True))
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) is None or name in seen:
            continue
        detail_url = urljoin(final_url, str(anchor.get("href", "")).strip())
        if not detail_url or detail_url == final_url:
            raise RuntimeError(f"人物{name}缺少可验证的独立详情页链接")
        detail_result = fetch_html_with_strategy(detail_url, "requests")
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        content = detail_soup.select_one("#contentText")
        if content is None:
            raise RuntimeError(f"人物{name}详情页缺少#contentText正文")
        detail_text = normalize_layout(content.get_text(" ", strip=True))
        duty_match = re.search(r"现任[^。]*。", detail_text)
        if duty_match is None:
            raise RuntimeError(f"人物{name}详情正文未找到完整现任句")
        evidence = duty_match.group(0).removeprefix("现任").strip().removesuffix("。")
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_result.final_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "目录人物链接按DOM顺序；在线详情#contentText完整现任句",
            }
        )
    if not rows:
        raise RuntimeError("领导目录未提取到有效人物链接")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
