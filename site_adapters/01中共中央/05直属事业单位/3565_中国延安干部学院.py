from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


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


def is_hidden(node: Tag) -> bool:
    """排除当前职务组及祖先节点上的明确隐藏状态。"""
    for current in (node, *node.parents):
        if not isinstance(current, Tag):
            continue
        style = str(current.get("style") or "")
        classes = {str(value).lower() for value in current.get("class", [])}
        if current.has_attr("hidden") or str(current.get("aria-hidden") or "").lower() == "true":
            return True
        if re.search(r"display\s*:\s*none", style, flags=re.IGNORECASE):
            return True
        if classes.intersection({"hidden", "hide", "dn", "d-none"}):
            return True
        if "l_con" in classes:
            break
    return False


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.celay.org.cn",
        "page_type": "人物列表完整页",
        "structure_group": "celay_leader_duty_groups_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_duty_group_names",
        "collector": "static_http",
        "parser": "page_celay_leader_duty_groups_v1",
        "leader_region_selector": ".l_con",
        "name_selector": ".leader_con li span",
        "duty_selector": ".leader_title",
        "detail_link_selector": "",
        "content_scope": {
            "include_selectors": [".l_con"],
            "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display:none']", "script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "none",
            "candidate_links": [],
        },
        "risk_flag": "verified_grouped_leader_list_with_hidden_group_exclusion",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".l_con",
                "group_selector": ":scope > .leader",
                "duty_selector": ":scope > .leader_title",
                "name_selector": ":scope > .leader_con li span",
            },
            "api": {"enabled": False, "reason": "静态HTML职务组已直接包含姓名与职务"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按职务组及组内姓名的原始DOM顺序抽取可见领导。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".l_con")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    parser = str(page_rule.get("parser", ""))
    for group in region.select(":scope > .leader"):
        if is_hidden(group):
            continue
        duty_node = group.select_one(":scope > .leader_title")
        duty = re.sub(
            r"\s+",
            "",
            normalize_space(duty_node.get_text(" ", strip=True) if duty_node else ""),
        ).strip(" ：:，,。.")
        if not duty:
            continue
        for name_node in group.select(":scope > .leader_con li span"):
            name = clean_name(name_node.get_text(" ", strip=True))
            if not is_name(name) or name in seen_names:
                continue
            seen_names.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": parser,
                    "selector_summary": "strategy=custom_parse_page；region=.l_con；group=.leader；fields=.leader_title+.leader_con li span",
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
    output_path = run_page_adapter(
        page_rule,
        globals(),
        runtime_context=runtime_context,
        update_fetch_memory=False,
    )
    print(f"实际采集器：{runtime_context.get('actual_collector', '')}")
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "3565"
    main(rule_id_value)
