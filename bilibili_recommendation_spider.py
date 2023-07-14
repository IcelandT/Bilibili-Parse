import requests
import execjs
import subprocess
from loguru import logger

import json
import re
import os


class BilibiliSpider:
    headers: dict = {
        'Connection': 'close',
        'Origin': 'https://www.bilibili.com',
        'Cookie': "buvid3=822E2C15-49B3-1C49-9476-882861297A7353598infoc; b_nut=1689151953; i-wanna-go-back=-1; _uuid=AF62FFE6-BC66-D661-7272-2E737A10A9CCF55290infoc; FEED_LIVE_VERSION=V8; header_theme_version=CLOSE; home_feed_column=5; buvid4=65ABB004-A3A5-9338-2C5D-C1C0BBE827BC02525-023070310-5XDEyMmqGJZ2Goa4%2Buy5ORAMxPKSas%2Fu; buvid_fp=88bc13d87440d348e368be232ade8863; CURRENT_FNVAL=4048; SESSDATA=38aa6af9%2C1704707686%2Cdd049%2A72VSSQqWZM7eqjwHMIJg_AUf01FwFJGE7vi7X5eefaEfN12lWD61SZGYpZxecg5FoYi2crRQAAXQA; bili_jct=7fa503ac811dab64643bfd7e629b4b72; DedeUserID=352118593; DedeUserID__ckMd5=caa5a0065a7ba677; rpdid=|(k|mmYl~|u)0J\"uY)mullYmR; sid=53tcmcnr; b_ut=5; bsource=search_baidu; bp_video_offset_352118593=817710847735365600; nostalgia_conf=-1; innersign=0; b_lsid=FBB7FE66_1894E416A23; browser_resolution=1920-961; PVID=5",
        'Referer': 'https://www.bilibili.com/video/BV1BW4y1f7HH/?spm_id_from=333.1007.tianma.5-2-16.click&vd_source=1a31b1526ae03de47f95a1a72bb61fa6',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    proxies: dict = {
        'http': '127.0.0.1:7890',
        "https": '127.0.0.1:7890'
    }

    def __init__(self):
        pass

    @staticmethod
    def get_w_rid_and_wts(params: dict):
        """
        执行本地 js 代码，模拟加密
        """
        with open('w_rid_wts.js', mode='r', encoding='utf-8') as f:
            js_file = f.read()

        js_code = execjs.compile(js_file)
        js_encrypt = js_code.call('js_encrypt', params)
        w_rid = js_encrypt.get('w_rid')
        wts = js_encrypt.get('wts')
        logger.debug(
            """
                -------------- JSEncrypt information --------------
                encrypt = %s
            """
            % (
                js_encrypt
            )
        )
        return w_rid, wts

    def get_response(
            self,
            url: str,
            method: str = "GET",
            params: dict = None,
            data: dict = None
    ):
        response = requests.get(url=url, headers=self.headers, proxies=self.proxies, params=params)
        if method == "POST":
            response = requests.post(url=url, headers=self.headers, proxies=self.proxies, data=data)

        if response.status_code in [200, 206]:
            logger.debug(
                """
                    -------------- request information --------------
                    url = %s
                    method = %s
                    args = {'headers': %s, 'proxies': %s, 'params': %s, 'data': %s}
                """
                % (
                    url,
                    method,
                    self.headers,
                    self.proxies,
                    params,
                    data
                )
            )
            # print(response.text)
            return response
        else:
            logger.error(
                """
                    -------------- bad request --------------
                    url = %s
                    method = %s
                    status code = %s
                    args = {'headers': %s, 'proxies': %s, 'params': %s, 'data': %s}
                """
                % (
                    url,
                    method,
                    response.status_code,
                    self.headers,
                    self.proxies,
                    params,
                    data
                )
            )
            pass

    def start_request(self):
        start_url = 'https://www.bilibili.com/'
        yield self.get_response(url=start_url)

    def parse_data(self):
        for response in self.start_request():
            # 正则表达式提取规则
            show_list_template = '.reportId="(.*?)";'
            uniq_id_template = '"uniq_page_id":(.*?)}'

            # 正则提取
            show_list = re.findall(show_list_template, response.text)
            uniq_id = re.findall(uniq_id_template, response.text)

            # 拼接参数
            show_list = [show.replace('_n', '') for show in show_list]
            last_show_list = ','.join(show_list)
            if uniq_id and last_show_list:
                # 构建请求 params
                params = {
                    'web_location': '1430650',
                    'y_num': '4',
                    'fresh_type': '4',
                    'feed_version': 'V8',
                    'fresh_idx_1h': '2',
                    'fetch_row': '7',
                    'fresh_idx': '2',
                    'brush': '2',
                    'homepage_ver': '1',
                    'ps': '12',
                    'last_y_num': '5',
                    'screen': '1920-961',
                    'outside_trigger': '',
                    'last_showlist': last_show_list,
                    'uniq_id': uniq_id[0],
                }

                # 获取加密值
                w_rid, wts = self.get_w_rid_and_wts(params)
                update_params = {
                    'w_rid': w_rid,
                    'wts': wts
                }
                params.update(update_params)

                api = 'https://api.bilibili.com/x/web-interface/wbi/index/top/feed/rcmd'
                yield self.get_response(
                    url=api,
                    method='GET',
                    params=params
                )

    def parse_under_api_url(self):
        """ 解析 api 中推荐视频的 bvid """
        for response in self.parse_data():
            # bvid 的提取规则
            bvid_template = '"bvid":"(.*?)"'

            # 提取所有bvid
            bvid_list = re.findall(bvid_template, response.text)
            bvid_list = [bvid for bvid in bvid_list if bool(bvid)]
            for bvid in bvid_list:
                video_url = f'https://www.bilibili.com/video/{bvid}/'
                params = {
                    'spm_id_from': '333.1007.tianma.1-1-1.click',
                    'vd_source': '1a31b1526ae03de47f95a1a72bb61fa6'
                }
                yield self.get_response(
                    url=video_url,
                    method='GET',
                    params=params
                )

    def parse_video_and_audio_url(self):
        """ 解析 video 和 audio  """
        for response in self.parse_under_api_url():
            # 提取包含 video 和 audio 的字段
            get_field_template = 'window.__playinfo__=(.*?)</script>'
            bvid_template = '"bvid":"(.*?)"'

            # 正则提取
            field_list = re.findall(get_field_template, response.text)
            bvid_list = re.findall(bvid_template, response.text)
            if field_list and bvid_list:
                field = field_list[0]
                bvid = bvid_list[0]
                json_field = json.loads(field)

                # 提取 video 和 audio url
                video_url = json_field['data']['dash']['video'][0]['baseUrl']
                if 'logo=' in video_url:
                    video_url = json_field['data']['dash']['video'][1]['baseUrl']
                audio_url = json_field['data']['dash']['audio'][0]['baseUrl']

                information_dict = dict(bvid=bvid, video_url=video_url, audio_url=audio_url)
                self.download_video_and_audio(information_dict)

    def download_video_and_audio(self, data_dict: dict):
        """ 下载器 """
        bvid = data_dict['bvid']
        del data_dict['bvid']

        # download
        for keys in list(data_dict.keys()):
            url = data_dict[keys]
            content = self.get_response(url=url, method='GET')
            if content:
                content = content.content

                with open(f'./video/{bvid}_{keys.split("_")[0]}.m4s', mode='wb') as f:
                    f.write(content)

        # 检查 m4s 文件是否完整
        for _, _, files in os.walk('./video'):
            m4s_files = [file for file in files if bvid and '.m4s' in file]
            m4s_count = len(m4s_files)
            if m4s_count == 2:
                video = f'./video/{bvid}_video.m4s'
                audio = f'./video/{bvid}_audio.m4s'

                cmd = f'ffmpeg -r 30 -i {video} -i {audio} -c copy -shortest ./video/{bvid}.mp4 -n'
                subprocess.run(cmd, shell=True)
            else:
                # 删除 m4s 文件
                for m4s_file in m4s_files:
                    os.remove(f'./video/{m4s_file}')

    def run(self):
        self.parse_video_and_audio_url()


if __name__ == '__main__':
    bilibili_spider = BilibiliSpider()
    bilibili_spider.run()