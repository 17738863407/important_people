from __future__ import annotations

import html as html_lib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3474",
    "page_type": "人物列表完整页",
    "structure_group": "华电领导公开JSONP接口",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "api_jsonp",
    "parser": "ChdLeaderJsonpParser_v1",
    "leader_region_selector": ".director_main",
    "name_selector": "JSONP TITLE",
    "duty_selector": "JSONP CONTENT",
    "detail_link_selector": "JSONP ARTICLELINK",
    "api": {
        "discovery": "从入口内联脚本读取getarticleurl、website_id与oc",
        "method": "GET",
        "response": "callbackMethod(JSON数组)",
        "name_field": "TITLE",
        "duty_field": "CONTENT",
        "detail_field": "ARTICLELINK",
    },
    "detail_strategy": {"required": False, "mode": "api_field"},
    "risk_flag": "入口HTML仅含空卡片；必须从当前内联脚本动态发现公开JSONP接口和业务参数",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    decoded = html_lib.unescape(value or "")
    return re.sub(r"[\s\u2002\u2003\u3000\xa0]+", " ", decoded).strip()


def _discover_api(html: str, base_url: str) -> tuple[str, dict[str, str]]:
    """从当前入口脚本发现公开JSONP地址及稳定业务参数。"""
    soup = BeautifulSoup(html, "html.parser")
    scripts = "\n".join(node.get_text() for node in soup.select("script:not([src])"))
    endpoint_match = re.search(r'getarticleurl\s*=\s*["\']([^"\']+)', scripts)
    params_match = re.search(r"website_id=([0-9a-f]+)&oc=(\d+)", scripts)
    if endpoint_match is None or params_match is None:
        raise RuntimeError("入口脚本未发现领导JSONP接口或业务参数")
    endpoint = endpoint_match.group(1).replace("callback=?", "").rstrip("?&")
    return urljoin(base_url, endpoint), {
        "website_id": params_match.group(1),
        "oc": params_match.group(2),
    }


def _fetch_api(html: str, base_url: str) -> list[dict]:
    api_url, params = _discover_api(html, base_url)
    response = requests.get(
        f"{api_url}?{urlencode(params)}",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": base_url,
        },
        timeout=30,
    )
    response.raise_for_status()
    matched = re.fullmatch(r"\s*callbackMethod\((.*)\)\s*", response.text, flags=re.S)
    if matched is None:
        raise RuntimeError("华电领导接口未返回预期callbackMethod JSONP")
    payload = json.loads(matched.group(1))
    if not isinstance(payload, list):
        raise RuntimeError("华电领导接口数据不是数组")
    return payload


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按JSONP数组顺序解析姓名、原始职务和可选详情链接。"""
    records: list[dict] = []
    seen_names: set[str] = set()
    for item in _fetch_api(html, base_url):
        name = re.sub(r"\s+", "", _clean_text(str(item.get("TITLE", ""))))
        evidence = _clean_text(str(item.get("CONTENT", "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not evidence:
            continue
        if name in seen_names:
            continue
        seen_names.add(name)
        raw_link = _clean_text(str(item.get("ARTICLELINK", "")))
        detail_url = urljoin(base_url, raw_link) if raw_link else ""
        records.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": detail_url,
                "parser": PAGE_RULE["parser"],
                "selector_summary": "内联脚本动态发现articleListSearch；JSONP TITLE/CONTENT/ARTICLELINK",
            }
        )
    if not records:
        raise RuntimeError("华电领导JSONP接口未解析到人物记录")
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
