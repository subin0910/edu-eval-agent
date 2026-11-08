"""Deterministic-first intent and reference resolver. No invented exam facts."""
from __future__ import annotations
import re
from typing import Literal
from pydantic import BaseModel, Field

Intent = Literal['overview','lowest','student_score','student_wrong','ranking','question_detail','generate','weakness','greeting','unsupported','internal','general']

class Plan(BaseModel):
    intent: Intent = 'general'
    question_numbers: list[int] = Field(default_factory=list)
    student_id: str | None = None
    rank: int | None = None
    count: int | None = None
    source: str = 'unspecified'  # explicit, ranking, context, hardest
    exclude_ties: bool = False
    difficulty: str = 'similar'

    @property
    def question_number(self) -> int | None:
        # Compatibility with V2 callers/tests.
        return self.question_numbers[0] if self.question_numbers else None

INTERNAL = re.compile(r'(system\s*prompt|시스템\s*프롬프트|api\s*key|api\s*키|비밀\s*키|내부\s*(?:도구|설정|지침)|어떤\s*tool|연결된\s*tool|tool\s*목록|프롬프트\s*(?:공개|보여)|개발자\s*메시지|무시하고\s*.*(?:지침|명령))',re.I)
ATTEND = re.compile(r'출석|결석|지각|수업\s*(?:참여|왔|빠졌)|어제\s*수업')
STUDENT = re.compile(r'(?<!\d)(\d+)\s*(?:번\s*)?학생')
# NOTE: '40번이랑', '40번과', '40번 문제' all recognized. Students handled first.
QUESTION = re.compile(r'(?<!\d)(\d{1,3})\s*번(?!\s*학생)')
GENERATE = re.compile(r'유사|비슷|문제\s*(?:만들|생성|출제)|문항\s*(?:만들|생성|출제)|연습\s*문제|보충\s*문제|다시\s*만들')
RANKS = {'첫':1,'두':2,'둘':2,'세':3,'셋':3,'네':4,'넷':4,'다섯':5,'여섯':6,'일곱':7,'여덟':8,'아홉':9,'열':10}


def ordinal(query: str) -> int | None:
    m = re.search(r'(?<!\d)(\d+)\s*(?:번째|위)',query)
    if m: return int(m.group(1))
    for word,n in sorted(RANKS.items(),key=lambda item:-len(item[0])):
        if re.search(rf'{word}\s*번째', query): return n
    return None


def count(query: str) -> int | None:
    for pattern in (r'(?:상위|많이\s*틀린\s*(?:문항|문제))\s*(\d+)\s*(?:개|문항|문제|위)?',
                    r'(?<!\d)(\d+)\s*(?:개|문항|문제)\s*(?:만\s*)?(?:알려|뽑아|만들|생성|보여|뭐야|추천)'):
        match = re.search(pattern,query)
        if match: return int(match.group(1))
    return None


def explicit_questions(query: str, student_present: bool = False) -> list[int]:
    # Remove student mentions and rankings so they cannot become question numbers.
    cleaned = STUDENT.sub('',query)
    return list(dict.fromkeys(int(m.group(1)) for m in QUESTION.finditer(cleaned)))


