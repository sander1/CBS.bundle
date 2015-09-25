SHOWS_URL = 'http://www.cbs.com/shows/%s/'
SECTION_CAROUSEL = 'http://www.cbs.com/carousels/videosBySection/%s/offset/0/limit/15/xs/0'
CATEGORIES = [
	{'category_id': 'primetime', 'title': 'Primetime'},
	{'category_id': 'daytime', 'title': 'Daytime'},
	{'category_id': 'late-night', 'title': 'Late Night'}
]

RE_S_EP_DURATION = Regex('(S(\d+) Ep(\d+) )?\((\d+:\d+)\)')
RE_SAFE_TITLE = Regex('/shows/([^/]+)')
RE_SEASON = Regex('Season ([0-9]+),')

EXCLUDE_SHOWS = [
]

####################################################################################################
def Start():

	ObjectContainer.title1 = 'CBS'
	HTTP.CacheTime = CACHE_1HOUR
	HTTP.Headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36'

####################################################################################################
@handler('/video/cbs', 'CBS')
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
		if not url.startswith('http://'):
			url = 'http://www.cbs.com/%s' % url.lstrip('/')
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

	oc = ObjectContainer(title2=title)

	try:
		html = HTML.ElementFromURL(url)
	except:
		return ObjectContainer(header="Empty", message="Can't find video's for this show.")

	for carousel in html.xpath('//div[starts-with(@id, "id-carousel")]/@id'):
		json_url = SECTION_CAROUSEL % carousel.split('-')[-1]
		json_obj = JSON.ObjectFromURL(json_url)

		if json_obj['success']:
			title = json_obj['result']['title']

			oc.add(DirectoryObject(
				key = Callback(Video, title=title, json_url=json_url),
				title = title,
				thumb = Resource.ContentsOfURLWithFallback(thumb)
			))

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
		if not url.startswith('http://'):
			url = 'http://www.cbs.com/%s' % url.lstrip('/')

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
			index = int(episode) if episode is not None and episode != '' else None
			duration = Datetime.MillisecondsFromString(duration) if duration is not None else None
			summary = video['description']
            
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
	return oc
