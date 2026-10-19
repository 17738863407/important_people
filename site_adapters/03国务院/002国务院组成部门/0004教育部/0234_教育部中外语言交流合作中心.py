from __future__ import annotations

import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0234",
    "page_type": "人物列表完整页",
    "structure_group": "中心领导接口正文段落",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http_api",
    "parser": "ChineseCnCenterLeadersApiParser_v2",
    "leader_region_selector": "#app",
    "name_selector": "items/141 content p冒号前",
    "duty_selector": "items/141 content p完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "入口id=140为中心简介，领导正文来自同站公开items/141接口；141是合并领导页而非个人详情页，详情链接必须留空",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """在线读取公开领导接口，按正文段落顺序抽取人物。"""
    response = requests.get(
        "https://www.chinese.cn/items/141",
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.chinese.cn/page/#/pcpage/publicinfodetail?id=140",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/145.0 Safari/537.36",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json().get("data", {})
    if data.get("title") != "中心领导":
        raise RuntimeError("items/141接口标题不再是中心领导")
    soup = BeautifulSoup(str(data.get("content") or ""), "html.parser")

    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.find_all("p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)[：:]\s*(中外语言交流合作中心.+)", evidence)
        if not matched:
            continue
        name = re.sub(r"\s+", "", matched.group(1))
        duty = _clean_text(matched.group(2))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": "GET /items/141；title=中心领导；content p逐段；冒号前姓名；完整段落证据",
            }
        )
    if not records:
        raise RuntimeError("中心领导接口正文未解析到人物记录")
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
