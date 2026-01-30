# Frontend Engineer Rules

Follow these rules when writing frontend code (React, TypeScript).

## Implementation Guidelines

### 1. Component Design

- **Structure**: Split components into `src/components`. Maintain reusability.
- **Typing**: Strict TypeScript definitions for Props. **No `any`**.
- **Responsive**: Mobile-first approach is recommended.

### 2. State & Logic

- **Contexts**: Use `src/contexts` for global state (Auth, Theme).
- **Separation**: Extract API calls and complex logic into custom hooks. Separate View from Logic.

### 3. User Experience (UX)

- **Feedback**: Explicitly show Loading, Success, and Error states in the UI. Never leave the user wondering if something is happening.
- **Error Handling**: specific, helpful messages (Toast/Modal) instead of just console logs.

### 4. Translation Tone (UI Text)

- As per `paper-translation` skill, use a **gentle "desu/masu" tone** for Japanese UI text.
- Add explanations for technical terms where possible.

### 5. Visual Verification & Feedback

- **Screenshot Presentation**: When creating or significantly modifying a UI component, you MUST take a screenshot (using the browser tool/generate_image tool as appropriate) and present it to the user.
- **Iterative Refinement**: Explicitly ask for specific feedback on the design (layout, colors, spacing) and refine based on the user's instructions. Do not assume the first implementation is final.
