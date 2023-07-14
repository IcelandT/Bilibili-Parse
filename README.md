# Bilibili-spider
#### 项目地址: <https://github.com/IcelandT/Bilibili-spider/tree/main>
## 文件说明
#### 1. bilibili_recommendation_spider.py  
> #### 首页推荐视频爬虫，不推荐使用.
###  
#### 2. bvid_download.py
> #### 对指定的bvid视频进行下载，暂时只支持同步下载
###
#### 3. w_rid_wts.js  
> #### w_rid 与 wts 参数加密文件，用于获取推荐视频的bvid，推荐使用pyexecjs本地运行
#### 参数逆向的分析讲解前往 
#### <https://blog.csdn.net/weixin_52807972/article/details/131700890?spm=1001.2014.3001.5501>
***
### 使用方法
+ #### python bilibili_recommendation_spider.py 
> #### 该文件会自动获取首页推荐视频的bvid，并对音频和视频进行下载
+ #### python bvid_download.py -b bvid
> #### -b 参数可以是单个也可以是多个，例如:
> ####     python bvid_download.py -b "123123123" "123123123"(必须是双引号，单引号会报错)