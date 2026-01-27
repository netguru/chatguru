"""
RAGAS Dataset Builder for LLM-based RAG Evaluation.

This module provides utilities for creating and managing evaluation datasets
compatible with RAGAS (Retrieval-Augmented Generation Assessment) framework.
"""

from typing import Any

import pandas as pd
from datasets import Dataset


def get_ragas_test_cases() -> list[dict[str, Any]]:
    """
    Golden test set for RAGAS LLM-based evaluation.
    Change this set rarely and deliberately.

    Each test case should have:
    - question: The user query
    - ground_truth: Expected correct answer
    - expected_product_ids: IDs of products that should be relevant (optional)
    """

    return [
        {
            "question": "What t-shirts do you have around $40?",
            "ground_truth": (
                "We offer the Oversized Graphic T-Shirt (Vintage Wash) priced at $40. "
                "It is made from 100% cotton and available in washed blue."
            ),
        },
        {
            "question": "What denim products do you offer?",
            "ground_truth": (
                "We offer Denim Overalls with a relaxed fit priced at $99, as well as "
                "Slim Fit Stretch Denim Shorts priced at $49."
            ),
        },
    ]


def build_empty_ragas_dataset() -> Dataset:
    """
    Create an empty RAGAS-compatible dataset skeleton.

    The 'answer' and 'contexts' columns will be populated by the RAG pipeline.
    This follows RAGAS expected format for evaluation.

    Returns:
        HuggingFace Dataset with columns: question, ground_truth, answer, contexts
    """
    test_cases = get_ragas_test_cases()

    dataset_df = pd.DataFrame(
        {
            "question": [tc["question"] for tc in test_cases],
            "ground_truth": [tc["ground_truth"] for tc in test_cases],
            "answer": ["" for _ in test_cases],  # To be filled by LLM
            "contexts": [[] for _ in test_cases],  # To be filled by retriever
        }
    )

    return Dataset.from_pandas(dataset_df)


def build_ragas_dataset_with_contexts(contexts_list: list[list[str]]) -> Dataset:
    """
    Create a RAGAS dataset with pre-populated contexts.

    Args:
        contexts_list: List of context lists, one per test case

    Returns:
        Dataset ready for answer generation and evaluation
    """
    test_cases = get_ragas_test_cases()

    if len(contexts_list) != len(test_cases):
        expected = len(test_cases)
        actual = len(contexts_list)
        msg = f"Expected {expected} context lists, got {actual}"
        raise ValueError(msg)

    dataset_df = pd.DataFrame(
        {
            "question": [tc["question"] for tc in test_cases],
            "ground_truth": [tc["ground_truth"] for tc in test_cases],
            "answer": ["" for _ in test_cases],
            "contexts": contexts_list,
        }
    )

    return Dataset.from_pandas(dataset_df)


def build_complete_ragas_dataset(
    contexts_list: list[list[str]], answers_list: list[str]
) -> Dataset:
    """
    Create a complete RAGAS dataset with contexts and answers.

    Args:
        contexts_list: List of context lists, one per test case
        answers_list: List of generated answers, one per test case

    Returns:
        Complete dataset ready for RAGAS evaluation
    """
    test_cases = get_ragas_test_cases()

    if len(contexts_list) != len(test_cases) or len(answers_list) != len(test_cases):
        expected = len(test_cases)
        actual_contexts = len(contexts_list)
        actual_answers = len(answers_list)
        msg = (
            "Expected "
            f"{expected} items, got "
            f"{actual_contexts} contexts and "
            f"{actual_answers} answers"
        )
        raise ValueError(msg)

    dataset_df = pd.DataFrame(
        {
            "question": [tc["question"] for tc in test_cases],
            "ground_truth": [tc["ground_truth"] for tc in test_cases],
            "answer": answers_list,
            "contexts": contexts_list,
        }
    )

    return Dataset.from_pandas(dataset_df)
