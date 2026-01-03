# Better Auth MCP

MCP server that exposes Better Auth documentation as tools, deployed on Modal. Includes a Streamlit chatbot demo client powered by Gemini.

The server exposes two MCP tools:

- `get_table_of_contents`: Fetches the Better Auth documentation index
- `read_page`: Reads a specific documentation page by route

## MCP Server Deployment

The server (`mcp-server.py`) is deployed to [Modal](https://modal.com). First authenticate Modal and then deploy the server:

```bash
modal token new
modal deploy mcp-server.py
```

Modal will output a URL like `https://your-username--example-mcp-server.modal.run`. Add this URL to the `.env` file as `MCP_SERVER_URL` (don't forget to append `/mcp` to the base URL).

## Client Demo

The Streamlit chatbot `main.py` is a demo client that uses the MCP server to answer questions about Better Auth. It uses `gemini-2.5-flash-lite` to process queries and automatically calls the MCP tools to fetch relevant documentation.

```bash
cp .env.example .env
# Edit .env with GEMINI_API_KEY and MCP_SERVER_URL
```

To start the demo client, run:

```bash
uv sync
streamlit run main.py
```

## Project Structure

```
better-auth-mcp/
├── mcp-server.py          # MCP server
├── main.py                # Streamlit app entry point
├── chatbot.py             # Chatbot client with Gemini integration
└── test_endpoint.py       # Test script for MCP endpoints
```
