import asyncio

from app.providers.inference_client import get_inference_client


async def test():
    client = await get_inference_client()
    res = await client.analyze_layout("sample.pdf", [0, 1])
    import pprint

    pprint.pprint(res[:2])


if __name__ == "__main__":
    asyncio.run(test())
