from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None

from crawler_core.exporter import OUTPUT_FIELDS
from crawler_core.paths import resolve_path_argument

V3_OUTPUT_FIELDS = tuple(OUTPUT_FIELDS)


@dataclass
class TxtResult:
    """单个结果文件的排序与内容信息。"""

    file_path: Path
    domain: str
    sort_url: str
    rule_id: str
    organization: str
    header: str
    data_lines: list[str]


def write_log(log_path: Path, message: str) -> None:
    """同时输出到控制台和日志文件。"""
    print(message)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(message + "\n")


def iter_with_progress(items: list[Path], description: str) -> Iterable[Path]:
    """在 tqdm 可用时显示进度条。"""
    if tqdm is None:
        return items
    return tqdm(items, desc=description, unit="个文件")


def read_text_lines(file_path: Path) -> list[str]:
    """优先按 UTF-8 读取，失败时兼容少量非 UTF-8 文本。"""
    try:
        return file_path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeDecodeError:
        return file_path.read_text(encoding="gb18030", errors="replace").splitlines()


def normalize_url_for_sort(url: str) -> str:
    """生成稳定的小写排序键。"""
    return url.strip().lower()


def extract_domain(url: str) -> str:
    """从网址中提取域名，失败时返回空字符串。"""
    parsed = urlparse(url.strip())
    if parsed.hostname:
        return parsed.hostname.lower()
    return ""


def find_column(header: str, target_name: str) -> int:
    """按列名定位字段，未找到时返回-1。"""
    columns = header.split("\t")
    for index, column_name in enumerate(columns):
        if column_name.strip() == target_name:
            return index
    return -1


def load_rule_order(rule_table_path: Path) -> tuple[dict[str, int], dict[str, int]]:
    """按规则主表物理行序建立脚本序号和机构名称排序映射。"""
    if not rule_table_path.is_file():
        raise FileNotFoundError(f"未找到规则主表：{rule_table_path}")
    lines = [line for line in read_text_lines(rule_table_path) if line.strip()]
    if not lines:
        raise ValueError("规则主表为空")
    headers = [column.strip() for column in lines[0].split("\t")]
    expected_headers = [
        "组织体系", "目录链接", "机构类型", "机构层级", "所属省*", "所属市",
        "机构名称", "机构别称", "官网链接", "领导链接", "脚本序号", "备注",
    ]
    if headers != expected_headers:
        raise ValueError(f"规则主表表头或列序不符合十二列契约：{headers}")

    organization_index = headers.index("机构名称")
    rule_id_index = headers.index("脚本序号")
    rule_id_order: dict[str, int] = {}
    organization_order: dict[str, int] = {}
    for physical_order, line in enumerate(lines[1:]):
        columns = line.split("\t")
        if len(columns) != len(headers):
            raise ValueError(
                f"规则主表第{physical_order + 2}行列数错误："
                f"应为{len(headers)}列，实际为{len(columns)}列"
            )
        organization = columns[organization_index].strip()
        rule_id = columns[rule_id_index].strip()
        if not organization or not rule_id:
            raise ValueError(f"规则主表第{physical_order + 2}行机构名称或脚本序号为空")
        if rule_id in rule_id_order:
            raise ValueError(f"规则主表脚本序号重复：{rule_id}")
        rule_id_order[rule_id] = physical_order
        organization_order.setdefault(organization, physical_order)
    return rule_id_order, organization_order


def get_output_column_indices(header: str) -> list[int]:
    """校验V3十二列表头，并返回按统一契约重排所需的列索引。"""
    columns = [column_name.strip() for column_name in header.split("\t")]
    missing_fields = [field for field in V3_OUTPUT_FIELDS if field not in columns]
    if missing_fields:
        raise ValueError(f"不是V3十二列结果，缺少字段：{'、'.join(missing_fields)}")
    return [columns.index(field) for field in V3_OUTPUT_FIELDS]


