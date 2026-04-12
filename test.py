import asyncio
from scout.agents.extraction_agent import extract
from pydantic import BaseModel


async def main() -> None:
    # config = BrowserManagerConfig()

    # async with BrowserManager(config) as mgr:
    #     websocket_url = await mgr.get_websocket_debugger_url()
    #     print(f"Session ID:         {mgr.config.session_id}")
    #     print(f"CDP HTTP URL:       {mgr.cdp_url}")
    #     print(f"CDP WebSocket URL:  {websocket_url}")
    #     print(f"Debugging port:     {mgr.debugging_port}")
    #     print(f"CDP bind address:   {mgr.config.remote_debugging_address}")
    #     print(
    #         f"User data dir:      {mgr._user_data_temp.name if mgr._user_data_temp else 'custom'}"
    #     )
    #     print("\nBrowser open for 300 seconds...")

    #     await asyncio.sleep(300)

    #     print("Closing browser...")

    class Features(BaseModel):
        name: str
        feature: str

    class Feedbacks(BaseModel):
        features: list[Features]
        images: list[str]

    with open("test.md") as markdown:
        result = await extract(
            markdown.read(),
            model=Feedbacks,
            query="Give me all feedbacks and features only",
        )
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
