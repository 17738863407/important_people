from __future__ import annotations

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
    "rule_id": "1950",
    "page_type": "人物列表完整页",
    "structure_group": "海洋环境预报中心领导JSON数组",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NmefcLeaderApiParser_v2",
    "leader_region_selector": "API obj数组",
    "name_selector": "title",
    "duty_selector": "description HTML文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "api_config": {
        "endpoint": "/api/cms/plate/leader/list",
        "pid": "03880df8ce9949ac91c9f85f92701dfc",
        "first_char": "",
        "data_path": "obj",
        "name_field": "title",
        "duty_field": "description",
    },
    "risk_flag": "content字段为主持/负责等分工，不得作为主职务；中心领导页面不展示详情按钮",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    text = BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"[\s\u3000\xa0]+", "", text).strip("；。")


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """调用公开领导接口并按JSON数组顺序提取姓名与职务。"""
    api_config = dict(rule.get("api_config", {}))
    response = requests.get(
        urljoin(base_url, str(api_config["endpoint"])),
        params={"pid": str(api_config["pid"]), "firstChar": str(api_config["first_char"])},
        headers={"User-Agent": "Mozilla/5.0", "Referer": base_url},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get(str(api_config["data_path"]))
    if payload.get("code") != "1000" or not isinstance(items, list):
        raise RuntimeError("领导接口未返回有效obj数组")
    records: list[dict] = []
    seen_names: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _clean_text(str(item.get(str(api_config["name_field"]), "")))
        duty = _clean_text(str(item.get(str(api_config["duty_field"]), "")))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "GET /api/cms/plate/leader/list；obj[].title/description；保持数组顺序",
            }
        )
    if not records:
        raise RuntimeError("领导接口未解析到人物记录")
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
