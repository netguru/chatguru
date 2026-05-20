import json
import re
from pathlib import Path
from typing import Any, cast

import pandas as pd
from datasets import Dataset
from httpx import ConnectError

from src.config import get_logger
from src.rag.documents import create_product_document
from src.rag.simple_retriever import SimpleProductRetriever
from src.vector_db import VectorDatabase, create_vector_database

MIN_WORD_LENGTH = 2

logger = get_logger("rag_eval")


class RagEvaluator:

    def __init__(self, products_file: Path | str = "src/rag/products.json") -> None:
        """
        Initialize the Rag evaluator.

        Args:
            products_file: Path to the products JSON file
        """
        self.products_file = Path(products_file)
        self.products_data = self._load_products()
        self.retriever = self._setup_retriever()
        self.vector_db = RagEvaluator._setup_vector_db()

    @staticmethod
    def _setup_vector_db() -> VectorDatabase | None:
        """Set up the vector database, returning None if not available."""
        try:
            return create_vector_database()
        except (ConnectError, RuntimeError) as exc:
            logger.warning("Vector database not available: %s", exc)
            return None

    def _load_products(self) -> list[dict[str, Any]]:
        """Load products data from JSON file."""
        with Path(self.products_file).open(encoding="utf-8") as f:
            data = json.load(f)
            return cast(list[dict[str, Any]], data)

    def _setup_retriever(self) -> SimpleProductRetriever:
        """Set up the SimpleProductRetriever for evaluation."""
        documents = [
            create_product_document(cast(Any, product))
            for product in self.products_data
        ]
        return SimpleProductRetriever(
            documents, k=3
        )  # Change k here for different number of results

    async def generate_test_dataset(self) -> Dataset:
        """
        Generate a test dataset for Rag evaluation.

        This creates a dataset with questions, ground truth answers, and retrieved contexts
        based on the products data.

        Returns:
            HuggingFace Dataset ready for Rag evaluation
        """
        test_samples = []

        # Sample test cases covering different product categories and scenarios
        test_cases = [
            {
                "question": "What are some affordable t-shirts under $30?",
                "ground_truth": "We have the Classic Crewneck T-Shirt for $25.00 in White, Black, and Navy colors.",
                "product_ids": ["1001"],
            },
            {
                "question": "Do you have any denim jeans?",
                "ground_truth": "Yes, we have Slim-Fit Selvedge Denim Jeans for $95.99 in Dark Indigo and Black.",
                "product_ids": ["1002"],
            },
            {
                "question": "What cashmere sweaters do you carry?",
                "ground_truth": "We offer the Cashmere Blend Turtleneck Sweater for $149.90 in Camel, Charcoal Gray, and Forest Green.",
                "product_ids": ["1003"],
            },
            {
                "question": "Tell me about waterproof jackets",
                "ground_truth": "We have the Waterproof Trench Coat for $189.00 in Beige and Stone colors.",
                "product_ids": ["1004"],
            },
            {
                "question": "What brands do you carry for knitwear?",
                "ground_truth": "We carry Luxe Knit for our knitwear collection, offering the Cashmere Blend Turtleneck Sweater.",
                "product_ids": ["1003"],
            },
            {
                "question": "Do you have any cotton clothing?",
                "ground_truth": "Yes, our Classic Crewneck T-Shirt is made of 100% Cotton.",
                "product_ids": ["1001"],
            },
            {
                "question": "What sizes are available for jeans?",
                "ground_truth": "The Slim-Fit Selvedge Denim Jeans are available in sizes: 28/30, 30/32, 32/32, 34/34, 36/34.",
                "product_ids": ["1002"],
            },
            {
                "question": "What care instructions do you have for wool items?",
                "ground_truth": "For our Cashmere Blend Turtleneck Sweater (70% Wool, 30% Cashmere), "
                "the care instructions are: Hand wash cold or dry clean only.",
                "product_ids": ["1003"],
            },
        ]

        for test_case in test_cases:
            # Get retrieved contexts using the retriever
            retrieved_docs = await self.retriever.ainvoke(str(test_case["question"]))
            contexts = [doc.page_content for doc in retrieved_docs]

            # Also get results from vector database for comparison
            vector_contexts = []
            if self.vector_db:
                try:
                    vector_results = await self.vector_db.search(
                        test_case["question"], limit=3
                    )  # Change limit here
                    vector_contexts = [
                        self.vector_db.format_products([product])
                        for product in vector_results
                    ]
                except (ConnectError, RuntimeError) as exc:
                    logger.warning("Vector DB search failed: %s", exc)
            else:
                logger.info("Vector database not available, skipping vector search")

            test_samples.append(
                {
                    "question": test_case["question"],
                    "ground_truth": test_case["ground_truth"],
                    "contexts": contexts,
                    "vector_contexts": vector_contexts,
                    "product_ids": test_case["product_ids"],
                }
            )

        return Dataset.from_pandas(pd.DataFrame(test_samples))

    async def evaluate_retriever(
        self, dataset: Dataset | None = None
    ) -> dict[str, Any]:
        """
        Evaluate the retriever using custom metrics (no LLM calls required).

        This performs a lightweight evaluation focusing on:
        - Retrieval success rate (whether expected products are retrieved)
        - Context relevance (whether retrieved products match query intent)
        - Retrieval diversity (variety of products returned)

        Args:
            dataset: Optional pre-generated dataset. If None, generates a new one.

        Returns:
            Dictionary with evaluation results
        """
        if dataset is None:
            dataset = await self.generate_test_dataset()

        logger.info(
            "Starting custom retrieval evaluation with %d samples", len(dataset)
        )

        results: dict[str, Any] = {
            "retrieval_success_rate": 0.0,
            "context_relevance_score": 0.0,
            "retrieval_diversity_score": 0.0,
            "average_retrieved_products": 0.0,
            "details": [],
        }

        total_samples = len(dataset)
        successful_retrievals = 0.0
        total_relevance_score = 0.0
        total_diversity_score = 0.0
        total_products_retrieved = 0

        for sample in dataset:
            question = sample["question"]
            contexts = sample["contexts"]
            expected_product_ids = sample["product_ids"]

            num_retrieved = len(contexts)
            total_products_retrieved += num_retrieved

            expected_product_names = []
            for pid in expected_product_ids:
                for product in self.products_data:
                    if product["id"] == pid:
                        expected_product_names.append(product["name"].lower())
                        break

            retrieved_success = 0.0
            for expected_name in expected_product_names:
                if any(expected_name in context.lower() for context in contexts):
                    retrieved_success = 1.0
                    break
            successful_retrievals += retrieved_success

            # Calculate context relevance (simple keyword matching)
            relevance_score = RagEvaluator._calculate_relevance_score(
                question, contexts
            )
            total_relevance_score += relevance_score

            # Calculate diversity score (number of unique categories/brands)
            diversity_score = self._calculate_diversity_score(contexts)
            total_diversity_score += diversity_score

            results["details"].append(
                {
                    "question": question,
                    "retrieval_success": retrieved_success,
                    "relevance_score": relevance_score,
                    "diversity_score": diversity_score,
                    "products_retrieved": num_retrieved,
                    "expected_product_ids": expected_product_ids,
                    "expected_product_names": expected_product_names,
                }
            )

        results["retrieval_success_rate"] = successful_retrievals / total_samples
        results["context_relevance_score"] = total_relevance_score / total_samples
        results["retrieval_diversity_score"] = total_diversity_score / total_samples
        results["average_retrieved_products"] = total_products_retrieved / total_samples

        logger.info("Custom retrieval evaluation completed")
        return results

    @staticmethod
    def _calculate_relevance_score(question: str, contexts: list[str]) -> float:
        """
        Calculate relevance score based on keyword matching between question and contexts.

        Args:
            question: The search question
            contexts: Retrieved product contexts

        Returns:
            Relevance score between 0.0 and 1.0
        """
        if not contexts:
            return 0.0

        question_lower = question.lower()

        stop_words = {
            "what",
            "are",
            "some",
            "do",
            "you",
            "have",
            "tell",
            "me",
            "about",
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
        }
        key_terms = [
            word
            for word in question_lower.split()
            if word not in stop_words and len(word) > MIN_WORD_LENGTH
        ]

        if not key_terms:
            return 0.5

        total_score = 0.0
        for context in contexts:
            context_lower = context.lower()
            matches = sum(1 for term in key_terms if term in context_lower)
            context_score = matches / len(key_terms)
            total_score += context_score

        return min(total_score / len(contexts), 1.0)

    @staticmethod
    def _calculate_diversity_score(contexts: list[str]) -> float:
        """
        Calculate diversity score based on variety of categories and brands.

        Args:
            contexts: Retrieved product contexts

        Returns:
            Diversity score between 0.0 and 1.0
        """
        if not contexts:
            return 0.0

        categories = set()
        brands = set()

        for context in contexts:
            category_match = re.search(r"Category: ([^\n]+)", context)
            brand_match = re.search(r"Brand: ([^\n]+)", context)

            if category_match:
                categories.add(category_match.group(1).strip())
            if brand_match:
                brands.add(brand_match.group(1).strip())

        # Diversity score based on unique categories and brands
        max_diversity = 2.0  # Max score for having both category and brand diversity
        diversity_score = (len(categories) + len(brands)) / max_diversity

        return min(diversity_score, 1.0)

    async def evaluate_vector_db(  # noqa: PLR0914
        self, dataset: Dataset | None = None
    ) -> dict[str, Any]:
        """
        Evaluate the vector database search using custom metrics.

        This performs the same evaluation as evaluate_retriever but for vector DB results.
        Only runs if vector database is available and has results.

        Args:
            dataset: Optional pre-generated dataset. If None, generates a new one.

        Returns:
            Dictionary with evaluation results (empty if vector DB not available)
        """
        if dataset is None:
            dataset = await self.generate_test_dataset()

        vector_samples = [
            {
                "question": sample["question"],
                "contexts": sample["vector_contexts"],
                "ground_truth": sample["ground_truth"],
                "product_ids": sample["product_ids"],
            }
            for sample in dataset
            if sample.get("vector_contexts")
        ]

        if not vector_samples:
            logger.warning("No vector database results available for evaluation")
            return {}

        logger.info(
            "Starting vector DB evaluation with %d samples", len(vector_samples)
        )

        results: dict[str, Any] = {
            "retrieval_success_rate": 0.0,
            "context_relevance_score": 0.0,
            "retrieval_diversity_score": 0.0,
            "average_retrieved_products": 0.0,
            "details": [],
        }

        total_samples = len(vector_samples)
        successful_retrievals = 0.0
        total_relevance_score = 0.0
        total_diversity_score = 0.0
        total_products_retrieved = 0

        for sample in vector_samples:
            question = sample["question"]
            contexts = sample["contexts"]
            expected_product_ids = sample["product_ids"]

            num_retrieved = len(contexts)
            total_products_retrieved += num_retrieved

            expected_product_names = []
            for pid in expected_product_ids:
                for product in self.products_data:
                    if product["id"] == pid:
                        expected_product_names.append(product["name"].lower())
                        break

            retrieved_success = 0.0
            for expected_name in expected_product_names:
                if any(expected_name in context.lower() for context in contexts):
                    retrieved_success = 1.0
                    break
            successful_retrievals += retrieved_success

            # Calculate context relevance
            relevance_score = self._calculate_relevance_score(question, contexts)
            total_relevance_score += relevance_score

            # Calculate diversity score
            diversity_score = self._calculate_diversity_score(contexts)
            total_diversity_score += diversity_score

            results["details"].append(
                {
                    "question": question,
                    "retrieval_success": retrieved_success,
                    "relevance_score": relevance_score,
                    "diversity_score": diversity_score,
                    "products_retrieved": num_retrieved,
                    "expected_product_ids": expected_product_ids,
                    "expected_product_names": expected_product_names,
                }
            )

        results["retrieval_success_rate"] = successful_retrievals / total_samples
        results["context_relevance_score"] = total_relevance_score / total_samples
        results["retrieval_diversity_score"] = total_diversity_score / total_samples
        results["average_retrieved_products"] = total_products_retrieved / total_samples

        logger.info("Vector DB evaluation completed")
        return results

    def save_evaluation_results(  # noqa: PLR6301
        self, results: dict[str, Any], filename: str = "rag_results.json"
    ) -> None:
        """
        Save evaluation results to a JSON file.

        Args:
            results: Evaluation results dictionary
            filename: Output filename
        """
        output_path = Path(filename)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info("Evaluation results saved to %s", output_path)

    async def run_full_evaluation(self) -> dict[str, Any]:
        """
        Run a complete evaluation of both retriever and vector database.

        Returns:
            Dictionary with all evaluation results
        """
        logger.info("Starting full RAG evaluation")

        # Generate test dataset
        dataset = await self.generate_test_dataset()

        # Evaluate retriever
        retriever_results = await self.evaluate_retriever(dataset)

        # Evaluate vector database
        vector_results = await self.evaluate_vector_db(dataset)

        # Combine results
        full_results = {
            "retriever_evaluation": retriever_results,
            "vector_db_evaluation": vector_results,
            "metadata": {
                "total_products": len(self.products_data),
                "test_samples": len(dataset),
                "evaluation_timestamp": pd.Timestamp.now().isoformat(),
            },
        }

        # Save results
        self.save_evaluation_results(full_results)

        logger.info("Full evaluation completed")
        return full_results


