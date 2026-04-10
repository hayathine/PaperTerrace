import { useState } from "react";
import type { Grounding } from "../components/Chat/types";
import type { SelectedFigure } from "../components/PDF/types";

type Coords = { page: number; x: number; y: number };

export function useWordInteraction() {
	// 翻訳専用 state
	const [translationWord, setTranslationWord] = useState<string | undefined>(
		undefined,
	);
	const [translationContext, setTranslationContext] = useState<
		string | undefined
	>(undefined);
	const [translationCoordinates, setTranslationCoordinates] = useState<
		Coords | undefined
	>(undefined);
	const [translationConf, setTranslationConf] = useState<number | undefined>(
		undefined,
	);

	// 解説専用 state
	const [explanationWord, setExplanationWord] = useState<string | undefined>(
		undefined,
	);
	const [explanationContext, setExplanationContext] = useState<
		string | undefined
	>(undefined);
	const [explanationCoordinates, setExplanationCoordinates] = useState<
		Coords | undefined
	>(undefined);

	// テキスト選択・図表クリッピング用 state
	const [selectedWord, setSelectedWord] = useState<string | undefined>(
		undefined,
	);
	const [selectedContext, setSelectedContext] = useState<string | undefined>(
		undefined,
	);
	const [selectedCoordinates, setSelectedCoordinates] = useState<
		Coords | undefined
	>(undefined);
	const [selectedImage, setSelectedImage] = useState<string | undefined>(
		undefined,
	);

	// ページジャンプ
	const [jumpTarget, setJumpTarget] = useState<{
		page: number;
		x: number;
		y: number;
		term?: string;
	} | null>(null);

	// サイドバー pending state
	const [pendingFigureId, setPendingFigureId] = useState<string | null>(null);
	const [pendingChatPrompt, setPendingChatPrompt] = useState<string | null>(
		null,
	);
	const [selectedFigure, setSelectedFigure] = useState<SelectedFigure | null>(
		null,
	);
	const [activeEvidence, setActiveEvidence] = useState<Grounding | undefined>(
		undefined,
	);

	/** 論文切り替え時などに全 state をリセット */
	const resetWordState = () => {
		setTranslationWord(undefined);
		setTranslationContext(undefined);
		setTranslationCoordinates(undefined);
		setTranslationConf(undefined);
		setExplanationWord(undefined);
		setExplanationContext(undefined);
		setExplanationCoordinates(undefined);
		setSelectedWord(undefined);
		setSelectedContext(undefined);
		setSelectedCoordinates(undefined);
		setSelectedImage(undefined);
		setPendingChatPrompt(null);
		setPendingFigureId(null);
	};

	/** 翻訳対象の単語をセット */
	const setTranslation = (
		word: string,
		context?: string,
		coords?: Coords,
		conf?: number,
	) => {
		setTranslationWord(word);
		setTranslationContext(context);
		setTranslationCoordinates(coords);
		setTranslationConf(conf);
	};

	/** テキスト選択（コメント用） */
	const setTextSelection = (text: string, coords: Coords) => {
		const truncated =
			text.length > 40 ? `${text.substring(0, 37).trim()}...` : text;
		setSelectedWord(truncated);
		setSelectedContext(`> ${text}\n\n`);
		setSelectedImage(undefined);
		setSelectedCoordinates(coords);
	};

	/** エリア選択（図クリッピング用） */
	const setAreaSelection = (imageUrl: string, coords: Coords) => {
		setSelectedWord(`Figure clipping (Page ${coords.page})`);
		setSelectedContext("");
		setSelectedImage(imageUrl);
		setSelectedCoordinates(coords);
	};

	/** AI解説対象をセット */
	const setExplanation = (word: string, context?: string, coords?: Coords) => {
		setExplanationWord(word);
		setExplanationContext(context);
		setExplanationCoordinates(coords);
	};

	return {
		// 翻訳
		translationWord,
		translationContext,
		translationCoordinates,
		translationConf,
		// 解説
		explanationWord,
		explanationContext,
		explanationCoordinates,
		// 選択
		selectedWord,
		selectedContext,
		selectedCoordinates,
		selectedImage,
		// ジャンプ
		jumpTarget,
		setJumpTarget,
		// pending / figure
		pendingFigureId,
		setPendingFigureId,
		pendingChatPrompt,
		setPendingChatPrompt,
		selectedFigure,
		setSelectedFigure,
		activeEvidence,
		setActiveEvidence,
		// アクション
		resetWordState,
		setTranslation,
		setTextSelection,
		setAreaSelection,
		setExplanation,
	};
}
