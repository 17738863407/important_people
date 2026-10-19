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
    "rule_id": "3984", "domain": "www.ebchina.com", "page_type": "集团领导履历列表",
    "structure_group": "everbright_group_leader_profiles", "reuse_scope": "everbright_group_leaders",
    "load_mode": "静态HTML直出", "fetch_mode": "online", "extract_mode": "list_direct", "collector": "static_http",
    "parser": "page_everbright_group_leader_profiles_v1", "leader_region_selector": ".articleWrap",
    "name_selector": ".articleWrap dl dd h2", "duty_selector": ".articleWrap dl dd",
    "content_scope": {"include_selectors": [".articleWrap"], "exclude_selectors": ["script", "style"]},
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "标题含中英文姓名且正文混合学历履历，只能在单个dl内提取中文姓名和完整现任句",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
    "locator": {"css": {"record_selector": ".articleWrap > dl", "name_selector": "dd h2", "bio_selector": "dd"}},
}


def normalize_text(value: str) -> str:
    """将富文本排版空白规范为单个空格。"""
    return re.sub(r"[\s\u00a0\u3000]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """逐个领导dl提取标题开头中文姓名与正文完整现任句。"""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    for card in soup.select(".articleWrap > dl"):
        heading = card.select_one("dd h2")
        content = card.select_one("dd")
        heading_text = normalize_text(heading.get_text(" ", strip=True)) if heading else ""
        name_match = re.match(r"([\u3400-\u9fff·]{2,4})(?:\s|$)", heading_text)
        bio = normalize_text(content.get_text(" ", strip=True)) if content else ""
        duty_match = re.search(r"现任([^。]+)", bio)
        name = name_match.group(1) if name_match else ""
        duty = duty_match.group(1).strip("。；; ") if duty_match else ""
        if not name or not duty:
            continue
        rows.append({
            "name": name, "duty": duty, "evidence": duty, "detail_url": "",
            "parser": str(page_rule.get("parser", "")), "selector_summary": "领导dl标题中文姓名及正文完整现任句",
        })
    if not rows:
        raise RuntimeError("集团领导履历区未解析出有效人物")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
