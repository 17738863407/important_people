from __future__ import annotations

import sys
import re
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4560",
    "page_type": "法院领导段落名单",
    "structure_group": "shanxi_high_court_paragraph_list_v1",
    "reuse_scope": "single_page",
    "load_mode": "浏览器渲染（站点拒绝普通HTTP客户端）",
    "force_browser": True,
    "extract_mode": "paragraph_list",
    "parser": "page_shanxi_high_court_paragraph_list_v1",
    "leader_region_selector": ".text.general",
    "name_selector": ".text.general > p 姓名前缀",
    "duty_selector": ".text.general > p 机构全称起始文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "risk_flag": "同一领导正文含仅任审判委员会专职委员者；按正文原序全部保留。",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按正文段落原序拆分姓名和完整职务，包括仅任委员者。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(".text.general")
    if region is None:
        raise RuntimeError("未找到法院领导正文 .text.general")
    rows: list[dict[str, str]] = []
    for paragraph in region.find_all("p", recursive=False):
        text = re.sub(r"[\s\u00a0\u3000]+", "", paragraph.get_text(" ", strip=True))
        match = re.match(r"^([\u3400-\u9fff·]{2,4})(?=山西省(?:高级人民法院|纪委监委))", text)
        if match is None:
            continue
        name, evidence = match.group(1), text[match.end():]
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name):
            continue
        rows.append({"name": name, "duty": evidence, "evidence": evidence, "detail_url": "", "confidence": "high", "parser": str(page_rule.get("parser", "")), "selector_summary": ".text.general直属p按机构全称切分姓名职务；委员及专职委员段落保留"})
    if not rows:
        raise RuntimeError("法院领导正文未提取到有效领导")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
