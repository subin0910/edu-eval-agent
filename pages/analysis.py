"""Streamlit analysis page; grades and conversation are isolated per browser session."""
from __future__ import annotations

import hashlib
import time

import pandas as pd
import streamlit as st

from core.answer_parser import parse_answer_pdf
from core.omr_parser import parse_omr_excel
from core.grading import grade_students
from core.statistics import calculate_statistics
from core.excel_export import export_excel
from agent.chatbot import reply

st.title('📊 자동 채점 및 AI 평가 도우미')
st.caption('정확한 채점은 Python이 수행하고, AI는 자유로운 질문 해석과 유사문제 생성에 사용됩니다.')

with st.sidebar:
    st.header('시험 자료')
    question_upload = st.file_uploader('문제지 PDF', type='pdf', key='question_file')
    answer_upload = st.file_uploader('정답·배점 PDF', type='pdf', key='answer_file')
    omr_upload = st.file_uploader('학생 OMR Excel', type='xlsx', key='omr_file')
    ready = all([question_upload, answer_upload, omr_upload])
    run = st.button('🚀 분석 시작', type='primary', disabled=not ready, use_container_width=True)

blobs = [f.getvalue() if f else b'' for f in (question_upload, answer_upload, omr_upload)]
signature = hashlib.sha256(b''.join(hashlib.sha256(x).digest() for x in blobs)).hexdigest()
if st.session_state.get('upload_signature') != signature:
    for name in ('analysis_result', 'messages', 'chat_context'):
        st.session_state.pop(name, None)
    st.session_state['upload_signature'] = signature

if run:
    try:
        with st.spinner('정답 PDF 추출 및 OMR 채점 중...'):
            key = parse_answer_pdf(blobs[1])
            omr = parse_omr_excel(blobs[2], list(key))
            graded = grade_students(omr, key)
            stats = calculate_statistics(graded, key)
            report = export_excel(graded, stats, key)
            st.session_state['analysis_result'] = {
                'key': key, 'graded': graded, 'stats': stats,
                'excel': report, 'pdf': blobs[0]
            }
            st.session_state['messages'] = []
            st.session_state['chat_context'] = {}
        st.success(f"{stats['student_count']}명 · {stats['question_count']}문항 채점을 완료했습니다.")
    except Exception as exc:
        st.error(f'입력 확인 또는 채점 중 오류가 발생했습니다: {exc}')

if 'analysis_result' not in st.session_state:
    st.info('문제지·정답지·OMR 파일을 업로드하고 분석 시작을 클릭해 주세요.')
    st.stop()

result = st.session_state['analysis_result']
key, graded, stats = result['key'], result['graded'], result['stats']

st.subheader('📈 성적 요약')
c1, c2, c3, c4 = st.columns(4)
c1.metric('평균', f"{stats['mean']:.2f}점")
c2.metric('중앙값', f"{stats['median']:.2f}점")
c3.metric('표준편차 (모집단)', f"{stats['std']:.2f}")
c4.metric('학생 수', f"{stats['student_count']}명")
st.write('오답 상위 문항: ' + ', '.join(f"{x['number']}번 ({x['wrong_count']}명)" for x in stats['questions'][:3]))

with st.expander('정답 PDF 추출 내용 확인'):
    st.dataframe(pd.DataFrame([{'문항': n, '정답': v.answer, '배점': v.points}
                               for n, v in key.items()]), hide_index=True, use_container_width=True)
with st.expander('학생별 채점 결과'):
    st.dataframe(graded, hide_index=True, use_container_width=True)
with st.expander('문항별 오답 순위 (전체)'):
    st.dataframe(pd.DataFrame([{'순위': i, '문항': x['number'], '오답 학생 수': x['wrong_count'],
                               '오답률': f"{x['wrong_rate']:.1%}"}
                              for i, x in enumerate(stats['questions'], 1)]),
                 hide_index=True, use_container_width=True)

st.download_button('📥 채점 결과 Excel 다운로드', data=result['excel'],
                   file_name='exam_grade_report.xlsx',
                   mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                   use_container_width=True)
st.divider()
st.subheader('💬 AI 평가 도우미')
st.caption('예: 오답률 4위 문항은? · 그 문제 몇 점이야? · 28번과 유사한 문제 생성 · 900학생의 오답은?')

messages = st.session_state.setdefault('messages', [])
for msg in messages:
    with st.chat_message(msg['role']):
        st.markdown(msg['content'])

if prompt := st.chat_input('질문을 입력해 주세요'):
    with st.chat_message('user'):
        st.markdown(prompt)
    with st.chat_message('assistant'):
        with st.spinner('분석 중...'):
            start = time.perf_counter()
            answer, context = reply(prompt, graded, stats, key, result['pdf'],
                                    messages, st.session_state.get('chat_context'))
            elapsed = time.perf_counter() - start
            st.markdown(answer)
            st.caption(f'응답 시간: {elapsed:.2f}초' + (' · 20초 초과 주의' if elapsed > 20 else ''))
    st.session_state['chat_context'] = context
    messages.extend([{'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': answer}])
