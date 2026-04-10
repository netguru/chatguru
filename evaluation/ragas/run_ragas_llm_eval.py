"""
LLM-based RAG Evaluation using RAGAS Framework.

This script performs comprehensive evaluation of the RAG system using RAGAS metrics
that require LLM calls. It evaluates faithfulness, answer relevancy, context relevancy,
and other advanced metrics.

Usage:
    python scripts/run_ragas_llm_eval.py
    # or
    make ragas-llm-eval

Requirements:
    - Azure OpenAI API access (for evaluation LLM and system)
    - Azure OpenAI access (for embeddings and retriever)
    - Optional: Vector database service running (for comparison)
"""

import asyncio
import os
from pathlib import Path
from typing import Any, cast

import pandas as pd
from datasets import Dataset
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI
from openai import OpenAI
from pydantic import SecretStr
from ragas import evaluate
from ragas.embeddings.base import LangchainEmbeddingsWrapper
from ragas.evaluation import EvaluationResult
from ragas.llms import llm_factory
from ragas.metrics import AnswerRelevancy, Faithfulness
from src.config import get_logger
from src.rag.documents import create_product_document
from src.rag.simple_retriever import SimpleProductRetriever
from src.vector_db import create_vector_database

from evaluation.ragas.test_ragas_dataset import (
    build_complete_ragas_dataset,
    build_empty_ragas_dataset,
    build_ragas_dataset_with_contexts,
)

logger = get_logger("ragas_llm_eval")


