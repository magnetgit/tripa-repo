"""seed_demo 가 쓰는 '여행지까지 가는 길' 만들기 (데모 전용, 실제 시간표·요금 아님).

- 회원마다 사는 곳(HOMES)이 있고, 여행은 집에서 출발해요.
- plan_route(rnd, home_city, dest) → (access_way, legs, t_way)
  access_way: car(자차)·ktx·train_transfer(환승)·bus(고속버스)·flight·ferry
  legs: [{mode, label, from, to, minutes}] — 시각(depart·arrive)은 with_times() 가 붙여요.
  t_way: 여행지 안에서 다니는 방법 (앱과 같은 값: car·public_transport)
- 제주: 가까운 공항 경유 비행기 / 배(차를 싣거나 사람만) / 제주 안에서는 렌터카·버스
- 울릉도: 포항·강릉·묵호·후포에서 배
- 육지끼리: 자차 / KTX 바로 / 오송·서울 환승 / 고속버스 / 먼 곳은 비행기, 내린 뒤 렌터카도 섞음
"""
import math
from datetime import datetime, timedelta

# 사는 곳: (도시, 이름, 주소, 위도, 경도, 비중)
HOMES = [
    ('서울', '서울 마포구 망원동', '서울 마포구 망원로 50', 37.5559, 126.9018, 12),
    ('서울', '서울 강남구 역삼동', '서울 강남구 테헤란로 152', 37.5003, 127.0365, 12),
    ('서울', '서울 노원구 상계동', '서울 노원구 동일로 1414', 37.6549, 127.0613, 8),
    ('인천', '인천 부평구 부평동', '인천 부평구 부평대로 25', 37.4895, 126.7244, 7),
    ('대전', '대전 유성구 봉명동', '대전 유성구 계룡로 87', 36.3563, 127.3461, 7),
    ('청주', '충북 청주시 흥덕구 복대동', '충북 청주시 흥덕구 대농로 17', 36.6357, 127.4302, 4),
    ('대구', '대구 수성구 범어동', '대구 수성구 달구벌대로 2450', 35.8588, 128.6254, 7),
    ('부산', '부산 해운대구 우동', '부산 해운대구 센텀중앙로 55', 35.1691, 129.1310, 7),
    ('부산', '부산 부산진구 부전동', '부산 부산진구 중앙대로 672', 35.1578, 129.0600, 5),
    ('울산', '울산 남구 삼산동', '울산 남구 삼산로 261', 35.5389, 129.3381, 5),
    ('광주', '광주 북구 용봉동', '광주 북구 용봉로 77', 35.1764, 126.9055, 7),
    ('제주', '제주 제주시 연동', '제주 제주시 연동 312-1', 33.4890, 126.4983, 6),
]

# 도시 가운데 좌표 (걸리는 시간 어림용)
CITY_POS = {
    '서울': (37.5665, 126.9780), '인천': (37.4563, 126.7052), '대전': (36.3504, 127.3845), '청주': (36.6424, 127.4890),
    '대구': (35.8714, 128.6014), '부산': (35.1796, 129.0756), '울산': (35.5384, 129.3114), '광주': (35.1595, 126.8526),
    '제주': (33.4996, 126.5312), '강릉': (37.7519, 128.8761), '속초': (38.2070, 128.5918), '춘천': (37.8813, 127.7298),
    '경주': (35.8562, 129.2247), '여수': (34.7604, 127.6622), '전주': (35.8242, 127.1480), '울릉도': (37.4844, 130.9057),
    '목포': (34.8118, 126.3922), '완도': (34.3110, 126.7550), '포항': (36.0190, 129.3435),
}

