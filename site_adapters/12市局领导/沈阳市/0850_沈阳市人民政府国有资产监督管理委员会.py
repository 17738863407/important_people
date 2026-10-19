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
    "rule_id": "0850", "page_type": "人物列表完整页", "structure_group": "shenyang_sasac_department_details_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_sasac_department_details_v2",
    "leader_region_selector": "部门领导标题后的ul.xxgk_rul",
    "name_selector": "部门领导列表a[href*=bmld]", "duty_selector": ".node__content.artical中包含当前姓名和机构的p",
    "detail_link_selector": "部门领导列表a[href*=bmld]",
    "detail_strategy": {"required": True, "mode": "limited_inline_detail", "max_detail_links": 50},
    "risk_flag": "详情人物节点为机构、原始职务和姓名的完整一行；必须原样保留该节点并排除后续工作分工",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def compact_name(value: str) -> str:
    """清除姓名节点中的展示空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def find_leader_links(html: str, source_url: str) -> list[tuple[str, str]]:
    """按“部门领导”列表DOM顺序取得姓名和详情链接。"""
    soup = BeautifulSoup(html or "", "html.parser")
    title = soup.find("span", string=lambda text: bool(text and "部门领导" in text))
    title_box = title.find_parent("div") if title is not None else None
    list_node = title_box.find_next_sibling("ul") if title_box is not None else None
    if list_node is None:
        raise RuntimeError("未定位到部门领导列表")
    links: list[tuple[str, str]] = []
    for link in list_node.select("a[href]"):
        href = clean_text(link.get("href", ""))
        if "bmld/" not in href:
            continue
        name = compact_name(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            raise RuntimeError("部门领导列表姓名异常")
        links.append((name, urljoin(source_url, href)))
    if not links:
        raise RuntimeError("部门领导列表没有有效详情链接")
    return links


def extract_person_line(html: str, name: str, organization: str) -> str:
    """提取详情正文中包含当前姓名与机构的完整原始人物节点。"""
    soup = BeautifulSoup(html or "", "html.parser")
    matches: list[str] = []
    for node in soup.select(".node__content.artical p"):
        text = clean_text(node.get_text(" ", strip=True))
        if organization in text and name in compact_name(text):
            matches.append(text)
    if len(matches) != 1:
        raise RuntimeError(f"详情人物节点命中数量异常：{name}={len(matches)}")
    return matches[0]


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """顺序抓取部门领导详情并保留完整原始人物节点。"""
    from crawler_core.fetcher import fetch_online_html_with_fallback
    from crawler_core.models import PersonRecord

    source_url = final_url or page_rule["url"]
    organization = page_rule["organization"]
    records: list[object] = []
    seen_names: set[str] = set()
    for name, detail_url in find_leader_links(html, source_url):
        if name in seen_names:
            raise RuntimeError(f"部门领导姓名重复：{name}")
        detail_html = fetch_online_html_with_fallback(detail_url).html
        evidence = extract_person_line(detail_html, name, organization)
        name_pattern = r"\s*".join(re.escape(character) for character in name)
        evidence = re.sub(rf"\s*{name_pattern}\s*$", "", evidence).strip()
        seen_names.add(name)
        records.append(PersonRecord(organization=organization, url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
