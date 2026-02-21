---
name: react-design
description: ReactとTailwind CSSを使用したフロントエンド設計
---

# React Design Skill

## 概要

PaperTerraceのフロントエンド開発におけるReactコンポーネント設計とTailwind CSSの運用ルールです。

## コンポーネント設計

### 1. 粒度と責務

- **Atomic Design** (参考): 再利用可能な小さな部品（Button, Input）と、それらを組み合わせた大きな部品（Form, Card）を意識的に区別する。
- **1ファイル1コンポーネント**: 基本的に1つのファイルには1つのコンポーネントを定義する。
- **PascalCase**: ファイル名はコンポーネント名と一致させる（例: `SummaryCard.tsx`）。

### 2. Hooksとロジックの分離

- View（JSX）とLogic（状態管理、副作用）を分離する。
- 複雑なロジックはカスタムフック（`usePaperAnalysis` など）に切り出し、コンポーネントは見栄えに集中させる。

### 3. TypeScript

- **Interface/Type**: Propsの型は必ず定義する。`any` は禁止。
- **FC (Functional Component)**: 関数コンポーネントを使用する。

## Tailwind CSS ベストプラクティス

### 1. ユーティリティファースト

CSSファイルを作成せず、基本的にはクラス名でスタイルを完結させる。

```tsx
// Good
<button className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded">
  Button
</button>
```

### 2. クラスの整理

クラス名が長くなりすぎる場合は、可読性を維持するために以下の対策を行う。

- 適切な粒度でコンポーネント化する（推奨）。
- `clsx` や `tailwind-merge` などのライブラリを使用して条件付きスタイルを整理する。

### 3. デザインシステム

- 色やフォントサイズは、ハードコード（`text-[14px]`）せず、Tailwindのテーマ設定（`text-sm`）やデザインシステムで定義されたトークンを使用する。
