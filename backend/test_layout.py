import asyncio

from app.domain.services.paddle_layout_service import get_layout_service


async def test():
    service = get_layout_service()
    res = await service.analyze_pdf_layout("sample.pdf", pages=[0, 1])
    import pprint

    pprint.pprint(res[:2])


if __name__ == "__main__":
    asyncio.run(test())
