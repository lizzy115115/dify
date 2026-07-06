"""Build importable Dify workflow DSL for the banking research production agent."""

from __future__ import annotations

from typing import Any

from prompts import (
    ANSWER_SYSTEM,
    ANSWER_USER,
    CLASSIFIER_INSTRUCTION,
    PARAMETER_EXTRACTOR_INSTRUCTION,
    QUERY_REWRITE_SYSTEM,
    QUERY_REWRITE_USER,
)

# Stable node IDs (numeric strings for Dify workflow graph)
N_START = "2000000000001"
N_EXTRACT = "2000000000002"
N_REWRITE = "2000000000003"
N_CLASSIFIER = "2000000000004"
N_RET_REG = "2000000000005"
N_RET_FILING = "2000000000006"
N_RET_EQUITY = "2000000000007"
N_RET_MACRO = "2000000000008"
N_RET_ALL = "2000000000009"
N_AGG = "2000000000010"
N_ANSWER = "2000000000011"
N_END = "2000000000013"


def _model_config(provider: str, model: str, temperature: float = 0.2) -> dict[str, Any]:
    return {
        "provider": provider,
        "name": model,
        "mode": "chat",
        "completion_params": {"temperature": temperature},
    }


def _node_shell(node_id: str, title: str, node_type: str, x: int, y: int, height: int = 90) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "custom",
        "width": 244,
        "height": height,
        "position": {"x": x, "y": y},
        "positionAbsolute": {"x": x, "y": y},
        "selected": False,
        "sourcePosition": "right",
        "targetPosition": "left",
        "data": {"title": title, "type": node_type, "desc": "", "selected": False},
    }


def _edge(source: str, target: str, source_type: str, target_type: str, source_handle: str = "source") -> dict[str, Any]:
    edge_id = f"{source}-{source_handle}-{target}-target"
    return {
        "id": edge_id,
        "source": source,
        "target": target,
        "sourceHandle": source_handle,
        "targetHandle": "target",
        "type": "custom",
        "data": {
            "isInIteration": False,
            "isInLoop": False,
            "sourceType": source_type,
            "targetType": target_type,
        },
    }


