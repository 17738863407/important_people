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
    "rule_id": "3100",
    "page_type": "人物表格页",
    "structure_group": "水利信息中心领导班子换行名单",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MwrInformationCenterLeadersParser_v2",
    "leader_region_selector": "span.STYLE18",
    "name_selector": "每个br分隔行冒号前",
    "duty_selector": "每个br分隔行冒号后",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "老式表格页面含大量导航与联系方式；领导班子仅在唯一span.STYLE18中以br分行，姓名含全角空格且无人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", "", value).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按领导班子换行顺序解析“姓名：职务”记录。"""
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one("span.STYLE18")
    if container is None:
        raise RuntimeError("未找到领导班子名单容器span.STYLE18")
    lines = container.get_text("\n", strip=True).splitlines()
    records: list[dict] = []
    seen_names: set[str] = set()
    for line in lines:
        evidence = _clean_text(line)
        matched = re.fullmatch(r"([\u4e00-\u9fff·]{2,5})[：:](.+)", evidence)
        if not matched:
            continue
        name = matched.group(1)
        duty = _clean_text(matched.group(2))
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
                "selector_summary": "唯一span.STYLE18；按br换行；姓名：职务完整原文",
            }
        )
    if not records:
        raise RuntimeError("领导班子容器未解析到姓名职务记录")
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
