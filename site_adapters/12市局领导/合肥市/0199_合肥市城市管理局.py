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
    "rule_id": "0199",
    "page_type": "多人物详情合并页",
    "structure_group": "hefei_profile_paragraph_current_duty",
    "reuse_scope": "single_page",
    "load_mode": "动态DOM渲染",
    "fetch_mode": "online",
    "force_browser": True,
    "extract_mode": "merged_profiles",
    "collector": "browser_dom",
    "parser": "hefei_city_management_profile_current_duty_v1",
    "leader_region_selector": "#zoom",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "content_scope": {
        "start_anchor": "",
        "end_anchor": "",
        "include_selectors": [],
        "exclude_selectors": [],
    },
    "risk_flag": "正文同时含简历、分工和办公电话，只接受人物简介首段内的完整现任句",
    "confidence": "high",
    "profile_reusable": "",
    "profile_judgement": "",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    """仅清理网页排版空白，不改写语义内容。"""
    return re.sub(r"[\s\u3000\xa0\u2000-\u200b]+", " ", value).strip()


def _is_hidden(node: object) -> bool:
    """排除当前节点及祖先上的明确隐藏标记。"""
    current = node
    while getattr(current, "name", None):
        attrs = getattr(current, "attrs", {}) or {}
        style = str(attrs.get("style", "")).replace(" ", "").lower()
        classes = {str(item).lower() for item in attrs.get("class", [])}
        if attrs.get("hidden") is not None or str(attrs.get("aria-hidden", "")).lower() == "true":
            return True
        if "display:none" in style or "visibility:hidden" in style:
            return True
        if classes.intersection({"hidden", "hide", "dn", "d-none"}):
            return True
        current = getattr(current, "parent", None)
    return False


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """从每个人的简介首段提取姓名及完整现任职务句。"""
    from crawler_core.models import PersonRecord

    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(page_rule["leader_region_selector"])
    if region is None:
        raise RuntimeError("领导简介正文 #zoom 未命中")

    records: list[object] = []
    seen_names: set[str] = set()
    for paragraph in region.select("p"):
        if _is_hidden(paragraph):
            continue
        text = _clean_text(paragraph.get_text(" ", strip=True))
        profile_match = re.match(r"^个人(?:简历|简介)\s*[：:]\s*(?P<name>[^，,]{2,12})[，,]", text)
        if not profile_match:
            continue
        name = re.sub(r"\s+", "", profile_match.group("name"))
        if not re.fullmatch(r"[一-鿿·]{2,8}", name) or name in seen_names:
            raise RuntimeError(f"人物简介姓名无效或重复：{name or '空'}")
        duty_match = re.search(r"现任[^。]*。", text)
        if not duty_match:
            raise RuntimeError(f"人物简介首段缺少完整现任句：{name}")
        evidence = _clean_text(duty_match.group(0))
        evidence = re.sub(r"^现任\s*", "", evidence).rstrip("。")
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
        raise RuntimeError("未从人物简介首段取得任何姓名与现任职务")
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
