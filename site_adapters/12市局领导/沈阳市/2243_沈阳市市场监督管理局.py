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
    "rule_id": "2243", "page_type": "人物列表完整页", "structure_group": "shenyang_market_image_paragraph_blocks_v2",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "online",
    "extract_mode": "custom_parse_page", "parser": "shenyang_market_image_paragraph_blocks_v2",
    "leader_region_selector": "唯一div.view.TRS_UEDITOR中的图片锚点人物块",
    "name_selector": "当前图片p之后首个非空p", "duty_selector": "当前图片p之后第二个非空p",
    "detail_link_selector": "", "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "第三个非空p为工作分工；末尾办公信息在人物块之后，均须排除",
    "confidence": "high", "filter_policy": "strong_no_wordlist", "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML节点中的排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按图片锚点顺序提取其后姓名和原始职务段落。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    views = soup.select("div.view.TRS_UEDITOR")
    if len(views) != 1:
        raise RuntimeError(f"人物正文命中数量异常：{len(views)}")
    paragraphs = views[0].find_all("p", recursive=False)
    image_indexes = [index for index, paragraph in enumerate(paragraphs) if paragraph.find("img") is not None]
    if not image_indexes:
        raise RuntimeError("人物正文没有图片锚点")
    records: list[object] = []
    seen_names: set[str] = set()
    for position, start in enumerate(image_indexes):
        end = image_indexes[position + 1] if position + 1 < len(image_indexes) else len(paragraphs)
        texts = [clean_text(node.get_text(" ", strip=True)) for node in paragraphs[start + 1:end]]
        texts = [text for text in texts if text]
        if len(texts) < 2:
            raise RuntimeError("图片人物块缺少姓名或职务段落")
        name = re.sub(r"\s+", "", texts[0])
        evidence = texts[1]
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or not evidence:
            raise RuntimeError("图片人物块姓名或职务字段异常")
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
