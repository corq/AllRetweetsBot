# -*- coding: utf-8 -*-

import datetime
import logging
import logging.config
import math
import sqlite3
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET

from config.settings import *


logger = logging.getLogger('logger')


def read_offset():
    """ Read status offset from file if exists
    """

    offset_id = None

    if os.path.isfile(OFFSET_FILE):
        logger.info('Offset file found. Try to read an offset...')
        with open(OFFSET_FILE, 'r') as offset_file:
            st = int(offset_file.readline())
            if st > 0:
                logger.info('Offset from the file seems valid. We will use it')
                offset_id = st
            else:
                logger.warning('Offset from the files doesn\'t seem valid')
    else:
        logger.info('Offset file not found')

    return offset_id


def write_offset(offset):
    """ Write an offset to file
    """

    with open(OFFSET_FILE, 'w') as offset_file:
        offset_file.write(str(offset) + '\n')
        offset_file.flush()
        os.fsync(offset_file.fileno())


def read_and_prepare(filename):
    """ Read data from file and prepare them for work
    """

    result = []

    if os.path.isfile(filename):
        with open(filename, 'r') as f:
            lines = f.readlines()

        for i in range(0, len(lines)):
            lines[i] = lines[i].rstrip('\n')

        result = [x for x in lines if x != '']

    return result


def log_tweet(res, reason):
    """ Log interesting tweets
    """

    if reason == 'already_retweeted':
        logger.info('\t[Skipping retweet by %s (%d)]' % (res.user.screen_name, res.user.id))
        logger.info('\t[Reason: already retweeted]')
        logger.info('\t[Original tweet data:]')
        logger.info('\t[Created: %s UTC]' % str(res.retweeted_status.created_at))
        logger.info('\t[User ID: %d]' % res.retweeted_status.user.id)
        logger.info('\t[User SN: %s]' % res.retweeted_status.user.screen_name)
        logger.info('\t[User Name: %s]' % res.retweeted_status.user.name)
        logger.info('\t[Tweet ID: %d]' % res.retweeted_status.id)
        logger.info('\t[Text: %s]' % res.retweeted_status.text)

        return True
    elif reason == 'blacklisted_user':
        logger.info('\t[Skipping retweet by %s (%d)]' % (res.user.screen_name, res.user.id))
        logger.info('\t[Reason: user is in blacklist]')
        logger.info('\t[Original tweet data:]')
        logger.info('\t[Created: %s UTC]' % str(res.created_at))
        logger.info('\t[User ID: %d]' % res.user.id)
        logger.info('\t[User SN: %s]' % res.user.screen_name)
        logger.info('\t[User Name: %s]' % res.user.name)
        logger.info('\t[Tweet ID: %d]' % res.id)
        logger.info('\t[Text: %s]' % res.text)

        return True
    elif reason == 'blacklisted_word':
        logger.info('\t[Skipping retweet by %s (%d)]' % (res.user.screen_name, res.user.id))
        logger.info('\t[Reason: tweet contains blacklisted phrases]')
        logger.info('\t[Original tweet data:]')
        logger.info('\t[Created: %s UTC]' % str(res.created_at))
        logger.info('\t[User ID: %d]' % res.user.id)
        logger.info('\t[User SN: %s]' % res.user.screen_name)
        logger.info('\t[User Name: %s]' % res.user.name)
        logger.info('\t[Tweet ID: %d]' % res.id)
        logger.info('\t[Text: %s]' % res.text)

        return True
    elif reason == 'arabian_bot':
        logger.info('\t[Skipping retweet by %s (%d)]' % (res.user.screen_name, res.user.id))
        logger.info('\t[Reason: blocked arabian bot]')
        logger.info('\t[Original tweet data:]')
        logger.info('\t[Created: %s UTC]' % str(res.created_at))
        logger.info('\t[User ID: %d]' % res.user.id)
        logger.info('\t[User SN: %s]' % res.user.screen_name)
        logger.info('\t[User Name: %s]' % res.user.name)
        logger.info('\t[Tweet ID: %d]' % res.id)
        logger.info('\t[Text: %s]' % res.text)

        return True
    elif reason == 'valid_tweet':
        logger.info('\tCreated: %s UTC' % str(res.created_at))
        logger.info('\tUser ID: %d' % res.user.id)
        logger.info('\tUser SN: %s' % res.user.screen_name)
        logger.info('\tUser Name: %s' % res.user.name)
        logger.info('\tTweet ID: %d' % res.id)
        logger.info('\tText: %s' % res.text)

        return True
    else:
        return False


