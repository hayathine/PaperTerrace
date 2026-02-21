// Stamps specific script
const StampsLayer = {
	isStampMode: false,
	selectedStamp: "👍",
	paperId: null,

	init() {
		this.createPalette();
		this.attachEventListeners();
		console.log("StampsLayer initialized");
	},

	createPalette() {
		const palette = document.createElement("div");
		palette.id = "stamp-palette";
		palette.className =
			"fixed bottom-20 left-1/2 transform -translate-x-1/2 bg-white rounded-full shadow-2xl border border-slate-200 p-2 flex space-x-2 transition-all duration-300 translate-y-24 opacity-0 z-50";

		const stamps = ["👍", "❓", "💡", "⚠️", "⭐", "🔥"];

		stamps.forEach((s) => {
			const btn = document.createElement("button");
			btn.className = `w-10 h-10 rounded-full flex items-center justify-center text-lg hover:bg-slate-100 transition-colors ${s === this.selectedStamp ? "bg-indigo-100 ring-2 ring-indigo-300" : ""}`;
			btn.innerHTML = s;
			btn.onclick = () => this.selectStamp(s, btn);
			palette.appendChild(btn);
		});

		document.body.appendChild(palette);
	},

	selectStamp(stamp, btnElement) {
		this.selectedStamp = stamp;
		// UI update
		const palette = document.getElementById("stamp-palette");
		Array.from(palette.children).forEach((c) => {
			c.className =
				"w-10 h-10 rounded-full flex items-center justify-center text-lg hover:bg-slate-100 transition-colors";
		});
		btnElement.className =
			"w-10 h-10 rounded-full flex items-center justify-center text-lg bg-indigo-100 ring-2 ring-indigo-300 hover:bg-indigo-200 transition-colors";
	},

	toggleMode() {
		this.isStampMode = !this.isStampMode;
		const palette = document.getElementById("stamp-palette");
		const stampBtn = document.getElementById("stamp-mode-btn");
		const readerView = document.getElementById("reader-view");

		if (this.isStampMode) {
			palette.classList.remove("translate-y-24", "opacity-0");
			stampBtn.classList.add(
				"bg-indigo-100",
				"text-indigo-600",
				"ring-2",
				"ring-indigo-300",
			);
			readerView.style.cursor = "crosshair";
			this.showToast("スタンプモード: タップしてスタンプを押せます");
		} else {
			palette.classList.add("translate-y-24", "opacity-0");
			stampBtn.classList.remove(
				"bg-indigo-100",
				"text-indigo-600",
				"ring-2",
				"ring-indigo-300",
			);
			readerView.style.cursor = "default";
		}
	},

	attachEventListeners() {
		const readerView = document.getElementById("reader-view");
		// Delegate click event
		readerView.addEventListener("click", (e) => {
			if (!this.isStampMode) return;

			// Prevent default text selection or dictionary lookup if possible?
			// Actually dictionary uses hx-trigger="click".
			// We might collide. If we stopPropagation, htmx might not work.
			// But we want to place stamp INSTEAD of dictionary in stamp mode.

			this.updatePaperId();
			if (!this.paperId) {
				this.showToast("エラー: 論文IDが見つかりません", true);
				return;
			}

			// Calculate position
			const rect = readerView.getBoundingClientRect();
			// Relative to reader content
			// The reader-view has padding.
			// We want coordinates relative to the nearest positioned ancestor OR the reader view itself if it's relative.
			// Note: #reader-view adds paragraphs.

			// Let's rely on event target for positioning if it is inside a page container (for PDF mode)
			// or just global relative to reader-view for text mode.

			// For simplicity, we stick relative to the clicked element's PAGE container if possible?
			const pageContainer = e.target.closest('[id^="page-"]');
			const pageNumber = null;
			const x = e.clientX;
			const y = e.clientY + readerView.scrollTop; // Adjust for scroll?

			// Simplest approach: Place absolutely on the document body where clicked, then calculate relative?
			// No, we want it to scroll with content.

			// Let's create the element at the click position relative to the target container
			const targetRect = e.target.getBoundingClientRect();
			const relativeX = e.clientX - targetRect.left;
			const relativeY = e.clientY - targetRect.top;

			// Store relative coordinate to the clicked PARAGRAPH or PAGE
			// If it's a PDF page, e.target might be the image or a word overlay.

			// Determine context
			let contextId = null;
			if (e.target.id) {
				contextId = e.target.id;
			} else if (e.target.parentElement.id) {
				contextId = e.target.parentElement.id;
			}

			// Place visual stamp
			this.placeVisualStamp(e.pageX, e.pageY, this.selectedStamp);

			// Save to backend
			this.saveStamp(
				this.paperId,
				this.selectedStamp,
				e.pageX,
				e.pageY,
				pageNumber,
			);

			e.stopPropagation(); // Stop dictionary lookup
			e.preventDefault();
		});
	},

	updatePaperId() {
		const input = document.getElementById("current-paper-id");
		if (input && input.value) {
			this.paperId = input.value;
		}
	},

	placeVisualStamp(x, y, symbol) {
		const el = document.createElement("div");
		el.textContent = symbol;
		el.className =
			"absolute text-2xl animate-bounce pointer-events-none select-none z-50 drop-shadow-md";
		el.style.left = x - 12 + "px";
		el.style.top = y - 12 + "px";
		document.body.appendChild(el);

		// Animation reset
		setTimeout(() => {
			el.classList.remove("animate-bounce");
		}, 1000);
	},

	async saveStamp(paperId, type, x, y, pageNum) {
		try {
			await fetch(`/stamps/paper/${paperId}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					stamp_type: type,
					x: x,
					y: y,
					page_number: pageNum, // Optional
				}),
			});
			console.log("Stamp saved");
		} catch (e) {
			console.error("Failed to save stamp", e);
		}
	},

	showToast(msg, isError = false) {
		const toast = document.createElement("div");
		toast.className = `fixed top-20 left-1/2 transform -translate-x-1/2 px-4 py-2 rounded-lg shadow-lg text-sm font-bold text-white z-[100] animate-fade-in ${isError ? "bg-red-500" : "bg-slate-800"}`;
		toast.textContent = msg;
		document.body.appendChild(toast);
		setTimeout(() => toast.remove(), 2000);
	},
};

window.StampsLayer = StampsLayer;
