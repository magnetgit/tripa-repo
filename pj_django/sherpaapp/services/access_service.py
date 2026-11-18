"""여행지까지 가는 방법 비교·선택 (cloud-tripa transport_service 를 TRIPA 에 맞게 옮김)

- compare(travel): 집(출발지) → 여행지로 갈 수 있는 방법을 모두 만들어 가격·시간을 비교한다.
  자차 · KTX(바로/환승) · KTX+렌터카 · 고속버스 · 비행기(+렌터카) · 배(+차 싣기)
  섬은 배가 떠나는 항구마다 따로 비교한다 (🟧 11/17): 대중교통으로 항구까지 · 항구에 차 두고 · 내 차 싣고
  열차·항공·고속버스·여객선은 공공데이터 실제 시간표(transport_timetable), 없으면 어림값.
- choose(travel, mode): 고른 방법을 Travel.access_way·access_route 에 저장하고
  첫날 출발점을 도착 공항·역·항구로, 출발 시각을 도착(렌터카 수령) 뒤로, 교통 예산을 고친 뒤 첫날 일정을 다시 계산한다.

access_route 모양 (데모 데이터도 같은 모양):
  {'mode', 'key', 'title', 'total', 'minutes', 'people', 'items': [{label, amount}], 'real': bool,
   'origin': {name, addr, lat, lon}, 'arrive': {name, addr, lat, lon}, 'ready': 'HH:MM',
   'go': [leg], 'back': [leg]}
  leg = {'mode', 'label', 'from', 'to', 'minutes', 'depart', 'arrive', 'fare', 'detail', 'real',
         'from_pt': [lat, lon], 'to_pt': [lat, lon]}
  mode: car·rental·ktx·itx·bus·subway·local_bus·flight·ferry·taxi·wait
  key: 고를 때 쓰는 이름. 보통은 mode 와 같고, 배는 항구까지 붙는다 ('ferry_park@묵호'). choose() 는 key·mode 둘 다 받는다
"""
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta

from django.core.cache import cache

from . import rest_stop_service
from .region_cities import REGION_CITIES
from . import transport_timetable as tt

# 도시: 좌표, TAGO 역 이름, 고속버스 터미널, 가까운 공항, 항구
CITIES = {
    '서울': {'pos': (37.5665, 126.9780), 'station': '서울', 'terminal': '서울경부', 'airport': '김포국제공항'},
    '인천': {'pos': (37.4563, 126.7052), 'terminal': '인천', 'airport': '김포국제공항', 'port': '인천항연안여객터미널'},
    '대전': {'pos': (36.3504, 127.3845), 'station': '대전', 'terminal': '대전복합', 'airport': '청주국제공항'},
    '청주': {'pos': (36.6424, 127.4890), 'station': '오송', 'terminal': '청주(센트럴)', 'airport': '청주국제공항'},
    '대구': {'pos': (35.8714, 128.6014), 'station': '동대구', 'terminal': '동대구', 'airport': '대구국제공항'},
    '부산': {'pos': (35.1796, 129.0756), 'station': '부산', 'terminal': '부산', 'airport': '김해국제공항',
             'port': '부산항연안여객터미널'},
    '울산': {'pos': (35.5384, 129.3114), 'station': '울산', 'terminal': '울산', 'airport': '울산공항'},
    '광주': {'pos': (35.1595, 126.8526), 'station': '광주송정', 'terminal': '광주(유·스퀘어)', 'airport': '광주공항'},
    '강릉': {'pos': (37.7519, 128.8761), 'station': '강릉', 'terminal': '강릉', 'airport': '양양국제공항'},
    '속초': {'pos': (38.2070, 128.5918), 'terminal': '속초', 'airport': '양양국제공항'},
    '춘천': {'pos': (37.8813, 127.7298), 'station': '춘천', 'terminal': '춘천'},
    '경주': {'pos': (35.8562, 129.2247), 'station': '경주', 'terminal': '경주', 'airport': '포항경주공항'},
    '여수': {'pos': (34.7604, 127.6622), 'station': '여수EXPO', 'terminal': '여수', 'airport': '여수공항'},
    '전주': {'pos': (35.8242, 127.1480), 'station': '전주', 'terminal': '전주'},
    '포항': {'pos': (36.0190, 129.3435), 'station': '포항', 'terminal': '포항', 'airport': '포항경주공항',
             'port': '포항여객선터미널'},
    '목포': {'pos': (34.8118, 126.3922), 'station': '목포', 'port': '목포항국제여객터미널'},
    '완도': {'pos': (34.3110, 126.7550), 'port': '완도항여객선터미널'},
    '제주': {'pos': (33.4996, 126.5312), 'airport': '제주국제공항', 'port': '제주항연안여객터미널', 'island': True},
    '울릉도': {'pos': (37.4844, 130.9057), 'port': '울릉 도동항여객선터미널', 'island': True},
    # 배로만 가는 섬 (🟧 11/17). 열차·버스·비행기 칸이 없어서 배 방법만 비교됨. 섬을 더 넣으려면 여기 한 줄 + FERRY_ROUTES
    '백령도': {'pos': (37.9590, 124.6650), 'port': '백령도 용기포신항', 'island': True},
    '흑산도': {'pos': (34.6840, 125.4350), 'port': '흑산도항여객선터미널', 'island': True},
    '홍도': {'pos': (34.6830, 125.1940), 'port': '홍도항여객선터미널', 'island': True},
    '거문도': {'pos': (34.0280, 127.3080), 'port': '거문도여객선터미널', 'island': True},
    '덕적도': {'pos': (37.2260, 126.1440), 'port': '덕적도 진리도우선착장', 'island': True},
    '욕지도': {'pos': (34.6330, 128.2640), 'port': '욕지항여객선터미널', 'island': True},
    '청산도': {'pos': (34.1800, 126.8580), 'port': '청산도항여객터미널', 'island': True},
}
# 큰 도시(위 표): 출발지가 어느 도시인지, 작은 도시로 갈 때 어디를 거칠지 정할 때 씀
CORE_CITIES = tuple(CITIES)
# 🟧 11/18 지방 시·군 139곳 더하기 (services/region_cities.py). 전엔 표에 없는 도시(거제 등)는 60km 안의
# 가장 가까운 큰 도시(부산)로 잡혀서, 차로 가도 '부산 시내' 도착 → 부산에서 거제로 다시 가는 일정이 됐음
for _name, _city in REGION_CITIES.items():
    CITIES.setdefault(_name, dict(_city))
