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
    "rule_id": "0212",
    "page_type": "人物目录详情页",
    "structure_group": "changchun_government_merged_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "changchun_government_merged_profiles_v2",
    "leader_region_selector": "div.zc_zfld",
    "name_selector": "div.zc_ldjs h2 a[href]",
    "duty_selector": "div.zc_ldjs h3",
    "detail_link_selector": "div.zc_ldjs h2 a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_matching_profile_block",
        "detail_profile_selector": ".fsz_jl",
        "detail_heading_selector": "dt.xyh_fsz h2",
        "detail_content_selector": ".mqj_fszgrjl",
        "max_detail_links": 50,
    },
    "risk_flag": "详情响应包含全部人物档案，必须按当前姓名定位对应.fsz_jl块后提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _compact(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value)


def _find_profile_block(soup: object, name: str, page_rule: dict) -> object | None:
    strategy = page_rule["detail_strategy"]
    for block in soup.select(strategy["detail_profile_selector"]):
        headings = block.select(strategy["detail_heading_selector"])
        heading_text = _compact(" ".join(node.get_text(" ", strip=True) for node in headings))
        if name in heading_text:
            return block
    return None


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按首页卡片顺序发现人物，并在合并详情中定位当前人物档案块。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in region.select("div.zc_ldjs h2 a[href]"):
        name = _compact(link.get_text(" ", strip=True))
        if name in seen or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        seen.add(name)
        candidates.append((name, urljoin(entry_url, link["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    for name, detail_url in candidates:
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        profile = _find_profile_block(detail_soup, name, page_rule)
        content = (
            profile.select_one(page_rule["detail_strategy"]["detail_content_selector"])
            if profile is not None
            else None
        )
        detail_text = _clean_text(content.get_text(" ", strip=True)) if content else ""
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        if evidence_match is None:
            raise RuntimeError(f"人物详情正文缺少可验证的现任职务依据：{name}")
        evidence = _compact(evidence_match.group(0))
        evidence = re.sub(r"^现任\s*", "", evidence)
        evidence = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", evidence)
        evidence = re.sub(r"[。.]$", "", evidence).strip()
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
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
