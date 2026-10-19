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
    "rule_id": "2948",
    "page_type": "多人物详情合并页",
    "structure_group": "wulumuqi_housing_current_duty_paragraphs_v2",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "custom_parse_page",
    "parser": "wulumuqi_housing_current_duty_paragraphs_v2",
    "leader_region_selector": "#NewsContent .gjnr",
    "name_selector": "人物段加粗职务后、同志前姓名；兼容旧页现任标记前姓名",
    "duty_selector": "人物段加粗姓名前职务；兼容旧页现任标记后的完整原始职务",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "人物现职段后紧随一至两段负责和分管内容，原HTML含职务字距空格",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def clean_text(value: str) -> str:
    """确定性清理现职字段的排版空白。"""
    text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", value or "").strip()
    text = re.sub(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])", "", text)
    return re.sub(r"\s*([，、；：（）])\s*", r"\1", text)


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """按人物段DOM顺序提取加粗职务姓名，兼容旧版现任句结构。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html or "", "html.parser")
    regions = soup.select("#NewsContent .gjnr")
    if len(regions) != 1:
        raise RuntimeError(f"领导正文区域数量异常：{len(regions)}")
    pattern = re.compile(
        r"^(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,19}?)"
        r"\s+现任\s*(?P<duty>.+)$"
    )

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in regions[0].select("p"):
        if paragraph.select_one("p") is not None:
            continue
        text = re.sub(r"[\s\u2000-\u200f\u3000\xa0]+", " ", paragraph.get_text(" ", strip=True)).strip()
        match = pattern.fullmatch(text)
        if match is not None:
            name = match.group("name").replace(" ", "")
            evidence = clean_text(match.group("duty"))
        else:
            bold_text = re.sub(
                r"[\s\u2000-\u200f\u3000\xa0]+",
                " ",
                " ".join(node.get_text(" ", strip=True) for node in paragraph.select("b")),
            ).strip()
            bold_match = re.fullmatch(
                r"(?P<duty>.+?)\s+"
                r"(?P<name>[\u3400-\u9fff·](?:\s*[\u3400-\u9fff·]){1,3})\s*同志[，,]?",
                bold_text,
            )
            if bold_match is None:
                continue
            name = re.sub(r"\s+", "", bold_match.group("name"))
            evidence = clean_text(bold_match.group("duty"))
            if not any(keyword in evidence for keyword in ("书记", "局长", "调研员")):
                raise RuntimeError(f"加粗人物段缺少可验证职务关键词：{text}")
        if not re.fullmatch(r"[\u3400-\u9fff·]{2,4}", name) or not evidence:
            raise RuntimeError(f"人物姓名或职务格式异常：{text}")
        if name in seen_names:
            raise RuntimeError(f"人物姓名重复：{name}")
        if paragraph.select_one("a[href]") is not None:
            raise RuntimeError(f"人物现职段出现未审计链接：{name}")
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
        raise RuntimeError("领导正文没有可验证的人物现职段")
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
