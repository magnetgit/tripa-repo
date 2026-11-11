"""가는 방법 비교(access_service)용 시간표: 열차·국내항공·고속버스(TAGO), 연안여객선 + 카카오 대중교통·장소 좌표

- 🟩 timetable_service(first_trip·last_trip, 첫날 자동 맞춤)와 따로: 여기는 편 목록·역/터미널 ID·요금을 낱개로 돌려줌

- 공공데이터포털 인증키는 계정마다 하나라서 관광공사 키(TOUR_API_KEY)를 그대로 쓴다 (DATA_GO_KR_KEY가 있으면 그것).
- 열차·항공·고속버스는 여행 날짜 시간표가 미리 나온다. 여객선은 며칠 뒤까지만 나와서 먼 날짜는 '최근 운항 시각'으로.
- 목록(공항·역·터미널)은 오래, 시간표는 몇 시간만 캐시한다. 실패하면 None/[] → access_service 가 어림값으로 남긴다.
- cloud-tripa timetable_service 를 옮겨 온 것 (+ 고속버스, 장소 좌표 hub_point)
"""
import hashlib
import logging
import math
from datetime import date, timedelta

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TAGO = 'https://apis.data.go.kr/1613000/'
FERRY = 'https://apis.data.go.kr/B554035/oprt-schd-info-v2/get-oprt-schd-info-v2'
KAKAO_TRANSIT = 'https://dapi.kakao.com/v2/routing/publictraffic'
KAKAO_KEYWORD = 'https://dapi.kakao.com/v2/local/search/keyword.json'
LIST_TTL = 60 * 60 * 24 * 30
TIMETABLE_TTL = 60 * 60 * 6


def _key():
    return getattr(settings, 'DATA_GO_KR_KEY', '') or getattr(settings, 'TOUR_API_KEY', '')


def _kakao_key():
    return getattr(settings, 'KAKAO_REST_API_KEY', '')


def _items(data):
    body = ((data or {}).get('response') or {}).get('body') or {}
    items = body.get('items')
    item = items.get('item') if isinstance(items, dict) else None
    if not item:
        return []
    return item if isinstance(item, list) else [item]


def _get(url, ttl, **params):
    """공공데이터 호출 (실패하면 두 번 더, 캐시). 실패하면 None."""
    if not _key():
        return None
    ck = 'tt:' + hashlib.md5(('%s:%s' % (url, sorted(params.items()))).encode()).hexdigest()
    hit = cache.get(ck)
    if hit is not None:
        return hit
    last = None
    for _ in range(3):
        try:
            r = requests.get(url, params=dict(serviceKey=_key(), **params), timeout=15)
            if r.status_code == 200:
                data = r.json()
                cache.set(ck, data, ttl)
                return data
            logger.warning('시간표 API %s: HTTP %s', url.rsplit('/', 1)[-1], r.status_code)
            return None
        except (requests.RequestException, ValueError) as error:
            last = error
    logger.warning('시간표 API 실패 %s: %s', url.rsplit('/', 1)[-1], last)
    return None


def _hhmm(value):
    """202611200705 / 20261120050600 → '07:05'."""
    s = str(value or '')
    return '%s:%s' % (s[8:10], s[10:12]) if len(s) >= 12 else ''


def minutes_of(hhmm):
    """'07:05' → 425"""
    try:
        h, m = hhmm.split(':')
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


# ---------------------------------------------------------------- 장소 좌표 (역·공항·항구·터미널)
def hub_point(name):
    """이름 → (위도, 경도, 주소) 카카오 장소 검색 첫 결과 (한 달 캐시). 못 찾으면 None."""
    ck = 'tt:hub:' + hashlib.md5(name.encode()).hexdigest()
    hit = cache.get(ck)
    if hit is not None:
        return tuple(hit) if hit else None
    point = None
    if _kakao_key():
        try:
            r = requests.get(KAKAO_KEYWORD, headers={'Authorization': 'KakaoAK ' + _kakao_key()},
                             params={'query': name, 'size': 1}, timeout=8)
            docs = r.json().get('documents') or []
            if docs:
                d = docs[0]
                point = (float(d['y']), float(d['x']), d.get('road_address_name') or d.get('address_name') or '')
        except (requests.RequestException, ValueError, KeyError):
            return None
    cache.set(ck, list(point) if point else '', LIST_TTL)
    return point


