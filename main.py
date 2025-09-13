import praw
import os
import uuid as uuid_lib
from time import time

from media import compose_video_with_speech
from secret import secrets, video_path, music_path
from util import generate_story
from voice import generate_audio


def main():
    reddit = praw.Reddit(
        client_id=secrets.reddit_client_id,
        client_secret=secrets.reddit_client_secret,
        user_agent=secrets.reddit_user_agent
    )

    posts = reddit.subreddit("nosleep").top(time_filter="all", limit=1)

    for post in posts:
        start_time = time()
        uuid = str(uuid_lib.uuid4())
        os.makedirs(f"data/{uuid}", exist_ok=True)

        print(f"Scraped {post.title} --- \n{len(post.selftext)} chars")

        post = generate_story(post.title + "\n\n" + post.selftext, uuid)
        story_generation_time = time() - start_time
        print(f"Generated {post.title} --- \n{len(post.story)} chars. Time taken: {story_generation_time} seconds")

        file = generate_audio(post.story, uuid)
        audio_generation_time = time() - story_generation_time
        print(f"Generated audio {file}. Time taken: {audio_generation_time} seconds")

        output = compose_video_with_speech(
            speech_audio_path=file,
            background_video_path=video_path,
            background_music_path=music_path,
            output_video_path=f"data/{uuid}/final.mp4",
            music_volume_db_reduction=8.0,
            enable_ducking=True,
        )
        video_generation_time = time() - audio_generation_time
        print(f"Generated video {output}. Time taken: {video_generation_time} seconds")

        end_time = time()
        print(f"Time taken: {end_time - start_time} seconds")


if __name__ == "__main__":
    main()
