# 여행지 정보 RAG: 관광지 소개글(한국관광공사)을 미리 조각·임베딩해 embed_chunk(kind=tour)에 넣기 (🟩 11/11)
#   python manage.py index_tour                 # 부산 장소 표 + 데모 여행지 표의 관광지 전부
#   python manage.py index_tour --region 부산 --limit 20
#   python manage.py index_tour --copy-from text-embedding-3-small   # 시연 PC(설정 B): 관광공사 안 부르고 다시 임베딩만
# 이미 넣은 곳은 건너뜀 (--again 이면 다시). 안 넣은 곳도 채팅에서 처음 물을 때 넣어져요
# ⚠️ 한 곳에 관광공사 API 2~3번 → 400곳이면 1,000번 넘음. 같은 키를 사진·운영시간도 쓰니 --limit 로 나눠서
#    (사용량을 다 쓰면 429 → 바로 멈춤, 다음 날 이어서)
import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from sherpaapp.models import EmbedChunk
from sherpaapp.services import busan_spots, embed_service, tour_rag
from sherpaapp.services.embed_service import EmbedError

DEMO_CSV = Path(settings.BASE_DIR).parent / 'docs' / 'data' / 'demo_spots_regions.csv'
SKIP_CONCEPTS = ('음식', '카페', '숙소', '숙박')     # 식당·카페·숙소는 소개글이 거의 없음


class Command(BaseCommand):
    help = '관광공사 소개글을 embed_chunk(kind=tour)에 넣기 (여행지 정보 RAG)'

    def add_arguments(self, parser):
        parser.add_argument('--region', default='', help='이 지역만 (예: 부산)')
        parser.add_argument('--limit', type=int, default=0, help='최대 몇 곳 (0 = 전부)')
        parser.add_argument('--again', action='store_true', help='이미 넣은 곳도 다시')
        parser.add_argument('--copy-from', default='', metavar='MODEL',
                            help='관광공사를 안 부르고, 다른 임베딩 모델로 이미 넣은 글을 지금 모델로 다시 임베딩만 '
                                 '(예: --copy-from text-embedding-3-small → 설정 B bge-m3 용)')

    def _copy(self, source_model):
        """이미 저장한 소개글 조각(다른 모델)을 지금 모델로 다시 임베딩 → 관광공사 API 0번"""
        rows = EmbedChunk.objects.filter(kind=tour_rag.KIND, model=source_model).order_by('ref_id', 'seq')
        groups = {}
        for row in rows:
            groups.setdefault(row.ref_id, {'meta': row.meta, 'texts': []})['texts'].append(row.text)
        saved = 0
        for ref_id, group in groups.items():
            saved += embed_service.save_chunks(tour_rag.KIND, ref_id, group['texts'], meta=group['meta'])
        self.stdout.write(self.style.SUCCESS(
            '%s → %s: 장소 %d곳 · 조각 %d개 다시 임베딩 (관광공사 호출 없음)'
            % (source_model, embed_service._model(), len(groups), saved)))

    def _spots(self, region):
        spots = []
        if not region or region == '부산':
            for row in busan_spots.load_rows():
                if row['concept'] not in SKIP_CONCEPTS:
                    spots.append(('부산', row['name'], row['lat'], row['lon']))
        if DEMO_CSV.exists():
            with open(DEMO_CSV, encoding='utf-8-sig', newline='') as f:
                for raw in csv.DictReader(f):
                    if (raw.get('컨셉') or '') in SKIP_CONCEPTS or (region and raw.get('지역') != region):
                        continue
                    try:
                        spots.append((raw['지역'], raw['이름'], float(raw['위도']), float(raw['경도'])))
                    except (KeyError, TypeError, ValueError):
                        continue
        seen, unique = set(), []
        for spot in spots:
            if spot[1] not in seen:
                seen.add(spot[1])
                unique.append(spot)
        return unique

    def handle(self, *args, **opts):
        if opts['copy_from']:
            try:
                return self._copy(opts['copy_from'])
            except EmbedError as error:
                self.stderr.write(self.style.ERROR('임베딩 실패: %s — .env AI 설정 확인' % error))
                return

        spots = self._spots(opts['region'])
        if opts['limit']:
            spots = spots[:opts['limit']]

        done = skipped = missing = 0
        for region, name, lat, lon in spots:
            if not opts['again'] and tour_rag.indexed_id(name):
                skipped += 1
                continue
            try:
                result = tour_rag.index_place(name, lat, lon)
            except EmbedError as error:
                self.stderr.write(self.style.ERROR('임베딩 실패 (%s): %s — .env AI 설정 확인' % (name, error)))
                return
            except tour_rag.TourQuotaError:
                self.stderr.write(self.style.ERROR(
                    '관광공사 API 오늘 사용량을 다 써서 멈췄어요 (%s 에서 멈춤, 이번에 넣음 %d곳). 내일 다시 돌리면 이어서 넣어요' % (name, done)))
                return
            if result:
                done += 1
                self.stdout.write('  %s %s → %s 조각 %d' % (region, name, result['name'], result['chunks']))
            else:
                missing += 1

        self.stdout.write(self.style.SUCCESS(
            '넣음 %d곳 · 이미 있음 %d곳 · 관광공사에 없음 %d곳 (전체 %d곳)' % (done, skipped, missing, len(spots))
        ))
