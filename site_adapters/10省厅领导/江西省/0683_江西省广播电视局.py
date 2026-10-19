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
    "rule_id": "0683",
    "domain": "gdj.jiangxi.gov.cn",
    "page_type": "人物列表完整页",
    "structure_group": "jiangxi_broadcast_child_channel_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "channel_metadata_to_api",
    "collector": "api_post",
    "parser": "page_inline_jiangxi_broadcast_child_channel_profiles_v2",
    "api_config": {
        "endpoint": "/queryList",
        "method": "POST",
        "website_code": "jxsgbdsj",
        "unitid": "309449",
        "page_size": 1,
        "data_path": "data.results[0].source.content.content",
    },
    "detail_strategy": {"required": True, "mode": "dynamic_child_channel"},
    "risk_flag": "入口DOM为空；人物顺序与子频道链接来自channelsTagSelf.children；正文由接口加载",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩HTML和接口文本中的排版空白。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def compact_name(value: str) -> str:
    """移除姓名中的排版空白和HTML标签。"""
    text = BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", "", clean_text(text))


def extract_current_children(html: str) -> list[dict[str, object]]:
    """从入口当前频道元数据读取可见人物子频道数组顺序。"""
    match = re.search(
        r"var\s+channelsTagSelf\s*=\s*(\{.*?\})\s*;\s*//当前栏目信息",
        html,
        flags=re.S,
    )
    if match is None:
        return []
    try:
        channel = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    children = channel.get("children", [])
    return [child for child in children if isinstance(child, dict)]


def query_child_profile(
    final_url: str,
    child_code: str,
    child_url: str,
    page_rule: dict[str, object],
) -> tuple[str, str]:
    """复现人物子频道的POST接口并提取接口标题与正文。"""
    api_config = dict(page_rule.get("api_config", {}))
    response = requests.post(
        urljoin(final_url, str(api_config.get("endpoint", "/queryList"))),
        data=[
            ("current", "1"),
            ("unitid", str(api_config.get("unitid", ""))),
            ("webSiteCode[]", str(api_config.get("website_code", ""))),
            ("channelCode[]", child_code),
            ("dataBefore", ""),
            ("dataAfter", ""),
            ("perPage", str(api_config.get("page_size", 1))),
            ("showMode", "full"),
            ("groupSize", "1"),
            ("barPosition", "bottom"),
            ("titleMax", "42"),
            ("templateContainerId", "div309449"),
            ("themeName", "default"),
        ],
        headers={"User-Agent": "Mozilla/5.0", "Referer": child_url},
        timeout=40,
    )
    response.raise_for_status()
    results = response.json().get("data", {}).get("results", [])
    if not results:
        return "", ""
    source = results[0].get("source", {})
    name = compact_name(str(source.get("title", "")))
    content = str(source.get("content", {}).get("content", ""))
    text = clean_text(BeautifulSoup(content, "html.parser").get_text(" ", strip=True))
    match = re.search(r"现任[^。]*。", text)
    evidence = re.sub(r"^现任\s*", "", clean_text(match.group(0))).removesuffix("。") if match else ""
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按入口子频道数组顺序在线取得每个人物的完整现任句。"""
    source_url = str(page_rule.get("url", "")) or final_url
    records: list[dict[str, str]] = []
    seen: set[str] = set()

    for child in extract_current_children(html):
        listed_name = compact_name(str(child.get("name") or child.get("showName") or ""))
        child_code = clean_text(str(child.get("code", "")))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,5}", listed_name) or not child_code:
            continue
        try:
            url_data = json.loads(str(child.get("urls", "{}")))
        except json.JSONDecodeError:
            continue
        child_path = str(url_data.get("pc", ""))
        if not child_path:
            continue
        child_url = urljoin(final_url, child_path)
        try:
            name, evidence = query_child_profile(final_url, child_code, child_url, page_rule)
        except Exception:
            continue
        if name != listed_name or not evidence or name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": source_url,
                "name": name,
                "duty": evidence,
                "detail_url": child_url,
                "evidence": evidence,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；order=channelsTagSelf.children；"
                    "POST=/queryList per child channel；"
                    "name=source.title；duty=source.content scoped-current-sentence"
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
