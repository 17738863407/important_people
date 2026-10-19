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
    return re.sub(r"\s+", " ", str(text or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(text: str) -> str:
    return re.sub(r"[\s\u200b]+", "", normalize_space(text))


def clean_duty(text: str) -> str:
    duty = normalize_space(text)
    duty = re.sub(r"\s+([、，,）)])", r"\1", duty)
    duty = re.sub(r"([（(、，,])\s+", r"\1", duty)
    return duty.rstrip("。.")


def is_name(text: str) -> bool:
    return bool(re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", clean_name(text)))


def split_h4_text(text: str) -> tuple[str, str]:
    parts = [normalize_space(part) for part in re.split(r"[\r\n]+", str(text or "")) if normalize_space(part)]
    if len(parts) < 2:
        return "", ""
    return clean_name(parts[0]), clean_duty(" ".join(parts[1:]))


def build_page_rule(rule_id: str) -> dict:
    return {
        "rule_id": rule_id,
        "domain": "kjt.hubei.gov.cn",
        "page_type": "人物列表完整页",
        "structure_group": "",
        "reuse_scope": "single_page",
        "load_mode": "静态HTML直出",
        "fetch_mode": "online",
        "extract_mode": "leader_card_h4_direct",
        "parser": "page_hubei_science_leader_h4_cards_v1",
        "leader_region_selector": ".leader ul.list-p",
        "name_selector": ".leader ul.list-p li h4 line 1",
        "duty_selector": ".leader ul.list-p li h4 line 2",
        "detail_link_selector": ".leader ul.list-p li a[href]",
        "content_scope": {
            "start_anchor": "",
            "end_anchor": "",
            "include_selectors": [".leader ul.list-p"],
            "exclude_selectors": [],
        },
        "detail_strategy": {"required": False, "mode": "none"},
        "risk_flag": "",
        "confidence": "high",
        "profile_reusable": "",
        "profile_judgement": "",
        "filter_policy": "strong_no_wordlist",
        "locator_strategy": "custom_parse_page",
        "locator": {
            "css": {
                "leader_region_selector": ".leader ul.list-p",
                "name_selector": ".leader ul.list-p li h4 line 1",
                "duty_selector": ".leader ul.list-p li h4 line 2",
                "detail_link_selector": ".leader ul.list-p li a[href]",
                "content_scope": {
                    "start_anchor": "",
                    "end_anchor": "",
                    "include_selectors": [".leader ul.list-p"],
                    "exclude_selectors": [],
                },
            },
            "api": {"enabled": False, "reason": "领导信息页 h4 直接列出姓名和职务"},
        },
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".leader ul.list-p")
    if region is None:
        return []

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for item in region.select("li"):
        h4 = item.select_one("h4")
        if h4 is None:
            continue
        name, duty = split_h4_text(h4.get_text("\n", strip=True))
        if not is_name(name) or name in seen_names or not duty or len(duty) > 120:
            continue

        link = item.select_one("a[href]")
        detail_url = urldefrag(urljoin(final_url, link.get("href", ""))).url if link else ""
        parsed = urlsplit(detail_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or detail_url.rstrip("/") == final_url.rstrip("/"):
            detail_url = ""
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "strategy=custom_parse_page；region=.leader ul.list-p；fields=li h4 line1/line2；detail_chain=0",
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
    rule_id_value = "1380"
    main(rule_id_value)
