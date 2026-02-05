# Design & Interaction Specifications

## 🎨 UI/UX Guidelines

- **Tone**: "Intellectual & Relaxed". Gentle "Desu/Masu" for Japanese text.
- **Visuals**: Premium, modern aesthetics. Use shadows, glassmorphism, and smooth transitions.
- **Responsiveness**: Mobile-first recommended.
- **Feedback**: ALWAYS show loading/success/error states.

## 🖱️ Interaction Modes

### 1. Text Mode (Default)

- **Action**: Select text.
- **Menu**:
  - **Translate**: Instant Japanese translation.
  - **Ask AI**: Chat with selection as context.
  - **Highlight**: Mark text.
  - **Copy**: Copy text.

### 2. Click Mode (Object Explorer)

- **Target**: Figures, Tables, Citations.
- **Visual**: Hover effects on bounding boxes.
- **Action**: Click to open Lightbox (Figures) or Tooltip (Citations).

### 3. Crop Mode (Capture)

- **Action**: Drag to select area (Rubber-banding).
- **Menu**:
  - **Add to Note**: Save image to notes.
  - **Explain**: Multimodal AI explains the visual content.

### 4. Stamp Mode (Annotation)

- **Tools**: 👍 Good, 👀 Check, ❓ Question, ⭐️ Important.
- **Action**: Click to place stamp on PDF coordinates.
- **Persistence**: Saved to backend, persists across sessions.

## 🧩 Frontend Architecture

- **PDF Viewing**: `react-pdf` with custom overlay layers for functionality (Highlights, BBoxes).
- **State**:
  - `AuthContext`: User session.
  - `ThemeContext`: Dark/Light mode.
  - `PaperContext`: Current paper data and interaction mode.
