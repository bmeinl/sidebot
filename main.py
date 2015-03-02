import praw
import urllib2 as urllib
import json
from time import strftime
import arrow


def getTopStreams(game, count=7):
    from urllib import urlencode
    get_params = urlencode({'game': game})
    req = urllib.Request('https://api.twitch.tv/kraken/streams?' + get_params,
                         headers={'Accept': 'application/vnd.twitchtv.v3+json'})
    res = urllib.urlopen(req)
    streams = json.loads(res.read())['streams'][:count]
    return [ { 'name': s['channel']['name'],
               'viewers': s['viewers'],
               'preview': s['preview']['template'],
               'url': s['channel']['url'],
               'status': s['channel']['status'],
             } for s in streams
           ]


def makeSpritesheet(urls, width, height):
    from PIL import Image
    import io

    spritesheet = Image.new('RGB', (len(urls) * width, height))

    for i, url in enumerate(urls):
        fd = urllib.urlopen(url.format(width=width, height=height))
        im = Image.open(io.BytesIO(fd.read()))
        spritesheet.paste(im, (i * width, 0))

    spritesheet.save('twitchimages.jpg')


def streams_to_markdown(streams):
    md = [(u">>>#[{status}]({url}#profile-{i})\n"
           u"###{viewers} watching @ {name}\n"
           u"\n"
           u">>[](//)\n"
           u"\n").format(i=i, **stream)
          for (i, stream) in enumerate(streams)
      ]
    return ''.join(md)


def main(subreddit='streetfightercss'):
    import re
    r = praw.Reddit(user_agent='crossplatform:sidebot:v0.1 (by /u/SweetScientist)')
    r.login()
    settings = r.get_settings(subreddit)
    sub = r.get_subreddit(subreddit)
    sidebar = settings['description']
    stylesheet = r.get_stylesheet(sub)['stylesheet']
    pat = r"(?<={}).*?(?={})".format(re.escape("[**Live Streams**](http://reddit.com/#heading)\n\n\n"),
                                     re.escape("[**SFxTwitter**](http://reddit.com/#heading)"))
    streams = getTopStreams('Ultra Street Fighter IV')
    print len(streams)
    stream_md = streams_to_markdown(streams)
    updated_sidebar = re.sub(pat, stream_md, sidebar, flags=re.DOTALL|re.UNICODE)
    makeSpritesheet([s['preview'] for s in streams], 45, 30)    
    r.upload_image(sub, 'twitchimages.jpg')
    try:
        # this raises captcha exception but it still works, *shrug*
        r.update_settings(sub, description=updated_sidebar)
    except praw.errors.InvalidCaptcha as e:
        pass
    # have to do this or it won't show new spritesheet
    r.set_stylesheet(sub, stylesheet)
    print "{}: Updated sidebar.".format(arrow.now().isoformat())

if __name__ == '__main__':
    main()
