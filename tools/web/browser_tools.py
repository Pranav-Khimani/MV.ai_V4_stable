
import webbrowser
from urllib.parse import quote_plus

from core.tool import Tool
from core.tool_schema import ActionSchema


class BrowserTool(Tool):
    name = "browser"
    description = "Open websites and search Google or YouTube."
    actions = {
        "open_website": ActionSchema(
            description="Open a website or URL in the default browser.",
            required_arguments=("query",),
            example={"query": "youtube"},
        ),
        "google_search": ActionSchema(
            description="Search Google for a query.",
            required_arguments=("query",),
            example={"query": "MV.ai desktop assistant"},
        ),
        "youtube_search": ActionSchema(
            description="Search YouTube for a query.",
            required_arguments=("query",),
            example={"query": "Python tutorial"},
        ),
    }

    def execute(self, args=None):
        if not args:
            return "Please provide a browser action."

        action = args.get("action")
        query = args.get("query", "").strip()

        if action == "open_website":
            return self.open_website(query)

        if action == "google_search":
            return self.google_search(query)

        if action == "youtube_search":
            return self.youtube_search(query)

        return f"Unknown browser action: {action}"

    def open_website(self, website):
        if not website:
            return "Please provide a website."

        websites = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "github": "https://github.com",
            "gmail": "https://mail.google.com",
        }

        url = websites.get(website.lower(), website)

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        webbrowser.open(url)
        return f"Opened {website}."

    def google_search(self, query):
        if not query:
            return "Please provide something to search on Google."

        url = f"https://www.google.com/search?q={quote_plus(query)}"
        webbrowser.open(url)

        return f"Searched Google for: {query}"

    def youtube_search(self, query):
        if not query:
            return "Please provide something to search on YouTube."

        url = (
            "https://www.youtube.com/results"
            f"?search_query={quote_plus(query)}"
        )

        webbrowser.open(url)

        return f"Searched YouTube for: {query}"