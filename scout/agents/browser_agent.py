from . import model
import subprocess
from dataclasses import dataclass
from pydantic_ai import Agent, RunContext
from ..logger import get_logger
from . import model

agent = Agent(
    model=model,
    retries=4,
    system_prompt="Use the browser agent tool for running exeucting the actions",
)
logger = get_logger("AGENT")


@dataclass
class Deps:
    cdp_endpoint: str
    page_snapshot: str


@agent.system_prompt
def get_agent_browser_command(ctx: RunContext[Deps]):
    cdp_endpoint = ctx.deps.cdp_endpoint
    return f"""
    You are an autonomous browser automation agent. You complete tasks by interacting with a browser using the browser tool. Be autonomous — break tasks into steps, execute ALL steps without stopping early, and be concise.
    
    You are already on the correct page.
    
    A snapshot of the current page is provided in the USER message. Use it as your starting point.

    Use the browser tool to interact with the page.
    
    ## Browser Tool — agent-browser commands
    The browser tool runs agent-browser CLI commands. Each tool call should contain a single command or a short chain (joined with &&).

    Commands:
    agent-browser --cdp {cdp_endpoint} snapshot                Get full accessibility tree with clickable refs (@e1, @e2...), prefer using -i
    agent-browser --cdp {cdp_endpoint} snapshot -i             Only interactive elements
    agent-browser --cdp {cdp_endpoint} snapshot -s "#css"      Scope snapshot to a CSS selector
    agent-browser --cdp {cdp_endpoint} click @e1               Click element by ref
    agent-browser --cdp {cdp_endpoint} fill @e2 "text"         Clear field and type text
    agent-browser --cdp {cdp_endpoint} type @e2 "text"         Type without clearing
    agent-browser --cdp {cdp_endpoint} select @e1 "option"     Select dropdown option
    agent-browser --cdp {cdp_endpoint} check @e1               Toggle checkbox
    agent-browser --cdp {cdp_endpoint} press Enter             Press a key
    agent-browser --cdp {cdp_endpoint} keyboard type "text"    Type at current focus
    agent-browser --cdp {cdp_endpoint} hover @e1               Hover element
    agent-browser --cdp {cdp_endpoint} scroll down 500         Scroll down (px)
    agent-browser --cdp {cdp_endpoint} scroll up 500           Scroll up (px)
    agent-browser --cdp {cdp_endpoint} get text @e1            Get text content of element
    agent-browser --cdp {cdp_endpoint} get title               Get page title
    agent-browser --cdp {cdp_endpoint} get url                 Get current URL
    agent-browser --cdp {cdp_endpoint} wait @e1                Wait for element to appear
    agent-browser --cdp {cdp_endpoint} wait --load networkidle Wait for network idle
    agent-browser --cdp {cdp_endpoint} wait --text "Welcome"   Wait for text to appear
    agent-browser --cdp {cdp_endpoint} wait 2000               Wait milliseconds
    agent-browser --cdp {cdp_endpoint} find text "X" click     Find element by text and click
    agent-browser --cdp {cdp_endpoint} find role button click --name "Submit"
    agent-browser --cdp {cdp_endpoint} find placeholder "Q" type "query"
    agent-browser --cdp {cdp_endpoint} frame @e2               Scope to iframe
    agent-browser --cdp {cdp_endpoint} frame main              Return to main frame
    agent-browser --cdp {cdp_endpoint} eval "js code"          Run JavaScript in page
    agent-browser --cdp {cdp_endpoint} back                    Go back

    ## Workflow
    1. An initial page snapshot is provided — use it immediately, don't re-snapshot.
    2. Interact with elements using @refs from the snapshot.
    3. After interactions that change the page, call snapshot to see the updated state.
    4. Use the new @refs from the latest snapshot for further interactions.
    5. Repeat until the task is complete.

    ## Rules
    1. You are already on the target page. Do NOT navigate to external sites or search engines.
    2. @refs are invalidated after page changes — always snapshot again after interactions.
    3. Chain independent commands with && to save round-trips.
    4. When extracting data, use agent-browser get text or agent-browser eval to pull content.
    5. If a command fails, try a different approach (different selector, wait first, use find, etc.).
    6. NEVER open new tabs. Always work in the current tab. Do not use agent-browser tab new or agent-browser open. If you need to navigate within the site, click links directly.

    ## Output Format
    Your final text response is what the user sees. It MUST be a clean, human-readable answer:
    - If asked for a price → respond with the product name and price (e.g. "iPhone 15 Pro Max: $1,199")
    - If asked for a list → respond with a clean list of items
    - If asked to perform an action → confirm what was done
    - NEVER dump raw HTML, accessibility trees, or @ref identifiers in your final response
    - Be concise and direct — just the answer the user asked for
    """


@agent.tool
async def browser_tool(ctx: RunContext[Deps], command: str) -> str:
    """Run an agent-browser CLI command in the browser. Each call should be one command or a short && chain."""
    logger.info(msg=command, tag="COMMAND")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)


async def execute(query: str, deps: Deps):
    prompt = f"""
            ## Task
            {query}

            ## Current Page Snapshot
            {deps.page_snapshot}

            ## Instructions
            - Use the snapshot to understand the page
            - Use @refs from the snapshot
            - Do NOT re-snapshot unless needed
    """

    result = await agent.run(prompt, deps=deps)
    return result.output
