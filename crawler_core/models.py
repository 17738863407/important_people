from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PersonRecord:
    """页面级爬虫输出的人物记录。"""

    organization: str
    url: str
    name: str
    duty: str
    detail_url: str = ""
    evidence: str = ""
    confidence: str = "待人工判定"
    parser: str = ""
    snapshot_path: str = ""
    adapter_script: str = ""
    selector_summary: str = ""
    order: str = ""
    sort_order: str = ""
    rank: str = ""
    province: str = ""
    city: str = ""
    maintainer: str = ""
    script_sequence: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，便于 TXT 导出。"""
        return asdict(self)
