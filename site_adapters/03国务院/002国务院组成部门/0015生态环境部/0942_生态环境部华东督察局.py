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
    "rule_id": "0942",
    "domain": "hddc.mee.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "mee_hddc_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_mee_hddc_current_leaders_v1",
    "leader_region_selector": ".ldbaz",
    "name_selector": ".ldbaz_right_top .left b",
    "duty_selector": ".ldbaz_right_top .left中姓名后的文本",
    "detail_link_selector": ".ldbaz_right_top a[href]",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".ldbaz"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "list_anchor",
        "detail_collector_type": "static_http",
        "detail_link_selector": ".ldbaz_right_top a[href]",
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 20,
        "candidate_links": [],
    },
    "risk_flag": "旧脚本依赖快照和旧八列导出；页面注释含历史模板人物，BeautifulSoup真实DOM解析自动排除注释",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "css": {
            "leader_region_selector": ".ldbaz",
            "name_selector": ".ldbaz_right_top .left b",
            "duty_selector": ".ldbaz_right_top .left中姓名后的文本",
            "detail_link_selector": ".ldbaz_right_top a[href]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": [".ldbaz"],
                "exclude_selectors": [],
            },
        },
        "api": {"enabled": False, "reason": "当前原始HTML已静态直出姓名、职务和详情链接"},
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


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按可见领导卡片DOM顺序抽取姓名、原始职务和详情页。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = "strategy=custom_parse_page；leader=.ldbaz；name=.left b；duty=.left姓名后文本；detail=.ldbaz_right_top a[href]"

    for card in soup.select(".ldbaz"):
        field = card.select_one(".ldbaz_right_top .left")
        name_node = field.select_one("b") if field else None
        name = re.sub(r"\s+", "", clean_text(name_node.get_text(" ", strip=True) if name_node else ""))
        combined = clean_text(field.get_text(" ", strip=True) if field else "")
        evidence = clean_text(combined[len(name):]) if combined.startswith(name) else ""
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence or name in seen:
            continue

        detail_url = ""
        link = card.select_one(".ldbaz_right_top a[href]")
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
