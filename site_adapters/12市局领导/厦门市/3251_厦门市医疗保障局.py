from __future__ import annotations

import re
import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "3251",
    "page_type": "图片人物块相邻HTML简介",
    "structure_group": "xm_healthcare_portrait_html_profile_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_healthcare_portrait_html_profile_v2",
    "leader_region_selector": ".ldfg_con",
    "name_selector": ".ldfg_con .ldfg_txt p span",
    "duty_selector": ".ldfg_con .ldfg_txt1 p.f_i内完整现任句",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "页面含人物头像但姓名与简介为可验证HTML文本；职务链接回到入口页，不作为详情链接",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物块顺序从HTML姓名字段及当前简介提取可回指结果。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    records: list[object] = []
    seen_names: set[str] = set()
    for block in soup.select(page_rule["leader_region_selector"]):
        name = ""
        for node in block.select(".ldfg_txt p span"):
            match = re.match(r"^姓名\s*[：:]\s*([\u3400-\u9fff·]{2,10})$", clean_text(node.get_text(" ", strip=True)))
            if match is not None:
                name = match.group(1)
                break
        if not name:
            continue
        evidence = ""
        for paragraph in block.select(".ldfg_txt1 p.f_i"):
            text = clean_text(paragraph.get_text(" ", strip=True))
            match = re.search(r"现任[^。]*。", text)
            if match is not None and name in re.sub(r"\s+", "", text):
                evidence = re.sub(
                    r"^现任(?:职务)?(?:\s*[：:]\s*)?\s*",
                    "",
                    match.group(0),
                    count=1,
                )
                break
        if not evidence:
            raise RuntimeError(f"人物块缺少与姓名对应的完整现任句：{name}")
        if name in seen_names:
            raise RuntimeError(f"人物块姓名重复：{name}")
        seen_names.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url="",
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导人物块中未提取到HTML姓名与现任句")
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
