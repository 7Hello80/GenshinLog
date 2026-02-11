from flask import Flask, render_template, request, jsonify
import json
import requests
from api.api import http, gacha_page, create_task, delete_task, get_task_progress
from config import gacha_query_type_dict, gacha_type_dict
from time import sleep
from ServerConfig import ServerPort, DebugMode

app = Flask(__name__)

# 歪掉的角色和武器名单
WAI_CHARACTERS = {
    '七七', '迪卢克', '琴', '梦见月瑞希', '莫娜', '提纳里', '迪希雅', '刻晴'
}

WAI_WEAPONS = {
    '天空之卷', '天空之翼', '天空之刃', '天空之脊', '天空之傲',
    '狼的末路', '和璞鸢', '四风原典', '阿莫斯之弓', '风鹰剑'
}

def is_wai_item(name, item_type, gacha_type):
    """判断是否是歪掉的角色或武器（常驻池不显示歪）"""
    if gacha_type == '200':  # 常驻池不显示歪
        return False
    if item_type == '角色':
        return name in WAI_CHARACTERS
    elif item_type == '武器':
        return name in WAI_WEAPONS
    return False

# 配置 Jinja2 使用不同的分隔符，避免与 Vue 的 {{ }} 冲突
app.jinja_env.variable_start_string = '[['
app.jinja_env.variable_end_string = ']]'

# 头像缓存
avatar_cache = {
    "characters": {},
    "weapons": {}
}

# 头像映射字典
avatar_map = {
    "characters": {},
    "weapons": {}
}

def load_avatars():
    """加载角色和武器头像数据"""
    global avatar_map
    
    try:
        # 获取角色头像数据
        character_resp = requests.get(
            "https://act-api-takumi-static.mihoyo.com/common/blackboard/ys_obc/v1/home/content/list?app_sn=ys_obc&channel_id=25",
            timeout=30
        )
        
        # 获取武器头像数据
        weapon_resp = requests.get(
            "https://act-api-takumi-static.mihoyo.com/common/blackboard/ys_obc/v1/home/content/list?app_sn=ys_obc&channel_id=5",
            timeout=30
        )
        
        if character_resp.status_code == 200:
            char_data = character_resp.json()
            if char_data.get('retcode') == 0 and 'data' in char_data:
                # 解析角色头像数据
                char_list = char_data['data']['list'][0].get('list', [])
                for char in char_list:
                    name = char.get('title', '')
                    icon_url = char.get('icon', '')
                    if name and icon_url:
                        avatar_map['characters'][name] = icon_url
                        # 同时缓存
                        avatar_cache['characters'][f"角色_{name}"] = icon_url
                
        if weapon_resp.status_code == 200:
            weapon_data = weapon_resp.json()
            if weapon_data.get('retcode') == 0 and 'data' in weapon_data:
                # 解析武器头像数据
                weapon_list = weapon_data['data']['list'][0].get('list', [])
                for weapon in weapon_list:
                    name = weapon.get('title', '')
                    icon_url = weapon.get('icon', '')
                    if name and icon_url:
                        avatar_map['weapons'][name] = icon_url
                        # 同时缓存
                        avatar_cache['weapons'][f"武器_{name}"] = icon_url
                
    except Exception as e:
        print(f"加载头像数据失败: {e}")

def get_avatar_url(name, item_type):
    """获取角色或武器的头像URL"""
    cache_key = f"{item_type}_{name}"
    
    # 先从缓存中查找
    if cache_key in avatar_cache["characters"]:
        return avatar_cache["characters"][cache_key]
    elif cache_key in avatar_cache["weapons"]:
        return avatar_cache["weapons"][cache_key]
    
    # 从映射字典中查找
    if item_type == "角色" and name in avatar_map["characters"]:
        avatar_url = avatar_map["characters"][name]
        avatar_cache["characters"][cache_key] = avatar_url
        return avatar_url
    elif item_type == "武器" and name in avatar_map["weapons"]:
        avatar_url = avatar_map["weapons"][name]
        avatar_cache["weapons"][cache_key] = avatar_url
        return avatar_url
    
    # 如果都没有找到，返回默认占位图
    avatar_url = f"https://ui-avatars.com/api/?name={name}&background=random&size=128"
    
    # 存入缓存
    if item_type == "角色":
        avatar_cache["characters"][cache_key] = avatar_url
    else:
        avatar_cache["weapons"][cache_key] = avatar_url
    
    return avatar_url

def calculate_pulls(gacha_list):
    """计算每个五星的抽数"""
    if not gacha_list:
        return []
    
    gacha_list = list(reversed(gacha_list))
    
    gacha_type = gacha_list[0].get('gacha_type', '') if gacha_list else ''
    results = []
    current_pulls = 0

    for item in gacha_list:
        current_pulls += 1
        if item['rank_type'] == '5':  # 五星
            # 判断是否歪了
            is_wai = is_wai_item(item['name'], item['item_type'], gacha_type)
            
            results.append({
                'name': item['name'],
                'rank_type': item['rank_type'],
                'item_type': item['item_type'],
                'time': item['time'],
                'pulls': current_pulls,  # 到这个五星之前的抽数（不包括五星）
                'avatar_url': get_avatar_url(item['name'], item['item_type']),
                'pulls_before': current_pulls,  # 五星下面的抽数（不包括五星）
                'primogems_cost': current_pulls * 160,  # 原石消耗（不包括五星）
                'is_wai': is_wai  # 是否歪了
            })
            current_pulls = 0
    return results

