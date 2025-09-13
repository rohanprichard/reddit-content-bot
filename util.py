import anthropic
import instructor
import elevenlabs

from secret import secrets
from model import Story


prompt = ""

with open("data/prompt.txt", "r") as file:
    prompt = file.read()

anthropic_client = anthropic.Anthropic(
    api_key=secrets.anthropic_api_key
)
client = instructor.from_anthropic(anthropic_client)
elevenlabs_client = elevenlabs.ElevenLabs(
    api_key=secrets.elevenlabs_api_key
)

def generate_story(story: str, uuid: str):
    response = client.chat.completions.create(
        model="claude-sonnet-4-20250514",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": story}
        ],
        max_tokens=1000,
        temperature=0.6,
        response_model=Story
    )

    with open(f"data/{uuid}/story.txt", "w") as file:
        file.write(response.title + "\n\n" + response.story)

    return response