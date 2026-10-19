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
    "rule_id": "3086",
    "page_type": "人物列表完整页",
    "structure_group": "xm_gov_office_primary_leader_chain_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_gov_office_primary_leader_chain_v2",
    "leader_region_selector": ".con_r",
    "name_selector": "主要领导标题后的.list a[href]",
    "duty_selector": "详情页.TRS_Editor内完整现任句",
    "detail_link_selector": "主要领导标题后的.list a[href]",
    "detail_strategy": {"required": True, "mode": "custom_detail_chain"},
    "risk_flag": "同页另有职责栏目，须以主要领导标题限定唯一人物列表并在线读取详情",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def fetch_detail(session: requests.Session, detail_url: str) -> str:
    """按站点声明的中文编码在线获取领导详情页。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    return response.content.decode("gb18030")


def extract_evidence(html: str, expected_name: str) -> str:
    """从当前人物详情正文提取完整现任句，并清理句首现任标签。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_Editor")
    if region is None:
        raise RuntimeError(f"详情页缺少正文 .TRS_Editor：{expected_name}")
    text = clean_text(region.get_text(" ", strip=True))
    if expected_name not in re.sub(r"\s+", "", text):
        raise RuntimeError(f"详情正文缺少目录姓名：{expected_name}")
    match = re.search(r"现任[^。]*。", text)
    if match is None:
        raise RuntimeError(f"详情正文缺少完整现任句：{expected_name}")
    return re.sub(r"^现任(?:职务)?(?:\s*[：:]\s*)?\s*", "", match.group(0), count=1)


def find_leader_container(soup: object) -> object:
    """定位“主要领导”标题之后且仅与其相邻的列表。"""
    for heading in soup.select(".con_r .tit1"):
        if clean_text(heading.get_text(" ", strip=True)) != "主要领导":
            continue
        container = heading.find_next_sibling("div", class_="list")
        if container is not None:
            return container
    raise RuntimeError("未找到主要领导标题对应的人物列表")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按主要领导目录顺序逐页在线提取姓名、现任句和详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    container = find_leader_container(soup)
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    seen_names: set[str] = set()
    for link in container.select("a[href]"):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        if name in seen_names:
            raise RuntimeError(f"主要领导姓名重复：{name}")
        evidence = extract_evidence(fetch_detail(session, detail_url), name)
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("主要领导列表中未提取到人物")
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
