#!/usr/bin/python3

# -*- coding: utf-8 -*-

import argparse
import datetime
import logging
import logging.config
import shutil
import sqlite3
import sys
import time

import twitter

from libbot import *
from config.settings import *


def start_bot():
    """ Bot launcher
    """

    # Authenticate and get API
    logger.info('Start authenticating...')
    authed = False
    while not authed:
        try:
            api = twitter.Api(consumer_key=API_KEY, consumer_secret=API_SECRET,
                              access_token_key=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET)
        except:
            logger.error('An error occurred. Sleep for %d seconds and try again...' % SLEEP_ERROR_INTERVAL)
            time.sleep(SLEEP_ERROR_INTERVAL)
        else:
            authed = True
            logger.info('Done')

    # Start threads
    t_watcher = TWatcher('t_watcher', api)
    t_watcher.start()
    t_statsmaker = TStatsMaker('t_statsmaker', api)
    t_statsmaker.start()

    try:
        t_watcher.join()
        t_statsmaker.join()
    except KeyboardInterrupt:
        logger.info('KeyboardInterrupt exception caught')

        logger.info('Stopping TWatcher thread...')
        setattr(t_watcher, 'stop_now', True)
        while t_watcher.is_alive():
            time.sleep(1)
        logger.info('Done')

        logger.info('Stopping TStatsMaker thread...')
        setattr(t_statsmaker, 'stop_now', True)
        while t_statsmaker.is_alive():
            time.sleep(1)
        logger.info('Done')


def rebuild_retweets():
    """ This procedure rebuilds table 'retweets'.
        It needs, for example, when the bot's admin un-retweets some statuses.
    """

    proceed = False
    while not proceed:
        c = input('Are you sure you want to rebuild retweets table? (Y/N) ')
        if c.lower() in ('n', 'no'):
            logger.info('Abort execution. Exit')
            sys.exit()
        elif c.lower() in ('y', 'yes'):
            proceed = True
        else:
            print('Choose an answer')

    renew_offset = False
    proceed = False
    while not proceed:
        c = input('Do you want to renew offset? (y/N) ')
        if c.lower() in ('n', 'no') or c == '':
            logger.info('Offset will not be renewed')
            renew_offset = False
            proceed = True
        elif c.lower() in ('y', 'yes'):
            logger.info('Offset will be renewed')
            renew_offset = True
            proceed = True
        else:
            print('Choose an answer')

    logger.info('Connecting to Twitter API...')
    try:
        api = twitter.Api(consumer_key=API_KEY, consumer_secret=API_SECRET,
                          access_token_key=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET)
    except:
        logger.info('Can\'t connect to Twitter API. Exit')
        sys.exit()
    else:
        logger.info('Done')

    if not os.path.isfile(DB_FILE):
        logger.error('Database file doesn\'t exists. Exit')
        sys.exit()

    logger.info('Creating backup...')
    file_postfix = str(datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d_%H-%M-%S'))
    if not os.path.isdir(BACKUP_DIR):
        os.mkdir(BACKUP_DIR)
    shutil.copy2(DB_FILE, os.path.join(BACKUP_DIR, '-'.join([file_postfix, DB_FILE])))
    if os.path.isfile(OFFSET_FILE):
        shutil.copy2(OFFSET_FILE, os.path.join(BACKUP_DIR, '-'.join([file_postfix, OFFSET_FILE])))
    logger.info('Done')

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute('''DROP TABLE IF EXISTS retweets''')
    conn.commit()
    logger.info('Dropped table \'retweets\'')
    cur.execute('''CREATE TABLE IF NOT EXISTS retweets
                                (retweeted TIMESTAMP NOT NULL, created TIMESTAMP NOT NULL,
                                user_id INTEGER NOT NULL, user_sn TEXT NOT NULL, user_n TEXT NOT NULL,
                                tweet_id INTEGER NOT NULL, tweet_text TEXT NOT NULL,
                                PRIMARY KEY (retweeted))''')
    conn.commit()
    logger.info('Created new table')

    count_all = 0
    buffer = 100
    flag = True
    max_id = None

    msgs = []

    logger.info('Begin loading statuses')
    t_start = datetime.datetime.now()
    while flag:
        msgs_all = api.GetUserTimeline(user_id=MY_ID, max_id=max_id, count=buffer)

        if len(msgs_all) < buffer:
            flag = False
        else:
            max_id = msgs_all[len(msgs_all) - 1].id - 1

        msgs.extend([x for x in msgs_all if x.retweeted_status is not None])

        count_all += len(msgs_all)
        logger.info('%d statuses loaded...' % count_all)
    logger.info('Elapsed time: %s' % (datetime.datetime.now() - t_start))

    count = len(msgs)
    logger.info('There are %d tweets loaded' % count_all)
    logger.info('%d of them are retweets' % count)

    logger.info('Writing statuses to DB...')
    offset = 0
    t_start = datetime.datetime.now()
    for i in range(count - 1, -1, -1):
        m = msgs[i]

        if m.id > offset:
            offset = m.id

        params = (time.strftime('%Y-%m-%d %H:%M:%S', datetime.datetime.timetuple(
            datetime.datetime.strptime(m.created_at, '%a %b %d %H:%M:%S %z %Y') + datetime.timedelta(hours=UTC_OFFSET))),
                  str(m.retweeted_status.created_at),
                  m.retweeted_status.user.id, m.retweeted_status.user.screen_name, m.retweeted_status.user.name,
                  m.retweeted_status.id, m.retweeted_status.text)
        cur.execute('INSERT INTO retweets VALUES (?,?,?,?,?,?,?)', params)
        conn.commit()
    logger.info('Elapsed time: %s' % (datetime.datetime.now() - t_start))

    conn.close()
    logger.info('Done!')

    if renew_offset:
        with open(OFFSET_FILE, 'w') as f:
            f.write(str(offset))
        logger.info('New offset is written')


def main():
    logger.info('Bot started')

    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-s', '--start-bot', action='store_true')
    group.add_argument('-r', '--rebuild-retweets', action='store_true')
    args = parser.parse_args()

    if args.start_bot:
        logger.info('Preparing bot to start')
        start_bot()
    elif args.rebuild_retweets:
        rebuild_retweets()
    else:
        logger.error('You must specify a parameter. See [./bot.py --help]')
        sys.exit()


if __name__ == '__main__':
    # Initialize logging

    if not os.path.isdir('logs'):
        os.mkdir('logs')

    logging.config.dictConfig(LOG_OPTIONS)
    logger = logging.getLogger('logger')
    logger.info('Logging initialized')

    try:
        main()
    except Exception as e:
        logger.error('Unknown exception.')
        logger.error('Exception details: {}'.format(e))
    else:
        logger.info('Thank you!')
