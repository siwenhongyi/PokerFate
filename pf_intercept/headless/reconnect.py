"""Reconnect the transport without replacing the run's bridge or bankroll."""

from __future__ import annotations

import asyncio
import logging

from pf_intercept.headless.session import LoginRejected

log = logging.getLogger("pf_headless")
RETRY_DELAYS = (1, 2, 4, 8, 16, 30)


async def until_stopped(operation, stop: asyncio.Event) -> bool:
    """Run one operation, with stop interrupting connect, recovery or backoff."""
    task = asyncio.create_task(operation)
    stopper = asyncio.create_task(stop.wait())
    try:
        await asyncio.wait({task, stopper}, return_when=asyncio.FIRST_COMPLETED)
        if stop.is_set():
            return False
        await task
        return True
    finally:
        task.cancel()
        stopper.cancel()
        await asyncio.gather(task, stopper, return_exceptions=True)


async def maintain_game(session, stop, *, big_blind, buyin_bb, server_index=0, observer=None) -> bool:
    """True for an explicit stop; False for a terminal server rejection.

    The initial connection is already open. Every connection must restore its
    authoritative location before it can request any new matchmaking.
    """
    def status(value):
        if observer is not None:
            observer.set_connection_status(value)

    async def restore():
        status("restoring")
        await session.restore_or_start(big_blind=big_blind, buyin_bb=buyin_bb)
        if not session.connected:
            raise ConnectionError("恢复期间连接断开")

    ready = False
    try:
        if not await until_stopped(restore(), stop):
            return True
        ready = True
    except Exception as exc:
        log.warning("[RECONNECT] 初次位置恢复失败: %s", exc)
        await session.disconnect("initial restore failed")

    while not stop.is_set():
        if ready:
            status("connected")
            if not await until_stopped(session.wait_closed(), stop):
                return True
            ready = False
        if session.fatal_error:
            log.error("[RECONNECT] %s", session.fatal_error)
            status("disconnected")
            return False
        status("reconnecting")
        log.warning("[RECONNECT] 连接中断 reason=%s；保留本次资金、奖励和续入次数", session.disconnect_reason)
        attempt = 0
        while not stop.is_set():
            delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
            index = (server_index + attempt) % len(session.login.servers)
            log.warning("[RECONNECT] 第 %d 次尝试，%ss 后连接 server_index=%d", attempt + 1, delay, index)
            if not await until_stopped(asyncio.sleep(delay), stop):
                return True
            try:
                if not await until_stopped(session.connect(server_index=index), stop):
                    return True
                if not await until_stopped(restore(), stop):
                    return True
                server_index = index
                ready = True
                log.info("[RECONNECT] 恢复成功 server_index=%d，继续本次运行", index)
                break
            except LoginRejected as exc:
                log.error("[RECONNECT] 登录被拒绝，停止重试: %s", exc)
                status("disconnected")
                return False
            except Exception as exc:
                log.warning("[RECONNECT] 本次未恢复: %s: %s", type(exc).__name__, exc)
                await session.disconnect("reconnect failed")
                if session.fatal_error:
                    log.error("[RECONNECT] %s", session.fatal_error)
                    status("disconnected")
                    return False
                status("reconnecting")
                attempt += 1
    return True
