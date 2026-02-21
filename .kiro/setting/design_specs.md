# Design & Interaction Specifications

## 🎨 UI/UX

### 1. PDF Viewer

- **Rendering**: Pages are rendered as images. A transparent layer of BBoxes (Bounding Boxes) is overlaid for text selection and interaction.
- **Lazy Loading**: Text layer and page images are streamed (Phase 1). Layout detection for clickable objects follows (Phase 2).
- **Responsive**: Adapts to screen width while maintaining the paper's aspect ratio.
- **Feedback**: ALWAYS show loading/success/error states.

### 2. General Guidelines

- **Tone**: "Intellectual & Relaxed". Gentle "Desu/Masu" for Japanese text.
- **Visuals**: Premium, modern aesthetics. Use shadows, glassmorphism, and smooth transitions.
- **Responsiveness**: Mobile-first recommended.

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
- **Note**: Interactive bboxes are loaded lazily as background analysis completes.

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

- **PDF Viewing**: Custom Image-based renderer with transparent `TextLayer` and `OverlayLayer` for interaction.
- **State**:
  - `AuthContext`: User session.
  - `ThemeContext`: Dark/Light mode.
  - `PaperContext`: Current paper data and interaction mode.
