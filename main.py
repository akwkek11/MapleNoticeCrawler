# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from time import sleep
from pytz import timezone, utc
from fake_useragent import UserAgent

import datetime
import os
import requests
import shutil
import telegram

# String concatenation without '+' for the performance issue
def concat_all(*strings: list) -> str:
    str_list = []
    for st in strings:
        str_list.append(st)

    return ''.join(str_list)

# Web crawling with bs4
def crawling(req: requests) -> str:
    html = req.text
    soup = BeautifulSoup(html, 'html.parser')
    return soup.select('html > body > div#wrap > div#container > div.div_inner > div.contents_wrap > div.news_board > ul > li > p > a')

def crawling_main(req: requests) -> str:
    html = req.text
    soup = BeautifulSoup(html, 'html.parser')
    return soup.select('html > body > div#wrap > div#section03 > div.div_inner > div.client_update_wrap > div.client_update > ul > li > dl > dd.announcement_title > a')

# Get Time - KST(GMT+9)
def get_time() -> str:
    now = datetime.datetime.utcnow()
    kst = timezone('Asia/Seoul')
    return utc.localize(now).astimezone(kst).strftime('%Y-%m-%d %H:%M:%S')

# Create Random UA to prevent code from exception (requests.exceptions.ConnectionError)
def randomize_header(ua: UserAgent) -> UserAgent:
    return {'User-Agent' : ua.random}

def main_update(bot, chat_id, BASE_DIR: str, target: str, database_name: str, push_name: str, user_agent: UserAgent, is_homepage: bool) -> None:
    FILE_NAME = database_name
    MAIN_URL = 'https://maplestory.nexon.com'

    url = concat_all(MAIN_URL, target)

    headers = randomize_header(user_agent)

    req = requests.get(url, headers=headers)
    req.encoding = 'utf-8'

    posts = crawling_main(req) if is_homepage else crawling(req)
    latest = posts[0].text.strip()
    latest_link = posts[0].get('href')

    # Read previous notice ( latest )
    with open(os.path.join(BASE_DIR, FILE_NAME), 'r+') as f_read:
        before = f_read.readline()
        
        print(concat_all('이전 ', push_name, ' 공지 : ', before, '\n최근 ', push_name, ' 공지 : ', latest))
        # Push text to Telegram
        if before != latest and before != '':
            now = get_time()
            PUSH_TEXT = ' 공지가 올라왔어요!\n'
            message = concat_all(push_name, PUSH_TEXT, now, '\n', '제목 : ', latest,'\n', MAIN_URL, latest_link)
            
            bot.sendMessage(chat_id=chat_id, text=message)

        '''
        # for Debugging
        else:
            bot.sendMessage(chat_id=chat_id, text='Hello, World!')
        '''

        f_read.close()

    # Modify to latest notice
    with open(os.path.join(BASE_DIR, FILE_NAME), 'w+') as f_write:
        f_write.write(latest)
        f_write.close()

def test_client_download(bot, chat_id, BASE_DIR: str, user_agent: UserAgent) -> None:
    # test_client_version.dat must be set to release version code. ex) 01097
    version = 0
    DB_FILE_NAME = 'test_client_version.dat'
    with open(os.path.join(BASE_DIR, DB_FILE_NAME), 'r+') as f_read:
        version = f_read.readline()
        f_read.close()

    URL = 'http://maplestory.dn.nexoncdn.co.kr/PatchT/'
    
    # Release Version
    str_version = version
    version = concat_all('0', str(int(version) + 1))

    # Test Beta Version
    str_version_2 = version
    version = concat_all('0', str(int(version) - 1))

    final_url = concat_all(URL, str_version_2, '/', str_version, 'to', str_version_2, '.patch')
    file_path = concat_all('./patch/', final_url.split('/')[-1])

    headers = randomize_header(user_agent)

    # File Download
    try:
        with requests.get(final_url, stream=True, headers=headers) as response:
            with open(file_path, 'wb') as f :
                shutil.copyfileobj(response.raw, f)
                
            # print(concat_all(final_url, ', ', str(response.status_code)))
            
            # Push Text to Telegram
            if response.status_code == 200:
                now = get_time()
                PUSH_TEXT = '테섭 업데이트가 존재합니다.\n'
                patch_file = os.path.getsize(file_path)
                message = concat_all(PUSH_TEXT, now, '\n', file_path.split('/')[-1], ', 용량 : ', str(round(patch_file/1024/1024, 2)), 'MB')
                
                bot.sendMessage(chat_id=chat_id, text=message)

                # Modify Version
                with open(os.path.join(BASE_DIR, DB_FILE_NAME), 'w+') as f_write:
                    f_write.write(str_version_2)
                    f_write.close()

    except requests.exceptions.ConnectionError as e:
        print("test_client_download error : Connection refused.")

def main():
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    TARGET: list = [['/Home/Main', 'main_homepage_latest.dat', '본 서버 홈페이지'],
                    ['/News/Notice/Inspection', 'main_inspection_latest.dat', '본 서버 점검관련'], 
                    ['/Testworld/Totalnotice', 'test_notice_latest.dat', '테스트서버']]
    ua: UserAgent = UserAgent()
    is_homepage: bool = False

    with open(os.path.join(BASE_DIR, 'bot_token.dat'), 'r+') as f_read:
        token = f_read.readline()
        bot = telegram.Bot(token=token)
        chat_id = bot.getUpdates()[-1].message.chat.id
    # infinite loop
    while True:
        print(get_time())
        for i in range(len(TARGET)):
            is_homepage = True if i == 0 else False
            main_update(bot, chat_id, BASE_DIR, TARGET[i][0], TARGET[i][1], TARGET[i][2], ua, is_homepage)
        test_client_download(bot, chat_id, BASE_DIR, ua)

        # iterate n seconds
        sleep(5)

if __name__ == '__main__':
    main()