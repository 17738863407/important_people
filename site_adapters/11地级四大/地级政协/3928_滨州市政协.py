from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3928",
    "page_type": "职务标题多人行",
    "structure_group": "binzhou_cppcc_role_lines_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML",
    "fetch_mode": "raw_http",
    "_fetch_mode_override": True,
    "extract_mode": "custom",
    "collector": "raw_http",
    "parser": "page_inline_binzhou_cppcc_lines_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".is-detail",
    "name_selector": "直属段落span冒号后多人名单",
    "duty_selector": "冒号前主席/副主席/秘书长标题",
    "detail_link_selector": "none_article_roster",
    "risk_flag": "副主席为单行多人名单，必须按原始空白分隔顺序拆分",
    "confidence": "high",
}


def clean_text(value: object) -> str:
    """压缩网页排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", str(value or "")).strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """按正文职务行顺序拆分各行人名。"""
    soup = BeautifulSoup(html, "lxml")
    region = soup.select_one(".is-detail")
    if region is None:
        raise RuntimeError("未定位到政协领导名单正文")

    rows: list[dict] = []
    seen_names: set[str] = set()
    valid_duties = {"主席", "副主席", "秘书长"}
    for paragraph in region.find_all("p", recursive=False):
        for field in paragraph.find_all("span", recursive=False):
            text_value = clean_text(field.get_text(" ", strip=True))
            parts = re.split(r"[：:]", text_value, maxsplit=1)
            if len(parts) != 2:
                continue
            duty = parts[0].replace(" ", "")
            if duty not in valid_duties:
                continue
            for name in clean_text(parts[1]).split(" "):
                if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen_names:
                    continue
                seen_names.add(name)
                rows.append(
                    {
                        "name": name,
                        "duty": duty,
                        "evidence": duty,
                        "detail_url": "",
                        "confidence": "high",
                        "parser": page_rule["parser"],
                        "selector_summary": ".is-detail直属段落span职务标题多人行",
                    }
                )

    if not rows:
        raise RuntimeError("政协领导名单正文未提取到有效人物")
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
