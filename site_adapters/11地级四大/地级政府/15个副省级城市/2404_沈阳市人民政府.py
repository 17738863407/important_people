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
    "rule_id": "2404",
    "page_type": "职务分组详情页",
    "structure_group": "shenyang_government_grouped_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "shenyang_government_grouped_profiles_v2",
    "leader_region_selector": ".lm0-main",
    "name_selector": ".list ul.txt li a[href]",
    "duty_selector": ".xsy_rcontent1.artical .view",
    "detail_link_selector": ".list ul.txt li a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".xsy_rcontent1.artical",
        "max_detail_links": 20,
    },
    "risk_flag": "首页存在移动端和桌面端领导名单文本，秘书长分组当前为空；只解析桌面lm0-main实际链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按首页领导分组顺序抓取独立人物页中的完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = next(
        (
            node
            for node in soup.select(page_rule["leader_region_selector"])
            if node.select_one(".title")
            and _clean_text(node.select_one(".title").get_text(" ", strip=True))
            == "市政府领导"
        ),
        None,
    )
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for link in region.select(".list ul.txt li a[href]"):
        name = _clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        seen.add(name)
        candidates.append((name, urljoin(entry_url, link["href"])))

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
        heading = profile.select_one(".sy-lingdao-text2") if profile else None
        heading_parts = (
            [_clean_text(part) for part in heading.stripped_strings if _clean_text(part)]
            if heading
            else []
        )
        biography = profile.select_one(".view") if profile else None
        biography_text = _clean_text(biography.get_text(" ", strip=True)) if biography else ""
        evidence_match = re.search(r"现任[^。]*。", biography_text)
        if not heading_parts or heading_parts[0] != expected_name:
            raise RuntimeError(f"人物详情现任信息无法核对：{expected_name}")
        if evidence_match is not None:
            evidence = evidence_match.group(0).removeprefix("现任").removesuffix("。")
        else:
            evidence = "；".join(heading_parts[1:])
        if not evidence:
            raise RuntimeError(f"人物详情职务字段为空：{expected_name}")
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=expected_name,
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
