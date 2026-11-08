"""Deterministic grading, never delegated to an LLM."""
import pandas as pd
from .answer_parser import KeyItem


def grade_students(omr: pd.DataFrame, key: dict[int, KeyItem]) -> pd.DataFrame:
    result = pd.DataFrame({'student_id': omr['student_id'].astype(str)})
    for n, item in key.items():
        col = f'Q{n:02d}'
        result[col] = omr[col].eq(item.answer).fillna(False).astype(bool)
    result['score'] = sum(result[f'Q{n:02d}'].astype(float) * item.points for n, item in key.items())
    result['correct_count'] = result[[f'Q{n:02d}' for n in key]].sum(axis=1).astype(int)
    return result
