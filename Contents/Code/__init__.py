import ssl, urllib2

PREFIX = '/video/cbs'
ART = 'art-default.jpg'
ICON = 'icon-default.jpg'

HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.0.2 Safari/605.1.15'
}

SHOWS_URL = 'https://www.cbs.com/shows/{}'
EPISODES_JSON_URL = 'https://www.cbs.com/shows/{}/xhr/episodes/page/0/size/50/xs/0/season/'
TP_VIDEO_URL = 'http://link.theplatform.com/s/dJ5BDC/media/guid/2198311517/{}?mbr=true&assetTypes=StreamPack&formats=MPEG4,M3U'

CATEGORIES = [
    {'category_id': 'originals', 'title': 'Originals'},
    {'category_id': 'drama', 'title': 'Drama'},
    {'category_id': 'comedy', 'title': 'Comedy'},
    {'category_id': 'reality', 'title': 'Reality'},
    {'category_id': 'primetime', 'title': 'Primetime'},
    {'category_id': 'late-night', 'title': 'Late Night'},
    {'category_id': 'daytime', 'title': 'Daytime'},
    {'category_id': 'classics', 'title': 'Classics'},
    {'category_id': 'news', 'title': 'News'}
]

EXCLUDE_SHOWS = []

####################################################################################################
def Start():

    ObjectContainer.title1 = 'CBS'
    DirectoryObject.thumb = R(ICON)

    Dict['episodes'] = {}

    try:
        json_obj = JSON.ObjectFromURL('http://ip-api.com/json', headers=HTTP_HEADERS, cacheTime=10)
    except:
        Log("IP Address Check Failed")
        json_obj = None

    if json_obj and 'countryCode' in json_obj and json_obj['countryCode'] != 'US':
        Log("= WARNING ==========================================================================================")
        Log("  According to your IP address you are not in the United States.")
        Log("  Due to geo-blocking by the content provider, this channel does not work outside the United States.")
        Log("====================================================================================================")

####################################################################################################
@handler(PREFIX, 'CBS', thumb=ICON, art=ART)
def MainMenu():

    oc = ObjectContainer()

    for category in CATEGORIES:

        oc.add(DirectoryObject(
            key = Callback(Shows, cat_title=category['title'], cat_id=category['category_id']),
            title = category['title']
        ))

    return oc

####################################################################################################
@route(PREFIX + '/shows')
def Shows(cat_title, cat_id):

    oc = ObjectContainer(title2=cat_title)
    html = HTML.ElementFromString(GetData(SHOWS_URL.format(cat_id)))

    for item in html.xpath('//article[@class="show-browse-item"]//img'):

        title = item.get('alt')

        if title.lower() in EXCLUDE_SHOWS or 'previews' in title.lower() or 'premieres' in title.lower():
            continue

        slug = item.xpath('./parent::div/parent::a/@href')[0].split('shows/')[-1].split('/')[0]
        thumb = item.get('data-src')

        oc.add(DirectoryObject(
            key = Callback(Episodes, title=title, slug=slug),
            title = title,
            thumb = thumb
        ))

    return oc

####################################################################################################
@route(PREFIX + '/episodes')
def Episodes(title, slug):

    oc = ObjectContainer(title2=unicode(title))
    json_obj = JSON.ObjectFromString(GetData(EPISODES_JSON_URL.format(slug)))

    if 'result' in json_obj and 'data' in json_obj['result']:

        for video in json_obj['result']['data']:

            if video['type'] != "Full Episode" or video['status'] != "AVAILABLE":
                continue

            content_id = video['content_id']

            if content_id not in Dict['episodes']:

                Dict['episodes'][content_id] = {
                    'show': video['series_title'],
                    'title': video['episode_title'],
                    'originally_available_at': Datetime.ParseDate(video['airdate']).date(),
                    'season': video['season_number'],
                    'index': video['episode_number'],
                    'duration': video['duration_raw'] * 1000,
                    'thumb': video['thumb']['large']
                }

            oc.add(CreateEpisodeObject(content_id=content_id))

    if len(oc) < 1:
        Log("There aren't any episodes available for {}.".format(title))
        return ObjectContainer(header="None Available", message="There aren't any episodes available for {}.".format(title))
    else:
        return oc

####################################################################################################
@route(PREFIX + '/create_episodeobject', include_container=bool)
def CreateEpisodeObject(content_id, include_container=False, **kwargs):

    episode = Dict['episodes'][content_id]

    episode_obj = EpisodeObject(
        key = Callback(CreateEpisodeObject, content_id=content_id, include_container=True),
        rating_key = "cbs:{}".format(content_id),
        show = episode['show'],
        title = "{}x{}: {}".format(episode['season'], episode['index'], episode['title']) if episode['season'] and episode['index'] else episode['title'],
        originally_available_at = episode['originally_available_at'],
        season = int(episode['season']) if episode['season'] else None,
        index = int(episode['index']) if episode['index'] and episode['index'].isdigit() else None,
        duration = episode['duration'],
        thumb = episode['thumb'],
        items = [
            MediaObject(
                parts = [
                    PartObject(key=HTTPLiveStreamURL(Callback(PlayVideo, content_id=content_id)))
                ],
                video_resolution = '1080',
                audio_channels = 2,
                optimized_for_streaming = True
            )
        ]
    )

    if include_container:
        return ObjectContainer(objects=[episode_obj])
    else:
        return episode_obj

####################################################################################################
@route(PREFIX + '/playvideo.m3u8')
@indirect
def PlayVideo(content_id, **kwargs):

    try:
        tp = HTTP.Request(TP_VIDEO_URL.format(content_id), headers=HTTP_HEADERS, follow_redirects=False).content
    except Ex.RedirectError, e:
        if 'Location' in e.headers:
            if not '?' in e.headers['Location']:
                video_url = "{}?__b__=5000".format(e.headers['Location'])
            else:
                video_url = "{}&__b__=5000".format(e.headers['Location'])

            return IndirectResponse(VideoClipObject, key=HTTPLiveStreamURL(url=video_url))
        else:
            Log("No redirect URL found")
            raise Ex.MediaNotAvailable
    except:
        Log("HTTP request for TP failed")
        raise Ex.MediaNotAvailable

####################################################################################################
@route(PREFIX + '/getdata')
def GetData(url):

    Log("Requesting '{}'".format(url))

    # Quick and dirty workaround
    # Do not validate ssl certificate
    # http://stackoverflow.com/questions/27835619/ssl-certificate-verify-failed-error
    req = urllib2.Request(url, headers=HTTP_HEADERS)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    data = urllib2.urlopen(req, context=ssl_context).read()

    return data
