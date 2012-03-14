#!/usr/bin/python2.7 
import json
import urllib2
import pprint
import re
import sys
import codecs
import os
import time
import pickle
from xml.etree.ElementTree import parse
import gdata.youtube
import gdata.youtube.service
import glob

print "Edit GRAPH_ID, ACCESS_TOKEN, YT_PLAYLISTS and GDATA_USER/PASS first"
sys.exit(1)

#I declare utf-8 in the Content-type, so print what I say, ok?
sys.stdout = codecs.getwriter('utf8')(sys.stdout)

#run this script with argument 'refresh' to build the pickle
#otherwise will render html as a cgi

#get token
#https://www.facebook.com/dialog/oauth?client_id=230867407010370&redirect_uri=https://www.facebook.com/connect/login_success.html&response_type=token&scope=offline_access,read_stream

#DEFINE ME
GRAPH_ID = ''
ACCESS_TOKEN = ''
GDATA_USER = ''
GDATA_PASS = ''
YT_PLAYLISTS = []

LINK_REGEX = '(?:mixcloud|soundcloud|youtu.be|youtube)'
MAIN_URL = 'https://graph.facebook.com/%s/feed?limit=100&access_token=%s' % (GRAPH_ID,ACCESS_TOKEN)
YT_IMAGE = 'http://img.youtube.com/vi/%s/2.jpg'
YT_DATA = 'http://gdata.youtube.com/feeds/api/videos/%s?alt=json'
GDATA_KEY = 'AI39si5-9UlaRwUl3c3kWqebs7_kyR9OKJHOdtYWb9hsPM-HEXo0KoHa7pmPrSJpVriuXsX45vdN0UF4c6lPZLMbgOu94aW0dw'
YT_PLAYLIST_URL = 'http://gdata.youtube.com/feeds/api/playlists/%s'
YT_PLAYLIST_MAIN = 'http://www.youtube.com/playlist?list=PL%s&feature=view_all'
YT_BASE = 'http://www.youtube.com/watch?v=%s'
PICKLE_FILE = '%s/fbscrape.pickle' % '/var/tmp'
RIP_GLOB = '/var/tmp/rip/%s.*'

pp = pprint.PrettyPrinter(indent=4)
re_link = re.compile('(https*://\S+)')
re_embedlink = re.compile('(https*%3A%2F%2F(?:[^\&]|$)+)')
re_ytid = re.compile('(?:youtu\.be/|youtube.com/watch\?v=|youtube.com/embed/|youtube.com/watch?.*?&v=)([\w_-]+)')


def parse_graph(url):
    retries = 5
    f = None
    while retries > 0:
        try:
            f = urllib2.urlopen(url)
            break
        except urllib2.URLError, e:
            retries = retries - 1
            continue
    if f is None:
        return None
    return json.load(f)

def scrape_facebook(url,data=None):
    links = list()
    posts = list()
    g = parse_graph(url)
    if g is None:
        return None
    posts = posts + g['data']
    while 'paging' in g:
        g = parse_graph(g['paging']['next'])
        posts = posts + g['data']

    for post in posts:
        if 'link' in post:
            icon = 'picture' in post and post['picture'] or None
            links.append( {
                'link': post['link'],
                'icon': icon, 
                'time': post['created_time'],
                'title': '', 
            } )
        #maybe fb didn't parse out the link
        elif 'message' in post:
            m = re_link.match(post['message'])
            icon = 'picture' in post and post['picture'] or None
            if m:
                links.append( {
                    'link': m.group(1),
                    'icon': icon, 
                    'time': post['created_time'],
                    'title': '', 
                } )
        #and people tend to add more in comments too
        if 'data' in post['comments']:
            for comment_data in post['comments']['data']:
                m = re_link.search(comment_data['message'])
                if m:
                    icon = 'picture' in comment_data and comment_data['picture'] or None
                    links.append( {
                        'link': m.group(1), 
                        'icon': icon, 
                        'time': comment_data['created_time'],
                        'title': '', 
                    } )
    #a little housecleaning now...
    titles = dict()
    for link in links:
        #find any embedded links and unquote them
        m = re_embedlink.search(link['link'])
        if m:
            link['link'] = urllib2.unquote(m.group(1))
        #get a fresh icon/title for any youtube links
        m = re_ytid.search(link['link'])
        if m:
            ytid = m.group(1)
            title = None
            if data and ytid in data['titles']:
                title = data['titles'][ytid]
            else:
                title = yt_title(ytid)
            link['link'] = YT_BASE % ytid
            link['icon'] = YT_IMAGE % ytid
            link['title'] = title
            files = glob.glob(RIP_GLOB % ytid)
            if files and files[0].split('.')[-1] != 'part':
                link['filename'] = files[0].split('/')[-1]
            titles[ytid] = title
            
    return { 'posts': len(posts), 'links': links, 'timestamp': time.time(), 'titles': titles }


