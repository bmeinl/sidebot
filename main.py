import praw
import urllib2 as urllib
from urllib import urlencode
import json
from time import strftime
import arrow
from PIL import Image
import io
import re
import twitter
import sys


def escape_md(s):
    return re.sub(r'([*\[\]()>~^])', r'\\\1', s)


def getTopStreams(game, count=7):
    get_params = urlencode({'game': game})
    req = urllib.Request('https://api.twitch.tv/kraken/streams?' + get_params,
                         headers={'Accept': 'application/vnd.twitchtv.v3+json'})
    res = urllib.urlopen(req)
    streams = json.loads(res.read())['streams'][:count]
    try:
        return [ { 'name': s['channel']['name'],
                   'viewers': s['viewers'],
                   'preview': s['preview']['template'],
                   'url': s['channel']['url'],
                   'status': escape_md(s['channel']['status'][:40]),
                   'highlighted': s['viewers'] >= 500
               } for s in streams
        ]
    except KeyError as e:
        return []


def makeSpritesheet(urls, width, height):
    spritesheet = Image.new('RGB', (len(urls) * width, height))

    for i, url in enumerate(urls):
        fd = urllib.urlopen(url.format(width=width, height=height))
        im = Image.open(io.BytesIO(fd.read()))
        spritesheet.paste(im, (i * width, 0))

    spritesheet.save('twitchimages.jpg')


def streams_to_markdown(streams):
    md = u''
    for (i, stream) in enumerate(streams):
        if stream['highlighted']:
            viewers = u'###[{viewers} watching @ {name}](#maxcpm)\n'
        else:
            viewers = u'###{viewers} watching @ {name}\n'
        md += (u">>>#[{status}]({url}#profile-{i})\n" + 
               viewers + u'\n' +
               u"\n" + 
               u">>[](//)\n" + 
               u"\n").format(i=i, **stream)
    return md


def login_twitter(configfile):
    with open(configfile) as f:
        config = [line.strip('\r\n') for line in f]
    api = twitter.Api(consumer_key=config[0], 
                      consumer_secret=config[1],
                      access_token_key=config[2],
                      access_token_secret=config[3])
    return api


def get_good_tweets(api, count=7):
    users = [str(user.id) for user in api.GetListMembers(None, slug='fgc', owner_screen_name='soulsynapse')]
    keywords = ['footsies', 'ultra', 'kappa', 'hype', 'ull', 'lol']
    tweets = api.GetStreamFilter(follow=users)
    return tweets


def update_sidebar(subreddit='streetfightercss', r=None):
    print "{}: Starting to update sidebar, try not to interrupt.".format(arrow.now().isoformat())
    sys.stdout.flush()
    if not r:
        r = praw.Reddit(user_agent='crossplatform:sidebot:v0.1 (by /u/SweetScientist)')
        r.login()
    settings = r.get_settings(subreddit)
    sub = r.get_subreddit(subreddit)
    sidebar = settings['description']
    stylesheet = r.get_stylesheet(sub)['stylesheet']
    pat = r"(?<={}).*?(?={})".format(re.escape("[**Live Streams**](##heading)\n\n\n"),
                                     re.escape("[**SFxTwitter (Broken atm: fix eta Friday)**](##heading)"))
    streams = getTopStreams('Ultra Street Fighter IV')
    stream_md = streams_to_markdown(streams)
    updated_sidebar = re.sub(pat, stream_md, sidebar, flags=re.DOTALL|re.UNICODE)
    try:
        makeSpritesheet([s['preview'] for s in streams], 45, 30)    
    except:
        print 'Something went wrong with spritesheet! # Streams: {}'.format(len(streams))
        return
    r.upload_image(sub, 'twitchimages.jpg')
    try:
        # this raises captcha exception but it still works, *shrug*
        r.update_settings(sub, description=updated_sidebar, hide_ads=None)
    except praw.errors.InvalidCaptcha as e:
        pass
    # have to do this or it won't show new spritesheet
    try:
        r.set_stylesheet(sub, stylesheet)
    except praw.requests.exceptions.HTTPError as e:
        print "Couldn't set stylesheet (HTTPError)!"
    print "{}: Updated sidebar.\n\n".format(arrow.now().isoformat())
    sys.stdout.flush()


if __name__ == '__main__':
    import time
    r = praw.Reddit(user_agent='crossplatform:sidebot:v0.1 (by /u/SweetScientist)')
    r.login()
    while True:
        update_sidebar('streetfighter', r)
        time.sleep(60)

