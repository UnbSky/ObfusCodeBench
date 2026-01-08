from llm_caller import call_api
import json
import time
import os
import argparse
from concurrent.futures import ThreadPoolExecutor
import random

prompt_template = (
    "The following code is obfuscated but originally solves a specific programming problem. "
    "Your task is to fully analyze and rewrite it into a clean, readable, and fully deobfuscated version "
    "that preserves the exact original functionality. "
    "The obfuscation may include techniques such as variable name mangling, numeric encoding, string encryption, "
    "or control flow flattening. "
    "When rewriting:\n"
    "- Rename variables, functions, and classes with meaningful and descriptive names.\n"
    "- Maintain the code's simplicity and full executability, preserving and restoring the parts necessary to perform the original functionality.\n"
    "- Ensure the code is easy to understand and functionally equivalent; you may add comments where appropriate to improve readability.\n"
    "- Return only the deobfuscated code (no explanations outside the code).\n"
    "- If the language is Java, ensure the main class is named Main, has a "
    "public static void main(String args[]) entry point, follows Java 11 standards, "
    "and does not use any external libraries.\n"
    "- If the language is Python, do not use any external libraries and ensure compliance with Python 3.9.\n\n"
    "Programming Language: {language}\n"
    "Obfuscated Code:\n{code}\n\n"
    "Deobfuscated Code:\n"
)

key_list_norm = [
    ("ero_code_int", "ero_code_int_regen"),
    ("ero_code_obf", "ero_code_obf_regen"),
    ("ero_code_pro", "ero_code_pro_regen")
]

key_list_type = [
    ("ero_code_jii", "ero_code_jii_regen"),
    ("ero_code_dfi", "ero_code_dfi_regen"),
    ("ero_code_ne", "ero_code_ne_regen"),
    ("ero_code_se", "ero_code_se_regen"),
    ("ero_code_ie", "ero_code_ie_regen")
]

key_list = key_list_type
first_keys_list = [k[0] for k in key_list]


def generate_deobfuscated_code(model_name, index, total, language, code_key, code, attempt, retry_time, args):
    """
    Call the model API to generate deobfuscated code, with retry support.
    """
    if not code.strip():
        return code_key, attempt, "<<EMPTY>>"

    prompt = prompt_template.format(language=language, code=code)

    cut_offset = 0
    for retry in range(1, retry_time + 1):
        try:
            print(f"[{index}/{total}][{code_key}][Attempt {attempt+1} | Retry {retry}] Start")

            start_time = time.time()
            desc, [p_token, c_token] = call_api(
                prompt, model_name, args.max_len - cut_offset, args.client_type
            )
            elapsed = time.time() - start_time

            print(f"[{index}/{total}][{code_key}][Attempt {attempt+1} | Retry {retry}] "
                  f"Finished in {elapsed:.2f}s | Tokens used: {p_token}|{c_token}")
            return code_key, attempt, desc.strip()

        except Exception as e:
            err_msg = str(e)
            print(f"Error on [{index}/{total}][{code_key}][Attempt {attempt+1} | Retry {retry}]: {err_msg}")
            if "Please reduce the length of the messages" in err_msg:
                cut_offset += 400
                print(f"Change max_len to {args.max_len - cut_offset}")
            if retry == retry_time:
                return code_key, attempt, "<<ERROR>>"
            else:
                time.sleep(2)


def process_data(model_name, data, index, total, executor, gen_time, retry_time, args):
    """
    Run deobfuscation multiple times for a single data entry.
    """
    language = data["language"]
    futures = []

    for code_key, desc_key in key_list:
        code = data.get(code_key, "")
        if not code.strip():
            continue

        for i in range(gen_time):
            future = executor.submit(
                generate_deobfuscated_code,
                model_name, index, total, language, code_key, code, i, retry_time, args
            )
            futures.append((future, desc_key))

    desc_results = {}
    for future, desc_key in futures:
        code_key, attempt, result = future.result()
        desc_results.setdefault(desc_key, []).append(result)

    for desc_key, results in desc_results.items():
        data[desc_key] = results

    return data


def compute_expected_calls(json_datas, cache_lookup, gen_time, language_filter, sampled_indices):
    """
    Compute how many API calls are expected considering:
    - language filter
    - cache availability
    - sampling
    """
    expected = 0
    for idx, data in enumerate(json_datas):
        if sampled_indices is not None and idx not in sampled_indices:
            continue

        lang = data["language"].lower()
        task_id = data["task"]

        if (task_id, lang) in cache_lookup:
            continue

        if language_filter != "all" and lang != language_filter:
            if (task_id, lang) not in cache_lookup:
                print(f"[Warning] Task {task_id} (lang={lang}) not found in cache, skipping.")
            continue

        for code_key in first_keys_list:
            code = data.get(code_key, "")
            if code.strip():
                expected += gen_time
            else:
                if code_key == "ero_code_int" and lang == "python":
                    print(f"[Warning] Task {task_id} (lang={lang}) have no {code_key}")
                if code_key in ["ero_code_pro", "ero_code_obf"] and lang == "java":
                    print(f"[Warning] Task {task_id} (lang={lang}) have no {code_key}")
    return expected