# ---------------------------------------------------------------- 항공
def airports():
    """{'김포국제공항': 'NAARKSS', ...}"""
    return {i['airportNm']: i['airportId']
            for i in _items(_get(TAGO + 'DmstcFlightNvgInfo/GetArprtList', LIST_TTL, _type='json'))}


def airport_id(name):
    """'김포국제공항'·'제주' 같은 이름 → TAGO 공항 ID (앞 두 글자로 맞춤)."""
    head = (name or '').replace('국제', '')[:2]
    return next((aid for nm, aid in airports().items() if nm.startswith(head)), None)


def flights(dep_id, arr_id, day):
    """그날 항공편 [{'dep': '07:05', 'arr': '08:20', 'name': '아시아나 항공 OZ8911', 'fare': 61900}] 출발 순."""
    if not dep_id or not arr_id:
        return []
    data = _get(TAGO + 'DmstcFlightNvgInfo/GetFlightOpratInfoList', TIMETABLE_TTL, _type='json', numOfRows=200,
                pageNo=1, depAirportId=dep_id, arrAirportId=arr_id, depPlandTime=day.strftime('%Y%m%d'))
    rows = [{'dep': _hhmm(i.get('depPlandTime')), 'arr': _hhmm(i.get('arrPlandTime')),
             'name': ('%s %s' % (i.get('airlineNm') or '', i.get('vihicleId') or '')).strip(),
             'fare': int(i.get('economyCharge') or 0) or None}
            for i in _items(data)]
    return sorted([r for r in rows if r['dep'] and r['arr']], key=lambda r: r['dep'])


# ---------------------------------------------------------------- 열차
def _city_codes():
    return [str(i['citycode']) for i in _items(_get(TAGO + 'TrainInfo/GetCtyCodeList', LIST_TTL, _type='json'))]


def _all_stations():
    """{'서울': 'NAT010000', ...} (전국 역, 한 달 캐시)"""
    ck = 'tt:stations:all'
    hit = cache.get(ck)
    if hit:
        return hit
    found = {}
    for code in _city_codes():
        data = _get(TAGO + 'TrainInfo/GetCtyAcctoTrainSttnList', LIST_TTL, _type='json', cityCode=code,
                    numOfRows=300, pageNo=1)
        for i in _items(data):
            found[i['nodename']] = i['nodeid']
    if found:
        cache.set(ck, found, LIST_TTL)
    return found


def station_id(name):
    """'광주송정역'·'울산' → 역 ID (역 글자 빼고 같은 이름, 없으면 앞이 같은 것)"""
    base = (name or '').removesuffix('역')
    stations = _all_stations()
    return stations.get(base) or next((sid for nm, sid in stations.items() if nm.startswith(base)), None)


def trains(dep_id, arr_id, day):
    """그날 열차 [{'dep': '05:06', 'arr': '07:01', 'name': 'KTX 00801', 'grade': 'KTX', 'fare': 27600}] 출발 순."""
    if not dep_id or not arr_id:
        return []
    data = _get(TAGO + 'TrainInfo/GetStrtpntAlocFndTrainInfo', TIMETABLE_TTL, _type='json', numOfRows=200, pageNo=1,
                depPlaceId=dep_id, arrPlaceId=arr_id, depPlandTime=day.strftime('%Y%m%d'))
    rows = [{'dep': _hhmm(i.get('depplandtime')), 'arr': _hhmm(i.get('arrplandtime')),
             'grade': i.get('traingradename') or '', 'name': '%s %s' % (i.get('traingradename') or '', str(i.get('trainno') or '').lstrip('0')),
             'fare': int(i.get('adultcharge') or 0) or None}
            for i in _items(data)]
    return sorted([r for r in rows if r['dep'] and r['arr']], key=lambda r: r['dep'])


# ---------------------------------------------------------------- 고속버스
def _terminals():
    """{'서울경부': 'NAEK010', ...}"""
    ck = 'tt:terminals'
    hit = cache.get(ck)
    if hit:
        return hit
    data = _get(TAGO + 'ExpBusInfo/GetExpBusTrminlList', LIST_TTL, _type='json', numOfRows=500, pageNo=1)
    found = {i['terminalNm']: i['terminalId'] for i in _items(data)}
    if found:
        cache.set(ck, found, LIST_TTL)
    return found


