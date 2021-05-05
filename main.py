from bs4 import BeautifulSoup
from urllib import parse
import requests
import lxml
import json
import re
import os
import time
import aria2p
from datetime import datetime

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36'
}
url = 'https://www.comicat.org/'
search = 'search.php?keyword='
path = ''
tracker = 'http://open.acgtracker.com:1096/announce'
rpc_secret=''
rpc_port=6800
rpc_host='http://localhost'


# 获取正在追的番剧信息
def get_unfinished_list():
    f = open(path + '追番信息.json')
    return json.load(f)['unfinished']


# 将网页上的表单统一转化成自己程序处理的格式
def data_transform(res):
    soup = BeautifulSoup(res.text, 'lxml')
    result_form = soup.find_all(id='data_list')[0].find_all('tr')
    data_list = []
    for tr in result_form:
        td = tr.find_all('td')
        href = td[2].find('a')['href']
        upload_time = td[0].text
        title = td[2].text
        file_size = td[3].text
        uploader = td[7].text
        data_list.append(
            {'href': href, 'upload_time': upload_time, 'title': title, 'file_size': file_size, 'uploader': uploader}
        )
    return data_list


def get_magnet_link(page_url):
    response = requests.get(page_url, headers=headers)
    time.sleep(1)

    # bs寻找法
    soup = BeautifulSoup(response.text, 'lxml')
    str_tmp = soup.find_all(id='text_hash_id')[0].text.split('：', 1)
    hash_code = str_tmp[1]

    # 正则表达式直接匹配法（没写好，懒得写了
    # pattern = re.compile(re.escape("\"magnet:?xt=urn:btih:") + ".*?" + re.escape("\""))

    return 'magnet:?xt=urn:btih:' + hash_code + '&tr=' + tracker


# 获取单个番剧当次所有要下载的链接 mode 0 追更模式 mode 1 全下模式
def get_download_links(ani, mode):
    # ani_downloaded = os.listdir(path + ani['name'])
    # os.path.splitext(ani_downloaded[0])[0] # 这样获取没有后缀的文件名
    """
    response = requests.get(url + search + ani['keywords'][0] + ani['keywords'][1], headers=headers)
    soup = BeautifulSoup(response.text, 'lxml')
    result_list = soup.find_all('tbody')[1].find_all('a')
    for i in range(int(len(result_list) / 3)):
        escape = [re.escape(ani['keywords'][0]), re.escape(ani['keywords'][1])]
        if (re.search(escape[0], result_list[i * 3 + 1].text) is not None) and \
                (re.search(escape[1], result_list[i * 3 + 1].text) is not None):
            full_pattern = escape[0] + '(.+?)' + escape[1]
            ani_num = re.findall(r'%s' % full_pattern, result_list[i * 3 + 1].text)
            input()
    """
    response = requests.get(url + search + parse.quote(ani['search_keywords']), headers=headers)
    time.sleep(1)
    data_list = data_transform(response)
    true_data_list = []
    for data in data_list:
        i = 0
        for match_keyword in ani['match_keywords']:
            if re.search(re.escape(match_keyword), data['title'], flags=re.I) is None:
                i += 1
        if i == 0:
            true_data_list.append(data)
    for true_data in true_data_list:
        if mode == 0:
            if re.search('昨天', true_data['upload_time'], flags=re.I):
                link = get_magnet_link(url + true_data['href'])
            else:
                link = '0'
        elif mode == 1:
            link = get_magnet_link(url + true_data['href'])
        true_data['full_magnet'] = link
    return true_data_list


if __name__ == '__main__':
    ufd_list = get_unfinished_list()
    # [调用rpc]模块初始化
    aria2 = aria2p.API(
        aria2p.Client(
            host=rpc_host,
            port=rpc_port,
            secret=rpc_secret
        )
    )
    for ufd_ani in ufd_list:
        # 如果路径已经存在，则使用继续追番模式，只下载昨天新上传的内容。如果路径不存在的话则开启全下模式。
        if os.path.exists(path + ufd_ani['name']):
            dl_links = get_download_links(ufd_ani, 0)
        else:
            os.mkdir(path + ufd_ani['name'])
            dl_links = get_download_links(ufd_ani, 1)
        for dl_link in dl_links:
            # 追番模式下，不是昨天刚发布的不下载。当该资源不是昨天发布的时候，磁力链接会显示为0。
            if dl_link['full_magnet'] != '0':
                # # 直接新开一个aria2进程进行下载，而不是调用rpc
                # command = 'aria2c -D ' +\
                #           '-d ' + path + ufd_ani['name'] + '/ ' +\
                #           dl_link['full_magnet']
                # os.system(command)

                # 调用rpc下载
                download = aria2.add_magnet(dl_link['full_magnet'], {'dir': path + ufd_ani['name'] + '/'})
                print(str(datetime.now()) + '创建下载任务：' + dl_link['title'])
