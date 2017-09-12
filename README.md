# AllRetweetsBot
A simple Python bot for Twitter that retweets specified words and/or hashtags, saves the tweets into the database and tweet weekly stastistics. As secondary function, it tweets the local weather report every several hours and weather forecast once a day.

## Installation
### Requirements
This bot doesn't support Python2 and will not in future. Python 3.5 or 3.6 fits the best.

All 3rd party modules are listed in requirements.txt. You can install them all by running:
```
pip3 install -r requirements.txt
```
`requirements.txt` contains only one item so far - the nice [python-twitter](https://github.com/bear/python-twitter) module that simplifies interaction with Twitter API.

### Configuration
After installing Python and required modules you should rename configuration file `config/settings.py-dist` to `config/settings.py` and make following changes:
1. Specify your Twitter API keys and tokens:
   ```
   # Auth parameters
   API_KEY = ''
   API_SECRET = ''
   ACCESS_TOKEN = ''
   ACCESS_TOKEN_SECRET = ''
   ```
   To get your keys you need to log in in Twitter and go to https://apps.twitter.com/
2. Specify your bot's user_id:
   ```
   # Bot user_id
   MY_ID = 0
   ```
   *For now I don't know how to get this ID automatically using python-twitter module. If I learn how to do it, I'll fix it and    remove this setting. Or, if you know how, you can make PR.*
3. Specify the words or the hashtags the bot will search for:
   ```
   # Words list to search for
   WORDS = ['#Twitter']
   ```
   It is just a list.
4. Set right yr.no URLs accodring to your geographic place. Example:
   ```
   FORECAST_URL_HOUR = 'http://www.yr.no/place/Russia/Magadan/Magadan/forecast_hour_by_hour.xml'
   FORECAST_URL = 'http://www.yr.no/place/Russia/Magadan/Magadan/forecast.xml'
   ```
   See http://om.yr.no/verdata/xml/.
   
All other options you may leave as written in default configuration - the bot is going to work well.

## Running the bot
### Searching for words
To start the bot searching for specified words just run:
```
./bot.py --start-bot
```
or
```
python3 bot.py --start-bot
```
By running this command the bot starts searching for the words specified in configuration file and retweeting them when find. You can close it by pressing `Ctrl-C`. The bot doesn't close immediately - it tries to stop its threads first and then closes itself.

### Repairing the database
If you think the database contains wrong information about retweets (if you un-retweet some statuses manually, for example), you can rebuild appropriate table by running:
```
./bot.py --rebuild-retweets
```
After that the bot will backup database, offset file (if you want), drop table `retweets`, load every retweet it made and re-create this table. If you think that the offset file needn't to be repaired, you can leave it. Otherwise it will be also rewritten (but it may change - don't worry about that).

## Coda
Feel free to fork this projects and make push requests - I'd be open to your help and new ideas.

My contacts:

   Email: [sgtstrom@gmail.com](mailto:sgtstrom@gmail.com)
   
   Twitter: https://twitter.com/sgtStrom
   