STATION_LABEL = {'여수EXPO': '여수엑스포역', '경주': '신경주역'}
# ---- 섬 가는 배 (🟧 11/17 항구별로 다시 짬) ----
# 뭍 쪽 항구: 이름(카카오 검색용) · 좌표(검색 실패 때) · 화면에 쓰는 짧은 이름
FERRY_PORTS = {
    '강릉': {'name': '강릉항여객터미널', 'pos': (37.7722, 128.9512)},
    '묵호': {'name': '묵호항여객선터미널', 'pos': (37.5490, 129.1160)},
    '포항': {'name': '포항여객선터미널', 'pos': (36.0497, 129.3790)},
    '영일만': {'name': '포항영일만항 국제여객터미널', 'pos': (36.1110, 129.4350), 'label': '포항 영일만'},
    '후포': {'name': '후포항여객선터미널', 'pos': (36.6790, 129.4560), 'label': '울진 후포'},
    '목포': {'name': '목포항국제여객터미널', 'pos': (34.7835, 126.3840)},
    '목포연안': {'name': '목포연안여객선터미널', 'pos': (34.7810, 126.3810), 'label': '목포'},
    '완도': {'name': '완도항여객선터미널', 'pos': (34.3170, 126.7560)},
    '녹동': {'name': '녹동신항여객선터미널', 'pos': (34.5230, 127.1380), 'label': '고흥 녹동'},
    '진도': {'name': '진도항 연안여객선터미널', 'pos': (34.3640, 126.1340)},
    '삼천포': {'name': '삼천포신항여객터미널', 'pos': (34.9240, 128.0700), 'label': '사천 삼천포'},
    '부산': {'name': '부산항연안여객터미널', 'pos': (35.0975, 129.0370)},
    '인천': {'name': '인천항연안여객터미널', 'pos': (37.4530, 126.6010)},
    '여수': {'name': '여수연안여객선터미널', 'pos': (34.7380, 127.7340)},
    '통영': {'name': '통영항여객선터미널', 'pos': (34.8390, 128.4200)},
}
# 섬 → 노선들. 한 줄 = 뭍 항구 하나에서 그 섬으로 가는 배
#   port : FERRY_PORTS 의 키          isle : 섬 쪽에서 내리는 곳 이름 (없으면 CITIES[섬]['port'])
#   fare : 1인 편도 뱃삯(어림)        car  : 차 1대 편도 선적 운임(어림). None = 차를 못 싣는 배(쾌속선)
#   sail : 배 타는 시간(분)           words: 운항 시간표에서 찾는 글자 (출발 항구, 도착 항구) — 해운조합 자료의 oport_nm·dest_nm
#   usual: 시간표를 못 받았을 때 평소 출항 시각 (가는 배, 오는 배)
# ⚠️ 뱃삯·선적 운임은 어림값이라 화면에도 '어림'이라고 알린다. 출항 시각·배 이름은 실제 시간표(transport_timetable.ferries)
FERRY_ROUTES = {
    '울릉도': [
        {'port': '묵호', 'isle': '울릉 도동항여객선터미널', 'fare': 64000, 'car': None, 'sail': 170,
         'words': ('묵호', '울릉(도동)'), 'usual': ('08:20', '17:20')},
        {'port': '강릉', 'isle': '울릉 저동항여객선터미널', 'fare': 66000, 'car': None, 'sail': 180,
         'words': ('강릉', '울릉(저동)'), 'usual': ('08:00', '17:20')},
        {'port': '포항', 'isle': '울릉 도동항여객선터미널', 'fare': 68000, 'car': None, 'sail': 200,
         'words': ('포항', '울릉'), 'usual': ('09:50', '14:20')},
        # 차를 실을 수 있는 큰 배 (밤에 떠나 다음 날 아침 도착)
        {'port': '영일만', 'isle': '울릉 사동항여객선터미널', 'fare': 80000, 'car': 210000, 'sail': 420,
         'words': ('영일만', '울릉(사동)'), 'usual': ('23:00', '12:30')},
        {'port': '후포', 'isle': '울릉 사동항여객선터미널', 'fare': 66000, 'car': 150000, 'sail': 270,
         'words': ('후포', '울릉(사동)'), 'usual': ('08:15', '14:00')},
    ],
    '제주': [
        {'port': '목포', 'fare': 42000, 'car': 120000, 'sail': 270, 'words': ('목포', '제주'), 'usual': ('08:30', '16:45')},
        {'port': '완도', 'fare': 36000, 'car': 100000, 'sail': 170, 'words': ('완도', '제주'), 'usual': ('09:00', '16:30')},
        {'port': '진도', 'fare': 42000, 'car': 110000, 'sail': 100, 'words': ('진도', '제주'), 'usual': ('08:00', '13:30')},
        {'port': '녹동', 'fare': 36000, 'car': 100000, 'sail': 220, 'words': ('녹동', '제주'), 'usual': ('09:00', '16:30')},
        {'port': '삼천포', 'fare': 40000, 'car': 110000, 'sail': 420, 'words': ('삼천포', '제주'), 'usual': ('23:30', '14:00')},
        {'port': '부산', 'fare': 55000, 'car': 150000, 'sail': 720, 'words': ('부산', '제주'), 'usual': ('19:00', '19:00')},
        {'port': '인천', 'fare': 70000, 'car': 180000, 'sail': 780, 'words': ('인천', '제주'), 'usual': ('19:00', '19:00')},
    ],
    '백령도': [{'port': '인천', 'fare': 70000, 'car': None, 'sail': 240, 'words': ('인천', '백령'), 'usual': ('08:30', '13:00')}],
    '흑산도': [{'port': '목포연안', 'fare': 37000, 'car': None, 'sail': 120, 'words': ('목포', '흑산'), 'usual': ('07:50', '15:30')}],
    '홍도': [{'port': '목포연안', 'fare': 45000, 'car': None, 'sail': 150, 'words': ('목포', '홍도'), 'usual': ('07:50', '15:30')}],
    '거문도': [{'port': '여수', 'fare': 39000, 'car': None, 'sail': 140, 'words': ('여수', '거문'), 'usual': ('07:30', '16:00')},
            {'port': '녹동', 'fare': 26000, 'car': None, 'sail': 180, 'words': ('녹동', '거문'), 'usual': ('07:00', '14:00')}],
    '덕적도': [{'port': '인천', 'fare': 26000, 'car': None, 'sail': 80, 'words': ('인천', '덕적'), 'usual': ('08:30', '15:30')}],
    '욕지도': [{'port': '통영', 'fare': 12000, 'car': 25000, 'sail': 60, 'words': ('통영', '욕지'), 'usual': ('09:30', '16:30')}],
    '청산도': [{'port': '완도', 'fare': 8000, 'car': 25000, 'sail': 50, 'words': ('완도', '청산'), 'usual': ('08:30', '17:00')}],
}
# 한 섬에 방법 종류마다 몇 항구까지 보여 줄지 (좋은 순서로)
FERRY_SHOW = {'ferry_car': 2, 'ferry_park': 3, 'ferry': 2}
FERRY_SHOW_AIR = {'ferry_car': 2, 'ferry_park': 1, 'ferry': 1}     # 비행기로도 가는 섬(제주): 배 카드가 너무 많아지지 않게
RENT_PER_DAY = {'제주': 55000, '울릉도': 90000}
RENT_DEFAULT = 70000
CAR_WON_PER_KM = 220        # 유류비 + 통행료 (차 1대)
PARKING_PER_DAY = 10000     # 공항·항구 주차
KTX_WON_PER_KM = 130        # 시간표 요금이 없을 때
BUS_WON_PER_KM = 75
FLIGHT_FARE = 65000
TIME_VALUE_PER_HOUR = 8000  # '추천' 점수: 1인 1시간을 이만큼의 비용으로 본다
LEAVE_HOME = 7 * 60         # 첫날 집에서 나서는 가장 이른 시각
RETURN_AFTER = 17 * 60      # 마지막 날 돌아오는 편은 오후 5시 뒤 첫 편
BUFFER = {'flight': 50, 'ferry': 40, 'ktx': 15, 'itx': 15, 'bus': 15}
CACHE_SECONDS = 600
VIA_LAST_MAX = 150          # 다른 도시의 역·터미널을 거칠 때, 거기서 여행지까지 이보다 오래 걸리면 그 방법은 뺌 (분)
TITLES = {
    'car': '자차', 'ktx': 'KTX', 'ktx_rent': 'KTX + 렌터카', 'train_transfer': 'KTX 환승', 'bus': '고속버스',
    'flight': '비행기 + 대중교통', 'flight_rent': '비행기 + 렌터카', 'ferry': '배 + 대중교통', 'ferry_car': '배에 내 차 싣기',
    'ferry_park': '항구에 차 두고 배',      # 🟧 11/17 항구까지 내 차로 가서 세워 두고 사람만 배를 탐
}
# 화면·대시보드에 쓰는 큰 분류 (Travel.access_way)
ACCESS_WAY = {'car': 'car', 'ktx': 'ktx', 'ktx_rent': 'ktx', 'train_transfer': 'train_transfer', 'bus': 'bus',
              'flight': 'flight', 'flight_rent': 'flight', 'ferry': 'ferry', 'ferry_car': 'ferry', 'ferry_park': 'ferry'}
