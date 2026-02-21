import React, { useState, useRef, useEffect } from "react";
import { STAMP_CATEGORIES, StampType } from "./types";

interface StampPaletteProps {
  isStampMode: boolean;
  onToggleMode: () => void;
  selectedStamp: StampType;
  onSelectStamp: (stamp: StampType) => void;
}

const StampPalette: React.FC<StampPaletteProps> = ({
  isStampMode,
  onToggleMode,
  selectedStamp,
  onSelectStamp,
}) => {
  const [activeCategory, setActiveCategory] = useState(STAMP_CATEGORIES[0].id);
  const [customStamps, setCustomStamps] = useState<StampType[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const saved = localStorage.getItem("customStamps");
    if (saved) {
      try {
        setCustomStamps(JSON.parse(saved));
      } catch (e) {
        console.error("Failed to parse custom stamps");
      }
    }
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Check initial file size limit before upload (e.g. 5MB to be safe, exact limit is 512KB on backend)
    if (file.size > 5 * 1024 * 1024) {
      alert("File is too large. Please select a smaller image.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await fetch("/api/stamps/upload_custom", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Failed to upload image");
      }

      const data = await response.json();
      const newStamps = [data.url, ...customStamps].slice(0, 20); // Keep last 20 custom stamps
      setCustomStamps(newStamps);
      localStorage.setItem("customStamps", JSON.stringify(newStamps));
      onSelectStamp(data.url);
      setActiveCategory("custom");
    } catch (err) {
      alert(err instanceof Error ? err.message : "Upload failed");
    } finally {
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const dynamicCategories = [
    ...STAMP_CATEGORIES,
    { id: "custom", name: "Custom", stamps: customStamps },
  ];

  return (
    <div className="fixed bottom-8 left-1/2 transform -translate-x-1/2 z-50 flex flex-col items-center gap-4 w-full max-w-sm sm:max-w-md px-4">
      {/* Main Toggle Button */}
      <button
        onClick={onToggleMode}
        className={`group px-8 py-4 rounded-full shadow-2xl font-bold transition-all transform hover:scale-105 flex items-center gap-3
                    ${
                      isStampMode
                        ? "bg-indigo-600 text-white ring-4 ring-indigo-200 ring-offset-2"
                        : "bg-white text-slate-700 hover:bg-indigo-50 border border-slate-200"
                    }
                `}
      >
        <span className="text-xl animate-bounce-subtle">
          {isStampMode ? "✨" : "👍"}
        </span>
        <span>{isStampMode ? "Stamp Mode Active" : "Use Stamps"}</span>
      </button>

      {/* Palette Container */}
      <div
        className={`
                w-full bg-white/95 backdrop-blur-md rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.15)] border border-white/20 p-4 transition-all duration-500 ease-out
                ${isStampMode ? "opacity-100 translate-y-0" : "opacity-0 translate-y-12 pointer-events-none"}
            `}
      >
        {/* Category Switcher */}
        <div className="flex space-x-1 mb-4 overflow-x-auto no-scrollbar pb-1">
          {dynamicCategories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`px-3 py-1.5 rounded-full text-xs font-bold whitespace-nowrap transition-all
                                ${
                                  activeCategory === cat.id
                                    ? "bg-indigo-100 text-indigo-700"
                                    : "text-slate-500 hover:bg-slate-100"
                                }
                            `}
            >
              {cat.name}
            </button>
          ))}
        </div>

        {/* Stamp Grid */}
        <div className="grid grid-cols-5 sm:grid-cols-6 gap-3 max-h-48 overflow-y-auto pr-1 custom-scrollbar">
          {dynamicCategories
            .find((c) => c.id === activeCategory)
            ?.stamps.map((s) => (
              <button
                key={s}
                onClick={() => onSelectStamp(s)}
                className={`
                                aspect-square rounded-2xl flex items-center justify-center text-2xl transition-all duration-200 transform hover:scale-125
                                ${
                                  s === selectedStamp
                                    ? "bg-indigo-600 shadow-lg shadow-indigo-200 text-white scale-110"
                                    : "bg-slate-50 text-slate-700 hover:bg-indigo-50 hover:shadow-md"
                                }
                            `}
              >
                {s.startsWith("/") ||
                s.startsWith("http") ||
                s.startsWith("data:image") ? (
                  <img
                    src={s}
                    alt="stamp"
                    className="w-8 h-8 object-contain pointer-events-none rounded-sm"
                  />
                ) : (
                  s
                )}
              </button>
            ))}
          {activeCategory === "custom" && (
            <button
              onClick={() => fileInputRef.current?.click()}
              className="aspect-square rounded-2xl flex items-center justify-center text-xl bg-indigo-50 text-indigo-500 hover:bg-indigo-100 transition-all border-2 border-dashed border-indigo-300 transform hover:scale-110"
              title="Upload Custom Stamp"
            >
              ➕
            </button>
          )}
        </div>
        <input
          type="file"
          accept="image/*"
          ref={fileInputRef}
          className="hidden"
          onChange={handleFileUpload}
        />
      </div>

      <style>{`
                .no-scrollbar::-webkit-scrollbar { display: none; }
                .no-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
                .custom-scrollbar::-webkit-scrollbar { width: 4px; }
                .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
                .custom-scrollbar::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }
            `}</style>
    </div>
  );
};

export default StampPalette;
