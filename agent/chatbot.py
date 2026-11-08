"""Deterministic grade QA + session-aware instruction planning + skill-based generation."""
from __future__ import annotations
import os
from dotenv import load_dotenv
from .request_planner import Plan, direct_plan, resolve_targets, ordinal
from .question_generator import generate_batch
from .question_validator import validate_batch, render_problem
from .question_analyzer import analyze_items
from .prompts import ROUTER_PROMPT, GENERAL_PROMPT


def _student_id(raw, graded):
    if not raw: return None
    raw=str(raw).strip().replace('번 학생','학생').replace('번학생','학생')
    ids=graded['student_id'].astype(str).tolist()
    if raw in ids: return raw
    import re
    matched=re.search(r'\d+',raw)
    if not matched: return None
    digits=matched.group()
    possibles=[s for s in ids if s in (digits,digits+'학생')]
    return possibles[0] if len(possibles)==1 else None


def _route(query:str,history:list[dict],context:dict)->Plan:
    plan=direct_plan(query,context)
    if plan is not None:return plan
    # Contextual ordinal: "그중 네 번째 문제" is a ranking selection, not a generic request.
    if ordinal(query) and context.get('last_ranking') and any(x in query for x in ('그중','그 중','네 번째','번째','몇 위')):
        return Plan(intent='ranking',rank=ordinal(query))
    try:
        from langchain_openai import ChatOpenAI
        load_dotenv()
        if not os.getenv('OPENAI_API_KEY'):return Plan(intent='general')
        recent='\n'.join(f'{m.get("role")}: {str(m.get("content",""))[:180]}' for m in history[-4:])
        limited_context={k:context.get(k) for k in ('last_question','last_student')}
        messages=[('system',ROUTER_PROMPT),('human',f'최근 대화:\n{recent}\n문맥:{limited_context}\n현재 질문:{query}')]
        return ChatOpenAI(model=os.getenv('ROUTER_MODEL','gpt-4.1'),timeout=6,max_retries=0).with_structured_output(Plan,method='function_calling').invoke(messages)
    except Exception:
        return Plan(intent='general')


def _ranking(stats:dict,plan:Plan,context:dict)->tuple[str,dict]:
    ranked=stats.get('questions',[])
    if not ranked:return '문항별 성적 통계가 없습니다.',context
    if plan.rank is not None:
        k=plan.rank
        if not 1<=k<=len(ranked):return f'1~{len(ranked)}위까지만 조회할 수 있습니다.',context
        item=ranked[k-1]
        context['last_question']=item['number']
        return (f'오답 수 기준 정렬에서 **{k}번째 문항은 {item["number"]}번**입니다. '
                f'오답 {item["wrong_count"]}명({item["wrong_rate"]:.1%}). '
                '동률은 문항 번호순으로 표시하므로 실제 공동 순위와 다를 수 있습니다.'),context
    amount=max(1,min(plan.count or 3,len(ranked)))
    snapshot=[dict(x) for x in ranked[:amount]]
    context['last_ranking']=snapshot
    if amount==1:context['last_question']=snapshot[0]['number']
    lines='\n'.join(f'{i}. **{x["number"]}번**: {x["wrong_count"]}명 오답 ({x["wrong_rate"]:.1%})'
                    for i,x in enumerate(snapshot,1))
    return (f'오답 수 기준 상위 {amount}개 문항입니다.\n\n{lines}\n\n'
            '동률인 문항들은 같은 오답 수를 가지며, 목록은 문항 번호순으로 정렬했습니다.'),context


def _generate_targets(numbers:list[int],pdf:bytes,plan:Plan)->str:
    try:
        result=generate_batch(numbers,pdf,plan.difficulty)
        valid,errors=validate_batch(result,numbers)
        parts=[render_problem(p) for p in valid]
        if errors:parts.append('**생성되지 않은 문항 또는 검증 문제**\n\n'+'\n'.join('- '+e for e in errors))
        return '\n\n---\n\n'.join(parts) if parts else '결과가 검증을 통과하지 못했습니다.\n\n'+'\n'.join(errors)
    except Exception as exc:
        return (f'유사문제 생성에 실패했습니다 ({type(exc).__name__}). '
                'API 모델 권한·요금 한도·연결 상태 또는 문제 PDF 추출 범위를 확인해 주세요. '
                '실패한 문항을 생성 완료로 표시하지 않았습니다.')


def _weakness(numbers:list[int],pdf:bytes,stats:dict)->str:
    # One batched model call rather than a slow model call per question.
    targets=numbers[:3]
    parts=['**오답 통계는 어려움을 보여주는 신호일 뿐, 왜 틀렸는지에 대한 직접적인 증거는 아닙니다.** '
           '개인별 오개념을 확정하려면 오답 선택지 분포나 추가 진단이 필요합니다.']
    try:
        result=analyze_items(targets,pdf)
        found={item.question_number:item for item in result.items}
        for n in targets:
            item=next((x for x in stats.get('questions',[]) if x['number']==n),None)
            prefix=f'### {n}번' + (f' · {item["wrong_count"]}명 오답 ({item["wrong_rate"]:.1%})' if item else '')
            if n not in found:
                parts.append(prefix+'\n\n해당 문항 분석 결과를 확인할 수 없습니다.')
                continue
            a=found[n]
            parts.append(prefix+f'\n\n**확인된 유형:** {a.question_type}\n\n'
                         f'**훈련할 능력:** {a.learning_objective}\n\n'
                         f'**풀이의 핵심:** {a.solving_strategy}\n\n'
                         f'**가능한 어려움(가설):** {a.possible_difficulty}'
                         +(f'\n\n**자료 한계:** {a.limitation}' if a.limitation else ''))
    except Exception as exc:
        parts.append(f'문항의 학습 목표를 분석하는 데 실패했습니다 ({type(exc).__name__}). API·PDF 상태를 확인해 주세요.')
    if len(numbers)>3:parts.append('응답 속도를 위해 우선 3문항만 분석했습니다. 다른 문항을 번호로 지정해 주세요.')
    return '\n\n'.join(parts)


