import logging
import re
import traceback

from django.apps import AppConfig

# 로그에 API 키가 그대로 찍히지 않게 가린다 (🟧 11/18)
# 공공데이터·카카오 요청이 실패하면 requests 오류 문장에 요청 주소가 통째로 들어가는데,
# 그 주소에 serviceKey=… 가 붙어 있어서 서버 로그(journalctl)에 키가 남았다.
_SECRET_RE = re.compile(r'((?:serviceKey|appkey|api_key|apikey|access_token|client_secret)=)[^&\s\'"<>]+', re.I)


def _mask(value):
    return _SECRET_RE.sub(r'\1***', value)


def _install_log_mask():
    if getattr(logging, '_tripa_mask', False):
        return
    old_factory = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        try:
            if isinstance(record.msg, str):
                record.msg = _mask(record.msg)
            if isinstance(record.args, tuple):
                record.args = tuple(
                    _mask(str(a)) if isinstance(a, (str, BaseException)) else a for a in record.args)
            if record.exc_info and record.exc_info[0] is not None:
                # 오류 내용(traceback)을 여기서 미리 글자로 만들어 가려 둔다 → 출력할 때 이 글자를 그대로 씀
                text = ''.join(traceback.format_exception(*record.exc_info)).rstrip('\n')
                record.exc_text = _mask(text)
        except Exception:      # 가리다 실패해도 로그 자체는 남게
            pass
        return record

    logging.setLogRecordFactory(factory)
    logging._tripa_mask = True


class SherpaappConfig(AppConfig):
    name = 'sherpaapp'

    def ready(self):
        _install_log_mask()