def terminal_id(word):
    """'동대구'·'속초' → 터미널 ID (이름에 그 글자가 들어간 첫 터미널)"""
    terms = _terminals()
    return terms.get(word) or next((tid for nm, tid in terms.items() if word in nm), None)


def buses(dep_id, arr_id, day):
    """그날 고속버스 [{'dep': '07:00', 'arr': '11:20', 'name': '우등', 'fare': 38200}] 출발 순."""
    if not dep_id or not arr_id:
        return []
    data = _get(TAGO + 'ExpBusInfo/GetStrtpntAlocFndExpbusInfo', TIMETABLE_TTL, _type='json', numOfRows=200, pageNo=1,
                depTerminalId=dep_id, arrTerminalId=arr_id, depPlandTime=day.strftime('%Y%m%d'))
    rows = [{'dep': _hhmm(i.get('depPlandTime')), 'arr': _hhmm(i.get('arrPlandTime')),
             'name': '고속버스 ' + (i.get('gradeNm') or ''), 'fare': int(i.get('charge') or 0) or None}
            for i in _items(data)]
    return sorted([r for r in rows if r['dep'] and r['arr']], key=lambda r: r['dep'])


# ---------------------------------------------------------------- 연안여객선
def ferries(day, from_word, to_word):
    """그날 여객선 출항 [{'dep': '07:00', 'name': '퀸제누비아'}].
    먼 날짜는 시간표가 아직 없어 가장 가까운 날(오늘~3일 뒤) 운항 시각으로 대신하고 recent=True."""
    def sailings(d):
        data = _get(FERRY, TIMETABLE_TTL, pageNo=1, numOfRows=1000, dataType='JSON', rlvtYmd=d.strftime('%Y%m%d'))
        rows = []
        for i in _items(data):
            if from_word in (i.get('oport_nm') or '') and to_word in (i.get('dest_nm') or ''):
                t = str(i.get('sail_tm') or '').zfill(4)
                rows.append({'dep': '%s:%s' % (t[:2], t[2:]), 'name': i.get('psnshp_nm') or ''})
        return sorted(rows, key=lambda r: r['dep'])

    rows = sailings(day)
    if rows:
        return rows, False
    for offset in range(0, 4):
        rows = sailings(date.today() + timedelta(days=offset))
        if rows:
            return rows, True
    return [], False


# ---------------------------------------------------------------- 카카오 대중교통 (집 ↔ 역·공항)
def transit(slat, slon, elat, elon):
    """두 지점 사이 대중교통 경로 하나 (가장 빠른 것).
    {'minutes': 36, 'transfers': 1, 'fare': 1550, 'summary': '지하철 2호선 → 공항철도'} 또는 None."""
    if not _kakao_key():
        return None
    ck = 'tt:transit:%.4f:%.4f:%.4f:%.4f' % (slat, slon, elat, elon)
    hit = cache.get(ck)
    if hit is not None:
        return hit or None
    try:
        r = requests.get(KAKAO_TRANSIT, headers={'Authorization': 'KakaoAK ' + _kakao_key()},
                         params={'start_x': slon, 'start_y': slat, 'end_x': elon, 'end_y': elat}, timeout=10)
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    if data.get('status') != 'OK' or not data.get('routes'):
        cache.set(ck, '', TIMETABLE_TTL)
        return None
    route = min(data['routes'], key=lambda x: (x.get('properties') or {}).get('totalTime') or 10 ** 9)
    props = route.get('properties') or {}
    names = []
    for step in route.get('steps') or []:
        sp = step.get('properties') or {}
        if sp.get('type') in ('BUS', 'SUBWAY'):
            vehicles = [v.get('name') for v in (sp.get('vehicles') or []) if v.get('name')]
            label = ('버스 ' if sp['type'] == 'BUS' else '') + '/'.join(vehicles[:2])
            if label.strip() and label not in names:
                names.append(label.strip())
    fare = props.get('fare') or {}
    result = {
        'minutes': max(1, round((props.get('totalTime') or 0) / 60)),
        'transfers': props.get('transfers') or 0,
        'fare': fare.get('value') if isinstance(fare, dict) else None,
        'summary': ' → '.join(names[:4]),
    }
    cache.set(ck, result, TIMETABLE_TTL)
    return result
