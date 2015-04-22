import oauth2 as oauthpls
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
from TwitterAPI import TwitterAPI, TwitterRestPager
import twitter


live_streams_header = "[**Live Streams**](##heading)\n\n\n"
tweets_header = "[**SFxTwitter** - 10 Favorites + RT's](##heading)\n\n"
below_tweets = "[**Welcome to /r/StreetFighter!**](##heading)"


def shorten_url(url):
    post_url = 'https://www.googleapis.com/urlshortener/v1/url?key=AIzaSyBHndWCBh_Er1wHmEnw0Lc7WrrIR0pbhaQ'
    postdata = {'longUrl': url}
    headers = {'Content-Type': 'application/json'}
    req = urllib.Request(
        post_url,
        json.dumps(postdata),
        headers
    )
    ret = urllib.urlopen(req).read()
    return json.loads(ret)['id']


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
                   'url': shorten_url(s['channel']['url']),
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
    api2 = twitter.Api(config[0], config[1], config[2], config[3])
    return (api, api2)

def get_good_tweets(api, keywords, tournament_mode, count=5):
    n = 0
    good_tweets = []
    r = TwitterRestPager(api, 'lists/statuses',
                              {'slug': 'fgc', 'owner_screen_name': 'soulsynapse',
                               'count': 1000, 'include_entities': False, 'include_rts': tournament_mode})
    for t in r.get_iterator():
        n += 1
        if len(good_tweets) >= count:
            break
        if 'text' in t and t['retweet_count'] + t['favorite_count'] >= 10:
            if tournament_mode:
                good_tweets.append(t)
            else:
                for k in keywords:
                    if k and re.search(r'\b' + k + r'\b', t['text'].lower().replace('#', '')):
                        good_tweets.append(t)
                        break
    print 'Took me {} tweets to find {} good ones!'.format(n, len(good_tweets))
    return good_tweets


def tweets_to_markdown(tweets):
    md = u''
    for (i, tweet) in enumerate(tweets):
        md += u'>>>[~~{text}~~ ~~P~~ ~~{name}~~ ~~{when}~~]({url}#twt-{i})\n\n'.format(
            i=i,
            text = escape_md(tweet['text'].strip()).replace('\n', ''),
            name = escape_md(tweet['user']['name'].strip()),
            when = arrow.get(tweet['created_at'], 'ddd MMM DD HH:mm:ss Z YYYY').humanize(),
            url = shorten_url('http://twitter.com/{}/status/{}'.format(tweet['user']['screen_name'], tweet['id']))
        )
        md += u'>>[](//)\n\n'
    return md

seen_tweets = []
def update_sidebar(subreddit, r, t, keywords, tournament_mode, t2):
    print "{}: Starting to update sidebar, try not to interrupt.".format(arrow.now().isoformat())
    sys.stdout.flush()
    settings = r.get_settings(subreddit)
    sub = r.get_subreddit(subreddit)
    sidebar = settings['description']
    stylesheet = r.get_stylesheet(sub)['stylesheet']
    
    # update streams
    pat = r"(?<={}).*?(?={})".format(re.escape(live_streams_header),
                                     re.escape(tweets_header))
    try:
        streams = getTopStreams('Ultra Street Fighter IV')
    except urllib.HTTPError:
        print ('HTTPError caught! Going on...')
        streams = []
    stream_md = streams_to_markdown(streams)
    if stream_md:
        updated_sidebar = re.sub(pat, stream_md, sidebar, flags=re.DOTALL|re.UNICODE)
    else:
        print "Twitch didn't give us anything."
        updated_sidebar = sidebar
    if streams:
        makeSpritesheet([s['preview'] for s in streams], 45, 30, 'twitchimages.jpg')    
        r.upload_image(sub, 'twitchimages.jpg')

    # update tweets
    pat = r"(?<={}).*?(?={})".format(re.escape(tweets_header),
                                     re.escape(below_tweets))
    
    tweets = get_good_tweets(t, keywords, tournament_mode)
    tweets_md = tweets_to_markdown(tweets)
    finished_sidebar = re.sub(pat, tweets_md, updated_sidebar, flags=re.DOTALL|re.UNICODE)
    #if tweets:
    #    makeSpritesheet([t['user']['profile_image_url'] for t in tweets], 30, 30, 'twitterimages.jpg')
    #    r.upload_image(sub, 'twitterimages.jpg')

    try:
        # this raises captcha exception but it still works, *shrug*
        r.update_settings(sub, description=finished_sidebar, hide_ads=None)
    except praw.errors.InvalidCaptcha as e:
    # have to do this or it won't show new spritesheet
    try:
        r.set_stylesheet(sub, stylesheet)
    except praw.requests.exceptions.HTTPError as e:
        print "Couldn't set stylesheet (HTTPError)!"
    print "{}: Updated sidebar.".format(arrow.now().isoformat())
    sys.stdout.flush()

    # forward good tweets to subreddit Twitter account
    for tweet in tweets:
        if tweet['id'] not in seen_tweets:
            seen_tweets.append(tweet['id'])
            t2.PostRetweet(tweet['id'])
            print "Tweeted: " + tweet['text'][:50] + "..."
            
    print "\n\n"

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 't':
        print "Starting in tournament mode!"
        tournament_mode = True
    else:
        tournament_mode = False
    import time
    r = praw.Reddit(user_agent='crossplatform:sidebot:v0.1 (by /u/SweetScientist)')
    r.login()
    t,t2 = login_twitter('twitter.conf')
    with open('keywords.txt') as f:
        keywords = f.readlines()
        keywords = [f.strip().lower() for f in keywords]
    while True:
        update_sidebar('streetfighter', r, t, keywords, tournament_mode, t2)
        time.sleep(60)
