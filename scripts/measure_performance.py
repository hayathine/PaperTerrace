import asyncio
import os
import time

import httpx

# 推論サービスのURL（staging）
URL = "https://paperterrace-inference-staging-t2nx5gtwia-an.a.run.app"
# テストに使用する画像ディレクトリ
IMAGE_DIR = "/home/gwsgs/work_space/paperterrace/backend/src/static/paper_images/3c12d053be494b71d0bd4cbc761244586daa407b19831ef1f2616692e33d6d9f"
# テスト画像リスト（バッチ処理用）
IMAGES = ["page_1.png", "page_2.png", "page_3.png", "page_4.png"]


async def measure_batch(num_images):
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 画像の読み込み
        files = []
        selected_images = IMAGES[:num_images]
        for img_name in selected_images:
            img_path = os.path.join(IMAGE_DIR, img_name)
            if not os.path.exists(img_path):
                print(f"Error: {img_path} not found")
                continue
            with open(img_path, "rb") as f:
                content = f.read()
                files.append(("files", (img_name, content, "image/png")))

        if not files:
            print("No files to process.")
            return

        print(f"\n--- Testing batch analysis with {len(files)} images ---")
        start_time = time.time()
        try:
            response = await client.post(
                f"{URL}/api/v1/analyze-images-batch", files=files
            )
            total_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                processing_time = data.get("processing_time", 0)
                comm_time = total_time - processing_time
                parallel_workers = data.get("parallel_workers", "unknown")

                print(f"Total Response Time: {total_time:.4f}s")
                print(f"Processing Time (Server-side): {processing_time:.4f}s")
                print(
                    f"Communication Time (Network + Request Overhead): {comm_time:.4f}s"
                )
                print(f"Parallel Workers Used: {parallel_workers}")
                print(f"Average time per image: {total_time / len(files):.4f}s")

                return {
                    "num_images": len(files),
                    "total_time": total_time,
                    "processing_time": processing_time,
                    "comm_time": comm_time,
                    "parallel_workers": parallel_workers,
                }
            else:
                print(f"Error: HTTP {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"Exception: {e}")
            return None


async def main():
    print("PaperTerrace Inference Performance Measurement")
    print(f"Target URL: {URL}")

    # 1枚の解析時間（ベースライン）
    result1 = await measure_batch(1)

    # 2枚の解析時間
    result2 = await measure_batch(2)

    # 4枚の解析時間
    result4 = await measure_batch(4)

    print("\n" + "=" * 50)
    print("Summary Profile")
    print("=" * 50)
    if result1:
        print(
            f"1 Image:  Total {result1['total_time']:.2f}s (Proc: {result1['processing_time']:.2f}s, Comm: {result1['comm_time']:.2f}s)"
        )
    if result2:
        print(
            f"2 Images: Total {result2['total_time']:.2f}s (Proc: {result2['processing_time']:.2f}s, Comm: {result2['comm_time']:.2f}s)"
        )
    if result4:
        print(
            f"4 Images: Total {result4['total_time']:.2f}s (Proc: {result4['processing_time']:.2f}s, Comm: {result4['comm_time']:.2f}s)"
        )
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
