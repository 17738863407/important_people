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
    "rule_id": "0736",
    "page_type": "人物列表完整页",
    "structure_group": "chengdu_government_leader_cards",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "list_to_detail",
    "collector": "browser_dom_list_and_detail",
    "parser": "custom_parse_page",
    "leader_region_selector": "div.main_r div.html008 ul.list > li.myflex",
    "name_selector": "div.cont",
    "duty_selector": "详情页 #part_03 .content #myFont 内完整现任句或职务标签后首个非空段落",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["div.main_r div.html008 ul.list"],
        "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display: none']"],
    },
    "detail_strategy": {
        "required": True,
        "mode": "custom_list_to_detail",
        "detail_link_selector": "li.myflex[onclick*=window.open]",
        "max_detail_links": 30,
    },
    "risk_flag": "入口及详情页受动态防护保护，使用项目独立Chrome CDP通道；详情页优先提取完整现任句，没有现任句时读取明确职务字段，不采集分工",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "成都市政府信息公开平台同类页面历史上使用该领导区域，本入口当前受防护拦截",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "css",
    "locator": {
        "css": {
            "leader_region_selector": "div.main_r div.html008 ul.list > li.myflex",
            "name_selector": "div.cont",
            "duty_selector": "详情页 #part_03 .content #myFont 内完整现任句或职务标签后首个非空段落",
            "detail_link_selector": "li.myflex[onclick*=window.open]",
            "content_scope": {
                "start_anchor": "",
                "end_anchor": "",
                "include_selectors": ["div.main_r div.html008 ul.list"],
                "exclude_selectors": ["[hidden]", "[aria-hidden='true']", "[style*='display: none']"],
            },
        },
        "api": {
            "enabled": False,
            "reason": "未发现可复现且含领导字段的稳定接口，改用项目独立Chrome CDP通道读取渲染DOM",
        },
    },
}


def clean_text(value: str) -> str:
    """清理页面排版空白，保留姓名中的中间点。"""
    return re.sub(r"\s+", "", value or "").strip()


def clean_evidence(value: str) -> str:
    """清理已经定位到的现职证据，仅删除固定句首标签和句末标点。"""
    evidence = " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())
    evidence = re.sub(r"^(?:现任|职务[：:]?)", "", evidence)
    return evidence.rstrip("。；; ")


def extract_detail_evidence(html: str, expected_name: str) -> str:
    """从当前人物详情页简介块提取现任句，缺失时读取明确职务字段。"""
    soup = BeautifulSoup(html, "html.parser")
    title_node = soup.select_one("#part_03 h1")
    title_name = clean_text(title_node.get_text(" ", strip=True) if title_node else "")
    if title_name != expected_name:
        raise RuntimeError(f"详情页姓名不匹配：列表={expected_name}，详情={title_name or '<空>'}")

    profile = soup.select_one("#part_03 .content #myFont")
    if profile is None:
        raise RuntimeError(f"{expected_name} 详情页未找到简介区域 #myFont")
    profile_text = " ".join(profile.get_text(" ", strip=True).split())
    current_match = re.search(r"现任[^。]*。", profile_text)
    if current_match is not None:
        evidence = clean_evidence(current_match.group(0))
    else:
        evidence = ""
        for paragraph in profile.select("p"):
            if clean_text(paragraph.get_text(" ", strip=True)).rstrip("：:") != "职务":
                continue
            sibling = paragraph.find_next_sibling("p")
            while sibling is not None and not clean_evidence(sibling.get_text(" ", strip=True)):
                sibling = sibling.find_next_sibling("p")
            evidence = clean_evidence(sibling.get_text(" ", strip=True) if sibling else "")
            break
    if not evidence:
        raise RuntimeError(f"{expected_name} 详情页未找到完整现任句或明确职务字段")
    return evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按入口列表顺序进入每个人物详情页，提取现任职务。"""
    from crawler_core.fetcher import fetch_html_with_strategy

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select("div.main_r div.html008 ul.list > li.myflex")
    if not cards:
        raise RuntimeError("未找到领导成员列表 li.myflex")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for card in cards:
        name_node = card.select_one(":scope > div.cont")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        onclick = str(card.get("onclick") or "")
        detail_match = re.search(r"window\.open\(\s*['\"]([^'\"]+)['\"]", onclick)
        if not re.fullmatch(r"[\u4e00-\u9fff\u3400-\u4dbf·]{2,8}", name):
            raise RuntimeError(f"领导姓名格式异常：{name or '<空>'}")
        if not detail_match:
            raise RuntimeError(f"{name} 缺少可验证的 onclick 详情页")
        if name in seen_names:
            raise RuntimeError(f"领导姓名重复：{name}")
        seen_names.add(name)
        detail_url = urljoin(final_url or str(page_rule.get("url") or ""), detail_match.group(1))
        try:
            detail_result = fetch_html_with_strategy(detail_url, strategy="chrome")
            evidence = extract_detail_evidence(detail_result.html, name)
        except Exception as error:
            raise RuntimeError(f"{name} 详情页采集或解析失败：{error}") from error
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "parser": "custom_parse_page",
                "selector_summary": "列表li.myflex；div.cont姓名；onclick详情页；详情#myFont内现任句或职务字段",
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
