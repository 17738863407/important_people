from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "3153",
    "page_type": "多人物详情合并页",
    "structure_group": "yinchuan_earthquake_combined_profiles_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_yinchuan_earthquake_combined_profiles_v2",
    "leader_region_selector": ".zwxxgk_bd",
    "name_selector": "叶级人物简介段首姓名或明确调研员句姓名",
    "duty_selector": "人物简介段完整现任句或明确调研员原句",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [".zwxxgk_bd"],
        "exclude_selectors": [],
    },
    "detail_strategy": {
        "required": False,
        "mode": "none",
        "detail_collector_type": "static_http",
        "detail_link_selector": None,
        "detail_name_selector": "",
        "detail_duty_selector": "",
        "detail_content_selector": "",
        "max_detail_links": 0,
    },
    "risk_flag": "正文存在包裹全部内容的嵌套p与叶级人物p；排除含子p的重复容器",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


PROFILE_PATTERN = re.compile(r"^([\u4e00-\u9fff·]{2,4})\s*[，,].*?(现\s*任\s*[^。]*。)")
ASSISTING_PATTERN = re.compile(r"^三级调研员\s*([\u4e00-\u9fff·]{2,4})\s*同志[^。]*。$")


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def _clean_text(value: str) -> str:
    """压缩正文中的全角空格和连续空白。"""
    return " ".join(str(value or "").replace("\u3000", " ").replace("\xa0", " ").split())


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    """按叶级正文段落提取现任句和网页明确标注的调研员句。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector") or ""))
    if region is None:
        return []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for paragraph in region.select("p"):
        if paragraph.select_one("p") is not None:
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True))
        profile_match = PROFILE_PATTERN.search(text)
        assisting_match = ASSISTING_PATTERN.fullmatch(text)
        if profile_match is not None:
            name = "".join(profile_match.group(1).split())
            evidence = _clean_text(profile_match.group(2)).removeprefix("现任").removesuffix("。").strip()
        elif assisting_match is not None:
            name = "".join(assisting_match.group(1).split())
            evidence = re.sub(rf"{re.escape(name)}同志.*$", "", text).strip("，、；。 ")
        else:
            continue
        if name in seen:
            continue
        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": evidence,
                "evidence": evidence,
                "detail_url": "",
                "parser": str(page_rule.get("parser") or ""),
                "selector_summary": ".zwxxgk_bd内不含子p的叶级段落；完整现任句或明确三级调研员原句",
            }
        )
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
