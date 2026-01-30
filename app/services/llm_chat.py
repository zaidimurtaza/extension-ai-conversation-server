import requests
import json
import base64

def chat_with_deepseek(messages, text_only=False):
    """
    Send messages to DeepSeek-V3.1 and get the assistant's reply.
    
    messages: list of dicts, e.g.
        [
            {"role": "system", "content": "Be a helpful assistant"},
            {"role": "user", "content": "Hi"}
        ]
    """
    model = "nvidia/Nemotron-3-Nano-30B-A3B" if text_only else "moonshotai/Kimi-K2.5"
    url = "https://api.deepinfra.com/v1/openai/chat/completions"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": model,
        # "model": "black-forest-labs/FLUX-1-dev",
        "messages": messages,
        "stream": False,
        "reasoning_effort": "high"
    }

    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        data = response.json()
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
          "text": "Find product attributes and give me list"
        }
      ]
    }
  ]

    reply = chat_with_deepseek(messages, text_only=True)
    print(reply)
    # reply = chat_with_image_model(messages)
    # print(reply)