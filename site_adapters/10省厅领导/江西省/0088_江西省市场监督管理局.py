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
    "rule_id": "0088",
    "domain": "amr.jiangxi.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangxi_market_supervision_query_api_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "api_to_detail",
    "collector": "api_post",
    "parser": "page_inline_jiangxi_market_supervision_query_api_profiles_v2",
    "api_config": {
        "endpoint": "/queryList",
        "method": "POST",
        "channel_code": "ldxx160",
        "page_size": 15,
        "sort": "sortNum",
        "order": "desc",
        "data_path": "data.results[].source",
        "field_map": {"name": "title", "duty": "summary", "detail": "urls.pc"},
    },
    "detail_strategy": {"required": True, "mode": "api_to_detail"},
    "risk_flag": "入口为概况父栏目；领导列表由POST接口加载；详情职务限定#zoom现任句",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML和接口文本中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def clean_duty_evidence(value: str) -> str:
    """删除现任句的固定引导词和纯句末句号。"""
    text = clean_text(value)
    text = re.sub(r"^现任\s*", "", text)
    text = re.sub(r"[。．]\s*$", "", text)
    return clean_text(text)


def compact_name(value: str) -> str:
    """移除姓名中的排版空白和标题标签。"""
    text = BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", "", clean_text(text))


def fetch_api_sources(final_url: str, page_rule: dict[str, object]) -> list[dict[str, object]]:
    """复现官网前端POST请求并返回接口原始人物数组顺序。"""
    api_config = dict(page_rule.get("api_config", {}))
    endpoint = str(api_config.get("endpoint", "/queryList"))
    channel_code = str(api_config.get("channel_code", ""))
    page_size = int(api_config.get("page_size", 15))
    api_url = urljoin(final_url, endpoint)
    leader_list_url = urljoin(final_url, "/amr/ldxx160/pc/list.html")
    response = requests.post(
        api_url,
        data=[
            ("channelCode[]", channel_code),
            ("current", "1"),
            ("pageSize", str(page_size)),
            ("sort", str(api_config.get("sort", "sortNum"))),
            ("order", str(api_config.get("order", "desc"))),
            ("webSiteCode[]", "amr"),
            ("notReturnContent", "false"),
        ],
        headers={"User-Agent": "Mozilla/5.0", "Referer": leader_list_url},
        timeout=40,
    )
    response.raise_for_status()
    results = response.json().get("data", {}).get("results", [])
    return [item.get("source", {}) for item in results if isinstance(item, dict)]


def fetch_detail_html(detail_url: str, attempt_offset: int) -> str:
    """使用公共原始HTTP能力读取详情页，不落地缓存。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    return result.html


def extract_current_sentence(detail_html: str, name: str) -> str:
    """只在当前人物详情正文#zoom中提取完整现任句。"""
    body = BeautifulSoup(detail_html, "html.parser").select_one("#zoom")
    if body is None:
        return ""
    text = clean_text(body.get_text(" ", strip=True))
    if name not in re.sub(r"\s+", "", text):
        return ""
    match = re.search(r"现任[^。]*。", text)
    return clean_duty_evidence(match.group(0)) if match else ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按接口数组顺序动态发现人物，并从对应详情正文取得现任职务证据。"""
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, item in enumerate(fetch_api_sources(final_url, page_rule), start=1):
        name = compact_name(str(item.get("title", "")))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or name in seen:
            continue
        try:
            url_data = json.loads(str(item.get("urls", "{}")))
        except json.JSONDecodeError:
            continue
        detail_path = str(url_data.get("pc", ""))
        if not detail_path or "/ldxx160/" not in detail_path:
            continue
        detail_url = urljoin(source_url, detail_path)
        evidence = ""
        try:
            detail_html = fetch_detail_html(detail_url, source_order)
            evidence = extract_current_sentence(detail_html, name)
        except Exception:
            evidence = ""
        if not evidence:
            evidence = clean_duty_evidence(str(item.get("summary", "")))
        if not evidence:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": evidence,
                "detail_url": detail_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；POST=/queryList；channelCode=ldxx160；"
                    "order=API sortNum desc；detail=#zoom scoped-current-sentence；"
                    "fallback=API summary"
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
