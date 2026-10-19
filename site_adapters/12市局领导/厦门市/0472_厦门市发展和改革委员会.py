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
    "rule_id": "0472",
    "page_type": "人物目录详情页",
    "structure_group": "xm_dpc_leader_directory_profiles_v2",
    "reuse_scope": "single_site",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_dpc_leader_directory_profiles_v2",
    "leader_region_selector": ".tabs_header",
    "name_selector": ".list_base li a[href]",
    "detail_link_selector": ".list_base li a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".article_content",
        "max_detail_links": 20,
    },
    "risk_flag": "入口有多组信息列表；从领导介绍标题定位相邻名单，并在每个详情正文中提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def clean_name(value: str) -> str:
    """清除姓名节点中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导介绍名单顺序抓取各详情正文中的完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    leader_anchor = soup.find("a", string=lambda text: clean_text(text) == "领导介绍")
    leader_header = leader_anchor.find_parent("div", class_="tabs_header") if leader_anchor else None
    leader_list = leader_header.find_next_sibling("div") if leader_header else None
    if leader_list is None:
        return []
    entry_url = final_url or page_rule["url"]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": entry_url})
    records: list[object] = []
    seen: set[str] = set()
    for link in leader_list.select(".list_base li a[href]"):
        name = clean_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        detail_url = urldefrag(urljoin(entry_url, link.get("href", "")))[0]
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        content = detail_soup.select_one(".article_content")
        if content is None:
            raise RuntimeError(f"人物详情正文缺失：{name}")
        detail_text = clean_text(content.get_text(" ", strip=True))
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        if name not in detail_text or evidence_match is None:
            raise RuntimeError(f"人物详情无法核对姓名或现任句：{name}")
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0))
        evidence = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", evidence)
        evidence = re.sub(r"\s*[。.]$", "", evidence).strip()
        seen.add(name)
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
