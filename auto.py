# -*- coding: utf-8 -*-
import datetime
import getpass
import os
import time

import json
import re
import requests
import urllib3
import argparse
from apscheduler.schedulers.blocking import BlockingScheduler
from halo import Halo

import random
import base64
import urllib.parse
from bs4 import BeautifulSoup
from Cryptodome.Cipher import AES
from Cryptodome.Util import Padding

class DaKa(object):
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.base_url = "https://wxxy.csu.edu.cn/ncov/wap/default/index"
        self.save_url = "https://wxxy.csu.edu.cn/ncov/wap/default/save"
        self.info = None
        self.sess = requests.Session()
    
    def randomString(length):
        '''
        获取随机字符串
        :param length:随机字符串长度
        '''
        ret_string = ''
        aes_chars = 'ABCDEFGHJKMNPQRSTWXYZabcdefhijkmnprstwxyz2345678'
        for i in range(length):
            ret_string += random.choice(aes_chars)
        return ret_string
    
    def getAesString(data, key, iv):
        '''
        用AES-CBC方式加密字符串
        :param data: 需要加密的字符串
        :param key: 密钥
        :param iv: 偏移量
        :return: base64格式的加密字符串
        '''
        # 预处理字符串
        data = str.encode(data)
        data = Padding.pad(data, AES.block_size)

        # 预处理密钥和偏移量
        key = str.encode(key)
        iv = str.encode(iv)

        # 初始化加密器
        cipher = AES.new(key, AES.MODE_CBC, iv)
        cipher_text = cipher.encrypt(data)

        # 返回的是base64格式的密文
        cipher_b64 = str(base64.b64encode(cipher_text), encoding='utf-8')
        return cipher_b64

    def login(self):
        '''
        做任何操作前都要先登录以获得cookie
        '''
        url1 = self.base_url
        response1 = self.sess.get(url1)

        soup = BeautifulSoup(response1.text, 'html.parser')
        salt = soup.find('input', id="pwdEncryptSalt")['value']
        execution = soup.find('input', id="execution")['value']

        url2 = urllib.parse.unquote(response1.url)
        data2 = {
            'username': self.username,
            'password': self.getAesString(self.randomString(64)+self.password, salt, self.randomString(16)),
            'captcha': '',
            '_eventId': 'submit',
            'cllt': 'userNameLogin',
            'dllt': 'generalLogin',
            'lt': '',
            'execution': execution
        }
        response2 = self.sess.post(url2, data=data2)

    def get_info(self, html=None):
        """Get hitcard info, which is the old info with updated new time."""
        if not html:
            urllib3.disable_warnings()
            res = self.sess.get(self.base_url, headers=self.header, verify=False)
            html = res.content.decode()

        jsontext = re.findall(r'def = {[\s\S]*?};', html)[0]
        jsontext = eval(jsontext[jsontext.find("{"):jsontext.rfind(";")].replace(" ", ""))

        geo_text = jsontext['geo_api_info']
        geo_text = geo_text.replace("false", "False").replace("true", "True")
        geo_obj = eval(geo_text)['addressComponent']
        area = geo_obj['province'] + " " + geo_obj['city'] + " " + geo_obj['district']
        name = re.findall(r'realname: "([^\"]+)",', html)[0]
        number = re.findall(r"number: '([^\']+)',", html)[0]

        new_info = jsontext.copy()
        new_info['name'] = name
        new_info['number'] = number
        new_info['area'] = area
        new_info["date"] = self.get_date()
        new_info["created"] = round(time.time())
        self.info = new_info
        return new_info

    def get_date(self):
        today = datetime.date.today()
        return "%4d%02d%02d" % (today.year, today.month, today.day)

    def post(self):
        """Post the hitcard info"""
        res = self.sess.post(self.save_url, data=self.info)
        return json.loads(res.text)


def main(username, password):
    print("\n[Time] %s" % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("🚌 打卡任务启动")
    spinner = Halo(text='Loading', spinner='dots')
    spinner.start('正在新建打卡实例...')
    dk = DaKa(username, password)
    spinner.succeed('已新建打卡实例')

    spinner.start(text='登录到中南大学信息门户...')
    dk.login()
    spinner.succeed('已登录到中南大学信息门户')

    spinner.start(text='正在获取个人信息...')
    dk.get_info()
    spinner.succeed('%s %s同学, 你好~' % (dk.info['number'], dk.info['name']))

    spinner.start(text='正在为您打卡打卡打卡')
    res = dk.post()
    if str(res['e']) == '0':
        spinner.stop_and_persist(symbol='🦄 '.encode('utf-8'), text='已为您打卡成功！')
    else:
        spinner.stop_and_persist(symbol='🦄 '.encode('utf-8'), text=res['m'])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='manual to this script')
    parser.add_argument('--username', type=str, default=None)
    parser.add_argument('--password', type=str, default=None)
    args = parser.parse_args()
    main(args.username, args.password)
