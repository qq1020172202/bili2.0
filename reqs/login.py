import base64
import requests
import utils
from json_rsp_ctrl import Ctrl, JsonRspType, In


# 为 login 的相关请求专门设计，在登陆中返回"JsonRspType.LOGOUT"不管的。
# 其余和 BASE_CTRL 一样就行
LOGIN_CTRL = Ctrl(
    extend=(
        {'code': 0}, JsonRspType.OK,  # 目前为止，0 肯定成功，如果例外，自己另写

        {'code': 1024}, JsonRspType.IGNORE,
        {'msg': In('操作太快')}, JsonRspType.IGNORE,
        {'msg': In('系统繁忙')}, JsonRspType.IGNORE,
        {'msg': In('过于频繁')}, JsonRspType.IGNORE,
        {'message': In('服务繁忙')}, JsonRspType.IGNORE,
    ),
    base=None,
    default=JsonRspType.OK
)


class LoginReq:
    @staticmethod
    async def logout(user):
        url = 'https://passport.bilibili.com/login?act=exit'
        json_rsp = await user.login_session.request_json('GET', url, headers=user.pc.headers, ctrl=LOGIN_CTRL)
        return json_rsp

    @staticmethod
    async def fetch_key(user):
        url = 'https://passport.bilibili.com/api/oauth2/getKey'
        params = user.app_sign()
        json_rsp = await user.login_session.request_json('POST', url, params=params, ctrl=LOGIN_CTRL)
        return json_rsp
        
    @staticmethod
    async def fetch_key_tv(user):
        url = 'https://passport.snm0516.aisee.tv/api/oauth2/getKey'
        temp_params = f'appkey={user.dict_bilitv["appkey"]}'
        sign = user.calc_sign_tv(temp_params)
        params = {'appkey': user.dict_bilitv['appkey'], 'sign': sign}
        json_rsp = await user.login_session.request_json('POST', url, data=params)
        return json_rsp

    @staticmethod
    async def fetch_capcha(user):
        url = "https://passport.bilibili.com/captcha"
        binary_rsp = await user.login_session.request_binary('GET', url)
        return binary_rsp
    
    @staticmethod
    async def fetch_capcha_tv(user):
        headers = {
            'Accept': 'application/json, text/plain, */*',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36',
            'Host': 'passport.snm0516.aisee.tv',
            'cookie': "sid=hxt5szbb"
        }
        url = "https://passport.snm0516.aisee.tv/api/captcha?token=5598158bcd8511e2"
        binary_rsp = await user.login_session.request_binary('GET', url,headers=headers)
        return binary_rsp

    @staticmethod
    async def login_tv(user, url_name, url_password, captcha=''):
        temp_params = f"appkey={user.dict_bilitv['appkey']}&build={user.dict_bilitv['build']}&captcha={captcha}&channel=master&guid=XYEBAA3E54D502E37BD606F0589A356902FCF&mobi_app=android_tv_yst&password={url_password}&platform=android&token=5598158bcd8511e2&ts=0&username={url_name}"
        sign = user.calc_sign_tv(temp_params)
        payload = f'{temp_params}&sign={sign}'
        url = "https://passport.snm0516.aisee.tv/api/tv/login"
        json_rsp = await user.login_session.request_json('POST', url, params=payload)
        return json_rsp
        
    @staticmethod
    async def login(user, url_name, url_password, captcha=''):
        validate = ''
        challenge = ''
        extra_params = {
            'seccode': f'{validate}|jordan' if validate else '',
            'validate': validate,
            'challenge': challenge,
            'username': url_name,
            'password': url_password,
            'ts': utils.curr_time(),
        }
        params = user.app_sign(extra_params)

        # url_password 存在一些 % 这些，b站要求作为 string 不编码为 "%25"
        # aiohttp doc 符合，但是
        # https://github.com/aio-libs/aiohttp/blob/10c8ce9567d008d4f92a99ffe45f8d0878e99275/aiohttp/client_reqrep.py#L215-L219
        # yarl 兼容问题
        # 故手动处理
        params_str = utils.prepare_params(params)
        url_aiohttp = f'https://passport.bilibili.com/x/passport-login/oauth2/login?{params_str}'
        json_rsp = await user.login_session.request_json('POST', url_aiohttp, headers=user.app.headers, params=None, ctrl=LOGIN_CTRL)
        return json_rsp
    @staticmethod
    async def access_token_2_cookies(user,access_token):
        temp_params = f"access_key={access_token}&appkey={user.dict_bilitv['appkey']}&gourl=https%3A%2F%2Faccount.bilibili.com%2Faccount%2Fhome"
        sign = user.calc_sign_tv(temp_params)
        payload = f'{temp_params}&sign={sign}'
        url = f"https://passport.bilibili.com/api/login/sso?{payload}"
        response = requests.get(url, allow_redirects=False)
        return response.cookies.get_dict(domain=".bilibili.com")
    @staticmethod
    async def is_token_usable(user):
        dict_cookie = dict()
        for param in user.dict_user['cookie'].split(';'):
            key, value = param.split('=')
            dict_cookie[key] = value

        extra_params = {
            'access_key': user.dict_user['access_key'],
            'access_token': user.dict_user['access_key'],
            'ts': utils.curr_time(),
            ** dict_cookie
        }
        params = user.app_sign(extra_params)
        # 这里没办法，cookie 里面有特殊字符，与 yarl 兼容无关
        params_str = utils.prepare_params(params)
        true_url = f'https://passport.bilibili.com/api/v3/oauth2/info?{params_str}'
        json_rsp = await user.login_session.request_json('GET', true_url, params=None, headers=user.app.headers, ctrl=LOGIN_CTRL)
        return json_rsp

    @staticmethod
    async def refresh_token(user):
        dict_cookie = dict()
        for param in user.dict_user['cookie'].split(';'):
            key, value = param.split('=')
            dict_cookie[key] = value

        extra_params = {
            'access_key': user.dict_user['access_key'],
            'access_token': user.dict_user['access_key'],
            'refresh_token': user.dict_user['refresh_token'],
            'ts': utils.curr_time(),
            ** dict_cookie
        }
        params = user.app_sign(extra_params)
        # 这里没办法，cookie 里面有特殊字符，与 yarl 兼容无关
        params_str = utils.prepare_params(params)
        url = f'https://passport.bilibili.com/api/v2/oauth2/refresh_token?{params_str}'
        json_rsp = await user.login_session.request_json('POST', url, headers=user.app.headers, params=None, ctrl=LOGIN_CTRL)
        print('json_rsp', json_rsp)
        return json_rsp
        
    @staticmethod
    async def cnn_captcha(user, content):
        url = "http://152.32.186.69:19951/captcha/v1"
        str_img = base64.b64encode(content).decode(encoding='utf-8')
        json_rsp = await user.other_session.orig_req_json('POST', url, json={"image": str_img})
        captcha = json_rsp['message']
        print(f"此次登录出现验证码,识别结果为{captcha}")
        return captcha