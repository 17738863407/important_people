from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0095",
    "page_type": "人物目录详情页",
    "structure_group": "xm_data_leader_directory_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "page_detail_xm_data_leader_intro_v2",
    "leader_region_selector": "table.tab1",
    "name_selector": "td.pad_l25 a[href]",
    "detail_link_selector": "td.pad_l25 a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "list_to_detail_first_paragraph",
        "detail_content_selector": "div.xl_con1.trsContent, div.TRS_Editor",
        "max_detail_links": 30,
    },
    "risk_flag": "详情正文同时包含简历与分工；依据说明只取与目录姓名匹配的首个原始职务段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白，不改写职务语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """清除姓名节点中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录顺序抓取详情页首个“姓名＋职务”段落。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        return []

    entry_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    seen: set[str] = set()
    for link in region.select(page_rule["detail_link_selector"]):
        name = clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        detail_url = urldefrag(urljoin(entry_url, link.get("href", "")))[0]
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        content = detail_soup.select_one("div.xl_con1.trsContent") or detail_soup.select_one(
            "div.TRS_Editor"
        )
        if content is None:
            raise RuntimeError(f"人物详情页正文缺失：{name}")
        evidence = next(
            (
                clean_text(paragraph.get_text(" ", strip=True))
                for paragraph in content.select("p")
                if clean_text(paragraph.get_text(" ", strip=True))
            ),
            "",
        )
        duty_match = re.fullmatch(rf"{re.escape(name)}\s+(?P<duty>.+)", evidence)
        if duty_match is None:
            raise RuntimeError(f"人物详情页首段无法核对姓名与职务：{name}")
        duty = clean_text(duty_match.group("duty"))
        if not duty:
            raise RuntimeError(f"人物详情页职务为空：{name}")
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=duty,
                detail_url=response.url,
                evidence=duty,
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
