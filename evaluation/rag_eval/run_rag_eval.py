"""Script to run Rag evaluation for the chatguru Agent RAG system."""

import asyncio

from src.config import get_logger

from evaluation.rag_eval.test_rag_dataset import RagEvaluator

logger = get_logger("rag_eval_script")


async def main() -> int:
    evaluator = RagEvaluator()
    logger.info("Starting Rag evaluation for chatguru Agent RAG system")
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


if __name__ == "__main__":
    exit_code = asyncio.run(main())
