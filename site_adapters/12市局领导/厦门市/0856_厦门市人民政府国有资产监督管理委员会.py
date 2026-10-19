from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0856",
    "page_type": "人物列表完整页",
    "structure_group": "xm_sasac_current_detail_chain_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_sasac_current_detail_chain_v2",
    "leader_region_selector": ".leader_content",
    "name_selector": ".leader_content h3",
    "duty_selector": ".tab_base职务 + .article_content",
    "detail_link_selector": ".leader_name_list a[href]",
    "detail_strategy": {"required": True, "mode": "custom_detail_chain"},
    "risk_flag": "入口页是首人详情并列出其余人物；职务必须取职务标签后的强结构原文，不得纳入简介和分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def extract_profile(html: str) -> tuple[str, str]:
    """从单个人物详情页提取姓名及“职务”标签对应的原始内容。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".leader_content")
    if content is None:
        raise RuntimeError("详情页缺少 .leader_content")
    name_node = content.select_one("h3")
    name = clean_text(name_node.get_text(" ", strip=True)) if name_node is not None else ""
    evidence = ""
    for label in content.select(".tab_base"):
        if clean_text(label.get_text(" ", strip=True)) != "职务":
            continue
        value_node = label.find_next_sibling("div", class_="article_content")
        evidence = clean_text(value_node.get_text(" ", strip=True)).removesuffix("。") if value_node is not None else ""
        break
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
        raise RuntimeError("详情页缺少可核对的姓名或职务原文")
    return name, evidence


def fetch_detail(session: requests.Session, detail_url: str) -> str:
    """在线获取一个人物详情页，失败时显式终止当前脚本。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """先解析入口页首人，再按目录顺序解析其余独立人物详情页。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    source_url = page_rule["url"]
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[str, str, str]] = [("", source_url, html)]
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    for link in soup.select(page_rule["detail_link_selector"]):
        name_hint = clean_text(link.get_text(" ", strip=True))
        detail_url = urljoin(source_url, str(link.get("href") or ""))
        candidates.append((name_hint, detail_url, fetch_detail(session, detail_url)))

    records: list[object] = []
    seen: set[str] = set()
    for index, (name_hint, detail_url, detail_html) in enumerate(candidates):
        name, evidence = extract_profile(detail_html)
        if name_hint and name != name_hint:
            raise RuntimeError(f"目录姓名与详情页不一致：{name_hint} != {name}")
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=source_url,
                name=name,
                duty=evidence,
                detail_url="" if index == 0 else detail_url,
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
