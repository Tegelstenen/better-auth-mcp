import httpx
import asyncio
import json

def parse_sse_response(text: str) -> dict:
    """Parse SSE response and extract JSON data."""
    lines = text.strip().split('\n')
    for line in lines:
        if line.startswith('data: '):
            data_str = line[6:]  # Remove 'data: ' prefix
            return json.loads(data_str)
    return {}

async def test_mcp_tools():
    url = "https://filip-max-marc-modal-hackathon--example-mcp-server-state-4aff44.modal.run/mcp/sse"

    request_data = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list"
    }

    print(f"Testing MCP tools/list...")
    print(f"Request: {json.dumps(request_data, indent=2)}\n")

    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        try:
            response = await client.post(
                url,
                json=request_data,
                headers={"Accept": "application/json, text/event-stream"},
            )
            print(f"Status: {response.status_code}\n")

            # Parse SSE response
            data = parse_sse_response(response.text)

            if "result" in data:
                tools = data["result"].get("tools", [])
                print(f"Found {len(tools)} tools:")
                for tool in tools:
                    print(f"  - {tool['name']}: {tool['description'][:60]}...")
            elif "error" in data:
                print(f"Error: {data['error']}")
            else:
                print(f"Unexpected response: {data}")

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mcp_tools())
