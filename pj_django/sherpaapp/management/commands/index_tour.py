# 여행지 정보 RAG: 관광지 소개글(한국관광공사)을 미리 조각·임베딩해 embed_chunk(kind=tour)에 넣기 (🟩 11/11)
#   python manage.py index_tour                 # 부산 장소 표 + 데모 여행지 표의 관광지 전부
#   python manage.py index_tour --region 부산 --limit 20
#   python manage.py index_tour --copy-from text-embedding-3-small   # 시연 PC(설정 B): 관광공사 안 부르고 다시 임베딩만
#   python manage.py index_tour --check-wrong   # 🟧 11/16 다른 지역 장소가 붙은 줄 찾기만 (관광공사 호출 없음)
#   python manage.py index_tour --fix-wrong     # 그 줄을 지우고, 거리 확인을 넣은 규칙으로 다시 넣기 (의심 줄만 관광공사 호출)
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
        parser.add_argument('--check-wrong', action='store_true',
                            help='다른 지역의 같은 이름 장소가 붙은 줄을 찾아 보여 주기만 (예: 전주 신중앙시장 → 목포 신중앙시장)')
        parser.add_argument('--fix-wrong', action='store_true',
                            help='--check-wrong 으로 찾은 줄을 지우고 다시 넣기 (같은 지역에서 못 찾으면 비워 둠)')
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

    def _wrong(self, spots, fix):
        """다른 지역 장소가 붙은 줄 찾기 (fix 면 지우고 다시 넣기)"""
        found = fixed = emptied = kept = 0
        for region, name, lat, lon in spots:
            wrong = tour_rag.wrong_region(region, name, lat, lon)
            if not wrong:
                continue
            found += 1
            content_id, saved_name, addr = wrong
            self.stdout.write('  %s %s → 붙어 있던 것: %s (%s)' % (region, name, saved_name, addr))
            if not fix:
                continue
            # 거리 확인을 넣은 규칙으로 다시 찾아본다. 같은 곳이 나오면 맞는 것 (국립공원처럼 주소만 옆 지역) → 그대로 둠
            try:
                item = tour_rag.find_item(name, lat, lon)
            except tour_rag.TourQuotaError:
                self.stderr.write(self.style.ERROR('관광공사 API 오늘 사용량을 다 써서 멈췄어요 (%s). 내일 다시' % name))
                return
            if item and str(item.get('contentid')) == str(content_id):
                kept += 1
                self.stdout.write('      다시 찾아도 같은 곳 → 그대로 둠')
                continue
            # 잘못 붙은 글을 지운다. (그 글이 진짜 필요한 다른 지역 장소가 목록에 있으면 다음 index_tour 때 다시 들어감)
            EmbedChunk.objects.filter(kind=tour_rag.KIND, ref_id=content_id).delete()
            try:
                result = tour_rag.index_place(name, lat, lon)
            except EmbedError as error:
                self.stderr.write(self.style.ERROR('임베딩 실패 (%s): %s' % (name, error)))
                return
            except tour_rag.TourQuotaError:
                self.stderr.write(self.style.ERROR('관광공사 API 오늘 사용량을 다 써서 멈췄어요 (%s). 내일 다시' % name))
                return
            if result:
                fixed += 1
                self.stdout.write('      다시 넣음 → %s 조각 %d' % (result['name'], result['chunks']))
            else:
                emptied += 1
                self.stdout.write('      같은 지역에서는 관광공사에 없음 → 비워 둠')
        if fix:
            self.stdout.write(self.style.SUCCESS(
                '의심 %d곳 → 다시 넣음 %d곳 · 비워 둠 %d곳 · 맞는 곳이라 그대로 %d곳' % (found, fixed, emptied, kept)))
        else:
            self.stdout.write(self.style.SUCCESS('주소가 다른 지역인 줄 %d곳 (고치려면 --fix-wrong)' % found))

    def handle(self, *args, **opts):
        if opts['copy_from']:
            try:
                return self._copy(opts['copy_from'])
            except EmbedError as error:
                self.stderr.write(self.style.ERROR('임베딩 실패: %s — .env AI 설정 확인' % error))
                return

        spots = self._spots(opts['region'])
        if opts['check_wrong'] or opts['fix_wrong']:
            return self._wrong(spots, opts['fix_wrong'])
        if opts['limit']:
            spots = spots[:opts['limit']]

        done = skipped = missing = 0
        for region, name, lat, lon in spots:
            if not opts['again'] and tour_rag.indexed_id(name, lat, lon):
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
