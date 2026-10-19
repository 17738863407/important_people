from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0]+", " ", value or "").strip()


def is_hidden(node: Tag, boundary: Tag) -> bool:
    """排除正文中通过属性或内联样式隐藏的节点。"""
    current: Tag | None = node
    while current is not None:
        classes = {str(item).lower() for item in (current.get("class") or [])}
        style = re.sub(r"\s+", "", str(current.get("style") or "")).lower()
        if (
            current.has_attr("hidden")
            or str(current.get("aria-hidden") or "").lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "hide", "none"})
        ):
            return True
        if current is boundary:
            break
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """以人物图片为卡片起点，读取其后的首个非空职务姓名段落。"""
    soup = BeautifulSoup(html or "", "html.parser")
    region = soup.select_one("#cont")
    if region is None:
        raise RuntimeError("院领导简介页缺少正文区域 #cont")

    rows: list[dict[str, str]] = []
    seen_names: set[str] = set()
    waiting_for_caption = False
    for paragraph in region.select("p"):
        if is_hidden(paragraph, region):
            continue
        if paragraph.select_one("img[src]") is not None:
            waiting_for_caption = True
            continue
        if not waiting_for_caption:
            continue
        text = clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        match = re.fullmatch(r"(.+?)\s+([\u3400-\u9fff·]{2,10})", text)
        if match is None:
            raise RuntimeError(f"人物图片后的职务姓名段落格式异常：{text}")
        duty = clean_text(match.group(1)).strip("：:，,；; ")
        name = match.group(2)
        waiting_for_caption = False
        if not duty:
            raise RuntimeError(f"人物图片后的职务证据为空：{text}")
        if name in seen_names:
            raise RuntimeError(f"人物卡片出现重复姓名：{name}")
        seen_names.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": "#cont中人物图片后的首个非空职务姓名段落",
            }
        )
    if not rows:
        raise RuntimeError("院领导简介正文未提取到领导人物")
    return rows


PAGE_RULE = {
    "rule_id": "4557",
    "page_type": "检察院领导头像职务姓名正文",
    "structure_group": "ningxia_procuratorate_leader_paragraphs_v1",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "parser": "page_ningxia_procuratorate_leader_paragraphs_v1",
    "leader_region_selector": "#cont",
    "name_selector": "#cont人物图片后的首个非空p中末尾姓名",
    "duty_selector": "#cont人物图片后的首个非空p中姓名前文本",
    "detail_link_selector": "页面未提供独立人物链接",
    "detail_strategy": {"required": False, "mode": "none"},
    "locator_strategy": "custom_parse_page",
    "risk_flag": "正文以人物图片和紧随其后的职务姓名段落组成卡片；动态遍历全部卡片以纳入末尾专职委员，共用文章不作为人物详情页",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    print(f"输出文件：{run_page_adapter(PAGE_RULE, globals(), update_fetch_memory=False)}")


if __name__ == "__main__":
    main()
