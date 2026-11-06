import http_client as requests
import random
import time
import re
import rsa
import base64
from urllib.parse import parse_qs, urlsplit, quote
from upstream.log import Log

log = Log()

class gtfed():
    """好游快爆签到
    """
    url = 'https://huodong3.3839.com/n/hykb/cornfarm/ajax_sign.php'
    def __init__(self,SignToken) -> None:
        self.gtfed = SignToken['gtfed']['cookie']
        self.head = {
            "User-Agent":"Mozilla/5.0 (Linux; Android 7.0; Meizu S6 Build/NRD90M; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/65.0.3325.110 Mobile Safari/537.36Androidkb/1.5.5.305(android;Meizu S6;7.0;720x1374;4G);@4399_sykb_android_activity@",
            "Origin":"https://huodong3.3839.com",
            "X-Requested-With":"XMLHttpRequest",
            "Content-Type":"application/x-www-form-urlencoded; charset=UTF-8",
            "Referer":"https://huodong3.3839.com/n/hykb/cornfarm/index.php",
	    }

    def Sign(self):
        if self.gtfed != "":
            zz = requests.post(url=self.url,data=self.gtfed,headers=self.head).json()
            key = str(zz.get('key', ''))
            if key in ('ok', '1001'):
                return "好游快爆:签到成功"
            if key == '1002':
                return "好游快爆:尚未播种，请先在 App 中播种"
            if key == '1003':
                return "好游快爆:玉米进度已满，请在 App 中收割"
            return "好游快爆:" + str(zz.get('info') or zz.get('tip') or "登录失效或需要在 App 中完成验证")
        else:
            log.info("好游快爆:没有配置cookie")
            return "好游快爆:没有配置cookie"

