import praw
import urllib2 as urllib
from urllib import urlencode
import json
from time import strftime
import arrow
from PIL import Image
import io
import re
import sys
from TwitterAPI import TwitterAPI


def escape_md(s):
    return re.sub(r'([*\\[\]()>~^#])', r'\\\1', s)


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


def makeSpritesheet(urls, width, height, filename):
    spritesheet = Image.new('RGB', (len(urls) * width, height))

    for i, url in enumerate(urls):
        fd = urllib.urlopen(url.format(width=width, height=height))
        im = Image.open(io.BytesIO(fd.read()))
        spritesheet.paste(im, (i * width, 0))

    spritesheet.save(filename)


def streams_to_markdown(streams):
    if not streams: return False
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
    api = TwitterAPI(config[0], config[1], config[2], config[3])
    return api


def get_good_tweets(api, count=5):
    good_tweets = []
    for t in api.request('lists/statuses', {'slug': 'fgc', 'owner_screen_name': 'soulsynapse',
                                            'count': 100, 'include_entities': False, 'include_rts': False}):
        if len(good_tweets) >= count: break
        if 'text' in t and t['retweet_count'] + t['favorite_count'] >= 10:
            good_tweets.append(t)
    return good_tweets


def tweets_to_markdown(tweets):
    md = u''
    for (i, tweet) in enumerate(tweets):
        md += u'>>>[~~{text}~~ ~~PIC~~ ~~{name}~~ ~~{when}~~]({url}#twt-{i})\n\n'.format(
            i=i,
            text = escape_md(tweet['text'].strip()),
            name = escape_md(tweet['user']['name'].strip()),
            when = arrow.get(tweet['created_at'], 'ddd MMM DD HH:mm:ss Z YYYY').humanize(),
            url = 'http://twitter.com/{}/status/{}'.format(tweet['user']['screen_name'], tweet['id']))
        md += u'>>[](//)\n\n'
    return md


def update_sidebar(subreddit, r, t):
    print "{}: Starting to update sidebar, try not to interrupt.".format(arrow.now().isoformat())
    sys.stdout.flush()
    settings = r.get_settings(subreddit)
    sub = r.get_subreddit(subreddit)
    sidebar = settings['description']
    stylesheet = r.get_stylesheet(sub)['stylesheet']
    
    # update streams
    pat = r"(?<={}).*?(?={})".format(re.escape("[**Live Streams**](##heading)\n\n\n"),
                                     re.escape("[**SFxTwitter**](##heading)"))
    streams = getTopStreams('Ultra Street Fighter IV')
    stream_md = streams_to_markdown(streams)
    if stream_md:
        updated_sidebar = re.sub(pat, stream_md, sidebar, flags=re.DOTALL|re.UNICODE)
    else:
        print "Twitch didn't give us shat."
        updated_sidebar = sidebar
    if streams:
        makeSpritesheet([s['preview'] for s in streams], 45, 30, 'twitchimages.jpg')    
        r.upload_image(sub, 'twitchimages.jpg')

    # update tweets
    pat = r"(?<={}).*?(?={})".format(re.escape("[**SFxTwitter**](##heading)\n\n"),
                                     re.escape("[**Subreddit Rules**](##heading)"))
    
    tweets = get_good_tweets(t)
    tweets_md = tweets_to_markdown(tweets)
    with open('tweets_md', 'w') as f: print >>f, tweets_md.encode('utf-8')
    finished_sidebar = re.sub(pat, tweets_md, updated_sidebar, flags=re.DOTALL|re.UNICODE)
    with open('finished', 'w') as f: print >>f, finished_sidebar.encode('utf-8')
    #if tweets:
    #    makeSpritesheet([t['user']['profile_image_url'] for t in tweets], 30, 30, 'twitterimages.jpg')
    #    r.upload_image(sub, 'twitterimages.jpg')

    try:
        # this raises captcha exception but it still works, *shrug*
        r.update_settings(sub, description=finished_sidebar, hide_ads=None)
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
    t = login_twitter('twitter.conf')
    while True:
        update_sidebar('streetfighter', r, t)
        time.sleep(60)
