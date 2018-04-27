ART = 'art-default.jpg'
ICON = 'icon-default.jpg'

SHOWS_URL = 'https://www.cbs.com/shows/%s'
SECTION_CAROUSEL = 'https://www.cbs.com/carousels/videosBySection/%s/offset/0/limit/40/xs/0'
CATEGORIES = [
    {'category_id': 'primetime', 'title': 'Primetime'},
    {'category_id': 'daytime', 'title': 'Daytime'},
    {'category_id': 'late-night', 'title': 'Late Night'},
    {'category_id': ' ', 'title': 'All Shows'}
]

RE_SECTION_IDS = Regex('(?:video\.section_ids = |"section_ids"\:)\[([^\]]+)\]')
RE_SECTION_METADATA = Regex('(?:video.section_metadata = |"section_metadata"\:)({.+?}})')
RE_SEASONS = Regex('video.seasons = (.+?);', Regex.DOTALL)

EXCLUDE_SHOWS = []

####################################################################################################
def Start():

    try:
        json_obj = JSON.ObjectFromURL('http://ip-api.com/json', cacheTime=10)
    except:
        Log("IP Address Check Failed")
        json_obj = None

    if json_obj and 'countryCode' in json_obj and json_obj['countryCode'] != 'US':
        Log("= WARNING ==========================================================================================")
        Log("  According to your IP address you are not in the United States.")
        Log("  Due to geo-blocking by the content provider, this channel does not work outside the United States.")
        Log("====================================================================================================")

    ObjectContainer.title1 = 'CBS'
    HTTP.CacheTime = CACHE_1HOUR
    HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36'

####################################################################################################
@handler('/video/cbs', 'CBS', thumb=ICON, art=ART)
def MainMenu():

    oc = ObjectContainer()

    for category in CATEGORIES:

        oc.add(DirectoryObject(
            key = Callback(Shows, cat_title=category['title'], category=category['category_id']),
            title = category['title']))

    return oc

####################################################################################################
@route('/video/cbs/shows')
def Shows(cat_title, category):

    oc = ObjectContainer(title2=cat_title)
    html = HTML.ElementFromURL(SHOWS_URL % (category))

    for item in html.xpath('//ul[@id="id-shows-list"]/li//img'):

        title = item.get('title')

        if title in EXCLUDE_SHOWS or 'Previews' in title or 'Premieres' in title:
            continue

        url = item.xpath('./parent::a/@href')[0]
        if not url.startswith('http'):
            url = 'https://www.cbs.com/%s' % url.lstrip('/')
        if not url.endswith('/video/'):
            url = '%s/video/' % url.rstrip('/')

        thumb = item.get('src')

        oc.add(DirectoryObject(
            key = Callback(Category, title=title, url=url, thumb=thumb),
            title = title,
            thumb = Resource.ContentsOfURLWithFallback(thumb)
        ))

    return oc

####################################################################################################
@route('/video/cbs/category')
def Category(title, url, thumb):

    oc = ObjectContainer(title2=unicode(title))

    try: content = HTTP.Request(url).content
    except: return ObjectContainer(header="Empty", message="Can't find video's for this show.")

    try: 
        carousel_list = RE_SECTION_IDS.search(content).group(1).split(',')
        carousel_metalist = RE_SECTION_METADATA.search(content).group(1)
    except:
        carousel_list = []
	
    for carousel in carousel_list:

        json_url = SECTION_CAROUSEL % carousel

        # If there are seasons displayed then the json URL for each season must be pulled
        try:
            display_seasons = JSON.ObjectFromString(carousel_metalist)[carousel]['display_seasons']
        except:
            display_seasons = False

        if display_seasons:

            title = JSON.ObjectFromString(carousel_metalist)[carousel]['title']
            season_list = RE_SEASONS.search(content).group(1)

            oc.add(DirectoryObject(
                key = Callback(Seasons, title=title, thumb=thumb, json_url=json_url, season_list=season_list),
                title = title,
                thumb = Resource.ContentsOfURLWithFallback(thumb)
            ))
        else:
            json_obj = JSON.ObjectFromURL(json_url)

            if json_obj['success']:

                title = json_obj['result']['title']

                oc.add(DirectoryObject(
                    key = Callback(Video, title=title, json_url=json_url),
                    title = title,
                    thumb = Resource.ContentsOfURLWithFallback(thumb)
                ))

    if len(oc) < 1:
        Log ('still no value for objects')
        return ObjectContainer(header="Empty", message="There are no video sections to list right now.")
    else:
        return oc

####################################################################################################
# This function pulls the season numbers for any season that contains free content to add to the json url
@route('/video/cbs/seasons')
def Seasons(title, thumb, json_url, season_list):

    oc = ObjectContainer(title2=title)

    try: season_json = JSON.ObjectFromString(season_list)
    except: return ObjectContainer(header="Empty", message="Can't find video's for this season.")
    
    for item in season_json['filter']:
        # Skip seasons that only offer premium content
        if item["total_count"] == item["premiumCount"]:
            continue
        title = item["title"]
        season_url = '%s/%s/' %(json_url, item["season"])
        json_obj = JSON.ObjectFromURL(season_url)
        if json_obj['success']:
            oc.add(DirectoryObject(
                key = Callback(Video, title=title, json_url=season_url),
                title = title,
                thumb = Resource.ContentsOfURLWithFallback(thumb)
            ))

    if len(oc) < 1:
        Log ('still no value for objects')
        return ObjectContainer(header="Empty", message="There are no seasons to list right now.")
    else:
        return oc
####################################################################################################
@route('/video/cbs/video')
def Video(title, json_url):

    oc = ObjectContainer(title2=title)

    for video in JSON.ObjectFromURL(json_url)['result']['data']:

        if 'status' in video and video['status'].lower() != 'available':
            continue

        title = video['title'].split(' - ', 1)[-1]
        vid_type = video['type']

        thumb = video['thumb']['large']
        if not thumb:
            thumb = video['thumb']['small']

        airdate = Datetime.ParseDate(video['airdate']).date()

        url = video['url']
        if not url.startswith('http'):
            url = 'https://www.cbs.com/%s' % url.lstrip('/')

        if vid_type == 'Clip':
            oc.add(VideoClipObject(
                url = url,
                title = title,
                originally_available_at = airdate,
                thumb = Resource.ContentsOfURLWithFallback(thumb)
            ))
        elif vid_type == 'Full Episode':
            show = video['series_title']

            (season, episode, duration) = (video['season_number'], video['episode_number'], video['duration'])
            season = int(season) if season is not None and season != '' else None
            # found an episode value that had two numbers separated by a comma so use try/except instead
            try: index = int(episode)
            except: index = 0
            duration = Datetime.MillisecondsFromString(duration) if duration is not None else None
            summary = video['description'] if 'description' in video else None
            
            oc.add(EpisodeObject(
                url = url,
                show = show,
                title = title,
                summary = summary,
                originally_available_at = airdate,
                season = season,
                index = index,
                duration = duration,
                thumb = Resource.ContentsOfURLWithFallback(thumb)
            ))

    oc.objects.sort(key=lambda obj: obj.originally_available_at, reverse=True)
    if len(oc) < 1:
        Log ('still no value for objects')
        return ObjectContainer(header="Empty", message="There are no videos to list right now.")
    else:
        return oc
