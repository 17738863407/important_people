from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

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
    """清理姓名排版空白及页面独立的兼任标记。"""
    name = re.sub(r"\s+", "", normalize_space(text))
    return re.sub(r"[（(]兼[）)]$", "", name)


def clean_duty(text: str) -> str:
    """清理职务标题中的排版空白和字段分隔符。"""
    return re.sub(r"\s+", "", normalize_space(text)).strip("：:")


def is_name(text: str) -> bool:
    """仅接受领导表格强结构姓名单元格中的常见中文姓名形式。"""
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", text))


def build_page_rule(rule_id: str) -> dict:
    """构造当前页面经过在线核验的技术规则。"""
    return {
        "rule_id": rule_id,
        "domain": "www.chinapeace.gov.cn",
        "page_type": "领导职务分组表格",
        "structure_group": "chinapeace_ld_bg_table_2026",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "duty_heading_multi_name",
        "collector": "static_http",
        "parser": "page_chinapeace_leader_table_v1",
        "leader_region_selector": "table.ld_bg",
        "name_selector": "tr td:not(.td01) a",
        "duty_selector": "tr td.td01",
        "detail_link_selector": "tr td:not(.td01) a[href]",
        "content_scope": {
            "include_selectors": ["table.ld_bg"],
            "exclude_selectors": ["script", "style"],
        },
        "detail_strategy": {
            "required": False,
            "mode": "direct_name_link",
            "detail_link_selector": "td:not(.td01) a[href]",
            "candidate_links": [],
        },
        "risk_flag": "verified_duty_heading_multi_name_table",
        "confidence": "high",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": "table.ld_bg",
                "item_selector": "tr",
                "name_selector": "td:not(.td01) a",
                "duty_selector": "td.td01",
                "detail_link_selector": "td:not(.td01) a[href]",
            },
            "api": {"enabled": False, "reason": "静态HTML领导表格已直接包含职务分组、姓名和可用详情链接"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按领导表格原始顺序抽取，并合并同一人物在不同职务行中的现职。"""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.ld_bg")
    if table is None:
        return []

    rows: list[dict[str, str]] = []
    name_to_index: dict[str, int] = {}
    for table_row in table.select("tr"):
        duty_node = table_row.select_one("td.td01")
        if duty_node is None:
            continue
        duty = clean_duty(duty_node.get_text(" ", strip=True))
        if not duty:
            continue

        for name_link in table_row.select("td:not(.td01) a"):
            name = clean_name(name_link.get_text(" ", strip=True))
            if not is_name(name):
                continue
            href = normalize_space(str(name_link.get("href", "")))
            detail_url = urljoin(final_url, href) if href else ""
            if name in name_to_index:
                existing = rows[name_to_index[name]]
                duties = existing["duty"].split("；")
                if duty not in duties:
                    existing["duty"] = f'{existing["duty"]}；{duty}'
                    existing["evidence"] = existing["duty"]
                if not existing["detail_url"] and detail_url:
                    existing["detail_url"] = detail_url
                continue

            name_to_index[name] = len(rows)
            rows.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": detail_url,
                    "parser": str(page_rule.get("parser", "")),
                    "selector_summary": "strategy=custom_parse_page；region=table.ld_bg；item=tr；fields=td.td01+姓名链接",
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
    rule_id_value = "3552"
    main(rule_id_value)
