
"""Create deterministic development and test splits for evaluation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_PATTERN = str(REPO_ROOT / "data" / "eval" / "questions_p*.jsonl")
DEFAULT_DEV = REPO_ROOT / "data" / "eval" / "questions_dev.jsonl"
DEFAULT_TEST = REPO_ROOT / "data" / "eval" / "questions_test.jsonl"


def is_test_question(question_id: str) -> bool:
    """Assign questions to test using the professor's deterministic rule."""
    digest = hashlib.md5(str(question_id).encode("utf-8")).hexdigest()
    return int(digest, 16) % 10 < 3


def split_questions(
    questions: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split questions deterministically using their stable IDs."""
    dev = []
    test = []
    seen_ids = set()

    for question in questions:
        question_id = question.get("id", question.get("question_id"))

        if question_id is None or str(question_id).strip() == "":
            raise ValueError(f"Question has no valid ID: {question}")

        question_id = str(question_id)

        if question_id in seen_ids:
            raise ValueError(f"Duplicate question ID found: {question_id}")

        seen_ids.add(question_id)

        if is_test_question(question_id):
            test.append(question)
        else:
            dev.append(question)

    return dev, test


def load_questions(pattern: str) -> list[dict]:
    """Load questions from all files matching the input glob pattern."""
    import glob

    files = sorted(glob.glob(pattern))

    if not files:
        raise FileNotFoundError(f"No question files matched: {pattern}")

    questions = []

    for filename in files:
        file_path = Path(filename)

        with file_path.open("r", encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue

                try:
                    question = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"Invalid JSON in {file_path}, line {line_number}"
                    ) from exc

                if not isinstance(question, dict):
                    raise ValueError(
                        f"Expected a JSON object in {file_path}, "
                        f"line {line_number}"
                    )

                questions.append(question)

    return questions


def write_jsonl(path: Path, questions: list[dict]) -> None:
    """Write questions to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for question in questions:
            file.write(json.dumps(question, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create deterministic development and test splits."
    )
    parser.add_argument("--input", default=DEFAULT_PATTERN)
    parser.add_argument("--dev", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--test", type=Path, default=DEFAULT_TEST)

    args = parser.parse_args()

    questions = load_questions(args.input)
    dev, test = split_questions(questions)

    if not questions:
        raise ValueError("The input question files contain no questions.")

    write_jsonl(args.dev, dev)
    write_jsonl(args.test, test)

    total = len(questions)

    print(f"Total questions: {total}")
    print(f"Development: {len(dev)} ({len(dev) / total * 100:.1f}%)")
    print(f"Test: {len(test)} ({len(test) / total * 100:.1f}%)")
    print(f"Development file: {args.dev}")
    print(f"Test file: {args.test}")


if __name__ == "__main__":
    main()