class RagasLLMEvaluator:
    """LLM-based RAG evaluator using RAGAS framework."""

    def __init__(self, *, use_vector_db: bool = True) -> None:
        """
        Initialize the RAGAS LLM evaluator.

        Args:
            use_vector_db: Whether to use vector database for retrieval (if available)
        """
        self.use_vector_db = use_vector_db
        self.retriever = self._setup_retriever()
        self.vector_db = self._setup_vector_db() if use_vector_db else None

        # Initialize generation LLM (for answer generation)
        llm_endpoint = os.getenv("LLM_ENDPOINT")
        llm_api_key = os.getenv("LLM_API_KEY")
        llm_api_version = os.getenv("LLM_API_VERSION")
        llm_deployment_name = os.getenv("LLM_DEPLOYMENT_NAME")
        llm_compat_base = (os.getenv("LLM_OPENAI_BASE_URL") or "").strip()
        missing_vars_msg = "Missing required environment variables for LLM"
        if not all([llm_api_key, llm_deployment_name]):
            raise ValueError(missing_vars_msg)
        self.gen_llm: ChatOpenAI | AzureChatOpenAI
        if llm_compat_base:
            endpoint_required_msg = (
                "LLM_ENDPOINT is required for embeddings when using RAGAS eval"
            )
            if not llm_endpoint:
                raise ValueError(endpoint_required_msg)
            self.gen_llm = ChatOpenAI(
                model=str(llm_deployment_name),
                api_key=SecretStr(str(llm_api_key)),
                base_url=llm_compat_base.rstrip("/"),
                default_headers={"api-key": str(llm_api_key)},
                temperature=0,
            )
            eval_base = llm_compat_base.rstrip("/")
        else:
            if not all([llm_endpoint, llm_api_version]):
                raise ValueError(missing_vars_msg)
            self.gen_llm = AzureChatOpenAI(
                azure_endpoint=str(llm_endpoint),
                api_key=SecretStr(str(llm_api_key)),
                api_version=str(llm_api_version),
                azure_deployment=str(llm_deployment_name),
                temperature=0,
            )
            eval_base = f"{str(llm_endpoint).rstrip('/')}/openai/deployments/{llm_deployment_name}"

        # Initialize evaluation LLM (using RAGAS llm_factory for structured outputs)
        openai_client = OpenAI(
            api_key=str(llm_api_key),
            base_url=eval_base,
            default_headers={"api-key": str(llm_api_key)},
        )
        self.eval_llm = llm_factory(
            model=str(llm_deployment_name),
            client=openai_client,
        )

        # Initialize embeddings for RAGAS metrics using Azure
        llm_embedding_deployment_name = os.getenv("LLM_EMBEDDING_DEPLOYMENT_NAME")
        missing_embedding_msg = "Missing LLM_EMBEDDING_DEPLOYMENT_NAME"
        if not llm_embedding_deployment_name:
            raise ValueError(missing_embedding_msg)
        azure_embeddings = AzureOpenAIEmbeddings(
            azure_endpoint=str(llm_endpoint),
            api_key=SecretStr(str(llm_api_key)),
            api_version=str(llm_api_version),
            azure_deployment=str(llm_embedding_deployment_name),
        )
        self.embeddings = LangchainEmbeddingsWrapper(azure_embeddings)

        logger.info("Initialized RAGAS LLM evaluator")

    @staticmethod
    def _setup_retriever() -> SimpleProductRetriever:
        """Set up the SimpleProductRetriever."""
        # Load products data
        products_file = Path("src/rag/products.json")
        with products_file.open(encoding="utf-8") as f:
            products_data = __import__("json").load(f)

        documents = [create_product_document(product) for product in products_data]
        return SimpleProductRetriever(documents, k=5)

    @staticmethod
    def _setup_vector_db() -> Any:
        """Set up vector database if available."""
        try:
            return create_vector_database()
        except (RuntimeError, OSError) as e:
            logger.warning("Vector database not available: %s", e)
            return None

    async def retrieve_contexts(self, dataset: Dataset) -> list[list[str]]:
        """
        Retrieve contexts for all questions in the dataset.

        Args:
            dataset: Dataset with questions

        Returns:
            List of context lists, one per question
        """
        contexts_list = []

        for sample in dataset:
            question = sample["question"]

            try:
                if self.vector_db:
                    results = await self.vector_db.search(question, limit=2)
                    contexts = [
                        self.vector_db.format_products([product]) for product in results
                    ]
                else:
                    docs = await self.retriever.ainvoke(question)
                    contexts = [doc.page_content for doc in docs]

                contexts_list.append(contexts)
                logger.info(
                    "Retrieved %d contexts for: '%s...'", len(contexts), question[:50]
                )

            except Exception:
                logger.exception("Failed to retrieve contexts for '%s'", question)
                contexts_list.append([])

        return contexts_list

    async def generate_answers(self, dataset: Dataset) -> list[str]:
        """
        Generate answers for each question using retrieved contexts.

        Args:
            dataset: Dataset with questions and contexts

        Returns:
            List of generated answers
        """
        answers = []

        for sample in dataset:
            question = sample["question"]
            contexts = sample["contexts"]

            if not contexts:
                answers.append(
                    "I don't have enough information to answer this question."
                )
                continue

            prompt = (
                "You are a helpful shopping assistant for an online fashion store.\n\n"
                "Answer the question using ONLY the information from the provided context.\n"
                "If the information needed to answer the question is not present in the context, "
                'say "I don\'t have enough information to answer this question."\n\n'
                f"Context:\n{chr(10).join(f'- {ctx}' for ctx in contexts)}\n\n"
                f"Question: {question}\n\nAnswer:"
            )

            try:
                response = await self.gen_llm.ainvoke(prompt)
                content = response.content
                answer = (
                    content.strip()
                    if isinstance(content, str)
                    else str(content).strip()
                )
                answers.append(answer)
                logger.info("Generated answer for: '%s...'", question[:50])

            except Exception:
                logger.exception("Failed to generate answer for '%s'", question)
                answers.append("Error generating answer.")

        return answers

    async def evaluate_dataset(self, dataset: Dataset) -> Any:
        """
        Evaluate the dataset using RAGAS metrics.

        Args:
            dataset: Complete dataset with questions, answers, contexts, and ground truth

        Returns:
            Dictionary with evaluation results
        """
        logger.info("Starting RAGAS LLM evaluation...")

        # Define RAGAS metrics
        metrics = [
            Faithfulness(),
            AnswerRelevancy(),
        ]

        result = evaluate(
            dataset=dataset,
            metrics=metrics,
            llm=self.gen_llm,
            embeddings=self.embeddings,
        )

        logger.info("RAGAS evaluation completed")
        evaluation_result = cast(EvaluationResult, result)
        data = evaluation_result.to_pandas().to_dict()

        return dict(data)

    async def run_full_evaluation(self) -> dict[str, Any]:
        """
        Run the complete RAGAS LLM evaluation pipeline.

        Returns:
            Evaluation results dictionary
        """
        logger.info("Starting full RAGAS LLM evaluation pipeline")

        # Step 1: Create empty dataset
        dataset = build_empty_ragas_dataset()
        logger.info("Created dataset with %d test cases", len(dataset))

        # Step 2: Retrieve contexts
        contexts_list = await self.retrieve_contexts(dataset)
        dataset = build_ragas_dataset_with_contexts(contexts_list)

        # Step 3: Generate answers
        answers_list = await self.generate_answers(dataset)
        dataset = build_complete_ragas_dataset(contexts_list, answers_list)

        # Step 4: Evaluate with RAGAS
        results = await self.evaluate_dataset(dataset)
        typed_results: dict[str, Any] = dict(results)

        # Step 5: Save results
        self._save_results(typed_results)

        return typed_results

    @staticmethod
    def _save_results(
        results: dict[str, Any], filename: str = "ragas_llm_results.csv"
    ) -> None:
        """Save evaluation results to CSV."""
        try:
            evaluation_df = pd.DataFrame(results)
            output_path = Path(filename)
            evaluation_df.to_csv(output_path, index=False)
            logger.info("Results saved to %s", output_path)

            logger.info("RAGAS LLM Evaluation Summary:")
            logger.info("=" * 50)
            logger.info(evaluation_df.describe())

        except Exception:
            logger.exception("Failed to save results")


async def main() -> int:
    """Main function to run RAGAS LLM evaluation."""
    load_dotenv()

    # Set OpenAI API key for RAGAS compatibility
    os.environ["OPENAI_API_KEY"] = os.getenv("LLM_API_KEY", "")

    logger.info("Starting RAGAS LLM-based RAG Evaluation")
    logger.info("This will use LLM calls and may take several minutes...")

    try:
        evaluator = RagasLLMEvaluator()
        await evaluator.run_full_evaluation()

        logger.info("RAGAS LLM evaluation completed successfully!")
        logger.info("Results saved to ragas_llm_results.csv")

    except Exception:
        logger.exception("RAGAS LLM evaluation failed")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