class TWatcher(threading.Thread):
    """ This thread searches for tweets containing certain keywords every CHECK_INTERVAL seconds
    """
    
    def __init__(self, name, api):
        super(TWatcher, self).__init__()
        self.name = name
        self.api = api

    def run(self):
        thth = threading.current_thread()

        # Read an offset from file
        offset_id = read_offset()

        # Form a query
        query = ' OR '.join(WORDS)

        # If an offset file doesn't exist or invalid, search for an offset
        if not offset_id:
            logger.info('Trying to get a new offset')
            got_offset = False
            while not got_offset:
                try:
                    offset_id = self.api.GetSearch(term=query, count=10, result_type='recent')[0].id
                except:
                    logger.error('An error occurred. Sleep for %d seconds and try again...' % SLEEP_ERROR_INTERVAL)
                    time.sleep(SLEEP_ERROR_INTERVAL)
                else:
                    got_offset = True
                    logger.info('Done')
            write_offset(offset_id)

        # Initialize database
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS retweets (retweeted TIMESTAMP NOT NULL, created TIMESTAMP NOT NULL,
                    user_id INTEGER NOT NULL, user_sn TEXT NOT NULL, user_n TEXT NOT NULL,
                    tweet_id INTEGER NOT NULL, tweet_text TEXT NOT NULL,
                    PRIMARY KEY (retweeted))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS stats
                    (date TEXT NOT NULL, followers TEXT NOT NULL, PRIMARY KEY (followers))''')
        conn.commit()

        stop_thread = False
        while not stop_thread:
            # Start working
            logger.info('Making a new query...')
            made_search = False
            while not made_search:
                try:
                    results_tmp = self.api.GetSearch(term=query, since_id=offset_id)
                except:
                    logger.error('An error occurred. Sleep for %d seconds and try again...' % SLEEP_ERROR_INTERVAL)
                    time.sleep(SLEEP_ERROR_INTERVAL)
                else:
                    made_search = True
            results = [x for x in results_tmp if x.user.id != MY_ID]
            results_count = len(results)
            if results_count > 0:
                logger.info('Got %d new tweet(s)' % results_count)
                for i in range(results_count - 1, -1, -1):
                    res = results[i]

                    # Load blacklists every time they may be needed to be able to update them online.
                    blacklist_users = read_and_prepare(BLACKLIST_USERS_FILE)
                    blacklist_words = read_and_prepare(BLACKLIST_WORDS_FILE)

                    logger.info('Tweet %d:' % (results_count - i))
                    if res.retweeted_status is not None:
                        log_tweet(res, 'already_retweeted')

                        offset_id = res.id
                        write_offset(offset_id)
                    elif str(res.user.id) in blacklist_users or res.user.screen_name in blacklist_users:
                        log_tweet(res, 'blacklisted_user')

                        offset_id = res.id
                        write_offset(offset_id)
                    elif len([x for x in blacklist_words if x in res.text]) > 0:
                        log_tweet(res, 'blacklisted_word')

                        offset_id = res.id
                        write_offset(offset_id)
                    elif res.lang == 'ar':
                        # Workaround against some arabian bots. No nationalism :)

                        log_tweet(res, 'arabian_bot')

                        offset_id = res.id
                        write_offset(offset_id)
                    else:
                        log_tweet(res, 'valid_tweet')

                        try:
                            self.api.PostRetweet(res.id)
                        except:
                            logger.error('Can\'t retweet. Skipping')
                        else:
                            logger.info('Retweeted!')
                            offset_id = res.id
                            write_offset(offset_id)
                            params = (str(datetime.datetime.now())[0:20], res.created_at, res.user.id,
                                      res.user.screen_name, res.user.name, res.id, res.text)
                            cur.execute('INSERT INTO retweets VALUES (?,?,?,?,?,?,?)', params)
                            conn.commit()
                            logger.info('Saved to database')
            else:
                logger.info('No new tweets found')

            for i in range(0, CHECK_INTERVAL*10):
                if getattr(thth, 'stop_now', False):
                    stop_thread = True
                    break
                time.sleep(0.1)


class TStatsMaker(threading.Thread):
    """ This thread make and tweet statistics every Monday
    """

    def __init__(self, name, api):
        super(TStatsMaker, self).__init__()
        self.name = name
        self.api = api

    def run(self):
        thth = threading.current_thread()

        # Initialize database
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS retweets
                    (retweeted TIMESTAMP NOT NULL, created TIMESTAMP NOT NULL,
                    user_id INTEGER NOT NULL, user_sn TEXT NOT NULL, user_n TEXT NOT NULL,
                    tweet_id INTEGER NOT NULL, tweet_text TEXT NOT NULL,
                    PRIMARY KEY (retweeted))''')
        cur.execute('''CREATE TABLE IF NOT EXISTS stats
                    (date TEXT NOT NULL, followers TEXT NOT NULL, PRIMARY KEY (followers))''')
        conn.commit()

        # Whether the day of the week was checked
        week_day_checked = False

        stop_thread = False
        while not stop_thread:
            if datetime.datetime.isoweekday(datetime.datetime.now()) == 1:
                if not week_day_checked:
                    logger.info('Seems today is Monday. Time to post stats')

                    logger.info('Getting today\'s stats from db...')
                    cur.execute('SELECT * FROM stats WHERE date=\'%s\'' % datetime.date.today())
                    conn.commit()
                    followers_db = cur.fetchone()
                    logger.info('Done')
                    if followers_db is None:
                        logger.info('Stats was not posted today')

                        logger.info('Saving today\'s stats...')
                        logger.info('Getting followers list...')
                        got_followers = False
                        while not got_followers:
                            try:
                                followers = self.api.GetFollowerIDs(user_id=MY_ID, stringify_ids=True)
                            except:
                                logger.error('Can\'t get followers list. Will sleep for %d seconds and try again'
                                             % SLEEP_ERROR_INTERVAL)
                                time.sleep(SLEEP_ERROR_INTERVAL)
                            else:
                                logger.info('Got followers list')
                                got_followers = True
                        cur.execute('INSERT INTO stats VALUES (?,?)', (datetime.date.today(), ','.join(followers)))
                        conn.commit()
                        logger.info('Data saved')

                        logger.info('Getting last Monday\'s stats...')
                        cur.execute('SELECT * FROM stats WHERE date=\'%s\''
                                    % (datetime.date.today() - datetime.timedelta(days=7)))
                        conn.commit()
                        followers_old_s = cur.fetchone()[1]
                        logger.info('Done')
                        if followers_old_s is not None:
                            logger.info('Found some data')
                            followers_old = followers_old_s.split(',')
                            followers_added = [x for x in followers if x not in followers_old]
                            followers_removed = [x for x in followers_old if x not in followers]
                        else:
                            logger.info('There is no last Monday\'s data')
                            followers_added = list()
                            followers_removed = list()

                        logger.info('Getting last week retweets...')
                        cur.execute('SELECT * FROM retweets WHERE retweeted BETWEEN \'%s\' AND \'%s\''
                                    % (str(datetime.date.today() - datetime.timedelta(days=7))[0:10] + ' 00:00:00',
                                       str(datetime.date.today() - datetime.timedelta(days=1))[0:10] + ' 23:59:59'))
                        conn.commit()
                        res = cur.fetchall()
                        logger.info('Done')

                        logger.info('Forming a tweet and sending...')
                        text = 'Статистика прошедшей недели:\n\n'
                        text += 'Всего фолловеров: %d\n' % len(followers)
                        if len(followers_added) > 0:
                            text += 'Новых: %d\n' % len(followers_added)
                        if len(followers_removed) > 0:
                            text += 'Отписавшихся: %d\n' % len(followers_removed)
                        text += '\nВсего ретвитов: %d\n' % len(res)
                        text += '\n#AllMagadanWeekly'

                        stats_sent = False
                        while not stats_sent:
                            try:
                                self.api.PostUpdate(text)
                            except:
                                logger.error(
                                    'Can\'t send stats. Will sleep for %d seconds and try again' % SLEEP_ERROR_INTERVAL)
                                time.sleep(SLEEP_ERROR_INTERVAL)
                            else:
                                stats_sent = True
                        logger.info('Done')
                    else:
                        logger.info('Stats already have been posted today')
                    week_day_checked = True
            else:
                week_day_checked = False

            for i in range(0, CHECK_INTERVAL*10):
                if getattr(thth, 'stop_now', False):
                    stop_thread = True
                    break
                time.sleep(0.1)


