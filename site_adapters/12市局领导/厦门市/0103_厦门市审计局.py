from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0103",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_audit_leader_sidebar_profiles_v2",
    "reuse_scope": "single_site",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_audit_leader_sidebar_profiles_v2",
    "leader_region_selector": ".gl_l .gl_list",
    "name_selector": "li a[href]",
    "detail_link_selector": "li a[href]",
    "detail_strategy": {
        "required": True,
        "mode": "dynamic_current_sentence",
        "detail_content_selector": ".gl_r .ldfg_con1:first-of-type",
        "max_detail_links": 20,
    },
    "risk_flag": "每个详情页含简介与分工两个同类块；仅在首个简介块提取完整现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value or "").strip()


def clean_duty_evidence(value: str) -> str:
    """删除现任句的固定引导词和纯句末句号。"""
    text = re.sub(r"^现任\s*", "", clean_text(value))
    return re.sub(r"[。．]\s*$", "", text).strip()


def canonical_url(value: str) -> str:
    """生成用于判断入口页与详情页是否相同的规范URL。"""
    parts = urlsplit(urldefrag(value)[0])
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按左侧人物目录顺序抓取详情简介中的完整现任句。"""
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
        name = clean_text(link.get_text(" ", strip=True))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        detail_url = urldefrag(urljoin(entry_url, link.get("href", "")))[0]
        response = session.get(detail_url, timeout=30)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        detail_soup = BeautifulSoup(response.text, "html.parser")
        blocks = detail_soup.select(".gl_r .ldfg_con1")
        if not blocks:
            raise RuntimeError(f"人物简介块缺失：{name}")
        biography = clean_text(blocks[0].get_text(" ", strip=True))
        evidence_match = re.search(r"现任[^。]*。", biography)
        if name not in biography or evidence_match is None:
            raise RuntimeError(f"人物简介无法核对姓名或现任句：{name}")
        evidence = clean_duty_evidence(evidence_match.group(0))
        verified_detail_url = (
            "" if canonical_url(response.url) == canonical_url(page_rule["url"]) else response.url
        )
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=verified_detail_url,
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
