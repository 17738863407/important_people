from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3887",
    "page_type": "人物目录详情页",
    "structure_group": "suzhou_anhui_government_leader_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_suzhou_anhui_government_list_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "a[href]:has(> .leader_name_add):has(> .leader_job_add)",
    "name_selector": ".leader_name_add",
    "duty_selector": ".leader_job_add",
    "detail_link_selector": "a[href]",
    "risk_flag": "详情头部重复展示当前人物，仅解析市政府领导列表中成对姓名职务字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def clean_text(value: object) -> str:
    """压缩跨行排版空白，不改变职务字段语义。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", "", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按市政府领导列表原始顺序提取姓名、完整职务和详情链接。"""
    soup = BeautifulSoup(html, "lxml")
    links = soup.select(page_rule["leader_region_selector"])
    if not links:
        raise RuntimeError("未找到市政府领导列表的姓名职务字段")

    base_url = final_url or page_rule["url"]
    rows: list[dict] = []
    seen_names: set[str] = set()
    for link in links:
        name_node = link.select_one(page_rule["name_selector"])
        duty_node = link.select_one(page_rule["duty_selector"])
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        href = str(link.get("href") or "").strip()
        detail_url = urljoin(base_url, href) if href else ""
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or not duty:
            continue
        if name in seen_names or not detail_url:
            continue

        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": detail_url,
                "confidence": "high",
                "parser": page_rule["parser"],
                "selector_summary": "人物链接直属.leader_name_add姓名与.leader_job_add完整职务",
            }
        )

    if not rows:
        raise RuntimeError("市政府领导列表未提取到有效人物")
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

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
