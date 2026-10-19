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
    "rule_id": "1840",
    "page_type": "人物列表完整页",
    "structure_group": "教育技术与资源发展中心领导列表",
    "reuse_scope": "ncet_leader_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "NcetLeaderColonParser_v2",
    "leader_region_selector": ".JianJie ul.Ling_l",
    "name_selector": "li冒号前文本",
    "duty_selector": "li完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "全页存在大量导航li，必须限定.JianJie ul.Ling_l；人物采用姓名在前、职务在后的冒号格式，页面无人物独立详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """限定中心领导列表，按列表顺序解析冒号前姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one(".JianJie ul.Ling_l")
    if container is None:
        raise RuntimeError("中心领导页面未找到.JianJie ul.Ling_l")

    records: list[dict] = []
    seen_names: set[str] = set()
    for item in container.select(":scope > li"):
        evidence = _clean_text(item.get_text(" ", strip=True))
        matched = re.fullmatch(r"([\u4e00-\u9fff·](?:\s*[\u4e00-\u9fff·]){1,4})[：:]\s*(.+)", evidence)
        if not matched:
            continue
        name = re.sub(r"\s+", "", matched.group(1))
        duty = matched.group(2)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".JianJie ul.Ling_l > li；姓名：职务完整段落",
            }
        )
    if not records:
        raise RuntimeError("中心领导列表未解析到人物记录")
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
