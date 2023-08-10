from sys import exit
from re import findall
from json import loads
import os
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from textwrap import dedent

import asyncio
import aiofiles
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
from aiohttp import ClientSession
from moviepy.editor import VideoFileClip, AudioFileClip

console = Console()


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


class AsyncBParse(object):
    headers = {
        'Referer': 'https://www.bilibili.com/',
        'Cookie': 'SESSDATA=6fa654bd%2C1705137814%2C77ce0%2A721XIprtlSi35wkAFvu9Hr7ZTZ0Y_q2QTtYva2zkwkCOpSLv10zMuVL_S8l2HZNXlpU2-XEwAAXQA',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }

    def __init__(self, vid) -> None:
        self.vid = vid
        self.video_dir = '.\\video'

    @staticmethod
    async def parse_audio_frequency(response) -> tuple[str, str, str]:
        """
        解析视频中的信息，如 video url、播放量等
        :param response:
        :return:
        """
        match_script_code = '<script>window.__playinfo__=(.*?)</script>'
        match_video_title = '"title":"(.*?)",'
        match_play_volume = '视频播放量 (.*?)、'
        match_barrage_quantity = '弹幕量 (.*?)、'
        match_like_count = '点赞数 (.*?)、'
        match_coins_nums = '投硬币枚数 (.*?)、'

        script_code_list = findall(match_script_code, response)
        play_volume_list = findall(match_play_volume, response)
        barrage_quantity_list = findall(match_barrage_quantity, response)
        video_title_list = findall(match_video_title, response)
        like_count_list = findall(match_like_count, response)
        coins_nums = findall(match_coins_nums, response)
        if script_code_list and video_title_list:
            json_script_code = loads(script_code_list[0])
            dash = json_script_code.get('data').get('dash')
            if dash:
                video_url = dash.get('video')[0].get('baseUrl')
                audio_url = dash.get('audio')[0].get('baseUrl')
                video_title = video_title_list[0]
                if video_url and audio_url:
                    # 视频基本信息
                    table = Table(show_header=True, header_style='bold magenta')
                    table.add_column('播放量', justify='right',)
                    table.add_column('弹幕量', justify='right',)
                    table.add_column('点赞数', justify='right',)
                    table.add_column('硬币数', justify='right',)
                    table.add_column('标题')
                    table.add_row(
                        play_volume_list[0],
                        barrage_quantity_list[0],
                        like_count_list[0],
                        coins_nums[0],
                        video_title
                    )
                    console.print(table)
                    return video_url, audio_url, video_title
                else:
                    console.print('提取时出现错误', style='bold red')
                    exit(1)

    @staticmethod
    async def download_chunk(session, url, start_chunk, end_chunk, progress_bar) -> bytes:
        headers = {'Range': f'bytes={start_chunk}-{end_chunk}'}
        async with session.get(url=url, headers=headers) as response:
            chunk = await response.read()
            progress_bar.update(len(chunk))
            return chunk

    async def download(self, url, url_type, video_title) -> None:
        if url_type == 'video':
            file_name = video_title + '_video.m4s'
        else:
            file_name = video_title + '_audio.m4s'

        async with ClientSession() as session:
            async with session.get(url) as response:
                if not os.path.exists(self.video_dir):
                    os.mkdir(self.video_dir)
                save_path = os.path.join(self.video_dir, file_name)
                # 文件总大小
                total_size = int(response.headers['Content-Length'])
                # 设置进度条样式和参数
                progress_bar = tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    dynamic_ncols=True,
                    ncols=20
                )
                progress_bar.set_description(url_type)
                # 分段下载
                tasks = list()
                num_chunks = 20
                chunk_size = total_size // num_chunks
                for i in range(num_chunks):
                    start_byte = i * chunk_size
                    # 计算最后一段的结束位置
                    end_byte = start_byte + chunk_size - 1 if i < num_chunks - 1 else total_size - 1
                    task = asyncio.create_task(
                        self.download_chunk(session, url, start_byte, end_byte, progress_bar)
                    )
                    tasks.append(task)
                all_chunk = await asyncio.gather(*tasks)
                async with aiofiles.open(save_path, mode='wb') as f:
                    for chunk in all_chunk:
                        await f.write(chunk)
                progress_bar.close()

    async def parser(self, vid) -> None:
        url = 'https://www.bilibili.com/video/' + vid + '/'
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
        video_url, audio_url, video_title = await self.parse_audio_frequency(response)

        # 将 video、audio url 分别传入下载器
        await self.download(video_url, 'video', video_title)
        await self.download(audio_url, 'audio', video_title)

        # 合并音视频
        video_file = os.path.join(self.video_dir, video_title + '_video.m4s')
        audio_file = os.path.join(self.video_dir, video_title + '_audio.m4s')
        video = VideoFileClip(video_file)
        audio = AudioFileClip(audio_file)
        video = video.set_audio(audio)
        # 输出合并后的文件
        out_file = os.path.join(self.video_dir, video_title + '.mp4')
        video.write_videofile(
            out_file,
            codec='libx264',
            audio_codec='aac',
            fps=30.303,
            preset='ultrafast'
        )
        console.print(':victory_hand_medium-light_skin_tone:'
                      ' 下载成功! '
                      ':victory_hand_medium-light_skin_tone:', style='bold cyan')
        # 删除音视频文件
        os.remove(video_file)
        os.remove(audio_file)

    async def start(self) -> None:
        self.vid = self.vid.replace(' ', '')
        vid_list = self.vid.split(',')
        if len(vid_list) == 1:
            tasks = [
                asyncio.create_task(self.parser(vid))
                for vid in vid_list
            ]
            await asyncio.gather(*tasks)
        else:
            console.print(
                ':warning-emoji: 当前仅允许传入一个vid!\n'
                ':warning-emoji: 输入 python Async_BParse.py -h 获取帮助'
            )


if __name__ == '__main__':
    parser = ArgumentParser(
        description='Bilibili parse',
        formatter_class=RawDescriptionHelpFormatter,
        epilog=dedent(
            r"""
                    ____  ______    ________  ______    ____   ____  ___    ____  _____ ______
                   / __ )/  _/ /   /  _/ __ )/  _/ /   /  _/  / __ \/   |  / __ \/ ___// ____/
                  / __  |/ // /    / // __  |/ // /    / /   / /_/ / /| | / /_/ /\__ \/ __/   
                 / /_/ // // /____/ // /_/ // // /____/ /   / ____/ ___ |/ _, _/___/ / /___   
                /_____/___/_____/___/_____/___/_____/___/  /_/   /_/  |_/_/ |_|/____/_____/   

                如何使用？
                方法: python ABParse.py -b 视频vid号
                例如: python ABParse.py -b BV1UQ4y1d7os
            """
        ))
    parser.add_argument('-v', '--vid', type=str, help='vid号')
    args = parser.parse_args()
    vid = args.vid
    if vid:
        Async_BParse = AsyncBParse(vid)
        asyncio.run(Async_BParse.start())
    else:
        console.print(
            ':warning-emoji:[bold red] 未填写对应的参数!\n'
            ':warning-emoji:[bold red] 输入 python Async_BParse.py -h 获取帮助'
        )