def _metadata_conditions(extra: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    conditions: list[dict[str, Any]] = [
        {"name": "is_valid", "comparison_operator": "=", "value": 1},
    ]
    if extra:
        conditions.extend(extra)
    return {"logical_operator": "and", "conditions": conditions}


def _retrieval_node(
    node_id: str,
    title: str,
    x: int,
    y: int,
    dataset_ids: list[str],
    rerank_model: str,
    rerank_provider: str,
    top_k: int,
    score_threshold: float,
    extra_metadata: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    node = _node_shell(node_id, title, "knowledge-retrieval", x, y)
    node["data"].update(
        {
            "desc": "hybrid_search + Rerank + is_valid=1",
            "dataset_ids": dataset_ids,
            "retrieval_mode": "multiple",
            "query_variable_selector": [N_REWRITE, "text"],
            "metadata_filtering_mode": "manual",
            "metadata_filtering_conditions": _metadata_conditions(extra_metadata),
            "multiple_retrieval_config": {
                "top_k": top_k,
                "score_threshold": score_threshold,
                "reranking_enable": True,
                "reranking_mode": "reranking_model",
                "reranking_model": {"model": rerank_model, "provider": rerank_provider},
            },
        }
    )
    return node


def normalize_parameter_extractor_query(graph: dict[str, Any]) -> bool:
    """Flatten legacy nested query selectors on parameter-extractor nodes."""
    changed = False
    for node in graph.get("nodes", []):
        data = node.get("data", {})
        if data.get("type") != "parameter-extractor":
            continue
        query = data.get("query")
        if (
            isinstance(query, list)
            and len(query) == 1
            and isinstance(query[0], list)
            and len(query[0]) == 2
            and all(isinstance(part, str) for part in query[0])
        ):
            data["query"] = list(query[0])
            changed = True
    return changed


def build_workflow_graph(
    routing: dict[str, str],
    *,
    llm_provider: str,
    llm_model: str,
    rerank_provider: str,
    rerank_model: str,
    top_k: int,
    score_threshold: float,
) -> dict[str, Any]:
    public_keys = ("macro", "industry", "equity", "filings", "regulation")
    all_public_ids = [routing[k] for k in public_keys if k in routing]

    nodes: list[dict[str, Any]] = []

    start = _node_shell(N_START, "用户输入", "start", 30, 300)
    start["data"]["variables"] = [
        {
            "label": "投研问题",
            "variable": "query",
            "type": "paragraph",
            "required": True,
            "max_length": 2000,
            "options": [],
        }
    ]
    nodes.append(start)

    extract = _node_shell(N_EXTRACT, "参数提取", "parameter-extractor", 300, 300, height=120)
    extract["data"].update(
        {
            "desc": "提取 ticker / 年份 / 报告期 / 行业",
            "query": [N_START, "query"],
            "reasoning_mode": "prompt",
            "instruction": PARAMETER_EXTRACTOR_INSTRUCTION,
            "model": _model_config(llm_provider, llm_model, 0.1),
            "parameters": [
                {
                    "name": "ticker",
                    "type": "string",
                    "description": "证券代码，如 600519、688256、NVDA",
                    "required": False,
                },
                {
                    "name": "fiscal_year",
                    "type": "string",
                    "description": "会计年度或自然年，如 2025、2026",
                    "required": False,
                },
                {
                    "name": "report_period",
                    "type": "string",
                    "description": "报告期，如 2025年报、2026Q1、FY2026 10-K",
                    "required": False,
                },
                {
                    "name": "industry_hint",
                    "type": "string",
                    "description": "行业关键词",
                    "required": False,
                },
            ],
            "vision": {"enabled": False},
        }
    )
    nodes.append(extract)

    rewrite = _node_shell(N_REWRITE, "查询改写", "llm", 570, 300)
    rewrite["data"].update(
        {
            "desc": "补全机构、报告期、指标，写入 ticker/年份",
            "model": _model_config(llm_provider, llm_model, 0.2),
            "prompt_template": [
                {"role": "system", "text": QUERY_REWRITE_SYSTEM},
                {"role": "user", "text": QUERY_REWRITE_USER},
            ],
            "context": {"enabled": False, "variable_selector": []},
            "variables": [],
            "vision": {"enabled": False},
        }
    )
    nodes.append(rewrite)

    classifier = _node_shell(N_CLASSIFIER, "意图路由", "question-classifier", 840, 300, height=180)
    classes = [
        {"id": "1", "name": "监管政策问询", "label": "监管政策"},
        {"id": "2", "name": "财报公告问询", "label": "财报公告"},
        {"id": "3", "name": "个股研报问询", "label": "个股研报"},
        {"id": "4", "name": "宏观行业问询", "label": "宏观行业"},
        {"id": "5", "name": "综合投研问询", "label": "综合投研"},
    ]
    classifier["data"].update(
        {
            "desc": "按意图路由至子库检索，降低 P99",
            "query_variable_selector": [N_REWRITE, "text"],
            "instruction": CLASSIFIER_INSTRUCTION,
            "classes": classes,
            "_targetBranches": [{"id": c["id"], "name": c["label"]} for c in classes],
            "model": _model_config(llm_provider, llm_model, 0.2),
            "vision": {"enabled": False},
        }
    )
    nodes.append(classifier)

    retrieval_specs = [
        (N_RET_REG, "检索-监管库", routing["regulation"], "1", 1110, 80),
        (N_RET_FILING, "检索-财报库", routing["filings"], "2", 1110, 220),
        (N_RET_EQUITY, "检索-个股库", routing["equity"], "3", 1110, 360),
        (N_RET_MACRO, "检索-宏观行业", [routing["macro"], routing["industry"]], "4", 1110, 500),
        (N_RET_ALL, "检索-综合五库", all_public_ids, "5", 1110, 640),
    ]

    for node_id, title, ds_ids, _class_id, _x, y in retrieval_specs:
        ids = ds_ids if isinstance(ds_ids, list) else [ds_ids]
        nodes.append(
            _retrieval_node(
                node_id,
                title,
                1110,
                y,
                ids,
                rerank_model,
                rerank_provider,
                top_k,
                score_threshold,
            )
        )

    agg = _node_shell(N_AGG, "检索结果汇聚", "variable-aggregator", 1380, 360, height=160)
    agg["data"].update(
        {
            "desc": "合并五路检索结果（仅命中分支有值）",
            "output_type": "array[object]",
            "advanced_settings": {"group_enabled": False, "groups": []},
            "variables": [
                [N_RET_REG, "result"],
                [N_RET_FILING, "result"],
                [N_RET_EQUITY, "result"],
                [N_RET_MACRO, "result"],
                [N_RET_ALL, "result"],
            ],
        }
    )
    nodes.append(agg)

    answer = _node_shell(N_ANSWER, "投研回答生成", "llm", 1650, 360, height=120)
    answer["data"].update(
        {
            "desc": "强制 segment_id 引用 + 元数据年份核对",
            "model": _model_config(llm_provider, llm_model, 0.3),
            "prompt_template": [
                {"role": "system", "text": ANSWER_SYSTEM},
                {"role": "user", "text": ANSWER_USER},
            ],
            "context": {"enabled": True, "variable_selector": [N_AGG, "output"]},
            "variables": [],
            "vision": {"enabled": False},
        }
    )
    nodes.append(answer)

    end = _node_shell(N_END, "输出", "end", 1920, 360)
    end["data"]["outputs"] = [
        {
            "variable": "answer",
            "value_selector": [N_ANSWER, "text"],
            "value_type": "string",
        },
        {
            "variable": "rewrite_query",
            "value_selector": [N_REWRITE, "text"],
            "value_type": "string",
        },
        {
            "variable": "extracted_ticker",
            "value_selector": [N_EXTRACT, "ticker"],
            "value_type": "string",
        },
    ]
    nodes.append(end)

    edges: list[dict[str, Any]] = [
        _edge(N_START, N_EXTRACT, "start", "parameter-extractor"),
        _edge(N_EXTRACT, N_REWRITE, "parameter-extractor", "llm"),
        _edge(N_REWRITE, N_CLASSIFIER, "llm", "question-classifier"),
        _edge(N_CLASSIFIER, N_RET_REG, "question-classifier", "knowledge-retrieval", "1"),
        _edge(N_CLASSIFIER, N_RET_FILING, "question-classifier", "knowledge-retrieval", "2"),
        _edge(N_CLASSIFIER, N_RET_EQUITY, "question-classifier", "knowledge-retrieval", "3"),
        _edge(N_CLASSIFIER, N_RET_MACRO, "question-classifier", "knowledge-retrieval", "4"),
        _edge(N_CLASSIFIER, N_RET_ALL, "question-classifier", "knowledge-retrieval", "5"),
        _edge(N_RET_REG, N_AGG, "knowledge-retrieval", "variable-aggregator"),
        _edge(N_RET_FILING, N_AGG, "knowledge-retrieval", "variable-aggregator"),
        _edge(N_RET_EQUITY, N_AGG, "knowledge-retrieval", "variable-aggregator"),
        _edge(N_RET_MACRO, N_AGG, "knowledge-retrieval", "variable-aggregator"),
        _edge(N_RET_ALL, N_AGG, "knowledge-retrieval", "variable-aggregator"),
        _edge(N_AGG, N_ANSWER, "variable-aggregator", "llm"),
        _edge(N_ANSWER, N_END, "llm", "end"),
    ]

    graph = {"nodes": nodes, "edges": edges}
    normalize_parameter_extractor_query(graph)
    return graph


def build_app_dsl(
    routing: dict[str, str],
    *,
    llm_provider: str,
    llm_model: str,
    rerank_provider: str,
    rerank_model: str,
    top_k: int,
    score_threshold: float,
) -> dict[str, Any]:
    graph = build_workflow_graph(
        routing,
        llm_provider=llm_provider,
        llm_model=llm_model,
        rerank_provider=rerank_provider,
        rerank_model=rerank_model,
        top_k=top_k,
        score_threshold=score_threshold,
    )

    return {
        "app": {
            "name": "投研知识库智能体",
            "description": (
                "生产级投研 RAG：参数提取 → 查询改写 → 意图路由 → "
                "分库 hybrid/Rerank + is_valid 元数据过滤 → 引用式回答"
            ),
            "icon": "📊",
            "icon_background": "#E4F2FF",
            "mode": "workflow",
            "use_icon_as_answer_icon": False,
        },
        "dependencies": [],
        "kind": "app",
        "version": "0.4.0",
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [],
            "features": {
                "file_upload": {"enabled": False},
                "opening_statement": (
                    "华东投研知识库智能体（Milvus hybrid + Rerank + 元数据过滤）。\n"
                    "回答仅含三章：结论摘要、依据与数据、元数据说明；资料不足时将直接说明无依据。"
                ),
                "retriever_resource": {"enabled": True},
                "sensitive_word_avoidance": {"enabled": False},
                "speech_to_text": {"enabled": False},
                "suggested_questions": [
                    "2026年工信部75号人工智能科技伦理审查办法的核心要求是什么？",
                    "贵州茅台600519 2026Q1报告里的营收和归母净利润是多少？",
                    "贵州茅台600519 2025年年度报告摘要披露的关键财务指标有哪些？",
                    "寒武纪688256 2026Q1季报营收与毛利率是多少？",
                    "对比600519、300502、688256三家公司2026Q1业绩增速",
                ],
                "suggested_questions_after_answer": {"enabled": False},
                "text_to_speech": {"enabled": False},
            },
            "graph": {
                "nodes": graph["nodes"],
                "edges": graph["edges"],
                "viewport": {"x": 0, "y": 0, "zoom": 0.55},
            },
        },
    }


def dump_yaml(dsl: dict[str, Any]) -> str:
    import yaml

    class _Dumper(yaml.SafeDumper):
        pass

    def _str_representer(dumper: yaml.SafeDumper, data: str) -> yaml.nodes.ScalarNode:
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    _Dumper.add_representer(str, _str_representer)
    return yaml.dump(dsl, Dumper=_Dumper, allow_unicode=True, sort_keys=False, width=120)
