from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1756",
    "domain": "mzj.jiangxi.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangxi_government_query_api_inline_detail_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "api_to_inline_detail",
    "collector": "api_post_and_raw_detail",
    "parser": "page_inline_jiangxi_mzj_query_api_detail_payload_v1",
    "api_config": {
        "endpoint": "/queryList",
        "method": "POST",
        "channel_code": "col5542",
        "website_code": "jxsmzzjswj",
        "page_size": 15,
        "sort": "sortNum",
        "order": "desc",
        "data_path": "data.results[].source",
        "field_map": {"name": "title", "detail": "urls.pc"},
    },
    "detail_strategy": {"required": True, "mode": "api_to_inline_detail"},
    "risk_flag": "列表由POST接口加载；现职依据位于详情页内联JSON正文且与分管段落相邻",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """仅压缩接口和HTML中的排版空白，不改写原始职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def fetch_api_sources(final_url: str, page_rule: dict[str, object]) -> list[dict[str, object]]:
    """复现官网前端POST请求，并保留接口数组的原始人物顺序。"""
    api_config = dict(page_rule.get("api_config", {}))
    response = requests.post(
        urljoin(final_url, str(api_config.get("endpoint", "/queryList"))),
        data=[
            ("channelCode[]", str(api_config.get("channel_code", ""))),
            ("current", "1"),
            ("pageSize", str(api_config.get("page_size", 15))),
            ("sort", str(api_config.get("sort", "sortNum"))),
            ("order", str(api_config.get("order", "desc"))),
            ("webSiteCode[]", str(api_config.get("website_code", ""))),
            ("notReturnContent", "false"),
        ],
        headers={"User-Agent": "Mozilla/5.0", "Referer": final_url},
        timeout=40,
    )
    response.raise_for_status()
    results = response.json().get("data", {}).get("results", [])
    return [item.get("source", {}) for item in results if isinstance(item, dict)]


def parse_detail_path(value: object) -> str:
    """从接口urls字段取得当前人物的PC详情路径。"""
    if isinstance(value, dict):
        return str(value.get("pc", ""))
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return ""
    return str(parsed.get("pc", "")) if isinstance(parsed, dict) else ""


def iter_embedded_content(html: str) -> list[str]:
    """解析页面脚本中的JSON对象，返回其中动态下发的正文HTML。"""
    decoder = json.JSONDecoder()
    contents: list[str] = []
    for match in re.finditer(r"(?:[\"']?content[\"']?)\s*:\s*(?=\{)", html):
        try:
            payload, _ = decoder.raw_decode(html, match.end())
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        content = payload.get("content")
        if isinstance(content, str) and content not in contents:
            contents.append(content)
    return contents


def extract_detail_duty(detail_html: str, name: str) -> str:
    """从当前人物详情载荷中提取“领导简历”前的原始现职段落。"""
    biography_marker = f"领导简历：{name}"
    for content in iter_embedded_content(detail_html):
        content_text = clean_text(BeautifulSoup(content, "html.parser").get_text(" ", strip=True))
        if biography_marker not in content_text:
            continue

        paragraphs = [
            clean_text(node.get_text(" ", strip=True))
            for node in BeautifulSoup(content, "html.parser").select("p")
        ]
        biography_index = next(
            (index for index, text in enumerate(paragraphs) if biography_marker in text),
            len(paragraphs),
        )
        for text in reversed(paragraphs[:biography_index]):
            if not text or text.startswith(("分管", "负责", "协助", "联系")):
                continue
            if any(keyword in text for keyword in ("党组", "局长", "巡视员", "纪检监察组组长")):
                return text
    return ""


def fetch_detail_duty(detail_url: str, name: str, attempt_offset: int) -> str:
    """在线抓取详情页，并校验正文载荷属于当前接口人物。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    return extract_detail_duty(result.html, name)


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按官网接口数组顺序提取姓名、详情链接和原始现职依据。"""
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, item in enumerate(fetch_api_sources(final_url, page_rule), start=1):
        name = re.sub(r"\s+", "", clean_text(item.get("title", "")))
        detail_path = parse_detail_path(item.get("urls", {}))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name):
            continue
        if not detail_path or "/col/col5542/content/" not in detail_path or name in seen:
            continue

        detail_url = urljoin(source_url, detail_path)
        try:
            duty = fetch_detail_duty(detail_url, name, source_order)
        except Exception:
            continue
        if not duty:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": duty,
                "detail_url": detail_url,
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；POST=/queryList；order=sortNum desc；"
                    "name=API title；detail=API urls.pc；"
                    "duty=detail inline JSON paragraph before biography"
                ),
            }
        )

    return records


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
