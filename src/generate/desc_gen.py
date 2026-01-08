import argparse
import json
import os
import time
import hashlib
from llm_caller import call_api
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

progress_count = 0
progress_lock = threading.Lock()

key_list_norm = [
    ("code", "desc_gen"),
    ("ero_code_int", "ero_desc_int"),
    ("ero_code_obf", "ero_desc_obf"),
    ("ero_code_pro", "ero_desc_pro")
]

key_list_type = [
    ("ero_code_jii", "ero_desc_jii"),
    ("ero_code_dfi", "ero_desc_dfi"),
    ("ero_code_ne", "ero_desc_ne"),
    ("ero_code_se", "ero_desc_se"),
    ("ero_code_ie", "ero_desc_ie")
]

key_list = key_list_norm


def get_code_hash(code: str) -> str:
    """Generate hash of code for cache deduplication"""
    return hashlib.md5(code.encode("utf-8")).hexdigest()


def load_cache(cache_path: str):
    """Load cache data from cache_path into a dictionary"""
    print(cache_path)
    if not os.path.exists(cache_path):
        print(f"[Cache] No cache found at {cache_path}")
        return {}

    cache = {}
    with open(cache_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                item = json.loads(line.strip())
                for code_key, desc_key in key_list:
                    code = item.get(code_key, "")
                    if code.strip():
                        h = get_code_hash(code)
                        cache[(h, code_key)] = item.get(desc_key, [])
            except Exception as e:
                print(f"[Cache] Error reading line: {e}")
    print(f"[Cache] Loaded {len(cache)} entries from {cache_path}")
    return cache


def process_one(index, data, cache, args, prompt_template, total_size):
    global progress_count

    language = data["language"]

    for code_key, desc_key in key_list:
        code = data.get(code_key, "")
        if code_key != "code" and not code.strip():
            continue

        code_hash = get_code_hash(code)

        if (code_hash, code_key) in cache:
            data[desc_key] = cache[(code_hash, code_key)]
            if not args.dry_run:
                with progress_lock:
                    progress_count += 1
                    print(f"[Cache Hits][{code_key}] [{progress_count}/{total_size}] {data[desc_key]}")
            continue

        if args.dry_run:
            with progress_lock:
                progress_count += 1
            return data, len(key_list)

        prompt = prompt_template.format(language=language, code=code)

        desc_list = []
        cut_offset = 0
        for i in range(args.gen_time):
            try:
                start_time = time.time()
                desc, [p_token, c_token] = call_api(
                    prompt, args.mode_name, args.max_len - cut_offset, args.client_type
                )
                elapsed = time.time() - start_time
                desc_list.append(desc.strip())
                with progress_lock:
                    progress_count += 1
                    print(
                        f"[{args.mode_name} Call][Token {p_token}|{c_token}]"
                        f"(Time {elapsed:.2f}s)[{progress_count}/{total_size}]"
                        f"[{code_key}][Attempt {i+1}] {desc}"
                    )
                break
            except Exception as e:
                err_msg = str(e)
                print(f"Error on {code_key} (attempt {i+1}): {err_msg}")
                if "Please reduce the length of the messages" in err_msg:
                    cut_offset += 400
                    print(f"Change max_len to {args.max_len - cut_offset}")
                time.sleep(1)

        data[desc_key] = desc_list

    return data, 0


def main(args):
    global key_list

    if args.key_type == "norm":
        key_list = key_list_norm
    else:
        key_list = key_list_type

    with open(args.json_path, "r", encoding="utf-8") as file:
        json_datas = json.load(file)

    cache = load_cache(args.cache_path)

    prompt_template = (
        "Given the following code which solves a problem, write a concise and objective code summary. "
        "The provided code may be obfuscated, so try to understand its original purpose. "
        "The summary must start with 'The code ...' and should be fluent, precise, and easy to understand. "
        "Focus only on what the code is designed to accomplish. "
        "Do not mention implementation details such as input/output constraints, time or memory limits. "
        "Exclude technical phrases like 'with the result returned modulo 998244353' from the summary. "
        "Prefer a short one-sentence summary that clearly explains what problem the code is solving. "
        "Programming Language: {language}\n"
        "Code:\n{code}\n\n"
        "One-sentence Short Code Summarization:"
    )

    total_calls = 0
    cached_hits = 0

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)

    lock = threading.Lock()

    with open(args.out_path, "w", encoding="utf-8") as out_file:
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [
                executor.submit(process_one, idx, data, cache, args, prompt_template, len(json_datas))
                for idx, data in enumerate(json_datas)
            ]

            for future in as_completed(futures):
                data, add_calls = future.result()
                total_calls += add_calls

                if not args.dry_run:
                    with lock:
                        out_file.write(json.dumps(data, ensure_ascii=False) + "\n")
                        out_file.flush()

    if args.dry_run:
        print(f"[{args.mode_name} Dry Run] Total model calls needed: {total_calls}")
        print(f"[{args.mode_name} Dry Run] Cached hits: {cached_hits}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode_name", type=str, default="gpt-4o-mini")
    parser.add_argument("--client_type", type=str, default="api")
    parser.add_argument("--json_path", type=str, default="")
    parser.add_argument("--out_path", type=str, default="")
    parser.add_argument("--cache_path", type=str, default="")
    parser.add_argument("--max_len", type=int, default=100000)
    parser.add_argument("--gen_time", type=int, default=100)
    parser.add_argument("--dry_run", action="store_true", help="If set, do not call model, only count needed calls")
    parser.add_argument("--key_type", type=str, choices=["norm", "type"], default="type",
                        help="Choose which key set to use")
    args = parser.parse_args()

    print(f"--->[[[Start {args.mode_name} with max_workers=8]]]<---")

    main(args)
