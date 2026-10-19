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
    "rule_id": "1469",
    "domain": "lyj.fj.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "fujian_forestry_leader_window_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "static_http",
    "parser": "page_inline_fujian_forestry_leader_window_v1",
    "leader_region_selector": ".ldzc-box",
    "name_selector": "h5",
    "duty_selector": ".wop-det现任句, h5 + p",
    "detail_link_selector": ".wop-det a[href], li > a[href]",
    "detail_strategy": {
        "required": False,
        "mode": "current_profile_and_card_links",
    },
    "risk_flag": "首人位于个人简历块，须限定同一块提取完整现任句；其余人物为h5/p卡片",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def normalize_space(value: str) -> str:
    """确定性压缩HTML排版空白。"""
    return re.sub(r"[\s\u3000\u00a0]+", " ", str(value or "")).strip()


def clean_name(value: str) -> str:
    return re.sub(r"[\s\u3000\u00a0]+", "", str(value or ""))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按首人简介块和其余领导卡片的网页顺序抽取。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(str(page_rule["leader_region_selector"]))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    profile = region.select_one(".wop-nr")
    if profile is not None:
        name_node = profile.select_one("h5")
        text_node = profile.select_one(".wop-det")
        link = text_node.select_one("a[href]") if text_node else None
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        profile_text = normalize_space(text_node.get_text(" ", strip=True) if text_node else "")
        sentence_match = re.search(r"现任[^。]*。", profile_text)
        if re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) and sentence_match is not None:
            evidence = sentence_match.group(0).removeprefix("现任").removesuffix("。").strip()
            seen.add(name)
            rows.append(
                {
                    "name": name,
                    "duty": evidence,
                    "evidence": evidence,
                    "detail_url": urljoin(final_url, str(link.get("href") or "")) if link else "",
                }
            )

    for link in region.select("li > a[href]"):
        name_node = link.select_one("h5")
        duty_node = link.select_one("p")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node else "")
        evidence = normalize_space(duty_node.get_text(" ", strip=True) if duty_node else "")
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,10}", name) or not evidence or name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": urljoin(final_url, str(link.get("href") or "")),
            }
        )
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
