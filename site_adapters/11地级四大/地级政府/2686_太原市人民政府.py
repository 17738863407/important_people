from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2686",
    "page_type": "人物目录详情页",
    "structure_group": "taiyuan_government_window_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_government_window_profiles_v2",
    "leader_region_selector": ".ldxx",
    "name_selector": ".ldxxleftblock .szjj h1 span, .ldxxrightblock ul li a[href] > p",
    "duty_selector": ".leader_intro .ld_intros",
    "detail_link_selector": ".ldxxleftblock > a[href], .ldxxrightblock ul li a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".leader_intro",
        "max_detail_links": 20,
    },
    "risk_flag": "市长主卡片与常务副市长、副市长列表结构不同，左侧另有机关简介等非人物链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按市长主卡片和右侧分组列表顺序抓取详情页完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    cards = []
    mayor_card = soup.select_one(".mayor-profile[onclick]")
    if mayor_card is not None:
        cards.append((mayor_card, ".mayor-info h2 span"))
    cards.extend((card, ":scope > span") for card in soup.select(".deputy-group .deputy-card[onclick]"))
    for card, name_selector in cards:
        name_node = card.select_one(name_selector)
        name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        onclick = str(card.get("onclick") or "")
        href_match = re.search(r"window\.open\(['\"]([^'\"]+)", onclick)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        if href_match is None:
            continue
        seen.add(name)
        candidates.append((name, urljoin(entry_url, href_match.group(1))))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    for expected_name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        profile = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        name_node = profile.select_one(".ldPics p") if profile else None
        profile_name = _clean_text(name_node.get_text(" ", strip=True)) if name_node else ""
        biography = profile.select_one(".ld_intros") if profile else None
        biography_text = _clean_text(biography.get_text(" ", strip=True)) if biography else ""
        evidence_match = re.search(r"现任[^。]*。", biography_text)
        if profile_name != expected_name or evidence_match is None:
            raise RuntimeError(
                f"目录与详情现任信息无法核对：{expected_name} -> {profile_name or '空'}"
            )
        evidence = re.sub(
            r"^现任(?:职务)?[：:]?",
            "",
            evidence_match.group(0),
            count=1,
        )
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=profile_name,
                duty=evidence,
                detail_url=response.url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
