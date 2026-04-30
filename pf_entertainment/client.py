from __future__ import annotations

import asyncio
import json


async def send_command(
    command: str,
    host: str = "127.0.0.1",
    port: int = 9021,
    timeout: float = 30.0,
) -> str:
    reader, writer = await asyncio.open_connection(host, port)
    try:
        writer.write((command.rstrip() + "\n").encode("utf-8"))
        await writer.drain()
        data = await asyncio.wait_for(reader.read(65536), timeout=timeout)
        return data.decode("utf-8", errors="replace").strip()
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def send_json_command(
    command: str,
    host: str = "127.0.0.1",
    port: int = 9021,
    timeout: float = 30.0,
) -> dict:
    response = await send_command(command, host=host, port=port, timeout=timeout)
    try:
        return json.loads(response)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"指令返回不是 JSON: {response}") from exc
