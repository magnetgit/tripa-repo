# 장소별 리뷰 묶음을 임베딩해 저장 (비슷한 장소 찾기용). 리뷰가 늘었으면 다시 돌린다
#   python manage.py index_reviews
from django.core.management.base import BaseCommand

from sherpaapp.services import embed_service


class Command(BaseCommand):
    help = '장소별 리뷰를 임베딩해 embed_chunk(kind=review)에 저장'

    def handle(self, *args, **opts):
        n = embed_service.index_reviews()
        self.stdout.write(self.style.SUCCESS(f'리뷰 묶음 저장: 장소 {n}곳'))
