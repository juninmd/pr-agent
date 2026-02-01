import json
import re
import aiohttp
import html2text
from pr_agent.log import get_logger

def parse_llm_response(response: str):
    """
    Parses the JSON response from the LLM.
    Handles markdown code blocks and basic cleanup.
    """
    try:
        match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
        json_str = match.group(1) if match else response
        # Basic cleanup for potential trailing commas or markdown issues
        json_str = json_str.strip()
        return json.loads(json_str)
    except Exception as e:
        get_logger().warning(f"JSON Parse Error: {e}")
        return None

async def fetch_url_content(url: str, timeout_sec: int = 10, max_chars: int = 10000):
    """
    Fetches the content of a URL and converts it to markdown text.
    """
    if not url.startswith(("http://", "https://")):
        return "Error: URL must start with http:// or https://"
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_sec)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return f"Error: Failed to fetch {url}, status {response.status}"
                html = await response.text()
                h = html2text.HTML2Text()
                h.ignore_links = False
                return h.handle(html)[:max_chars]
    except Exception as e:
        return f"Error viewing website: {e}"
