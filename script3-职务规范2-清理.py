from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from tqdm import tqdm

from crawler_core.paths import resolve_path_argument, timestamped_output_path


def build_runtime_config() -> dict[str, Any]:
    """构造清理阶段使用的确定性规则。"""
    return {
        "headers": [
            "姓名*", "职务*", "排序*", "职级*", "所属省*", "所属市",
            "依据链接", "依据说明", "维护人", "机构", "详情页链接", "脚本序号",
        ],
        "prefix_noise": re.compile(r"^(?:职\s*务|现任职务|职位|现任|现为|担任)[:：]?"),
        "title_terms": (
            "党组书记", "党组副书记", "党组成员", "党委书记", "党委副书记", "党委委员",
            "党委常委", "纪委书记", "常务副书记", "书记", "副书记", "常委", "委员",
            "主任委员", "副主任委员", "常务委员", "主任", "副主任", "部长", "副部长",
            "局长", "副局长", "厅长", "副厅长", "院长", "副院长", "校长", "副校长",
            "庭长", "副庭长", "站长", "副站长", "所长", "副所长", "馆长", "副馆长",
            "检察长", "副检察长", "组长", "副组长", "处长", "副处长", "科长", "副科长",
            "司长", "副司长", "团长", "副团长", "理事长", "副理事长", "常务理事", "理事",
            "会长", "副会长", "社长", "副社长", "主编", "主席", "副主席", "秘书长",
            "副秘书长", "董事长", "副董事长", "董事", "外部董事", "职工董事", "总经理",
            "副总经理", "总裁", "副总裁", "董事会秘书", "总法律顾问", "首席合规官",
            "总经理助理", "总工程师", "总经济师", "总会计师", "总审计师", "总农艺师",
            "总规划师", "总畜牧师", "总队长", "副总队长", "政委", "第一政委", "督察长",
            "第一副督察长", "副总督查", "主任督学", "教授", "研究员", "主任医师",
            "首席专家", "负责人", "一级巡视员", "二级巡视员", "一级调研员", "二级调研员",
            "三级调研员", "四级调研员", "一级主任科员", "二级主任科员", "三级主任科员",
            "四级主任科员", "一级警务专员", "二级警务专员", "一级高级警长", "二级高级警长",
            "三级高级警长", "四级高级警长", "一级高级监察官", "二级高级监察官",
            "三级高级监察官", "四级高级监察官", "纪检组组长", "纪检监察组组长",
            "人大常委会主任", "人大常委会副主任", "人大主任", "政协主席", "政协副主席",
            "总理", "市长", "代市长", "副市长", "州长", "副州长", "区长", "副区长",
            "县长", "副县长", "常务副省长", "常务副市长", "常务副州长", "常务副区长",
            "常务副县长", "常务副主任", "常务副秘书长", "常务副会长", "常务副馆长",
            "常务副校长", "书记处书记", "主席团委员", "首席合伙人", "副总指挥",
            "执行副总指挥", "一级总监",
        ),
    }


def write_log(log_path: Path, message: str) -> None:
    """同时输出到控制台和UTF-8日志。"""
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t{message}"
    print(line)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def clean_tsv_value(value: object) -> str:
    """清除会破坏TSV单元格的控制字符。"""
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


