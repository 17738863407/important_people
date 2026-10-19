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
    "rule_id": "4538", "page_type": "已核验领导页面",
    "structure_group": "henan_high_court_verified_v1", "reuse_scope": "single_page",
    "load_mode": "静态HTML", "extract_mode": "custom", "parser": "page_henan_high_court_v1",
    "leader_region_selector": "当前领导正文",
    "name_selector": "当前领导姓名", "duty_selector": "对应现任职务",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page", 
    "confidence": "high", "filter_policy": "strong_no_wordlist",
    "risk_flag": "仅提取当前领导人物简介中可回指的现任职务；领导区内委员、专职委员同样保留。",
}

def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    rows = []
    for node in soup.find_all("a"):
        text = clean(node.get_text(" ", strip=True))
        match = re.search(r"^([\u3400-\u9fff·]{2,10})，.*?现任(河南省高级人民法院[^。]+)", text)
        if match:
            rows.append({"name": match.group(1), "duty": match.group(2), "evidence": match.group(2), "detail_url": urljoin(final_url, node.get("href", "")), "parser": str(page_rule.get("parser", "")), "selector_summary": "当前领导人物链接简介中的现任职务；委员职务同样保留"})
    if not rows: raise RuntimeError("当前领导区域未提取到人物")
    return rows

def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path: sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals())}")

if __name__ == "__main__":
    main()
