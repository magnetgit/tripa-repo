"""리뷰 사진 (🟧 11/20) — 장소 리뷰에 사진 1장, 장소 대표 사진 1순위

올리기
  - JPEG·PNG·WEBP·GIF(첫 장)·BMP, 8MB 까지
  - 긴 변 1280px 로 줄이고 JPEG 로 다시 저장 → 사진 속 위치(GPS) 같은 EXIF 정보는 남지 않음
  - 폰 사진이 옆으로 누워 있으면 EXIF 방향대로 바로 세움
저장: review_photo 표 (리뷰 1개당 1장, DB 에 그대로). 리뷰를 지우면 같이 지워짐
보여 주기: GET /review_photo/<rv_id>/  (views.review_photo)
대표 사진: photo_service 가 카카오 장소 ID 로 리뷰 사진을 먼저 찾음 → {"url": "/review_photo/12/?v=3", "source": "review"}
"""
import io

from django.db.models import Count
from django.urls import reverse

from sherpaapp.models import ReviewPhoto

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_SIDE = 1280
MAX_PIXELS = 40_000_000           # 너무 큰 그림(압축 폭탄) 막기
QUALITY = 82
FORMATS = ('JPEG', 'MPO', 'PNG', 'WEBP', 'GIF', 'BMP')

TOO_BIG = '사진은 8MB까지 올릴 수 있어요.'
NOT_IMAGE = '사진 파일(JPG·PNG·WEBP)만 올릴 수 있어요.'


def clean_upload(upload):
    """올린 파일 → (JPEG 바이트, 너비, 높이). 사진이 아니거나 너무 크면 ValueError(안내 문구)"""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if upload.size > MAX_UPLOAD_BYTES:
        raise ValueError(TOO_BIG)
    raw = upload.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError(TOO_BIG)
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            if probe.format not in FORMATS:
                raise ValueError(NOT_IMAGE)
            if probe.width * probe.height > MAX_PIXELS:
                raise ValueError('사진이 너무 커요. 더 작은 사진으로 올려 주세요.')
            probe.verify()                       # 깨진 파일 거르기
        with Image.open(io.BytesIO(raw)) as image:
            image.seek(0)                        # GIF 는 첫 장
            image = ImageOps.exif_transpose(image)
            if image.mode not in ('RGB', 'L'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                rgba = image.convert('RGBA')
                background.paste(rgba, mask=rgba.split()[-1])
                image = background
            image = image.convert('RGB')
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            out = io.BytesIO()
            image.save(out, 'JPEG', quality=QUALITY, optimize=True)   # exif 를 넘기지 않아서 정보가 빠짐
            return out.getvalue(), image.width, image.height
    except ValueError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError):
        raise ValueError(NOT_IMAGE)


def save_photo(review, upload):
    """리뷰에 사진을 넣거나 바꾼다 (검사는 clean_upload 로 먼저)"""
    data, width, height = upload if isinstance(upload, tuple) else clean_upload(upload)
    ReviewPhoto.objects.update_or_create(review=review, defaults={'data': data, 'width': width, 'height': height})


def photo_url(rv_id, updated_at):
    """사진 주소. 사진을 바꾸면 ?v= 값(고친 시각)이 달라져서 브라우저가 새로 받는다"""
    stamp = int(updated_at.timestamp()) if updated_at else 0
    return '%s?v=%d' % (reverse('review_photo', args=[rv_id]), stamp)


def best_photos(kakao_ids):
    """카카오 장소 ID 목록 → {kakao_id: 사진 주소}. 장소마다 추천 많고 별점 높은 최근 리뷰의 사진 하나"""
    ids = sorted({str(k) for k in kakao_ids if k})
    if not ids:
        return {}
    rows = (
        ReviewPhoto.objects
        .filter(review__kakao_id__in=ids)
        .annotate(helpful=Count('review__helpfuls'))
        .order_by('-helpful', '-review__rating', '-review__created_at', '-rp_id')
        .values_list('review__kakao_id', 'review_id', 'rp_id', 'updated_at')
    )
    best = {}
    for kakao_id, rv_id, rp_id, updated in rows:
        if kakao_id not in best:
            best[kakao_id] = photo_url(rv_id, updated)
    return best
