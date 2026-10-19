from __future__ import annotations

import ast
import codecs
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from workspace.tools.project_paths import resolve_project_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path


@dataclass(frozen=True)
class SourceEdit:
    """记录一次不会改变业务抽取逻辑的源码区间替换。"""

    start: int
    end: int
    replacement: str
    reason: str


def write_log(log_path: Path, message: str) -> None:
    """同时向控制台和 UTF-8 日志文件输出信息。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def unique_output_path(path: Path) -> Path:
    """避免覆盖既有报告或日志，存在同名文件时追加时间戳。"""
    if not path.exists():
        return path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{timestamp}{path.suffix}")


def read_source(script_path: Path) -> tuple[str, bool]:
    """读取源码并保留 UTF-8 BOM 与原有换行符。"""
    raw = script_path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    if has_bom:
        raw = raw[len(codecs.BOM_UTF8) :]
    return raw.decode("utf-8"), has_bom


def write_source(script_path: Path, source: str, has_bom: bool) -> None:
    """按原 BOM 状态写回 UTF-8 源码。"""
    payload = source.encode("utf-8")
    if has_bom:
        payload = codecs.BOM_UTF8 + payload
    script_path.write_bytes(payload)


def build_line_index(source: str) -> tuple[list[str], list[int]]:
    """构建行文本及其绝对字符偏移，供 AST 字节列号转换使用。"""
    lines = source.splitlines(keepends=True)
    if not lines:
        lines = [""]
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)
    return lines, starts


def ast_position_to_offset(lines: list[str], starts: list[int], lineno: int, byte_col: int) -> int:
    """将 AST 的 UTF-8 字节列号转换为 Python 字符串绝对偏移。"""
    line = lines[lineno - 1]
    encoded_line = line.encode("utf-8")
    character_col = len(encoded_line[:byte_col].decode("utf-8"))
    return starts[lineno - 1] + character_col


def node_span(node: ast.AST, lines: list[str], starts: list[int]) -> tuple[int, int]:
    """返回 AST 节点在源码中的字符区间。"""
    if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
        raise ValueError(f"节点缺少源码位置：{type(node).__name__}")
    start = ast_position_to_offset(lines, starts, node.lineno, node.col_offset)
    end = ast_position_to_offset(lines, starts, node.end_lineno, node.end_col_offset)
    return start, end


def expand_comma_item(source: str, start: int, end: int) -> tuple[int, int]:
    """扩展逗号分隔项的删除范围，优先带走右侧逗号，否则带走左侧逗号。"""
    right = end
    while right < len(source) and source[right].isspace():
        right += 1
    if right < len(source) and source[right] == ",":
        return start, right + 1

    left = start - 1
    while left >= 0 and source[left].isspace():
        left -= 1
    if left >= 0 and source[left] == ",":
        return left, end
    raise ValueError("无法识别逗号分隔项边界")


def expand_dict_item(source: str, start: int, end: int) -> tuple[int, int]:
    """扩展字典项范围，并兼容由圆括号包裹的隐式字符串拼接值。"""
    right = end
    while right < len(source) and source[right].isspace():
        right += 1
    while right < len(source) and source[right] == ")":
        right += 1
        while right < len(source) and source[right].isspace():
            right += 1
    if right < len(source) and source[right] == ",":
        return start, right + 1
    return expand_comma_item(source, start, end)


def full_statement_span(node: ast.AST, source: str, lines: list[str], starts: list[int]) -> tuple[int, int]:
    """扩展为完整语句行，删除参数常量赋值时不留下空白残片。"""
    start = starts[node.lineno - 1]
    end_line = node.end_lineno
    if end_line < len(starts):
        end = starts[end_line]
    else:
        end = len(source)
    return start, end


def is_adapter_path_literal(node: ast.AST) -> bool:
    """判断节点是否为旧式 site_adapters Python 路径字面量。"""
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        return False
    normalized = node.value.replace("/", "\\")
    return normalized.startswith("site_adapters\\") and normalized.lower().endswith(".py")


def function_name(call: ast.Call) -> str:
    """读取简单函数调用名称。"""
    return call.func.id if isinstance(call.func, ast.Name) else ""


def collect_source_edits(source: str, tree: ast.Module) -> list[SourceEdit]:
    """收集路径元数据清理编辑，不修改选择器、网址和解析逻辑。"""
    lines, starts = build_line_index(source)
    edits: list[SourceEdit] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == "adapter_script":
                    start, _ = node_span(key, lines, starts)
                    _, end = node_span(value, lines, starts)
                    start, end = expand_dict_item(source, start, end)
                    edits.append(SourceEdit(start, end, "", "删除规则中的 adapter_script 字段"))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            positional_args = [*node.args.posonlyargs, *node.args.args]
            for argument in positional_args:
                if argument.arg != "adapter_script":
                    continue
                start, end = node_span(argument, lines, starts)
                start, end = expand_comma_item(source, start, end)
                edits.append(SourceEdit(start, end, "", "删除 adapter_script 函数参数"))

        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "adapter_script_value" for target in node.targets):
                start, end = full_statement_span(node, source, lines, starts)
                edits.append(SourceEdit(start, end, "", "删除 adapter_script_value 路径常量"))

        if isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "adapter_script_value":
                start, end = full_statement_span(node, source, lines, starts)
                edits.append(SourceEdit(start, end, "", "删除 adapter_script_value 路径常量"))

        if isinstance(node, ast.Call):
            call_name = function_name(node)
            for argument in node.args:
                remove_argument = (
                    isinstance(argument, ast.Name)
                    and argument.id == "adapter_script_value"
                ) or (
                    call_name == "build_page_rule"
                    and isinstance(argument, ast.Name)
                    and argument.id == "adapter_script"
                ) or (
                    call_name == "build_page_rule"
                    and is_adapter_path_literal(argument)
                )
                if not remove_argument:
                    continue
                start, end = node_span(argument, lines, starts)
                start, end = expand_comma_item(source, start, end)
                edits.append(SourceEdit(start, end, "", "删除调用中的 adapter_script 实参"))

            for keyword in node.keywords:
                if keyword.arg != "adapter_script":
                    continue
                start, _ = node_span(keyword, lines, starts)
                _, end = node_span(keyword.value, lines, starts)
                start, end = expand_comma_item(source, start, end)
                edits.append(SourceEdit(start, end, "", "删除 adapter_script 关键字实参"))

    return edits


def apply_source_edits(source: str, edits: list[SourceEdit]) -> str:
    """按逆序应用互不重叠的源码编辑。"""
    ordered = sorted(edits, key=lambda item: (item.start, item.end))
    for previous, current in zip(ordered, ordered[1:]):
        if previous.end > current.start:
            raise ValueError(f"源码编辑区间重叠：{previous.reason} / {current.reason}")

    updated = source
    for edit in reversed(ordered):
        updated = updated[: edit.start] + edit.replacement + updated[edit.end :]
    return updated


def audit_adapter_metadata(tree: ast.Module) -> list[str]:
    """检查脚本中是否仍残留旧式 adapter_script 结构。"""
    problems: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key in node.keys:
                if isinstance(key, ast.Constant) and key.value == "adapter_script":
                    problems.append("仍存在 adapter_script 字典字段")
        if isinstance(node, ast.arg) and node.arg == "adapter_script":
            problems.append("仍存在 adapter_script 函数参数")
        if isinstance(node, ast.Name) and node.id in {"adapter_script", "adapter_script_value"}:
            problems.append(f"仍存在变量：{node.id}")
        if isinstance(node, ast.keyword) and node.arg == "adapter_script":
            problems.append("仍存在 adapter_script 关键字实参")
        if is_adapter_path_literal(node):
            problems.append("仍存在 site_adapters Python 路径字面量")
    return sorted(set(problems))


def normalize_one_script(script_path: Path, apply_changes: bool) -> tuple[str, int, str]:
    """规范单个脚本，并在写回前后执行语法验证。"""
    source, has_bom = read_source(script_path)
    tree = ast.parse(source, filename=str(script_path))
    edits = collect_source_edits(source, tree)
    if not edits:
        problems = audit_adapter_metadata(tree)
        if problems:
            return "失败", 0, "；".join(problems)
        return "已符合", 0, "无需修改"

    updated = apply_source_edits(source, edits)
    updated_tree = ast.parse(updated, filename=str(script_path))
    problems = audit_adapter_metadata(updated_tree)
    if problems:
        return "失败", 0, "；".join(problems)

    if apply_changes:
        write_source(script_path, updated, has_bom)
        return "已修改", len(edits), "已移除脚本内路径元数据，改由公共运行器注入"
    return "待修改", len(edits), "审计通过，尚未写回"


def normalize_v3_scripts(
    adapter_dir: Path,
    report_path: Path,
    log_path: Path,
    apply_changes: bool,
) -> None:
    """递归规范 V3 脚本；单个文件失败时记录并继续处理。"""
    report_path = unique_output_path(report_path)
    log_path = unique_output_path(log_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    script_paths = sorted(path for path in adapter_dir.rglob("*.py") if path.is_file())

    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None

    rows: list[list[str]] = [["状态", "编辑数", "脚本", "说明"]]
    status_counts: dict[str, int] = {}
    iterator = tqdm(script_paths, desc="统一V3脚本路径元数据") if tqdm else script_paths
    for script_path in iterator:
        try:
            status, edit_count, note = normalize_one_script(script_path, apply_changes)
        except Exception as error:
            status, edit_count, note = "失败", 0, str(error)
        status_counts[status] = status_counts.get(status, 0) + 1
        relative_path = str(script_path.relative_to(adapter_dir)).replace("/", "\\")
        rows.append([status, str(edit_count), relative_path, note])
        if status == "失败":
            write_log(log_path, f"失败：{relative_path}：{note}")

    with report_path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write("\t".join(value.replace("\t", " ").replace("\n", " ") for value in row) + "\n")

    write_log(log_path, f"脚本目录：{adapter_dir}")
    write_log(log_path, f"扫描脚本数：{len(script_paths)}")
    for status, count in sorted(status_counts.items()):
        write_log(log_path, f"{status}：{count}")
    write_log(log_path, f"报告路径：{report_path}")
    write_log(log_path, f"写回模式：{'是' if apply_changes else '否'}")


def main(
    adapter_dir: Path,
    report_path: Path,
    log_path: Path,
    apply_changes: bool,
) -> None:
    """脚本统一入口。"""
    normalize_v3_scripts(
        adapter_dir=adapter_dir,
        report_path=report_path,
        log_path=log_path,
        apply_changes=apply_changes,
    )


if __name__ == "__main__":
    adapter_dir_value = resolve_project_path("important_people/site_adapters/V3", anchor=__file__)
    report_path_value = resolve_project_path(
        "important_people/workspace/reports/V3脚本路径元数据统一报告.txt", anchor=__file__
    )
    log_path_value = resolve_project_path(
        "important_people/workspace/log/V3脚本路径元数据统一.log", anchor=__file__
    )
    apply_changes_value = True
    main(
        adapter_dir=adapter_dir_value,
        report_path=report_path_value,
        log_path=log_path_value,
        apply_changes=apply_changes_value,
    )
