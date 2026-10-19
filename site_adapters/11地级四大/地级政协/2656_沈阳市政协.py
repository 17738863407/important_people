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
    "rule_id": "2656",
    "page_type": "人物列表完整页",
    "structure_group": "shenyang_cppcc_single_text_group",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "requests",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "page_inline_shenyang_cppcc_text_group_v2",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": "ul.list22 li p.mt10 a",
    "name_selector": "职务标签后的中文姓名",
    "duty_selector": "主席、副主席、秘书长人选文本标签",
    "detail_link_selector": "",
    "risk_flag": "领导名单集中在单条文本中，须限定领导列表项并按明确职务标签分组",
    "confidence": "high",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _append_row(rows: list[dict[str, str]], name: str, duty: str) -> None:
    rows.append(
        {
            "name": name,
            "duty": duty,
            "detail_url": "",
            "evidence": duty,
            "confidence": "high",
            "parser": "page_inline_shenyang_cppcc_text_group_v2",
        }
    )


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """解析领导列表项中的“职务—姓名”分组，保持网页原始顺序。"""
    soup = BeautifulSoup(html, "lxml")
    leader_node = soup.select_one("ul.list22 li p.mt10 a")
    if leader_node is None:
        raise RuntimeError("未找到政协领导名单文本")
    text = _clean_text(leader_node.get_text(" ", strip=True))
    match = re.fullmatch(
        r"主\s*席\s+(?P<chair>[\u3400-\u9fff]{2,4})\s+"
        r"副主席\s+(?P<vice>.+?)\s+"
        r"秘书长人选\s+(?P<secretary>[\u3400-\u9fff]{2,4})",
        text,
    )
    if not match:
        raise RuntimeError("政协领导名单文本不符合预期职务分组结构")
    rows: list[dict[str, str]] = []
    _append_row(rows, match.group("chair"), "主席")
    for name in re.split(r"[、，,]\s*", match.group("vice")):
        name = _clean_text(name)
        if not re.fullmatch(r"[\u3400-\u9fff]{2,4}", name):
            raise RuntimeError(f"副主席姓名格式异常：{name}")
        _append_row(rows, name, "副主席")
    _append_row(rows, match.group("secretary"), "秘书长人选")
    return rows


def main() -> None:
    """运行当前页面级在线爬虫。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
