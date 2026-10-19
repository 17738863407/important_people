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
    "rule_id": "0245",
    "page_type": "多人物详情合并页",
    "structure_group": "现任领导头像与职务姓名段落",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "static_http",
    "parser": "CivteCurrentLeadersParagraphParser_v2",
    "leader_region_selector": "div.about-p #vsb_content_503",
    "name_selector": "p冒号后",
    "duty_selector": "p完整原文",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面头部兼容脚本含旧版浏览器提示，使用raw_http保留权威静态正文；只解析现任领导内容区的职务姓名段落",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ").replace("\u3000", " ")).strip()


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """按现任领导正文中头像后职务姓名段落的DOM顺序抽取。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    seen_names: set[str] = set()
    for paragraph in soup.select("div.about-p #vsb_content_503 p"):
        evidence = _clean_text(paragraph.get_text(" ", strip=True))
        matched = re.fullmatch(r"(.+?)[：:]\s*([\u4e00-\u9fff·]{2,5})", evidence)
        if not matched:
            continue
        duty = _clean_text(matched.group(1))
        name = matched.group(2)
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
                "selector_summary": "div.about-p #vsb_content_503 p；职务：姓名完整段落；排除图片空段与历任领导页",
            }
        )
    if not records:
        raise RuntimeError("现任领导职务姓名段落未解析到人物记录")
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
