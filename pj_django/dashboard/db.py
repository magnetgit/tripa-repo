"""대시보드용 DB 연결 — pj_django/.env 의 DB_* 값으로 (사이트와 같은 DB)"""
from pathlib import Path

import environ
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

env = environ.Env()
environ.Env.read_env(Path(__file__).resolve().parent.parent / '.env')

engine = create_engine(URL.create(
    'mysql+mysqldb',                       # 사이트가 쓰는 것과 같은 드라이버(mysqlclient)
    username=env('DB_USER'),
    password=env('DB_PASSWORD'),
    host=env('DB_HOST', default='127.0.0.1'),
    port=env.int('DB_PORT', default=3306),
    database=env('DB_NAME'),
    query={'charset': 'utf8mb4'},
))
