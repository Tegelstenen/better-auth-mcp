import streamlit as st
import httpx
from typing import Dict, Any, List
import json
from google import genai
from google.genai import types
import os


class Chatbot:
    def __init__(self, api_url: str, gemini_api_key: str):
        self.api_url = api_url
        self.gemini_api_key = gemini_api_key
        self.client = genai.Client(api_key=gemini_api_key)
        self.mcp_tools = []
        self.gemini_tools = []

    def parse_sse_response(self, text: str) -> dict:
        """Parse SSE response and extract JSON data."""
        lines = text.strip().split('\n')
        for line in lines:
            if line.startswith('data: '):
                data_str = line[6:]  # Remove 'data: ' prefix
                return json.loads(data_str)
        return {}

    async def send_mcp_request(self, method: str, params: dict = None):
        """Send an MCP request over SSE and get the response."""
        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
        }
        if params:
            request_data["params"] = params

        async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
            response = await client.post(
                f"{self.api_url}/sse",
                json=request_data,
                headers={"Accept": "application/json, text/event-stream"},
            )
            return self.parse_sse_response(response.text)

    async def get_tools(self):
        response = await self.send_mcp_request("tools/list")
        return response.get("result", {})

    def json_schema_to_gemini_schema(self, json_schema: dict) -> dict:
        """Convert JSON Schema to Gemini Schema format.

        Only includes fields supported by Gemini's Schema proto:
        - type, description, properties, required, items
        """
        schema = {}

        # Type is required for Gemini - convert to uppercase enum
        if "type" in json_schema:
            schema["type"] = json_schema["type"].upper()

        # Description is optional
        if "description" in json_schema:
            schema["description"] = json_schema["description"]

        # Properties for object types
        if "properties" in json_schema:
            schema["properties"] = {}
            for prop_name, prop_schema in json_schema["properties"].items():
                schema["properties"][prop_name] = self.json_schema_to_gemini_schema(prop_schema)

        # Required fields list
        if "required" in json_schema:
            schema["required"] = json_schema["required"]

        # Items for array types
        if "items" in json_schema:
            schema["items"] = self.json_schema_to_gemini_schema(json_schema["items"])

        return schema

    def mcp_to_gemini_tools(self, mcp_tools: List[Dict]) -> types.Tool:
        """Convert MCP tools to Gemini Tool object."""
        function_declarations = []
        for tool in mcp_tools:
            # Convert the JSON Schema to Gemini Schema
            parameters = self.json_schema_to_gemini_schema(tool["inputSchema"])

            func_decl = types.FunctionDeclaration(
                name=tool["name"],
                description=tool["description"],
                parameters=parameters
            )
            function_declarations.append(func_decl)

        return types.Tool(function_declarations=function_declarations)

    async def call_mcp_tool(self, tool_name: str, tool_args: dict) -> str:
        """Call an MCP tool and return the result."""
        response = await self.send_mcp_request(
            "tools/call",
            {"name": tool_name, "arguments": tool_args}
        )
        if "result" in response:
            # Handle wrapped result format
            result = response["result"]
            if isinstance(result, dict) and "result" in result:
                return str(result["result"])
            return str(result)
        elif "error" in response:
            return f"Error: {response['error']}"
        return str(response)

    async def render(self):
        st.title("MCP Client with Gemini")

        # Initialize session state for chat history
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Load MCP tools
        with st.sidebar:
            st.subheader("Settings")
            st.write("API URL:", self.api_url)

            with st.spinner("Loading MCP tools..."):
                result = await self.get_tools()

            st.subheader("Available Tools")
            if "tools" in result:
                self.mcp_tools = result["tools"]
                for tool in self.mcp_tools:
                    st.write(f"• {tool['name']}")
            else:
                st.error(f"No tools found. Keys: {list(result.keys())}")

        # Convert MCP tools to Gemini format
        if self.mcp_tools:
            self.gemini_tools = self.mcp_to_gemini_tools(self.mcp_tools)

        # Display chat history
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            elif msg["role"] == "assistant":
                st.chat_message("assistant").write(msg["content"])
            elif msg["role"] == "tool":
                with st.chat_message("assistant"):
                    with st.expander(f"🔧 Called tool: {msg['tool_name']}"):
                        st.json({"args": msg.get("args", {}), "result": msg["content"]})

        # Handle new query
        query = st.chat_input("Ask me about Better Auth...")
        if query:
            # Add user message to history
            st.session_state.chat_history.append({"role": "user", "content": query})
            st.chat_message("user").write(query)

            try:
                # Build conversation history for context
                contents = []
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        contents.append(types.Content(role="user", parts=[types.Part(text=msg["content"])]))
                    elif msg["role"] == "assistant":
                        contents.append(types.Content(role="model", parts=[types.Part(text=msg["content"])]))

                # Add system instruction
                system_instruction = """You are a helpful assistant that answers questions about Better Auth using the provided tools.

IMPORTANT TOOL USAGE INSTRUCTIONS:
1. ALWAYS call 'get_table_of_contents' FIRST to see available documentation
2. When user asks about a specific topic, use 'read_page' with the FULL path from the table of contents
   - Example: If table of contents shows "/llms.txt/docs/plugins/email-otp.md", use that EXACT path
3. DO NOT call 'get_table_of_contents' multiple times - reuse the information
4. When reading pages, use the complete path including '/llms.txt/docs/' prefix

Available tools:
- get_table_of_contents: Get the full documentation structure (call once at start)
- read_page: Read specific documentation page (use full path from table of contents)"""

                # Send message with tools
                with st.spinner("Thinking..."):
                    response = self.client.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=[self.gemini_tools] if self.gemini_tools else None,
                            system_instruction=system_instruction,
                            temperature=0.7
                        )
                    )

                # Handle tool calls
                max_iterations = 5
                iteration = 0
                while response.candidates[0].content.parts[0].function_call and iteration < max_iterations:
                    iteration += 1

                    function_call = response.candidates[0].content.parts[0].function_call
                    tool_name = function_call.name
                    tool_args = dict(function_call.args)

                    # Show tool call
                    with st.chat_message("assistant"):
                        with st.expander(f"🔧 Calling tool: {tool_name}"):
                            st.json({"args": tool_args})

                    # Call MCP tool
                    with st.spinner(f"Calling {tool_name}..."):
                        tool_result = await self.call_mcp_tool(tool_name, tool_args)

                    # Add tool call to history
                    st.session_state.chat_history.append({
                        "role": "tool",
                        "tool_name": tool_name,
                        "args": tool_args,
                        "content": tool_result
                    })

                    # Add function call to contents
                    contents.append(types.Content(
                        role="model",
                        parts=[types.Part(function_call=function_call)]
                    ))

                    # Add function response to contents
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part(
                            function_response=types.FunctionResponse(
                                name=tool_name,
                                response={"result": tool_result}
                            )
                        )]
                    ))

                    # Continue conversation
                    response = self.client.models.generate_content(
                        model="gemini-2.5-flash-lite",
                        contents=contents,
                        config=types.GenerateContentConfig(
                            tools=[self.gemini_tools] if self.gemini_tools else None,
                            system_instruction=system_instruction,
                            temperature=0.7
                        )
                    )

                # Get final text response
                final_response = response.text
                st.session_state.chat_history.append({"role": "assistant", "content": final_response})
                st.chat_message("assistant").write(final_response)

            except Exception as e:
                st.error(f"Error: {str(e)}")
                import traceback
                st.code(traceback.format_exc())