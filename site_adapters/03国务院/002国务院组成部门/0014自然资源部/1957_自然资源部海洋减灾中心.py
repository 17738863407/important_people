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
    "rule_id": "1957",
    "page_type": "人物列表完整页",
    "structure_group": "海洋减灾中心姓名空格职务段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NmhmsLeaderWhitespaceParagraphParser_v2",
    "leader_region_selector": ".page-box-content",
    "name_selector": "p文本连续空格分隔符前",
    "duty_selector": "p文本连续空格分隔符后",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "姓名内部与姓名职务之间均使用不换行空格；必须按较长空格边界拆分并动态解析，禁止固定人物表",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _parse_line(value: str) -> tuple[str, str]:
    raw = value.replace("\u3000", " ").replace("\xa0", " ").strip()
    parts = re.split(r"\s{4,}", raw, maxsplit=1)
    if len(parts) != 2:
        return "", ""
    name = re.sub(r"\s+", "", parts[0])
    duty = re.sub(r"\s+", " ", parts[1]).strip(" ：:，,。.")
    if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty:
        return "", ""
    return name, duty


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按段落原始连续空格边界动态拆分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".page-box-content")
    if region is None:
        raise RuntimeError("未找到中心领导正文区域")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        name, duty = _parse_line(paragraph.get_text(" ", strip=True))
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".page-box-content p；4个以上连续空格分隔姓名与职务；无人物链接",
            }
        )
    if not records:
        raise RuntimeError("中心领导正文未解析到人物记录")
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
