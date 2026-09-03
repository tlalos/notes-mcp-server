"""
Minimal example: launch the Notes MCP server over stdio and call its tools
programmatically with the MCP Python SDK.

    pip install mcp httpx
    NOTES_API_URL=https://macross.no-ip.info NOTES_API_TOKEN=xxxx python examples/list_and_create.py
"""
import asyncio
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(
        command="python",
        args=["-m", "notes_mcp.server"],
        env={
            "NOTES_API_URL": os.environ["NOTES_API_URL"],
            "NOTES_API_TOKEN": os.environ["NOTES_API_TOKEN"],
        },
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            created = await session.call_tool(
                "create_note",
                {"title": "From my agent", "content": "Hello from MCP!", "tags": "agent,demo"},
            )
            print("Created:", created.content)

            listed = await session.call_tool("list_notes", {"query": "agent"})
            print("Matches:", listed.content)


if __name__ == "__main__":
    asyncio.run(main())
