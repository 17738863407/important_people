from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def normalize_space(text: str) -> str:
    """清理人物简介中的排版空白，不改变网页原始语义。"""
    value = str(text or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def is_name(text: str) -> bool:
    """仅接受人物简介句首明确出现的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict:
    """构造当前报社编委会页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.ce.cn",
        "page_type": "图片下方人物简介",
        "structure_group": "ce_editorial_board_biography_cards_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "biography_card_last_clause_duty",
        "collector": "static_http",
        "parser": "page_ce_editorial_board_cards_v1",
        "leader_region_selector": ".wrap.con",
        "name_selector": ".picboxa p, .picbox p",
        "duty_selector": ".picboxa p, .picbox p",
        "detail_link_selector": "",
        "content_scope": {
            "include_selectors": [".wrap.con"],
            "exclude_selectors": ["script", "style", ".hide"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "detail_link_selector": "",
            "candidate_links": [],
        },
        "risk_flag": "人物简介与职务同句，按当前人物段落末个逗号后的现职字段提取",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".wrap.con",
                "item_selector": ".picboxa, .picbox",
                "name_selector": "p",
                "duty_selector": "p",
            },
            "api": {"enabled": False, "reason": "静态HTML人物简介已直接包含姓名和完整现职"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按网页人物卡片顺序提取姓名及简介末尾的完整现职字段。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()

    for card in soup.select(".wrap.con .picboxa, .wrap.con .picbox"):
        paragraph = card.select_one("p")
        image = card.select_one("img[src]")
        if paragraph is None or image is None:
            continue

        biography = normalize_space(paragraph.get_text(" ", strip=True))
        name_match = re.match(r"^(?P<name>[\u4e00-\u9fff·]{2,4})[，,]", biography)
        duty_match = re.search(r"[，,](?P<duty>[^，,。]+)[。.]?$", biography)
        if name_match is None or duty_match is None:
            continue

        name = name_match.group("name")
        duty = normalize_space(duty_match.group("duty")).strip("，,。.;； ")
        if not is_name(name) or not duty or name in seen_names:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.wrap.con；"
                    "item=.picboxa,.picbox；fields=p句首姓名+p末个逗号后现职"
                ),
            }
        )
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(page_rule, globals(), runtime_context=runtime_context)
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"尝试链路：{runtime_context.get('attempted_collectors', [])}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3593"
    main(rule_id_value)
