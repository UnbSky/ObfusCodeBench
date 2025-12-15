import os
import subprocess
import shutil
from multiprocessing import Pool, cpu_count

def obfuscate_file(index_info):
    index, rawcode_base, output_base = index_info
    raw_dir = os.path.join(rawcode_base, str(index))
    main_py_path = os.path.join(raw_dir, "main.py")
    if not os.path.isdir(raw_dir) or not os.path.isfile(main_py_path):
        return f"Jump：{raw_dir}"

    output_dir = os.path.join(output_base, str(index))
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    shutil.copytree(raw_dir, output_dir)

    in_main = os.path.join(raw_dir, "main.py")
    out_main = os.path.join(output_dir, "main.py")

    try:
        cmd = f"pyobfuscate -f {in_main} > {out_main}"
        print("Running:", cmd)
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if proc.returncode != 0:
            return f"Error（{raw_dir}）：{proc.stderr.strip()}"

        return f"Finish（{output_dir}）"

    except FileNotFoundError:
        return "Error No pyobfuscate"
    except subprocess.SubprocessError as e:
        return f"（{raw_dir}）：{e}"


def main():
    rawcode_base = "code_s_task_scaled/rawcode"
    output_base = "code_s_task_scaled/decompiled_code_python"

    index_list = []
    index = 0
    while True:
        raw_dir = os.path.join(rawcode_base, str(index))
        main_py_path = os.path.join(raw_dir, "main.py")
        if not os.path.isdir(raw_dir):
            break
        if os.path.isfile(main_py_path):
            index_list.append((index, rawcode_base, output_base))
        index += 1

    n_tasks = len(index_list)
    processes = min(10, cpu_count())
    with Pool(processes=processes) as pool:
        for result in pool.imap_unordered(obfuscate_file, index_list):
            print(result)


if __name__ == "__main__":
    main()
