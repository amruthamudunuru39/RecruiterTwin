"""Job-DNA for the Redrob 'Senior AI Engineer — Founding Team' JD.

This module encodes what the JD *means*, not just what it says:
- must-have concept groups (evidence must appear in career-history text,
  not merely in the skills list — that's the keyword-stuffer trap)
- explicit disqualifiers (research-only, consulting-only, LangChain-only,
  CV/speech-only, title-chasers)
- logistics preferences (location, notice period, experience band)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Concept lexicons. Matched (lowercased substring) against career-history
# descriptions + summary + headline. Each group is one "must-have" axis.
# ---------------------------------------------------------------------------

MUST_HAVE_CONCEPTS: dict[str, list[str]] = {
    # Production embeddings-based retrieval
    "embeddings_retrieval": [
        "embedding", "semantic search", "dense retrieval", "sentence-transformer",
        "sentence transformer", "bge", " e5", "retrieval system", "retrieval pipeline",
        "vector search", "retrieval-augmented", "rag pipeline", "rag system",
        "two-tower", "bi-encoder", "cross-encoder", "ann index", "approximate nearest",
    ],
    # Vector DB / hybrid search infrastructure
    "vector_search_infra": [
        "pinecone", "weaviate", "qdrant", "milvus", "faiss", "opensearch",
        "elasticsearch", "elastic search", "vespa", "pgvector", "hybrid search",
        "hybrid retrieval", "bm25", "solr", "lucene", "hnsw", "ivf index",
    ],
    # Ranking / search / recommendation systems shipped to users
    "ranking_systems": [
        "ranking system", "ranking model", "ranker", "re-rank", "rerank",
        "recommendation system", "recommender", "recommendation engine",
        "search relevance", "learning-to-rank", "learning to rank", "ltr",
        "personalization", "feed ranking", "candidate retrieval", "matching engine",
        "search ranking", "query understanding", "relevance model",
    ],
    # Evaluation rigor for ranking systems
    "evaluation": [
        "ndcg", "mrr", "map@", "mean average precision", "a/b test", "ab test",
        "offline evaluation", "online evaluation", "evaluation framework",
        "eval framework", "evaluation harness", "offline metrics", "online metrics",
        "interleaving", "click model", "relevance judgment", "golden set",
        "recall@", "precision@",
    ],
    # Modern LLM depth (nice-to-have leaning must in spirit)
    "llm_depth": [
        "fine-tun", "lora", "qlora", "peft", "instruction tun", "llm",
        "large language model", "distillation", "quantization", "prompt",
        "transformer", "gpt", "bert", "t5 ", "llama",
    ],
    # Production engineering / Python
    "production_engineering": [
        "production", "deployed", "shipped", "latency", "scal", "real users",
        "throughput", "monitoring", "inference", "serving", "pipeline",
        "microservice", "api", "ci/cd", "kubernetes", "docker",
    ],
}

NICE_TO_HAVE_CONCEPTS: dict[str, list[str]] = {
    "ltr_models": ["xgboost", "lightgbm", "lambdamart", "gbdt", "catboost"],
    "hr_marketplace": [
        "recruit", "talent", "hiring", "marketplace", "job board", "ats",
        "candidate matching", "two-sided",
    ],
    "distributed_scale": [
        "distributed", "spark", "kafka", "large-scale", "billions", "millions of",
        "high-throughput", "sharding",
    ],
    "open_source": ["open source", "open-source", "oss", "maintainer", "contributor"],
}

# Domains the JD explicitly does NOT want as a primary specialty
# (CV / speech / robotics without NLP/IR exposure).
OFF_DOMAIN_TERMS = [
    "computer vision", "image classification", "object detection", "image segmentation",
    "speech recognition", "asr", "text-to-speech", "tts", "robotics", "slam",
    "autonomous driving", "lidar", "3d reconstruction", "video analytics", "ocr",
    "gans", "diffusion model", "stable diffusion",
]

NLP_IR_TERMS = [
    "nlp", "natural language", "text classification", "named entity", "ner",
    "information retrieval", "search", "retrieval", "ranking", "embedding",
    "language model", "llm", "bert", "transformer", "semantic",
]

# Consulting / pure-services firms (JD: consulting-ONLY career is out).
CONSULTING_FIRMS = [
    "tcs", "tata consultancy", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mindtree", "ltimindtree", "l&t infotech",
    "mphasis", "deloitte", "ibm consulting", "dxc", "ust global", "virtusa",
    "hexaware", "zensar", "birlasoft", "ntt data", "genpact",
]

# Research-only career markers (JD hard disqualifier when *entire* career).
RESEARCH_ORG_TERMS = [
    "university", "institute of", "research lab", "labs research", "academy",
    "iisc", "iit ", "csir", "max planck", "postdoc", "academic",
]
RESEARCH_TITLE_TERMS = [
    "research scientist", "research fellow", "phd researcher", "postdoctoral",
    "research assistant", "professor", "lecturer", "research intern",
]

# Titles that signal the candidate is not a hands-on AI/software engineer.
NON_ENGINEERING_TITLE_TERMS = [
    "marketing", "sales", "recruiter", "hr ", "human resources", "talent acquisition",
    "account manager", "business development", "customer success", "designer",
    "content writer", "operations manager", "finance", "accountant", "support engineer",
    "qa ", "quality assurance", "test engineer", "scrum master", "project manager",
    "delivery manager", "product manager",
]

ENGINEERING_TITLE_TERMS = [
    "engineer", "developer", "scientist", "architect", "ml", "ai ", "sde",
    "programmer", "technologist", "tech lead",
]

# Location logic from the JD.
PREFERRED_CITIES = ["pune", "noida"]
TIER1_INDIA_CITIES = [
    "pune", "noida", "delhi", "new delhi", "gurgaon", "gurugram", "ghaziabad",
    "faridabad", "hyderabad", "mumbai", "navi mumbai", "bengaluru", "bangalore",
    "chennai", "kolkata",
]

# Experience band from the JD ("5-9 years", ideal 6-8).
EXP_MIN, EXP_MAX = 5.0, 9.0
EXP_IDEAL_LO, EXP_IDEAL_HI = 6.0, 8.0

# Free-text query used for the TF-IDF semantic-similarity feature.
JD_QUERY_TEXT = """
Senior AI Engineer founding team. Own the intelligence layer: ranking, retrieval,
matching systems for candidate and job search. Production experience with
embeddings-based retrieval, sentence-transformers, BGE, E5, vector databases,
Pinecone, Weaviate, Qdrant, Milvus, FAISS, OpenSearch, Elasticsearch, hybrid
search, BM25, LLM re-ranking, fine-tuning, LoRA, evaluation frameworks, NDCG,
MRR, MAP, offline online A/B testing, recommendation systems shipped to real
users at product companies, strong Python, learning-to-rank XGBoost, NLP,
information retrieval, large-scale inference, search relevance.
"""
