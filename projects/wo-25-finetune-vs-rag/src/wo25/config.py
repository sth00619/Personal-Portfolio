"""Pinned datasets, model, and experiment controls."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_ROOT / "raw"
PROCESSED_DATA_DIR = DATA_ROOT / "processed"
DATA_CACHE_DIR = DATA_ROOT / "cache"
MODEL_DIR = PROJECT_ROOT / "models" / "qwen2.5-1.5b-instruct-4bit"
ARTIFACT_DIR = PROJECT_ROOT / "artifacts"
GENERATION_DIR = ARTIFACT_DIR / "generations"
ADAPTER_DIR = ARTIFACT_DIR / "adapters"
RESULTS_DIR = PROJECT_ROOT / "results"

GSM8K_REPO = "openai/gsm8k"
GSM8K_REVISION = "740312add88f781978c0658806c59bc2815b9866"
GSM8K_TRAIN_FILE = "main/train-00000-of-00001.parquet"
GSM8K_TEST_FILE = "main/test-00000-of-00001.parquet"
MMLU_REPO = "cais/mmlu"
MMLU_REVISION = "c30699e8356da336a370243923dbaf21066bb9fe"
MMLU_TEST_FILE = "all/test-00000-of-00001.parquet"
MMLU_DEV_FILE = "all/dev-00000-of-00001.parquet"
MMLU_SUBJECTS = (
    "astronomy",
    "business_ethics",
    "college_computer_science",
    "elementary_mathematics",
    "global_facts",
    "high_school_biology",
    "high_school_mathematics",
    "medical_genetics",
    "security_studies",
    "world_religions",
)
BASE_MODEL_REPO = "Qwen/Qwen2.5-1.5B-Instruct"
BASE_MODEL_REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
MODEL_LICENSE = "Apache-2.0"
DATASET_LICENSE = "MIT"

RANDOM_SEED = 2507
GSM8K_TEST_SIZE = 1319
GSM8K_TRAIN_SIZE = 7473
VALIDATION_SIZE = 200
MMLU_SAMPLE_SIZE = 100
MMLU_PER_SUBJECT = 10
FEW_SHOT_COUNTS = (3, 5)
RAG_TOP_K_VALUES = (3, 5)
LORA_RANK_VALUES = (4, 8)
LORA_TRAIN_SAMPLE_SIZES = (256, 1024)
LORA_TUNE_STEPS = 100
LORA_FINAL_STEPS = 600
LORA_LAYERS = 8
LORA_BATCH_SIZE = 1
LORA_MAX_SEQUENCE_LENGTH = 1024
LORA_LEARNING_RATE = 1e-5
LORA_DROPOUT = 0.05
LORA_VALIDATION_BATCHES = 25
MODEL_MAX_TOKENS = 256
QUANTIZATION_BITS = 4

