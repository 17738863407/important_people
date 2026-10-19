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
    "rule_id": "2653",
    "page_type": "职务分组名单页",
    "structure_group": "leader_info_duty_name_field",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "ShaanxiHealthLeaderInfoFieldParser_v1",
    "leader_region_selector": ".content p",
    "name_selector": "第二个冒号后文本",
    "duty_selector": "两个冒号之间文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "confidence": "high",
    "risk_flag": "机构职能正文较长，只允许解析明确的领导信息字段段落",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(text: str) -> str:
    return " ".join((text or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, base_url: str, rule: dict) -> list[dict[str, str]]:
    """从机构职能页明确的“领导信息：职务：姓名”字段提取记录。"""
    del base_url
    soup = BeautifulSoup(html, "html.parser")
    for paragraph in soup.select(".content p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        match = re.fullmatch(r"领导信息\s*[：:]\s*(.+?)\s*[：:]\s*([\u4e00-\u9fff·]{2,8})", text)
        if match is None:
            continue
        duty = _clean_text(match.group(1))
        name = re.sub(r"\s+", "", match.group(2))
        return [
            {
                "name": name,
                "duty": "",
                "detail_url": "",
                "evidence": duty,
                "parser": rule["parser"],
                "selector_summary": ".content p领导信息字段；职务=两个冒号之间；姓名=第二个冒号后",
                "order": "1",
            }
        ]
    return []


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
