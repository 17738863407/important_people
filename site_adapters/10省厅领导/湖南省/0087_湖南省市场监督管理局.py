from __future__ import annotations

import sys
from pathlib import Path


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")

PAGE_RULE = {'rule_id': '0087',
 'page_type': '人物目录详情页',
 'structure_group': 'hunan_amr_playwright_leader_profiles',
 'reuse_scope': 'single_page',
 'load_mode': '动态DOM渲染',
 'fetch_mode': 'playwright',
 'extract_mode': 'list_then_detail',
 'collector': 'playwright_hidden',
 'parser': 'page_inline_hunan_amr_profiles_v2',
 'leader_region_selector': '.listPage-r-li > ul > li',
 'name_selector': '.jgld_leader .jdld_leader_tit',
 'duty_selector': '.jgld_leader li.jdld_leader_zw',
 'detail_link_selector': 'a[title][href]',
 'detail_strategy': {'required': True,
                     'mode': 'list_then_detail',
                     'detail_link_selector': 'a[title][href]'},
 'risk_flag': 'requests存在BAD_ECPOINT，Playwright稳定；职务与工作职责使用相同class，须按字段标签区分',
 'confidence': 'high'}


def parse_page(html: str, final_url: str, page_rule: dict[str, object]) -> list[dict[str, str]]:
    """按目录顺序逐页核名，只取明确标注“职务”的详情字段。"""
    import re
    from urllib.parse import urljoin

    from bs4 import BeautifulSoup
    from crawler_core.fetcher import fetch_by_playwright

    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, str]] = []
    candidates = soup.select(".listPage-r-li > ul > li > a[title][href]")
    if not candidates:
        raise RuntimeError("Playwright目录未发现机构领导详情链接")
    for link in candidates:
        name = re.sub(r"[\s\u00a0\u3000]+", "", str(link.get("title") or ""))
        if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
            raise RuntimeError(f"领导目录姓名字段无效：{name}")
        detail_result = fetch_by_playwright(urljoin(final_url, str(link["href"])))
        detail_soup = BeautifulSoup(detail_result.html, "html.parser")
        name_node = detail_soup.select_one(".jgld_leader .jdld_leader_tit")
        detail_name = re.sub(
            r"[\s\u00a0\u3000]+",
            "",
            name_node.get_text(" ", strip=True) if name_node else "",
        )
        if detail_name != name:
            raise RuntimeError(f"目录与详情姓名不一致：{name} != {detail_name}")
        duty_node = next(
            (
                node
                for node in detail_soup.select(".jgld_leader li.jdld_leader_zw")
                if re.match(r"^职\s*务\s*[：:]", node.get_text(" ", strip=True))
            ),
            None,
        )
        if duty_node is None:
            raise RuntimeError(f"详情页缺少职务字段：{detail_result.final_url}")
        raw_evidence = " ".join(duty_node.get_text(" ", strip=True).split())
        duty = re.sub(r"^职\s*务\s*[：:]\s*", "", raw_evidence).strip()
        duty = re.sub(r"[（(]\s*(?:挂职|兼|主持日常工作)\s*[）)]", "", duty)
        duty = re.sub(r"\s*([，,、；;])\s*", r"\1", duty)
        duty = re.sub(r"\s+", " ", duty).strip()
        duty = re.sub(r"[。.]$", "", duty).strip()
        if not duty:
            raise RuntimeError(f"详情页职务字段为空：{detail_result.final_url}")
        rows.append(
            {
                "name": name,
                "duty": duty,
                "detail_url": detail_result.final_url,
                "evidence": duty,
                "confidence": "high",
                "parser": "page_inline_hunan_amr_profiles_v2",
            }
        )
    return rows


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
