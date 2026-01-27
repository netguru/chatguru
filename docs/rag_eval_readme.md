# RAGAS Evaluation Guide

This project includes two types of RAGAS (Retrieval-Augmented Generation Assessment) evaluations for the chatguru Agent RAG system.

## Evaluation Types

### 1. Custom RAG Evaluation (`rag-eval`)
- **Purpose**: Fast, lightweight evaluation without LLM API calls
- **Metrics**:
  - Retrieval Success Rate: Percentage of queries finding expected products
  - Context Relevance Score: Keyword matching quality
  - Retrieval Diversity Score: Variety of categories/brands
  - Average Retrieved Products: Number of results per query
- **Runtime**: ~10 seconds
- **Output**: `rag_results.json`

### 2. LLM-based RAG Evaluation (`ragas-llm-eval`)
- **Purpose**: Comprehensive evaluation using RAGAS framework with LLM calls
- **Metrics**:
  - Faithfulness: Answer consistency with context
  - Answer Relevancy: Answer relevance to question
  - Context Relevance: Context relevance to question (not enabled)
  - Context Precision: Precision of retrieved contexts (not enabled)
  - Context Recall: Recall of relevant contexts (not enabled)
- **Runtime**: ~30 seconds (for current 2 test cases)
- **Output**: `ragas_llm_results.csv`

## Usage

### Quick Custom Evaluation
```bash
make rag-eval
```

### Comprehensive LLM Evaluation
```bash
make ragas-llm-eval
```

### Interactive Dashboard
```bash
make rag-dashboard
# or
uv run streamlit run evaluation/rag_eval/streamlit_rag_eval.py
```
**Features**:
- Real-time metrics visualization
- Per-question detailed analysis
- Failure analysis with drill-down
- Side-by-side retriever vs vector DB comparison
- Metadata and interpretation guide

### With Docker Services
For full evaluation including vector database comparison:
```bash
make docker-run  # Start services in one terminal
make rag-eval  # Run evaluation in another terminal
```

## File Structure
```
evaluation/rag_eval/
├── test_rag_dataset.py              # Custom evaluation implementation
├── run_rag_eval.py          # Custom evaluation script
└── streamlit_rag_eval.py      # Interactive dashboard for results

evaluation/ragas/
├── run_ragas_llm_eval.py      # LLM-based evaluation script
└── test_ragas_dataset.py           # Dataset builder for LLM evaluation
```

## Test Dataset

The evaluation uses a curated set of 8 test questions covering:
- Product availability queries
- Price-based searches
- Category/brand questions
- Material/care instructions
- Size/color information

Test cases are defined in `evaluation/rag_eval/test_ragas_dataset.py` and should be changed rarely.

## Output Formats

### Custom Evaluation (`rag_results.json`)
```json
{
  "retriever_evaluation": {
    "retrieval_success_rate": 0.625,
    "context_relevance_score": 0.304,
    "retrieval_diversity_score": 1.0,
    "average_retrieved_products": 5.0,
    "details": [...]
  }
}
```

### LLM Evaluation (`ragas_llm_results.csv`)
CSV with columns for each metric score per test case, plus summary statistics.

## Requirements

### For Custom Evaluation
- Azure OpenAI API access
- Python dependencies (installed via `uv sync`)

### For LLM Evaluation
- Azure OpenAI API access (for evaluation LLM and system)
- Optional: Real OpenAI API key (for answer relevancy metric)

## Troubleshooting

### Import Errors
Ensure you're running from the project root and all dependencies are installed:
```bash
uv sync
```

### API Rate Limits
The LLM evaluation makes multiple API calls. If you hit rate limits, wait and retry, or reduce the number of test cases.

## Extending the Evaluation

### Adding Test Cases
Edit `evaluation/rag_eval/test_ragas_dataset.py` and add new cases to the `get_ragas_test_cases()` function.

### Custom Metrics
For the custom evaluation, modify the scoring functions in `evaluation/rag_eval/test_rag_dataset.py`.

### LLM Metrics
For LLM evaluation, add new metrics from `ragas.metrics.collections` in `evaluation/rag_eval/run_ragas_llm_eval.py`.
