from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "1301",
    "domain": "jyj.beijing.gov.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "beijing_prison_leader_info_items_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_beijing_prison_leader_info_items_v1",
    "risk_flag": "同页包含多个page-content业务区，必须限定当前市局领导页并保留完整现任句",
    "confidence": "high",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """压缩网页文本中的换行、全角空格和连续空白。"""
    return re.sub(r"\s+", " ", str(value or "").replace("\u3000", " ").replace("\xa0", " ")).strip()


def clean_name(value: str) -> str:
    """删除姓名中的排版空白。"""
    return re.sub(r"\s+", "", clean_text(value))


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按市局领导区的DOM原始顺序提取姓名和完整现任职务句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()

    for item in soup.select("#page-市局领导.page-content.active li.leader-info-item"):
        if item.has_attr("hidden") or str(item.get("aria-hidden", "")).lower() == "true":
            continue
        name_node = item.select_one(".leader-info-name")
        duty_node = item.select_one(".leader-info-position")
        name = clean_name(name_node.get_text(" ", strip=True) if name_node is not None else "")
        evidence = clean_text(duty_node.get_text(" ", strip=True) if duty_node is not None else "")
        duty = evidence.removeprefix("现任").removesuffix("。").strip()
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name) or not duty or name in seen:
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "当前#page-市局领导内leader-info姓名与完整现任职务句",
            }
        )
    return rows


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
