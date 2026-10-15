import asyncio
import json
import secrets
import sys

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def main():
    nonce = secrets.token_hex(16)
    params = StdioServerParameters(command=sys.executable, args=["-m", "worldguard.mcp_server"])
    async with Client(params, read_timeout_seconds=15) as client:
        result = await client.call_tool("wg_health", {"nonce": nonce})
        payload = result.model_dump(mode="json", by_alias=True)
        structured = payload.get("structuredContent")
        if structured is None:
            structured = json.loads(payload["content"][0]["text"])
        assert not payload.get("isError") and structured["nonce"] == nonce, payload
        print(
            json.dumps(
                {
                    "status": "MCP_PROTOCOL_PASS",
                    "runtime_mode": "DETERMINISTIC",
                    "nonce": nonce,
                    "result": structured,
                    "model_requests": 0,
                }
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
