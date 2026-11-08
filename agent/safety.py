"""Application boundary controls: no private data from untrusted documents.

These rules are defense in depth, not a guarantee against every injection.
"""
from __future__ import annotations
import re

_SECRET = re.compile(
    r'(?:api[ _-]?key|secret[ _-]?key|access[ _-]?token|비밀\s*키|인증\s*토큰|'
    r'환경\s*변수|\.env|secrets\.toml|system\s*prompt|developer\s*(?:prompt|message)|'
    r'시스템\s*(?:프롬프트|지침|메시지)|개발자\s*(?:지침|메시지)|'
    r'내부\s*(?:프롬프트|지침|설정|도구|tool)|'
    r'(?:어떤|무슨|연결된|사용하는|사용\s*중인)\s*(?:tool|도구)|'
    r'(?:tool|도구)\s*(?:목록|이름|구성|스키마|정의|연결)|'
    r'(?:프롬프트|지침)\s*(?:공개|출력|보여|알려|노출|뭐라고|내용|원문)|'
    r'(?:위|앞선|이전)\s*(?:명령|지침|규칙).*무시|'
    r'(?:ignore|reveal|print|dump)\s+(?:all\s+)?(?:previous|system|developer)\s+(?:instructions|prompts))',
    re.I,
)

# Knowledge we have not ingested. Broad enough to prevent fabricated personal facts.
_UNAVAILABLE = re.compile(
    r'(?:출석|결석|지각|조퇴|수업\s*(?:참여|왔|빠졌)|어제\s*수업|'
    r'출결|숙제\s*(?:했|제출|안)|과제\s*제출|상담\s*기록|'
    r'학부모|연락처|전화번호|주소|생년월일|주민등록|'
    r'(?:오늘|내일|어제)\s*(?:날씨|기온|비\s*와|미세먼지))',
    re.I,
)

GRADE_TERMS = re.compile(r'(?:학생|점수|성적|정답|오답|문제|문항|시험|평균|중앙|등수|순위|등급|배점|취약|백분위|표준편차|채점|만점)',re.I)


def protected_request(text: str) -> bool:
    return bool(_SECRET.search(text))


def unavailable_request(text: str) -> bool:
    return bool(_UNAVAILABLE.search(text))


def safe_internal_answer() -> str:
    return ('보안상 내부 지침·설정·도구 구성·인증 정보는 안내하지 않습니다. '
            '이 서비스에서는 시험 채점 결과 조회, 오답 분석, 학습 목표 설명과 유사문제 생성을 이용하실 수 있습니다.')


def safe_unavailable_answer(query: str) -> str:
    if re.search(r'날씨|기온|미세먼지',query):
        return '이 서비스에는 실시간 날씨 데이터가 연결되어 있지 않아 현재 날씨를 확인할 수 없습니다.'
    return ('현재 업로드된 자료에는 해당 정보가 없어 확인할 수 없습니다. '
            '시험 문제지·정답표·OMR 응답으로 확인할 수 있는 점수와 오답 정보는 안내해 드릴 수 있습니다.')
