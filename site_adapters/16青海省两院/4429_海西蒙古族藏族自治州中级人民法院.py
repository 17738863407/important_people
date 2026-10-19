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


def normalize_profile_text(text: str) -> str:
    """合并富文本编辑器拆开的行内节点，不改变网页文字顺序。"""
    value = str(text or "").replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", "", value).strip()


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按正文段落顺序提取每人的姓名及“现任”后的完整职务证据。"""
    soup = BeautifulSoup(html, "html.parser")
    region = soup.select_one(".detail > .text")
    if region is None:
        raise RuntimeError("页面未找到领导正文区域 .detail > .text")

    rows: list[dict[str, str]] = []
    for paragraph in region.select("p"):
        text = normalize_profile_text(paragraph.get_text(" ", strip=True))
        if "现任" not in text:
            continue
        match = re.fullmatch(
            r"(?P<name>[\u4e00-\u9fff·]{2,8})[，,].*?现任(?P<duty>[^。；;]+)[。.]?",
            text,
        )
        if match is None:
            raise RuntimeError(f"领导简介段落缺少可验证的姓名—现任职务边界：{text}")
        duty = match.group("duty").strip()
        if not duty:
            raise RuntimeError(f"领导简介现任职务为空：{match.group('name')}")
        rows.append(
            {
                "name": match.group("name"),
                "duty": duty,
                "evidence": duty,
                "detail_url": "",
                "confidence": "high",
                "parser": str(page_rule.get("parser", "")),
                "selector_summary": (
                    "strategy=custom_parse_page；region=.detail>.text；"
                    "fields=p段落起始姓名与现任句；detail=none"
                ),
            }
        )

    if not rows:
        raise RuntimeError("领导正文未解析出含现任职务的人物段落")
    return rows


PAGE_RULE = {
    "rule_id": "4429",
    "domain": "hxzy.qhwsfy.gov.cn",
    "page_type": "多人领导简介正文页",
    "structure_group": "qinghai_court_profile_paragraph_current_duty",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "extract_mode": "list_direct",
    "collector": "raw_http",
    "parser": "page_qinghai_court_profile_paragraph_current_duty_v1",
    "locator_strategy": "custom_parse_page",
    "leader_region_selector": ".detail > .text",
    "name_selector": "p",
    "duty_selector": "p",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none", "candidate_links": []},
    "risk_flag": "职务和法官等级被富文本行内节点拆分，必须在单个人物段落内按原顺序合并",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator": {
        "css": {
            "leader_region_selector": ".detail > .text",
            "profile_paragraph_selector": "p",
        },
        "api": {"enabled": False, "reason": "当前多人简介和现职由静态正文直接提供"},
    },
}


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
