from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0803",
    "page_type": "动态JSON目录详情页",
    "structure_group": "guangzhou_government_postmeta_details_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "guangzhou_government_postmeta_details_v2",
    "leader_region_selector": "#fj",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "api": {
        "enabled": True,
        "method": "GET",
        "endpoint": "https://www.gz.gov.cn/postmeta/i/5148.json",
        "data_path": "articles",
        "name_field": "title",
        "duty_field": "subtitle",
        "detail_url_field": "url",
    },
    "detail_strategy": {
        "required": True,
        "mode": "api_list_to_detail",
        "detail_content_selector": ".ldzc-cr .txt",
        "max_detail_links": 50,
    },
    "risk_flag": "侧栏由官方JSON接口填充，只按接口articles顺序发现领导",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    text = re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()
    return re.sub(r"\s+([，。；：])", r"\1", text)


def _clean_current_evidence(value: str) -> str:
    """删除现任句的固定标签和纯句末句号，保留完整任职语义。"""
    evidence = re.sub(r"^现任\s*", "", value).strip()
    return re.sub(r"。$", "", evidence).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """从官方postmeta接口按原始数组顺序发现人物，并逐详情提取现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Referer": final_url or page_rule["url"],
        }
    )
    api_response = session.get(page_rule["api"]["endpoint"], timeout=30)
    api_response.raise_for_status()
    payload = api_response.json()
    articles = payload.get(page_rule["api"]["data_path"])
    if not isinstance(articles, list):
        raise RuntimeError("领导目录接口缺少articles数组")

    records: list[object] = []
    seen: set[str] = set()
    for article in articles:
        if not isinstance(article, dict):
            continue
        name = re.sub(
            r"[\s\u2000-\u200b\u3000\xa0]+",
            "",
            str(article.get(page_rule["api"]["name_field"]) or ""),
        )
        detail_url = str(article.get(page_rule["api"]["detail_url_field"]) or "").strip()
        if name in seen or not detail_url or not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
            continue
        seen.add(name)
        detail_response = session.get(detail_url, timeout=30)
        detail_response.raise_for_status()
        detail_response.encoding = detail_response.apparent_encoding or detail_response.encoding
        detail_soup = BeautifulSoup(detail_response.text, "html.parser")
        content = detail_soup.select_one(
            page_rule["detail_strategy"]["detail_content_selector"]
        )
        detail_text = _clean_text(content.get_text(" ", strip=True)) if content else ""
        evidence_match = re.search(r"现任[^。]*。", detail_text)
        if evidence_match is None:
            raise RuntimeError(f"人物详情简介缺少可验证的现任职务依据：{name}")
        evidence = _clean_current_evidence(
            re.sub(
                r"[\s\u2000-\u200b\u3000\xa0]+",
                "",
                evidence_match.group(0),
            )
        )
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_response.url,
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