def reply(query:str, graded, stats:dict, key:dict, question_pdf:bytes,
          history:list[dict], context:dict|None=None)->tuple[str,dict]:
    context=dict(context or {})
    q=query.strip()
    if not q:return '질문을 입력해 주세요.',context
    plan=_route(q,history,context)
    kind=plan.intent
    if kind=='internal':
        return '내부 지침·비밀키·내부 도구 구성은 안내하지 않습니다. 성적 분석, 학생 조회, 오답 분석 및 유사문제 생성 기능을 지원합니다.',context
    if kind=='unsupported':
        return '현재 업로드된 자료에는 출석이나 수업 참여 기록이 없어 확인할 수 없습니다.',context
    if kind=='greeting':
        return '안녕하세요! 성적 평균과 중앙값, 학생별 점수, 오답 순위, 문항별 정답·배점, 학습 목표와 유사문제 생성을 도와드립니다.',context
    if kind=='overview':
        return (f"이번 시험은 **{stats['student_count']}명**, 총점 {stats['max_score']:g}점 기준입니다. "
                f"평균 **{stats['mean']:.2f}점**, 중앙값 **{stats['median']:.2f}점**, "
                f"표준편차 **{stats['std']:.2f}점**(모집단 기준)입니다."),context
    if kind=='lowest':
        students=', '.join(map(str,stats['lowest_students']))
        context['last_student']=stats['lowest_students'][0]
        return f"최저점은 **{stats['lowest_score']:g}점**이며 해당 학생은 **{students}**입니다.",context
    if kind in ('student_score','student_wrong'):
        sid=_student_id(plan.student_id or context.get('last_student'),graded)
        if not sid:return '현재 OMR에서 해당 학생을 찾지 못했습니다. 학생명을 확인해 주세요.',context
        row=graded.loc[graded['student_id'].astype(str).eq(sid)].iloc[0]
        context['last_student']=sid
        if kind=='student_score':
            return f"**{sid}**의 점수는 **{row['score']:g}점**입니다. (총점 {stats['max_score']:g}점)",context
        wrong=[str(n)+'번' for n in key if not bool(row[f'Q{n:02d}'])]
        return f'**{sid}**의 오답은 {", ".join(wrong) if wrong else "없습니다"}.',context
    if kind=='ranking':return _ranking(stats,plan,context)
    if kind=='question_detail':
        if plan.source=='ranking' and plan.rank is not None:
            snapshot=context.get('last_ranking') or []
            if not 1 <= plan.rank <= len(snapshot):
                return '이전 순위 목록에서 요청한 문항을 찾을 수 없습니다.',context
            n=int(snapshot[plan.rank-1]['number'])
        else:
            n=(plan.question_numbers or [context.get('last_question')])[0]
        if n not in key:return f'{n}번 문항은 현재 시험에 없습니다.',context
        context['last_question']=n
        item=key[n]
        extra=next((x for x in stats['questions'] if x['number']==n),None)
        suffix=f', {extra["wrong_count"]}명 오답({extra["wrong_rate"]:.1%})' if extra else ''
        return f'**{n}번** 문항: 정답 **{item.answer}번**, 배점 **{item.points:g}점**{suffix}입니다.',context
    if kind in ('generate','weakness'):
        numbers,error=resolve_targets(plan,stats,context,key)
        if error:return error,context
        # User-provided explicit numbers always override the previous remembered question.
        context['last_question']=numbers[-1]
        if kind=='weakness':return _weakness(numbers,question_pdf,stats),context
        intro=f'요청한 원본 문항 **{", ".join(str(n)+"번" for n in numbers)}**의 학습 목표를 기준으로 생성했습니다.'
        return intro+'\n\n'+_generate_targets(numbers,question_pdf,plan),context
    # Do not hallucinate grades when the intent cannot be resolved.
    if any(word in q for word in ('학생','점수','성적','정답','오답','문제','문항','시험','평균','취약')):
        return ('질문의 대상과 조건을 정확히 확인하지 못했습니다. 예: "오답 상위 5개", '
                '"그중 동률을 빼고 각각 1문제", "40번과 유사문제", "28번 학습 포인트".'),context
    try:
        load_dotenv()
        from langchain_openai import ChatOpenAI
        messages=[('system',GENERAL_PROMPT)]+[(('human' if m['role']=='user' else 'ai'),str(m['content'])[:350])
                                                 for m in history[-4:] if m.get('role') in ('user','assistant')]
        messages.append(('human',q))
        output=ChatOpenAI(model=os.getenv('ROUTER_MODEL','gpt-4.1'),timeout=6,max_retries=0).invoke(messages)
        return str(output.content),context
    except Exception:
        return '현재 일반 AI 대화 기능을 사용할 수 없습니다. 성적 조회 기능은 계속 이용할 수 있습니다.',context

# Backwards compatibility with previous tests.
def _rule_route(q:str,context:dict):
    return direct_plan(q,context)