# KTX(·ITX) 역과 노선. 같은 노선이거나 한쪽이 서울이면 바로, 아니면 오송(경부·호남·전라) 또는 서울(강릉선·경춘선) 환승
STATIONS = {
    '서울': ('서울역', '*'), '대전': ('대전역', '경부'), '청주': ('오송역', '*'), '대구': ('동대구역', '경부'),
    '부산': ('부산역', '경부'), '울산': ('울산역', '경부'), '경주': ('신경주역', '경부'), '포항': ('포항역', '경부'),
    '광주': ('광주송정역', '호남'), '목포': ('목포역', '호남'), '전주': ('전주역', '전라'), '여수': ('여수엑스포역', '전라'),
    '강릉': ('강릉역', '강릉'), '춘천': ('춘천역', '경춘'),
}
TERMINALS = {
    '서울': '서울고속버스터미널', '인천': '인천종합버스터미널', '대전': '대전복합터미널', '청주': '청주고속버스터미널',
    '대구': '동대구복합환승센터', '부산': '부산종합버스터미널', '울산': '울산고속버스터미널', '광주': '유스퀘어(광주종합버스터미널)',
    '강릉': '강릉고속버스터미널', '속초': '속초고속버스터미널', '춘천': '춘천시외버스터미널', '경주': '경주고속버스터미널',
    '여수': '여수종합버스터미널', '전주': '전주고속버스터미널', '포항': '포항시외버스터미널',
}
# 가까운 공항
AIRPORT = {
    '서울': '김포국제공항', '인천': '김포국제공항', '대전': '청주국제공항', '청주': '청주국제공항', '대구': '대구국제공항',
    '부산': '김해국제공항', '울산': '울산공항', '광주': '광주공항', '여수': '여수공항', '강릉': '양양국제공항',
    '속초': '양양국제공항', '경주': '포항경주공항', '포항': '포항경주공항', '제주': '제주국제공항',
}
# 공항에서 그 도시까지 (탈것, 분). 공항이 그 도시에 있으면 시내로 가는 길
AIRPORT_TO_CITY = {
    '서울': ('subway', '지하철 5·9호선', 40), '인천': ('subway', '공항철도·인천 1호선', 55), '대전': ('bus', '공항 리무진', 70),
    '청주': ('bus', '시내버스', 35), '대구': ('bus', '시내버스', 25), '부산': ('subway', '부산김해경전철·지하철', 45),
    '울산': ('bus', '시내버스', 25), '광주': ('subway', '광주 지하철 1호선', 25), '여수': ('bus', '공항 리무진', 35),
    '강릉': ('bus', '공항 셔틀버스', 50), '속초': ('bus', '공항 셔틀버스', 30), '경주': ('bus', '공항 리무진', 50),
    '제주': ('bus', '급행버스', 30),
}
# 제주 가는 배: 출발 항구, 그 항구가 있는 도시, 배 시간(분), 밤배인지
JEJU_FERRIES = {
    '인천': ('인천항연안여객터미널', '인천', 780, True), '서울': ('목포항국제여객터미널', '목포', 270, False),
    '광주': ('완도항여객선터미널', '완도', 170, False), '대전': ('목포항국제여객터미널', '목포', 270, False),
    '청주': ('목포항국제여객터미널', '목포', 270, False), '부산': ('부산항연안여객터미널', '부산', 720, True),
    '울산': ('부산항연안여객터미널', '부산', 720, True), '대구': ('부산항연안여객터미널', '부산', 720, True),
}
# 울릉도 가는 배: (항구, 그 항구 도시, 배 시간)
ULLEUNG_PORTS = [('포항여객선터미널', '포항', 200), ('강릉항여객터미널', '강릉', 180),
                 ('묵호항여객선터미널', '강릉', 170), ('후포항여객선터미널', '포항', 140)]
MODE_LABEL = {'car': '자차', 'rental': '렌터카', 'ktx': 'KTX', 'itx': 'ITX-청춘', 'bus': '고속버스', 'subway': '지하철',
              'local_bus': '시내버스', 'flight': '비행기', 'ferry': '배', 'taxi': '택시', 'walk': '걷기'}


def _km(a, b):
    (la1, lo1), (la2, lo2) = CITY_POS[a], CITY_POS[b]
    p = math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _leg(mode, frm, to, minutes, label=None):
    return {'mode': mode, 'label': label or MODE_LABEL[mode], 'from': frm, 'to': to, 'minutes': int(minutes)}


def _car_min(a, b):
    return _km(a, b) * 1.3 / 80 * 60 + 15


def _to_hub(rnd, city, home, hub):
    """집 → 역·터미널·공항·항구 (도시 안 이동)"""
    if city in ('서울', '인천', '부산', '대구', '대전', '광주'):
        mode = rnd.choice(['subway', 'subway', 'local_bus', 'taxi'])
    else:
        mode = rnd.choice(['local_bus', 'taxi'])
    return _leg(mode, home, hub, rnd.randint(20, 50))


