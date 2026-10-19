from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3939",
    "domain": "www.jxjazx.gov.cn",
    "page_type": "动态JSON接口分组目录",
    "structure_group": "jian_cppcc_ajax_groups_2026",
    "reuse_scope": "single_page",
    "load_mode": "动态JSON接口",
    "fetch_mode": "online",
    "extract_mode": "api_json",
    "collector": "static_http",
    "parser": "page_jian_cppcc_ajax_groups_v1",
    "leader_region_selector": ".main .container",
    "name_selector": ".rig .info p",
    "duty_selector": ".fil",
    "detail_link_selector": ".rig > a[href]",
    "content_scope": {"include_selectors": [".main .container"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物卡片由公开POST接口按四个栏目动态加载，入口HTML本身无姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": True,
            "method": "POST",
            "url": "api-ajax_list-1.html",
            "site_id": "113",
            "groups": [
                {"category_id": "25", "page_size": "1", "duty": "党组书记"},
                {"category_id": "20", "page_size": "1", "duty": "主席"},
                {"category_id": "21", "page_size": "10", "duty": "副主席"},
                {"category_id": "23", "page_size": "1", "duty": "秘书长"},
            ],
            "data_path": "data[]",
            "name_field": "title",
            "detail_url_field": "url",
        }
    },
}


def normalize_name(value: str) -> str:
    """删除接口姓名中的排版空白。"""
    return re.sub(r"[\s\u00a0\u3000]+", "", value or "")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """复现入口页公开POST请求，按职务分组顺序解析当前领导。"""
    api = page_rule["locator"]["api"]
    endpoint = urljoin(final_url or str(page_rule.get("url", "")), str(api["url"]))
    rows: list[dict[str, str]] = []
    row_by_name: dict[str, dict[str, str]] = {}
    for group in api["groups"]:
        payload = {
            "ajax_type[0]": f"{api['site_id']}_news",
            "ajax_type[1]": str(group["category_id"]),
            "ajax_type[2]": str(api["site_id"]),
            "ajax_type[3]": "news",
            "ajax_type[4]": "Y-m-d",
            "ajax_type[5]": "50",
            "ajax_type[6]": str(group["page_size"]),
            "ajax_type[7][0]": "displayorder ASC",
            "ajax_type[7][1]": "inputtime ASC",
            "ajax_type[7][2]": "is_top ASC",
            "ajax_type[8]": "",
            "is_ds": "1",
        }
        response = requests.post(endpoint, data=payload, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        result = response.json()
        for item in result.get("data", []):
            name = normalize_name(str(item.get("title", "")))
            duty = str(group["duty"])
            detail_url = urljoin(endpoint, str(item.get("url", "")))
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,4}", name):
                continue
            if name in row_by_name:
                existing = row_by_name[name]
                duties = existing["duty"].split("；")
                if duty not in duties:
                    existing["duty"] += f"；{duty}"
                    existing["evidence"] = existing["duty"]
                continue
            row = {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "api-ajax_list-1.html；栏目25/20/21/23；title/url字段",
            }
            row_by_name[name] = row
            rows.append(row)
    if not rows:
        raise RuntimeError("政协领导公开接口未返回有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
