# ClipsToDiscord

automatically posts twitch clips to discord.
uses the raspberrypi and cron to check my twitch channel every 5 minutes to see if there are any new clips.
If there are clips, then automatically posts it on discord using webhooks.

Uses the discord-webhook module https://pypi.org/project/discord-webhook/

runs every 5 minutes using cron:
*/5 * * * * python /path/of/script

This script is not very nicely written. I'm a beginner programmer. So there is a likely chance that this only works on my rpi and not anyone elses. If that is the case i'm sorry. lol
