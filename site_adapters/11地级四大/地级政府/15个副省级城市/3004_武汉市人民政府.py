from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3004",
    "page_type": "动态JSON接口",
    "structure_group": "wuhan_government_jsonp_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "动态JSON接口",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "wuhan_government_jsonp_profiles_v2",
    "leader_region_selector": "#zfld-list",
    "name_selector": "API name",
    "duty_selector": "API resume中的现任句",
    "detail_link_selector": "API url",
    "api": {
        "enabled": True,
        "method": "GET",
        "endpoint": "https://www.wuhan.gov.cn/whszfwz/zfld/pushinfo.jsonp",
        "response_format": "JSONP",
        "array_path": "$",
        "name_field": "name",
        "resume_field": "resume",
        "detail_url_field": "url",
    },
    "detail_strategy": {
        "required": False,
        "mode": "api_detail_url",
        "max_detail_links": 20,
    },
    "risk_flag": "入口原始HTML的zfld-list为空，浏览器通过官方JSONP接口填充；职务必须从API简历现任句提取",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", value).strip()


def _canonical_url(value: str) -> str:
    parts = urlsplit(value)
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
    )


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按官方JSONP数组顺序解析简历HTML中的完整现任句。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    endpoint = page_rule["api"]["endpoint"]
    response = requests.get(
        endpoint,
        headers={"User-Agent": "Mozilla/5.0", "Referer": final_url or page_rule["url"]},
        timeout=30,
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    match = re.fullmatch(r"\s*[A-Za-z_$][\w$]*\s*\((.*)\)\s*", response.text, re.S)
    if match is None:
        raise RuntimeError("官方领导接口未返回可解析的JSONP")
    payload_text = re.sub(r",\s*]$", "]", match.group(1))
    payload = json.loads(payload_text)
    if not isinstance(payload, list):
        raise RuntimeError("官方领导接口顶层不是数组")

    records: list[object] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = _clean_text(str(item.get("name") or ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen:
            continue
        resume_html = str(item.get("resume") or "")
        resume_text = _clean_text(
            BeautifulSoup(resume_html, "html.parser").get_text(" ", strip=True)
        )
        evidence_match = re.search(r"现任[^。]*。", resume_text)
        if evidence_match is None:
            raise RuntimeError(f"API简历缺少现任句：{name}")
        seen.add(name)
        evidence = evidence_match.group(0).removeprefix("现任").strip().removesuffix("。")
        evidence = evidence.replace("（兼）", "").replace("(兼)", "")
        candidate_url = str(item.get("url") or "").strip()
        verified_detail_url = (
            ""
            if not candidate_url
            or _canonical_url(candidate_url) == _canonical_url(page_rule["url"])
            else candidate_url
        )
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
