from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


PAGE_RULE = {
    "rule_id": "0902", "page_type": "多人物详情合并页", "structure_group": "harbin_duty_name_biography_blocks",
    "reuse_scope": "single_page", "load_mode": "静态HTML直出", "fetch_mode": "requests",
    "extract_mode": "list_direct", "collector": "static_http", "parser": "builtin_parse_page",
    "leader_region_selector": "#detailContent", "name_selector": "职务姓名标题段落",
    "duty_selector": "标题后当前人物工作简历现任句", "detail_link_selector": "",
    "content_scope": {"start_anchor": "", "end_anchor": "", "include_selectors": [], "exclude_selectors": []},
    "detail_strategy": {"required": False, "mode": "none", "max_detail_links": 50},
    "risk_flag": "按标题至下一标题边界绑定工作简历，排除工作分工段落",
    "confidence": "high", "filter_policy": "strong_no_wordlist",
}


def clean_text(value: str) -> str:
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", str(value or "")).strip()


def heading_parts(text: str) -> tuple[str, str]:
    match = re.fullmatch(r"(?P<duty>党组[^ ]+|[一二三四]级(?:巡视员|调研员))\s+(?P<name>[\u4e00-\u9fff· ]{2,12})", text)
    if not match:
        return "", ""
    return clean_text(match.group("name")).replace(" ", ""), clean_text(match.group("duty"))


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = soup.select("#detailContent p")
    rows: list[dict[str, str]] = []
    for index, paragraph in enumerate(paragraphs):
        name, heading_duty = heading_parts(clean_text(paragraph.get_text("", strip=True)))
        if not name:
            continue
        evidence = ""
        for following in paragraphs[index + 1 :]:
            following_text = clean_text(following.get_text("", strip=True))
            if heading_parts(following_text)[0]:
                break
            if not following_text.startswith("工作简历"):
                continue
            match = re.search(r"现任[^。]*(?:。|$)", following_text)
            if match:
                evidence = re.sub(r"^现任\s*", "", clean_text(match.group(0))).rstrip("。 ")
                break
        if not evidence or heading_duty not in evidence:
            raise ValueError(f"当前人物工作简历现任句与标题职务不一致：{name}")
        rows.append({"name": name, "duty": heading_duty, "evidence": evidence, "detail_url": "",
                     "selector_summary": "#detailContent职务姓名标题及当前块工作简历现任句"})
    if not rows:
        raise ValueError("领导信息正文未发现可验证的人物详情块")
    return rows


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter
    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
