from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0400",
    "domain": "da.jiangsu.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "jiangsu_drug_leader_sidebar_with_current_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_jiangsu_drug_leader_sidebar_with_current_profile_v2",
    "detail_strategy": {"required": False, "mode": "inline_with_verified_links"},
    "risk_flag": "普通固定请求头可能403；当前人物右侧职务比左侧列表更完整；首人链接与入口同址",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """清理中文页面的排版空白。"""
    text = re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()
    return re.sub(r"\s*([、，,；;：:])\s*", r"\1", text)


def compact_name(value: str) -> str:
    """移除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def canonical_url(value: str) -> str:
    """移除查询、片段和末尾斜杠，供同址判断使用。"""
    parts = urlsplit(value)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, "", ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """继承左侧领导列表顺序，并用当前右侧详情字段校正同名人物职务。"""
    soup = BeautifulSoup(html, "html.parser")
    current_name_node = soup.select_one(".sjld_pic b")
    current_duty_node = soup.select_one(".sjld_pic p")
    current_name = compact_name(current_name_node.get_text(" ", strip=True) if current_name_node else "")
    current_duty = clean_text(current_duty_node.get_text(" ", strip=True) if current_duty_node else "")
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select(".sjld2022_l li"):
        link = item.select_one("a[href]")
        duty_node = item.select_one("span")
        if link is None or duty_node is None:
            continue
        name = compact_name(link.get_text(" ", strip=True))
        duty = clean_text(duty_node.get_text(" ", strip=True)).replace(" ", "")
        if name == current_name and current_duty:
            duty = current_duty.replace(" ", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
            continue
        profile_url = urljoin(final_url, str(link.get("href", "")))
        same_as_entry = canonical_url(profile_url) == canonical_url(
            str(page_rule.get("url", "")) or final_url
        )
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "" if same_as_entry else profile_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；list=.sjld2022_l li；"
                    "fields=a-name+span-duty；current=.sjld_pic b+p；detail=a[href]"
                ),
            }
        )

    return records


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
