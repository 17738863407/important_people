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
    "rule_id": "0307",
    "page_type": "职务分组名单页",
    "structure_group": "最高法职能机构多单元格职务姓名表格",
    "reuse_scope": "court_function_department",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CourtDepartmentDutyNameCellsParser_v1",
    "leader_region_selector": ".txt_txt table tr",
    "name_selector": "同一单元格冒号后或下一非空单元格",
    "duty_selector": "单元格冒号前",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "表格同时含职责、图片、空职务和一行多人物；仅按单元格边界配对非空职务姓名",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    """清理网页排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按表格行和单元格DOM顺序解析“职务：姓名”。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for row in soup.select(".txt_txt table tr"):
        pending_duty = ""
        for cell in row.select(":scope > th, :scope > td"):
            text = _clean_text(cell.get_text(" ", strip=True))
            if not text:
                continue
            full_pair = re.fullmatch(r"(.+?)[：:]([\u4e00-\u9fff·]{2,5})", text)
            if full_pair:
                duty, name = full_pair.groups()
            elif re.fullmatch(r".+?[：:]", text):
                pending_duty = text.rstrip("：:")
                continue
            elif pending_duty and re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", text):
                duty, name = pending_duty, text
                pending_duty = ""
            else:
                pending_duty = ""
                continue
            if name in seen_names:
                continue
            seen_names.add(name)
            records.append(
                {
                    "name": name,
                    "duty": duty,
                    "evidence": duty,
                    "detail_url": "",
                    "parser": PAGE_RULE["parser"],
                    "selector_summary": ".txt_txt table tr > td；按单元格配对职务：姓名",
                }
            )
    if not records:
        raise RuntimeError("职务姓名表格未解析到人物记录")
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
