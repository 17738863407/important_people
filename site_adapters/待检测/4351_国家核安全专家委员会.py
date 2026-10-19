from __future__ import annotations

import io
import math
import re
import sys
from pathlib import Path

import pdfplumber
import requests


def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")


PAGE_RULE = {
    "rule_id": "4351",
    "page_type": "PDF委员会名单",
    "structure_group": "nnsa_expert_committee_pdf_grid_v1",
    "load_mode": "PDF文本层",
    "fetch_mode": "online",
    "extract_mode": "custom",
    "parser": "page_inline_nnsa_pdf_grid_v1",
    "leader_region_selector": "pdf_text_layer",
    "detail_strategy": {"required": False, "mode": "none"},
    "risk_flag": "PDF含多栏姓名及两字姓名字间距，依据文本坐标网格恢复姓名，不按空格直接切分。",
    "confidence": "high",
    "filter_policy": "strong_no_wordlist",
    "locator_strategy": "pdf_word_coordinates",
}


def clean_name(value: str) -> str:
    """删除院士附注与纯排版空白，保留姓名字符。"""
    value = re.sub(r"（院士）", "", value)
    return re.sub(r"\s+", "", value)


def build_row(name: str, duty: str) -> dict[str, str]:
    """构造委员会名单记录。"""
    return {"name": name, "duty": duty, "detail_url": ""}


def names_from_compact_tail(value: str) -> list[str]:
    """解析以院士附注或行尾分隔的紧凑姓名串。"""
    return [clean_name(item) for item in re.findall(r"([\u3400-\u9fff·]{2,20})(?:（院士）|$)", value)]


def group_grid_line(words: list[dict], base_x: float = 76.6, cell_width: float = 64.0) -> list[str]:
    """按PDF横向网格合并被字间距拆开的两字姓名。"""
    cells: dict[int, list[str]] = {}
    for word in words:
        index = math.floor((float(word["x0"]) - base_x + 16.0) / cell_width)
        cells.setdefault(index, []).append(str(word["text"]))
    return [clean_name("".join(cells[index])) for index in sorted(cells)]


def parse_pdf(pdf_bytes: bytes) -> list[dict[str, str]]:
    """从两页PDF的文本坐标层恢复委员会全部名单及网页明确职务。"""
    rows: list[dict[str, str]] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if len(pdf.pages) != 2:
            raise RuntimeError(f"国家核安全专家委员会PDF页数异常：{len(pdf.pages)}")
        first_words = pdf.pages[0].extract_words(use_text_flow=False, keep_blank_chars=False)

        # 资深委员区为三列布局，每个姓名在文本层中保持为一个词。
        for word in first_words:
            top = float(word["top"])
            text = str(word["text"])
            if 240.0 <= top <= 312.0:
                name = clean_name(text)
                if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                    rows.append(build_row(name, "资深委员"))

        # 主席类职务按行标签解析；院士附注只用于姓名边界，不写入职务。
        first_text = pdf.pages[0].extract_text() or ""
        for line in first_text.splitlines():
            compact = re.sub(r"\s+", "", line)
            if compact.startswith("副主席："):
                for name in names_from_compact_tail(compact.split("：", 1)[1]):
                    rows.append(build_row(name, "副主席"))
            elif compact.startswith("主席："):
                name = clean_name(compact.split("：", 1)[1])
                if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                    rows.append(build_row(name, "主席"))
            elif compact.startswith("秘书长："):
                name = clean_name(compact.split("：", 1)[1])
                if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                    rows.append(build_row(name, "秘书长"))

        deputy_words = [word for word in first_words if 463.0 <= float(word["top"]) <= 473.0]
        if not deputy_words:
            raise RuntimeError("PDF未定位到副秘书长行")
        deputy_tokens: list[str] = []
        first_token = str(deputy_words[0]["text"])
        deputy_tokens.append(first_token.split("：", 1)[-1])
        deputy_tokens.extend(str(word["text"]) for word in deputy_words[1:])
        index = 0
        while index < len(deputy_tokens):
            token = clean_name(deputy_tokens[index])
            if len(token) == 1 and index + 1 < len(deputy_tokens):
                token += clean_name(deputy_tokens[index + 1])
                index += 2
            else:
                index += 1
            if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", token):
                rows.append(build_row(token, "副秘书长"))

        # 委员区采用64点等距网格；两字姓名会被拆为同一网格单元内的两个词。
        member_lines: list[list[dict]] = []
        for page_index, page in enumerate(pdf.pages):
            grouped: dict[float, list[dict]] = {}
            for word in page.extract_words(use_text_flow=False, keep_blank_chars=False):
                top = round(float(word["top"]), 1)
                if (page_index == 0 and top >= 559.0) or page_index == 1:
                    grouped.setdefault(top, []).append(word)
            for top in sorted(grouped):
                line_words = grouped[top]
                line_text = "".join(str(word["text"]) for word in line_words)
                if "以下委员" in line_text:
                    continue
                member_lines.append(line_words)

        for line_words in member_lines:
            for name in group_grid_line(line_words):
                if re.fullmatch(r"[\u3400-\u9fff·]{2,20}", name):
                    rows.append(build_row(name, "委员"))

    if not rows:
        raise RuntimeError("PDF文本层未解析到委员会名单")
    return rows


def parse_page(html: str, final_url: str, page_rule: dict) -> list[dict]:
    """动态下载规则主表入口PDF，并解析当前文本坐标层。"""
    del html, page_rule
    session = requests.Session()
    session.trust_env = False
    response = session.get(final_url, timeout=30, verify=False)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise RuntimeError("国家核安全专家委员会入口未返回PDF文件")
    return parse_pdf(response.content)


def main() -> None:
    project_dir = resolve_project_dir()
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))

    from crawler_core.runner import run_page_adapter

    output_path = run_page_adapter(PAGE_RULE, globals())
    print(f"输出文件：{output_path}")


if __name__ == "__main__":
    main()
