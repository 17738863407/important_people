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
    "rule_id": "2527",
    "page_type": "人物列表完整页",
    "structure_group": "xm_sports_leader_detail_chain_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_sports_leader_detail_chain_v2",
    "leader_region_selector": ".list_base.list_large",
    "name_selector": "领导目录人物链接文本",
    "duty_selector": "详情页.TRS_Editor内完整现任句",
    "detail_link_selector": ".list_base.list_large li a[href]",
    "detail_strategy": {"required": True, "mode": "custom_detail_chain"},
    "risk_flag": "历史版本依赖快照且详情证据串入页脚；现逐页在线裁剪.TRS_Editor并只取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def fetch_detail(session: requests.Session, detail_url: str) -> str:
    """在线获取一个人物详情页，失败时显式终止当前脚本。"""
    response = session.get(detail_url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def extract_evidence(html: str, expected_name: str) -> str:
    """从详情正文提取与目录姓名对应的完整现任句。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".TRS_Editor")
    if region is None:
        raise RuntimeError(f"详情页缺少正文容器：{expected_name}")
    text = clean_text(region.get_text(" ", strip=True))
    if expected_name not in text:
        raise RuntimeError(f"详情正文缺少目录姓名：{expected_name}")
    match = re.search(r"现任厦门市体育局[^。]*。", text)
    if match is None:
        raise RuntimeError(f"详情正文缺少完整现任句：{expected_name}")
    return re.sub(r"^现任\s*", "", match.group(0)).strip(" ，,。；;：: ")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按领导目录顺序逐页在线提取姓名、现任句和详情链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    records: list[object] = []
    seen_urls: set[str] = set()
    seen_names: set[str] = set()
    for link in soup.select(page_rule["detail_link_selector"]):
        name = re.sub(r"\s+", "", clean_text(link.get_text(" ", strip=True)))
        detail_url = urljoin(page_rule["url"], str(link.get("href") or ""))
        if (
            not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name)
            or "/zzjg/ldbz/" not in detail_url
            or not detail_url.endswith((".htm", ".html"))
            or detail_url in seen_urls
        ):
            continue
        if name in seen_names:
            raise RuntimeError(f"领导目录姓名重复：{name}")
        evidence = extract_evidence(fetch_detail(session, detail_url), name)
        seen_urls.add(detail_url)
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
        raise RuntimeError("领导目录中未提取到人物详情链接")
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
