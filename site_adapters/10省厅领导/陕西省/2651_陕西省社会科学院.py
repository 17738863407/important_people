from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2651",
    "page_type": "多人物详情合并页",
    "structure_group": "article_api_person_list",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "api_list_direct",
    "collector": "static_http_with_json_api",
    "parser": "ShaanxiAcademyCurrentLeaderApiParser_v1",
    "leader_region_selector": "WebArticle/GetWebArticleList result.items",
    "name_selector": "title竖线前文本",
    "duty_selector": "title竖线后文本",
    "detail_link_selector": "item.url + item.id",
    "api": {
        "enabled": True,
        "url": "https://www.sxsky.org.cn/skyapi/WebArticle/GetWebArticleList",
        "method": "POST",
        "site_id": 32515065266181,
        "class_id": 32515284944645,
        "data_path": "result.items",
        "order": "接口数组顺序",
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "入口HTML仅为前端壳，人物数据来自稳定JSON接口；禁止扫描整页模板正文",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """调用页面当前JSON接口，按接口数组顺序解析现任领导。"""
    del html
    import requests

    api_rule = rule["api"]
    payload = {
        "page": 1,
        "pageSize": 100,
        "total": 0,
        "isPublish": 1,
        "isRecommend": -1,
        "isTop": -1,
        "isHeadline": -1,
        "isImg": -1,
        "isSlide": -1,
        "siteId": api_rule["site_id"],
        "classId": api_rule["class_id"],
    }
    response = requests.post(api_rule["url"], json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    items = data.get("result", {}).get("items", [])

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        title = _clean_text(str(item.get("title", "")))
        parts = re.split(r"\s*\|\s*", title, maxsplit=1)
        if len(parts) != 2:
            continue
        name = re.sub(r"\s+", "", parts[0])
        duty = _clean_text(parts[1])
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if not duty or name in seen:
            continue
        detail_path = str(item.get("url", ""))
        item_id = str(item.get("id", ""))
        detail_url = urljoin(base_url, f"{detail_path}?id={item_id}") if detail_path and item_id else ""
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": "",
                "detail_url": detail_url,
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": "API=result.items；姓名=title竖线前；职务=title竖线后；详情=item.url+id",
                "order": str(len(records) + 1),
            }
        )
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