def do_html(data):
    links = data['links']
    posts = data['posts']
    now = time.time()
    timedelta = now - data['timestamp']
    print "Content-type: text/html;charset=utf-8\n"
    print "<html><body>"
    print "<p>posts evaluated: %d<br />" % posts
    print "last evaluation: %d seconds ago</p>" % timedelta
    listidx = 1
    print '<p style="background-color: silver;">'
    for listid in YT_PLAYLISTS:
        print '<a href="%s"><strong>Playlist %d</strong></a><br />' % (YT_PLAYLIST_MAIN % listid, listidx)
        listidx += 1
    print '</p><br /><br /><br />Individual songs:<br />'
    for link in links:
        url = link['link']
        icon = link['icon']
        created_time = link['time']
        title = link['title']
        re_music = re.compile(LINK_REGEX)
        skipped = list()
        if re_music.search(url):
            #found an interesting url
            print '<div width="100%" style="border-top-style: solid; border-top-width: 1px; border-top-color: silver;">'
            print '<span>'
            if icon is not None:
                print '<img src="%s" style="vertical-align: text-top; width: 80px; height: 60px;" />' % icon
            else:
                print '<span style="width: 80px; display: inline-block; height: 60px;">&nbsp;</span>'
            print '<a href="%s">%s</a> - %s</span>' % (url,url,title)
            if 'filename' in link:
                realfile = re.sub('"', '%22', '%s.%s' % ( title,link['filename'].split('.')[-1] ))
                print '<span><a href="/ps20dl/%s?filename=%s">Download</a></span>' % (link['filename'],realfile)
            print '<span style="float: right;">%s</span>' % created_time 
            print '</div>'
        else:
           skipped.append([icon,url])
    
    #print "<p>links deemed non-interesting:<br />"
    #for skip in skipped:
    #    print '<a href="%(url)s"><img src="%(icon)s">%(url)s</a><br />' % { 'url': url, 'icon': icon, 'time': created_time }
    #print "</p>"
    print "</body></html>"

def yt_title(ytid):
    try:
        f = urllib2.urlopen(YT_DATA % ytid)
        d = json.load(f)
        title = d['entry']['title']['$t']
        return title
    except urllib2.HTTPError, e:
        print "Error getting YouTube title: %s" % e
        return None

def get_ytids(data):
    ytids = list()
    for row in data['links']:
        m = re_ytid.search(row['link'])
        if m:
            id = m.group(1)
            ytids.append(id)
    return ytids

