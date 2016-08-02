import time
import praw
import re
import urllib2
import signal, sys
import itemparser as ip
import OAuth2Util
import json


# Function that does all the magic
def bot_comments():
    ids = []
    sub_comments = subreddit.get_comments()
    for comment in sub_comments:
        ids.append(comment.id)
        # Checks if the post is not actually the bot itself (since the details say [[NAME]]
        if comment.id not in already_done and not str(comment.author) == username:
            reply = build_reply(comment.body)
            if reply:
                try:
                    comment.reply(reply)
                except Exception, e:
                    print str(e)
            # Add the post to the list of parsed comments
            already_done.append(comment.id)
    # Finally, return the list of parsed comments (seperate from already_done)
    return ids


def bot_submissions():
    sub_ids = []
    sub_subs = subreddit.get_new(limit=5)
    for submission in sub_subs:
        sub_ids.append(submission.id)
        if submission.id not in already_done:
            reply = build_reply(submission.selftext)
            if reply:
                try:
                    submission.add_comment(reply)
                except Exception, e:
                    print str(e)
            already_done.append(submission.id)
    return sub_ids


def bot_messages():
    msg_ids = []
    msg_messages = r.get_messages(limit=20)
    for message in msg_messages:
        msg_ids.append(message.id)
        if message.id not in already_done:
            reply = build_reply(message.body)
            if reply:
                try:
                    message.reply(reply)
                except Exception, e:
                    print str(e)
            already_done.append(message.id)
    return msg_ids


# Regex Magic that finds the text encaptured with [[ ]]
pattern = re.compile("\[\[([^\[\]]*)\]\]")

def build_reply(text):
    reply = ""
    if text is None: return reply 
    links = pattern.findall(text)
    if len(links) == 0: return reply
    # Remove duplicates
    unique_links = []
    for i in links:
        if i not in unique_links:
            unique_links.append(i)
    # Because a comment can only have a max length, limit to only the first 30 requests
    if len(unique_links) > 30: unique_links = unique_links[0:30]
    for i in unique_links:
        print i
        i = i.split('/')[0]
        name, link = lookup_name(i)
        if link is None: continue
        page = get_page(link)
        if page is None: continue
        reply += "[%s](%s)\n\n" % (name, link)
        reply += ip.parse_item(page)
    if reply is "": 
        return None        
    return reply + "^\(Questions? ^Message ^/u/ha107642 ^- ^Call ^wiki ^pages ^((e.g. items or gems)^) ^with ^[[NAME]])"


# Fetches a page and returns the response.
def get_page(link):
    try:
        request = urllib2.Request(link, headers={"User-Agent": "PoEWiki"})
        response = urllib2.urlopen(request)
        return response.read()
    except urllib2.HTTPError, e:
        return None
    except AttributeError, e:
        print "ERROR: %s" % str(e)
        return None


def lookup_name(name):
    name = urllib2.quote(name)
    search_url = "http://pathofexile.gamepedia.com/api.php?action=opensearch&search=%s" % name
    response = get_page(search_url)
    hits = json.loads(response)
    # opensearch returns a json array in a SoA fashion, 
    # where arr[0] is the search text, arr[1] matching pages,
    # arr[2] ??, arr[3] links to the matching pages.
    # e.g. ["facebreaker",["Facebreaker","FacebreakerUnarmedMoreDamage"],["",""],["http://pathofexile.gamepedia.com/Facebreaker","http://pathofexile.gamepedia.com/FacebreakerUnarmedMoreDamage"]]
    if len(hits[1]) == 0:
        return (None, None) # If we did not find anything, return None. 
    return (hits[1][0], hits[3][0]) # Otherwise, return the first match in a tuple with (name, url).


# Function that backs up current parsed comments
def write_done():
    with open(parsed_filename, "w") as f:
        for i in already_done:
            f.write(str(i) + '\n')


# Function that is called when ctrl-c is pressed. It backups the current parsed comments into a backup file and then quits.
def signal_handler(signal, frame):
    write_done()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def read_login_info(filename):
    with open(filename, 'r') as f:
        content = f.readlines()
        return (content[0], content[1])


# This string is sent by praw to reddit in accordance to the API rules
user_agent = ("REDDIT Bot v1.4 by /u/ha107642")
r = praw.Reddit(user_agent=user_agent)

# username, password = read_login_info('login.txt')
# username = username.strip()
# password = password.strip()
# r.login(username, password)
oauth = OAuth2Util.OAuth2Util(r)
username = r.get_me().name

# Fill in the subreddit(s) here. Multisubs are done with + (e.g. MagicTCG+EDH)
subreddit = r.get_subreddit('pathofexile')

# This loads the already parsed comments from a backup text file
already_done = []
parsed_filename = "parsed_comments.txt"
try:
    with open(parsed_filename, 'r+') as f:
        for i in f:
            already_done.append(i.replace("\n", ""))
except IOError:
    open(parsed_filename, 'a').close()

# Infinite loop that calls the function. The function outputs the post-ID's of all parsed comments.
# The ID's of parsed comments is compared with the already parsed comments so the list stays clean
# and memory is not increased. It sleeps for 15 seconds to wait for new posts.
while True:
    ids = bot_comments()
    time.sleep(5)
    sub_ids = bot_submissions()
    time.sleep(5)
    msg_ids = bot_messages()
    new_done = []
    # Checks for both comments and submissions
    for i in already_done:
        if i in ids:
            new_done.append(i)
        if i in sub_ids:
            new_done.append(i)
        if i in msg_ids:
            new_done.append(i)
    already_done = new_done[:]
    # Back up the parsed comments to a file
    write_done()
    oauth.refresh()
    time.sleep(10)