def _arrive_local(rnd, dest, frm):
    """내린 곳 → 여행지 안: 렌터카(t_way car) 또는 대중교통(t_way public_transport)"""
    rental = .6 if dest in ('제주', '울릉도') else .3
    if rnd.random() < rental:
        return [_leg('rental', frm, f'{dest} 렌터카 영업소', rnd.randint(15, 30), '렌터카 인수')], 'car'
    if dest == '제주':                                       # 제주 안은 급행·간선버스로
        return [_leg('local_bus', frm, '제주 시내(숙소)', rnd.randint(25, 50), rnd.choice(['급행버스', '간선버스']))], 'public_transport'
    if dest == '울릉도':
        return [_leg('local_bus', frm, '울릉 숙소', rnd.randint(10, 30), '울릉 순환버스')], 'public_transport'
    return [], 'public_transport'


def _ktx_legs(rnd, frm_city, to_city):
    """KTX 구간 (같은 노선·서울 출발이면 바로, 아니면 환승). → (legs, 환승했는지)"""
    s1, l1 = STATIONS[frm_city]
    s2, l2 = STATIONS[to_city]
    kind = 'itx' if '경춘' in (l1, l2) else 'ktx'
    if kind == 'itx' and frm_city == '서울':
        s1 = '용산역'
    if l1 == l2 or '*' in (l1, l2):
        return [_leg(kind, s1, s2, _km(frm_city, to_city) * 1.15 / 170 * 60 + 15)], False
    via, via_city = ('서울역', '서울') if {'강릉', '경춘'} & {l1, l2} else ('오송역', '청주')
    if kind == 'itx':
        via = '용산역'
    return [_leg('ktx', s1, via, _km(frm_city, via_city) * 1.15 / 170 * 60 + 15),
            _leg(kind, via, s2, _km(via_city, to_city) * 1.15 / 170 * 60 + 25)], True


