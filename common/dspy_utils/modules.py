import random
from typing import Callable

import dspy

from common.dspy_utils.signatures import (
    AdversarialCritique,
    BuildDecisionProfile,
    ChatGeneral,
    ContextAwareTranslation,
    DeepExplanation,
    ExtractUserTraits,
    PaperRecommendation,
    PaperSummary,
    PaperSummaryContext,
    PaperSummarySections,
    PersonaAdapterSignature,
    SentenceTranslation,
    SimpleTranslation,
    SolveTask,
    SystemContextSignature,
    VisionAnalyzeFigure,
)


class PromptCandidatePool:
    """GEPA の Pareto フロントから生成された複数の最適化済みプロンプト候補を管理するプール。

    呼び出しのたびにランダムに1つの候補を選択することで、
    各候補のパフォーマンスをオンラインで比較・評価できる。
    選択された候補インデックスは TraceContext.candidate_index に記録する。

    使用例::

        pool = PromptCandidatePool.from_pg(PaperSummaryModule, "paper_summary")
        module, idx = pool.select()
        context.candidate_index = idx
        result, trace_id = await trace_dspy_call(..., module_callable=module, context=context)
    """

    def __init__(self, candidates: list[dspy.Module]) -> None:
        if not candidates:
            raise ValueError("candidates must not be empty")
        self.candidates = candidates

    def select(self) -> tuple[dspy.Module, int]:
        """候補をランダムに1つ選択して返す。

        Returns:
            (選択されたモジュール, そのインデックス) のタプル。
        """
        idx = random.randrange(len(self.candidates))
        return self.candidates[idx], idx

    def __len__(self) -> int:
        return len(self.candidates)

    @classmethod
    def from_pg(
        cls,
        module_factory: Callable[[], dspy.Module],
        program_name: str,
    ) -> "PromptCandidatePool":
        """logs.prompt_candidates テーブルから最新の Pareto 候補をロードしてプールを生成する。

        候補が存在しない場合は module_factory() による単一モジュールで初期化する。

        Args:
            module_factory: 新規モジュールインスタンスを生成する callable。
            program_name: PostgreSQL 上の識別子（例: 'paper_summary'）。
        """
        from common.dspy_utils.prompt_store import load_candidates

        candidates = load_candidates(module_factory, program_name)
        return cls(candidates)


class UserPersonaModule(dspy.Module):
    """ユーザーの行動ログから特性を抽出し、推論方針（ペルソナ）を構築する2段階のモジュール"""

    def __init__(self):
        super().__init__()
        self.extract_traits = dspy.Predict(ExtractUserTraits)
        self.build_persona = dspy.Predict(BuildDecisionProfile)

    def forward(self, behavior_logs: str, current_logs: str, user_feedback: str):
        # 1. 行動ログから特性（興味、専門性、好みなど）を抽出
        traits = self.extract_traits(behavior_logs=behavior_logs)

        # 2. 抽出された特性と現在の状況を組み合わせて推論用ペルソナを構築
        result = self.build_persona(
            current_logs=current_logs,
            user_feedback=user_feedback,
            interests=traits.interests,
            expertise_level=traits.expertise_level,
            explanation_preference=traits.explanation_preference,
            key_words=traits.key_words,
            stress_level=traits.stress_level,
        )
        return result


class SystemModule(dspy.Module):
    """
    グローバルシステムコンテキストを生成するモジュール。

    出力はユーザー非依存の不変制約（役割定義・言語強制・品質基準）のみを含む。
    """

    def __init__(self):
        super().__init__()
        self.generate = dspy.Predict(SystemContextSignature)

    def forward(self, task_type: str, lang_name: str) -> str:
        result = self.generate(task_type=task_type, lang_name=lang_name)
        return result.system_context


class PersonaAdapter(dspy.Module):
    """
    ユーザーペルソナとタスク種別から純粋な行動指示（persona_instruction）を生成するアダプター。

    GEPA 最適化の対象はこのモジュールのみ。system_context の制約に従いつつ、
    コンテンツ（input_data）には依存せず「どう振る舞うか」という行動ポリシーのみを出力する。
    """

    def __init__(self):
        super().__init__()
        self.adapter = dspy.Predict(PersonaAdapterSignature)

    def forward(
        self,
        system_context: str,
        user_persona: str,
        task_description: str,
        lang_name: str,
    ) -> str:
        result = self.adapter(
            system_context=system_context,
            user_persona=user_persona,
            task_description=task_description,
            lang_name=lang_name,
        )
        return result.persona_instruction