async def main() -> int:
    """Main function to run Rag evaluation."""
    evaluator = RagEvaluator()

    logger.info("Starting RAG evaluation for chatguru Agent RAG system")
    logger.info("Loaded %d products from database", len(evaluator.products_data))

    try:
        results = await evaluator.run_full_evaluation()

        logger.info("Evaluation Results Summary:")
        logger.info("=" * 50)

        if results.get("retriever_evaluation"):
            retriever_scores = results["retriever_evaluation"]
            logger.info("Retriever Evaluation:")
            for metric, score in retriever_scores.items():
                if isinstance(score, (int | float)):
                    logger.info("  %s: %.3f", metric, score)

        if results.get("vector_db_evaluation"):
            vector_scores = results["vector_db_evaluation"]
            logger.info("Vector Database Evaluation:")
            for metric, score in vector_scores.items():
                if isinstance(score, (int | float)):
                    logger.info("  %s: %.3f", metric, score)

        logger.info("Results saved to rag_results.json")
        logger.info("Metadata:")
        logger.info(
            "   • Products evaluated: %d", results["metadata"]["total_products"]
        )
        logger.info("   • Test samples: %d", results["metadata"]["test_samples"])
        logger.info(
            "   • Evaluation time: %s", results["metadata"]["evaluation_timestamp"]
        )

    except Exception:
        logger.exception("Evaluation failed")
        return 1

    return 0