def plan_route(rnd, home_city, home, dest):
    """→ (access_way, legs, t_way)"""
    # 1) 제주로
    if dest == '제주':
        if rnd.random() < .75:                                  # 가까운 공항 경유 비행기
            ap = AIRPORT[home_city]
            legs = [_to_hub(rnd, home_city, home, ap) if home_city in ('서울', '인천')
                    else _leg(rnd.choice(['car', 'local_bus', 'taxi']), home, ap, rnd.randint(20, 60))]
            if legs[0]['mode'] == 'car':
                legs[0]['label'] = '자차 (공항 주차)'
            legs.append(_leg('flight', ap, '제주국제공항', rnd.randint(55, 70)))
            more, way = _arrive_local(rnd, '제주', '제주국제공항')
            return 'flight', legs + more, way
        port, port_city, sail, night = JEJU_FERRIES[home_city]
        if rnd.random() < .5:                                   # 차를 싣고 가는 배
            legs = [_leg('car', home, port, _car_min(home_city, port_city) if port_city != home_city else 30),
                    _leg('ferry', port, '제주항', sail, '배 (차량 선적)' + (' · 밤배' if night else ''))]
            return 'ferry', legs, 'car'
        if port_city in STATIONS and home_city in STATIONS and port_city != home_city:
            legs = [_to_hub(rnd, home_city, home, STATIONS[home_city][0])] + _ktx_legs(rnd, home_city, port_city)[0]
            legs.append(_leg('taxi', STATIONS[port_city][0], port, 15))
        elif port_city != home_city:
            legs = [_to_hub(rnd, home_city, home, TERMINALS[home_city]),
                    _leg('bus', TERMINALS[home_city], port, _km(home_city, port_city) * 1.3 / 75 * 60 + 20, '시외버스')]
        else:
            legs = [_to_hub(rnd, home_city, home, port)]
        legs.append(_leg('ferry', port, '제주항', sail, '배' + (' · 밤배' if night else '')))
        more, way = _arrive_local(rnd, '제주', '제주항')
        return 'ferry', legs + more, way

    # 2) 제주에서 다른 곳으로
    if home_city == '제주':
        if dest == '울릉도':
            port, port_city, sail = ULLEUNG_PORTS[0]
            legs = [_leg('taxi', home, '제주국제공항', 20), _leg('flight', '제주국제공항', '포항경주공항', 70),
                    _leg('local_bus', '포항경주공항', port, 40, '리무진·시내버스'), _leg('ferry', port, '울릉 도동항', sail)]
            more, way = _arrive_local(rnd, dest, '울릉 도동항')
            return 'flight', legs + more, way
        if rnd.random() < .15 and dest in ('광주', '여수', '전주', '부산', '대구', '울산', '경주'):   # 차 싣고 배로 육지
            port, city, sail = (('부산항연안여객터미널', '부산', 720) if dest in ('부산', '대구', '울산', '경주')
                                else ('완도항여객선터미널', '완도', 170))
            legs = [_leg('car', home, '제주항', 20), _leg('ferry', '제주항', port, sail, '배 (차량 선적)'),
                    _leg('car', port, dest, _car_min(city, dest) if city != dest else 20)]
            return 'ferry', legs, 'car'
        ap = AIRPORT.get(dest)
        legs = [_leg(rnd.choice(['taxi', 'local_bus']), home, '제주국제공항', rnd.randint(15, 30))]
        if ap:
            legs.append(_leg('flight', '제주국제공항', ap, rnd.randint(55, 75)))
            fly_city = dest
        else:                                                   # 공항 없는 곳: 김포·광주 내려서 KTX·버스로 갈아탐
            ap, fly_city = ('광주공항', '광주') if dest == '전주' else ('김포국제공항', '서울')
            legs.append(_leg('flight', '제주국제공항', ap, rnd.randint(55, 70)))
        if fly_city == dest:
            if rnd.random() < .35:
                legs.append(_leg('rental', ap, f'{dest} 렌터카 영업소', 20, '렌터카 인수'))
                return 'flight', legs, 'car'
            mode, label, mins = AIRPORT_TO_CITY.get(dest, ('local_bus', '시내버스', 30))
            legs.append(_leg(mode, ap, f'{dest} 시내', mins, label))
            return 'flight', legs, 'public_transport'
        hub = STATIONS.get(fly_city, ('', ''))[0]
        if dest in STATIONS and hub:
            legs.append(_leg('subway', ap, hub, 35, '지하철'))
            legs += _ktx_legs(rnd, fly_city, dest)[0]
            return 'train_transfer', legs, 'public_transport'
        legs.append(_leg('subway', ap, TERMINALS[fly_city], 35, '지하철'))
        legs.append(_leg('bus', TERMINALS[fly_city], TERMINALS.get(dest, f'{dest} 터미널'), _km(fly_city, dest) * 1.3 / 75 * 60 + 15))
        return 'train_transfer', legs, 'public_transport'

    # 3) 울릉도로
    if dest == '울릉도':
        port, port_city, sail = rnd.choice(ULLEUNG_PORTS)
        if rnd.random() < .4:
            legs = [_leg('car', home, port, _car_min(home_city, port_city), '자차 (항구 주차)')]
        elif port_city in STATIONS and home_city in STATIONS and port_city != home_city:
            legs = [_to_hub(rnd, home_city, home, STATIONS[home_city][0])] + _ktx_legs(rnd, home_city, port_city)[0]
            legs.append(_leg('local_bus', STATIONS[port_city][0], port, rnd.randint(20, 40)))
        else:
            legs = [_to_hub(rnd, home_city, home, TERMINALS[home_city]),
                    _leg('bus', TERMINALS[home_city], TERMINALS[port_city], _km(home_city, port_city) * 1.3 / 75 * 60 + 15),
                    _leg('local_bus', TERMINALS[port_city], port, 25)]
        legs.append(_leg('ferry', port, '울릉 도동항', sail))
        more, way = _arrive_local(rnd, dest, '울릉 도동항')
        return 'ferry', legs + more, way

    # 4) 육지끼리
    km = _km(home_city, dest)
    options = [('car', 35), ('bus', 15)]
    if home_city in STATIONS and dest in STATIONS:
        options.append(('ktx', 30))
    elif dest in ('속초', '인천') or home_city == '인천':
        options.append(('train_transfer', 20))
    if km > 250 and home_city in AIRPORT and dest in AIRPORT and AIRPORT[home_city] != AIRPORT[dest]:
        options.append(('flight', 10))
    way = rnd.choices([o for o, _ in options], weights=[w for _, w in options])[0]
    if way == 'car':
        return 'car', [_leg('car', home, f'{dest} 도착', _car_min(home_city, dest))], 'car'
    if way == 'bus':
        legs = [_to_hub(rnd, home_city, home, TERMINALS.get(home_city, f'{home_city} 터미널')),
                _leg('bus', TERMINALS.get(home_city, f'{home_city} 터미널'), TERMINALS.get(dest, f'{dest} 터미널'),
                     km * 1.3 / 75 * 60 + 15)]
        more, t_way = _arrive_local(rnd, dest, TERMINALS.get(dest, f'{dest} 터미널'))
        return 'bus', legs + more, t_way
    if way == 'flight':
        a1, a2 = AIRPORT[home_city], AIRPORT[dest]
        legs = [_to_hub(rnd, home_city, home, a1), _leg('flight', a1, a2, rnd.randint(50, 65))]
        more, t_way = _arrive_local(rnd, dest, a2)
        if not more:
            mode, label, mins = AIRPORT_TO_CITY.get(dest, ('local_bus', '시내버스', 30))
            more = [_leg(mode, a2, f'{dest} 시내', mins, label)]
        return 'flight', legs + more, t_way
    if way == 'ktx':
        legs = [_to_hub(rnd, home_city, home, STATIONS[home_city][0])]
        ktx, moved = _ktx_legs(rnd, home_city, dest)
        more, t_way = _arrive_local(rnd, dest, STATIONS[dest][0])
        return ('train_transfer' if moved else 'ktx'), legs + ktx + more, t_way
    # 환승: 서울을 거쳐 속초(버스)·인천(지하철), 인천 출발은 서울까지 지하철
    if home_city == '인천':
        legs = [_leg('subway', home, '서울역', 60, '인천 1호선·공항철도')]
        if dest in STATIONS:
            legs += _ktx_legs(rnd, '서울', dest)[0]
        else:
            legs += [_leg('subway', '서울역', TERMINALS['서울'], 25),
                     _leg('bus', TERMINALS['서울'], TERMINALS.get(dest, f'{dest} 터미널'), _km('서울', dest) * 1.3 / 75 * 60 + 15)]
        more, t_way = _arrive_local(rnd, dest, legs[-1]['to'])
        return 'train_transfer', legs + more, t_way
    if dest == '인천':
        legs = [_to_hub(rnd, home_city, home, STATIONS.get(home_city, ('', ''))[0] or TERMINALS[home_city])]
        legs += _ktx_legs(rnd, home_city, '서울')[0] if home_city in STATIONS else [
            _leg('bus', TERMINALS[home_city], TERMINALS['서울'], _km(home_city, '서울') * 1.3 / 75 * 60 + 15)]
        legs.append(_leg('subway', legs[-1]['to'], '인천 시내', 60, '지하철 1호선·공항철도'))
        return 'train_transfer', legs, 'public_transport'
    # 속초: KTX로 서울 → 지하철 → 고속버스 (서울에 살면 바로 고속버스)
    if home_city == '서울':
        legs = [_to_hub(rnd, home_city, home, TERMINALS['서울'])]
    elif home_city in STATIONS:
        legs = [_to_hub(rnd, home_city, home, STATIONS[home_city][0])] + _ktx_legs(rnd, home_city, '서울')[0]
        legs.append(_leg('subway', '서울역', TERMINALS['서울'], 25))
    else:
        legs = [_to_hub(rnd, home_city, home, TERMINALS[home_city])]
    frm = TERMINALS['서울'] if home_city in STATIONS or home_city == '서울' else TERMINALS[home_city]
    legs.append(_leg('bus', frm, TERMINALS['속초'], 160 if frm == TERMINALS['서울'] else _km(home_city, '속초') * 1.3 / 75 * 60 + 15))
    more, t_way = _arrive_local(rnd, dest, TERMINALS['속초'])
    return 'train_transfer', legs + more, t_way


