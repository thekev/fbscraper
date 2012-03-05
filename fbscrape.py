#!/usr/bin/python2.7 
import json
import urllib2
import pprint
import re
import sys
import os
import time
import pickle

print "Edit GRAPH_ID and ACCESS_TOKEN first"
sys.exit(1)

#run this script with argument 'refresh' to build the pickle
#otherwise will render html as a cgi

GRAPH_ID = 'FIXME'
ACCESS_TOKEN = 'FIXME'
LINK_REGEX = '(?:mixcloud|soundcloud|youtu.be|youtube)'
MAIN_URL = 'https://graph.facebook.com/%s/feed?limit=100&access_token=%s' % (GRAPH_ID,ACCESS_TOKEN)
PICKLE_FILE = '%s/fbscrape.pickle' % '/var/tmp'

pp = pprint.PrettyPrinter(indent=4)

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

    re_link = re.compile('(https*://\S+)')
    for post in posts:
        #TODO show created_time in posts and comments
        #posts may have a link attribute - they're smarter than comments?
        if 'link' in post:
            icon = 'picture' in post and post['picture'] or None
            links.append( [icon, post['link']] )
        #apparently, sometimes the count key lies, so check for data key's existance instead
        if 'data' in post['comments']:
            for comment_data in post['comments']['data']:
                #comments appear to only have a message key, even if message contains a link
                m = re_link.search(comment_data['message'])
                if m:
                    icon = 'picture' in comment_data and comment_data['picture'] or None
                    links.append( [icon, m.group(1)] )
    return { 'links': links, 'posts': posts, 'timestamp': time.time() }

def do_html(data):
    links = data['links']
    posts = data['posts']
    timedelta = time.time() - data['timestamp']
    print "Content-type: text/html\n"
    print "<html><body>"
    print "<p>posts evaluated: %d<br />" % len(posts)
    print "last evaluation: %d seconds ago</p>" % timedelta
    for link in links:
        icon = link[0]
        url = link[1]
        re_music = re.compile(LINK_REGEX)
        skipped = list()
        if re_music.search(url):
            #found an interesting url
            if icon is not None:
                print '<a href="%(url)s"><img src="%(icon)s" />%(url)s</a><hr />' % { 'url': url, 'icon': icon }
            else:
                print '<a href="%(url)s">%(url)s</a><hr />' % { 'url': url }
        else:
           skipped.append([icon,url])
    
    print "<p>links deemed non-interesting:<br />"
    for skip in skipped:
        print '<a href="%(url)s"><img src="%(icon)s">%(url)s</a><br />' % { 'url': url, 'icon': icon }
    print "</p>"
    print "</body></html>"


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

