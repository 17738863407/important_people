from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0619",
    "page_type": "人物列表完整页",
    "structure_group": "taiyuan_police_official_api_paragraphs_v3",
    "reuse_scope": "single_page",
    "load_mode": "动态JSON接口",
    "fetch_mode": "online",
    "inline_parser_handles_fetch": True,
    "inline_fetch_collector": "requests",
    "extract_mode": "api_direct",
    "collector": "custom_api_http",
    "parser": "taiyuan_police_official_api_paragraphs_v3",
    "leader_region_selector": "api:data HTML paragraphs",
    "name_selector": "段落开头姓名",
    "duty_selector": "省公安厅或市公安局起始的完整职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "接口data为HTML片段，姓名可能被多个span拆分，按段落整体文本切分",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_api",
    "locator": {
        "api": {
            "enabled": True,
            "endpoint_path": "/baseApi/site/api/Business/Note/public_listshow",
            "method": "POST",
            "request_json": {"menuid": "4003100102"},
            "data_path": "data",
        }
    },
}


def clean_text(value: str) -> str:
    """合并渲染节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def fetch_leader_html(page_rule: dict) -> str:
    """从官方信息公开接口取得领导名单HTML片段。"""
    source_url = str(page_rule.get("url") or "")
    parsed_source = urlsplit(source_url)
    api_config = dict(page_rule.get("locator", {}).get("api", {}))
    api_url = f"{parsed_source.scheme}://{parsed_source.netloc}{api_config['endpoint_path']}"
    session = requests.Session()
    session.trust_env = False
    response = session.post(
        api_url,
        json=dict(api_config.get("request_json", {})),
        headers={
            "Referer": source_url,
            "Origin": f"{parsed_source.scheme}://{parsed_source.netloc}",
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload.get(str(api_config.get("data_path") or "data"))
    if payload.get("code") != 0 or not isinstance(content, str) or not content.strip():
        raise RuntimeError("官方领导接口未返回有效data HTML")
    return content


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按官方接口段落顺序解析人物姓名和完整职务。"""
    del html, final_url
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(fetch_leader_html(page_rule), "html.parser")
    pattern = re.compile(
        r"^(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,9})\s+"
        r"(?P<evidence>(?:省公安厅|市公安局).+)$"
    )

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in soup.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        match = pattern.fullmatch(text)
        if match is None:
            continue
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = re.sub(r"\s+", "", match.group("evidence"))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or name in seen_names:
            raise RuntimeError(f"人物姓名异常或重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
                selector_summary="api=Note/public_listshow；menuid=4003100102；rows=data HTML p；name=段落开头；duty=机构职务标志起始",
            )
        )
    if not records:
        raise RuntimeError("官方接口没有可验证的人物职务段落")
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
