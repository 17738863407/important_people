from __future__ import annotations

import sys
from pathlib import Path
import re

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '3181',
 'page_type': '人物列表完整页',
 'reuse_scope': 'single_page',
 'load_mode': '静态HTML直出',
 'fetch_mode': 'online',
 'extract_mode': 'list_direct',
 'parser': 'page_parse_page',
 'leader_region_selector': '.view.TRS_UEDITOR',
 'name_selector': '简介段开头、性别字段前姓名',
 'duty_selector': '简介段中文分号后的现任职务原句',
 'detail_link_selector': '',
 'detail_strategy': {'required': False, 'mode': 'none'},
 'risk_flag': '',
 'confidence': 'high',
 'filter_policy': 'strong_no_wordlist',
 'risk_note': '简介段后紧随工作分工，页面末尾还有AB岗说明；只保留简介分号后的现任职务原句。'}


def _clean_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\u3000", " ")
    text = " ".join(text.split())
    text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
    text = re.sub(r"(?<=[，、；：])\s+", "", text)
    return re.sub(r"\s+(?=[，。；：])", "", text)


def _clean_name(text: str) -> str:
    return re.sub(r"[，,、：:\s]+$", "", "".join(_clean_text(text).split()))


def _extract_name(text: str) -> str:
    match = re.match(r"^(.{2,8}?)[，,]\s*[男女]", text)
    return _clean_name(match.group(1)) if match else ""


def _extract_position(text: str) -> str:
    if "；" in text:
        return _clean_text(text.rsplit("；", 1)[-1].rstrip("。"))
    return ""


def parse_page(html: str, base_url: str, rule: dict) -> list[dict]:
    """解析银川市卫生健康委员会领导简介和工作分工。"""
    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for paragraph in soup.select(".view.TRS_UEDITOR p"):
        text = _clean_text(paragraph.get_text(" ", strip=True))
        if not text:
            continue
        name = _extract_name(text)
        position = _extract_position(text)
        if not name or not position:
            continue
        evidence = f"{position}。" if text.rstrip().endswith("。") else position
        records.append(
            {
                "name": name,
                "duty": evidence,
                "detail_url": "",
                "evidence": evidence,
                "parser": "page_parse_page",
                "selector_summary": "strategy=page_parse_page；region=.view.TRS_UEDITOR；name=简介段首；duty=中文分号后原句；detail=none",
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
