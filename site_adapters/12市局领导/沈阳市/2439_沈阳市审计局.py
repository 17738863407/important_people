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
    "rule_id": "2439", "page_type": "人物列表完整页", "structure_group": "shenyang_audit_image_heading_blocks_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_audit_image_heading_blocks_v2",
    "leader_region_selector": ".view.TRS_UEDITOR中的图片锚点人物块",
    "name_selector": "图片后沈阳市审计局标题p的职务结尾后", "duty_selector": "同一标题p的沈阳市审计局起始原文",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "部分标题同p含办公电话；后续工作分工及页面头尾iframe均须排除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


HEADING_PATTERN = re.compile(
    r"^(?P<duty>沈阳市审计局.*?(?:副局长|局长|主任|总审计师))"
    r"\s*(?P<name>[\u3400-\u9fff](?:[\s\u2000-\u200f\u3000\xa0]*[\u3400-\u9fff]){1,3})$"
)


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按图片锚点顺序拆分标题中的原始职务和末尾姓名。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    content = soup.select_one(".view.TRS_UEDITOR")
    if content is None:
        raise RuntimeError("未定位到审计局领导正文")
    paragraphs = content.find_all("p", recursive=False)
    image_indexes = [index for index, paragraph in enumerate(paragraphs) if paragraph.find("img") is not None]
    if not image_indexes:
        raise RuntimeError("领导正文没有人物图片锚点")
    records: list[object] = []
    seen_names: set[str] = set()
    for position, start in enumerate(image_indexes):
        end = image_indexes[position + 1] if position + 1 < len(image_indexes) else len(paragraphs)
        headings: list[str] = []
        for paragraph in paragraphs[start + 1:end]:
            raw_text = paragraph.get_text("", strip=True)
            text = clean_text(raw_text.split("办公电话", 1)[0])
            if text.startswith("沈阳市审计局"):
                headings.append(text)
        if len(headings) != 1:
            raise RuntimeError(f"图片人物块标题命中数量异常：{len(headings)}")
        match = HEADING_PATTERN.fullmatch(headings[0])
        if match is None:
            raise RuntimeError(f"人物标题无法拆分：{headings[0]}")
        name = re.sub(r"\s+", "", match.group("name"))
        evidence = clean_text(match.group("duty"))
        if name in seen_names:
            raise RuntimeError(f"图片人物块姓名重复：{name}")
        seen_names.add(name)
        records.append(PersonRecord(organization=page_rule["organization"], url=page_rule["url"], name=name, duty=evidence, detail_url="", evidence=evidence, confidence="high", parser=page_rule["parser"]))
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
