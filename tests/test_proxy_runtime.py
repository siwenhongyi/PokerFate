import asyncio
import json
import logging
import pytest

from pf_intercept.options import RunOptions
from pf_intercept.proxy import app


@pytest.mark.parametrize('worker_failure', [False, True])
def test_proxy_serves_and_uploads_same_snapshot_and_closes_components(monkeypatch, tmp_path, worker_failure):
    from pf_entertainment import web
    from pf_entertainment.remote_live import publisher
    sources, stopped = {}, []
    cert = tmp_path / 'cert'
    cert.touch()
    monkeypatch.setattr(app, 'SERVER_CERT', cert)
    monkeypatch.setattr(app, 'PASSTHROUGH_PORTS', [])
    monkeypatch.setattr(app, '_active_server_ws', None)
    monkeypatch.setattr(app, '_active_client_ws', None)
    monkeypatch.setattr(app, '_entertainment', None)
    monkeypatch.setattr(app, '_make_server_ssl', lambda: None)
    monkeypatch.setattr(app, 'archive_runtime_logs_on_startup', lambda _: None)
    monkeypatch.setattr(app, 'start_calibration_spool_worker', lambda: None)
    monkeypatch.setattr(app, 'stop_calibration_spool_worker', lambda: None)
    monkeypatch.setattr(web, 'get_logger', lambda: logging.getLogger('test-web'))
    class Worker:
        pid = 123
        def __init__(self, *, options):
            sources['options'] = options
            self.failed = asyncio.Event()
        async def start(self): pass
        async def stop(self): stopped.append('worker')
        def live_snapshot(self): return {'room_id':90, 'session_reward_chips':123}
        def bankroll_dashboard(self): return {'reward_chips':123, 'session_delta_chips':50}
    monkeypatch.setattr(app, 'BotWorkerClient', Worker)
    class Listener:
        def close(self): stopped.append('listener')
        async def wait_closed(self): pass
    async def serve(*a, **k): return Listener()
    monkeypatch.setattr(app.websockets, 'serve', serve)
    class Publisher:
        async def close(self): stopped.append('publisher')
    def upload(source, *, money_source, enabled):
        sources.update(live=source, money=money_source, enabled=enabled)
        return Publisher()
    monkeypatch.setattr(publisher, 'start_remote_live', upload)
    async def run():
        stop = asyncio.Event()
        task = asyncio.create_task(app.main(RunOptions(no_notify=True, web_host='127.0.0.1', web_port=0), stop))
        try:
            for _ in range(100):
                if app._entertainment and app._entertainment.web_port:
                    break
                await asyncio.sleep(.01)
            reader, writer = await asyncio.open_connection('127.0.0.1', app._entertainment.web_port)
            writer.write(b'GET /api/live HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n')
            await writer.drain()
            raw = await reader.read()
            writer.close()
            await writer.wait_closed()
            response = json.loads(raw.split(b'\r\n\r\n',1)[1])
            assert response['available'] and response['live']['room_id'] == 90
            assert sources['enabled'] is True
            assert sources['live']() == response['live']
            assert sources['money']()['reward_chips'] == 123
            assert app._entertainment.radar_board is not None
        finally:
            if worker_failure:
                app._bot.failed.set()
                with pytest.raises(RuntimeError, match='工作进程已退出'):
                    await task
            else:
                stop.set()
                await task
        assert set(stopped) == {'worker','listener','publisher'}
    asyncio.run(run())
