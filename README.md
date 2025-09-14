# Reddit Content Generator

I built a tool to help me generate reddit story-style videos with python, ffmpeg, claude and elevenlabs. It takes a subreddit and gets the top posts, a background audio and an background video file. 

## Input Parameters

 - Subreddit name
 - Number of posts
 - Sorting interval 
 - background audio in mp3
 - background video in mp4

```
REDDIT_SUBREDDIT = "nosleep"
REDDIT_TIME_FILTER = "year"
REDDIT_LIMIT = 1
```
Modify the variables above to your needs.

 ## Secret Variables

 - Elevenlabs API Key
 - Claude API Key
 - Reddit credentials

 ---

 ### Reddit credentials
 1. Log in to Reddit ￼

  Make sure you’re logged into your Reddit account. If you don’t have one, sign up at reddit.com

  2. Go to the App Preferences Page ￼

  Visit the Reddit app preferences page: https://www.reddit.com/prefs/apps ​⁠.

  3. Create a New Application ￼
  - Scroll down to the “Developed Applications” section.
  - Click “Create App” or “Create Another App”.

  4. Fill Out the Application Form ￼
  - Name: Choose a name for your app.
  - Description: (Optional) Add a description.
  - Redirect URI: For scripts, use `http://localhost:8000` or any valid URL (required even if not used).
  - Type: Select script type.

  5. Submit and Get Your Credentials ￼

  After submitting, you’ll see your app listed with:
  - Client ID 
  - Client Secret
  - User-Agent
  
  Use these as credentials for this project.

## Setup

Choose your audio and video files and store it in the data directory. 

Then, install the dependencies by running
```
uv sync
```
and then

```
uv run main.py
```

The final videos will be in 
```
data/{id}/final.mp4.
```
## License

This project is under an MIT license.