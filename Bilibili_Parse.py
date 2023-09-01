import os
import json
import operator
import threading
from time import sleep
from re import findall, sub
from textwrap import dedent
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from typing import Dict, Optional

from rich import box
from rich.table import Table
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)
import ffmpeg
import requests
from requests import Response
from requests.exceptions import HTTPError

import setting


class BlibiliParse(object):
    def __init__(
        self,
        bv: str,
        thread_nums: int = 5
    ) -> None:
        self.bv = bv
        self.video_url = None
        self.audio_url = None
        self.cookie = None
        self.console = Console()
        self.thread_nums = thread_nums

        if hasattr(setting, 'COOKIE'):
            self.cookie = getattr(setting, 'COOKIE')
            self.console.print("[i]✓[/i] cookie [i]✓[/i]", style='cyan')
        else:
            self.console.print("[i]✕[/i] cookie not allocation [i]✕[/i]", style='cyan')

        self.bv_name = None
        self.output_path = 'video'
        self.chunk_buffer = dict()

    @property
    def _headers(self) -> Dict:
        headers = {
            "Origin": "https://www.bilibili.com",
            "Referer": "https://www.bilibili.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
        }
        if self.cookie:
            headers.update({"Cookie": self.cookie})

        return headers

    @property
    def _merge_url(self) -> str:
        return 'https://www.bilibili.com/video/' + self.bv + '/'

    @property
    def _progress(self) -> Progress:
        progress = Progress(
            TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeElapsedColumn(),
        )
        return progress

    @property
    def save_video_audio(self):
        video_path = None
        audio_path = None
        if not os.path.exists(self.output_path):
            os.mkdir(self.output_path)

        for chunk_name in self.chunk_buffer:
            self.chunk_buffer[chunk_name] = sorted(self.chunk_buffer[chunk_name], key=operator.itemgetter(0))
            with open(f'{self.output_path}\\{chunk_name}.m4s', mode='wb') as vf:
                for chunk in self.chunk_buffer[chunk_name]:
                    content = chunk[1]
                    vf.write(content)

            if chunk_name == 'video':
                video_path = os.path.join(self.output_path, 'video') + '.m4s'
            else:
                audio_path = os.path.join(self.output_path, 'audio') + '.m4s'

        return video_path, audio_path

    def _get_response(
        self,
        url: Optional[str],
        name: Optional[str] = None,
        thread_num: Optional[int] = None,
        progress: Progress = None,
        task_id: TaskID = None,
        start_byte: Optional[str] = None,
        end_byte: Optional[str] = None
    ) -> Response:
        headers = self._headers
        if all([start_byte, end_byte]):
            headers = self._headers
            headers.update({"Range": f"bytes={start_byte}-{end_byte}"})

        response = requests.get(url=url, headers=headers, stream=True)
        if response.status_code in [200, 206]:
            if all([start_byte, end_byte]):
                chunk_buffer = list()
                for chunk in response.iter_content(1024):
                    progress.update(task_id, advance=len(chunk))
                    chunk_buffer.append(chunk)
                self.chunk_buffer[name].append((thread_num, b''.join(chunk_buffer)))

            return response
        else:
            raise HTTPError(f'response status code: {response.status_code}')

    def _parse_video_and_audio(self, text_dict: dict) -> None:
        """ 解析 video 和 audio """
        dash = text_dict.get('data').get('dash')
        video_list = dash.get('video'); audio_list = dash.get('audio')
        self.video_url = video_list[0].get('baseUrl')
        self.audio_url = audio_list[0].get('baseUrl')
        self.console.print(f"video {video_list[0].get('height')}P", style='cyan')

    def _parse_bv_brief_introduction(self, response: str) -> None:
        bv_title_regex = '"part":"(.*?)",'
        bv_author_regex = '视频作者 (.*?),'
        bv_title_list = findall(bv_title_regex, response)
        bv_author_list = findall(bv_author_regex, response)
        if all([bv_title_list, bv_author_list]):
            table = Table(box=box.SIMPLE, style='gray30')
            table.add_column('[i]bv[/i]', justify='center', style='gray46', header_style='gray46')
            table.add_column('[i]标题[/i]', justify='center', style='gray46', header_style='gray46')
            table.add_column('[i]作者[/i]', justify='center', style='gray46', header_style='gray46')

            bv_title = bv_title_list[0]
            bv_author = bv_author_list[0]
            table.add_row(self.bv, bv_title, bv_author)
            self.bv_name = bv_title
            self.console.print(table, justify='center')

    def _parse_bv_information(self, response: str) -> None:
        """ 提取 script """
        script_list = findall('<script>window.__playinfo__=(.*?)</script>', response)
        if not script_list:
            self.console.print('[i]✕[/i] 检查 bv 是否正确 [i]✕[/i]', style="cyan")
        else:
            self._parse_bv_brief_introduction(response)
            text_dict = json.loads(script_list[0])
            self._parse_video_and_audio(text_dict)

    def merge_video(self) -> None:
        video_file, audio_file = self.save_video_audio
        bv_name = sub('[\/:*"<>|?]', '', self.bv_name)
        output_file = os.path.join(self.output_path, bv_name) + '.mp4'
        input_video = ffmpeg.input(video_file)
        input_audio = ffmpeg.input(audio_file)
        output = ffmpeg.output(input_video, input_audio, output_file, vcodec='copy', acodec='copy', r=30, y='-y')
        ffmpeg.run(output, cmd='./ffmpeg/bin/ffmpeg.exe', capture_stderr=True)

        sleep(0.2)
        os.remove(video_file)
        os.remove(audio_file)

    def download(self) -> None:
        for key, value in dict(video=self.video_url, audio=self.audio_url).items():
            self.chunk_buffer[key] = list()
            response = self._get_response(value)
            total_size = int(response.headers.get('content-length'))
            # 分块
            chunk_size = total_size // self.thread_nums
            chunk_list = [(i * chunk_size, (i + 1) * chunk_size - 1) for i in range(self.thread_nums - 1)]
            chunk_list.append((chunk_list[-1][-1] + 1, total_size))

            thread_list = list()
            progress = self._progress
            task_id = progress.add_task("download", filename=key, total=total_size)
            with progress:
                for thread_num in range(self.thread_nums):
                    start_byte = str(chunk_list[thread_num][0])
                    end_byte = str(chunk_list[thread_num][1])

                    my_thread = threading.Thread(
                        target=self._get_response,
                        args=(value, key, thread_num, progress, task_id, start_byte, end_byte)
                    )
                    thread_list.append(my_thread)
                    my_thread.start()

                for thread in thread_list:
                    thread.join()

    def start_parse(self):
        response = self._get_response(self._merge_url)
        self._parse_bv_information(response.text)
        # 下载
        self.download()
        # 音视频合并
        self.merge_video()
        self.console.print(f'\n[i]✓[/i] {self.bv_name}', style='cyan')


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
                方法: python Bilibili_Parse.py -t 线程数(默认为5) -v 视频vid号
                例如: python Bilibili_Parse.py -t 5 -v BV1UQ4y1d7os
            """
        ))
    parser.add_argument('-t', '--thread', type=int, help='线程数量')
    parser.add_argument('-v', '--bv', type=str, help='vid号')
    args = parser.parse_args()
    thread_nums = args.thread
    bv = args.bv
    if bv:
        if thread_nums:
            parse = BlibiliParse(thread_nums=thread_nums, bv=bv)
        else:
            parse = BlibiliParse(bv=bv)

        parse.start_parse()
    else:
        Console().print(
            ':warning-emoji:[bold red] 未填写bv参数!\n'
            ':warning-emoji:[bold red] 输入 python Bilibili_Parse.py -h 获取帮助'
        )