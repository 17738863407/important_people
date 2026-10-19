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
    "rule_id": "1586",
    "page_type": "人物表格页",
    "structure_group": "正文BR分隔职务姓名行",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "MiitcfcLeaderFontLineParser_v2",
    "leader_region_selector": ".s4_con font",
    "name_selector": "",
    "duty_selector": "",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "领导信息由font内BR分隔，页面无独立人物详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按正文BR行序动态抽取职务和姓名。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".s4_con font")
    if region is None:
        raise RuntimeError("未找到中心领导正文 .s4_con font")

    rows: list[dict] = []
    for raw_line in region.get_text("\n", strip=True).splitlines():
        evidence = _clean_text(raw_line)
        match = re.fullmatch(r"(?P<duty>中心[\u4e00-\u9fff]+)\s+(?P<name>[\u4e00-\u9fff]{2,4})", evidence)
        if not match:
            continue
        rows.append(
            {
                "name": match.group("name"),
                "duty": match.group("duty"),
                "evidence": match.group("duty"),
                "detail_url": "",
                "parser": PAGE_RULE["parser"],
                "selector_summary": ".s4_con font；BR分行",
            }
        )

    if not rows:
        raise RuntimeError("中心领导正文未解析到职务姓名行")
    return rows


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
