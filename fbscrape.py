#!/usr/bin/python2.7 
import json
import urllib2
import pprint
import re
import sys
import os
import time
import pickle
from xml.etree.ElementTree import parse

print "Edit GRAPH_ID and ACCESS_TOKEN first"
sys.exit(1)

#run this script with argument 'refresh' to build the pickle
#otherwise will render html as a cgi

GRAPH_ID = 'FIXME'
ACCESS_TOKEN = 'FIXME'
LINK_REGEX = '(?:mixcloud|soundcloud|youtu.be|youtube)'
MAIN_URL = 'https://graph.facebook.com/%s/feed?limit=100&access_token=%s' % (GRAPH_ID,ACCESS_TOKEN)
YT_IMAGE = 'http://img.youtube.com/vi/%s/2.jpg'
YT_DATA = 'http://gdata.youtube.com/feeds/api/videos/%s?alt=json'
PICKLE_FILE = '%s/fbscrape.pickle' % '/var/tmp'

pp = pprint.PrettyPrinter(indent=4)
re_link = re.compile('(https*://\S+)')
re_embedlink = re.compile('(https*%3A%2F%2F(?:[^\&]|$)+)')
re_ytid = re.compile('(?:youtu\.be/|youtube.com/watch\?v=|youtube.com/embed/)([\w_-]+)')


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

def poll_facebook(url):
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
        #posts may have a link attribute - they're smarter than comments?
        if 'link' in post:
            icon = 'picture' in post and post['picture'] or None
            links.append( {
                'link': post['link'],
                'icon': icon, 
                'time': post['created_time'],
                'title': '', 
            } )
        if 'data' in post['comments']:
            for comment_data in post['comments']['data']:
                m = re_link.match(comment_data['message'])
                if m:
                    icon = 'picture' in comment_data and comment_data['picture'] or None
                    links.append( {
                        'link': m.group(1), 
                        'icon': icon, 
                        'time': comment_data['created_time'],
                        'title': '', 
                    } )
    for link in links:
        #find any embedded links and unquote them
        m = re_embedlink.search(link['link'])
        if m:
            link['link'] = urllib2.unquote(m.group(1))
        #get a fresh icon/title for any youtube links
        m = re_ytid.search(link['link'])
        if m:
            id = m.group(1)
            link['icon'] = YT_IMAGE % id
            link['title'] = yt_title(id)
    return { 'posts': len(posts), 'links': links, 'timestamp': time.time() }


def do_html(data):
    links = data['links']
    posts = data['posts']
    now = time.time()
    timedelta = now - data['timestamp']
    print "Content-type: text/html\n"
    print "<html><body>"
    print "<p>posts evaluated: %d<br />" % posts
    print "last evaluation: %d seconds ago</p>" % timedelta
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
            print '<span style="float: right;">%s</span>' % created_time 
            print '</div>'
        else:
           skipped.append([icon,url])
    
    print "<p>links deemed non-interesting:<br />"
    for skip in skipped:
        print '<a href="%(url)s"><img src="%(icon)s">%(url)s</a><br />' % { 'url': url, 'icon': icon, 'time': created_time }
    print "</p>"
    print "</body></html>"

def yt_title(id):
    try:
        f = urllib2.urlopen(YT_DATA % id)
        d = json.load(f)
        return d['entry']['title']['$t']
    except urllib2.HTTPError:
        return ''

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
    if len(sys.argv) > 1 and sys.argv[1] == 'refresh':
        data = poll_facebook(MAIN_URL)   
        store_pickle(data,PICKLE_FILE)
        sys.exit(0)
    else:
        data = read_pickle(PICKLE_FILE)
        if data is None:
            print "Something went horribly wrong, maybe FB access_token?"
            sys.exit(1)
        do_html(data)

