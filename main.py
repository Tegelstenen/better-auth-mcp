import asyncio
import os

import streamlit as st
from dotenv import load_dotenv

from chatbot import Chatbot

load_dotenv()


def get_config(key: str) -> str:
    """
    Get config from environment variable or Streamlit secrets.

    Args:
        key (str): The key to get the config for.
    Returns:
        str: The config value.
    """
    value = os.getenv(key)
    if not value:
        try:
            value = st.secrets.get(key)
        except:
            pass
    if not value:
        st.error(
            f"{key} not found. Please set it as an environment variable or in Streamlit secrets."
        )
        st.stop()
    return value


async def main():
    st.set_page_config(page_title="Better Auth MCP Client", page_icon=":robot:")

    api_url = get_config("MCP_SERVER_URL")
    gemini_api_key = get_config("GEMINI_API_KEY")

    chatbot = Chatbot(api_url, gemini_api_key)
    await chatbot.render()


if __name__ == "__main__":
    asyncio.run(main())
