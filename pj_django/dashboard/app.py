"""TRIPA 운영 대시보드 — 실행: pj_django 폴더에서  streamlit run dashboard/app.py"""
import os
import sys
from pathlib import Path

import altair as alt
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
page = st.sidebar.radio('보기', ['한눈에', '날짜별 추이', '선호 장소', '장소별 비용', '교통수단'])

# 한눈에: (화면 이름, 표, 언제 생겼는지 칸)
METRICS = [
    ('회원', 'member', 'JOINED_AT'),
    ('여행', 'travel', 'CREATED_AT'),
    ('리뷰', 'review', 'CREATED_AT'),
    ('예산 변경 기록', 'budget_log', 'CHANGED_AT'),
]
NAMES = [name for name, _, _ in METRICS]


def monthly_table():
    """달마다 새로 생긴 수 → 행: 기간(2026-11), 열: 회원·여행·리뷰·예산 변경 기록 (없는 달은 0)"""
    frames = []
    for name, table, col in METRICS:
        df = read(f"""
            SELECT YEAR({col}) AS y, MONTH({col}) AS m, COUNT(*) AS n
            FROM {table} WHERE {col} IS NOT NULL
            GROUP BY YEAR({col}), MONTH({col})
        """)
        df['name'] = name
        frames.append(df)
    df = pd.concat(frames)
    df['period'] = pd.to_datetime(dict(year=df.y, month=df.m, day=1)).dt.to_period('M')
    table = df.pivot_table(index='period', columns='name', values='n', aggfunc='sum')
    months = pd.period_range(table.index.min(), max(table.index.max(), pd.Period.now('M')), freq='M')
    return table.reindex(index=months, columns=NAMES, fill_value=0).fillna(0).astype(int)


def change(now, before):
    """증감 글자와 색: 늘면 빨간 ▲, 줄면 파란 ▼, 같으면 회색 –"""
    diff = now - before
    mark, color = ('▲', 'red') if diff > 0 else ('▼', 'blue') if diff < 0 else ('–', 'gray')
    rate = '' if not diff else f' ({diff / before:+.0%})' if before else ' (새로)'
    return f'{mark} {abs(diff):,}{rate}', color


def mark_color(v):
    v = str(v)
    return 'color: #d33' if v.startswith('▲') else 'color: #1c6fd1' if v.startswith('▼') else 'color: gray'


if page == '한눈에':
    month = monthly_table()
    year = month.groupby(month.index.year).sum()
    year.index = year.index.astype(str)
    month.index = month.index.astype(str)

    unit = st.radio('비교', ['월별 (전달 대비)', '연도별 (작년 대비)'], horizontal=True)
    table, prev_word = (month, '전달') if unit.startswith('월') else (year, '작년')
    periods = list(table.index)
    pick = st.selectbox('기간', periods[::-1])            # 최근 기간이 맨 위
    i = periods.index(pick)
    before = table.iloc[i - 1] if i else table.iloc[i] * 0

    st.caption(f'{pick}에 새로 생긴 수 · {prev_word} 대비 증감 · 막대는 최근 12{"달" if table is month else "년"} '
               f'(이번 달·올해는 오늘까지라 적게 보일 수 있어요)')
    cols = st.columns(len(NAMES))
    for col, name in zip(cols, NAMES):
        now = int(table[name].iloc[i])
        text, color = change(now, int(before[name]))
        col.metric(name, f'{now:,}', delta=text, delta_color=color, delta_arrow='off', border=True,
                   chart_data=table[name].iloc[max(0, i - 11):i + 1].tolist(), chart_type='bar')
        col.caption(f'누적 {int(table[name].iloc[:i + 1].sum()):,}')

    # 기간별 표: 수 옆에 증감 (최근이 위)
    view = pd.DataFrame(index=table.index)
    for name in NAMES:
        view[name] = table[name]
        view[f'{name} 증감'] = [change(n, b)[0] for n, b in zip(table[name], table[name].shift(1, fill_value=0))]
    view = view.iloc[:i + 1].iloc[::-1]
    st.dataframe(view.style.map(mark_color, subset=[f"{n} 증감" for n in NAMES]),
                 height=min(420, 35 * (len(view) + 1) + 3))   # 줄이 적으면 표도 작게

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

elif page == '장소별 비용':
    rows = stats_service.place_spending(limit=10)
    if not rows:
        st.info('아직 회원이 비용을 고친 기록이 없어요')
    else:
        df = pd.DataFrame(rows).set_index('name')
        st.bar_chart(df['edited_total'])
        st.dataframe(df)

else:   # 교통수단: 여행지까지 가는 방법(access_way) · 여행지 안에서 다니는 방법(t_way)
    ACCESS = {'car': '자차', 'ktx': 'KTX', 'train_transfer': '기차 환승', 'bus': '고속버스', 'flight': '비행기',
              'ferry': '배'}
    INSIDE = {'car': '자동차·렌터카', 'public_transport': '대중교통', 'walk': '도보', 'bike': '자전거'}
    trips = read("""
        SELECT t.T_PLACE AS place, t.ACCESS_WAY AS access, LOWER(t.T_WAY) AS inside,
               m.GENDER AS gender, m.AGE_GROUP AS age
        FROM travel t JOIN member m ON m.M_ID = t.M_ID
    """)
    trips['access'] = trips['access'].map(ACCESS).fillna('정하지 않음')
    trips['inside'] = trips['inside'].map(INSIDE).fillna('정하지 않음')

    names = stats_service.labels()
    a, b, c = st.columns(3)
    places = ['전체'] + sorted(trips['place'].dropna().unique().tolist())
    place = a.selectbox('여행지', places)
    gender = b.selectbox('성별', [None, *names['gender']],
                         format_func=lambda v: '전체' if v is None else names['gender'][v])
    age = c.selectbox('나이대', [None, *names['age']],
                      format_func=lambda v: '전체' if v is None else names['age'][v])
    view = trips
    if place != '전체':
        view = view[view['place'] == place]
    if gender is not None:
        view = view[view['gender'].isna()] if gender == 'none' else view[view['gender'] == gender]
    if age is not None:
        view = view[view['age'].isna()] if age == 'none' else view[view['age'] == age]

    st.caption(f'여행 {len(view):,}개 기준 · 여행 상세에서 고른 가는 방법(데모는 seed_demo 경로)')

    def pie(col, title):
        counts = view[col].value_counts().rename_axis('수단').reset_index(name='여행 수')
        if counts.empty:
            st.info('여행이 없어요')
            return
        counts['비율'] = (counts['여행 수'] / counts['여행 수'].sum() * 100).round(1)
        chart = (alt.Chart(counts).mark_arc(innerRadius=55)
                 .encode(theta='여행 수:Q', color=alt.Color('수단:N', sort='-x', legend=alt.Legend(title=None)),
                         tooltip=['수단', '여행 수', alt.Tooltip('비율:Q', format='.1f', title='비율(%)')])
                 .properties(title=title, height=300))
        st.altair_chart(chart, width='stretch')
        st.dataframe(counts, hide_index=True, width='stretch')

    left, right = st.columns(2)
    with left:
        pie('access', '여행지까지 가는 방법')
    with right:
        pie('inside', '여행지 안에서 다니는 방법')

    # 여행지별로 어떤 방법을 많이 골랐는지 (행: 여행지, 칸: 가는 방법, 값: 여행 수)
    st.subheader('여행지별 가는 방법')
    st.dataframe(pd.crosstab(view['place'], view['access']), width='stretch')
