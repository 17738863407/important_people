from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "2175",
    "domain": "rf.jiangxi.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "visible_profile_blocks_name_role_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "collector": "static_html",
    "parser": "page_inline_visible_profile_blocks_name_role_v1",
    "leader_region_selector": ".____article_content",
    "person_block_selector": ":scope > div[style*='display: block'][style*='height']",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "正文含整套旧版人物块HTML注释；头像链接不是人物详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩节点中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def extract_name(profile: Tag) -> str:
    """从人物块左栏的20像素姓名节点读取姓名。"""
    for node in profile.select("span[style*='font-size: 20px']"):
        name = re.sub(r"\s+", "", clean_text(node.get_text(" ", strip=True)))
        if re.fullmatch(r"[\u3400-\u9fff·]{2,5}", name):
            return name
    return ""


def extract_duty(profile: Tag) -> str:
    """从同一人物左栏的原始现职段落读取职务。"""
    for node in profile.find_all("p"):
        text = clean_text(node.get_text(" ", strip=True))
        if text and any(keyword in text for keyword in ("党组", "主任", "巡视员")):
            return text
    return ""


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按可见人物块的DOM顺序提取姓名与原始职务。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one(str(page_rule.get("leader_region_selector", "")))
    if region is None:
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for block in region.find_all("div", recursive=False):
        style = clean_text(block.get("style", "")).lower()
        if "display: block" not in style or "height" not in style:
            continue
        profile = block.find("div", recursive=False)
        if profile is None:
            continue
        name = extract_name(profile)
        duty = extract_duty(profile)
        if not name or not duty or name in seen:
            continue

        seen.add(name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.____article_content；"
                    "person=:scope > visible profile div；"
                    "name=left span[font-size:20px]；duty=left role p"
                ),
            }
        )

    return records


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