WAY_LABEL = {'car': '자차', 'ktx': 'KTX', 'train_transfer': '기차 환승', 'bus': '고속버스', 'flight': '비행기', 'ferry': '배'}


# ------------------------------------------------------------------ 작은 도우미
def _km(a, b):
    p = math.pi / 180
    h = (math.sin((b[0] - a[0]) * p / 2) ** 2
         + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(h))


def _clock(m):
    m = int(m) % (24 * 60)
    return '%02d:%02d' % (m // 60, m % 60)


def _won(n):
    return int(round((n or 0) / 100.0) * 100)


def city_of(text=None, point=None, core=False):
    """'제주도'·'부산광역시' 같은 이름이나 좌표 → CITIES 의 키 (못 찾으면 None)
    core=True 면 큰 도시(CORE_CITIES)에서만 — 출발지용 (성남에 살면 서울의 역·터미널·공항을 씀)"""
    text = text or ''
    names = CORE_CITIES if core else CITIES
    for key in sorted(names, key=len, reverse=True):
        if key[:2] in text:
            return key
    if point:
        key, d = min(((k, _km(point, CITIES[k]['pos'])) for k in names), key=lambda x: x[1])
        return key if d < 60 else None
    return None


def _hub_cities(d_city, kind):
    """d_city 로 갈 때 쓸 역('station')·터미널('terminal')이 있는 도시들: 그 도시 먼저, 다음은 70km 안에서 가까운 순 (최대 5곳)
    예) 거제(역 없음) → 창원·진주·부산 … 중 실제 시간표가 있는 첫 도시를 거쳐 감 (🟧 11/18)"""
    here = CITIES[d_city]
    near = sorted((_km(here['pos'], c['pos']), k) for k, c in CITIES.items()
                  if k != d_city and c.get(kind) and not c.get('island'))
    return ([d_city] if here.get(kind) else []) + [k for d, k in near if d <= 70][:4]


def _center(city):
    lat, lon = CITIES[city]['pos']
    return {'name': f'{city} 시내', 'lat': lat, 'lon': lon, 'addr': ''}


def _hub(name, fallback_city):
    """역·공항·항구 이름 → {'name', 'lat', 'lon', 'addr'} (못 찾으면 그 도시 가운데)"""
    p = tt.hub_point(name)
    lat, lon = (p[0], p[1]) if p else CITIES[fallback_city]['pos']
    return {'name': name, 'lat': lat, 'lon': lon, 'addr': p[2] if p else ''}


def _leg(mode, label, a, b, minutes, fare=0, detail='', real=False):
    return {'mode': mode, 'label': label, 'from': a['name'], 'to': b['name'], 'minutes': int(minutes),
            'fare': int(fare or 0), 'detail': detail, 'real': real,
            'from_pt': [round(a['lat'], 6), round(a['lon'], 6)], 'to_pt': [round(b['lat'], 6), round(b['lon'], 6)]}


def _local(a, b, people, car=False):
    """도시 안 이동 (집 ↔ 역·공항): 차면 어림, 아니면 카카오 대중교통 실제 값"""
    d = _km((a['lat'], a['lon']), (b['lat'], b['lon']))
    if car:
        return _leg('car', '자차', a, b, d * 1.3 / 40 * 60 + 10, _won(d * 1.3 * CAR_WON_PER_KM))
    r = tt.transit(a['lat'], a['lon'], b['lat'], b['lon'])
    if r:
        return _leg('subway' if '호선' in r['summary'] or '철' in r['summary'] else 'local_bus',
                    '대중교통', a, b, r['minutes'], (r['fare'] or 0) * people, r['summary'], True)
    if d < 3:
        return _leg('taxi', '택시', a, b, d * 3 + 8, _won(4800 + d * 1000))
    if d > 15:        # 도시를 넘는 구간(창원역 → 거제): 시외버스로 어림 (시내버스 속도로 치면 너무 오래 걸림)
        return _leg('local_bus', '시외버스', a, b, d * 1.3 / 50 * 60 + 20, _won((1500 + d * 1.3 * 110) * people),
                    '시외버스 어림')
    return _leg('local_bus', '대중교통', a, b, d * 1.4 / 25 * 60 + 10, 1500 * people)


def _pick(rows, earliest):
    """earliest(분) 뒤 첫 편, 없으면 None"""
    for r in rows:
        m = tt.minutes_of(r['dep'])
        if m is not None and m >= earliest:
            return r
    return None


def _timed(rows, earliest, recent=False):
    """시간표에서 고른 편 → (출발 분, 걸린 분, 1인 요금, 이름, 실제인지)"""
    r = _pick(rows, earliest)
    if not r:
        return None
    dep, arr = tt.minutes_of(r['dep']), tt.minutes_of(r['arr']) if r.get('arr') else None
    minutes = (arr - dep) % (24 * 60) if arr is not None else None
    return dep, minutes, r.get('fare'), r.get('name', ''), not recent


# ------------------------------------------------------------------ 큰 구간 (열차·버스·항공·배)
def _train(a_city, b_city, day, earliest, strict=False):
    """열차 한 번 (없으면 오송·서울·용산 환승) → [(출발역, 도착역, 출발분, 분, 1인 요금, 이름, 실제)]
    strict: 시간표에 없으면 어림하지 않고 None (작은 도시의 역은 그 구간 열차가 없을 수 있어서)"""
    s1, s2 = CITIES[a_city].get('station'), CITIES[b_city].get('station')
    if not s1 or not s2:
        return None
    rows = tt.trains(tt.station_id(s1), tt.station_id(s2), day)
    hit = _timed(rows, earliest)
    d = _km(CITIES[a_city]['pos'], CITIES[b_city]['pos'])
    if hit:
        return [(s1, s2) + hit[:2] + (hit[2] or _won(d * 1.15 * KTX_WON_PER_KM),) + hit[3:]]
    for via in ('오송', '서울', '용산'):
        if via in (s1, s2):
            continue
        first = _timed(tt.trains(tt.station_id(s1), tt.station_id(via), day), earliest)
        if not first:
            continue
        second = _timed(tt.trains(tt.station_id(via), tt.station_id(s2), day), first[0] + first[1] + 15)
        if second:
            return [(s1, via) + first, (via, s2) + second]
    if strict:
        return None
    # 시간표가 없으면 어림 (바로 가는 것으로)
    return [(s1, s2, earliest + 20, d * 1.15 / 160 * 60 + 15, _won(d * 1.15 * KTX_WON_PER_KM), 'KTX', False)]


def _bus(a_city, b_city, day, earliest, strict=False):
    t1, t2 = CITIES[a_city].get('terminal'), CITIES[b_city].get('terminal')
    if not t1 or not t2:
        return None
    i1, i2 = tt.terminal_id(t1), tt.terminal_id(t2)
    hit = _timed(tt.buses(i1, i2, day), earliest)
    if not hit:                     # 고속버스 시간표는 하루 뒤까지만 → 내일 운행 시각으로 대신
        hit = _timed(tt.buses(i1, i2, date.today() + timedelta(days=1)), earliest, recent=True)
    d = _km(CITIES[a_city]['pos'], CITIES[b_city]['pos'])
    if hit:
        return (t1, t2) + hit[:2] + (hit[2] or _won(d * 1.3 * BUS_WON_PER_KM),) + hit[3:]
    if strict:
        return None
    return (t1, t2, earliest + 20, d * 1.3 / 75 * 60 + 15, _won(d * 1.3 * BUS_WON_PER_KM), '고속버스', False)


def _flight(a_city, b_city, day, earliest):
    ap1, ap2 = CITIES[a_city].get('airport'), CITIES[b_city].get('airport')
    if not ap1 or not ap2 or ap1 == ap2:
        return None
    hit = _timed(tt.flights(tt.airport_id(ap1), tt.airport_id(ap2), day), earliest)
    if hit:
        return (ap1, ap2) + hit[:2] + (hit[2] or FLIGHT_FARE,) + hit[3:]      # 요금 칸이 빈 편은 어림 요금
    if tt.airport_id(ap1) and tt.airport_id(ap2) and tt.flights(tt.airport_id(ap1), tt.airport_id(ap2), day) == []:
        return None                 # 그 노선 비행기가 없음
    return (ap1, ap2, earliest + 30, 65, FLIGHT_FARE, '비행기', False)


def _port_hub(route):
    """뭍 쪽 항구 → {'name', 'lat', 'lon', 'addr'}"""
    port = FERRY_PORTS[route['port']]
    found = tt.hub_point(port['name'])
    lat, lon = (found[0], found[1]) if found else port['pos']
    return {'name': port['name'], 'lat': lat, 'lon': lon, 'addr': found[2] if found else ''}


def _port_label(route):
    return FERRY_PORTS[route['port']].get('label') or route['port']


def _sailings(route, day, back=False):
    """그날 그 노선의 출항 목록 → (rows, recent). 시간표에 없으면 ([], False)"""
    w_from, w_to = route['words']
    return tt.ferries(day, w_to if back else w_from, w_from if back else w_to)


def _running_routes(island, day):
    """그 섬 노선 가운데 지금 다니는 것만. 시간표를 아예 못 받았으면(먼 날짜·조회 실패) 전부 (평소 시각으로 어림)"""
    routes = FERRY_ROUTES.get(island, [])
    found = [r for r in routes if _sailings(r, day)[0]]
    return found or routes


def _ferry(route, island, day, earliest, back=False):
    """→ (출발항, 도착항, 출발분, 분, 1인 요금, 차 요금, 이름, 실제, 새벽에 나서야 하는지)"""
    fare, car_fare, sail, usual = route['fare'], route['car'], route['sail'], route['usual']
    p_main, p_isle = FERRY_PORTS[route['port']]['name'], route.get('isle') or CITIES[island]['port']
    rows, recent = _sailings(route, day, back)
    if not rows:                                   # 시간표에 없는 노선 → 평소 출항 시각
        rows, recent = [{'dep': usual[1] if back else usual[0], 'name': '여객선'}], True
    pick = _pick(rows, earliest)
    early = pick is None                           # 첫 배에 맞추려면 새벽에 나서야 함
    pick = pick or rows[0]
    a, b = (p_isle, p_main) if back else (p_main, p_isle)
    return a, b, tt.minutes_of(pick['dep']), sail, fare, car_fare, pick.get('name') or '여객선', not recent, early


# ------------------------------------------------------------------ 방법 하나 만들기
class _Ctx:
    def __init__(self, travel, origin, people):
        self.travel = travel
        self.origin = origin                         # {'name','lat','lon','addr'}
        self.people = max(1, people)
        self.start = travel.t_start
        self.end = travel.t_end or travel.t_start
        self.nights = max(0, (self.end - self.start).days)
        self.days = self.nights + 1
        self.o_city = city_of(None, (origin['lat'], origin['lon']), core=True) or city_of(origin['name'], core=True)
        self.d_city = city_of(travel.t_place) or city_of(None, _dest_point(travel))
        self.dest = _dest_hub(travel, self.d_city)
        self.return_after = _return_after(travel)


def _return_after(travel):
    """돌아오는 편 가장 이른 시각(분): 마지막 날 마지막 장소가 끝나고 1시간 뒤, 적어도 오후 5시"""
    from ..models import SchedulePlace
    last = (SchedulePlace.objects.filter(schedule__travel=travel, arrive_time__isnull=False)
            .order_by('-schedule__s_day', '-visit_order').first())
    if not last or (travel.t_end and last.schedule.s_day != travel.t_end):
        return RETURN_AFTER
    t = last.arrive_time
    return max(RETURN_AFTER, t.hour * 60 + t.minute + (last.stay_time or 60) + 60)


def _dest_point(travel):
    from ..models import SchedulePlace
    sp = (SchedulePlace.objects.filter(schedule__travel=travel, place__p_lat__isnull=False)
          .select_related('place').order_by('schedule__s_day', 'visit_order').first())
    return (float(sp.place.p_lat), float(sp.place.p_lon)) if sp else None


def _dest_hub(travel, d_city):
    p = _dest_point(travel)
    if p:
        return {'name': f'{travel.t_place} 첫 장소', 'lat': p[0], 'lon': p[1], 'addr': ''}
    if d_city:
        lat, lon = CITIES[d_city]['pos']
        return {'name': f'{d_city} 시내', 'lat': lat, 'lon': lon, 'addr': ''}
    return None


def _main_leg(kind, label, a_name, b_name, a_city, b_city, dep, minutes, fare_each, name, real, people):
    a, b = _hub(a_name, a_city), _hub(b_name, b_city)
    leg = _leg(kind, label, a, b, minutes, (fare_each or 0) * people, name, real)
    leg['_dep'] = dep
    return leg


def _add_rests(legs):
    """2시간 넘게 운전하는 자차 구간을 휴게소에서 나눈다 (🟧 11/18, 장거리 여행에 휴게소 포함)

    '자차 성남 → 강릉 2시간 47분' → '자차 성남 → 횡성휴게소 강릉방향' + (15분 쉼) + '자차 횡성휴게소 → 강릉'
    2시간마다 한 곳(최대 3곳). 휴게소를 못 찾으면 그 구간은 그대로 둔다.
    나눈 구간에는 추가 키 rest {'name', 'minutes'} (그 구간 끝에서 쉬는 곳) 가 붙는다.
    """
    out = []
    for leg in legs:
        count = rest_stop_service.stops_for(leg['minutes']) if leg['mode'] == 'car' and leg.get('_dep') is None else 0
        stops = rest_stop_service.find(tuple(leg['from_pt']), tuple(leg['to_pt']), count) if count else []
        if not stops:
            out.append(leg)
            continue
        marks = [0.0] + [x['at'] for x in stops] + [1.0]
        places = ([{'name': leg['from'], 'lat': leg['from_pt'][0], 'lon': leg['from_pt'][1]}] + stops
                  + [{'name': leg['to'], 'lat': leg['to_pt'][0], 'lon': leg['to_pt'][1]}])
        for i in range(len(places) - 1):
            share = marks[i + 1] - marks[i]
            detail = leg['detail'] if i == 0 else '휴게소에서 %d분 쉬고 출발' % rest_stop_service.REST_MINUTES
            part = _leg('car', leg['label'], places[i], places[i + 1], max(1, round(leg['minutes'] * share)),
                        _won(leg['fare'] * share) if leg['fare'] else 0, detail, leg['real'])
            if i < len(stops):
                part['_rest'] = rest_stop_service.REST_MINUTES
                part['rest'] = {'name': stops[i]['name'], 'minutes': rest_stop_service.REST_MINUTES}
            out.append(part)
        # 100원 단위로 나누다 생긴 차이는 마지막 구간에 (합계가 나누기 전과 같게)
        out[-1]['fare'] += leg['fare'] - sum(x['fare'] for x in out[-len(places) + 1:])
    return out


def _assemble(ctx, mode, go, back, items, t_way, arrive_hub, pickup=0, note=''):
    """구간들에 시각을 붙이고 합계·태그 전 값까지 만든다"""
    go, back = _add_rests(go), _add_rests(back)
    # 가는 길: 큰 구간 출발 시각(_dep)에서 앞 구간을 거꾸로 맞춤
    _schedule(go, LEAVE_HOME)
    _schedule(back, ctx.return_after, back=True)
    ready = tt.minutes_of(go[-1]['arrive']) + pickup if go else LEAVE_HOME
    total = sum(leg['fare'] for leg in go + back) + sum(i['amount'] for i in items)
    items = [{'label': '가는 길 요금', 'amount': sum(l['fare'] for l in go)},
             {'label': '오는 길 요금', 'amount': sum(l['fare'] for l in back)}] + items
    minutes = (tt.minutes_of(go[-1]['arrive']) - tt.minutes_of(go[0]['depart'])) % (24 * 60) if go else 0
    return {
        'mode': mode, 'title': TITLES[mode], 'total': _won(total), 'per_person': _won(total / ctx.people),
        'minutes': minutes, 'people': ctx.people, 'items': [i for i in items if i['amount']],
        'real': any(l['real'] for l in go + back if l['mode'] in ('ktx', 'itx', 'bus', 'flight', 'ferry')),
        'origin': ctx.origin, 'arrive': arrive_hub, 'ready': _clock(ready), 't_way': t_way,
        'go': [_clean(l) for l in go], 'back': [_clean(l) for l in back], 'note': note, 'tags': [],
    }


def _clean(leg):
    return {k: v for k, v in leg.items() if not k.startswith('_')}


def _schedule(legs, default_start, back=False):
    """구간마다 depart·arrive('HH:MM')를 붙인다. 큰 구간(_dep 있음)이 있으면 그 시각에 맞춰 앞 구간을 거꾸로 채움"""
    if not legs:
        return
    anchor = next((i for i, l in enumerate(legs) if l.get('_dep') is not None), None)
    if anchor is None:
        t = default_start
    else:
        t = legs[anchor]['_dep'] - sum(l['minutes'] for l in legs[:anchor]) - BUFFER.get(legs[anchor]['mode'], 10)
        t -= sum(l.get('_rest', 10) for l in legs[:anchor])     # 구간 사이 틈 (휴게소에서 쉬면 그만큼)
    for i, leg in enumerate(legs):
        if i == anchor:
            t = max(t, leg['_dep'])
            if leg['mode'] == 'ferry' and t + leg['minutes'] >= 24 * 60:
                leg['overnight'] = True           # 밤배: 다음 날 아침 도착
        leg['depart'] = _clock(t)
        t += leg['minutes']
        leg['arrive'] = _clock(t)
        gap = BUFFER.get(legs[i + 1]['mode'], 10) if i + 1 < len(legs) and i + 1 == anchor else 10
        t += max(gap, leg.get('_rest', 0))                       # 휴게소에서 쉬는 시간 (🟧 11/18)


def _rent_item(ctx):
    per = RENT_PER_DAY.get(ctx.d_city, RENT_DEFAULT)
    return {'label': f'렌터카 {ctx.days}일', 'amount': per * ctx.days}


def _plan_car(ctx):
    if CITIES[ctx.d_city].get('island') or CITIES.get(ctx.o_city, {}).get('island'):
        return None
    d = _km((ctx.origin['lat'], ctx.origin['lon']), (ctx.dest['lat'], ctx.dest['lon']))
    go = [_leg('car', '자차', ctx.origin, ctx.dest, d * 1.3 / 75 * 60 + 15, _won(d * 1.3 * CAR_WON_PER_KM),
               '유류비·통행료 어림')]
    back = [_leg('car', '자차', ctx.dest, ctx.origin, go[0]['minutes'], go[0]['fare'], '유류비·통행료 어림')]
    arrive = _center(ctx.d_city)             # 첫 장소와 같은 자리면 경로가 0이라
    return _assemble(ctx, 'car', go, back, [], 'car', arrive, note='차 1대 기준')


def _plan_train(ctx, rent=False):
    if not CITIES[ctx.o_city].get('station') and ctx.o_city != '인천':
        return None
    o_city = '서울' if ctx.o_city == '인천' else ctx.o_city
    s1 = _hub(STATION_LABEL.get(CITIES[o_city]['station'], CITIES[o_city]['station'] + '역'), o_city)
    to_st = _local(ctx.origin, s1, ctx.people)
    earliest = LEAVE_HOME + to_st['minutes'] + 15
    # 🟧 11/18 여행지에 역이 없거나 그 구간 열차가 없으면, 가까운 도시 중 실제 시간표가 있는 역을 거쳐 감
    #          (큰 도시끼리는 지금처럼 시간표가 없어도 어림으로 보여 줌)
    h_city = trips = back_trips = None
    for h in _hub_cities(ctx.d_city, 'station'):
        if h == o_city:
            continue
        strict = not (h == ctx.d_city and h in CORE_CITIES)
        trips = _train(o_city, h, ctx.start, earliest, strict)
        back_trips = _train(h, o_city, ctx.end, ctx.return_after, strict) if trips else None
        if trips and back_trips:
            h_city = h
            break
    if not h_city:
        return None
    via = h_city != ctx.d_city
    def legs_of(rows, a_city, b_city):
        out = []
        for i, (x, y, dep, mins, fare, name, real) in enumerate(rows):
            kind = 'itx' if '춘천' in (x, y) or 'ITX' in (name or '') else 'ktx'
            # 🟧 11/18 열차 종류를 이름 그대로 (ITX-새마을·무궁화호가 'ITX-청춘'으로 나오던 것)
            grade = (name or '').split(' ')[0]
            label = 'KTX' if not grade or grade.startswith('KTX') else ('ITX-청춘' if '춘천' in (x, y) else grade)
            out.append(_main_leg(kind, label,
                                 STATION_LABEL.get(x, x + '역'), STATION_LABEL.get(y, y + '역'),
                                 a_city if i == 0 else h_city, b_city, dep, mins, fare, name, real, ctx.people))
        return out
    go = [to_st] + legs_of(trips, o_city, h_city)
    s2 = _hub(go[-1]['to'], h_city)
    back = legs_of(back_trips, h_city, o_city)
    items = []
    if rent:
        go.append(_leg('rental', '렌터카 인수', s2, s2, 20, 0, '역 앞 렌터카'))
        items.append(_rent_item(ctx))
        t_way = 'car'
    else:
        t_way = 'public_transport'              # 역에서 첫 장소까지는 일정 화면이 대중교통으로 이어 줌
    back.append(_local(_hub(back[-1]['to'], o_city), ctx.origin, ctx.people))
    if ctx.o_city == '인천':
        go[0]['detail'] = (go[0]['detail'] + ' · 인천에서 서울역까지').strip(' ·')
    mode = 'ktx_rent' if rent else ('train_transfer' if len(trips) > 1 else 'ktx')
    if via:
        # 역에서 여행지까지 이어 가는 구간도 넣어서 시간·비용을 그대로 보여 줌 (도착 = 여행지)
        center = _center(ctx.d_city)
        go.append(_local(s2, center, ctx.people, car=rent))
        if go[-1]['minutes'] > VIA_LAST_MAX:
            return None                      # 역에서 여행지까지가 너무 멀면 이 방법은 안 보여 줌
        back.insert(0, _local(center, s2, ctx.people, car=rent))
        return _assemble(ctx, mode, go, back, items, t_way, center, 0,
                         note='%s까지 열차, 거기서 %s까지 %s' % (s2['name'], ctx.d_city, '렌터카' if rent else '버스'))
    return _assemble(ctx, mode, go, back, items, t_way, s2, 20 if rent else 10)


def _plan_bus(ctx):
    if CITIES[ctx.d_city].get('island') or not CITIES[ctx.o_city].get('terminal'):
        return None
    t1 = _hub(CITIES[ctx.o_city]['terminal'] + ' 고속버스터미널', ctx.o_city)
    to_t = _local(ctx.origin, t1, ctx.people)
    # 🟧 11/18 여행지 터미널로 가는 고속버스가 없으면, 가까운 도시 중 실제 시간표가 있는 터미널을 거쳐 감
    #          (거제 고현은 고속버스 시간표에 없음 → 통영 터미널까지 가서 버스로 이어 감)
    h_city = trip = back_trip = None
    for h in _hub_cities(ctx.d_city, 'terminal'):
        if h == ctx.o_city:
            continue
        strict = not (h == ctx.d_city and h in CORE_CITIES)
        trip = _bus(ctx.o_city, h, ctx.start, LEAVE_HOME + to_t['minutes'] + 15, strict)
        back_trip = _bus(h, ctx.o_city, ctx.end, ctx.return_after, strict) if trip else None
        if trip and back_trip:
            h_city = h
            break
    if not h_city:
        return None
    x, y, dep, mins, fare, name, real = trip
    go = [to_t, _main_leg('bus', '고속버스', x + ' 고속버스터미널', y + ' 고속버스터미널', ctx.o_city, h_city,
                         dep, mins, fare, name, real, ctx.people)]
    arrive = _hub(go[-1]['to'], h_city)
    x, y, dep, mins, fare, name, real = back_trip
    back = [_main_leg('bus', '고속버스', x + ' 고속버스터미널', y + ' 고속버스터미널', h_city, ctx.o_city,
                      dep, mins, fare, name, real, ctx.people)]
    back.append(_local(_hub(back[-1]['to'], ctx.o_city), ctx.origin, ctx.people))
    if h_city != ctx.d_city:
        center = _center(ctx.d_city)
        go.append(_local(arrive, center, ctx.people))
        if go[-1]['minutes'] > VIA_LAST_MAX:
            return None                      # 터미널에서 여행지까지가 너무 멀면 이 방법은 안 보여 줌
        back.insert(0, _local(center, arrive, ctx.people))
        return _assemble(ctx, 'bus', go, back, [], 'public_transport', center, 0,
                         note='%s까지 고속버스, 거기서 %s까지 버스' % (arrive['name'], ctx.d_city))
    return _assemble(ctx, 'bus', go, back, [], 'public_transport', arrive, 10)


def _plan_flight(ctx, rent=False):
    o_city, d_city = ctx.o_city, ctx.d_city
    island = CITIES[d_city].get('island') or CITIES[o_city].get('island')
    if not island and _km(CITIES[o_city]['pos'], CITIES[d_city]['pos']) < 250:
        return None
    a1 = CITIES[o_city].get('airport')
    a2 = CITIES[d_city].get('airport')
    if not a1 or not a2:
        return None
    ap1 = _hub(a1, o_city)
    to_ap = _local(ctx.origin, ap1, ctx.people, car=rent and not island)
    trip = _flight(o_city, d_city, ctx.start, LEAVE_HOME + to_ap['minutes'] + BUFFER['flight'])
    back_trip = _flight(d_city, o_city, ctx.end, ctx.return_after)
    if not trip or not back_trip:
        return None
    go = [to_ap, _main_leg('flight', '비행기', *trip[:2], o_city, d_city, *trip[2:], ctx.people)]
    ap2 = _hub(trip[1], d_city)
    back = [_main_leg('flight', '비행기', *back_trip[:2], d_city, o_city, *back_trip[2:], ctx.people)]
    back.append(_local(_hub(back_trip[1], o_city), ctx.origin, ctx.people))
    items = []
    if rent:
        go.append(_leg('rental', '렌터카 인수', ap2, ap2, 30, 0, '공항 렌터카 셔틀'))
        items.append(_rent_item(ctx))
        t_way = 'car'
    else:
        t_way = 'public_transport'
    return _assemble(ctx, 'flight_rent' if rent else 'flight', go, back, items, t_way, ap2, 30 if rent else 15)


def _ferry_leg(ctx, f, route, island, back, car):
    """배 구간 하나 (f = _ferry 가 돌려준 값)"""
    a, b, dep, sail, fare, car_fare, name, real, _ = f
    a_hub = _hub(a, island) if back else _port_hub(route)
    b_hub = _port_hub(route) if back else _hub(b, island)
    leg = _leg('ferry', '배 (차량 선적)' if car else '배', a_hub, b_hub, sail, (fare or 0) * ctx.people, name, real)
    leg['_dep'] = dep
    if car:
        leg['fare'] += car_fare or 0
        leg['detail'] = (name + ' · 차 1대 선적').strip(' ·')
    return leg


def _flip(leg):
    return dict(leg, **{'from': leg['to'], 'to': leg['from'], 'from_pt': leg['to_pt'], 'to_pt': leg['from_pt']})


def _plan_ferry_route(ctx, island, route, kind):
    """항구 하나로 가는 방법 하나. kind: 'ferry'(대중교통으로 항구까지) · 'ferry_park'(항구에 차 두고) · 'ferry_car'(차 싣고)"""
    car = kind == 'ferry_car'
    drive = kind in ('ferry_car', 'ferry_park')            # 항구까지 내 차로
    to_island = island == ctx.d_city
    p_main = _port_hub(route)
    home_side = ctx.origin if to_island else ctx.dest       # 뭍 쪽 끝 (집 또는 여행지)
    d = _km((home_side['lat'], home_side['lon']), (p_main['lat'], p_main['lon']))
    if d < 40:
        reach = _local(home_side, p_main, ctx.people, car=drive)
    elif drive:
        reach = _leg('car', '자차', home_side, p_main, d * 1.3 / 75 * 60 + 15, _won(d * 1.3 * CAR_WON_PER_KM),
                     '유류비·통행료 어림')
    else:
        reach = _leg('bus', '고속·시외버스', home_side, p_main, d * 1.3 / 70 * 60 + 15,
                     _won(d * 1.3 * BUS_WON_PER_KM * ctx.people))
    go_ferry = _ferry(route, island, ctx.start, LEAVE_HOME + reach['minutes'] + BUFFER['ferry'], back=not to_island)
    back_ferry = _ferry(route, island, ctx.end, ctx.return_after - 3 * 60, back=to_island)

    notes = []
    if go_ferry[-1]:
        notes.append('첫 배 시간에 맞추려면 새벽에 나서야 해요 (항구 근처 전날 1박도 생각해 보세요)')
    if go_ferry[2] + go_ferry[3] >= 24 * 60:
        notes.append('밤에 떠나 다음 날 아침에 도착하는 배예요')
    if kind == 'ferry_park':
        notes.append('섬 안에서는 대중교통·택시로 다녀요 (렌터카는 따로)')
    notes.append('뱃삯%s은 어림값이에요. 예매 전에 선사에서 확인하세요' % ('·차량 선적 운임' if car else ''))

    go_leg = _ferry_leg(ctx, go_ferry, route, island, not to_island, car)
    back_leg = _ferry_leg(ctx, back_ferry, route, island, to_island, car)
    if to_island:
        go, back = [reach, go_leg], [back_leg, _flip(reach)]
        arrive = _hub(go_leg['to'], island)
    else:                                   # 섬에서 나올 때: 내린 항구를 출발점으로 (항구 → 여행지 구간은 뺌)
        go = [_local(ctx.origin, _hub(go_leg['from'], island), ctx.people, car=drive), go_leg]
        back = [back_leg]
        arrive = p_main
    items = []
    if kind == 'ferry_park':                # 항구 주차: 여행 날 수만큼
        items.append({'label': '항구 주차 %d일' % ctx.days, 'amount': PARKING_PER_DAY * ctx.days})
    t_way = 'car' if car else 'public_transport'
    option = _assemble(ctx, kind, go, back, items, t_way, arrive, 20 if car else 15, ' · '.join(notes))
    option['key'] = '%s@%s' % (kind, route['port'])
    option['title'] = '%s · %s' % (TITLES[kind], _port_label(route))
    option['port'] = _port_label(route)
    # 섬에서 나올 때는 '내린 항구 → 여행지' 구간을 화면에서 빼지만, 어느 항구가 좋은지 고를 때는 그 길도 쳐야 함
    option['_rank'] = (0, 0) if to_island else (reach['fare'], reach['minutes'])
    return option


def _plan_ferries(ctx):
    """섬 여행이면 항구마다·방법 종류마다 만들어서, 종류별로 좋은 것 몇 개씩 → [option]  (🟧 11/17)

    종류: 대중교통으로 항구까지(ferry) · 항구에 차 두고(ferry_park) · 내 차 싣고(ferry_car, 차를 싣는 배만)
    좋은 순서 = 합계 + 걸린 시간을 돈으로 친 값 (_tag 의 '추천'과 같은 기준)
    """
    island = ctx.d_city if CITIES[ctx.d_city].get('island') else (ctx.o_city if CITIES[ctx.o_city].get('island') else None)
    if not island:
        return []
    day = ctx.start if island == ctx.d_city else ctx.end
    routes = _running_routes(island, day)
    made = {'ferry': [], 'ferry_park': [], 'ferry_car': []}
    for route in routes:
        for kind in made:
            if kind == 'ferry_car' and not route['car']:
                continue                               # 차를 못 싣는 배
            if kind == 'ferry_park' and island != ctx.d_city:
                continue                               # 섬에서 나오는 여행: 뭍에 세워 둘 내 차가 없음
            option = _safe(_plan_ferry_route, ctx, island, route, kind)
            if option:
                made[kind].append(option)
    def score(o):
        fare, minutes = o['_rank']
        return o['total'] + fare + (o['minutes'] + minutes) / 60 * TIME_VALUE_PER_HOUR * ctx.people

    show = FERRY_SHOW_AIR if CITIES[island].get('airport') else FERRY_SHOW
    out = []
    for kind, options in made.items():
        out += sorted(options, key=score)[:show[kind]]
    for o in out:
        o.pop('_rank', None)
    return out


def _tag(options, people):
    if not options:
        return None
    cheapest = min(options, key=lambda o: o['total'])
    fastest = min(options, key=lambda o: o['minutes'])
    best = min(options, key=lambda o: o['total'] + o['minutes'] / 60 * TIME_VALUE_PER_HOUR * people)
    for o in options:
        o['tags'] = ([('추천')] if o is best else []) + (['최저가'] if o is cheapest else []) + (['가장 빠름'] if o is fastest else [])
    return best.get('key') or best['mode']


# ------------------------------------------------------------------ 바깥에서 쓰는 함수
def origin_of(travel):
    """비교 기준 출발지: 고른 적이 있으면 그때 집, 아니면 travel.start_*"""
    saved = travel.access_route if isinstance(travel.access_route, dict) else {}
    if saved.get('origin'):
        return saved['origin']
    if travel.start_lat is None or travel.start_lon is None:
        return None
    return {'name': travel.start_place or '출발지', 'addr': travel.start_addr or '',
            'lat': float(travel.start_lat), 'lon': float(travel.start_lon)}


def compare(travel, people=None):
    """→ {applicable, options, recommended, note, origin, destination, people}"""
    origin = origin_of(travel)
    if not origin:
        return {'applicable': False, 'note': '출발지가 없어요. 여행 수정에서 출발지를 넣어 주세요.'}
    people = people or 1
    ck = 'access4:%s:%s:%s:%.4f:%.4f' % (travel.t_id, travel.t_start, people, origin['lat'], origin['lon'])
    hit = cache.get(ck)
    if hit:
        return hit
    ctx = _Ctx(travel, origin, people)
    if not ctx.d_city or not ctx.o_city or not ctx.dest:
        return {'applicable': False, 'note': '여행지나 출발지 도시를 알 수 없어요.'}
    if ctx.o_city == ctx.d_city or _km((origin['lat'], origin['lon']), (ctx.dest['lat'], ctx.dest['lon'])) < 30:
        return {'applicable': False, 'note': '출발지가 여행지 가까이에 있어서 장소 사이 이동만 보여 드려요.'}
    jobs = [(_plan_car,), (_plan_train,), (_plan_train, True), (_plan_bus,), (_plan_flight,), (_plan_flight, True),
            (_plan_ferries,)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda j: _safe(j[0], ctx, *j[1:]), jobs))
    options, seen = [], set()
    for found in results:
        for o in (found if isinstance(found, list) else [found]):     # 배는 항구마다 여러 개가 옴
            if not o:
                continue
            o.setdefault('key', o['mode'])                            # 고를 때 쓰는 이름 (배는 'ferry_park@묵호')
            if o['key'] not in seen:
                seen.add(o['key'])
                options.append(o)
    options.sort(key=lambda o: o['total'])
    result = {
        'applicable': bool(options), 'options': options, 'recommended': _tag(options, people), 'people': people,
        'origin': origin, 'destination': ctx.d_city, 'origin_city': ctx.o_city,
        'note': '' if options else '이 구간은 비교할 이동 방법을 찾지 못했어요.',
    }
    cache.set(ck, result, CACHE_SECONDS)
    return result


