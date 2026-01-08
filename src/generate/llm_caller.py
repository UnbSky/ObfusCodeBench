from openai import OpenAI
import tiktoken

client = OpenAI(api_key="", base_url="") #api key
client_vllm = OpenAI(api_key="", base_url="") #vllm server

def call_api(input_text, model="gpt-5", max_input_tokens=128000, client_type = "api"):
    local_client = client
    if client_type == "vllm":
        local_client = client_vllm

    token_count = 0

    encoding = tiktoken.encoding_for_model("gpt-3.5")
    tokens = encoding.encode(input_text)
    token_count = len(tokens)
    # print("token_count ", token_count)

    if token_count > max_input_tokens:
        print(f"[TO LONG] token {token_count} > {max_input_tokens}")
        tokens = tokens[:max_input_tokens]
        input_text = encoding.decode(tokens)

    response = local_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": input_text}
        ],
        stream=False
    )

    output = response.choices[0].message.content
    completion_tokens = response.usage.completion_tokens
    prompt_tokens = response.usage.prompt_tokens
    return output, [prompt_tokens, completion_tokens]