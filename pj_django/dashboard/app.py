"""TRIPA 운영 대시보드 — 실행: pj_django 폴더에서  streamlit run dashboard/app.py"""
import os
import sys
from pathlib import Path

import django
import pandas as pd
import streamlit as st

from db import engine

# --- Django ORM 켜기 (manage.py 가 해 주던 일을 직접) ---------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # pj_django 폴더를 import 경로에
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pj_django.settings')
django.setup()

from sherpaapp.services import stats_service  # noqa: E402  (반드시 setup 뒤에)

st.set_page_config(page_title='TRIPA 운영 대시보드', page_icon='📊', layout='wide')


@st.cache_data(ttl=300)                    # 5분 동안 같은 쿼리 결과 다시 씀
def read(sql):
    return pd.read_sql(sql, engine)


st.title('TRIPA 운영 대시보드')
page = st.sidebar.radio('보기', ['한눈에', '날짜별 추이', '선호 장소', '장소별 비용'])

if page == '한눈에':
    counts = read("""
        SELECT (SELECT COUNT(*) FROM member) AS members,
               (SELECT COUNT(*) FROM travel) AS travels,
               (SELECT COUNT(*) FROM review) AS reviews,
               (SELECT COUNT(*) FROM budget_log) AS changes
    """).iloc[0]
    a, b, c, d = st.columns(4)
    a.metric('회원', int(counts['members']))
    b.metric('여행', int(counts['travels']))
    c.metric('리뷰', int(counts['reviews']))
    d.metric('예산 변경 기록', int(counts['changes']))

elif page == '날짜별 추이':
    days = st.sidebar.slider('최근 며칠', 7, 365, 180)       # 기본 몇 일을 볼지

    travels = read(f"""
        SELECT T_DAY AS day, COUNT(*) AS travels
        FROM travel
        WHERE T_DAY >= CURDATE() - INTERVAL {days} DAY
        GROUP BY T_DAY
    """)
    reviews = read(f"""
        SELECT DATE(CREATED_AT) AS day, COUNT(*) AS reviews
        FROM review
        WHERE CREATED_AT >= CURDATE() - INTERVAL {days} DAY
        GROUP BY DATE(CREATED_AT)
    """)

    # 두 표를 날짜로 합치기 (없는 날은 0)
    trend = (pd.merge(travels, reviews, on='day', how='outer')
               .fillna(0)
               .sort_values('day')
               .set_index('day'))

    st.subheader('여행 만든 날 · 리뷰 쓴 날')
    st.line_chart(trend)

    st.subheader('합계')
    st.dataframe(trend.sum().rename('합계'))

elif page == '선호 장소':
    names = stats_service.labels()
    a, b, c = st.columns(3)
    gender = a.selectbox('성별', [None, *names['gender']],
                         format_func=lambda v: '전체' if v is None else names['gender'][v])
    age = b.selectbox('나이대', [None, *names['age']],
                      format_func=lambda v: '전체' if v is None else names['age'][v])
    order = c.radio('순서', ['visits', 'reviews', 'rating'], horizontal=True,
                    format_func={'visits': '방문', 'reviews': '리뷰', 'rating': '별점'}.get)

    rows = stats_service.favorite_places(gender=gender, age_group=age, limit=10, order=order)
    st.dataframe(pd.DataFrame(rows), hide_index=True)

else:   # 장소별 비용
    rows = stats_service.place_spending(limit=10)
    if not rows:
        st.info('아직 회원이 비용을 고친 기록이 없어요')
    else:
        df = pd.DataFrame(rows).set_index('name')
        st.bar_chart(df['edited_total'])
        st.dataframe(df)
