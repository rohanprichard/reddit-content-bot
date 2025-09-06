import praw

from secret import secrets

def main():
    reddit = praw.Reddit(
        client_id=secrets.reddit_client_id,
        client_secret=secrets.reddit_client_secret,
        user_agent=secrets.reddit_user_agent
    )

    posts = reddit.subreddit("all").top(time_filter="week")
    for post in posts:
        print(post)

if __name__ == "__main__":
    main()
