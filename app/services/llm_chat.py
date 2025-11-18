import requests
import json


def chat_with_deepseek(messages):
    """
    Send messages to DeepSeek-V3.1 and get the assistant's reply.
    
    messages: list of dicts, e.g.
        [
            {"role": "system", "content": "Be a helpful assistant"},
            {"role": "user", "content": "Hi"}
        ]
    """
    url = "https://api.deepinfra.com/v1/openai/chat/completions"
    headers = {"Content-Type": "application/json"}
    payload = {
        "model": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        # "model": "black-forest-labs/FLUX-1-dev",
        "messages": messages,
        "stream": False
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


if __name__ == "__main__":
    messages = [
    {
      "role": "user",
      "content": [
        {
          "type": "image_url",
          "image_url": {
            "url": "https://m.media-amazon.com/images/I/51OzKuZk0iL._SY741_.jpg"
          } 
        },
        {
          "type": "text",
          "text": "Find product attributes and give me list"
        }
      ]
    }
  ]

    reply = chat_with_deepseek(messages)
    print(reply)