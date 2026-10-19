from __future__ import annotations

import re
from typing import Any

from crawler_core.parser_registry import parse_with_registered_parser


def parse_and_filter_invalid_names(
    page_rule: dict[str, Any],
    html: str,
    final_url: str,
) -> list[object]:
    """运行已配置解析器，并剔除被误识别为姓名的职务、栏目和机构词。"""
    rows = parse_with_registered_parser(page_rule, html, final_url, None)
    invalid_name_pattern = re.compile(
        r"书记|董事|经理|会计师|工程师|经济师|组长|委员|成员|主席|主任|局长|院长|负责人|合规官|"
        r"党组|党委|纪委|领导|集团|公司|首页|链接|政府|国务院|委员会|办公室"
    )
    valid_rows: list[object] = []
    for row in rows:
        name = re.sub(r"\s+", "", str(getattr(row, "name", "") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            continue
        if invalid_name_pattern.search(name):
            continue
        valid_rows.append(row)
    return valid_rows