class UniversalTaskModule(dspy.Module):
    """
    4層パイプラインで任意の下流タスクを実行する汎用モジュール。

    パイプライン構造:
        [Layer 0] SystemModule (_compiled=True で凍結)
            task_type + lang_name → system_context

        [Layer 1] UserPersonaModule (最適化対象, オプション)
            behavior_logs + current_logs + user_feedback → user_persona
            ※ behavior_logs が渡されない場合は user_persona 引数にフォールバック

        [Layer 2] PersonaAdapter (最適化対象)
            system_context + user_persona + task_description + lang_name → persona_instruction

        [Layer 3] downstream Predict (_compiled=True で凍結)
            persona_instruction + task_inputs → 出力

    GEPA は Layer 1 (UserPersonaModule) と Layer 2 (PersonaAdapter) を最適化する。
    Layer 0, 3 は _compiled=True を設定することで DSPy 公式の凍結メカニズムにより
    optimizer のパラメータ走査対象から除外される。
    downstream は __init__ 時に拡張した固定シグネチャで実行する。
    """

    _TASK_DESCRIPTIONS: dict[str, str] = {
        "PaperSummary": "Summarize an academic paper into structured sections.",
        "PaperSummarySections": "Summarize an academic paper section by section.",
        "PaperSummaryContext": "Generate a brief context summary of a paper segment.",
        "ContextAwareTranslation": "Translate a technical word with academic context awareness.",
        "SimpleTranslation": "Translate a word or phrase concisely.",
        "PaperRecommendation": "Recommend related academic papers based on the current paper.",
        "AdversarialCritique": "Critically review an academic paper for hidden assumptions and risks.",
        "VisionAnalyzeFigure": "Analyze a figure or chart from an academic paper.",
        "ChatGeneral": "Answer a user's question about an academic paper.",
    }

    # Layer 0, 1, 3 がパイプライン内部で消費するキー（Layer 3 の solve に渡さない）
    _PIPELINE_INTERNAL_KEYS = frozenset(
        {"behavior_logs", "current_logs", "user_feedback", "user_persona"}
    )

    def __init__(self, signature=SolveTask):
        super().__init__()
        self.target_signature = signature
        # Layer 0: システムコンテキスト（_compiled=True で凍結 → optimizer の走査対象外）
        self.system_module = SystemModule()
        self.system_module._compiled = True
        # Layer 1: ユーザーペルソナ生成（最適化対象 → _compiled を設定しない）
        self.user_persona_module = UserPersonaModule()
        # Layer 2: ペルソナアダプター（最適化対象 → _compiled を設定しない）
        self.persona_adapter = PersonaAdapter()
        # Layer 3: 下流シグネチャに persona_instruction と lang_name を動的追加
        # 既にフィールドが存在するシグネチャへの重複追加を防止
        extended_sig = signature
        if "persona_instruction" not in signature.input_fields:
            extended_sig = extended_sig.append(
                "persona_instruction",
                dspy.InputField(
                    desc="Behavioral policy from PersonaAdapter: tone, terminology, and explanation depth guidelines"
                ),
                type_=str,
            )
        if "lang_name" not in extended_sig.input_fields:
            extended_sig = extended_sig.append(
                "lang_name",
                dspy.InputField(desc="Target language name for the response"),
                type_=str,
            )
        self.solve = dspy.Predict(extended_sig)
        # Layer 3: downstream Predict を凍結（_compiled=True → optimizer の走査対象外）
        self.solve._compiled = True

    def _get_task_description(self) -> str:
        sig_name = self.target_signature.__name__
        return self._TASK_DESCRIPTIONS.get(sig_name, f"Perform the {sig_name} task.")

    def forward(self, **kwargs):
        lang_name = kwargs.get("lang_name", "")
        sig_name = self.target_signature.__name__

        # Layer 0: 固定システムコンテキストを生成（凍結）
        system_context = self.system_module(
            task_type=sig_name,
            lang_name=lang_name,
        )

        # Layer 1: behavior_logs が渡された場合は UserPersonaModule でペルソナを動的生成（最適化対象）。
        # 渡されない場合は user_persona 引数にフォールバック（後方互換性）。
        behavior_logs = kwargs.get("behavior_logs", "")
        if behavior_logs:
            persona_result = self.user_persona_module(
                behavior_logs=behavior_logs,
                current_logs=kwargs.get("current_logs", ""),
                user_feedback=kwargs.get("user_feedback", ""),
            )
            user_persona = persona_result.user_persona
        else:
            user_persona = kwargs.get("user_persona", "")

        # Layer 2: ユーザーペルソナ + システムコンテキストから行動ポリシーを生成（GEPA最適化対象）
        persona_instruction = self.persona_adapter(
            system_context=system_context,
            user_persona=user_persona,
            task_description=self._get_task_description(),
            lang_name=lang_name,
        )

        # Layer 3: パイプライン内部キーを除いた kwargs を downstream に渡して実行
        solve_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in self._PIPELINE_INTERNAL_KEYS
        }
        return self.solve(persona_instruction=persona_instruction, **solve_kwargs)


