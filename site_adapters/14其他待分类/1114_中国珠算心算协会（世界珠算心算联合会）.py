from __future__ import annotations

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
    "rule_id": "1114",
    "page_type": "协会领导机构卡片页",
    "structure_group": "association_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "custom_zhzsxsxh_leader_cards_v1",
    "leader_region_selector": "#intro3tab1cont",
    "name_selector": ".top .name, .list .name",
    "duty_selector": ".job, .bot .name",
    "detail_link_selector": "a[href*='/detail/']",
    "content_scope": {
        "start_anchor": "#introduction3tab1",
        "end_anchor": "#introduction3tab2",
        "include_selectors": ["#intro3tab1cont"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导机构卡片与历任领导位于同一页面，需限定现任标签页",
    "confidence": "high",
    "profile_reusable": False,
    "profile_judgement": "已核验现任领导机构卡片结构",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "#intro3tab1cont",
            "name_selector": ".top .name, .list .name",
            "duty_selector": ".job, .bot .name",
            "detail_link_selector": "a[href*='/detail/']",
            "content_scope": {
                "start_anchor": "#introduction3tab1",
                "end_anchor": "#introduction3tab2",
                "include_selectors": ["#intro3tab1cont"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "现任领导姓名与职务直接呈现在HTML卡片中"},
        "migration": {"verified_status": "verified"},
    },
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def load_detail_duty(detail_url: str) -> str:
    """从人物详情页的“职务”字段补全列表卡片可能被省略的职务文本。"""
    response = requests.get(detail_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    detail_soup = BeautifulSoup(response.text, "html.parser")
    text = clean_text(detail_soup.get_text(" ", strip=True))
    match = re.search(r"职务：\s*(.*?)(?:\s+世界珠心算网|\s+办公地址：|$)", text)
    return clean_text(match.group(1)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析协会现任领导机构标签页中的卡片顺序、职务和详情链接。"""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#intro3tab1cont")
    if root is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for card in root.select(".top, .list .li"):
        link = card.select_one("a[href*='/detail/']")
        if link is None:
            continue
        name_node = card.select_one(".name")
        if name_node is None:
            continue
        text = clean_text(name_node.get_text(" ", strip=True))
        duty_node = card.select_one(".job")
        if duty_node is not None:
            duty = clean_text(duty_node.get_text(" ", strip=True)).rstrip("：:")
            name = text
        else:
            match = re.match(r"^(.*?)[：:]?\s*([\u4e00-\u9fff]{2,4})$", text)
            if match is None:
                continue
            duty, name = match.group(1).rstrip("：:").strip(), match.group(2)
        if not duty or not re.fullmatch(r"[\u4e00-\u9fff]{2,4}", name) or name in seen:
            continue
        seen.add(name)
        detail_url = urljoin(final_url, link.get("href", ""))
        detail_duty = load_detail_duty(detail_url)
        if detail_duty:
            duty = detail_duty
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#intro3tab1cont现任卡片：.job/.name + detail链接",
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
