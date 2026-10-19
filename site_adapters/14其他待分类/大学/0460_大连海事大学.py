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


def clean_text(value: str) -> str:
    """压缩网页字段中的全角空格和连续空白。"""
    return " ".join(
        str(value or "").replace("\u3000", " ").replace("\xa0", " ").split()
    )


def parse_page(
    html: str,
    final_url: str,
    page_rule: dict[str, object],
) -> list[dict[str, str]]:
    """仅从现任领导列表的明确姓名、职务节点提取数据。"""
    del final_url, page_rule
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    selector_summary = (
        "strategy=custom_parse_page；leader=.nymain li；"
        "name=.title .tit；duty=.title .info；detail=none"
    )

    for item in soup.select(".nymain li"):
        name_node = item.select_one(".title .tit")
        duty_node = item.select_one(".title .info")
        name = clean_text(name_node.get_text(" ", strip=True) if name_node else "")
        duty = clean_text(duty_node.get_text(" ", strip=True) if duty_node else "")
        if (
            not re.fullmatch(r"[\u4e00-\u9fa5·]{2,8}", name)
            or not duty
            or name in seen
        ):
            continue

        seen.add(name)
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": "",
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_dlmu_current_leaders_v2",
                "selector_summary": selector_summary,
            }
        )
    return rows


PAGE_RULE = {
    "rule_id": "0460",
    "domain": "www.dlmu.edu.cn",
    "page_type": "多人物详情合并页",
    "structure_group": "dlmu_current_leaders",
    "reuse_scope": "single_page",
    "load_mode": "静态HTML直出",
    "fetch_mode": "online",
    "extract_mode": "list_direct",
    "collector": "static_http",
    "parser": "page_inline_dlmu_current_leaders_v2",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "同一人物块还含负责、分管、联系等职责段落，依据说明只能取明确.info职务节点",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
    "locator": {
        "api": {
            "enabled": False,
            "reason": "当前静态HTML直接包含现任领导姓名和明确职务节点",
        },
        "migration": {
            "source": "legacy_page_rule",
            "verified_status": "online_verified_20260806",
            "behavior_changed": True,
        },
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
