import asyncio
import streamlit as st
from chatbot import Chatbot
import os
from dotenv import load_dotenv

load_dotenv()


async def main():
    st.set_page_config(page_title="MCP Client with Gemini", page_icon="🤖")

    # Get API keys
    API_URL = "https://filip-max-marc-modal-hackathon--example-mcp-server-state-4aff44.modal.run/mcp"

    # Try to get Gemini API key from environment or Streamlit secrets
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        try:
            gemini_api_key = st.secrets.get("GEMINI_API_KEY")
        except:
            pass

    if not gemini_api_key:
        st.error("GEMINI_API_KEY not found. Please set it as an environment variable or in Streamlit secrets.")
        st.stop()

    chatbot = Chatbot(API_URL, gemini_api_key)
    await chatbot.render()


if __name__ == "__main__":
    asyncio.run(main())