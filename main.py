# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
from pytz import timezone, utc
from fake_useragent import UserAgent

import datetime
import os
import requests
import shutil
import telegram
import traceback
import asyncio

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

async def main_update(bot, chat_id, BASE_DIR: str, target: str, database_name: str, push_name: str, user_agent: UserAgent, is_homepage: bool) -> None:
    FILE_NAME = database_name
    MAIN_URL = 'https://maplestory.nexon.com'
    url = concat_all(MAIN_URL, target)
    headers = randomize_header(user_agent)
    
    try:
        req = requests.get(url, headers=headers)
        req.encoding = 'utf-8'
        posts = crawling_main(req) if is_homepage else crawling(req)
        latest = posts[0].text.strip()
        latest_link = posts[0].get('href')

        latest_string: list = None
        first_check: bool = False

        # Read previous notice ( latest )
        too_long: bool = False

        with open(os.path.join(BASE_DIR, FILE_NAME), 'r+', encoding='utf-8') as f_read:
            before: list = f_read.read().splitlines()
            
            if len(before) == 0:
                first_check = True

            if len(before) >= 20:
                too_long = True
                latest_string = before[len(before)-2:]

            '''
            # for Debugging
            # print(concat_all('이전 ', push_name, ' 공지 : ', before, '\n최근 ', push_name, ' 공지 : ', latest))
            '''

            is_new: bool = True
            for string in before:
                if string == latest and before != '':
                    is_new = False
                    break
            
            # Push text to Telegram
            if is_new:
                now = get_time()
                PUSH_TEXT = ' 공지가 올라왔어요!\n'
                message = concat_all(push_name, PUSH_TEXT, now, '\n', '제목 : ', latest,'\n', MAIN_URL, latest_link)
                
                bot.sendMessage(chat_id=chat_id, text=message)

            '''
            # for Debugging
            else:
                bot.sendMessage(chat_id=chat_id, text='Hello, World!')
            '''

        # Modify to latest notice
        if is_new:
            with open(os.path.join(BASE_DIR, FILE_NAME), 'at', encoding='utf-8') as f_write:
                written_string: str = latest if first_check else concat_all('\n', latest)
                f_write.write(written_string)
                if too_long:
                    latest_string.append(latest)
        
        # Modify database
        if too_long:
            with open(os.path.join(BASE_DIR, FILE_NAME), 'wt', encoding='utf-8') as f_write:
                f_write.write('\n'.join(latest_string))
    
    except requests.exceptions.ConnectionError as e:
        print(traceback.format_exc())

def test_client_download(bot, chat_id, BASE_DIR: str, user_agent: UserAgent) -> None:
    # test_client_version.dat must be set to release version code. ex) 01097
    version: str = None
    DB_FILE_NAME: str = 'test_client_version.dat'
    with open(os.path.join(BASE_DIR, DB_FILE_NAME), 'r+') as f_read:
        version = f_read.readline()

    URL: str = 'http://maplestory.dn.nexoncdn.co.kr/PatchT/'
    
    # Release Version
    str_version: str = version
    version: str = concat_all('0', str(int(version) + 1))

    # Test Beta Version
    str_version_2: str = version
    version: str = concat_all('0', str(int(version) - 1))

    final_url: str = concat_all(URL, str_version_2, '/', str_version, 'to', str_version_2, '.patch')
    file_name: str = final_url.split('/')[-1]

    headers = randomize_header(user_agent)

    # File Download
    try:
        with requests.get(final_url, stream=True, headers=headers) as response:
            with open(os.path.join(BASE_DIR, 'patch', file_name), 'wb+') as f :
                shutil.copyfileobj(response.raw, f)
                
            # print(concat_all(final_url, ', ', str(response.status_code)))
            
            # Push Text to Telegram
            if response.status_code == 200:
                now = get_time()
                PUSH_TEXT = '테섭 업데이트가 존재합니다.\n'
                patch_file = os.path.getsize(os.path.join(BASE_DIR, 'patch', file_name))
                message = concat_all(PUSH_TEXT, now, '\n', final_url.split('/')[-1], ', 용량 : ', str(round(patch_file/1024/1024, 2)), 'MB')
                
                bot.sendMessage(chat_id=chat_id, text=message)

                # Modify Version
                with open(os.path.join(BASE_DIR, DB_FILE_NAME), 'w+') as f_write:
                    f_write.write(str_version_2)

    except requests.exceptions.ConnectionError as e:
        print(traceback.format_exc())

async def main():
    BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
    TARGET: list = [['/Home/Main', 'main_homepage_latest.dat', '본 서버 홈페이지'],
                    ['/News/Notice/Inspection', 'main_inspection_latest.dat', '본 서버 점검관련'], 
                    ['/Testworld/Totalnotice', 'test_notice_latest.dat', '테스트서버']]
    ua: UserAgent = UserAgent()

    bot = None
    chat_id = None
    
    with open(os.path.join(BASE_DIR, 'bot_token.dat'), 'r+') as f_read:
        token = f_read.readline()
        bot = telegram.Bot(token=token)

        try:
            chat_id = bot.getUpdates()[-1].message.chat.id
        except IndexError:
            chat_id = 0

    # infinite loop
    while True:
        print(get_time())
        
        # start = time.time()

        '''
        will be deprecated on python 3.11.x

        await asyncio.wait([main_update(bot, chat_id, BASE_DIR, TARGET[0][0], TARGET[0][1], TARGET[0][2], ua, True),
                            main_update(bot, chat_id, BASE_DIR, TARGET[1][0], TARGET[1][1], TARGET[1][2], ua, False),
                            main_update(bot, chat_id, BASE_DIR, TARGET[2][0], TARGET[2][1], TARGET[2][2], ua, False)])
        '''

        main_update1 = asyncio.create_task(main_update(bot, chat_id, BASE_DIR, TARGET[0][0], TARGET[0][1], TARGET[0][2], ua, True))
        main_update2 = asyncio.create_task(main_update(bot, chat_id, BASE_DIR, TARGET[1][0], TARGET[1][1], TARGET[1][2], ua, False))
        main_update3 = asyncio.create_task(main_update(bot, chat_id, BASE_DIR, TARGET[2][0], TARGET[2][1], TARGET[2][2], ua, False))
        await main_update1
        await main_update2
        await main_update3

        # end = time.time()
        # print(f'time taken: {end - start}')
        
        test_client_download(bot, chat_id, BASE_DIR, ua)

        # iterate n seconds
        await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main())