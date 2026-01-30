---
description: Guide to creating a new frontend component using React and Tailwind CSS
---

# New Frontend Component Workflow

This workflow guides you through creating a new UI component following the `react-design` skill.

1. **Review Design Guidelines**
   Read the React design skill to understand the component structure and styling rules.
   (Agent: Use `view_file` on `.agent/skills/react-design/SKILL.md`)

2. **Create Component File**
   Create a new file in `frontend/src/components/` (or a subdirectory).
   - Use PascalCase for the filename (e.g., `MyComponent.tsx`).
   - Define the Props interface explicitly.

3. **Implement Logic & UI**
   - Use Tailwind CSS for styling (Utility-first).
   - Separate complex logic into custom hooks if necessary.
   - Ensure the component is responsive.

4. **Handle Loading & Error States**
   - Implement visual feedback for loading states (skeletons, spinners).
   - specific error messages or fallback UIs.

5. **Integrate into Page**
   - Import and use the component in the target page or parent component.
   - Verify props are passed correctly.

6. **Verify translation tone (If displaying text)**
   - If the component displays static Japanese text, ensure it follows the "Terrace Vibe" (gentle, desu/masu tone) as described in `paper-translation` skill (adapted for UI text).
