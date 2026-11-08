"""Regression tests: broken requests from actual user screenshots."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agent.request_planner import direct_plan,resolve_targets
from agent.question_generator import GenerationBatch,GeneratedProblem
from agent.question_validator import validate_batch
from agent import chatbot


def ranking_fixture():
    items=[(8,62),(23,61),(31,60),(17,58),(42,58),(40,50)]
    stats={'questions':[{'number':n,'wrong_count':c,'wrong_rate':c/120} for n,c in items]}
    key={n:object() for n,_ in items}
    return stats,key


def test_explicit_number_beats_old_context():
    p=direct_plan('40번이랑 유사한 문제 만들어줘',{'last_question':33})
    assert p.intent=='generate' and p.question_numbers==[40] and p.source=='explicit'


def test_exclude_tied_previous_ranking():
    stats,key=ranking_fixture()
    context={'last_ranking':stats['questions'][:5], 'last_question':33}
    p=direct_plan('이 중 동률 문제들을 빼고 나머지 문제들은 유사한 문제 1개씩 만들어줘',context)
    assert p.intent=='generate' and p.exclude_ties
    targets,error=resolve_targets(p,stats,context,key)
    assert not error and targets==[8,23,31]


def test_many_explicit_numbers():
    p=direct_plan('8번, 23번, 31번 각각 유사문제 하나씩',{})
    assert p.question_numbers==[8,23,31]


def test_weakness_request():
    p=direct_plan('8번 문제를 학생들이 왜 어려워했을까?',{})
    assert p.intent=='weakness' and p.question_numbers==[8]


def test_generations_have_same_targets(monkeypatch):
    stats,key=ranking_fixture()
    ctx={'last_question':33}
    def mock_generate(numbers,pdf,difficulty):
        assert numbers==[40]
        return GenerationBatch(problems=[GeneratedProblem(
            target_number=40,question_type='요약문 완성',tested_skill='요약 핵심 어휘 추론',
            learning_objective='글의 핵심 요약',suspected_difficulty='근거를 압축하는 단계',
            passage='This is a realistic fictional passage with enough content to test validation.',
            question='Choose the best answer.',options=['A','B','C','D','E'],answer_index=2,
            explanation='The summary is supported by the passage.')])
    monkeypatch.setattr(chatbot,'generate_batch',mock_generate)
    response=chatbot._generate_targets([40],b'%PDF',direct_plan('40번이랑 유사한 문제 만들어줘',ctx))
    assert '40번' in response and '33번' not in response


def test_validator_rejects_wrong_number():
    p=GeneratedProblem(target_number=33,question_type='빈칸',tested_skill='추론',learning_objective='추론',
        suspected_difficulty='문맥',passage='A long enough passage to exercise the validator without real LLM calls.',
        question='Which?',options=['a','b','c','d','e'],answer_index=1,explanation='Reason')
    accepted,errors=validate_batch(GenerationBatch(problems=[p]),[40])
    assert not accepted and errors


def test_fourth_in_ranking_can_request_details():
    stats,key=ranking_fixture()
    context={'last_ranking':stats['questions'][:5]}
    p=direct_plan('그중 네 번째 문제의 정답과 배점 알려줘',context)
    assert p.intent=='question_detail' and p.rank==4


def test_generate_from_rank_reference():
    stats,key=ranking_fixture()
    context={'last_ranking':stats['questions'][:5]}
    p=direct_plan('그중 네 번째 문제랑 비슷한 문제 하나 만들어줘',context)
    n,error=resolve_targets(p,stats,context,key)
    assert not error and n==[17]
