from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0939",
    "page_type": "人物列表完整页",
    "structure_group": "nanchang_health_duty_name_division_paragraph_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "collector": "online",
    "parser": "page_nanchang_health_duty_name_division_paragraph_v1",
    "leader_region_selector": "p",
    "name_selector": "冒号前职务后缀之后的末尾姓名",
    "duty_selector": "人物段落冒号前、姓名之前的原始职务",
    "detail_link_selector": "",
    "risk_flag": "正文采用职务与姓名无分隔拼接格式，冒号后内容仅为分工",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性清理正文段落中的排版空白。"""
    return re.sub(r"[\s\u00a0\u2000-\u200f\u3000]+", "", str(value or "")).strip()


def split_duty_name(prefix: str) -> tuple[str, str]:
    """按通用职务后缀从冒号前文本中拆分末尾姓名。"""
    compact = clean_text(prefix)
    match = re.fullmatch(
        r"(?P<duty>.+(?:书记|主任|组长|局长|会长|调研员)(?:（[^）]+）)?)(?P<name>[\u4e00-\u9fff·]{2,4})",
        compact,
    )
    if not match:
        return "", ""
    return match.group("duty"), match.group("name")


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析“职务+姓名：分工”段落，分工不进入职务证据。"""
    del final_url
    if not str(html or "").strip():
        raise RuntimeError("在线入口返回空页面")

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select("p"):
        line = clean_text(paragraph.get_text(" ", strip=True))
        if "：" not in line:
            continue
        duty, name = split_duty_name(line.split("：", 1)[0])
        if not name or not duty or name in seen:
            continue
        duty = re.sub(r"[（(]\s*(?:兼|主持工作)\s*[）)]", "", duty)
        seen.add(name)
        rows.append(
            {
                "organization": str(page_rule["organization"]),
                "url": str(page_rule["url"]),
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_nanchang_health_duty_name_division_paragraph_v1",
                "selector_summary": "leader=p；pattern=职务后缀+姓名：分工；detail=none",
            }
        )
    if not rows:
        raise RuntimeError("未从领导分工正文中提取到有效人物")
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

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
