from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0771",
    "page_type": "多人物详情合并页",
    "structure_group": "xm_gxj_inline_leader_blocks_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "xm_gxj_inline_leader_blocks_v2",
    "leader_region_selector": ".ldfg_r",
    "name_selector": "h1",
    "duty_selector": "h1后至下一div.ld_img前的现任句",
    "detail_link_selector": "div.ld_img > a[href]",
    "detail_strategy": {"required": False, "mode": "list_item_link"},
    "risk_flag": "主容器后接页脚链接；每人文本必须止于下一头像块，详情链接只取当前姓名前一头像块",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """仅清理HTML排版空白。"""
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value or "").strip()


def collect_profile_text(name_node: object) -> str:
    """收集当前姓名之后、下一人物头像之前的文本。"""
    parts: list[str] = []
    for sibling in name_node.next_siblings:
        if getattr(sibling, "name", None) == "div" and "ld_img" in (sibling.get("class") or []):
            break
        parts.append(sibling.get_text(" ", strip=True) if hasattr(sibling, "get_text") else str(sibling))
    return clean_text(" ".join(parts))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按头像和姓名块的DOM顺序提取现任句及真实人物链接。"""
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("未找到领导分工主容器 .ldfg_r")

    records: list[object] = []
    seen: set[str] = set()
    for name_node in region.select("h1"):
        name = clean_text(name_node.get_text(" ", strip=True)).replace(" ", "")
        evidence_match = re.search(r"现任[^。]*。", collect_profile_text(name_node))
        image_block = name_node.find_previous_sibling("div", class_="ld_img")
        link_node = image_block.select_one("a[href]") if image_block is not None else None
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,10}", name) or evidence_match is None or link_node is None:
            raise RuntimeError(f"人物块缺少可核对字段：{name or '未知姓名'}")
        if name in seen:
            raise RuntimeError(f"人物姓名重复：{name}")
        evidence = re.sub(r"^现任\s*", "", evidence_match.group(0)).removesuffix("。").strip()
        detail_url = urljoin(page_rule["url"], str(link_node.get("href") or ""))
        seen.add(name)
        records.append(
            PersonRecord(
                organization=page_rule["organization"],
                url=page_rule["url"],
                name=name,
                duty=evidence,
                detail_url=detail_url,
                evidence=evidence,
                confidence="high",
                parser=page_rule["parser"],
            )
        )
    if not records:
        raise RuntimeError("领导分工主容器中未提取到人物")
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