def _safe(fn, ctx, *args):
    try:
        return fn(ctx, *args)
    except Exception:                          # 한 방법이 실패해도 나머지는 보여 줌
        import logging
        logging.getLogger(__name__).exception('가는 방법 만들기 실패: %s', fn.__name__)
        return None


def choose(travel, mode, people=None):
    """고른 방법을 저장하고 첫날 출발점·시각·교통 예산·일정을 바꾼다 → 저장한 access_route"""
    from ..models import Schedule, TravelBudget
    result = compare(travel, people)
    options = result.get('options') or []
    # mode 자리에 key('ferry_park@묵호')가 와도 되고, 예전처럼 mode('ferry')만 와도 됨
    # mode 만 오면 그 종류 가운데 가장 좋은 것(합계 + 시간 값) — 채팅에서 "배 타고 갈래"라고만 한 경우
    option = next((o for o in options if o.get('key') == mode), None)
    if not option:
        same = [o for o in options if o['mode'] == mode]
        n = result.get('people') or 1
        option = min(same, key=lambda o: o['total'] + o['minutes'] / 60 * TIME_VALUE_PER_HOUR * n) if same else None
    if not option:
        return None
    mode = option['mode']
    before = travel.access_route if isinstance(travel.access_route, dict) else {}
    arrive = option['arrive']
    travel.access_way = ACCESS_WAY[mode]
    travel.access_route = option
    travel.t_way = option['t_way']
    travel.start_place = f"{arrive['name']} (도착)" if arrive['name'] != option['origin']['name'] else arrive['name']
    travel.start_addr = arrive.get('addr') or travel.start_addr
    travel.start_lat, travel.start_lon = round(arrive['lat'], 7), round(arrive['lon'], 7)
    h, m = map(int, option['ready'].split(':'))
    travel.start_time = time(h, m)
    travel.save(update_fields=['access_way', 'access_route', 't_way', 'start_place', 'start_addr',
                               'start_lat', 'start_lon', 'start_time'])
    # 교통 예산: 예전에 고른 금액은 빼고 새 금액을 더함
    budget, _ = TravelBudget.objects.get_or_create(travel=travel, category='move', defaults={'amount': 0})
    budget.amount = max(0, (budget.amount or 0) - int(before.get('total') or 0) + int(option['total']))
    budget.save(update_fields=['amount'])
    # 첫날 일정 다시 계산 (도착 뒤부터)
    first = Schedule.objects.filter(travel=travel).order_by('s_day').first()
    if first:
        from ..views import recalculate_schedule_timeline
        recalculate_schedule_timeline(first)
    return option


def summary(route):
    """access_route → '지하철 → 김포국제공항 → 비행기 → 제주국제공항 → 렌터카' (대시보드·목록용)"""
    if not isinstance(route, dict):
        return ''
    legs = route.get('go') or []
    return ' → '.join(dict.fromkeys(l['label'] for l in legs))