# --- 以下、UniversalTaskModule のラッパーとして各モジュールを定義 ---


class RecommendationModule(UniversalTaskModule):
    """論文の解析結果とユーザープロフィールを照らし合わせ、パーソナライズされた推薦を行うモジュール"""

    def __init__(self):
        super().__init__(PaperRecommendation)

    def forward(
        self,
        paper_title: str,
        paper_abstract: str,
        user_profile: str,
        **kwargs,
    ):
        result = super().forward(
            paper_title=paper_title,
            paper_abstract=paper_abstract,
            user_profile=user_profile,
            **kwargs,
        )

        # 推薦固有の制約
        dspy.Assert(len(result.recommendations) >= 3, "推薦は3件以上必要")
        dspy.Assert(len(result.search_queries) >= 2, "検索クエリは2件以上必要")

        profile_lower = user_profile.lower()
        dspy.Suggest(
            not ("初級" in user_profile or "beginner" in profile_lower)
            or any("survey" in r.lower() for r in result.recommendations),
            "初級ユーザーにはsurvey論文を含めることを推奨",
        )

        return result


class PaperSummaryModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(PaperSummary)

    def forward(self, paper_text: str, **kwargs):
        return super().forward(
            input_data=paper_text,
            **kwargs,
        )


class SectionSummaryModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(PaperSummarySections)

    def forward(self, paper_text: str, **kwargs):
        return super().forward(
            input_data=paper_text,
            **kwargs,
        )


class ContextSummaryModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(PaperSummaryContext)

    def forward(self, paper_text: str, max_length: int = 500, **kwargs):
        return super().forward(
            input_data=paper_text,
            max_length=max_length,
            **kwargs,
        )


class AdversarialModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(AdversarialCritique)

    def forward(self, paper_text: str, **kwargs):
        return super().forward(
            input_data=paper_text,
            **kwargs,
        )


class TranslationModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(ContextAwareTranslation)

    def forward(self, paper_context: str, target_word: str, **kwargs):
        return super().forward(
            paper_context=paper_context,
            input_data=target_word,
            **kwargs,
        )


class SimpleTranslationModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(SimpleTranslation)

    def forward(self, paper_context: str, target_word: str, **kwargs):
        return super().forward(
            paper_context=paper_context,
            input_data=target_word,
            **kwargs,
        )


class SentenceTranslationModule(dspy.Module):
    """文章全体を翻訳するシンプルなモジュール。UniversalTaskModule を経由しない直接 Predict。"""

    def __init__(self):
        super().__init__()
        self.translate = dspy.Predict(SentenceTranslation)

    def forward(
        self,
        paper_context: str,
        target_word: str,
        lang_name: str = "Japanese",
        **kwargs,
    ):
        return self.translate(
            input_data=target_word,
            paper_context=paper_context,
            lang_name=lang_name,
        )


class DeepExplanationModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(DeepExplanation)

    def forward(self, summary_context: str, context: str, target_word: str, **kwargs):
        return super().forward(
            summary_context=summary_context,
            context=context,
            input_data=target_word,
            **kwargs,
        )


class VisionFigureModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(VisionAnalyzeFigure)

    def forward(self, caption_hint: str, **kwargs):
        return super().forward(
            input_data=caption_hint,
            **kwargs,
        )


class ChatModule(UniversalTaskModule):
    def __init__(self):
        super().__init__(ChatGeneral)

    def forward(
        self, document_context: str, history_text: str, user_message: str, **kwargs
    ):
        return super().forward(
            document_context=document_context,
            history_text=history_text,
            user_message=user_message,
            input_data=user_message,
            **kwargs,
        )
