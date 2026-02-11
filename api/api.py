from time import sleep
from urllib import parse
import threading

import requests
import json

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

gacha_page = {}  # 多任务进度存储：{task_id: {"name": "角色", "page": "第1页"}}
gacha_page_lock = threading.Lock()  # 线程锁，保证线程安全

gacha_type_dict = {
    "200": "常驻",
    "301": "角色",
    "302": "武器",
    "500": "混池",
}

def create_task(task_id):
    """创建新任务"""
    with gacha_page_lock:
        gacha_page[task_id] = {
            "name": "",
            "page": "第1页"
        }

def delete_task(task_id):
    """删除任务数据"""
    with gacha_page_lock:
        if task_id in gacha_page:
            del gacha_page[task_id]

def update_task_progress(task_id, name, page):
    """更新任务进度"""
    with gacha_page_lock:
        if task_id in gacha_page:
            gacha_page[task_id]["name"] = name
            gacha_page[task_id]["page"] = page

def get_task_progress(task_id):
    """获取任务进度"""
    with gacha_page_lock:
        return gacha_page.get(task_id, {"name": "", "page": "第1页"})

class http:
    @staticmethod
    def url_query_dict(url):
        parsed = parse.urlparse(url)
        querys = parse.parse_qsl(parsed.query)
        return dict(querys)
    
    @staticmethod
    def get_api(url, gachaType, size, page, end_id=""):
        param_dict = http.url_query_dict(url)
        param_dict["size"] = size
        param_dict["gacha_type"] = gachaType
        param_dict["page"] = page
        param_dict["lang"] = "zh-cn"
        param_dict["end_id"] = end_id
        param = parse.urlencode(param_dict)
        path = str(url).split("?")[0]
        api = path + "?" + param
        return api
    
    @staticmethod
    def get(url, gacha_type_id, task_id=None):
        size = 20
        # api限制一页最大20
        gacha_list = []
        end_id = 0
        for page in range(1, 9999):
            # 更新任务进度
            if task_id:
                update_task_progress(task_id, gacha_type_dict[gacha_type_id], f"第{page}页")
            api = http.get_api(url, gacha_type_id, size, page, end_id)
            session = requests.Session()
            r = session.get(api, headers=headers)
            s = r.content.decode()
            j = json.loads(s)
            
            if j["retcode"] == -101:
                return False
            
            gacha = j["data"]["list"]
            if not len(gacha):
                break
            for i in gacha:
                gacha_list.append(i)
            end_id = j["data"]["list"][-1]["id"]
            sleep(0.5)

        return gacha_list
