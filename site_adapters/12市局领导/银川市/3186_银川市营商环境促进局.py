from __future__ import annotations

import sys
import re
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "3186",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_business_environment_current_sentences",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_business_environment_leader_v2",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".zwxxgk_bd p",
    "name_selector": "人物简介段首逗号前姓名",
    "duty_selector": "同一人物简介段中的完整现任句",
    "detail_link_selector": "",
    "risk_flag": "人物简介后含工作分工，仅提取简介段内现任句",
    "confidence": "high",
}


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析银川市营商环境促进局领导信息正文。"""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for node in soup.select(".zwxxgk_bd p"):
        text = re.sub(r"\s+", "", node.get_text(" ", strip=True))
        match = re.match(r"^([\u4e00-\u9fa5]{2,4})[，,].*?现任([^。；;]+)", text)
        if not match:
            continue
        name, duty = match.group(1), match.group(2)
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_yinchuan_business_environment_leader_v2",
            }
        )
    if not rows:
        raise RuntimeError("领导信息正文未解析出人物简介中的现任句")
    return rows


if __name__ == "__main__":
    main()