def with_times(rnd, legs, day):
    """구간마다 출발·도착 시각을 붙인다. 밤배(10시간 넘는 배)는 전날 저녁에 떠남. → 마지막 도착 시각"""
    total = sum(leg['minutes'] for leg in legs) + 15 * (len(legs) - 1)      # 갈아타는 시간 15분씩
    night = [i for i, leg in enumerate(legs) if leg['mode'] == 'ferry' and leg['minutes'] >= 600]
    if night:                                   # 밤배는 전날 19:30 출항 → 그 앞 구간만큼 일찍 집을 나섬
        i = night[0]
        at = datetime.combine(day - timedelta(days=1), datetime.min.time()) + timedelta(hours=19, minutes=30)
        at -= timedelta(minutes=sum(leg['minutes'] for leg in legs[:i]) + 15 * i)
    else:
        at = datetime.combine(day, datetime.min.time()) + timedelta(hours=rnd.choice([6, 7, 7, 8, 9]),
                                                                    minutes=rnd.choice([0, 10, 20, 30, 40, 50]))
    for a, b in zip(legs, legs[1:]):            # 도시 안 이동은 다음 구간 출발지까지 (예: 지하철 → 용산역)
        if a['to'] != b['from'] and a['mode'] in ('subway', 'local_bus', 'taxi', 'car'):
            a['to'] = b['from']
    for leg in legs:
        start_day = at.date()
        leg['depart'] = at.strftime('%H:%M')
        at += timedelta(minutes=leg['minutes'])
        leg['arrive'] = at.strftime('%H:%M')
        if at.date() != start_day:
            leg['overnight'] = True                 # 다음 날 도착 (밤배)
        at += timedelta(minutes=15)
    return at - timedelta(minutes=15), total


