from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"\s+", "", normalize_space(text))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "jyt.hubei.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "list_direct",
        "parser": "page_hubei_education_leader_h4_cards_v1",
        "leader_region_selector": ".leader li a[href] h4",
        "name_selector": "h4 text prefix",
        "duty_selector": "h4 text suffix",
        "detail_link_selector": ".leader li a[href]",
        "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
        "detail_strategy": {"required": False, "mode": "none"},
        "risk_flag": "",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".leader li a[href] h4",
                "name_selector": "h4 text prefix",
                "duty_selector": "h4 text suffix",
                "detail_link_selector": ".leader li a[href]",
                "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
            },
            "api": {"enabled": False, "reason": "官网当前 HTML 领导卡片标题已包含姓名和职务"},
        },
    }


def extract_row(line: str) -> tuple[str, str] | None:
    text = normalize_space(line)
    match = re.match(r"^(.{2,8}?)\s+(省委|省教育厅|省纪委|省政府|正厅长级).+$", text)
    if not match:
        return None
    name = clean_name(match.group(1))
    duty = normalize_space(text[len(match.group(1)) :])
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        return None
    return name, duty


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    base_url = final_url or str(page_rule.get("url", ""))
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for link in soup.select(".leader li a[href]"):
        h4 = link.select_one("h4")
        if not h4:
            continue
        result = extract_row(h4.get_text(" ", strip=True))
        if not result:
            continue
        name, duty = result
        if name in seen:
            continue
        seen.add(name)
        detail_url = urldefrag(urljoin(base_url, link.get("href", "").strip())).url
        parsed = urlsplit(detail_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or detail_url.rstrip("/") == base_url.rstrip("/"):
            detail_url = ""
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.leader li a h4；field=姓名+职务标题",
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
    output_path = run_page_adapter(page_rule, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    rule_id_value = "1334"
    main(rule_id_value)
