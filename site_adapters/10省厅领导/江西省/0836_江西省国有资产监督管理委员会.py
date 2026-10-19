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
    "rule_id": "0836",
    "domain": "gzw.jiangxi.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "jiangxi_sasac_query_api_title_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "api_to_detail",
    "collector": "api_post",
    "parser": "page_inline_jiangxi_sasac_query_api_title_profiles_v2",
    "api_config": {
        "endpoint": "/queryList",
        "method": "POST",
        "channel_code": "ldxx157",
        "website_code": "jxsgzw",
        "page_size": 15,
        "sort": "sortNum",
        "order": "desc",
        "data_path": "data.results[].source",
        "field_map": {"title": "title", "detail": "urls.pc"},
    },
    "title_organization_prefix": "江西省国有资产监督管理委员会",
    "detail_strategy": {"required": True, "mode": "api_to_detail"},
    "risk_flag": "列表由POST接口加载；姓名以详情#zoom核验；职责不得混入接口标题职务",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML和接口文本中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def fetch_api_sources(final_url: str, page_rule: dict[str, object]) -> list[dict[str, object]]:
    """复现官网前端POST请求并返回人物接口数组原始顺序。"""
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


def fetch_detail_name(detail_url: str, attempt_offset: int) -> str:
    """在线读取详情正文并从人物简介开头取得姓名。"""
    from crawler_core.fetcher import fetch_by_raw_requests

    result = fetch_by_raw_requests(detail_url, timeout=40, attempt_offset=attempt_offset)
    body = BeautifulSoup(result.html, "html.parser").select_one("#zoom")
    if body is None:
        return ""
    text = clean_text(body.get_text(" ", strip=True))
    match = re.match(r"([\u3400-\u9fff·]{2,5})，(?:男|女)", text)
    return match.group(1) if match else ""


def extract_title_duty(title: str, name: str, page_rule: dict[str, object]) -> str:
    """以机构前缀和详情核验姓名裁定接口标题中的原始职务字段。"""
    compact_title = re.sub(r"\s+", "", clean_text(title))
    prefix = re.sub(r"\s+", "", str(page_rule.get("title_organization_prefix", "")))
    suffix = f"{name}同志"
    if not prefix or not compact_title.startswith(prefix) or not compact_title.endswith(suffix):
        return ""
    return compact_title[len(prefix) : -len(suffix)].strip("，,；;。 ")


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按接口数组顺序提取详情核验姓名与接口标题原始职务。"""
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for source_order, item in enumerate(fetch_api_sources(final_url, page_rule), start=1):
        try:
            url_data = json.loads(str(item.get("urls", "{}")))
        except json.JSONDecodeError:
            continue
        detail_path = str(url_data.get("pc", ""))
        if not detail_path or "/ldxx157/" not in detail_path:
            continue
        detail_url = urljoin(source_url, detail_path)
        try:
            name = fetch_detail_name(detail_url, source_order)
        except Exception:
            continue
        duty = extract_title_duty(str(item.get("title", "")), name, page_rule)
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name) or not duty or name in seen:
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
                    "name=detail #zoom biography prefix；"
                    "duty=API title between organization-prefix and verified-name+同志"
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