def main():
    parser = argparse.ArgumentParser(description="Code deobfuscation & regeneration with LLM")
    parser.add_argument("--model_name", type=str, required=True, help="Model name to use for API call")
    parser.add_argument("--json_path", type=str, required=True, help="Input JSON file path")
    parser.add_argument("--out_path", type=str, required=True, help="Output JSONL file path")
    parser.add_argument("--gen_time", type=int, default=1, help="Number of times to regenerate each code snippet")
    parser.add_argument("--max_workers", type=int, default=8, help="Number of concurrent API calls")
    parser.add_argument("--retry_time", type=int, default=3, help="Max retry attempts if API call fails")
    parser.add_argument("--dry_run", action="store_true", help="If set, only print expected API calls and exit")
    parser.add_argument("--cache_path", type=str, required=True, help="Cache JSONL file path for skipped languages")
    parser.add_argument("--language_filter", type=str, default="all", choices=["all", "python", "java"],
                        help="Filter by language; others will be loaded from cache")
    parser.add_argument("--sample_rate", type=float, default=1.0,
                        help="Sampling rate (0.0-1.0). Proportion of candidate items to actually run generation on.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    parser.add_argument("--max_len", type=int, default=100000, help="Maximum token length for generation")
    parser.add_argument("--client_type", type=str, default="api", help="Client type to use for API call")
    parser.add_argument("--key_type", type=str, choices=["norm", "type"], default="norm",
                        help="Choose which key set to use")

    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)
    
    global key_list, first_keys_list
    if args.key_type == "norm":
        key_list = key_list_norm
    else:
        key_list = key_list_type
    first_keys_list = [k[0] for k in key_list]

    if not (0.0 <= args.sample_rate <= 1.0):
        raise ValueError("sample_rate must be between 0.0 and 1.0")

    with open(args.json_path, "r", encoding="utf-8") as file:
        json_datas = json.load(file)

    cache_lookup = {}
    if os.path.exists(args.cache_path):
        with open(args.cache_path, "r", encoding="utf-8") as cache_file:
            for line in cache_file:
                item = json.loads(line)
                task_id = item["task"]
                lang = item["language"].lower()
                cache_lookup[(task_id, lang)] = item

    candidate_indices = []
    for idx, data in enumerate(json_datas):
        lang = data.get("language", "").lower()
        if args.language_filter == "all" or lang == args.language_filter:
            candidate_indices.append(idx)

    if args.sample_rate < 1.0:
        sample_count = int(len(candidate_indices) * args.sample_rate)
        rnd = random.Random(args.seed)
        if sample_count > 0:
            sampled_candidates = set(rnd.sample(candidate_indices, sample_count))
        else:
            sampled_candidates = set()
        print(f"Sampling enabled: rate={args.sample_rate}, seed={args.seed}, "
              f"candidates={len(candidate_indices)}, selected={len(sampled_candidates)}")
    else:
        sampled_candidates = set(candidate_indices)
        print(f"Sampling disabled or rate=1.0: all {len(sampled_candidates)} candidate items selected")

    expected_calls = compute_expected_calls(
        json_datas, cache_lookup, args.gen_time, args.language_filter, sampled_candidates
    )
    print(f"Dataset size: {len(json_datas)}, gen_time={args.gen_time}, expected API calls={expected_calls}")

    if args.dry_run:
        print("Dry run enabled. Exiting without actual API calls.")
        return

    print(f"Begin processing {len(json_datas)} items with model {args.model_name}")

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor, \
            open(args.out_path, "w", encoding="utf-8") as out_file:

        for index, data in enumerate(json_datas, start=1):
            idx0 = index - 1
            lang = data["language"].lower()
            task_id = data["task"]

            if idx0 in sampled_candidates:
                if (task_id, lang) in cache_lookup:
                    out_file.write(json.dumps(cache_lookup[(task_id, lang)], ensure_ascii=False) + "\n")
                    print(f"[Cache] Task {task_id} (lang={lang}) ->[in cache]<-, skipping.")
                    out_file.flush()
                    continue

                if args.language_filter != "all" and lang != args.language_filter:
                    if (task_id, lang) in cache_lookup:
                        out_file.write(json.dumps(cache_lookup[(task_id, lang)], ensure_ascii=False) + "\n")
                    else:
                        print(f"[Warning] Task {task_id} (lang={lang}) not found in cache, skipping.")
                    out_file.flush()
                    continue

                new_data = process_data(
                    args.model_name, data, index, len(json_datas),
                    executor, args.gen_time, args.retry_time, args
                )
                out_file.write(json.dumps(new_data, ensure_ascii=False) + "\n")
                out_file.flush()

    print("Done.")


if __name__ == "__main__":
    main()