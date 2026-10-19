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


PAGE_RULE = {
    "rule_id": "3098",
    "domain": "xxzx.mca.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "mca_info_center_navigation_leader_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_mca_info_center_leader_v2",
    "leader_region_selector": ".jgsz_zxld",
    "name_selector": ".jgsz_zxld p > strong",
    "duty_selector": ".jgsz_zxld p中strong后的文本",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "中心领导",
        "end_anchor": "组织机构页内设机构",
        "include_selectors": [".jgsz_zxld"],
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
    "risk_flag": "只解析组织机构页中的中心领导区域，排除内设机构",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".jgsz_zxld",
            "name_selector": "",
            "duty_selector": "",
            "detail_link_selector": "",
            "content_scope": {
                "start_anchor": "中心领导",
                "end_anchor": "内设机构",
                "include_selectors": [".jgsz_zxld"],
                "exclude_selectors": [],
            },
        },
        "api": {
            "enabled": False,
            "reason": "组织机构页静态HTML直接提供中心领导段落",
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
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"([、，；：])\s+", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """直接按组织机构页的中心领导段落原始顺序提取。"""
    soup = BeautifulSoup(html, "html.parser")
    leader_region = soup.select_one(page_rule["leader_region_selector"])
    if leader_region is None:
        raise RuntimeError("组织机构页未找到中心领导区域")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "leader=.jgsz_zxld；item=p；name=strong；duty=strong后原文"

    for item in leader_region.select("p"):
        name_node = item.select_one(":scope > strong")
        if name_node is None:
            continue
        name = clean_text(name_node.get_text(" ", strip=True)).rstrip("：:").replace(" ", "")
        name_node.extract()
        evidence = clean_text(item.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen:
            continue
        seen.add(name)
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
    if not rows:
        raise RuntimeError("中心领导区域未解析到合规姓名和现任职务")
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