def read_rows(input_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """读取UTF-8制表符TXT。"""
    lines = input_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    if not lines:
        return [], []
    headers = lines[0].split("\t")
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = line.split("\t")
        if len(values) < len(headers):
            values.extend([""] * (len(headers) - len(values)))
        rows.append({header: values[index] if index < len(values) else "" for index, header in enumerate(headers)})
    return headers, rows


def write_rows(output_path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    """写出UTF-8制表符TXT。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(clean_tsv_value(header) for header in headers)]
    for row in rows:
        lines.append("\t".join(clean_tsv_value(row.get(header, "")) for header in headers))
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def remove_all_whitespace(value: object) -> str:
    """删除全部排版空白。"""
    return re.sub(r"\s+", "", str(value or ""))


def normalize_parentheses(value: object) -> str:
    """统一圆括号；方括号和尖括号只删除符号。"""
    return (
        str(value or "").replace("(", "（").replace(")", "）").replace("[", "").replace("]", "")
        .replace("〈", "").replace("〉", "").replace("<", "").replace(">", "")
    )


def clean_status_parentheses(value: object) -> str:
    """删除所有圆括号及其内容，兼容嵌套和未闭合左括号。"""
    text = normalize_parentheses(value)
    output: list[str] = []
    depth = 0
    for character in text:
        if character == "（":
            depth += 1
            continue
        if character == "）":
            if depth > 0:
                depth -= 1
            continue
        if depth == 0:
            output.append(character)
    return "".join(output)


def normalize_duty_punctuation(value: object) -> str:
    """把职务分隔符统一为中文顿号。"""
    text = re.sub(r"[《》“”‘’\"']", "", normalize_parentheses(value))
    output: list[str] = []
    for character in text:
        if character in {"、", "（", "）"}:
            output.append(character)
        elif unicodedata.category(character).startswith("P") or character in {"/", "\\", "|", "·"}:
            output.append("、")
        else:
            output.append(character)
    text = re.sub(r"、+", "、", "".join(output))
    text = re.sub(r"、([）])", r"\1", text)
    text = re.sub(r"([（])、", r"\1", text)
    return text.strip("、")


def strip_name_prefix(value: str, name: str) -> str:
    """仅在开头删除与当前姓名完全一致的重复姓名。"""
    normalized_name = remove_all_whitespace(name)
    if not normalized_name:
        return value
    flexible_name = r"\s*".join(re.escape(character) for character in normalized_name)
    return re.sub(rf"^{flexible_name}\s*[，,、:：]?", "", value)


def strip_trailing_name(value: str, name: str) -> str:
    """删除“职务：姓名”结构末尾的当前姓名。"""
    normalized_name = remove_all_whitespace(name)
    if not normalized_name:
        return value
    flexible_name = r"\s*".join(re.escape(character) for character in normalized_name)
    text = re.sub(rf"\s*[:：—–－-]\s*{flexible_name}\s*$", "", value)
    return re.sub(rf"\s+{flexible_name}\s*(?:同志)?\s*(?:（[^）]*）)?\s*$", "", text)


def strip_history_prefix(value: str) -> str:
    """删除短现职句开头的单一日期和任职动词。"""
    if re.search(r"曾任|历任|先后任|此前任|原任|不再担任|免去", value):
        return value
    date_pattern = r"(?:19|20)\d{2}年(?:\d{1,2}月)?(?:\d{1,2}日)?"
    return re.sub(rf"(?:(?<=^)|(?<=[，,；;。]))(?:自)?{date_pattern}(?:至今)?(?:起)?(?:任|任职于|担任)", "", value)


def strip_responsibility_tail(value: str) -> str:
    """删除现职句之后的独立职责尾句。"""
    return re.split(
        r"[，,；;。](?=(?:负责|分管|联系|协助|代管|主持)(?!日常工作的(?:副书记|副主任|副局长|副厅长|副主委)))",
        value,
        maxsplit=1,
    )[0]


def remove_group_labels(value: str) -> str:
    """删除网页分组标签，保留标签后的真实职务。"""
    labels = (
        "党委常委", "党委", "董事会成员", "董事会", "高级管理人员", "集团领导", "经理层成员",
        "经理层", "市政协党组成员", "市政协主席会议成员", "领导职务", "现任职务",
    )
    pattern = "|".join(re.escape(label) for label in sorted(labels, key=len, reverse=True))
    return re.sub(rf"(?:^|[，,；;。])(?:{pattern})\s*[:：]", "、", value).lstrip("、")


def normalize_evidence_whitespace(value: str, title_terms: tuple[str, ...]) -> str:
    """将明确分隔职务的空格转为顿号，其余空白删除。"""
    text = re.sub(r"\s*([，,；;。:：、])\s*", r"\1", value)
    title_pattern = "|".join(re.escape(title) for title in sorted(set(title_terms), key=len, reverse=True))
    text = re.sub(rf"({title_pattern})\s+(?=[\u4e00-\u9fff])", r"\1、", text)
    text = re.sub(r"(?<=[）])\s+(?=[\u4e00-\u9fff])", "、", text)
    return remove_all_whitespace(text)


def clean_evidence_to_duty(row: dict[str, str], config: dict[str, Any]) -> str:
    """只执行真实性筛选、去噪、分段和标点统一，不补职务主体。"""
    evidence = row.get("依据说明", "")
    text = re.sub(r"<[^>]+>", "", str(evidence or ""))
    text = normalize_parentheses(text)
    text = strip_name_prefix(text, row.get("姓名*", ""))
    text = strip_trailing_name(text, row.get("姓名*", ""))
    text = config["prefix_noise"].sub("", text.strip()).replace("现任", "")
    text = strip_history_prefix(text)
    text = clean_status_parentheses(text)
    text = re.sub(
        r"(常务副(?:省|市|州|区|县)长)(?=(?:省|市|州|区|县)?(?:人民)?政府(?:党组|党委))",
        r"\1、",
        text,
    )
    text = strip_responsibility_tail(text)
    text = re.split(r"(?:工作)?分工\s*[:：]", text, maxsplit=1)[0]
    text = remove_group_labels(text).replace("中共", "")
    text = text.replace("分管日常工作的", "").replace("负责日常工作的", "").replace("主持日常工作的", "")
    text = text.replace("兼任", "、").replace("并任", "、").replace("同时担任", "、").replace("兼职", "")
    text = re.sub(r"(?<=[长员记任席事师官])兼(?=[\u4e00-\u9fff])", "、", text)
    text = re.sub(r"兼(?=[\u4e00-\u9fff])", "、", text)
    text = re.sub(
        r"((?:党组|党委)(?:书记|副书记|成员|委员))"
        r"(?=(?:常务)?副?(?:主任|局长|厅长|院长|主席|总经理|董事长))",
        r"\1、",
        text,
    )
    text = re.sub(r"(董事长|董事)(?=(?:党组|党委)(?:书记|副书记|成员|委员))", r"\1、", text)
    text = re.sub(
        r"((?:常务)?副?(?:主任|局长|厅长|院长|主席|总经理|董事长))"
        r"(?=(?:省|市|区|县|自治区|兵团)[\u4e00-\u9fff]{1,20}(?:局|厅|委|办|院|中心|协会|学会))",
        r"\1、",
        text,
    )
    text = re.sub(r"(?:^|[，,；;。、])(?:挂职(?:一|二|三|两)?年?|已退休)(?=$|[，,；;。、])", "、", text)
    text = text.replace("主持日常工作副主任", "副主任")
    text = re.sub(r"^委\s*员\s*[:：]\s*$", "委员", text)
    text = normalize_evidence_whitespace(text, config["title_terms"])
    text = normalize_duty_punctuation(text)
    if text in {"领导", "局领导", "厅领导", "部领导", "院领导", "公司领导", "集团领导"}:
        return ""
    return text


def find_cleaning_errors(duty: str) -> list[str]:
    """检查清理结果的括号、标点和残留噪声。"""
    errors: list[str] = []
    if "（" in duty or "）" in duty:
        errors.append("仍含应清理的圆括号内容")
    if duty.startswith("、") or duty.endswith("、") or "、、" in duty:
        errors.append("顿号位置异常")
    for character in duty:
        if unicodedata.category(character).startswith("P") and character != "、":
            errors.append(f"存在未统一标点：{character}")
    for noise in ("职务：", "现任", "兼任", "分管日常工作的", "主持日常工作的"):
        if noise in duty:
            errors.append(f"残留噪声：{noise}")
    return list(dict.fromkeys(errors))


def build_audit_row(line_number: int, source: dict[str, str], output: dict[str, str], reason: str) -> dict[str, str]:
    """构造清理阶段审计行。"""
    return {
        "行号": str(line_number),
        "姓名*": source.get("姓名*", ""),
        "清理前依据说明": source.get("依据说明", ""),
        "清理后职务*": output.get("职务*", ""),
        "机构": source.get("机构", ""),
        "脚本序号": source.get("脚本序号", ""),
        "审计原因": reason,
    }


def validate_cleaned_rows(source_path: Path, output_path: Path) -> list[str]:
    """验证清理阶段只修改姓名和职务并统一标点。"""
    config = build_runtime_config()
    source_headers, source_rows = read_rows(source_path)
    output_headers, output_rows = read_rows(output_path)
    errors: list[str] = []
    if source_headers != config["headers"] or output_headers != config["headers"]:
        errors.append("表头不是规定的十二列或列序错误")
    if len(source_rows) != len(output_rows):
        errors.append(f"行数不一致：输入{len(source_rows)}，输出{len(output_rows)}")
    protected_fields = [header for header in config["headers"] if header not in {"姓名*", "职务*"}]
    for line_number, (source, output) in enumerate(zip(source_rows, output_rows), start=2):
        for field in protected_fields:
            if source.get(field, "") != output.get(field, ""):
                errors.append(f"第{line_number}行非目标字段被修改：{field}")
        if output.get("姓名*", "") != remove_all_whitespace(source.get("姓名*", "")):
            errors.append(f"第{line_number}行姓名未删除全部空白")
        evidence = source.get("依据说明", "").strip()
        duty = output.get("职务*", "")
        if (not evidence or evidence.startswith("抽取失败：")) and duty:
            errors.append(f"第{line_number}行无有效依据说明却生成了职务")
        errors.extend(f"第{line_number}行{message}" for message in find_cleaning_errors(duty))
    return errors


def process_all_rows(input_path: Path, output_path: Path, audit_path: Path, log_path: Path) -> None:
    """逐行执行清理，单行失败时留空职务并继续。"""
    config = build_runtime_config()
    headers, rows = read_rows(input_path)
    if headers != config["headers"]:
        raise ValueError(f"输入表头不符合十二列契约：{headers}")
    outputs: list[dict[str, str]] = []
    audits: list[dict[str, str]] = []
    for line_number, row in enumerate(tqdm(rows, desc="姓名与职务清理", unit="行"), start=2):
        output = dict(row)
        try:
            output["姓名*"] = remove_all_whitespace(row.get("姓名*", ""))
            evidence = row.get("依据说明", "").strip()
            output["职务*"] = "" if not evidence or evidence.startswith("抽取失败：") else clean_evidence_to_duty(row, config)
            errors = find_cleaning_errors(output["职务*"])
            if errors:
                audits.append(build_audit_row(line_number, row, output, "；".join(errors)))
        except Exception as error:
            output["姓名*"] = remove_all_whitespace(row.get("姓名*", ""))
            output["职务*"] = ""
            audits.append(build_audit_row(line_number, row, output, f"清理失败：{error}"))
        outputs.append(output)
    audit_headers = list(build_audit_row(0, {}, {}, "").keys())
    write_rows(output_path, headers, outputs)
    write_rows(audit_path, audit_headers, audits)
    write_log(log_path, f"输入记录：{len(rows)}")
    write_log(log_path, f"清理异常记录：{len(audits)}")
    validation_errors = validate_cleaned_rows(input_path, output_path)
    write_log(log_path, f"全量质量门禁错误：{len(validation_errors)}")
    if validation_errors:
        raise ValueError(f"清理质量门禁未通过，共{len(validation_errors)}项：{'；'.join(validation_errors[:20])}")
    write_log(log_path, f"清理结果：{output_path}")
    write_log(log_path, f"审计报告：{audit_path}")


def build_output_paths(project_dir: Path) -> tuple[Path, Path, Path]:
    """构造清理结果、审计报告和日志路径。"""
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (
        project_dir / "职务规范2：清理.txt",
        timestamped_output_path(
            project_dir / "workspace" / "reports" / "职务规范2：清理审计报告.txt",
            run_timestamp,
        ),
        timestamped_output_path(
            project_dir / "workspace" / "log" / "职务规范2：清理日志.txt",
            run_timestamp,
        ),
    )


def main(input_path: str | Path, project_dir: str | Path) -> None:
    """统一入口：确认真实职务、清除噪声并统一标点。"""
    input_path = resolve_path_argument(input_path, anchor=__file__, must_exist=True)
    project_dir = resolve_path_argument(project_dir, anchor=__file__, must_exist=True)
    if not input_path.is_file():
        raise FileNotFoundError(f"未找到输入文件：{input_path}")
    if not project_dir.is_dir():
        raise NotADirectoryError(f"未找到项目根目录：{project_dir}")
    output_path, audit_path, log_path = build_output_paths(project_dir)
    if input_path.resolve() == output_path.resolve():
        raise ValueError("输出路径不得覆盖输入文件")
    process_all_rows(input_path, output_path, audit_path, log_path)
    print(f"清理结果：{output_path}")
    print(f"审计报告：{audit_path}")
    print(f"运行日志：{log_path}")


if __name__ == "__main__":
    input_path_value = r"important_people/职务规范1：合并.txt"
    project_dir_value = r"important_people"
    main(input_path=input_path_value, project_dir=project_dir_value)
