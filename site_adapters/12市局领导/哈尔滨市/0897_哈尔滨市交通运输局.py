from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

PAGE_RULE = {
    "rule_id": "0897",
    "page_type": "人物列表完整页",
    "structure_group": "harbin_channel_api_current_leader_content_v1",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "harbin_channel_api",
    "parser": "page_harbin_channel_api_current_leader_content_v1",
    "leader_region_selector": "API contentHtml中的人物职务段落",
    "name_selector": "人物职务段落末尾姓名",
    "duty_selector": "同段姓名之前的原始职务",
    "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "规则入口旧文章404，须由入口栏目代码调用官网栏目API动态取得当前领导正文",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    """确定性压缩接口HTML中的排版空白。"""
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def fetch_current_content(source_url: str) -> tuple[str, str]:
    """从规则入口栏目代码动态取得官网当前领导信息正文。"""
    parsed = urlsplit(source_url)
    path_parts = [part for part in parsed.path.split("/") if part]
    website_code = path_parts[0] if path_parts else ""
    channel_match = re.search(r"/(c\d+)/", parsed.path, re.I)
    if not parsed.netloc or not website_code or not channel_match:
        raise RuntimeError("规则入口无法解析官网站点代码或栏目代码")

    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
    )
    channel_code = channel_match.group(1)
    channel_response = session.get(
        urljoin(origin, "/common/getChannelList"),
        params={"channelCode": channel_code, "websiteCodeName": website_code},
        timeout=30,
    )
    channel_response.raise_for_status()
    channel_data = channel_response.json()
    channel = channel_data.get("results") or {}
    if str(channel.get("channelName", "")) != "领导信息":
        raise RuntimeError("规则入口栏目代码当前未对应领导信息栏目")
    channel_id = str(channel.get("channelId", "")).strip()
    if not channel_id:
        raise RuntimeError("官网栏目API未返回领导信息栏目ID")

    list_response = session.get(
        urljoin(origin, f"/common/search/{channel_id}"),
        params={
            "_isAgg": "true",
            "_isJson": "true",
            "_pageSize": "20",
            "_template": "index",
            "_rangeTimeGte": "",
            "_channelName": "",
            "page": "1",
        },
        timeout=30,
    )
    list_response.raise_for_status()
    results = ((list_response.json().get("data") or {}).get("results") or [])
    current = next(
        (
            item
            for item in results
            if str(item.get("channelCodeName", "")) == channel_code
            and "领导信息" in str(item.get("title", ""))
            and str(item.get("contentHtml", "")).strip()
        ),
        None,
    )
    if current is None:
        raise RuntimeError("官网领导信息栏目API未返回可验证的当前正文")
    return str(current["contentHtml"]), str(current.get("url", ""))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按接口正文段落顺序解析职务与末尾姓名。"""
    del final_url
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select("p"):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text or text.startswith("工作分工"):
            continue
        match = re.fullmatch(
            r"(?P<duty>.+(?:书记|局长|副局长|组长|主任|副主任|委员|调研员))\s*(?P<name>[\u4e00-\u9fff·]{2,4})",
            text,
        )
        if match is None:
            continue
        name = match.group("name")
        duty = clean_text(match.group("duty"))
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "规则入口栏目代码动态调用官网栏目API；contentHtml人物职务段落按原顺序解析",
            }
        )
    if not rows:
        raise RuntimeError("官网当前领导正文未发现可验证的职务姓名段落")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.business_sources import apply_business_source
    from crawler_core.exporter import export_records
    from crawler_core.rule_table import normalize_script_sequence
    from crawler_core.runner import (
        make_failure_record,
        normalize_inline_rows,
        normalize_record_source_urls,
        prepare_records_for_export,
        safe_filename,
    )

    rule = apply_business_source(PAGE_RULE)
    try:
        html, final_url = fetch_current_content(str(rule.get("url", "")))
        rows = normalize_inline_rows(rule, parse_page(html, final_url, rule))
        if not rows:
            rows = [make_failure_record(rule, "解析结果为空")]
    except Exception as error:
        rows = [make_failure_record(rule, str(error))]

    normalize_record_source_urls(rule, rows)
    prepare_records_for_export(rows)
    for row in rows:
        if not row.script_sequence:
            row.script_sequence = normalize_script_sequence(rule.get("rule_id"))

    output_name = (
        f"{str(rule.get('rule_id', '')).zfill(4)}_"
        f"{safe_filename(str(rule.get('page_type', '页面')))}_"
        f"{safe_filename(str(rule.get('load_mode', '在线')))}_"
        f"{safe_filename(str(rule.get('organization', '机构')))}.txt"
    )
    output_path = project_dir / "outputs" / output_name
    export_records(output_path, rows)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