def sync_ytlists(ytids):
    yt_service = gdata.youtube.service.YouTubeService()
    yt_service.developer_key = GDATA_KEY
    yt_service.client_id = 'fbscraper-0.2'
    yt_service.source = 'fbscraper'
    yt_service.email = GDATA_USER
    yt_service.password = GDATA_PASS
    yt_service.ProgrammaticLogin()
    yt_lists = dict()
    list_item_ids = dict()
    for listid in YT_PLAYLISTS:
        #make a map of all the IDs that are currently in the playlists
        yt_playlist = YT_PLAYLIST_URL % listid
        print 'Reading playlist: %s' % yt_playlist
        yt_lists[listid] = 0
        playlist_feed = yt_service.GetYouTubePlaylistVideoFeed(uri=yt_playlist)
        safety = 0
        while True:
            for entry in playlist_feed.entry:
                yt_lists[listid] += 1
                url = entry.media.player.url
                m = re_ytid.search(url)
                if m:
                    id = m.group(1)
                    list_item_ids[id] = True
                else:
                    print "WTF yt gave us a player url that isn't in their format?"
                    sys.exit(1)
            next_link = playlist_feed.GetNextLink()
            if next_link:
                playlist_feed = yt_service.GetYouTubePlaylistVideoFeed(uri=next_link.href)
            else:
                break
        
    #now add any video ids which aren't in the map
    for ytid in ytids:
        if ytid not in list_item_ids:
            try:
                yt_video = yt_service.GetYouTubeVideoEntry(video_id=ytid)
            except gdata.service.RequestError, e:
                err = e[0]
                if err['status'] == 403 and err['body'] == 'Private video':
                    print "Video %s is private" % ytid
                    continue
                elif err['status'] == 404:
                    print "Video %s doesn't exist" % ytid
                    continue
                else:
                    raise e
            listid = get_next_listid(yt_lists)
            yt_playlist = YT_PLAYLIST_URL % listid
            try:
                yt_service.AddPlaylistVideoEntryToPlaylist(yt_playlist,ytid)
                yt_lists[listid] += 1
                print "Added %s to playlist (%d)" % (ytid, yt_lists[listid])
            except gdata.service.RequestError, e:
                err = e[0]
                if err['status'] == 403:
                    print 'Gdata API hates us. Try later?'
                    print e
                    sys.exit(1)
                else:
                    print "Skipped %s(%d): %s" % (ytid, err['status'], err['body'])
#        else:
#            print "%s already in playlists" % ytid

def get_next_listid(yt_lists):
    for listid in YT_PLAYLISTS:
        #print "listid %s is %s" % (listid, yt_lists[listid])
        if yt_lists[listid] < 200:
            return listid

def store_pickle(data,filename):
    try:
        f = open(filename,'w')
    except IOError, e:
        print "Error writing %s: %s" % (filename, e)
        return None
    pickle.dump(data,f)
    f.close()

def read_pickle(filename):
    try:
        f = open(filename,'r')
    except IOError, e:
        print "Error reading %s: %s" % (filename, e)
        return None
    try:
        data = pickle.load(f)
    except EOFError, e:
        print "Error reading %s: %s" % (filename, e)
        return None
    finally:
        f.close()
    return data

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'scrape':
        data = read_pickle(PICKLE_FILE) #for the titles
        data = scrape_facebook(MAIN_URL,data)   
        if data:
            store_pickle(data,PICKLE_FILE)
            sys.exit(0)
        else:
            print "Error scraping facebook, access_token perhaps?"
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == 'playlist':
        data = read_pickle(PICKLE_FILE)  
        if data:
            ytids = get_ytids(data) #generally returns newest first
            ytids.reverse() #but we want oldest first
            sync_ytlists(ytids)
            sys.exit(0)
        else:
            print "Something is wrong with the pickle.  Scrape again?"
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == 'dump':
        data = read_pickle(PICKLE_FILE)  
        if data:
            ytids = get_ytids(data) #generally returns newest first
            ytids.reverse() #but we want oldest first
            for ytid in ytids:
                print ytid
            sys.exit(0)
        else:
            print "Something is wrong with the pickle.  Scrape again?"
            sys.exit(1)
    else:
        data = read_pickle(PICKLE_FILE)
        if data is None:
            print "Something is wrong with the pickle.  Scrape again?"
            sys.exit(1)
        do_html(data)