def project_tsv_line(line: str, keep_indices: list[int]) -> str:
    """按保留列索引投影 TSV 行，缺失列以空字符串补齐。"""
    columns = line.split("\t")
    return "\t".join(columns[index] if index < len(columns) else "" for index in keep_indices)


def get_row_column(line: str, column_index: int) -> str:
    """按制表符获取指定列，缺失时返回空字符串。"""
    columns = line.split("\t")
    if 0 <= column_index < len(columns):
        return columns[column_index].strip()
    return ""


def collect_txt_files(result_folder: Path, recursive: bool) -> list[Path]:
    """收集待合并的 txt 文件。"""
    if recursive:
        files = [path for path in result_folder.rglob("*.txt") if path.is_file()]
    else:
        files = [path for path in result_folder.glob("*.txt") if path.is_file()]
    return sorted(files, key=lambda path: path.name.lower())


def parse_result_file(file_path: Path) -> TxtResult:
    """解析单个结果 txt，保留原文件内部数据顺序。"""
    lines = [line.rstrip("\n\r") for line in read_text_lines(file_path) if line.strip()]
    if not lines:
        raise ValueError("文件为空")

    source_header = lines[0]
    source_data_lines = lines[1:]
    if not source_data_lines:
        raise ValueError("文件没有数据行")

    url_column_index = find_column(source_header, "依据链接")
    if url_column_index < 0:
        raise ValueError("表头缺少“依据链接”列")
    rule_id_column_index = find_column(source_header, "脚本序号")
    organization_column_index = find_column(source_header, "机构")

    sort_url = ""
    domain = ""
    for line in source_data_lines:
        current_url = get_row_column(line, url_column_index)
        current_domain = extract_domain(current_url)
        if current_url and current_domain:
            sort_url = current_url
            domain = current_domain
            break

    if not sort_url or not domain:
        raise ValueError("未找到有效网址")

    rule_ids = list(
        dict.fromkeys(
            value
            for line in source_data_lines
            if (value := get_row_column(line, rule_id_column_index))
        )
    )
    organizations = list(
        dict.fromkeys(
            value
            for line in source_data_lines
            if (value := get_row_column(line, organization_column_index))
        )
    )
    if len(rule_ids) > 1:
        raise ValueError(f"同一结果文件包含多个脚本序号：{'、'.join(rule_ids)}")
    if len(organizations) > 1:
        raise ValueError(f"同一结果文件包含多个机构：{'、'.join(organizations)}")
    rule_id = rule_ids[0] if rule_ids else ""
    if not rule_id:
        filename_match = re.match(r"^(\d{4})_", file_path.stem)
        rule_id = filename_match.group(1) if filename_match else ""

    keep_indices = get_output_column_indices(source_header)
    return TxtResult(
        file_path=file_path,
        domain=domain,
        sort_url=sort_url,
        rule_id=rule_id,
        organization=organizations[0] if organizations else "",
        header="\t".join(V3_OUTPUT_FIELDS),
        data_lines=[project_tsv_line(line, keep_indices) for line in source_data_lines],
    )


def build_result_sort_key(
    result: TxtResult,
    rule_id_order: dict[str, int],
    organization_order: dict[str, int],
) -> tuple[int, int, str, str, str]:
    """生成规则主表顺序优先、旧排序规则兜底的稳定排序键。"""
    physical_order = rule_id_order.get(result.rule_id)
    if physical_order is None:
        physical_order = organization_order.get(result.organization)
    if physical_order is not None:
        return (0, physical_order, "", "", result.file_path.name.lower())
    return (
        1,
        len(rule_id_order),
        result.domain,
        normalize_url_for_sort(result.sort_url),
        result.file_path.name.lower(),
    )


