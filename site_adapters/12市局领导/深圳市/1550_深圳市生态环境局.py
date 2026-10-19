from __future__ import annotations

import json
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
    "rule_id": "1550",
    "page_type": "人物列表完整页",
    "structure_group": "gd_gkmlpt_leader_api_abstract_v2",
    "reuse_scope": "gd_gkmlpt_same_structure",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "gd_gkmlpt_leader_api_abstract_v2",
    "leader_region_selector": "政府信息公开平台分类接口articles数组",
    "name_selector": "articles[].title",
    "duty_selector": "articles[].abstract",
    "detail_link_selector": "articles[].url",
    "detail_strategy": {"required": False, "mode": "api_direct_fields"},
    "api_config": {
        "url": "https://meeb.sz.gov.cn/gkmlpt/api/all/3746?page=1&sid=755014",
        "method": "GET",
        "data_path": "articles",
        "name_field": "title",
        "duty_field": "abstract",
        "detail_url_field": "url",
    },
    "risk_flag": "Python TLS与该站协商失败，使用公共无头Playwright读取权威JSON；职务来自接口abstract并已逐详情核验",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理接口字段中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def fetch_api_data(page_rule: dict) -> dict:
    """通过公共无头浏览器采集器取得浏览器可访问的机构领导JSON。"""
    from bs4 import BeautifulSoup

    from crawler_core.fetcher import fetch_html_with_strategy

    config = page_rule["api_config"]
    result = fetch_html_with_strategy(config["url"], strategy="playwright", timeout=60)
    pre = BeautifulSoup(result.html, "html.parser").select_one("pre")
    if pre is None:
        raise RuntimeError("机构领导接口浏览器响应缺少JSON正文")
    data = json.loads(pre.get_text())
    classify = data.get("classify") or {}
    articles = data.get(config["data_path"])
    if classify.get("id") != 3746 or classify.get("name") != "机构领导":
        raise RuntimeError("分类接口返回的栏目身份与机构领导不一致")
    if not isinstance(articles, list) or not articles or data.get("total") != len(articles):
        raise RuntimeError("机构领导分类接口为空或存在未获取分页")
    return data


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按接口数组原始顺序提取姓名、职务摘要与真实详情链接。"""
    from crawler_core.models import PersonRecord

    config = page_rule["api_config"]
    data = fetch_api_data(page_rule)
    records: list[object] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()
    for item in data[config["data_path"]]:
        name = re.sub(r"\s+", "", clean_text(str(item.get(config["name_field"]) or "")))
        evidence = clean_text(str(item.get(config["duty_field"]) or "")).removesuffix("。")
        detail_url = clean_text(str(item.get(config["detail_url_field"]) or ""))
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("机构领导接口返回异常姓名或空职务摘要")
        if not detail_url.startswith("https://meeb.sz.gov.cn/gkmlpt/content/"):
            raise RuntimeError("机构领导接口返回异常详情链接")
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
