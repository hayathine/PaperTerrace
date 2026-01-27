# PaperTerrace Design System (Unified Rules)

このプロジェクトのデザインは「 **Intellectual Clarity & Modern Flow** (知的明快さと現代的なフロー) 」をテーマに、Tailwind CSSを用いて構築されています。新規実装や修正の際は以下のルールを厳守してください。

## 1. デザイン哲学
*   **Glassmorphism (グラスモーフィズム):** ヘッダーやサイドバーなどのフローティング要素には、すりガラス効果 (`bg-white/80` + `backdrop-blur`) を使用し、コンテンツの重なりと奥行きを表現する。
*   **Micro-Typography:** ラベルやメタデータには極小サイズ (`text-[10px]`) かつ `UPPERCASE` + `tracking-widest` を多用し、情報を整理しつつノイズを減らす。
*   **Soft Shadows:** 影は `slate-200` や `indigo-200` をベースにした色付きの柔らかい拡散影を使用し、黒い影は避ける。

## 2. カラーパレット (Tailwind Config)

### Theme Colors (Brand)
*   **Primary (Brand):** Indigo & Violet
    *   Gradient: `bg-gradient-to-br from-indigo-600 to-violet-700` (ロゴ、主要ボタン)
    *   Text: `text-indigo-600`, `text-indigo-500`
    *   Background (Light): `bg-indigo-50`, `bg-indigo-100`
*   **Secondary (Function):**
    *   **Success/Add:** Emerald (`text-emerald-600`, `bg-emerald-600`) - 追加、完了、ポジティブなアクション
    *   **Critique/Analysis:** Purple (`text-purple-600`, `bg-purple-100`) - 批判的分析、考察
    *   **Warning/Error:** Red (`text-red-600`, `bg-red-50`) - 削除、エラー

### Neutrals (Slate)
*   **Background:** `bg-[#f8fafc]` (アプリ全体の背景)
*   **Surface:** `bg-white` (カード、メインエリア)
*   **Text Strong:** `text-slate-900` (本文、見出し)
*   **Text Muted:** `text-slate-400` (補足情報、プレースホルダー)
*   **Border:** `border-slate-200`, `border-slate-100`

## 3. タイポグラフィ (Inter)
Google Fonts "Inter" を使用。

| 用途 | クラス例 | 備考 |
| :--- | :--- | :--- |
| **Page Title** | `text-xl font-bold` | グラデーションテキストと組み合わせることが多い |
| **Section Header** | `text-sm font-bold uppercase tracking-widest text-slate-400` | アイコンとセットで使用 |
| **Body** | `text-xs` or `text-sm` | 基本サイズは小さめ (`text-xs` = 12px) を好む |
| **Micro Label** | `text-[10px] font-bold uppercase tracking-wider` | タブ、バッジ、メタデータ用 |
| **Content** | `text-lg leading-relaxed` | 論文リーダービューなどの長文用 |

## 4. コンポーネントルール

### Buttons & Interactables
*   **Primary:** Gradient BG + White Text + `rounded-xl` + `shadow-lg`
*   **Secondary/Tabs:** `bg-white` or Transparent + Colored Text + `border-slate-100`
*   **Hover:** 必ず `transition-all` を含める。ホバー時に `scale` させたり、背景色を一段濃くする (`hover:bg-indigo-700` 等)。

### Cards & Containers
*   **Base:** `bg-white rounded-2xl` (または `3xl`)
*   **Shadow:** `shadow-xl shadow-slate-200/50` (色付きの影)
*   **Border:** `border border-slate-100` (薄い境界線で引き締める)

### Inputs
*   **Style:** `bg-white border border-slate-200 rounded-xl p-3 text-xs`
*   **Focus:** `outline-none focus:ring-2 focus:ring-indigo-500`

## 5. モーション & インタラクション
*   **Fade In:** コンテンツの切り替えには `animate-fade-in` クラス (keyframes fadeIn) を使用する。
*   **Loading:** `htmx-indicator` と `animate-spin` を組み合わせ、ユーザーに処理中であることを明示する。
*   **Transitions:** インタラクティブな要素には `duration-200` 程度のトランジションを適用する。

## 6. CSSクラス構成例 (推奨)
```html
<!-- Section Header -->
<h3 class="text-sm font-bold text-slate-400 uppercase tracking-widest flex items-center">
  <icon class="w-4 h-4 mr-2" />
  TITLE
</h3>

<!-- Glassmorphism Container -->
<div class="glass-morphism border border-slate-200 rounded-2xl p-6 shadow-xl">
  ...
</div>

<!-- Primary Button -->
<button class="bg-gradient-to-r from-indigo-600 to-violet-600 text-white rounded-xl px-4 py-2 hover:shadow-lg transition-all">
  Action
</button>
```
