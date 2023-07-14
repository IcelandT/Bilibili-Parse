import requests
import ffmpeg
from tqdm import tqdm
from loguru import logger

import re
import json
import os


class BilibiliBvidDownload:
    headers = {
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://www.bilibili.com/',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    params = {
        'spm_id_from': '333.1007.tianma.1-1-1.click',
        'vd_source': '1a31b1526ae03de47f95a1a72bb61fa6'
    }

    def __init__(
            self,
            bvid
    ):
        assert isinstance(bvid, (str, list)), 'bvid参数的类型仅包含字符串或列表!'
        self.bvid = bvid

    def _process_request(self, params=None):
        for url in self._handle_bvid():
            yield self.get_response(url, params)

    def _handle_bvid(self):
        """ 处理 bvid """
        if isinstance(self.bvid, list):
            for vid in self.bvid:
                url = f'https://www.bilibili.com/video/{vid}/'
                yield url
        else:
            url = f'https://www.bilibili.com/video/{self.bvid}/'
            yield url

    def _merge_audio_and_video(self, bvid):
        """ ffmpeg合并音视频 """
        video_path = f'./video/{bvid}_video.m4s'
        audio_path = f'./video/{bvid}_audio.m4s'

        # 合并
        video = ffmpeg.input(video_path)
        audio = ffmpeg.input(audio_path)
        output = ffmpeg.output(video, audio, f'./video/{bvid}.mp4', r=60)
        ffmpeg.run(output, capture_stdout=True, capture_stderr=True, overwrite_output=True)

        # 删除m4s文件
        os.remove(video_path)
        os.remove(audio_path)

    def _process_merge(self, bvid):
        """ 处理需要合并的文件 """
        # 判断是否存在两个 bvid 相同的文件
        for _, _, files in os.walk('./video'):
            identical_bvid_files = [file for file in files if f'{bvid}_' in file]
            if len(identical_bvid_files) == 2:
                # 执行音视频合并命令
                self._merge_audio_and_video(bvid)
            else:
                for file in identical_bvid_files:
                    os.remove(f'./video/{file}')

    def _downloader(self, url, bvid, types):
        """ 下载器 """
        # 判断文件夹是否存在
        if not os.path.exists('./video'):
            os.mkdir('./video')

        # 保存音视频文件
        response = self.get_response(url)
        if response.status_code != 403:
            total = int(response.headers.get('content-length', 0))
            file_name = f'./video/{bvid}_{types}.m4s'
            with open(file_name, mode='wb') as f, tqdm(
                total=total,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024
            ) as bar:
                for content_data in response.iter_content(chunk_size=1024):
                    size = f.write(content_data)
                    bar.update(size)

    def get_response(self, url, params=None, stream=False):
        response = requests.get(
            url=url,
            headers=self.headers,
            params=params,
            stream=stream
        )
        if response.status_code in [200, 206]:
            # logger.debug(
            #     """
            #         -------------- request information --------------
            #         url = %s
            #         status code = %s
            #         args = {'headers': %s 'params': %s}
            #     """
            #     % (
            #         url,
            #         response.status_code,
            #         self.headers,
            #         params,
            #     )
            # )
            return response
        else:
            logger.error(
                """
                    -------------- bad request --------------
                    url = %s
                    status code = %s
                    args = {'headers': %s, 'params': %s}
                """
                % (
                    url,
                    response.status_code,
                    self.headers,
                    params
                )
            )

    def parse_download_url(self):
        """ 解析下载url """
        for response in self._process_request(self.params):
            response_text = response.text

            # 提取相关字段
            field_data_template = '<script>window.__playinfo__=(.*?)</script>'
            bvid_template = '"bvid":"(.*?)"'
            field_data = re.findall(field_data_template, response_text)[0]
            bvid = re.findall(bvid_template, response_text)[0]

            json_field_data = json.loads(field_data)
            # 获取所有 video baseUrl
            video_baseurl_list = list()
            video_list = json_field_data['data']['dash']['video']
            for video in video_list:
                video_baseurl_list.append(video['baseUrl'])

            # 获取所有的 audio baseUrl
            audio_baseurl_list = list()
            audio_list = json_field_data['data']['dash']['audio']
            for audio in audio_list:
                audio_baseurl_list.append(audio['baseUrl'])

            # 删除空数据
            video_baseurl_list = [baseurl for baseurl in video_baseurl_list if bool(baseurl)]
            audio_baseurl_list = [baseurl for baseurl in audio_baseurl_list if bool(baseurl)]

            for video_baseurl, audio_baseurl in zip(video_baseurl_list, audio_baseurl_list):
                # 找到一个可以下载的 url
                self._downloader(url=video_baseurl, bvid=bvid, types='video')
                self._downloader(url=audio_baseurl, bvid=bvid, types='audio')

                # 执行合并
                self._process_merge(bvid=bvid)

            if os.path.isfile(f'./video/{bvid}.mp4'):
                logger.debug(f'{bvid} 保存完成')
            else:
                logger.error(f'{bvid} 保存失败, 请重试')


if __name__ == '__main__':
    bvid_spider = BilibiliBvidDownload(['BV1J14y1o7x4', 'BV1nV4y187vG'])
    bvid_spider.parse_download_url()