def build_merged_lines(
    results: list[TxtResult],
    rule_id_order: dict[str, int],
    organization_order: dict[str, int],
) -> tuple[list[str], int]:
    """按机构在规则主表中的物理相对顺序合并所有数据行。"""
    if not results:
        return [], 0

    master_header = results[0].header
    merged_lines = [master_header]
    data_line_count = 0
    sorted_results = sorted(
        results,
        key=lambda item: build_result_sort_key(item, rule_id_order, organization_order),
    )
    for item in sorted_results:
        merged_lines.extend(item.data_lines)
        data_line_count += len(item.data_lines)

    return merged_lines, data_line_count


def main(
    result_folder_path: str | Path,
    recursive: bool,
    rule_table_path: str | Path,
    project_dir: str | Path | None = None,
) -> Path | None:
    """合并指定目录中的 txt 结果文件。"""
    project_root = resolve_path_argument(
        project_dir or r"important_people", anchor=__file__, must_exist=True
    )
    result_folder = resolve_path_argument(
        result_folder_path, anchor=__file__, must_exist=True
    )
    rule_table_path = resolve_path_argument(
        rule_table_path, anchor=__file__, must_exist=True
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = project_root / "职务规范1：合并.txt"
    log_path = project_root / "workspace" / "log" / f"职务规范1：合并_{timestamp}.log"

    write_log(log_path, f"开始时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    write_log(log_path, f"结果目录：{result_folder}")
    write_log(log_path, f"递归扫描：{recursive}")
    write_log(log_path, f"排序规则主表：{rule_table_path}")

    if not result_folder.exists() or not result_folder.is_dir():
        write_log(log_path, f"目录不存在或不是文件夹：{result_folder}")
        return None

    rule_id_order, organization_order = load_rule_order(rule_table_path)
    write_log(log_path, f"规则主表机构记录：{len(rule_id_order)}")

    txt_files = collect_txt_files(result_folder, recursive)
    write_log(log_path, f"发现 txt 文件：{len(txt_files)}")
    if not txt_files:
        write_log(log_path, "没有可合并的 txt 文件。")
        return None

    results: list[TxtResult] = []
    skipped_count = 0
    master_header = ""

    for file_path in iter_with_progress(txt_files, "解析结果文件"):
        try:
            result = parse_result_file(file_path)
            if not master_header:
                master_header = result.header
            elif result.header != master_header:
                write_log(log_path, f"跳过：{file_path.name}，原因：表头与首个文件不一致")
                skipped_count += 1
                continue
            results.append(result)
        except Exception as error:
            write_log(log_path, f"跳过：{file_path.name}，原因：{error}")
            skipped_count += 1

    merged_lines, data_line_count = build_merged_lines(results, rule_id_order, organization_order)
    if not merged_lines:
        write_log(log_path, "没有成功解析的数据，未生成合并文件。")
        return None

    output_path.write_text("\n".join(merged_lines) + "\n", encoding="utf-8")

    domain_count = len({result.domain for result in results})
    matched_count = sum(
        1
        for result in results
        if result.rule_id in rule_id_order or result.organization in organization_order
    )
    write_log(log_path, f"成功合并文件：{len(results)}")
    write_log(log_path, f"跳过文件：{skipped_count}")
    write_log(log_path, f"域名数量：{domain_count}")
    write_log(log_path, f"按规则主表定位文件：{matched_count}")
    write_log(log_path, f"未在规则主表定位文件：{len(results) - matched_count}")
    write_log(log_path, f"合并数据行：{data_line_count}")
    write_log(log_path, f"输出文件：{output_path}")
    write_log(log_path, f"结束时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return output_path


if __name__ == "__main__":
    project_dir_value = r"important_people"
    result_folder_path_value = r"important_people/outputs/成功"
    recursive_value = True
    rule_table_path_value = r"important_people/workspace/source_data/规则主表.txt"
    main(
        result_folder_path=result_folder_path_value,
        recursive=recursive_value,
        rule_table_path=rule_table_path_value,
        project_dir=project_dir_value,
    )
