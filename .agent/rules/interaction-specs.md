---
trigger: always_on
---

# Interaction Modes Specifications

This document defines the specifications for the four primary interaction modes in the PaperTerrace PDF Viewer.

## 1. Text Mode (テキストモード)

**Default interaction mode.** Focused on reading and text processing.

### Behavior

- **Cursor**: I-beam (text selection cursor).
- **Interaction**:
  - **Left Click + Drag**: Selects text within the PDF.
  - **Selection End**: Automatically triggers a **Context Menu/Popover** near the selected text.
- **Context Menu Options**:
  - **Translate (和訳)**: Translates the selection to Japanese. Results are displayed in a floating popover or the side panel.
  - **Copy (コピー)**: Copies pure text to clipboard.
  - **Highlight (マーカー)**: Applies a visual highlight (background color) to the text range.
  - **Ask AI (AIに聞く)**: Sends the selected text to the Chat interface as context.

### Technical Requirements

- Utilizes `TextLayer` from the PDF renderer (`react-pdf` / `pdf.js`).
- Must handle column-aware text selection (preserving reading order).

## 2. Click Mode (クリックモード)

**Object-based interaction mode.** Focused on exploring structured elements (Figures, Tables, Citations).

### Behavior

- **Cursor**: Default arrow, changes to Pointer (Hand) when hovering over interactable elements.
- **Interaction**:
  - **Hover**: specific bounding boxes (BBox) of recognized elements light up or show a subtle border.
  - **Left Click**: Activates the element.
- **Element Actions**:
  - **Figures/Images**: Opens the figure in a **Lightbox/Modal** for detailed view.
  - **Citations/Refs**: Shows a **Tooltip** with the full bibliography entry and a link to jump to the References section.
  - **Equations**: (Future) Shows LaTeX source or explanation.

### Technical Requirements

- Depends on **Layout Analysis** results (BBoxes of `Figure`, `Table`, etc.) stored in the database.
- **Lazy Loading**: Layout detection may run in the background after the page is first rendered. Interactive bboxes appear dynamically once analysis completes.
- requires an overlay layer that maps coordinate systems between the PDF page and the screen.

## 3. Crop Mode (切り取りモード)

**Region-based interaction mode.** Focused on capturing arbitrary visual information.

### Behavior

- **Cursor**: Crosshair (十).
- **Interaction**:
  - **Left Click + Drag**: Draws a rectangular selection box (Rubber-banding style).
  - **Visual Feedback**: Semi-transparent overlay indicating the selected area.
  - **Release**: Finalizes the crop area and opens an Action Menu.
- **Action Menu Options**:
  - **Add to Note (ノートに追加)**: Saves the cropped image to the side notes.
  - **Explain (解説)**: Sends the image (or coordinates) to the Multimodal AI for explanation.

### Technical Requirements

- Coordinate translation: `(Screen X, Y)` -> `(PDF Page X, Y, W, H)`.
- Backend support for on-demand image cropping or frontend canvas-based extraction (`canvas.toDataURL`).

## 4. Stamp Mode (スタンプモード)

**Annotation interaction mode.** Focused on "Casual & Relaxed" marking and feedback.

### UI Components

- **Stamp Toolbar**: A floating or fixed bar displaying available stamps.
- **Stamp Types**:
  - `👍` (Good/Like)
  - `👀` (Read later/Check)
  - `❓` (Question)
  - `⭐️` (Important)
  - `💡` (Idea)

### Behavior

- **Cursor**: Replaced by the icon of the currently selected stamp (faded/translucent).
- **Interaction**:
  - **Left Click**: Places the stamp at the specific `(Page, X, Y)` coordinates.
  - **Right Click (on existing stamp)**: Deletes the stamp.
  - **Hover (on existing stamp)**: Shows timestamp.
- **Persistence**:
  - Stamps are saved to the backend via `POST /stamps/paper/{id}`.
  - Stamps persist across sessions.

### Technical Requirements

- Stamps must scale appropriately with the PDF zoom level (anchored to PDF coordinates, not Screen coordinates).
- Backend storage (already implemented in `backend/app/routers/stamps.py`).
