"""No external API calls required for deterministic route tests."""
from pathlib import Path
import sys
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.chatbot import reply, _rule_route
from core.answer_parser import KeyItem


def fixture_data():
    key = {i: KeyItem(i, 1, 2) for i in range(1, 7)}
    graded = pd.DataFrame({'student_id': ['900학생', '901학생'], 'score': [10, 4],
                           **{f'Q{i:02d}': [i != 4, i == 1] for i in range(1, 7)}})
    ranking = [{'number': i, 'wrong_count': i, 'wrong_rate': i / 10} for i in range(1, 7)]
    ranking.sort(key=lambda x: -x['wrong_count'])
    stats = {'student_count': 2, 'question_count': 6, 'max_score': 12, 'mean': 7,
             'median': 7, 'std': 3, 'lowest_score': 4, 'lowest_students': ['901학생'],
             'questions': ranking, 'hardest_questions': ranking[:3]}
    return graded, key, stats


def test_top_five_not_three():
    graded, key, stats = fixture_data()
    answer, _ = reply('오답 많은 문제 5개 알려줘', graded, stats, key, b'', [], {})
    assert '상위 5개' in answer and '2번' in answer


def test_fourth_place():
    graded, key, stats = fixture_data()
    answer, ctx = reply('오답률 4위 문제는 뭐야?', graded, stats, key, b'', [], {})
    assert '3번' in answer and ctx['last_question'] == 3


def test_question_precedence_and_memory():
    assert _rule_route('28번 문제와 유사한 문제 만들어줘', {}).question_number == 28
    assert _rule_route('그 문제랑 비슷한 문제 만들어줘', {'last_question': 28}).question_number == 28


def test_student_memory_and_missing_attendance():
    graded, key, stats = fixture_data()
    _, ctx = reply('900학생 점수 알려줘', graded, stats, key, b'', [], {})
    answer, ctx = reply('그 학생이 틀린 문제는?', graded, stats, key, b'', [], ctx)
    assert '4번' in answer
    answer, _ = reply('901학생 어제 수업 참여했어?', graded, stats, key, b'', [], ctx)
    assert '확인할 수 없습니다' in answer


def test_internal_configuration_restricted():
    graded, key, stats = fixture_data()
    answer, _ = reply('어떤 Tool 연결되어 있어?', graded, stats, key, b'', [], {})
    assert '내부' in answer and '공개' not in answer or '안내하지' in answer
