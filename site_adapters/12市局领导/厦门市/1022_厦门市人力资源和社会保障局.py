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
    "rule_id": "1022",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_hrss_leader_detail_chain_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_hrss_leader_detail_chain_v2",
    "leader_region_selector": ".szf_ll",
    "name_selector": ".szf_ll li a[href]",
    "duty_selector": ".szf_img h1:first-of-type",
    "detail_link_selector": ".szf_ll li a[href]",
    "detail_strategy": {"required": True, "mode": "custom_detail_chain"},
    "risk_flag": "入口本身是首人详情；只按左侧名单逐页在线解析顶部职务和姓名标题，不读取历史快照",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def fetch_detail(session: requests.Session, detail_url: str) -> str:
    """在线获取人物详情页，失败时显式终止当前脚本。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_profile(html: str) -> tuple[str, str]:
    """从详情页顶部两个标题提取姓名和原始职务。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    headings = [clean_text(node.get_text(" ", strip=True)) for node in soup.select(".szf_img h1")]
    if len(headings) < 2:
        raise RuntimeError("详情页缺少职务、姓名标题")
    evidence, name = headings[0], headings[1].replace(" ", "")
    if not evidence or not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
        raise RuntimeError("详情页职务或姓名标题无效")
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按左侧名单顺序逐页在线提取人物标题字段。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    seen: set[str] = set()
    for index, link in enumerate(soup.select(page_rule["detail_link_selector"])):
        listed_name = clean_text(link.get_text(" ", strip=True)).replace(" ", "")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", listed_name):
            continue
        detail_url = urljoin(page_rule["url"], str(link.get("href") or ""))
        name, evidence = extract_profile(fetch_detail(session, detail_url))
        if name != listed_name:
            raise RuntimeError(f"目录姓名与详情页不一致：{listed_name} != {name}")
        if name in seen:
            raise RuntimeError(f"目录人物姓名重复：{name}")
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="" if detail_url == page_rule["url"] else detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("左侧领导名单中未提取到人物")
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