def calculate_four_star_pulls(gacha_list):
    """计算每个四星之前的抽数（以四星为结束点）"""
    if not gacha_list:
        return []
    
    gacha_list = list(reversed(gacha_list))
    results = []
    current_pulls = 0

    for item in gacha_list:
        current_pulls += 1
        
        if item['rank_type'] == '4':  # 四星
            # 四星下面的抽数就是 pulls_before
            results.append({
                'name': item['name'],
                'rank_type': item['rank_type'],
                'item_type': item['item_type'],
                'time': item['time'],
                'pulls': current_pulls,
                'avatar_url': get_avatar_url(item['name'], item['item_type']),
                'pulls_before': current_pulls,  # 四星下面的抽数（包含四星）
                'primogems_cost': current_pulls * 160  # 原石消耗（包含四星）
            })
            current_pulls = 0
    
    return results

def calculate_stats(gacha_list):
    """计算统计数据"""
    if not gacha_list:
        return {
            'total_pulls': 0,
            'total_primogems': 0,
            'five_star_count': 0,
            'four_star_count': 0,
            'three_star_count': 0
        }
    
    total_pulls = len(gacha_list)
    five_star_count = sum(1 for item in gacha_list if item['rank_type'] == '5')
    four_star_count = sum(1 for item in gacha_list if item['rank_type'] == '4')
    three_star_count = sum(1 for item in gacha_list if item['rank_type'] == '3')
    
    return {
        'total_pulls': total_pulls,
        'total_primogems': total_pulls * 160,
        'five_star_count': five_star_count,
        'four_star_count': four_star_count,
        'three_star_count': three_star_count
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/gachaLog', methods=['POST'])
def analyze():
    """分析抽卡数据"""
    task_id = None
    try:
        data = request.json
        url = data.get('url')
        task_id = data.get('task_id')
        
        if not url:
            return jsonify({'error': '请提供抽卡链接'}), 400
        
        if not task_id:
            return jsonify({'error': '缺少任务ID'}), 400
        
        # 创建任务
        create_task(task_id)
        
        # 获取所有卡池的数据
        gacha_data = {}
        for gacha_type_id in gacha_query_type_dict.keys():
            gacha_list = http.get(url, gacha_type_id, task_id)
            
            if gacha_list == False:
                return jsonify({'error': "抽卡记录链接已过期！"}), 500
            
            if gacha_list:
                pulls_data = calculate_pulls(gacha_list)
                four_star_pulls_data = calculate_four_star_pulls(gacha_list)
                stats_data = calculate_stats(gacha_list)
                
                gacha_data[gacha_type_id] = {
                    'name': gacha_type_dict.get(gacha_type_id, gacha_query_type_dict.get(gacha_type_id, '')),
                    'pulls': pulls_data,
                    'four_star_pulls': four_star_pulls_data,
                    'stats': stats_data,
                    'raw_data': gacha_list
                }
            else:
                gacha_data[gacha_type_id] = {
                    'name': gacha_type_dict.get(gacha_type_id, gacha_query_type_dict.get(gacha_type_id, '')),
                    'pulls': [],
                    'four_star_pulls': [],
                    'stats': {
                        'total_pulls': 0,
                        'total_primogems': 0,
                        'five_star_count': 0,
                        'four_star_count': 0,
                        'three_star_count': 0
                    },
                    'raw_data': []
                }
        
        return jsonify({
            'success': True,
            'data': gacha_data
        })
        
    except Exception as e:
        print(f"错误: {str(e)}")
        return jsonify({'error': str(e)}), 500
    finally:
        # 任务完成后删除任务数据
        if task_id:
            delete_task(task_id)

@app.route('/api/avatars', methods=['GET'])
def get_avatars():
    """获取角色和武器头像列表"""
    try:
        # 角色头像API
        character_url = "https://act-api-takumi-static.mihoyo.com/common/blackboard/ys_obc/v1/home/content/list?app_sn=ys_obc&channel_id=25"
        # 武器头像API
        weapon_url = "https://act-api-takumi-static.mihoyo.com/common/blackboard/ys_obc/v1/home/content/list?app_sn=ys_obc&channel_id=5"
        
        character_resp = requests.get(character_url, timeout=10)
        weapon_resp = requests.get(weapon_url, timeout=10)
        
        result = {
            'characters': character_resp.json() if character_resp.status_code == 200 else {},
            'weapons': weapon_resp.json() if weapon_resp.status_code == 200 else {}
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"获取头像错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/getPage', methods=['GET'])
def getPage():
    task_id = request.args.get('task_id')
    if task_id:
        return jsonify(get_task_progress(task_id))
    return jsonify({"name": "", "page": "第1页"})

if __name__ == '__main__':
    # 启动时加载头像数据
    load_avatars()
    app.run(host='0.0.0.0', port=ServerPort, debug=DebugMode)