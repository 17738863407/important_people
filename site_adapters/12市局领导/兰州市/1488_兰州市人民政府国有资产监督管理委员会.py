from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "1488",
    "page_type": "人物列表完整页",
    "structure_group": "lanzhou_sasac_leader_links_to_detail_first_duty_clause_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online_orchestrator",
    "parser": "page_lanzhou_sasac_leader_links_to_detail_first_duty_clause_v1",
    "leader_region_selector": ".zfxxgk_subtit + .zfxxgk_subcon",
    "name_selector": ".zfxxgk_subcon a[title]",
    "duty_selector": "人物详情页#zoom开头、职责说明前原始职务短语",
    "detail_link_selector": ".zfxxgk_subcon a[title][href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_list_to_detail",
        "detail_link_selector": ".zfxxgk_subcon a[title][href]",
        "detail_content_selector": "#zoom",
        "max_detail_links": 20,
    },
    "risk_flag": "historical_fixed_duty_map_is_forbidden_and_current_details_mix_duty_with_responsibilities",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_heading_selector": ".zfxxgk_subtit",
            "leader_container_selector": ".zfxxgk_subtit + .zfxxgk_subcon",
            "leader_link_selector": "a[title][href]",
            "detail_content_selector": "#zoom",
        },
        "api": {
            "enabled": False,
            "reason": "当前静态领导列表提供7个动态人物链接，详情页#zoom开头直接包含原始职务和后续职责说明",
        },
    },
}


def normalize_space(text: str) -> str:
    """只清理HTML排版空白及中文标点两侧空格。"""
    cleaned = re.sub(
        r"\s+",
        " ",
        str(text or "").replace("\u3000", " ").replace("\xa0", " "),
    ).strip()
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    return re.sub(r"\s*([、，。；：])\s*", r"\1", cleaned)


def fetch_detail_html(detail_url: str) -> str:
    """通过浏览器降级链路读取受 412 防护的当前人物详情页。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    result = fetch_html_with_strategy(
        detail_url,
        strategy="browser",
        force_browser=True,
        timeout=45,
    )
    return result.html


def extract_detail_duty(detail_html: str, expected_name: str) -> str:
    """校验详情页标题姓名，并取职责说明前的首个原始职务短语。"""
    soup = BeautifulSoup(detail_html, "html.parser")
    title = normalize_space(soup.title.get_text(" ", strip=True)) if soup.title else ""
    container = soup.select_one("#zoom")
    if expected_name not in title or container is None:
        return ""
    text = normalize_space(container.get_text(" ", strip=True))
    duty = normalize_space(re.split(r"[，。]", text, maxsplit=1)[0])
    return duty if re.search(r"书记|主任|副主任|组长|党委委员", duty) else ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """保持领导列表顺序，逐个在线读取详情页原始职务短语。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_heading = next(
        (
            node
            for node in soup.select(".zfxxgk_subtit")
            if normalize_space(node.get_text(" ", strip=True)) == "领导之窗"
        ),
        None,
    )
    leader_container = leader_heading.find_next_sibling(class_="zfxxgk_subcon") if leader_heading else None
    if leader_container is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for link in leader_container.select("a[title][href]"):
        name = re.sub(r"\s+", "", normalize_space(str(link.get("title", ""))))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or name in seen_names:
            continue
        detail_url = urljoin(final_url, str(link.get("href", "")).strip())
        try:
            duty = extract_detail_duty(fetch_detail_html(detail_url), name)
        except RuntimeError:
            continue
        if not duty:
            continue
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "领导之窗列表动态姓名链接；详情页标题校验姓名；#zoom开头首个职责性逗号/句号前原始职务短语",
            }
        )
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
