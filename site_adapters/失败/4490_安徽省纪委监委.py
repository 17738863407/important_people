from __future__ import annotations

import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup


def resolve_project_dir() -> Path:
    """向上查找项目根目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4490",
    "page_type": "领导机构分组名单",
    "load_mode": "静态HTML",
    "extract_mode": "page_inline",
    "parser": "page_inline_ahjjjc_leaders_v2",
    "leader_region_selector": ".xinxi",
    "detail_link_selector": "",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "仅解析领导机构正文；排除委员、常务委员会委员和监委委员；从当前分组小标题取得机构全称并组合职务，同名按首次出现顺序用顿号合并，保留提名人选限定",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
}


def parse_page(
    html: str, final_url: str, page_rule: dict[str, object]
) -> list[dict[str, str]]:
    """按正文段落的职务标签拆分名单，不读取导航及被排除的委员栏目。"""
    soup = BeautifulSoup(html, "lxml")
    # 先移除隐藏子树，避免隐藏姓名混入可见段落；同时检查正文祖先。
    for node in reversed(list(soup.find_all(True))):
        style = str(node.get("style", ""))
        classes = {str(value).lower() for value in node.get("class", [])}
        if (
            node.has_attr("hidden")
            or str(node.get("aria-hidden", "")).lower() == "true"
            or classes.intersection({"hidden", "hide", "d-none"})
            or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", style, re.I)
        ):
            node.decompose()
    regions = soup.select(str(page_rule["leader_region_selector"]))
    if len(regions) != 1:
        raise RuntimeError("领导机构正文容器缺失或不唯一")
    rows: list[dict[str, str]] = []
    by_name: dict[str, dict[str, str]] = {}
    duties_by_name: dict[str, list[str]] = {}
    section = ""
    section_title = ""
    sections_seen: set[str] = set()
    for paragraph in regions[0].find_all("p", recursive=False):
        text = re.sub(r"\s+", "", paragraph.get_text("", strip=True))
        if not text:
            continue
        if paragraph.find("strong"):
            if text.endswith("纪律检查委员会"):
                section = "纪委"
            elif text.endswith("监察委员会"):
                section = "监委"
            else:
                section = ""
            if section:
                section_title = text
                sections_seen.add(section)
            else:
                section_title = ""
            continue
        if not section:
            continue
        if text.startswith(("常务委员会委员", "监委委员", "委员")):
            continue
        match = re.fullmatch(
            r"(代理主任|副主任|主任|副书记|书记)(.+)", text
        )
        if not match:
            raise RuntimeError(f"领导正文存在未识别职务段落：{text}")
        duty, names_text = match.groups()
        allowed = {"书记", "副书记"} if section == "纪委" else {
            "代理主任", "主任", "副主任"
        }
        if duty not in allowed:
            raise RuntimeError(f"职务与当前分组不匹配：{section}/{duty}")
        for token in names_text.split("、"):
            name = re.sub(r"[（(][^（）()]*[）)]", "", token)
            annotations = re.findall(r"[（(]([^（）()]*)[）)]", token)
            if not re.fullmatch(r"[\u4e00-\u9fff·]{2,8}", name):
                raise RuntimeError(f"领导姓名格式异常：{token}")
            # 性别仅为姓名旁注；任职状态属于职务证据，必须保留。
            # 机构名称取自当前在线分组标题，避免纪委、监委的同名职务失去归属。
            evidence = section_title + duty + "".join(
                f"（{value}）" for value in annotations if value not in {"女", "男"}
            )
            if name in by_name:
                row = by_name[name]
                if evidence not in duties_by_name[name]:
                    duties_by_name[name].append(evidence)
                    row["evidence"] = "、".join(duties_by_name[name])
                    row["duty"] = row["evidence"]
            else:
                row = {"name": name, "duty": evidence, "evidence": evidence, "detail_url": ""}
                rows.append(row)
                by_name[name] = row
                duties_by_name[name] = [evidence]
    if sections_seen != {"纪委", "监委"} or not rows:
        raise RuntimeError("未取得完整的纪委、监委领导分组")
    return rows


def main() -> None:
    """从规则主表注入入口并在线采集。"""
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
