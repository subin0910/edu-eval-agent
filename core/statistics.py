"""Statistical summaries for any number of students/questions."""
import pandas as pd
from .answer_parser import KeyItem


def calculate_statistics(graded: pd.DataFrame, key: dict[int, KeyItem]) -> dict:
    if graded.empty:
        raise ValueError('채점 결과에 학생이 없습니다.')
    questions = []
    for n in key:
        wrong = int((~graded[f'Q{n:02d}']).sum())
        questions.append({'number': n, 'wrong_count': wrong, 'wrong_rate': wrong / len(graded), 'correct_rate': 1 - wrong / len(graded)})
    questions.sort(key=lambda x: (-x['wrong_count'], x['number']))
    minimum = float(graded['score'].min())
    return {
        'student_count': int(len(graded)),
        'question_count': len(key),
        'max_score': sum(item.points for item in key.values()),
        'mean': float(graded['score'].mean()),
        'median': float(graded['score'].median()),
        'std': float(graded['score'].std(ddof=0)),  # population standard deviation
        'lowest_score': minimum,
        'lowest_students': graded.loc[graded['score'].eq(minimum), 'student_id'].tolist(),
        'hardest_questions': questions[:3],
        'questions': questions,
    }
