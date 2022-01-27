import requests
import os
import time
import json
import sys
import datetime
import configparser
from discord_webhook import DiscordWebhook, DiscordEmbed
import schedule
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Debug Mode
# Set both to true
DISCORD_SEND = True # should It send the clip to discord
SAVE_TO_CHECK = True # should it add clip to checked file
HOURS_BACK = 1 # How many hours back should it check for clips

# Globals
PWD = os.path.dirname(os.path.abspath(__file__))
CONFIGPATH = PWD + "/config.ini"
CHECKEDPATH = PWD + "/checked.txt"
config = ''


def datetimeToIso(n):
    iso = n.isoformat() + "Z"
    logging.info(f'turning {n} to {iso}')
    return iso

def configParse(config_path):
    logging.info(f'parsing config file: {config_path}')
    con = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    con.read(config_path)
    return con

class twitchToDisc:

    def __init__(self):
        global config
        # global config (change to config file in future)
        self.broadcaster_id = config["twitch"]["broadcaster_id"]
        self.client_id = config["twitch"]["client_id"]
        self.client_secret = config["twitch"]["client_secret"]
        self.auth_token = self.getToken()
        self.headers = {
                "Authorization": "Bearer "+ self.auth_token["access_token"],
                "Client-Id": self.client_id}
    
    def getToken(self):
        authUrl = "https://id.twitch.tv/oauth2/token?client_id=" + self.client_id + "&client_secret=" + self.client_secret + "&grant_type=client_credentials"
        try:
            auth_info = requests.post(authUrl)
            auth_info.raise_for_status()
            auth_infoDic = json.loads(auth_info.text)
            logging.info("gotten authentication")
        except requests.exceptions.RequestException as e:
            logging.error(f"Authentication error: {e}")
            sys.exit()
        
        return auth_infoDic


    def getClips(self, started_at, ended_at):
        logging.info(f'Getting clips')

        clipsUrl = "https://api.twitch.tv/helix/clips?broadcaster_id=" + self.broadcaster_id + "&first=20&started_at=" + started_at + "&ended_at=" + ended_at

        clips_info = requests.get(clipsUrl, headers=self.headers)
        
        clips_infoJSON = json.loads(clips_info.text)
        clips_data = clips_infoJSON["data"]
        if clips_data:
            for i in clips_data:
                logging.info(f"Clip: {i['id']}")
        else:
            logging.info('No clips')
        return clips_infoJSON

    def getVideo(self, videoId):
        logging.info("getting video information")
        url = "https://api.twitch.tv/helix/videos?id=" + videoId
        video_info =  requests.get(url, headers=self.headers)
        video_infoJSON = json.loads(video_info.text)
        video_data = video_infoJSON["data"]
        if video_data:
            logging.info(f"Got video Info: {video_data[0]['title']}")
        return video_infoJSON


    def cleanClips(self, clips):
        # cleans the clips from accidental creation of clips
        # removes clips that has the same name as vods
        logging.info("Cleaning clips: Removing accidents")
        new_clip_data = {"data": []}
        for clip in clips["data"]:
            clip_title = clip["title"]
            clip_vod_origin_id = clip["video_id"]
            video_info = self.getVideo(clip_vod_origin_id)
            video_data = video_info["data"][0]
            video_title = video_data["title"]

            if video_title != clip_title:
                # not accidental clips
                logging.info(f"'{clip_title}' does not match '{video_title}' Must be a new clip!")
                new_clip_data["data"].append(clip)
            else:
                logging.info(f"video and clip has same name. Must be an accidental clip!")
        return new_clip_data

    def getUsers(self, login):
        logging.info(f'Getting users')
        usersUrl = "https://api.twitch.tv/helix/users?login=" + login 
        users_info = requests.get(usersUrl, headers=self.headers)
        return json.loads(users_info.text)

    def getPfp(self, login):
        user_info = self.getUsers(login)
        pfp = user_info["data"][0]["profile_image_url"]
        logging.info(f"getting pfp: {pfp}")
        return pfp

def thumbnailToMp4(thumbnail_url):
    mp4 = thumbnail_url.split("-preview")[0] + ".mp4"
    logging.info(f"Getting mp4 url: {mp4}")
    return mp4

def getMp4(url):
    r = requests.get(url)
    return r.content

def formatUTC(utc):
    logging.info(f'formating utc to something else')
    utcDatetime = datetime.datetime.strptime(utc, "%Y-%m-%dT%H:%M:%SZ")
    formatted = utcDatetime.strftime("%b %d, %Y %I:%M%p")
    return formatted

def discordPost(clip_item):
    global config
    logging.info(f'Posting to discord')
    clip_url = clip_item["url"]
    embed_url = clip_item["embed_url"]
    creator_name = clip_item["creator_name"]
    clip_title = clip_item["title"]
    thumb_url = clip_item["thumbnail_url"]
    created_at = clip_item["created_at"]

    down_url = thumbnailToMp4(thumb_url)
    mp4_file = getMp4(down_url)

    created_atFMT = formatUTC(created_at)


    content = f"**New clip created by {creator_name}**\n{clip_url}"

    
    webhook = DiscordWebhook(
        url=config['discord']['webhook'],
        content=content
    )
    response = webhook.execute()


def main(): 

    global config
    config = configParse(CONFIGPATH)
    twitch = twitchToDisc()
    logging.info(f'Initializing twitch wrapper')

    now = datetime.datetime.utcnow()
    started_at = now - datetime.timedelta(hours=HOURS_BACK)
    nowIso = datetimeToIso(now)
    started_atIso = datetimeToIso(started_at)


    dirty_clips = twitch.getClips(started_atIso, nowIso)
    if dirty_clips["data"]:
        clips = twitch.cleanClips(dirty_clips)["data"]
    else:
        logging.info(f"[!] No clips made in the {HOURS_BACK} hour")
        sys.exit()
    
    with open(CHECKEDPATH, 'r+') as f:
        checked_clips = [x.strip('\n') for x in f.readlines()]
        for clip_item in clips:
            clip_id = clip_item["id"]
            logging.info(f"[!] Checking {clip_id}")
            if clip_id not in checked_clips:
                if DISCORD_SEND:
                    discordPost(clip_item)
                    logging.info(f"[!] Posting to discord: {clip_id}")
                if SAVE_TO_CHECK:
                    f.write(clip_id + "\n")
                    logging.info(f"[!] Saving {clip_id} to file")
            else:
                logging.info(f"[!] {clip_id} already uploaded")

main()
#config = configParse(CONFIGPATH)
#print(config.get('discord', 'webhook'))
