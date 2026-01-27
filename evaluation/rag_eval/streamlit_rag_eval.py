import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, cast

import pandas as pd
import streamlit as st

st.set_page_config(page_title="RAG Evaluator", layout="wide")

st.title("🔎 RAG Evaluator Dashboard")

# ===============================
# LOAD JSON
# ===============================
json_path = st.text_input("Path to RAG evaluator JSON", value="rag_results.json")


def load_json_data(json_path: str) -> dict[str, Any]:
    """Load JSON data from file."""
    try:
        with Path(json_path).open(encoding="utf-8") as f:
            data = cast(dict[str, Any], json.load(f))
    except (FileNotFoundError, JSONDecodeError, OSError) as e:
        st.error(f"Failed to load JSON: {e}")
        return {}
    else:
        return data


data = load_json_data(json_path)

if data:
    st.success("RAG evaluation results loaded")

    retriever = data["retriever_evaluation"]
    vector_db = data["vector_db_evaluation"]

    st.divider()

    # ===============================
    # OVERALL METRICS
    # ===============================
    st.header("📊 Overall metrics")

    def show_metrics(title: str, section: dict[str, Any]) -> None:
        st.subheader(title)
        cols = st.columns(4)
        cols[0].metric(
            "Retrieval success rate", f"{section['retrieval_success_rate']:.2f}"
        )
        cols[1].metric("Context relevance", f"{section['context_relevance_score']:.2f}")
        cols[2].metric("Diversity score", f"{section['retrieval_diversity_score']:.2f}")
        cols[3].metric(
            "Avg retrieved products", f"{section['average_retrieved_products']:.1f}"
        )

    col1, col2 = st.columns(2)
    with col1:
        show_metrics("🧠 Retriever", retriever)
    with col2:
        show_metrics("📦 Vector DB", vector_db)

    st.divider()

    # ===============================
    # DETAILS TABLE
    # ===============================
    st.header("📋 Per-question details")

    def details_to_df(section: dict[str, Any]) -> pd.DataFrame:
        return pd.DataFrame(section["details"])

    tab1, tab2 = st.tabs(["Retriever", "Vector DB"])

    with tab1:
        df_r = details_to_df(retriever)
        st.dataframe(
            df_r[
                [
                    "question",
                    "retrieval_success",
                    "relevance_score",
                    "diversity_score",
                    "products_retrieved",
                ]
            ],
            width="stretch",
        )

    with tab2:
        df_v = details_to_df(vector_db)
        st.dataframe(
            df_v[
                [
                    "question",
                    "retrieval_success",
                    "relevance_score",
                    "diversity_score",
                    "products_retrieved",
                ]
            ],
            width="stretch",
        )

    st.divider()

    # ===============================
    # FAILURE ANALYSIS
    # ===============================
    st.header("❌ Failure analysis")

    def show_failures(df: pd.DataFrame, label: str) -> None:
        failed = df[df["retrieval_success"] == 0.0]
        st.subheader(label)
        if failed.empty:
            st.success("No retrieval failures 🎉")
        else:
            st.warning(f"{len(failed)} failed cases")
            st.dataframe(
                failed[
                    [
                        "question",
                        "expected_product_names",
                        "products_retrieved",
                        "relevance_score",
                    ]
                ],
                width="stretch",
            )

    col1, col2 = st.columns(2)
    with col1:
        show_failures(df_r, "Retriever failures")
    with col2:
        show_failures(df_v, "Vector DB failures")

    st.divider()

    # ===============================
    # METADATA
    # ===============================
    st.header("Metadata")

    meta = data["metadata"]
    st.json(meta)

    st.divider()
