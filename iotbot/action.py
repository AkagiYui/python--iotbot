"""一些常用的方法

Tips: 如果开启队列，请将`action`定义为全局变量!,最重要的一点，开启队列方法都没有返回值，
    所以对于获取信息的api，千万不能用这个模式

对于发送语音，图片的方法，建议将timeout设置很短，因为暂时发现这类请求因为需要文件上传操作，
响应时间会较长，而且目前来看，如果文件较大导致上传时间太长，IOTBOT端会报错, IOTBOT响应的结果一定是错误的,
不过发送去的操作是能正常完成的。
"""
import functools
import json
import os
import time
from queue import Queue
from threading import Thread
from typing import Callable

import requests
from requests.exceptions import Timeout

from .client import IOTBOT
from .logger import Logger


class Action:
    '''
    :param qq_or_bot: qq号或者机器人实例(`IOTBOT`)
    :param queue: 是否开启队列，开启后任务将按顺序发送并延时指定时间，此参数与`queue_delay`对应
                  启用后，发送方法`没有返回值`
    :param queue_delay: 开启队列时发送每条消息间的延时, 保持默认即可
    :param timeout: 等待IOTBOT响应时间，不是发送请求的延时
    :param log_file_path: 日志文件路径
    :param api_path: 方法路径
    :param port: 端口
    :param host: ip
    '''

    def __init__(self,
                 qq_or_bot=None,
                 queue=False,
                 queue_delay=1.1,
                 timeout=15,
                 log_file_path=None,
                 api_path='/v1/LuaApiCaller',
                 port=8888,
                 host='http://127.0.0.1'):
        self.__timeout = timeout
        self.__api_path = api_path
        self.__port = int(os.getenv('IOTBOT_PORT') or port)
        self.__host = os.getenv('IOTBOT_HOST') or host
        if isinstance(qq_or_bot, IOTBOT):
            self.bind_bot(qq_or_bot)
        else:
            self.qq = int(qq_or_bot)
        self.logger = Logger(log_file_path)

        if queue:
            self.__use_queue = True
            self.__queue_delay = queue_delay
            self.__send_queue = Queue(maxsize=1000)
            self.__last_send_time = time.time()
            # 开启发送队列线程
            t = Thread(target=self.__send_thread)
            t.start()
        else:
            self.__use_queue = False

    def bind_bot(self, bot: IOTBOT):
        """绑定机器人"""
        self.qq = bot.qq
        self.__port = bot.port
        self.__host = bot.host

    def __send_thread(self):
        """
        发送队列线程
        负责执行队列的任务，并判断是否应该立即执行
        """
        while True:
            job = self.__send_queue.get()  # type: Callable
            left_time = self.__queue_delay - (time.time() - self.__last_send_time)
            if left_time > 0:
                # print(f'还没到发送时间...,请等待{left_time}s')
                time.sleep(left_time)
            try:
                # print('即将发送....')
                job()
            except Exception as e:
                print(f'出错了，我帮你处理了 -> {e}')
            finally:
                self.__last_send_time = time.time()
                # print(f'上次运行时间：{self.__last_send_time}')

    def send_friend_text_msg(self, toUser: int, content: str, timeout=5, **kwargs) -> dict:
        """发送好友文本消息"""
        data = {
            "toUser": toUser,
            "sendToType": 1,
            "sendMsgType": "TextMsg",
            "content": content,
            "groupid": 0,
            "atUser": 0,
            "replayInfo": None
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def get_user_list(self, timeout=5, **kwargs) -> dict:
        """获取好友列表"""
        return self.baseSender('post', 'GetQQUserList', {"StartIndex": 0}, timeout=timeout, **kwargs)

    def send_friend_voice_msg(self, toUser, voiceUrl='', voiceBase64Buf='', timeout=5, **kwargs) -> dict:
        """发送好友语音消息"""
        data = {
            "toUser": toUser,
            "sendToType": 1,
            "sendMsgType": "VoiceMsg",
            "content": "",
            "groupid": 0,
            "atUser": 0,
            "voiceUrl": voiceUrl,
            "voiceBase64Buf": voiceBase64Buf
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_friend_pic_msg(self, toUser, content='', picUrl='', picBase64Buf='', fileMd5='',
                            flashPic=False, timeout=5, **kwargs) -> dict:
        """发送好友图片消息"""
        data = {
            "toUser": toUser,
            "sendToType": 1,
            "sendMsgType": "PicMsg",
            "content": content,
            "groupid": 0,
            "atUser": 0,
            "picUrl": picUrl,
            "picBase64Buf": picBase64Buf,
            "fileMd5": fileMd5,
            "flashPic": flashPic
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_group_text_msg(self, toUser: int, content='', atUser=0, timeout=5, **kwargs) -> dict:
        """发送群文字消息"""
        data = {
            "toUser": toUser,
            "sendToType": 2,
            "sendMsgType": "TextMsg",
            "content": content,
            "groupid": 0,
            "atUser": atUser
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_group_voice_msg(self, toUser, voiceUrl='', voiceBase64Buf='', timeout=5, **kwargs) -> dict:
        """发送群语音"""
        data = {
            "toUser": toUser,
            "sendToType": 2,
            "sendMsgType": "VoiceMsg",
            "content": '',
            "groupid": 0,
            "atUser": 0,
            "voiceUrl": voiceUrl,
            "voiceBase64Buf": voiceBase64Buf
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_group_pic_msg(self, toUser: int, picUrl='', flashPic=False, atUser=0, content='',
                           picBase64Buf='', fileMd5='', timeout=3, **kwargs) -> dict:
        """发送群图片
        Tips:
            [秀图id] 各id对应效果
            40000   秀图
            40001   幻影
            40002   抖动
            40003   生日
            40004   爱你
            40005   征友
            40006   无(只显示大图无特效)

            [PICFLAG] 改变图文消息顺序
        """
        data = {
            "toUser": toUser,
            "sendToType": 2,
            "sendMsgType": "PicMsg",
            "content": content,
            "groupid": 0,
            "atUser": atUser,
            "picUrl": picUrl,
            "picBase64Buf": picBase64Buf,
            "fileMd5": fileMd5,
            "flashPic": flashPic
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_private_text_msg(self, toUser: int, content: str, groupid: int, timeout=5, **kwargs) -> dict:
        """发送私聊文字消息"""
        data = {
            "toUser": toUser,
            "sendToType": 3,
            "sendMsgType": "TextMsg",
            "content": content,
            "groupid": groupid,
            "atUser": 0
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_private_voice_msg(self, toUser: int, groupid, voiceUrl='', voiceBase64Buf='', timeout=5, **kwargs) -> dict:
        """发送私聊语音"""
        data = {
            "toUser": toUser,
            "sendToType": 3,
            "sendMsgType": "VoiceMsg",
            "content": "",
            "groupid": groupid,
            "atUser": 0,
            "voiceUrl": voiceUrl,
            "voiceBase64Buf": voiceBase64Buf
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_private_pic_msg(self, toUser, groupid, picUrl='', picBase64Buf='', content='',
                             fileMd5='', timeout=5, **kwargs) -> dict:
        """发送私聊图片"""
        data = {
            "toUser": toUser,
            "sendToType": 3,
            "sendMsgType": "PicMsg",
            "content": content,
            "groupid": groupid,
            "atUser": 0,
            "picUrl": picUrl,
            "picBase64Buf": picBase64Buf,
            "fileMd5": fileMd5
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_group_json_msg(self, toUser: int, content='', atUser=0, timeout=5, **kwargs) -> dict:
        """发送群Json类型信息
        :param content: 可以为json文本，或者字典类型
        """
        if isinstance(content, dict):
            content = json.dumps(content)
        data = {
            "toUser": toUser,
            "sendToType": 2,
            "sendMsgType": "JsonMsg",
            "content": content,
            "groupid": 0,
            "atUser": atUser
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def send_group_xml_msg(self, toUser: int, content='', atUser=0, timeout=5, **kwargs) -> dict:
        """发送群Xml类型信息"""
        data = {
            "toUser": toUser,
            "sendToType": 2,
            "sendMsgType": "XmlMsg",
            "content": content,
            "groupid": 0,
            "atUser": atUser
        }
        return self.baseSender('POST', 'SendMsg', data, timeout, **kwargs)

    def revoke_msg(self, groupid: int, msgseq: int, msgrandom: int, type_=1, timeout=5, **kwargs) -> dict:
        """撤回消息
        :param type_: 1: RevokeMsg | 2: PbMessageSvc.PbMsgWithDraw
        """
        funcname = 'RevokeMsg' if type_ == 1 else 'PbMessageSvc.PbMsgWithDraw'
        data = {"GroupID": groupid, "MsgSeq": msgseq, "MsgRandom": msgrandom}
        return self.baseSender('POST', funcname, data, timeout, **kwargs)

    def search_group(self, content, page=0, timeout=5, **kwargs) -> dict:
        """搜索群组"""
        return self.baseSender('POST', 'SearchGroup', {"Content": content, "Page": page}, timeout, **kwargs)

    def get_user_info(self, userID: int, timeout=5, **kwargs) -> dict:
        '''获取用户信息'''
        return self.baseSender('POST', 'GetUserInfo', {'UserID': userID, 'GroupID': 0}, timeout, **kwargs)

    def get_cookies(self, timeout=2, **kwargs) -> dict:
        """获取cookies"""
        return self.baseSender('GET', 'GetUserCook', timeout=timeout, **kwargs)

    def get_group_list(self, timeout=5, **kwargs) -> dict:
        """获取群组列表"""
        return self.baseSender('POST', 'GetGroupList', {"NextToken": ""}, timeout, **kwargs)

    def get_group_user_list(self, groupid: int, timeout=5, **kwargs) -> dict:
        """获取群成员列表"""
        data = self.baseSender('POST', 'GetGroupUserList', {"GroupUin": groupid, "LastUin": 0}, timeout, **kwargs)
        #Count = data['Count']
        #GroupUin = data['GroupUin']
        LastUin = data['LastUin']
        MemberList = data['MemberList']
        while LastUin != 0:
            time.sleep(1.1)
            data = self.baseSender('POST', 'GetGroupUserList', {"GroupUin": groupid, "LastUin": LastUin}, timeout, **kwargs)
            #Count += data['Count']
            #GroupUin = data['GroupUin']
            LastUin = data['LastUin']
            MemberList += data['MemberList']
        return MemberList

    def set_unique_title(self, groupid: int, userid: int, Title: str, timeout=1, **kwargs) -> dict:
        """设置群成员头衔"""
        return self.baseSender('POST', 'OidbSvc.0x8fc_2', {"GroupID": groupid, "UserID": userid, "NewTitle": Title}, timeout, **kwargs)

    def modify_group_card(self, userID: int, groupID: int, newNick: str, timeout=5, **kwargs) -> dict:
        '''修改群名片

        :params userID: 修改的QQ号
        :params groupID: 群号
        :params newNick: 新群名片

        '''
        data = {
            'UserID': userID,
            'GroupID': groupID,
            'NewNick': newNick
        }
        return self.baseSender('POST', 'ModifyGroupCard', data, timeout, **kwargs)

    def refresh_keys(self, timeout=20) -> bool:
        '''刷新key二次登陆, 成功返回True， 失败返回False'''
        try:
            rep = requests.get(f'{self.__host}:{self.__port}/v1/RefreshKeys?qq={self.qq}', timeout=timeout)
            if rep.json()['Ret'] == 'ok':
                return True
        except Exception:
            pass
        return False

    def add_friend(self, userID: int, groupID: int, content='加个好友!', AddFromSource=2004, timeout=20, **kwargs) -> dict:
        """添加好友"""
        data = {
            "AddUserUid": userID,
            "FromGroupID": groupID,
            "AddFromSource": AddFromSource,
            "Content": content
        }
        return self.baseSender('POST', 'AddQQUser', data, timeout, **kwargs)

    def deal_friend(self) -> dict:
        """处理好友请求"""
        # TODO

    def all_shut_up_on(self, groupid, timeout=20, **kwargs) -> dict:
        """开启全员禁言"""
        return self.baseSender('POST', 'OidbSvc.0x89a_0', {"GroupID": groupid, "Switch": 1}, timeout, **kwargs)

    def all_shut_up_off(self, groupid, timeout=20, **kwargs) -> dict:
        """关闭全员禁言"""
        return self.baseSender('POST', 'OidbSvc.0x89a_0', {"GroupID": groupid, "Switch": 0}, timeout, **kwargs)

    def you_shut_up(self, groupid, userid, shut_time=0, timeout=20, **kwargs) -> dict:
        """群成员禁言"""
        return self.baseSender('POST', '', {"GroupID": groupid, "ShutUpUserID": userid, "ShutTime": shut_time}, timeout, **kwargs)

    def baseSender(self,
                   method: str,
                   funcname: str,
                   data: dict = None,
                   timeout: int = None,
                   api_path: str = None,
                   iot_timeout: int = None,
                   bot_qq: int = None) -> dict:
        """
        :param method: 请求方法
        :param funcname: 请求类型
        :param data: post的数据
        :param timeout: 发送请求等待响应的时间
        :param api_path: 默认为/v1/LuaApiCaller
        :param iot_timeout: IOT端处理请求等待的时间
        :param bot_qq: 机器人QQ

        :return: iotbot端返回的json数据(字典)，如果返回内容非json则返回空字典
        """
        job = functools.partial(
            self._baseSender,
            method=method,
            funcname=funcname,
            data=data,
            timeout=timeout,
            api_path=api_path,
            iot_timeout=iot_timeout,
            bot_qq=bot_qq
        )
        functools.update_wrapper(job, self.baseSender)
        if self.__use_queue:
            self.__send_queue.put(job)
            # print('加入队列...')
            return None
        # print('不加入队列...')
        return job()

    def _baseSender(self,
                    method: str,
                    funcname: str,
                    data: dict = None,
                    timeout: int = None,
                    api_path: str = None,
                    iot_timeout: int = None,
                    bot_qq: int = None) -> dict:
        params = {
            'funcname': funcname,
            'timeout': iot_timeout or self.__timeout,
            'qq': bot_qq or self.qq
        }
        if data is None:
            data = {}
        try:
            rep = requests.request(
                method=method,
                url='{}:{}{}'.format(self.__host, self.__port, api_path or self.__api_path),
                headers={'Content-Type': 'application/json'},
                params=params,
                json=data,
                timeout=timeout or self.__timeout
            )
            rep.raise_for_status()
            response = rep.json()
            if 'Ret' in response:
                if not response['Ret'] == 0:
                    if response['Ret'] == 241:
                        self.logger.error(f'请求频繁: {response}')
                    else:
                        self.logger.error(f'请求发送成功, 但处理失败: {response}')
            return response
        except Exception as e:
            if isinstance(e, Timeout):
                self.logger.warning('响应超时，但不代表处理未成功, 结果未知!')
                return {}
            self.logger.error(f'出现错误: {e}')
            return {}
