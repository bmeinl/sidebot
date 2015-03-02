import praw
import urllib2 as urllib
import json


def getTopStreams(game, count=7):
    from urllib import urlencode
    get_params = urlencode({"game": game})
    req = urllib.Request("https://api.twitch.tv/kraken/streams?" + get_params,
                         headers={"Accept": "application/vnd.twitchtv.v3+json"})
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

    spritesheet.save('spritesheet.jpg')


if __name__ == "__main__":
    print "Woop."
