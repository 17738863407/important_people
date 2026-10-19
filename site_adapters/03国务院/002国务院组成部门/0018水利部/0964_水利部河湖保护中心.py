from __future__ import annotations

import hashlib
import re
import secrets
import string
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "0964",
    "page_type": "职务分组名单页",
    "structure_group": "mwr_hhzx_signed_detail_api_v2",
    "reuse_scope": "single_page",
    "load_mode": "接口数据加载",
    "fetch_mode": "raw_http",
    "extract_mode": "custom_parse_page",
    "parser": "mwr_hhzx_signed_detail_api_v2",
    "leader_region_selector": "[中心领导]至[职责]",
    "name_selector": "职务分组冒号后的顿号名单",
    "duty_selector": "职务分组冒号前标签",
    "detail_link_selector": "",
    "api": {
        "endpoint": "/HhzxApi/PData_h/NewsDet.ashx",
        "method": "GET",
        "document_id_source": "entry_fragment",
        "document_body_path": "0.0.DocBody",
    },
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "接口要求按公开前端算法动态签名；仅解析中心领导到职责之间的分组字段",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "custom_parse_page",
}


def _clean_text(value: str) -> str:
    return re.sub(r"[\s\u2000-\u200b\u3000\xa0]+", " ", value).strip()


def _build_api_headers(entry_url: str) -> dict[str, str]:
    """按站点公开前端算法生成当次请求签名，不保存一次性令牌。"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    alphabet = string.digits + string.ascii_lowercase + string.ascii_uppercase
    nonce = "".join(secrets.choice(alphabet) for _ in range(16))
    signing_text = "ybd1234567890" + timestamp + nonce
    signature = hashlib.md5("".join(sorted(signing_text)).encode("utf-8")).hexdigest()
    return {
        "User-Agent": "Mozilla/5.0",
        "Referer": entry_url,
        "sign": signature,
        "timeStamp": timestamp,
        "nonceStr": nonce,
    }


def parse_page(html: str, final_url: str, page_rule: dict) -> list[object]:
    """在线读取组织机构文档，并解析中心领导职务分组。"""
    import requests
    from bs4 import BeautifulSoup

    from crawler_core.models import PersonRecord

    entry_url = page_rule["url"]
    route = urlparse(entry_url).fragment
    route_match = re.fullmatch(r"/?details/\d+/(?P<document_id>\d+)", route)
    if route_match is None:
        raise RuntimeError("依据链接片段中缺少可验证的详情文档ID")

    api_url = urljoin(final_url or entry_url, page_rule["api"]["endpoint"])
    response = requests.get(
        api_url,
        params={"ID": route_match.group("document_id")},
        headers=_build_api_headers(entry_url),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if (
        not isinstance(payload, list)
        or not payload
        or not isinstance(payload[0], list)
        or not payload[0]
        or not isinstance(payload[0][0], dict)
    ):
        raise RuntimeError("组织机构接口响应结构异常")

    document_body = str(payload[0][0].get("DocBody") or "")
    document_text = BeautifulSoup(document_body, "html.parser").get_text("\n", strip=True)
    block_match = re.search(
        r"\[\s*中心领导\s*\](?P<block>.*?)\[\s*职责\s*\]",
        document_text,
        re.S,
    )
    if block_match is None:
        return []

    records: list[object] = []
    seen: set[str] = set()
    for group_match in re.finditer(
        r"(?P<duty>[\u3400-\u9fff\s]{2,20})[：:]\s*(?P<names>[^\n]+)",
        block_match.group("block"),
    ):
        duty = re.sub(r"\s+", "", group_match.group("duty"))
        names_text = _clean_text(group_match.group("names"))
        for raw_name in re.split(r"[、，,]", names_text):
            name = re.sub(r"\s+", "", raw_name)
            if not re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name) or name in seen:
                continue
            seen.add(name)
            records.append(
                PersonRecord(
                    organization=page_rule["organization"],
                    url=page_rule["url"],
                    name=name,
                    duty=duty,
                    detail_url="",
                    evidence=duty,
                    confidence="high",
                    parser=page_rule["parser"],
                )
            )
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