class TWeather(threading.Thread):
    """ This thread make and tweet weather information every 3 hour
        and weather forecast once a day
    """

    def __init__(self, name, api):
        super(TStatsMaker, self).__init__()
        self.name = name
        self.api = api

    def run(self):
        thth = threading.current_thread()

        # Whether the weather is checked
        current_weather_checked = False

        stop_thread = False
        while not stop_thread:
            now = datetime.datetime.now()
            if (now.hour % 3 == 0) and (now.minute == 0):
                if not current_weather_checked:
                    logger.info('Current time is %d:%d. Time to post weather' % (now.hour, now.minute))

                    if not os.path.isdir(TEMP_DIR):
                        os.mkdir(TEMP_DIR)

                    logger.info('Loading weather data...')
                    got_weather = False
                    while not got_weather:
                        try:
                            with urllib.request.urlopen(FORECAST_URL_HOUR) as response:
                                yr_xml = response.read()
                        except:
                            logger.error('Error. Will sleep for %d seconds and try again' % SLEEP_ERROR_INTERVAL)
                            time.sleep(SLEEP_ERROR_INTERVAL)
                        else:
                            got_weather = True
                            logger.info('Done')

                    yr_xml_decoded = yr_xml.decode('utf-8')
                    with open(os.path.join(TEMP_DIR, YR_HOUR_FILE), 'w') as f:
                        f.write(yr_xml_decoded)

                    tree = ET.parse(os.path.join(TEMP_DIR, YR_HOUR_FILE))
                    root = tree.getroot()

                    forecast_now = root.find('./forecast/tabular/time')

                    val_temp = forecast_now[4].attrib['value']
                    if not val_temp.startswith('-'):
                        val_temp = '+' + val_temp
                    val_press = math.floor(float(forecast_now[5].attrib['value']) * 0.75006)
                    val_winddir = forecast_now[2].attrib['code']
                    val_windspeed = float(forecast_now[3].attrib['mps'])
                    val_weathercode = forecast_now[0].attrib['number']

                    logger.info('Forming a tweet and sending...')
                    text = 'Погода на данный момент:\n\n'
                    text += WEATHER_CODES[val_weathercode]
                    text += ', %s градусов.' % val_temp
                    text += '. Давление %d мм рт.ст.' % val_press
                    text += '. Ветер %s, %d м/с.' % (WEATHER_CODES[val_winddir], val_windspeed)
                    text += '\n\n#AllMagadanWeather'

                    weather_sent = False
                    while not weather_sent:
                        try:
                            self.api.PostUpdate(text)
                        except:
                            logger.error(
                                'Can\'t send tweet. Will sleep for %d seconds and try again' % SLEEP_ERROR_INTERVAL)
                            time.sleep(SLEEP_ERROR_INTERVAL)
                        else:
                            weather_sent = True
                    logger.info('Done')
                else:
                    logger.info('Weather already have been posted')
            else:
                current_weather_checked = False

            for i in range(0, CHECK_INTERVAL*10):
                if getattr(thth, 'stop_now', False):
                    stop_thread = True
                    break
                time.sleep(0.1)
