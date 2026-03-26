import time
import os
import sys

# Set search path
sys.path.append("/app")

from llama_cpp import Llama

# New Prompts
TRANSLATE_SYSTEM_PROMPT = """You are an expert academic research assistant.
Translate the target English text into the requested language using the provided academic paper context.
Prioritize domain-specific accuracy.
Output ONLY the translated word or phrase. Do NOT include any explanations or meta-comments.
Example: "Context: outperforms SOTA models. Target: SOTA" -> "最先端の" """

DICT_TRANSLATE_LLM_PROMPT = """[Academic Context]
{paper_context}

[Target Text]
{target_word}
[Target Language]: {lang_name}

Translation:"""

MODEL_PATH = os.environ.get("LLAMACPP_MODEL_PATH")

def run_bench(llm, paper_context, target_word, lang_name, config_name):
    print(f"\n--- Testing: {config_name} ---")
    
    user_content = DICT_TRANSLATE_LLM_PROMPT.format(
        paper_context=paper_context,
        target_word=target_word,
        lang_name=lang_name
    )
    
    messages = [
        {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
        {"role": "user", "content": user_content}
    ]
    
    start_time = time.time()
    res = llm.create_chat_completion(
        messages=messages,
        max_tokens=10,
        temperature=0.0
    )
    elapsed = time.time() - start_time
    output = res["choices"][0]["message"]["content"].strip()
    
    # Check for prefix cache hits in the console output if possible, 
    # but here we just show times.
    print(f"  Result: {output}")
    print(f"  Time: {elapsed:.2f}s")
    return elapsed

if __name__ == "__main__":
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=1024,
        n_threads=4,
        n_batch=512,
        use_mlock=True,
        verbose=True
    )

    ctx = "This is a test context for the translation service. It discusses something complex."
    word = "complex"
    
    print("\n[FIRST CALL] (Should compute instructions + context + word)")
    run_bench(llm, ctx, word, "Japanese", "First Call")
    
    print("\n[SECOND CALL] (Same everything - should hit cache for everything including context)")
    run_bench(llm, ctx, word, "Japanese", "Second Call (Same)")
    
    print("\n[THIRD CALL] (Different word, but same instructions - should hit cache for instructions)")
    run_bench(llm, ctx, "test", "Japanese", "Third Call (New Word)")
    
    print("\n[FOURTH CALL] (Different context - should only hit cache for instructions)")
    ctx2 = "Another different context about artificial intelligence."
    run_bench(llm, ctx2, "intelligence", "Japanese", "Fourth Call (New Context)")
