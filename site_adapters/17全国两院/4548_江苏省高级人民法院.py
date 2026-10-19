from __future__ import annotations
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup

def resolve_project_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

def clean(value: object) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", str(value or ""))

PAGE_RULE = {
    "rule_id": "4548", "page_type": "已核验领导页面",
    "structure_group": "jiangsu_high_court_verified_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_jiangsu_high_court_v1",
    "leader_region_selector": "当前领导正文",
    "name_selector": "当前领导姓名", "duty_selector": "对应现任职务",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", 
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "只解析当前领导正文中相邻的姓名—职务结构；领导区域中的审判委员会委员、检察委员会委员和专职委员均保留。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    lines = [clean(x) for x in BeautifulSoup(html or "", "html.parser").get_text("\n").splitlines() if clean(x)]
    rows = []
    for index, name in enumerate(lines):
        if re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) and index + 1 < len(lines):
            duty = lines[index + 1]
            if duty.startswith("江苏省") and any(x in duty for x in ("院长", "副院长", "纪检监察组组长", "政治部主任", "委员")):
                rows.append({"name": name, "duty": duty, "evidence": duty, "detail_url": "", "parser": str(page_rule.get("parser", "")), "selector_summary": "法院领导正文相邻姓名—职务；委员和专职委员职务完整保留"})
    if not rows: raise RuntimeError("法院领导正文未提取到有效领导")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")

if __name__ == "__main__":
    main()