def direct_plan(q: str, context: dict | None = None) -> Plan | None:
    context = context or {}
    if INTERNAL.search(q): return Plan(intent='internal')
    if ATTEND.search(q): return Plan(intent='unsupported')
    student = STUDENT.search(q)
    nums = explicit_questions(q)
    ranking_words = bool(re.search(r'많이\s*틀린|오답|정답률|오답률|어려운\s*(?:문제|문항)|순위|상위|몇\s*위',q))
    has_generation = bool(GENERATE.search(q))
    if has_generation:
        diff = 'harder' if re.search(r'더\s*어렵|난이도\s*높',q) else ('easier' if re.search(r'더\s*쉽|난이도\s*낮',q) else 'similar')
        ties = bool(re.search(r'동률|동점|같은\s*(?:오답|순위)|동순위',q) and re.search(r'제외|빼|말고',q))
        # The exact list takes precedence over any conversational state.
        if nums:
            return Plan(intent='generate', question_numbers=nums, source='explicit',difficulty=diff)
        if re.search(r'이\s*중|그\s*중|위\s*(?:문제|문항)|나머지\s*(?:문제|문항)|각각|문제들|문항들|상위\s*\d+',q):
            return Plan(intent='generate', source='ranking', exclude_ties=ties, rank=ordinal(q), count=count(q),difficulty=diff)
        if re.search(r'그\s*문제|그\s*문항|이\s*문제|해당\s*문제',q) and context.get('last_question'):
            return Plan(intent='generate', question_numbers=[int(context['last_question'])],source='context',difficulty=diff)
        return Plan(intent='generate',source='hardest',difficulty=diff)
    if student and re.search(r'틀린|오답|못\s*맞|정답\s*여부',q):
        return Plan(intent='student_wrong',student_id=student.group())
    if student and re.search(r'점수|몇\s*점|성적',q):
        return Plan(intent='student_score',student_id=student.group())
    if re.search(r'그\s*학생|해당\s*학생|그\s*친구',q) and context.get('last_student'):
        intent = 'student_wrong' if re.search(r'틀린|오답|못\s*맞',q) else 'student_score'
        return Plan(intent=intent,student_id=context['last_student'])
    if re.search(r'최저|꼴찌|성적이\s*(?:가장\s*)?(?:낮|저조)|가장\s*못\s*본',q):return Plan(intent='lowest')
    if re.search(r'평균|중앙\s*값|표준\s*편차|전체\s*성적|시험\s*개요',q):return Plan(intent='overview')
    if re.search(r'왜\s*(?:많이|틀)|어려워|어려웠|취약|학습\s*포인트|학습\s*목표|오개념|어떤\s*점',q):
        return Plan(intent='weakness',question_numbers=nums,source='explicit' if nums else 'ranking')
    if nums and re.search(r'정답|배점|몇\s*점|정보|설명',q):return Plan(intent='question_detail',question_numbers=nums,source='explicit')
    if ordinal(q) and context.get('last_ranking') and re.search(r'정답|배점|몇\s*점',q):
        return Plan(intent='question_detail', rank=ordinal(q), source='ranking')
    if re.search(r'그\s*문제|그\s*문항',q) and re.search(r'정답|배점|몇\s*점',q) and context.get('last_question'):
        return Plan(intent='question_detail',question_numbers=[int(context['last_question'])],source='context')
    if ordinal(q) and context.get('last_ranking') and re.search(r'그\s*중|번째|몇\s*위',q):
        return Plan(intent='ranking',rank=ordinal(q))
    if ranking_words:
        if nums and re.search(r'정답|배점|몇\s*점',q):return Plan(intent='question_detail',question_numbers=nums,source='explicit')
        return Plan(intent='ranking',rank=ordinal(q),count=count(q))
    if re.search(r'안녕|무슨\s*기능|어떤\s*기능|무엇을\s*할\s*수',q):return Plan(intent='greeting')
    return None


def resolve_targets(plan: Plan, stats: dict, context: dict, key: dict) -> tuple[list[int],str | None]:
    ranked = stats.get('questions',[])
    if plan.source in ('explicit','context') and plan.question_numbers:
        numbers = plan.question_numbers
    elif plan.source == 'ranking':
        snapshot = context.get('last_ranking') or []
        if not snapshot:
            return [], '앞서 조회한 문항 순위 목록이 없습니다. 먼저 오답 상위 문항을 조회해 주세요.'
        numbers = [int(x['number']) for x in snapshot]
        if plan.rank is not None:
            if not 1 <= plan.rank <= len(numbers):
                return [], f'이전 순위 목록에서 {plan.rank}번째 문항을 찾을 수 없습니다.'
            numbers = [numbers[plan.rank - 1]]
        if plan.exclude_ties:
            counts = [int(x['wrong_count']) for x in snapshot]
            eligible = [int(x['number']) for x in snapshot if counts.count(int(x['wrong_count'])) == 1]
            numbers = [n for n in numbers if n in eligible]
        if plan.count:
            numbers = numbers[:plan.count]
    elif plan.source == 'hardest':
        numbers = [int(ranked[0]['number'])] if ranked else []
    else:
        numbers = plan.question_numbers
    unknown = [n for n in numbers if n not in key]
    if unknown: return [], f'현재 시험 정답표에 없는 문항 번호: {unknown}'
    if not numbers: return [], '요청 조건에 해당하는 문항이 없습니다.'
    # Avoid silently ignoring large requests; UI can ask to split the request.
    if len(numbers) > 5: return [], f'{len(numbers)}개 문항을 요청했습니다. 한 번에 최대 5개까지 생성할 수 있으니 범위를 나누어 요청해 주세요.'
    return numbers,None
