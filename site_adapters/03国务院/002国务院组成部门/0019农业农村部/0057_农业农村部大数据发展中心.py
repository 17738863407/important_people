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


PAGE_RULE = {
    "rule_id": "0057",
    "domain": "www.abdc.org.cn",
    "page_type": "人物列表完整页",
    "structure_group": "abdc_leader_paragraphs",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_abdc_leader_paragraphs_v1",
    "leader_region_selector": "div.dsj_details div.TRS_Editor",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.dsj_details div.TRS_Editor"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": "",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
        "candidate_links": [],
    },
    "risk_flag": "姓名内部存在排版空格；需排除隐藏DOM和空白段落",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.dsj_details div.TRS_Editor",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["div.dsj_details div.TRS_Editor"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "当前静态HTML正文已直接提供领导姓名与职务段落",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白，不改变原始语义。"""
    text = (value or "").replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def is_hidden_node(node: Tag) -> bool:
    """检查当前节点及祖先是否为隐藏DOM。"""
    current: Tag | None = node
    while current is not None:
        style = str(current.get("style", "")).replace(" ", "").lower()
        classes = {str(item).lower() for item in (current.get("class") or [])}
        if "display:none" in style or current.has_attr("hidden"):
            return True
        if str(current.get("aria-hidden", "")).lower() == "true":
            return True
        if classes & {"hide", "hidden", "dn", "none"}:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def parse_line(value: str) -> tuple[str, str]:
    """按页面明确职务词边界拆分姓名与原始职务。"""
    text = clean_text(value)
    match = re.search(r"中心主任|中心副主任|党总支书记|副主任|主任", text)
    if not match:
        return "", ""

    name = clean_text(text[: match.start()]).replace(" ", "")
    evidence = clean_text(text[match.start() :])
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
        return "", ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按可见领导段落的DOM原始顺序抽取人物。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    selector_summary = "strategy=custom_parse_page；leader=div.dsj_details div.TRS_Editor；item=p"

    for node in soup.select("div.dsj_details div.TRS_Editor p"):
        if is_hidden_node(node):
            continue
        name, evidence = parse_line(node.get_text(" ", strip=True))
        key = (name, evidence)
        if not name or not evidence or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": evidence,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": selector_summary,
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
