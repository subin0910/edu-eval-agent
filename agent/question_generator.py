
"""Learning-objective-based generation grounded in a specific PDF question crop."""

from __future__ import annotations

import base64
import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from core.question_parser import locate_question
from .prompts import GENERATOR_PROMPT


class GeneratedProblem(BaseModel):
    target_number: int
    question_type: str
    tested_skill: str
    learning_objective: str
    suspected_difficulty: str
    passage: str
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    limitation: str = ""


class GenerationBatch(BaseModel):
    problems: list[GeneratedProblem] = Field(default_factory=list)


def model():
    from langchain_openai import ChatOpenAI

    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")

    return ChatOpenAI(
        model=os.getenv("GENERATOR_MODEL", "gpt-5.4"),
        timeout=17,
        max_retries=0,
    )


def generate_batch(
    numbers: list[int],
    question_pdf: bytes,
    difficulty: str = "similar",
) -> GenerationBatch:

    if not question_pdf:
        raise ValueError("업로드된 문제 PDF가 없습니다.")

    from langchain_core.messages import HumanMessage, SystemMessage

    content: list[dict] = [
        {
            "type": "text",
            "text": (
                f"원본 문항 번호(순서 유지)={numbers}. "
                f"목표 난이도={difficulty}. "
                "각 번호당 정확히 1문항. "
                "PDF 그림/표/선택지를 확인하고 "
                "문항의 학습 목표를 유지하여 "
                "새로운 문제를 생성하라."
            ),
        }
    ]

    for n in numbers:
        item = locate_question(question_pdf, n)

        content.extend(
            [
                {
                    "type": "text",
                    "text": (
                        f"=== 원본 {n}번, PDF {item['page']}p ===\n"
                        f"{item['text'][:8500]}"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            "data:image/png;base64,"
                            + base64.b64encode(
                                item["png_bytes"]
                            ).decode("ascii")
                        )
                    },
                },
            ]
        )

    output = (
        model()
        .with_structured_output(
            GenerationBatch,
            method="function_calling",
        )
        .invoke(
            [
                SystemMessage(content=GENERATOR_PROMPT),
                HumanMessage(content=content),
            ]
        )
    )

    return output
