from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2664", "page_type": "人物列表完整页", "structure_group": "gd_gkmlpt_leader_api_detail_json_ext_v1",
    "reuse_scope": "single_page", "load_mode": "接口数据加载", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "gd_gkmlpt_leader_api_detail_json_ext_v1",
    "leader_region_selector": "政府信息公开平台分类接口articles数组", "name_selector": "articles[].title及详情DETAIL.json_ext.EXT_name",
    "duty_selector": "详情DETAIL.json_ext.EXT_zw", "detail_link_selector": "articles[].url",
    "detail_strategy": {"required": True, "mode": "api_to_detail_json_ext"},
    "api_config": {"url": "http://szfb.sz.gov.cn/gkmlpt/api/all/4438", "method": "GET", "params": {"page": 1, "sid": "755021"}, "data_path": "articles", "name_field": "title", "detail_url_field": "url"},
    "risk_flag": "详情可见正文为空，姓名和原始职务来自页面内DETAIL.json_ext强结构字段",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理接口字段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def http_fetch_url(value: str) -> str:
    """使用同站HTTP地址获取详情，输出仍保留接口权威链接。"""
    parts = urlsplit(value)
    return urlunsplit(("http", parts.netloc, parts.path, parts.query, ""))


def fetch_json(session: requests.Session, page_rule: dict) -> dict:
    """请求经页面脚本核实的机构领导分类接口。"""
    config = page_rule["api_config"]
    response = session.get(config["url"], params=config["params"], timeout=30)
    response.raise_for_status()
    data = response.json()
    classify = data.get("classify") or {}
    articles = data.get(config["data_path"])
    if classify.get("id") != 4438 or classify.get("name") != "机构领导":
        raise RuntimeError("分类接口返回的栏目身份与机构领导不一致")
    if not isinstance(articles, list) or not articles or data.get("total") != len(articles):
        raise RuntimeError("机构领导分类接口为空或存在未获取分页")
    return data


def extract_fields(session: requests.Session, detail_url: str) -> tuple[str, str]:
    """从详情页内嵌DETAIL对象读取json_ext姓名与原始职务。"""
    response = session.get(http_fetch_url(detail_url), timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    marker = re.search(r"\bDETAIL\s*:\s*", response.text)
    if marker is None:
        raise RuntimeError("详情页缺少DETAIL对象")
    detail, _ = json.JSONDecoder().raw_decode(response.text[marker.end():])
    json_ext = json.loads(detail.get("json_ext") or "{}")
    name = re.sub(r"\s+", "", clean_text(str(json_ext.get("EXT_name") or "")))
    evidence = clean_text(str(json_ext.get("EXT_zw") or ""))
    if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
        raise RuntimeError("DETAIL.json_ext姓名或职务字段缺失")
    return name, evidence


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按分类接口数组顺序逐页在线提取人物和json_ext职务。"""
    from crawler_core.models import PersonRecord

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": final_url})
    data = fetch_json(session, page_rule)
    config = page_rule["api_config"]
    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for item in data[config["data_path"]]:
        api_name = re.sub(r"\s+", "", clean_text(str(item.get(config["name_field"]) or "")))
        detail_url = clean_text(str(item.get(config["detail_url_field"]) or ""))
        if not detail_url.startswith("https://szfb.sz.gov.cn/gkmlpt/content/"):
            raise RuntimeError("机构领导接口返回异常详情链接")
        name, evidence = extract_fields(session, detail_url)
        if name != api_name:
            raise RuntimeError(f"接口姓名与详情json_ext不一致：{api_name}")
        if name in seen_names or detail_url in seen_urls:
            raise RuntimeError(f"机构领导接口人物或链接重复：{name}")
        seen_names.add(name)
        seen_urls.add(detail_url)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url=detail_url, evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
