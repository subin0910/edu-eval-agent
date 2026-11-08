"""Deterministic checks; semantic validity still requires instructor review."""
from __future__ import annotations
import re
from .question_generator import GenerationBatch,GeneratedProblem


def validate_batch(result: GenerationBatch, targets: list[int]) -> tuple[list[GeneratedProblem],list[str]]:
    accepted=[]; errors=[]; by_number={}
    for p in result.problems:
        by_number.setdefault(p.target_number,[]).append(p)
    extras=[k for k in by_number if k not in targets]
    if extras: errors.append(f'요청하지 않은 문항 번호가 생성되었습니다: {extras}')
    for number in targets:
        items=by_number.get(number,[])
        if len(items)!=1:
            errors.append(f'{number}번: 생성된 문제가 {len(items)}개여서 제외했습니다.')
            continue
        p=items[0]
        if p.limitation.strip():
            errors.append(f'{number}번: 생성 제한 — {p.limitation.strip()}')
            continue
        if len(p.options)!=5 or not 1<=p.answer_index<=5:
            errors.append(f'{number}번: 선택지는 5개, 정답 번호는 1~5여야 합니다.')
            continue
        if any(not isinstance(x,str) or not x.strip() for x in p.options):
            errors.append(f'{number}번: 빈 선택지가 있습니다.')
            continue
        if len(set(re.sub(r'\s+','',x).lower() for x in p.options))!=5:
            errors.append(f'{number}번: 중복 선택지가 있습니다.')
            continue
        fields=(p.passage,p.question,p.explanation,p.question_type,p.tested_skill,p.learning_objective,p.suspected_difficulty)
        if any(not v.strip() for v in fields):
            errors.append(f'{number}번: 필수 학습 정보가 누락되었습니다.')
            continue
        # Reject obviously too-short artifacts; not a substitute for semantic review.
        if len(p.passage.strip())<45:
            errors.append(f'{number}번: 지문/문항 내용이 지나치게 짧습니다.')
            continue
        accepted.append(p)
    return accepted,errors


def render_problem(p: GeneratedProblem) -> str:
    opts='\n'.join(f'{i}. {x}' for i,x in enumerate(p.options,1))
    return (f'### {p.target_number}번 학습 목표 기반 유사문제\n\n'
            f'**유형:** {p.question_type}  \n**훈련 능력:** {p.tested_skill}  \n**학습 목표:** {p.learning_objective}\n\n'
            f'{p.passage}\n\n**{p.question}**\n\n{opts}\n\n'
            f'**정답: {p.answer_index}번**\n\n**해설:** {p.explanation}\n\n'
            f'**학생들이 어려워했을 수 있는 점(가설):** {p.suspected_difficulty}\n\n'
            '_위 어려움은 학생별 오개념 확정이 아닙니다. 생성 문제는 수업·인쇄 전 교사의 정답 및 표현 검토가 필요합니다._')
