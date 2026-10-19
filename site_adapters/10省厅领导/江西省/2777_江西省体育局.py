from __future__ import annotations

import json
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
    "rule_id": "2777",
    "domain": "tyj.jiangxi.gov.cn",
    "page_type": "人物表格页",
    "structure_group": "inline_json_image_name_role_blocks_v1",
    "reuse_scope": "single_page",
    "load_mode": "动态HTML载荷",
    "fetch_mode": "raw_http",
    "extract_mode": "custom",
    "collector": "raw_inline_json",
    "parser": "page_inline_json_image_name_role_blocks_v1",
    "person_text_selector": "p > span[style*='font-size: 29px']",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物正文由内联JSON载荷渲染；头像锚点仅链接JPG文件",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: object) -> str:
    """压缩载荷正文中的排版空白，不改变职务语义。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def iter_embedded_content(html: str) -> list[str]:
    """解析页面脚本中的JSON对象，并返回其中动态下发的正文HTML。"""
    decoder = json.JSONDecoder()
    contents: list[str] = []
    for match in re.finditer(r"(?:[\"']?content[\"']?)\s*:\s*(?=\{)", html):
        try:
            payload, _ = decoder.raw_decode(html, match.end())
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        content = payload.get("content")
        if isinstance(content, str) and content not in contents:
            contents.append(content)
    return contents


def parse_content(content: str, page_rule: dict[str, object], final_url: str) -> list[dict[str, str]]:
    """按人物正文段落顺序配对29像素姓名段和紧随其后的职务段。"""
    soup = BeautifulSoup(content, "html.parser")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    pending_name = ""

    for paragraph in soup.find_all("p", recursive=False):
        if not paragraph.select("span[style*='font-size: 29px']"):
            continue
        text = clean_text(paragraph.get_text("", strip=True))
        compact_text = re.sub(r"\s+", "", text)
        if re.fullmatch(r"[\u3400-\u9fff·]{2,5}", compact_text):
            pending_name = compact_text
            continue
        if not pending_name or not any(keyword in text for keyword in ("党组", "局长", "巡视员")):
            continue
        if pending_name in seen:
            pending_name = ""
            continue

        seen.add(pending_name)
        records.append(
            {
                "organization": str(page_rule.get("organization", "")),
                "url": str(page_rule.get("url", "")) or final_url,
                "name": pending_name,
                "duty": text,
                "detail_url": "",
                "evidence": text,
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；source=inline JSON content；"
                    "person=p sequence；name=29px exact Han paragraph；duty=next 29px role paragraph"
                ),
            }
        )
        pending_name = ""

    return records


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """动态选择人物正文载荷并提取人物块。"""
    for content in iter_embedded_content(html):
        if "font-size: 29px" not in content:
            continue
        records = parse_content(content, page_rule, final_url)
        if records:
            return records
    return []


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
