from __future__ import annotations

import math
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
    "rule_id": "1165",
    "page_type": "人物列表完整页",
    "structure_group": "济南市政务站群页面构建接口领导卡片",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "requests_raw_html",
    "parser": "custom_jinan_jpaas_paginated_leader_cards_v1",
    "leader_region_selector": "ul.ldxx .page-content > ul > li",
    "name_selector": ".ld_intro > div（标签为姓名）",
    "duty_selector": ".ld_intro > div（标签为职务）",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": ["ul.ldxx"],
        "exclude_selectors": [],
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "分页总数与内容由页面构建接口实时返回",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "api+css",
    "locator": {
        "css": {
            "leader_region_selector": "ul.ldxx .page-content > ul > li",
            "name_selector": ".ld_intro > div（标签为姓名）",
            "duty_selector": ".ld_intro > div（标签为职务）",
            "detail_link_selector": "",
        },
        "api": {
            "enabled": True,
            "path": "/api-gateway/jpaas-publish-server/front/page/build/unit",
            "method": "GET",
            "params": {
                "parseType": "bulidstatic",
                "webId": "7",
                "tplSetId": "SntS8ZDi5dhpKE2ls0Ey4",
                "pageType": "column",
                "tagId": "列表页",
                "editType": "null",
                "pageId": "115378",
            },
            "pagination": {"page_param": "pageNo", "size_param": "pageSize"},
        },
    },
}


def clean_text(text: str) -> str:
    """只清理标签排版产生的空白，不改变网页原义。"""
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def extract_page_rows(fragment: str) -> tuple[list[dict], int, int]:
    """从单页接口HTML中读取强结构姓名、职务及分页元数据。"""
    soup = BeautifulSoup(fragment or "", "html.parser")
    pager = soup.select_one(".pagination[count][rows]")
    if pager is None:
        raise ValueError("页面构建接口未返回分页元数据")

    count = int(str(pager.get("count") or "0"))
    page_size = int(str(pager.get("rows") or "0"))
    if count <= 0 or page_size <= 0:
        raise ValueError(f"分页元数据无效：count={count}, rows={page_size}")

    rows: list[dict] = []
    for card in soup.select("ul.ldxx .page-content > ul > li"):
        fields: dict[str, str] = {}
        for field in card.select(".ld_intro > div"):
            spans = field.find_all("span", recursive=False)
            if len(spans) < 2:
                continue
            label = clean_text(spans[0].get_text(" ", strip=True))
            value = clean_text(spans[1].get_text(" ", strip=True))
            if label and value:
                fields[label] = value

        name = fields.get("姓名", "")
        duty = fields.get("职务", "").removesuffix("。")
        if not name or not duty:
            continue
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "selector_summary": "页面构建接口分页+领导卡片姓名/职务标签",
            }
        )
    return rows, count, page_size


def fetch_unit_page(session: requests.Session, api_url: str, params: dict, page_no: int, page_size: int) -> str:
    request_params = dict(params)
    request_params["paramJson"] = f'{{"pageNo":{page_no},"pageSize":{page_size}}}'
    response = session.get(api_url, params=request_params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success") or not isinstance(payload.get("data"), dict):
        raise ValueError(f"页面构建接口返回失败：{payload.get('message') or payload.get('code')}")
    fragment = payload["data"].get("html")
    if not isinstance(fragment, str) or not fragment.strip():
        raise ValueError("页面构建接口未返回HTML内容")
    return fragment


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """由规则主表注入入口的站点基址，在线遍历页面构建接口全部分页。"""
    del html
    entry_url = final_url or page_rule["url"]
    api_rule = page_rule["locator"]["api"]
    api_url = urljoin(entry_url, api_rule["path"])
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    first_fragment = fetch_unit_page(session, api_url, api_rule["params"], 1, 5)
    first_rows, count, page_size = extract_page_rows(first_fragment)
    rows = list(first_rows)
    for page_no in range(2, math.ceil(count / page_size) + 1):
        fragment = fetch_unit_page(session, api_url, api_rule["params"], page_no, page_size)
        page_rows, page_count, returned_size = extract_page_rows(fragment)
        if page_count != count or returned_size != page_size:
            raise ValueError("分页过程中接口总数或每页条数发生变化")
        rows.extend(page_rows)

    if len(rows) != count:
        raise ValueError(f"接口声明{count}人，但可靠解析到{len(rows)}人")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
