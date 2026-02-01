---
trigger: always_on
---

- gemini 1.5 flash → gemini 2.0 flash
- google_cloud_run_v2_serviceのstartup_cpu_boostは必ずTrueに設定する
- pdfplumberのuse_text_flowは必ずTrueに設定する
- モード選択ポップアップはテキストモード，支援モード，切り取りモード，スタンプモードの順に表示する
- pypdfの解像度は必ず300に設定する
- 初期画面では中央に論文のアップロード機能を設置する