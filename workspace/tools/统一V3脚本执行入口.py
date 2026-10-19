from __future__ import annotations

import ast
import codecs
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from workspace.tools.project_paths import resolve_project_path, timestamped_output_path
except ModuleNotFoundError:
    from project_paths import resolve_project_path, timestamped_output_path


@dataclass(frozen=True)
class SourceEdit:
    """记录一次仅作用于脚本启动外壳的源码编辑。"""

    start: int
    end: int
    replacement: str
    reason: str


STANDARD_RESOLVER = '''def resolve_project_dir() -> Path:
    """向上查找项目根目录，兼容 site_adapters 下的任意层级脚本。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "crawler_core").is_dir():
            return parent
    raise RuntimeError("未找到包含 crawler_core 的项目根目录")
'''


def write_log(log_path: Path, message: str) -> None:
    """将相同进度信息同时写入控制台和 UTF-8 日志。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def read_source(script_path: Path) -> tuple[str, bool]:
    """读取 UTF-8 源码，并记录原文件是否带 BOM。"""
    raw = script_path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    if has_bom:
        raw = raw[len(codecs.BOM_UTF8) :]
    return raw.decode("utf-8"), has_bom


def write_source(script_path: Path, source: str, has_bom: bool) -> None:
    """按原有 BOM 状态写回 UTF-8 源码。"""
    payload = source.encode("utf-8")
    if has_bom:
        payload = codecs.BOM_UTF8 + payload
    script_path.write_bytes(payload)


def build_line_index(source: str) -> tuple[list[str], list[int]]:
    """建立 AST 字节列号到 Python 字符偏移的转换索引。"""
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
    """把 AST 使用的 UTF-8 字节列号转换为字符串字符偏移。"""
    line = lines[lineno - 1]
    character_col = len(line.encode("utf-8")[:byte_col].decode("utf-8"))
    return starts[lineno - 1] + character_col


def node_span(node: ast.AST, lines: list[str], starts: list[int]) -> tuple[int, int]:
    """返回 AST 节点在原始源码中的字符区间。"""
    if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
        raise ValueError(f"节点缺少源码位置：{type(node).__name__}")
    start = ast_position_to_offset(lines, starts, node.lineno, node.col_offset)
    end = ast_position_to_offset(lines, starts, node.end_lineno, node.end_col_offset)
    return start, end


def full_statement_span(node: ast.AST, source: str, starts: list[int]) -> tuple[int, int]:
    """扩展到完整语句行，避免替换后遗留半行缩进。"""
    start = starts[node.lineno - 1]
    end_line = node.end_lineno
    end = starts[end_line] if end_line < len(starts) else len(source)
    return start, end


def expand_comma_item(source: str, start: int, end: int) -> tuple[int, int]:
    """扩展逗号分隔项范围，优先删除右侧逗号。"""
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


def function_name(call: ast.Call) -> str:
    """读取简单函数调用名称。"""
    return call.func.id if isinstance(call.func, ast.Name) else ""


def assignment_target_name(node: ast.AST) -> str:
    """读取单目标普通赋值或注解赋值的变量名。"""
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    return ""


def assignment_value(node: ast.AST) -> ast.AST | None:
    """读取赋值语句右值。"""
    if isinstance(node, ast.Assign):
        return node.value
    if isinstance(node, ast.AnnAssign):
        return node.value
    return None


def is_standard_project_dir_call(node: ast.AST | None) -> bool:
    """判断右值是否为统一的 resolve_project_dir() 调用。"""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "resolve_project_dir"
        and not node.args
        and not node.keywords
    )


def is_inline_project_search(node: ast.AST | None) -> bool:
    """识别 main() 中按 crawler_core 标志目录向上查找根目录的旧写法。"""
    if node is None:
        return False
    rendered = ast.dump(node, include_attributes=False)
    return "crawler_core" in rendered and "parents" in rendered


def is_legacy_absolute_output_dir(node: ast.AST) -> bool:
    """判断 output_dir 是否为旧项目下写死的绝对 outputs 路径。"""
    if not isinstance(node, ast.Call) or function_name(node) != "Path" or len(node.args) != 1:
        return False
    argument = node.args[0]
    if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
        return False
    normalized = argument.value.replace("/", "\\").rstrip("\\").lower()
    return normalized.endswith("\\outputs") and (":\\" in normalized or normalized.startswith("\\\\"))


def top_level_function(tree: ast.Module, name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """按名称读取一个顶层函数。"""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    return None


def is_standard_resolver_definition(node: ast.AST) -> bool:
    """判断根目录函数是否与现行权威模板完全一致。"""
    standard_node = ast.parse(STANDARD_RESOLVER).body[0]
    return ast.dump(node, include_attributes=False) == ast.dump(standard_node, include_attributes=False)


def resolver_insertion_offset(tree: ast.Module, source: str, starts: list[int]) -> int:
    """把统一根目录函数插入模块导入区之后、业务定义之前。"""
    insert_after_line = 0
    for node in tree.body:
        is_docstring = (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and node is tree.body[0]
        )
        if isinstance(node, (ast.Import, ast.ImportFrom)) or is_docstring:
            insert_after_line = node.end_lineno
            continue
        break
    if insert_after_line == 0:
        return 0
    return starts[insert_after_line] if insert_after_line < len(starts) else len(source)


def collect_entry_edits(source: str, tree: ast.Module) -> list[SourceEdit]:
    """收集启动入口的安全机械编辑，不触碰网页定位和解析业务。"""
    lines, starts = build_line_index(source)
    edits: list[SourceEdit] = []
    resolver = top_level_function(tree, "resolve_project_dir")
    main_function = top_level_function(tree, "main")
    if main_function is None:
        return edits

    if resolver is None:
        insertion = resolver_insertion_offset(tree, source, starts)
        edits.append(SourceEdit(insertion, insertion, STANDARD_RESOLVER + "\n", "新增统一项目根目录解析函数"))
    elif not is_standard_resolver_definition(resolver):
        start, end = full_statement_span(resolver, source, starts)
        edits.append(SourceEdit(start, end, STANDARD_RESOLVER, "按权威模板更新项目根目录解析函数"))

    main_assignments = [
        node
        for node in main_function.body
        if assignment_target_name(node) in {"script_path", "project_dir"}
    ]
    project_assignment = next(
        (node for node in main_assignments if assignment_target_name(node) == "project_dir"),
        None,
    )
    if project_assignment is not None and is_inline_project_search(assignment_value(project_assignment)):
        start, end = full_statement_span(project_assignment, source, starts)
        original_line = lines[project_assignment.lineno - 1]
        indent = original_line[: len(original_line) - len(original_line.lstrip())]
        newline = "\r\n" if original_line.endswith("\r\n") else "\n"
        replacement = f"{indent}project_dir = resolve_project_dir(){newline}"
        edits.append(SourceEdit(start, end, replacement, "统一 main() 的项目根目录解析调用"))

        rendered_value = ast.dump(assignment_value(project_assignment), include_attributes=False)
        if "script_path" in rendered_value:
            script_assignment = next(
                (node for node in main_assignments if assignment_target_name(node) == "script_path"),
                None,
            )
            script_loads = [
                node
                for node in ast.walk(main_function)
                if isinstance(node, ast.Name) and node.id == "script_path" and isinstance(node.ctx, ast.Load)
            ]
            if script_assignment is not None and len(script_loads) == 1:
                script_start, script_end = full_statement_span(script_assignment, source, starts)
                edits.append(SourceEdit(script_start, script_end, "", "删除仅供旧根目录查找使用的 script_path 临时变量"))

    for node in ast.walk(main_function):
        if not isinstance(node, ast.Call) or function_name(node) != "run_page_adapter":
            continue
        for keyword in node.keywords:
            if keyword.arg != "output_dir":
                continue
            if not is_legacy_absolute_output_dir(keyword.value):
                continue
            start, _ = node_span(keyword, lines, starts)
            _, end = node_span(keyword.value, lines, starts)
            start, end = expand_comma_item(source, start, end)
            edits.append(SourceEdit(start, end, "", "删除写死的 output_dir，使用运行器默认项目输出目录"))

    return edits


def apply_source_edits(source: str, edits: list[SourceEdit]) -> str:
    """逆序应用互不重叠的源码编辑。"""
    ordered = sorted(edits, key=lambda item: (item.start, item.end))
    for previous, current in zip(ordered, ordered[1:]):
        if previous.end > current.start:
            raise ValueError(f"源码编辑区间重叠：{previous.reason} / {current.reason}")
    updated = source
    for edit in reversed(ordered):
        updated = updated[: edit.start] + edit.replacement + updated[edit.end :]
    return updated


def has_main_guard(tree: ast.Module) -> bool:
    """检查模块是否具有只调用 main() 的标准运行保护。"""
    for node in tree.body:
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
            continue
        test_text = ast.dump(node.test, include_attributes=False)
        if "__name__" not in test_text or "__main__" not in test_text:
            continue
        return any(
            isinstance(child, ast.Expr)
            and isinstance(child.value, ast.Call)
            and function_name(child.value) == "main"
            for child in node.body
        )
    return False


def audit_entry_structure(tree: ast.Module) -> tuple[list[str], str]:
    """验收统一入口，并区分公共运行器入口与站点专用入口。"""
    problems: list[str] = []
    resolvers = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "resolve_project_dir"
    ]
    if len(resolvers) != 1:
        problems.append(f"resolve_project_dir 顶层定义数量不是1：{len(resolvers)}")
    elif not is_standard_resolver_definition(resolvers[0]):
        problems.append("resolve_project_dir 与权威模板不一致")

    main_function = top_level_function(tree, "main")
    if main_function is None:
        problems.append("缺少 main() 函数")
        return problems, "未知入口"

    project_assignments = [
        node
        for node in main_function.body
        if assignment_target_name(node) == "project_dir"
    ]
    if len(project_assignments) != 1 or not is_standard_project_dir_call(assignment_value(project_assignments[0])):
        problems.append("main() 未唯一使用 project_dir = resolve_project_dir()")

    main_text = ast.dump(main_function, include_attributes=False)
    if "sys" not in main_text or "path" not in main_text or "insert" not in main_text:
        problems.append("main() 未把项目根目录加入 sys.path")
    if not has_main_guard(tree):
        problems.append("缺少标准 __main__ 运行保护")

    run_calls = [
        node
        for node in ast.walk(main_function)
        if isinstance(node, ast.Call) and function_name(node) == "run_page_adapter"
    ]
    for call in run_calls:
        if any(keyword.arg == "output_dir" for keyword in call.keywords):
            problems.append("run_page_adapter() 仍显式传入 output_dir")
    entry_type = "公共运行器入口" if run_calls else "站点专用入口"
    return sorted(set(problems)), entry_type


def normalize_one_script(script_path: Path, apply_changes: bool) -> tuple[str, int, str]:
    """规范单个脚本，并在写回前后分别完成语法和入口验收。"""
    source, has_bom = read_source(script_path)
    tree = ast.parse(source, filename=str(script_path))
    edits = collect_entry_edits(source, tree)
    updated = apply_source_edits(source, edits) if edits else source
    updated_tree = ast.parse(updated, filename=str(script_path))
    problems, entry_type = audit_entry_structure(updated_tree)
    if problems:
        return "失败", 0, "；".join(problems)
    if not edits:
        return "已符合", 0, entry_type
    reasons = "；".join(dict.fromkeys(edit.reason for edit in edits))
    if apply_changes:
        write_source(script_path, updated, has_bom)
        return "已修改", len(edits), f"{entry_type}；{reasons}"
    return "待修改", len(edits), f"{entry_type}；{reasons}"


def normalize_v3_entries(
    adapter_dir: Path,
    report_path: Path,
    log_path: Path,
    apply_changes: bool,
) -> None:
    """递归规范 V3 启动入口；单文件失败时记录后继续。"""
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = timestamped_output_path(report_path, run_timestamp)
    log_path = timestamped_output_path(log_path, run_timestamp)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    script_paths = sorted(path for path in adapter_dir.rglob("*.py") if path.is_file())

    try:
        from tqdm import tqdm
    except Exception:
        tqdm = None

    rows: list[list[str]] = [["状态", "编辑数", "脚本", "说明"]]
    status_counts: dict[str, int] = {}
    iterator = tqdm(script_paths, desc="统一V3脚本执行入口") if tqdm else script_paths
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
            cleaned = [value.replace("\t", " ").replace("\n", " ") for value in row]
            file.write("\t".join(cleaned) + "\n")

    write_log(log_path, f"脚本目录：{adapter_dir}")
    write_log(log_path, f"扫描脚本数：{len(script_paths)}")
    for status, count in sorted(status_counts.items()):
        write_log(log_path, f"{status}：{count}")
    write_log(log_path, f"报告路径：{report_path}")
    write_log(log_path, f"写回模式：{'是' if apply_changes else '否'}")


def main(adapter_dir: Path, report_path: Path, log_path: Path, apply_changes: bool) -> None:
    """统一脚本入口，封装完整的递归规范化流程。"""
    normalize_v3_entries(adapter_dir, report_path, log_path, apply_changes)


if __name__ == "__main__":
    adapter_dir_value = resolve_project_path("important_people/site_adapters/V3", anchor=__file__)
    report_path_value = resolve_project_path(
        "important_people/workspace/reports/V3脚本执行入口统一报告.txt", anchor=__file__
    )
    log_path_value = resolve_project_path(
        "important_people/workspace/log/V3脚本执行入口统一.log", anchor=__file__
    )
    apply_changes_value = True
    main(adapter_dir_value, report_path_value, log_path_value, apply_changes_value)
