import inspect
import os
from typing import Dict, List, Optional, Tuple
import crewai_tools
from crewai.tools import BaseTool
from storage.custom_tools import instantiate_custom_tool, list_custom_tools

# Tools in crewai_tools that require external paid API keys unless configured in env
ENV_DEPENDENT_TOOLS: Dict[str, str] = {
    "SerperDevTool": "SERPER_API_KEY",
    "BraveSearchTool": "BRAVE_API_KEY",
    "ExaSearchTool": "EXA_API_KEY",
    "FirecrawlCrawlWebsiteTool": "FIRECRAWL_API_KEY",
    "FirecrawlScrapeWebsiteTool": "FIRECRAWL_API_KEY",
    "FirecrawlSearchTool": "FIRECRAWL_API_KEY",
    "TavilySearchTool": "TAVILY_API_KEY",
    "BrowserbaseLoadTool": "BROWSERBASE_API_KEY",
}


def discover_builtin_tools() -> Dict[str, dict]:
    """
    Dynamically inspects the installed `crewai_tools` library and catalogs
    all available BaseTool subclasses that can be instantiated cleanly.
    """
    catalog: Dict[str, dict] = {}

    for attr_name in dir(crewai_tools):
        if attr_name.startswith("_") or attr_name == "BaseTool":
            continue

        obj = getattr(crewai_tools, attr_name, None)
        if not inspect.isclass(obj):
            continue

        try:
            if not issubclass(obj, BaseTool):
                continue
        except TypeError:
            continue

        # Check if an API key is strictly required and missing
        required_env = ENV_DEPENDENT_TOOLS.get(attr_name)
        if required_env and not os.getenv(required_env):
            continue

        # Check if the tool can be initialized with zero required positional args
        sig = inspect.signature(obj.__init__)
        has_required_args = any(
            p.default is inspect.Parameter.empty
            and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
            for name, p in sig.parameters.items()
            if name != "self"
        )
        if has_required_args:
            continue

        doc = inspect.getdoc(obj) or f"Built-in CrewAI tool: {attr_name}"
        first_line = doc.strip().splitlines()[0]

        catalog[attr_name] = {
            "name": attr_name,
            "source": "crewai_tools",
            "description": first_line,
        }

    return catalog


def get_full_toolbox_catalog() -> str:
    """
    Returns a formatted catalog combining:
      1. Ready-to-use built-in `crewai_tools`
      2. Previously synthesized tools in `storage/custom_tools`
    """
    builtins = discover_builtin_tools()
    customs = list_custom_tools()

    lines = ["=== AVAILABLE CREWAI TOOLBOX ==="]
    lines.append("\n[Built-in crewai_tools (Zero-Config Ready)]")
    if builtins:
        for name, meta in sorted(builtins.items()):
            lines.append(f"- {name}: {meta['description']}")
    else:
        lines.append("- No zero-config built-in tools detected.")

    lines.append("\n[Archived Custom Tools (Previously Crafted)]")
    if customs:
        for c in customs:
            lines.append(f"- {c['tool_name']}: {c['description']}")
    else:
        lines.append("- None archived yet.")

    lines.append(
        "\nNOTE: If a task needs a capability NOT listed above (e.g., scraping a specific "
        "public JSON endpoint, parsing custom logs, running specialized math/text transforms), "
        "the Tool-Smith can synthesize a brand-new CustomToolSpec."
    )
    return "\n".join(lines)


def resolve_tool_instance(tool_name: str) -> Optional[BaseTool]:
    """
    Resolves a tool string name into an instantiated BaseTool object.
    Checks built-in `crewai_tools` first, then `storage/custom_tools`.
    """
    # 1. Check built-in crewai_tools
    tool_cls = getattr(crewai_tools, tool_name, None)
    if inspect.isclass(tool_cls) and issubclass(tool_cls, BaseTool):
        try:
            return tool_cls()
        except Exception:
            return None

    # 2. Check persisted custom tools
    return instantiate_custom_tool(tool_name)


def resolve_tools_for_agent(tool_names: List[str]) -> Tuple[List[BaseTool], List[str]]:
    """
    Resolves a list of tool names into live BaseTool instances.
    Returns (instantiated_tools, unresolved_tool_names).
    """
    resolved: List[BaseTool] = []
    unresolved: List[str] = []

    for name in tool_names:
        instance = resolve_tool_instance(name)
        if instance is not None:
            resolved.append(instance)
        else:
            unresolved.append(name)

    return resolved, unresolved
