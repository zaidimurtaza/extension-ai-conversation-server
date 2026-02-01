import json
import base64
import requests

# Models to try in order when text_only=True; if one fails (non-200), we try the next
CHAT_MODELS = [
    "nvidia/Nemotron-3-Nano-30B-A3B",
    "deepseek-ai/DeepSeek-V3.2",
    "zai-org/GLM-4.7-Flash",
    "moonshotai/Kimi-K2.5",
]

URL = "https://api.deepinfra.com/v1/openai/chat/completions"


def chat_with_deepseek(messages, text_only=False):
    """
    Send messages to the chat API and get the assistant's reply.

    messages: list of dicts, e.g.
        [
            {"role": "system", "content": "Be a helpful assistant"},
            {"role": "user", "content": "Hi"}
        ]

    text_only=True: try each model in CHAT_MODELS in order; if response is not 200,
    try the next model until one succeeds or all fail (user always gets something).
    text_only=False: use only the last model (Kimi).
    """
    if text_only:
        models_to_try = CHAT_MODELS
    else:
        models_to_try = [CHAT_MODELS[-1]]

    last_error = None
    for model in models_to_try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "reasoning_effort": "low",
        }
        response = requests.post(URL, headers=headers, json=payload)

        if response.status_code != 200:
            last_error = f"Error {response.status_code}: {response.text}"
            continue

        data = response.json()
        try:
            return {
                "data": data["choices"][0]["message"]["content"],
                "usage": data.get("usage"),
                "model": data.get("model", model),
            }
        except (KeyError, IndexError):
            return data

    return last_error


def chat_with_image_model(messages):
    """
    Send messages to DeepSeek-V3.1 and get the assistant's reply.
    
    messages: list of dicts, e.g.
        [
            {"role": "system", "content": "Be a helpful assistant"},
            {"role": "user", "content": "Hi"}
        ]
    """
    url = "https://api.deepinfra.com/v1/openai/images/generations"
    headers = {"Content-Type": "application/json"}
    payload = {
    "prompt": "A photo of an astronaut riding a horse on Mars.",
    "size": "1024x1024",
    "model": "black-forest-labs/FLUX-2-pro",
    "n": 1
    }

    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:


        data = response.json()

    

        # This is the response from the model
        response = data  # your JSON object

        # Step 1: extract base64
        b64_image = response["data"][0]["b64_json"]

        # Step 2: decode base64
        image_bytes = base64.b64decode(b64_image)

        # Step 3: write to file
        with open("generated_image.png", "wb") as f:
            f.write(image_bytes)

        print("Image saved successfully")

        print(f"raw data: {json.dumps(data, indent=4   )}   ")


        # image_url = data["data"][0]["url"]
        # image_data = base64.b64encode(requests.get(image_url).content).decode("utf-8")
        
        print(f"raw data: {json.dumps(data, indent=4   )}   ")
        # Extract assistant reply from response
        try:
            return {
            "data": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", None)
            }
        except (KeyError, IndexError):
            return data  # fallback: return full response if format is different
    else:
        return f"Error {response.status_code}: {response.text}"


if __name__ == "__main__":
    messages = [
    {
      "role": "user",
      "content": [
        # {
        #   "type": "image_url",
        #   "image_url": {
        #     "url": "https://m.media-amazon.com/images/I/51OzKuZk0iL._SY741_.jpg"
        #   } 
        # },
        {
          "type": "text",
          "text": "Find product attributes and give me list ony 2 short line"
        }
      ]
    }
  ]

    reply = chat_with_deepseek(messages, text_only=True)
    print(reply)
    # reply = chat_with_image_model(messages)
    # print(reply)