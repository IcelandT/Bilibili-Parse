import sys
import re
import json
import os
import argparse
import textwrap

import asyncio
import aiofiles
from tqdm import tqdm
from rich.console import Console
from aiohttp import ClientSession
from moviepy.editor import VideoFileClip, AudioFileClip


class Requests(object):
    def __init__(self) -> None:
        self.url = ''
        self.headers = None,
        self.params = None,
        self.data = None,
        self.json = None,
        self.allow_redirects = True

    async def get(self, session: ClientSession) -> str:
        async with session.get(
            url=self.url,
            headers=self.headers,
            params=self.params,
            allow_redirects=self.allow_redirects
        ) as response:
            return await response.text()

    async def post(self, session: ClientSession) -> str:
        async with session.post(
                url=self.url,
                headers=self.headers,
                data=self.data,
                json=self.json,
                allow_redirects=self.allow_redirects
        ) as response:
            return await response.text()

    async def requests(
            self,
            url: str = '',
            method: str = 'GET',
            params: dict = None,
            data: dict = None,
            json_data: dict = None,
            headers: dict = None,
            allow_redirects: bool = True
    ) -> str:
        self.url = url
        self.headers = headers
        self.params = params
        self.data = data
        self.json = json_data
        self.allow_redirects = allow_redirects

        async with ClientSession() as session:
            if data or json_data or method == 'POST':
                return await self.post(session=session)
            else:
                return await self.get(session=session)


class BDown(object):
    headers = {
        'Referer': 'https://www.bilibili.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }

    def __init__(self, bvid, works) -> None:
        self.bvid = bvid
        self.works = works
        self.task = asyncio.Queue()

    @staticmethod
    def parse_audio_frequency(response) -> tuple[str, str, str]:
        """
        解析 response 中的 video url 和 audio url
        :param response:
        :return:
        """
        # 匹配 script、和视频标题
        script_code_template = '<script>window.__playinfo__=(.*?)</script>'
        video_title_template = '<title data-vue-meta="true">(.*?)</title>'

        script_code = re.findall(script_code_template, response)
        video_title_list = re.findall(video_title_template, response)
        if script_code and video_title_list:
            json_script_code = json.loads(script_code[0])
            data = json_script_code.get('data')
            dash = data.get('dash')
            video_url = dash.get('video')[0].get('baseUrl')
            audio_url = dash.get('audio')[0].get('baseUrl')
            video_title = video_title_list[0]
            if video_url and audio_url:
                return video_url, audio_url, video_title
            else:
                console = Console()
                console.print('提取时出现错误', style='bold red')
                sys.exit(1)

    async def create_task(self) -> None:
        if isinstance(self.bvid, list):
            for vid in self.bvid:
                await self.task.put(vid)
        elif isinstance(self.bvid, str):
            await self.task.put(self.bvid)
        else:
            console = Console()
            console.print('仅允许输入列表或字符串', style='bold red')
            sys.exit(1)

    async def download(self, url, url_type, video_title) -> None:
        if url_type == 'video':
            file_name = video_title + '_video.m4s'
        else:
            file_name = video_title + '_audio.m4s'

        async with ClientSession() as session:
            async with session.get(url, headers=self.headers) as response:
                if not os.path.exists('.\\video'):
                    os.mkdir('.\\video')
                save_path = os.path.join('.\\video', file_name)
                # 文件总大小
                total_size = int(response.headers['Content-Length'])
                # 设置进度条样式和参数
                progress_bar = tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    dynamic_ncols=True,
                    ncols=30,
                )
                progress_bar.set_description(url_type)
                async with aiofiles.open(save_path, mode='wb') as f:
                    async for chunk in response.content.iter_chunked(1024):
                        if not chunk:
                            break
                        await f.write(chunk)
                        progress_bar.update(len(chunk))
                    progress_bar.close()

    async def crawl(self, bvid) -> None:
        url = 'https://www.bilibili.com/video/' + bvid + '/'
        params = {
            'spm_id_from': '333.1007.tianma.2-3-6.click',
            'vd_source': '1a31b1526ae03de47f95a1a72bb61fa6'
        }
        response = await Requests().requests(
            url=url,
            method='GET',
            params=params,
            headers=self.headers
        )

        # 提取 video、audio 文件
        video_url, audio_url, video_title = self.parse_audio_frequency(response)

        # 分别传入下载器
        await self.download(video_url, 'video', video_title)
        await self.download(audio_url, 'audio', video_title)

        # 合并音视频
        video_file = os.path.join('.\\video', video_title + '_video.m4s')
        audio_file = os.path.join('.\\video', video_title + '_audio.m4s')
        video = VideoFileClip(video_file)
        audio = AudioFileClip(audio_file)
        video = video.set_audio(audio)
        # 输出合并后的文件
        out_file = os.path.join('.\\video', video_title + '.mp4')
        video.write_videofile(out_file, codec='libx264', audio_codec='aac')
        console = Console()
        console.print(':victory_hand_medium-light_skin_tone:'
                      ' 下载成功! '
                      ':victory_hand_medium-light_skin_tone:', style='bold cyan')
        # 删除音视频文件
        os.remove(video_file)
        os.remove(audio_file)

    async def worker(self) -> None:
        if not self.task.empty():
            bvid = await self.task.get()
            await self.crawl(bvid)
            self.task.task_done()
        else:
            pass

    async def start(self) -> None:
        await self.create_task()
        while not self.task.empty():
            workers = [
                asyncio.create_task(self.worker())
                for _ in range(int(self.works))
            ]
            await asyncio.gather(*workers)


async def main(bvid, works) -> None:
    spider = BDown(bvid, works)
    await spider.start()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Bilibili parse',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            r"""
                    ____  ______    ________  ______    ____   ____  ___    ____  _____ ______
                   / __ )/  _/ /   /  _/ __ )/  _/ /   /  _/  / __ \/   |  / __ \/ ___// ____/
                  / __  |/ // /    / // __  |/ // /    / /   / /_/ / /| | / /_/ /\__ \/ __/   
                 / /_/ // // /____/ // /_/ // // /____/ /   / ____/ ___ |/ _, _/___/ / /___   
                /_____/___/_____/___/_____/___/_____/___/  /_/   /_/  |_/_/ |_|/____/_____/   
                                                                                                                                                                                                                                                
                如何使用？
                方法: python async_b_down.py -b 视频的bvid号 -w 并发数量
                例如: python async_b_down.py -b BV1UQ4y1d7os -w 1
            """
        ))
    parser.add_argument('-b', '--bvid', type=str, required=True, help='bvid号')
    parser.add_argument('-w', '--works', type=int, required=True, help='并发数量')
    try:
        args = parser.parse_args()
        asyncio.run(main(args.bvid, args.works))
    except:
        console = Console()
        console.print(':light_bulb: 未填写对应的参数 :light_bulb:', style='bold yellow')