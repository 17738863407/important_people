from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2833",
    "page_type": "人物目录详情页",
    "structure_group": "taiyuan_people_congress_directory_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "taiyuan_people_congress_directory_details_v2",
    "leader_region_selector": '#right > div[style*="width:240px"]',
    "name_selector": 'a[href] font[color="#000000"]',
    "duty_selector": 'font[color="#005B82"]',
    "detail_link_selector": "a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".greybox.mgt10.js p.content",
        "max_detail_links": 50,
    },
    "risk_flag": "同页包含新闻链接，候选必须同时具备头像和黑色姓名节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _normalize_url(value: str) -> str:
    parsed = urlsplit(value)
    host = parsed.hostname or ""
    port = parsed.port
    if port and not ((parsed.scheme == "https" and port == 443) or (parsed.scheme == "http" and port == 80)):
        host = f"{host}:{port}"
    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导目录顺序发现详情页，并提取当前人物简介中的现任原句。"""
    import requests
    from bs4 import BeautifulSoup, Tag

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    current_group = ""
    candidates: list[tuple[str, str, str]] = []
    for node in region.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name == "font" and str(node.get("color", "")).upper() == "#005B82":
            current_group = _clean_text(node.get_text(" ", strip=True))
            continue
        if node.name != "a" or not current_group or node.find("img") is None:
            continue
        name_node = node.find("font", attrs={"color": "#000000"})
        if name_node is None:
            continue
        name = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", name_node.get_text(" ", strip=True))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            candidates.append((name, current_group, urljoin(entry_url, node["href"])))

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    for name, directory_duty, candidate_url in candidates:
        response = session.get(candidate_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        content = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        detail_text = _clean_text(content.get_text(" ", strip=True)) if content else ""
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        if evidence_match is None:
            raise RuntimeError(f"人物详情正文缺少可验证的现任职务依据：{name}")
        evidence = re.sub(r"^现任\s*", "", re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", evidence_match.group(0))).rstrip("。")
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=_normalize_url(response.url),
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
