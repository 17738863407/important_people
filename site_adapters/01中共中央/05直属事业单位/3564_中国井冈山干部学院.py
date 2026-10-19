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
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    """删除姓名节点中的纯排版空白。"""
    return re.sub(r"\s+", "", normalize_space(text))


def is_name(text: str) -> bool:
    """仅接受页面强结构姓名字段中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.celaj.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "celaj_leader_mixed_list_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_mixed_cards_and_grouped_names",
        "collector": "static_http",
        "parser": "page_celaj_leader_mixed_list_v1",
        "leader_region_selector": ".LeaderList > dl",
        "name_selector": "dd > h3, dd > ul > li",
        "duty_selector": "dd > p, dd > ul > li > span.name",
        "detail_link_selector": "",
        "content_scope": {
            "include_selectors": [".LeaderList > dl"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "candidate_links": [],
        },
        "risk_flag": "verified_mixed_direct_and_grouped_leader_list",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".LeaderList > dl",
                "direct_item_selector": ":scope > dd:has(> h3)",
                "group_item_selector": ":scope > dd > ul > li",
                "direct_name_selector": ":scope > h3",
                "direct_duty_selector": ":scope > p",
                "group_duty_selector": ":scope > span.name",
            },
            "api": {"enabled": False, "reason": "静态HTML人物区已直接包含姓名与职务"},
        },
    }


def append_row(rows: list[dict[str, str]], seen_names: set[str], name: str, duty: str, parser: str) -> None:
    """按页面顺序追加一条经过强结构校验的人物记录。"""
    clean_person_name = clean_name(name)
    clean_duty = normalize_space(duty).strip(" ：:，,。.")
    if not is_name(clean_person_name) or not clean_duty or clean_person_name in seen_names:
        return
    seen_names.add(clean_person_name)
    rows.append(
        {
            "name": clean_person_name,
            "duty": clean_duty,
            "evidence": clean_duty,
            "detail_url": "",
            "parser": parser,
            "selector_summary": "strategy=custom_parse_page；region=.LeaderList>dl；fields=p+h3或li>span.name+姓名文本",
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按人物区混合结构的原始DOM顺序抽取姓名与职务。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".LeaderList > dl")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    parser = str(page_rule.get("parser", ""))
    for item in region.find_all("dd", recursive=False):
        name_node = item.find("h3", recursive=False)
        duty_node = item.find("p", recursive=False)
        if name_node is not None and duty_node is not None:
            append_row(rows, seen_names, name_node.get_text(" ", strip=True), duty_node.get_text(" ", strip=True), parser)
            continue

        for list_item in item.select(":scope > ul > li"):
            group_duty_node = list_item.select_one(":scope > span.name")
            if group_duty_node is None:
                continue
            duty = group_duty_node.get_text(" ", strip=True)
            full_text = list_item.get_text(" ", strip=True)
            names_text = full_text[len(duty) :].strip(" ：:，,。.") if full_text.startswith(duty) else ""
            for name in re.split(r"[、，,\s]+", names_text):
                append_row(rows, seen_names, name, duty, parser)
    return rows


def main(rule_id: str) -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    page_rule = build_page_rule(rule_id)
    runtime_context: dict[str, object] = {}
    output_path = run_page_adapter(
        page_rule,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3564"
    main(rule_id_value)
