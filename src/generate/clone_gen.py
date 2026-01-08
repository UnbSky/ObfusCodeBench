import json
import argparse
import time
import os
import random
from tqdm import tqdm
from llm_caller import call_api
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

norm_keys = [
    ("code", "pred_gen"),
    ("ero_code_int", "pred_ero_int"),
    ("ero_code_obf", "pred_ero_obf"),
    ("ero_code_pro", "pred_ero_pro"),
]

type_keys = [
    ("ero_code_jii", "pred_ero_jii"),
    ("ero_code_dfi", "pred_ero_dfi"),
    ("ero_code_se", "pred_ero_se"),
    ("ero_code_ie", "pred_ero_ie"),
    ("ero_code_ne", "pred_ero_ne"),
]

def process_pair(line, args, clone_keys, total_size, progress_count):
    """Process a single clone pair"""
    pair = json.loads(line)
    item1 = pair["code1"]
    item2 = pair["code2"]
    language = item1.get("language", "Python")

    base_info = {
        key: item1.get(key, None)
        for key in ["path", "index", "language", "task", "token_len"]
    }

    out_record = base_info.copy()
    out_record["label"] = pair.get("label", None)

    prompt_template = (
        "You are given two code snippets written in {language}. "
        "Determine whether they implement the same functionality, regardless of variable names or code structure. "
        "Code clone means that the two snippets solve the same programming problem, "
        "even if the code has been obfuscated or altered. "
        "Do these two code snippets implement the same functionality? "
        "Respond with only 'Yes' if they are clones, or 'No' if they are not.\n\n"
        "Code 1:\n{code1}\n\n"
        "Code 2:\n{code2}\n\n"
        "Respond with only 'Yes' if they are clones, or 'No' if they are not."
    )

    for code_key, pred_key in clone_keys:
        code1 = item1.get(code_key, "")
        code2 = item2.get(code_key, "")

        if not code1 or not code2 or len(code1) <= 1 or len(code2) <= 1:
            out_record[pred_key] = ["<<EMPTY>>"]
            continue

        prompt = prompt_template.format(
            language=language,
            code1=code1,
            code2=code2
        )

        pred_list = []
        cut_offset = args.cut_offset

        for i in range(args.gen_time):
            try:
                start_time = time.time()
                desc, [p_token, c_token] = call_api(
                    prompt,
                    args.model_name,
                    args.max_len - cut_offset,
                    args.client_type
                )
                elapsed = time.time() - start_time

                print(
                    f"[{args.model_name} Call]"
                    f"[Token {p_token}|{c_token}]"
                    f"(Time {elapsed:.2f}s)"
                    f"[{progress_count}/{total_size}]"
                    f"[{code_key}]"
                    f"[Attempt {i+1}] {desc}"
                )

                pred_list.append(desc.strip())
                break

            except Exception as e:
                err_msg = str(e)
                print(f"Error on {code_key} (attempt {i+1}): {err_msg}")

                if "Please reduce the length of the messages" in err_msg:
                    cut_offset += 200
                    print(
                        f"⚠️ Prompt too long, reduce max_len to "
                        f"{args.max_len - cut_offset}"
                    )

                pred_list.append("<<ERROR>>")
                time.sleep(1)

        out_record[pred_key] = pred_list

    return json.dumps(out_record, ensure_ascii=False)

def main(args):
    print(f"=== Begin (mode: {args.model_name}, key_type: {args.key_type}) ===")

    os.makedirs(os.path.dirname(args.out_path), exist_ok=True)

    # Select key set
    if args.key_type == "norm":
        clone_keys = norm_keys
    elif args.key_type == "type":
        clone_keys = type_keys
    else:
        raise ValueError("key_type must be 'norm' or 'type'")

    with open(args.pair_path, "r", encoding="utf-8") as fin, \
         open(args.out_path, "w", encoding="utf-8") as fout:

        lines = fin.readlines()

        # ---------- Sampling ----------
        if args.p < 1.0:
            rng = random.Random(args.seed)
            lines = [line for line in lines if rng.random() < args.p]

        total_size = len(lines)

        print(
            f"Sampling enabled: p={args.p}, seed={args.seed}, "
            f"sampled_pairs={total_size}"
        )

        lock = Lock()

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {
                executor.submit(
                    process_pair,
                    line,
                    args,
                    clone_keys,
                    total_size,
                    idx + 1
                ): idx
                for idx, line in enumerate(lines)
            }

            for future in tqdm(
                as_completed(futures),
                total=total_size,
                desc="Processing"
            ):
                try:
                    result = future.result()
                    with lock:
                        fout.write(result + "\n")
                except Exception as e:
                    print(f"Thread error: {e}")

    print("Done.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate code clone results via API calls (multithreaded)")

    parser.add_argument("--pair_path", type=str, default="")
    parser.add_argument("--out_path", type=str, default="")
    parser.add_argument("--gen_time", type=int, default=1, help="Number of generation attempts per code pair")
    parser.add_argument("--model_name", type=str, default="deepseek-v3", help="Model name used in API")
    parser.add_argument("--client_type", type=str, default="api", help="API client type")
    parser.add_argument("--max_len", type=int, default=100000, help="Max token length per request")
    parser.add_argument("--cut_offset", type=int, default=50, help="Reserved length offset for prompt trimming")
    parser.add_argument("--workers", type=int, default=16, help="Number of concurrent threads")
    parser.add_argument("--key_type", type=str, choices=["norm", "type"], default="norm", help="Choose which key set to use")

    parser.add_argument("--p", type=float, default=1.0, help="Sampling ratio in [0,1], default=1.0 (use all data)")
    parser.add_argument("--seed", type=int, default=42,help="Random seed for sampling")

    args = parser.parse_args()
    main(args)
