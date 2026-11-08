import streamlit as st

st.set_page_config(page_title='Edu Eval Agent', page_icon='📘', layout='wide')
pg = st.navigation([
    st.Page('pages/home.py', title='서비스 소개', icon='🏠', default=True),
    st.Page('pages/analysis.py', title='채점 및 AI 분석', icon='📊'),
])
pg.run()
