from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup

from crawler_core.deepseek_client import DeepSeekJsonResult, call_deepseek_json
from crawler_core.models import PersonRecord
from crawler_core.rule_table import normalize_script_sequence


def compact_text(value: object) -> str:
    """压缩文本空白，供模型证据回指校验。"""
    return " ".join(str(value or "").replace("\u3000", " ").split()).strip()


def resolve_prompt_path(project_dir: Path, prompt_path_value: object) -> Path:
    """解析项目内提示词路径并阻止越出项目目录。"""
    raw_path = Path(str(prompt_path_value or "").strip())
    prompt_path = raw_path if raw_path.is_absolute() else project_dir / raw_path
    resolved_path = prompt_path.resolve()
    try:
        resolved_path.relative_to(project_dir.resolve())
    except ValueError as error:
        raise ValueError(f"提示词必须位于项目目录内：{resolved_path}") from error
    if not resolved_path.is_file():
        raise FileNotFoundError(f"提示词文件不存在：{resolved_path}")
    return resolved_path


def extract_article_source_text(html: str, strategy: dict[str, Any]) -> tuple[str, str]:
    """按已核验选择器裁剪文章正文，并删除明确噪声节点。"""
    content_selector = str(strategy.get("content_selector") or "").strip()
    if not content_selector:
        raise ValueError("文章大模型抽取缺少content_selector")
    soup = BeautifulSoup(html, "html.parser")
    content_node = soup.select_one(content_selector)
    if content_node is None:
        raise ValueError(f"正文选择器未命中：{content_selector}")

    for selector in strategy.get("exclude_selectors") or []:
        selector_text = str(selector or "").strip()
        if not selector_text:
            continue
        for node in content_node.select(selector_text):
            node.decompose()
    for node in content_node.select("script, style, noscript, template"):
        node.decompose()

    raw_lines = [compact_text(line) for line in content_node.get_text("\n", strip=True).splitlines()]
    source_text = "\n".join(line for line in raw_lines if line)
    if len(compact_text(source_text)) < 20:
        raise ValueError(f"正文文本过短：{len(compact_text(source_text))}")
    return source_text, content_selector


def normalize_model_order(value: object, fallback: int) -> int:
    """规范模型返回的来源顺序。"""
    try:
        order = int(value)
    except Exception:
        order = fallback
    return order if order > 0 else fallback


def validate_article_rows(
    rule: dict[str, Any],
    payload: dict[str, Any],
    source_text: str,
    content_selector: str,
) -> list[PersonRecord]:
    """验证模型记录能够回指正文，并转换为项目人物模型。"""
    raw_rows = payload.get("rows")
    if not isinstance(raw_rows, list):
        raise RuntimeError("文章大模型JSON缺少rows数组")

    normalized_source = compact_text(source_text)
    sequence = normalize_script_sequence(rule.get("rule_id") or rule.get("sequence"))
    pending_rows: list[tuple[int, PersonRecord]] = []
    seen_names: set[str] = set()
    for index, item in enumerate(raw_rows, start=1):
        if not isinstance(item, dict):
            continue
        name = compact_text(item.get("name")).replace(" ", "")
        raw_duty = compact_text(item.get("raw_duty") or item.get("duty"))
        evidence = compact_text(item.get("evidence"))
        if not re.fullmatch(r"[\u3400-\u9fff·•]{2,12}", name):
            continue
        if not raw_duty or not evidence or name in seen_names:
            continue
        if name not in evidence or raw_duty not in evidence:
            continue
        if evidence not in normalized_source:
            continue
        seen_names.add(name)
        order = normalize_model_order(item.get("source_order"), index)
        pending_rows.append(
            (
                order,
                PersonRecord(
                    organization=str(rule.get("organization", "")),
                    url=str(rule.get("url", "")),
                    name=name,
                    duty=raw_duty,
                    detail_url="",
                    evidence=evidence,
                    confidence=str(rule.get("confidence", "大模型原文已校验")),
                    parser=str(rule.get("parser", "LLM_TEXT_ARTICLE_V1")),
                    selector_summary=f"strategy=llm_text；content={content_selector}；evidence=正文原文回指",
                    order=str(order),
                    script_sequence=sequence,
                ),
            )
        )
    pending_rows.sort(key=lambda pair: pair[0])
    return [row for _, row in pending_rows]


def write_llm_audit(
    project_dir: Path,
    rule: dict[str, Any],
    result: DeepSeekJsonResult,
    prompt_path: Path,
    source_length: int,
    accepted_count: int,
) -> Path:
    """写出不含密钥的文章模型调用审计JSON。"""
    sequence = normalize_script_sequence(rule.get("rule_id") or rule.get("sequence")) or "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    audit_path = (
        project_dir / "workspace" / "reports" / "llm_audit" / f"{sequence}_article_{timestamp}.json"
    )
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "script_sequence": sequence,
        "type": "article_llm_text",
        "model": result.model,
        "base_url": result.base_url,
        "prompt_path": str(prompt_path.relative_to(project_dir)),
        "prompt_hash": result.prompt_hash,
        "input_hash": result.input_hash,
        "source_length": source_length,
        "accepted_count": accepted_count,
        "elapsed_seconds": round(result.elapsed_seconds, 3),
        "raw_response": result.raw_text,
        "parsed_payload": result.payload,
    }
    audit_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit_path


def parse_llm_text_records(
    rule: dict[str, Any],
    html: str,
    final_url: str,
    timeout_seconds: int,
) -> list[PersonRecord]:
    """裁剪文章正文，调用DeepSeek并返回证据可回指的人物记录。"""
    project_dir = Path(__file__).resolve().parents[1]
    strategy = rule.get("llm_strategy") if isinstance(rule.get("llm_strategy"), dict) else {}
    source_text, content_selector = extract_article_source_text(html, strategy)
    prompt_path = resolve_prompt_path(project_dir, strategy.get("prompt_path"))
    prompt = prompt_path.read_text(encoding="utf-8")
    extra_instruction = compact_text(strategy.get("instruction"))
    if extra_instruction:
        prompt = f"{prompt}\n\n本页补充要求：{extra_instruction}"
    prompt = (
        f"{prompt}\n\n机构：{compact_text(rule.get('organization'))}"
        f"\n依据链接：{compact_text(rule.get('url') or final_url)}"
    )
    result = call_deepseek_json(
        prompt=prompt,
        source_label="文章正文",
        source_text=source_text,
        project_dir=project_dir,
        timeout_seconds=timeout_seconds,
    )
    rows = validate_article_rows(rule, result.payload, source_text, content_selector)
    write_llm_audit(project_dir, rule, result, prompt_path, len(source_text), len(rows))
    return rows
