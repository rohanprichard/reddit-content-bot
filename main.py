import praw
import os
import uuid as uuid_lib
from time import time

from media import compose_video_with_speech
from secret import secrets, video_path, music_path
from util import generate_story
from voice import generate_audio
from transcribe import transcribe_words, words_to_single_word_events


REDDIT_SUBREDDIT = "nosleep"
REDDIT_TIME_FILTER = "year"
REDDIT_LIMIT = 1

def main():
    reddit = praw.Reddit(
        client_id=secrets.reddit_client_id,
        client_secret=secrets.reddit_client_secret,
        user_agent=secrets.reddit_user_agent
    )

    posts = reddit.subreddit(REDDIT_SUBREDDIT).top(time_filter=REDDIT_TIME_FILTER, limit=REDDIT_LIMIT)

    for post in posts:
        start_time = time()
        uuid = str(uuid_lib.uuid4())
        os.makedirs(f"data/{uuid}", exist_ok=True)

        print(f"Scraped {post.title} --- \n{len(post.selftext)} chars")

        post = generate_story(post.title + "\n\n" + post.selftext, uuid)
        story_generation_time = time() - start_time
        print(f"Generated {post.title} --- \n{len(post.story)} chars. Time taken: {story_generation_time} seconds")

        file = generate_audio(post.title + "\n\n" + post.story, uuid)
        audio_generation_time = time() - story_generation_time
        print(f"Generated audio {file}. Time taken: {audio_generation_time} seconds")

        words = transcribe_words(audio_path=f"data/{uuid}/audio.mp3", model_name="base", device="cpu")
        ass_events = words_to_single_word_events(words)

        output = compose_video_with_speech(
            speech_audio_path=f"data/{uuid}/audio.mp3",
            background_video_path=video_path,
            background_music_path=music_path,
            output_video_path=f"data/{uuid}/final.mp4",
            music_volume_db_reduction=0.0,
            enable_ducking=False,
            playback_speed=1.2,
            ass_events=ass_events,
            ass_font_name="SF Pro Display",
            ass_font_size=80,
            ass_primary_color="&H0000FFFF&",  # yellow
            ass_outline_color="&H00222222&",
            ass_italic=True,
            ass_bold=False,
            ass_outline=4,
            ass_shadow=0,
            burn_captions=True,
        )
        video_generation_time = time() - audio_generation_time
        print(f"Generated video {output}. Time taken: {video_generation_time} seconds")

        end_time = time()
        print(f"Time taken: {end_time - start_time} seconds")


if __name__ == "__main__":
    main()