#MIUI 历史版本签到
class Miui():
    """MIUI 历史版本签到
    """
    LoginUrl = "https://miuiver.com/wp-content/plugins/erphplogin//action/login.php"
    SignUrl = "https://miuiver.com/wp-admin/admin-ajax.php"
    def __init__(self,SignToken) -> None:
        self.switch = SignToken['MiUI']['switch']
        self.user = SignToken['MiUI']['user']
        self.password = SignToken['MiUI']['password']
        self.head = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept': 'application/json, text/javascript, */*; q=0.01'
        }
    #登录
    def Login(self):
        datas = {
            'log':self.user,
            'pwd':self.password,
            'action': 'mobantu_login'
        }
        response = requests.post(url=self.LoginUrl,data=datas,headers=self.head)
        if response.text == '1':
            log.info("MIUI历史版本:登录成功")
            cookies = response.cookies
            return cookies
        else:
            log.info("MIUI历史版本:登录失败,账号或密码错误")
    #签到
    def Sign(self):
        datas = {
            'action': 'epd_checkin'
        }
        if self.user != "" and self.password != "":
            cookies = self.Login()
            if cookies == None:
                pass
            else:
                response = requests.post(url=self.SignUrl,data=datas,headers=self.head,cookies=cookies).json()
                if response['status'] == 200:
                    log.info("MIUI历史版本:" + "签到成功积分+1")
                    return "MIUI历史版本:" + "签到成功积分+1"
                else:
                    log.info("MIUI历史版本:" + response["msg"])
                    return "MIUI历史版本:" + response["msg"]
        else:
            log.info("MIUI历史版本:账号或密码为空")
            return "MIUI历史版本:账号或密码为空"

# 小黑盒签到
class XiaoHeiHe():
    def __init__(self,SignToken) -> None:
        self.Xiaoheihe = SignToken['XiaoHeiHe']['cookie']
        self.imei = SignToken['XiaoHeiHe']['imei']
        self.n = self.get_nonce_str()
        self.t = int(time.time())
        self.u = "/task/sign"

    def get_nonce_str(self,length: int = 32) -> str:
            """
            生成随机字符串

            参数:
                length: 密钥参数
            返回:
                str: 随机字符串
            """
            source = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
            result = "".join(random.choice(source) for _ in range(length))
            return(result)

    # 感谢 https://github.com/chr233 的hkey算法接口
    def hkey(self):
        url = "http://146.56.234.178:8077/encode"
        params={"urlpath": self.u, "nonce": self.n, "timestamp": self.t}
        zz = requests.get(url,params=params).text
        return zz

    def Sgin(self):
        if self.Xiaoheihe != "":
            try:
                url = "https://api.xiaoheihe.cn/task/sign/"
                p = {
                    "_time":self.t,
                    "hkey":self.hkey(),
                    "nonce":self.n,
                    "imei":self.imei,
                    "heybox_id":"15083711",
                    "version":"1.3.221",
                    "divice_info":"M2012K11AC",
                    "x_app":"heybox",
                    "channel":"heybox_xiaomi",
                    "os_version":"12",
                    "os_type":"Android"
                }
                head = {
                    "User-Agent":"Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.118 Safari/537.36 ApiMaxJia/1.0",
                    "cookie":self.Xiaoheihe,
                    "Referer":"http://api.maxjia.com/"
                }
                req = requests.get(url=url,params=p,headers=head).json()
                if req['status'] == "ok":
                    if req['msg'] == "":
                        log.info("小黑盒:已经签到过了")
                        return "小黑盒:已经签到过了"
                    else:
                        log.info(f"小黑盒:{req['msg']}")
                        return f"小黑盒:{req['msg']}"
                else:
                    log.info(f"小黑盒:签到失败 - {req['msg']}")
                    return f"小黑盒:签到失败 - {req['msg']}"
            except Exception as e:
                log.info(f"小黑盒:出现了错误,错误信息{e}")
        else:
            log.info("小黑盒:没有配置cookie")
            return "小黑盒:没有配置cookie"

# 交易猫签到
class JiaoYiMao():
    def __init__(self,SignToken) -> None:
        self.jiaoyimao = SignToken['JiaoYiMao']['cookie']
        self.url = "https://m.jiaoyimao.com/api2/account/integration/getMyIntegration"
        self.sginurl = "https://m.jiaoyimao.com/api2/account/integration/signin"

    def Sgin(self):
        if self.jiaoyimao != "":
            head = {
                "user-agent":"jym_mobile (Linux; U; Android12; zh_CN; M2012K11AC; Build/SKQ1.220213.001; fca7d8fc-03b5-4fea-97e6-94173844b374; 1080x2400) com.jym.mall/206/JYN_548/7.0.2 AliApp(JYM/7.0.2) UT4Aplus/0.2.29; density/2.7; app_id/23072786;  WindVane/8.5.0; utdid/YH2ygxDifiEDAA6wMV75K10e; umid_token/7+9LGztLOiq8MTWA+l8fZZQW+RjvBE56; oaid/9933af2363237087;",
                "referer":"https://m.jiaoyimao.com/account/integration/center?spm=gcmall.home2022.topshortcut.0",
                "x-csrf-token": next((part.strip().split("=", 1)[1] for part in self.jiaoyimao.split(";") if part.strip().startswith("_csrfToken=")), ""),
                "x-requested-with":"com.jym.mall",
                "cookie":self.jiaoyimao
            }
            zz = requests.get(url=self.sginurl,headers=head).json()
            if zz['success']:
                rep = requests.get(self.url,headers=head).json()
                if rep['stateCode'] == 200:
                    Integral = rep['data']['amountLeft']
                else:
                    Integral = "获取积分失败"
                data = f"交易猫:签到成功 - 现有积分{Integral}"
                log.info(data)
                return data
            else:
                data = f"交易猫:签到失败 - {zz['extraErrMsg']}"
                log.info(data)
                return data
        else:
            log.info("交易猫:没有配置cookie")
            return "交易猫:没有配置cookie"

# 天翼云盘
# 使用了开源项目https://github.com/xtyuns/cloud189app-action
class TYYP():
    def __init__(self,SignToken) -> None:
        self.username = SignToken['tyyp']['username']
        self.password = SignToken['tyyp']['password']

    def Login(self, session, username, password):
        """Current Cloud189 web login protocol; stop if verification is required."""
        entry = session.get(
            "https://cloud.189.cn/api/portal/loginUrl.action",
            params={"redirectURL": "https://cloud.189.cn/web/redirect.html"},
        )
        query = parse_qs(urlsplit(entry.url).query)
        if not all(query.get(key) for key in ('appId', 'lt', 'reqId')):
            return None
        headers = {
            'User-Agent': 'Mozilla/5.0', 'Referer': entry.url,
            'lt': query['lt'][0], 'reqId': query['reqId'][0],
        }
        base = "https://open.e.189.cn"
        app = session.post(
            base + '/api/logbox/oauth2/appConf.do',
            headers=headers, data={'version': '2.0', 'appKey': query['appId'][0]},
        ).json()
        encryption = session.post(
            base + '/api/logbox/config/encryptConf.do',
            headers=headers, data={'appId': query['appId'][0]},
        ).json()
        if str(app.get('result')) != '0' or str(encryption.get('result')) != '0':
            return None
        conf = app['data']
        key = encryption['data']['pubKey']
        if 'BEGIN PUBLIC KEY' not in key:
            key = '-----BEGIN PUBLIC KEY-----\n' + key + '\n-----END PUBLIC KEY-----'
        public_key = rsa.PublicKey.load_pkcs1_openssl_pem(key.encode())
        prefix = encryption['data'].get('pre', '{RSA}')
        def encrypt(value):
            return prefix + base64.b64encode(rsa.encrypt(value.encode(), public_key)).decode()
        payload = {
            field: conf.get(field, '') for field in
            ('appKey', 'pageKey', 'accountType', 'mailSuffix', 'clientType', 'isOauth2', 'state', 'paramId')
        }
        payload.update({
            'version': 'v2.0', 'userName': encrypt(username), 'epd': encrypt(password),
            'returnUrl': quote(conf['returnUrl'], safe=''), 'dynamicCheck': 'FALSE',
            'captchaType': '', 'validateCode': '', 'smsValidateCode': '',
            'captchaToken': '', 'apToken': '', 'cb_SaveName': '0',
        })
        result = session.post(base + '/api/logbox/oauth2/loginSubmit.do', headers=headers, data=payload).json()
        if str(result.get('result')) != '0' or not result.get('toUrl'):
            return None
        target = urlsplit(result['toUrl'])
        if target.scheme != 'https' or not target.hostname or not (
            target.hostname == '189.cn' or target.hostname.endswith('.189.cn')
        ):
            return None
        session.get(result['toUrl'])
        return session

    def Sgin(self):
        if not self.username or not self.password:
            return "天翼云盘:账号或密码不能为空"
        with requests.Session() as session:
            if self.Login(session, self.username, self.password) is None:
                return "天翼云盘:登录失败、凭据失效或需要在官网登录完成验证"
            headers = {'User-Agent': 'Mozilla/5.0 Ecloud/8.6.3', 'Referer': 'https://m.cloud.189.cn/'}
            data = session.get(
                'https://api.cloud.189.cn/mkt/userSign.action', headers=headers,
                params={'rand': str(round(time.time() * 1000)), 'clientType': 'TELEANDROID',
                        'version': '8.6.3', 'model': 'SM-G930K'},
            ).json()
            if 'netdiskBonus' not in data or 'isSign' not in data:
                return "天翼云盘:签到失败，登录状态或平台接口已变化"
            if data['isSign'] in (False, 'false'):
                message = f"天翼云盘:签到成功，获得 {data['netdiskBonus']}M 空间"
            else:
                message = f"天翼云盘:已经签到过了，获得 {data['netdiskBonus']}M 空间"
            for task in ('TASK_SIGNIN', 'TASK_SIGNIN_PHOTOS'):
                try:
                    prize = session.get(
                        'https://m.cloud.189.cn/v2/drawPrizeMarketDetails.action', headers=headers,
                        params={'taskId': task, 'activityId': 'ACT_SIGNIN'},
                    ).json()
                    detail = str(prize['prizeName']) if 'prizeName' in prize else '没有抽奖次数或接口未接受请求'
                except Exception:
                    detail = '抽奖请求失败，签到结果不受影响'
                message += '\n天翼云盘:' + task + ' - ' + detail
            return message

# 网易云游戏签到
class wyyyx():
    def __init__(self,SignToken) -> None:
        self.wyyyx_cookie = SignToken['wyyyx']['cookie']

    def Sgin(self):
        url='https://n.cg.163.com/api/v2/sign-today'
        header={
            'Accept': 'application/json, text/plain, */*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7,ja-JP;q=0.6,ja;q=0.5',
            'Authorization': self.wyyyx_cookie,
            'Connection': 'keep-alive',
            'Content-Length': '0',
            'Host': 'n.cg.163.com',
            'Origin': 'https://cg.163.com',
            'Referer': 'https://cg.163.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
            'X-Platform': '0'
        }
        res = requests.post(url=url,headers=header).status_code
        if res == 200:
            log.info("网易云游戏:签到成功")
            return "网易云游戏:签到成功"
        else:
            log.info("网易云游戏:签到失败或已签到")
            return "网易云游戏:签到失败或已签到"
