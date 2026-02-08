import asyncio
import time

import httpx

# 推論サービスのURL（staging）
URL = "https://paperterrace-inference-staging-t2nx5gtwia-an.a.run.app"


async def measure_translation(text, target_lang="ja"):
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {"text": text, "target_lang": target_lang}

        print(f"\n--- Testing translation: '{text}' ---")
        start_time = time.time()
        try:
            response = await client.post(f"{URL}/api/v1/translate", json=payload)
            total_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                processing_time = data.get("processing_time", 0)
                comm_time = total_time - processing_time
                translation = data.get("translation", "")

                print(f"Result: {translation}")
                print(f"Total Response Time: {total_time:.4f}s")
                print(f"Processing Time (Server-side): {processing_time:.4f}s")
                print(
                    f"Communication Time (Network + Request Overhead): {comm_time:.4f}s"
                )

                return {
                    "text": text,
                    "total_time": total_time,
                    "processing_time": processing_time,
                    "comm_time": comm_time,
                }
            else:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None


async def main():
    print("PaperTerrace Translation Performance Measurement")
    print(f"Target URL: {URL}")

    # 単語の翻訳
    result_word = await measure_translation("Implementation")

    # 短い文章の翻訳
    result_sent = await measure_translation(
        "A powerful agentic AI coding assistant designed by Google Deepmind."
    )

    print("\n" + "=" * 50)
    print("Summary Profile")
    print("=" * 50)
    if result_word:
        print(
            f"Word:     Total {result_word['total_time']:.4f}s (Proc: {result_word['processing_time']:.4f}s, Comm: {result_word['comm_time']:.4f}s)"
        )
    if result_sent:
        print(
            f"Sentence: Total {result_sent['total_time']:.4f}s (Proc: {result_sent['processing_time']:.4f}s, Comm: {result_sent['comm_time']:.4f}s)"
        )
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
