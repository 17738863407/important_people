from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {
    "rule_id": "3155",
    "page_type": "人物列表完整页",
    "structure_group": "yinchuan_police_profile_duty_v3",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_public_security_leader_v3",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".content .view.TRS_UEDITOR p",
    "name_selector": "人物简介段首姓名",
    "duty_selector": "人物简介段中简历信息后的职务片段",
    "detail_link_selector": "",
    "risk_flag": "只解析正文中以姓名和性别开头的人物简介段，职务使用简历字段后的页面原文，后续分工段落不得并入",
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


def compact_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").replace("\xa0", " ").replace("\u3000", " ")).strip()


def normalize_duty(value: str) -> str:
    return value.strip("。；;")


def extract_duty(text: str) -> str:
    if "；" in text:
        return normalize_duty(text.rsplit("；", 1)[1])
    if "。" in text:
        return normalize_duty(text.rsplit("。", 1)[1])
    return ""


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """解析银川市公安局领导信息段落。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in soup.select(page_rule["leader_region_selector"]):
        if paragraph.find("p") is not None:
            continue
        text = compact_text(paragraph.get_text("", strip=True))
        match = re.match(r"^([\u4e00-\u9fa5]{2,4})[，,]男|^([\u4e00-\u9fa5]{2,4})[，,]女", text)
        if not match:
            continue
        name = match.group(1) or match.group(2)
        duty = extract_duty(text)
        if name in seen or not duty:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": page_rule["parser"],
            }
        )
    if not rows:
        raise RuntimeError("领导信息正文未解析出人物姓名和职务片段")
    return rows


if __name__ == "__main__":
    main()
