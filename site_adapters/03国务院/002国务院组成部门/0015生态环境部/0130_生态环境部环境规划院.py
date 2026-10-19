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


PAGE_RULE = {
    "rule_id": "0130",
    "domain": "www.caep.org.cn",
    "page_type": "人物列表完整页",
    "structure_group": "caep_current_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_caep_current_leaders_v1",
    "leader_region_selector": "div.company-leader",
    "name_selector": ".dean .leader-name, ul li .name a",
    "duty_selector": ".dean .leader-title, ul li .title",
    "detail_link_selector": ".dean .leader-name, ul li .name a",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.company-leader .dean", "div.company-leader ul li"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_anchor",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".dean .leader-name, ul li .name a",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
        "candidate_links": [],
    },
    "risk_flag": "站点HTTPS证书主机名不匹配且online编排页面版本缺少卡片，需保留原始HTTP响应；首张名誉院长卡片含长篇简介，依据仅取leader-title职务节点",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": "div.company-leader",
            "name_selector": ".dean .leader-name, ul li .name a",
            "duty_selector": ".dean .leader-title, ul li .title",
            "detail_link_selector": ".dean .leader-name, ul li .name a",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["div.company-leader .dean", "div.company-leader ul li"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前HTML已静态直出姓名、职务和独立人物链接"},
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "verified_online",
            "behavior_changed": True,
        },
    },
}


def clean_text(value: str) -> str:
    """确定性清理HTML排版空白及中文标点周边空格。"""
    text = re.sub(r"\s+", " ", (value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()
    text = re.sub(r"\s+([，、；。])", r"\1", text)
    return re.sub(r"([，、；。])\s+", r"\1", text)


def find_name_link(name_node) -> object | None:
    """取得姓名字段所属的详情链接节点。"""
    if name_node is None:
        return None
    if name_node.name == "a" and name_node.get("href"):
        return name_node
    return name_node.find_parent("a", href=True)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按现任领导卡片的原始DOM顺序抽取姓名、职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=div.company-leader；item=.dean, ul li"

    for card in soup.select("div.company-leader .dean, div.company-leader ul li"):
        name_node = card.select_one(".leader-name") or card.select_one(".name a")
        duty_node = card.select_one(".leader-title") or card.select_one(".title")
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen:
            continue

        detail_url = ""
        link = find_name_link(name_node)
        href = str(link.get("href", "")).strip() if link else ""
        if href and not href.lower().startswith(("#", "javascript:", "mailto:")):
            candidate = urljoin(final_url, href)
            if candidate.rstrip("/") != final_url.rstrip("/"):
                detail_url = candidate

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
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
