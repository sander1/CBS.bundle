ART = 'art-default.jpg'
ICON = 'icon-default.jpg'

SHOWS_URL = 'https://www.cbs.com/shows/{}'
SECTION_CAROUSEL = 'https://www.cbs.com/carousels/videosBySection/{}/offset/0/limit/40/xs/0'
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

RE_SECTION_IDS = Regex('(?:video\.section_ids = |"section_ids"\:)\[([^\]]+)\]')
RE_SECTION_METADATA = Regex('(?:video\.section_metadata = |"section_metadata"\:)({.+?}})')
RE_SEASONS = Regex('video\.seasons = (.+?);', Regex.DOTALL)

EXCLUDE_SHOWS = []

PREFIX = '/video/cbs'

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
    html = HTML.ElementFromURL(SHOWS_URL.format(cat_id))

    for item in html.xpath('//article[@class="show-browse-item"]//img'):

        title = item.get('alt')

        if title.lower() in EXCLUDE_SHOWS or 'previews' in title.lower() or 'premieres' in title.lower():
            continue

        url = item.xpath('./parent::div/parent::a/@href')[0]

        if not url.startswith('http'):
            url = 'https://www.cbs.com/{}'.format(url.lstrip('/'))

        if not url.endswith('/video/'):
            url = '{}/video/'.format(url.rstrip('/'))

        thumb = item.get('data-src')

        oc.add(DirectoryObject(
            key = Callback(Category, title=title, url=url, thumb=thumb),
            title = title,
            thumb = thumb
        ))

    return oc

####################################################################################################
@route(PREFIX + '/category')
def Category(title, url, thumb):

    oc = ObjectContainer(title2=unicode(title))

    try:
        content = HTTP.Request(url).content
    except:
        return ObjectContainer(header="Empty", message="Can't find videos for this show.")

    try:
        carousel_list = RE_SECTION_IDS.search(content).group(1).split(',')
        carousel_metalist = RE_SECTION_METADATA.search(content).group(1)
    except:
        carousel_list = []

    for carousel in carousel_list:

        json_obj = JSON.ObjectFromString(carousel_metalist)[carousel]

        if 'all access' in json_obj['title'].lower() or json_obj['title'].lower() == 'free full episodes':
            continue

        json_url = SECTION_CAROUSEL.format(carousel)

        # If there are seasons displayed then the json URL for each season must be pulled
        try:
            display_seasons = json_obj['display_seasons']
        except:
            display_seasons = False

        if display_seasons:

            season_list = RE_SEASONS.search(content)

            if not season_list:
                continue

            season_json = JSON.ObjectFromString(season_list.group(1))

            for item in season_json['filter']:

                # Check if there are seasons that have free content
                if item['total_count'] == item['premiumCount']:
                    continue
                else:
                    title = json_obj['title']

                    oc.add(DirectoryObject(
                        key = Callback(Seasons, title=title, thumb=thumb, json_url=json_url, season_list=season_list.group(1)),
                        title = title,
                        thumb = thumb
                    ))

                    break
        else:

            json_obj = JSON.ObjectFromURL(json_url)

            if json_obj['success']:

                # Check for at least 1 available video before adding this section
                for video in json_obj['result']['data']:

                    if 'status' in video and video['status'].lower() == 'available':

                        title = json_obj['result']['title']

                        oc.add(DirectoryObject(
                            key = Callback(Video, title=title, json_url=json_url),
                            title = title,
                            thumb = thumb
                        ))

                        break

                    else:
                        continue

    if len(oc) < 1:
        Log("There are no video sections to list right now.")
        return ObjectContainer(header="Empty", message="There are no video sections to list right now.")
    else:
        return oc

####################################################################################################
# This function pulls the season numbers for any season that contains free content to add to the json url
@route(PREFIX + '/seasons')
def Seasons(title, thumb, json_url, season_list):

    oc = ObjectContainer(title2=title)

    try:
        season_json = JSON.ObjectFromString(season_list)
    except:
        return ObjectContainer(header="Empty", message="Can't find videos for this season.")

    for item in season_json['filter']:

        # Skip seasons that only offer premium content
        if item['total_count'] == item['premiumCount']:
            continue

        title = item['title']
        season_url = '{}/{}/'.format(json_url, item['season'])

        json_obj = JSON.ObjectFromURL(season_url)

        if json_obj['success']:

            oc.add(DirectoryObject(
                key = Callback(Video, title=title, json_url=season_url),
                title = title,
                thumb = thumb
            ))

    if len(oc) < 1:
        Log("There are no seasons to list right now.")
        return ObjectContainer(header="Empty", message="There are no seasons to list right now.")
    else:
        return oc

####################################################################################################
@route(PREFIX + '/video')
def Video(title, json_url):

    oc = ObjectContainer(title2=title)

    for video in JSON.ObjectFromURL(json_url)['result']['data']:

        if not 'status' in video or video['status'].lower() != 'available':
            continue

        title = video['title'].split(' - ', 1)[-1]
        vid_type = video['type']

        thumb = video['thumb']['large']
        if not thumb:
            thumb = video['thumb']['small']

        airdate = Datetime.ParseDate(video['airdate']).date()

        url = video['url']
        if not url.startswith('http'):
            url = 'https://www.cbs.com/{}'.format(url.lstrip('/'))

        if vid_type == 'Clip':

            oc.add(VideoClipObject(
                url = url,
                title = title,
                originally_available_at = airdate,
                thumb = thumb
            ))

        elif vid_type == 'Full Episode':

            show = video['series_title']

            (season, episode, duration) = (video['season_number'], video['episode_number'], video['duration'])
            season = int(season) if season is not None and season != '' else None

            # Found an episode value that had two numbers separated by a comma so use try/except instead
            try:
                index = int(episode)
            except:
                index = None

            duration = Datetime.MillisecondsFromString(duration) if duration is not None else None
            summary = video['description'] if 'description' in video else None

            oc.add(EpisodeObject(
                url = url,
                show = show,
                title = "S{}E{} - {}".format(str(season).zfill(2), str(index).zfill(2), title) if season and index else title,
                summary = summary,
                originally_available_at = airdate,
                season = season,
                index = index,
                duration = duration,
                thumb = thumb
            ))

    oc.objects.sort(key=lambda obj: obj.originally_available_at, reverse=True)

    if len(oc) < 1:
        Log("There are no videos to list right now.")
        return ObjectContainer(header="Empty", message="There are no videos to list right now.")
    else:
        return oc
