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
    "rule_id": "1200",
    "page_type": "人物目录详情页",
    "structure_group": "姓名与机构职务换行列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MofFinanceDepartmentLeaderLineParser_v2",
    "leader_region_selector": ".TRS_Editor",
    "risk_flag": "姓名内部含字距空白，页面无人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _compact_text(value: str) -> str:
    """仅清除行内排版空白。"""
    return re.sub(r"[\s\u00a0\u3000\u2002-\u200b]+", "", str(value or "")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文换行顺序，以机构职务前缀切分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(rule["leader_region_selector"])
    if region is None:
        return []
    records: list[dict] = []
    seen: set[str] = set()
    for line in region.get_text("\n", strip=True).splitlines():
        compact_line = _compact_text(line)
        match = re.fullmatch(r"([\u4e00-\u9fff·]{2,8})(金融司.+)", compact_line)
        if not match:
            continue
        name, duty = match.groups()
        duty = re.sub(r"[（(]\s*挂职\s*[）)]", "", duty).strip()
        if name in seen:
            continue
        seen.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": rule["parser"],
                "selector_summary": ".TRS_Editor换行列表；金融司职务前缀切分姓名",
            }
        )
    return records


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