# ---------------------------------------------------------------- 실제 선택(access_service)과 같은 모양으로
BIG = ('flight', 'ferry', 'ktx', 'itx', 'bus')


def _title(way, legs, t_way):
    if way == 'flight':
        return 'flight_rent' if t_way == 'car' else 'flight'
    if way == 'ferry':
        return 'ferry_car' if any('선적' in l['label'] for l in legs) else 'ferry'
    if way == 'ktx':
        return 'ktx_rent' if t_way == 'car' else 'ktx'
    return way


def _point(name, home, dest):
    """구간 끝 이름 → [위도, 경도] (집이면 집 좌표, 역·공항·항구는 카카오 장소 검색, 모르면 여행지 가운데)"""
    from sherpaapp.services import transport_timetable as timetable_service
    if name == home[1]:
        return [home[3], home[4]]
    if any(w in name for w in ('공항', '역', '항', '터미널', '센터')):
        p = timetable_service.hub_point(name)
        if p:
            return [round(p[0], 6), round(p[1], 6)]
    if any(w in name for w in ('시내', '숙소', '렌터카 영업소', '도착')) or name.startswith(dest):
        lat, lon = CITY_POS.get(dest, CITY_POS['서울'])
        return [lat, lon]
    p = timetable_service.hub_point(name)
    if p:
        return [round(p[0], 6), round(p[1], 6)]
    city = next((c for c in CITY_POS if c in name), dest)
    return list(CITY_POS[city])


def access_route(way, legs, t_way, home, dest, people, start_time):
    """plan_route·with_times 결과 → Travel.access_route (access_service.compare 옵션과 같은 키)
    → (access_route, 도착 거점 {name, addr, lat, lon})"""
    from sherpaapp.services.access_service import TITLES
    for leg in legs:
        leg['from_pt'] = _point(leg['from'], home, dest)
        leg['to_pt'] = _point(leg['to'], home, dest)
        leg.setdefault('fare', 0)
        leg.setdefault('detail', '')
        leg['real'] = False
    main = [l for l in legs if l['mode'] in BIG]
    if main:
        end = main[-1]
    else:
        end = legs[-1]
    arrive = {'name': end['to'] if main else f'{dest} 시내', 'addr': '', 'lat': end['to_pt'][0], 'lon': end['to_pt'][1]}
    back = []
    for leg in reversed([l for l in legs if l['mode'] != 'rental']):
        back.append(dict(leg, **{'from': leg['to'], 'to': leg['from'], 'from_pt': leg['to_pt'], 'to_pt': leg['from_pt'],
                                 'overnight': False}))
    at = 18 * 60
    for leg in back:                            # 마지막 날 저녁 6시쯤 출발
        leg['depart'] = '%02d:%02d' % (at // 60 % 24, at % 60)
        at += leg['minutes']
        leg['arrive'] = '%02d:%02d' % (at // 60 % 24, at % 60)
        at += 15
    mode = _title(way, legs, t_way)
    minutes = sum(l['minutes'] for l in legs) + 15 * (len(legs) - 1)
    route = {'mode': mode, 'title': TITLES.get(mode, mode), 'total': 0, 'per_person': 0, 'minutes': minutes,
             'people': people, 'items': [], 'real': False,
             'origin': {'name': home[1], 'addr': home[2], 'lat': home[3], 'lon': home[4]},
             'arrive': arrive, 'ready': start_time.strftime('%H:%M'), 't_way': t_way,
             'go': legs, 'back': back, 'note': '데모 데이터 (어림 시간)', 'tags': []}
    return route, arrive
