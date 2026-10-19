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
    "rule_id": "3410",
    "page_type": "人物列表完整页",
    "structure_group": "地图审查中心姓名机构职务列表",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MapReviewCenterLeaderListParser_v2",
    "leader_region_selector": ".fg-box ul > li a",
    "name_selector": "机构前缀前文本",
    "duty_selector": "机构前缀起始文本",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同容器另含单位概况等导航链接；仅接受包含完整机构前缀的条目，领导a当前无href",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按列表顺序以完整机构前缀切分姓名和职务。"""
    soup = BeautifulSoup(html, "html.parser")
    prefix = "自然资源部地图技术审查中心"
    records: list[dict] = []
    seen_names: set[str] = set()
    for link in soup.select(".fg-box ul > li a"):
        date_node = link.select_one("span")
        if date_node is not None:
            date_node.extract()
        text = _clean_text(link.get_text(" ", strip=True))
        if prefix not in text:
            continue
        raw_name, duty_tail = text.split(prefix, 1)
        name = re.sub(r"\s+", "", raw_name)
        duty = prefix + _clean_text(duty_tail)
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", name) or not duty_tail.strip() or name in seen_names:
            continue
        seen_names.add(name)
        records.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".fg-box ul > li a；机构前缀切分姓名/完整职务；领导a无href",
            }
        )
    if not records:
        raise RuntimeError("领导信息列表未解析到人物记录")
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
