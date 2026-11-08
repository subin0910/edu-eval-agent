import streamlit as st

st.title('📘 Edu Eval Agent')
st.subheader('시험 채점부터 맞춤형 문제 생성까지')
st.markdown('**영어 시험 평가를 쉽고 신뢰성 있게**: 시험 문제지 PDF, 정답 PDF, 학생 OMR 엑셀을 업로드하면 채점과 분석을 수행합니다.')
cols = st.columns(3)
for col, (title, desc) in zip(cols, [
    ('✅ 자동 채점', '정답 PDF에서 문항별 정답·배점을 추출해 채점'),
    ('📈 성적 분석', '평균·중앙값·표준편차·오답 문항 분석 및 Excel 다운로드'),
    ('💬 AI 도우미', '성적 질의응답 및 취약 문항과 비슷한 문제 생성'),
]):
    with col:
        st.markdown(f'### {title}')
        st.write(desc)
st.info('시작하려면 왼쪽의 「채점 및 AI 분석」 페이지로 이동하세요.')
