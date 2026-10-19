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
    "rule_id": "3234",
    "page_type": "人物目录详情页",
    "structure_group": "xm_emergency_directory_detail_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_emergency_directory_detail_v2",
    "leader_region_selector": "table.tab1",
    "name_selector": "table.tab1 a[href]",
    "duty_selector": "详情页#trsContent内完整现任句",
    "detail_link_selector": "table.tab1 a[href]",
    "detail_strategy": {"required": True, "mode": "custom_detail_chain"},
    "risk_flag": "目录同一人物链接在桌面与移动结构中重复，须按真实详情URL去重并保持首次顺序",
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


def extract_evidence(html: str, expected_name: str) -> str:
    """从当前人物详情正文提取完整现任句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one("#trsContent")
    if region is None:
        raise RuntimeError(f"详情页缺少正文 #trsContent：{expected_name}")
    text = clean_text(region.get_text(" ", strip=True))
    if expected_name not in re.sub(r"\s+", "", text):
        raise RuntimeError(f"详情正文缺少目录姓名：{expected_name}")
    match = re.search(r"现任[^。]*。", text)
    if match is None:
        raise RuntimeError(f"详情正文缺少完整现任句：{expected_name}")
    return re.sub(r"\s*([，。；：])\s*", r"\1", clean_text(match.group(0))).removeprefix("现任").strip().removesuffix("。")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按目录首次出现顺序逐页在线提取人物及完整现任句。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("领导目录缺少 table.tab1")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for link in region.select("a[href]"):
        label = clean_text(link.get_text(" ", strip=True))
        name = re.sub(r"\s+", "", re.sub(r"个人简介\s*$", "", label))
        detail_url = urljoin(final_url, str(link.get("href") or ""))
        if (
            not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name)
            or not re.search(r"/jld/20\d{4}/t20\d{6}_\d+\.htm$", detail_url)
            or detail_url in seen_urls
        ):
            continue
        if name in seen_names:
            raise RuntimeError(f"领导目录姓名对应多个详情页：{name}")
        evidence = extract_evidence(fetch_detail(session, detail_url), name)
        seen_names.add(name)
        seen_urls.add(detail_url)
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
        raise RuntimeError("应急管理局领导目录中未提取到人物")
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
