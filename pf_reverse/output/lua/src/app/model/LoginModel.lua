---@class LoginModel
local P = class("LoginModel", BaseModel)

function P:ctor()
    self.saveData = {
        cloud = {
            __regTime = 0,
        }
    }

    self._serverTime = os.time()
    self._serverTimeSt = self._serverTime

    P.super.ctor(self)

    self.login_type = nil
    self._heartbeat = 0

    self:initStove()
end

function P:doLogin(params)
    params.os = bee.pfsys
    if not params.imei then
        params.imei = SdkHelper:getDeviceID()
    end
    params.lang = LanguageManager:getLanguage()
    params.adjust_id = SdkModel:getAdjustCache()
    Net:post("login", self:addLoginArgs(params), function (data) self:_onLoginSuccess(data, params) end, function() self:_onLoginFail() end)
end

function P:addLoginArgs(args)
    args.lang = LAN:getLanguage()
    args.adjust_id = SdkModel:getAdjustCache()
    args.mask = "LoginHttp"
    return args
end

-- 自定义设备号登录
function P:guestLoginTest(id)
    self.login_type = LOGIN_TYPE.GUEST
    local args = {
        type = LOGIN_TYPE.GUEST,
        token = id,
        os = bee.pfsys,
        imei = id,
        lang = LanguageManager:getLanguage(),
    }
    args.verify = self:getCheckMd5(args.os .. args.imei)

    local _onSuccess = function (data)
        self:_onLoginSuccess(data, args)
    end

    Net:post("login", self:addLoginArgs(args), _onSuccess)
end

-- 游客登录
function P:guestLogin()
    self.login_type = LOGIN_TYPE.GUEST
    local args = {
        type = LOGIN_TYPE.GUEST,
        token = SdkHelper:getDeviceID(),
        os = bee.pfsys,
        imei = SdkHelper:getDeviceID(),
        lang = LanguageManager:getLanguage(),
    }
    args.verify = self:getCheckMd5(args.os .. args.imei)

    local _onSuccess = function (data)
        self:_onLoginSuccess(data, args)
    end

    Net:post("login", self:addLoginArgs(args), _onSuccess, function() self:_onLoginFail() end)
end

-- 邮箱登录
function P:emailLogin(email, password, cb)
    self.login_type = LOGIN_TYPE.EMAIL
    local args = {
        type = LOGIN_TYPE.EMAIL,
        token = email,
        os = bee.pfsys,
        imei = SdkHelper:getDeviceID(),
        lang = LanguageManager:getLanguage(),
        verify = password,
    }

    local _onSuccess = function (data)
        if data.code == 0 then
            PlayerModel:setLoginEmail(email)
            PlayerModel:setLoginPw(password)
        end
        self:_onLoginSuccess(data, args)
        if cb then
            cb(data)
        end
    end

    Net:post("login", self:addLoginArgs(args), _onSuccess, function() self:_onLoginFail() end, cb ~= nil)
end

-- 获取邮箱验证码
function P:catchEmailCaptcha(email, cb, kind, noTipError)
    local args = {
        type = kind or 1,
        email = email,
        lang = LanguageManager:getLanguage(),
    }
    local _onSuccess = function (data)
        if cb then
            cb(data)
        end
    end

    Net:post("captcha", self:addLoginArgs(args), _onSuccess, function() end, noTipError)
end

-- 邮箱验证/注册
function P:emailRegister(email, captcha, password, step, cb, noTipError)
    local args = {
        email = email,
        captcha = captcha,
        password = password or "",
        step = step,
        os = bee.pfsys,
        imei = SdkHelper:getDeviceID(),
        adjust_id = SdkModel:getAdjustCache(),
    }

    local _onSuccess = function (data)
        if data.code == 0 and step == EMAIL_REGISTER_STEP.PASSWORD then
            PlayerModel:setLoginEmail(email)
            PlayerModel:setLoginPw(password)
        end

        if cb then
            cb(data)
        end
    end

    Net:post("register/email", self:addLoginArgs(args), _onSuccess, nil, noTipError) 
end

function P:initStove()
    self._isBinding = nil
    if G_CHNL_ID == 5 then
        CS.StoveMobileHelper.InitProviders("Guest,Email,Facebook,Google,Line")
    elseif G_CHNL_ID == 6 then
        CS.StoveMobileHelper.InitProviders("Guest,Email,Facebook,Apple,Google,Line")
    end
end

function P:loginStove()
    self:initStove()
    CS.ThirdManager.Instance:login()
end

function P:bindStove()
    self._isBinding = true
    if G_CHNL_ID == 5 then
        CS.StoveMobileHelper.InitProviders("Email,Facebook,Google,Line")
    elseif G_CHNL_ID == 6 then
        CS.StoveMobileHelper.InitProviders("Email,Facebook,Apple,Google,Line")
    end
    CS.ThirdManager.Instance:login()
end

-- 推特登录
function P:XLogin()
    self.login_type = LOGIN_TYPE.TWITTER
    local token = PlayerModel:getXToken()
    local secret = PlayerModel:getXSecret()

    if not token or not secret then
        -- 授权
        Net:post("xOauth", nil, function(data)
            if data.code == 0 then
                CU.Application.OpenURL(data.url)
            end
        end)
    else
        local args = {
            type = LOGIN_TYPE.TWITTER,
            token = token,
            verify = secret,
        }

        local _onSuccess = function(data)
            self:_onLoginSuccess(data, args)
        end

        Net:post("login", self:addLoginArgs(args), _onSuccess, function() self:_onLoginFail() end)
    end
end

function P:evt_XLogin(params)
    if not params then
        return
    end

    local args = {
        type = LOGIN_TYPE.TWITTER,
        token = params.token,
        verify = params.verifier,
    }

    local _onSuccess = function (data)
        self:_onLoginSuccess(data, args)

        if data.code == 0 then
            PlayerModel:setXToken(data.x_token)
            PlayerModel:setXSecret(data.x_secret)
        end
    end

    Net:post("login", self:addLoginArgs(args), _onSuccess, function() self:_onLoginFail() end)
end

function P:_onLoginSuccess(data, params)
    PlayerModel:clearDatas()
    if data.code and data.code < 0 then
        UiManager:hideLoadingMask("Login")
        bee.emit(EventDef.evt_login_fail)
        
        if self.login_type == LOGIN_TYPE.GUEST then
            bee.logEvent("login-guest-failure", data.code)
        elseif self.login_type == LOGIN_TYPE.EMAIL then
            bee.logEvent("login-email-failure", data.code)
        elseif self.login_type == LOGIN_TYPE.FACEBOOK then
            bee.logEvent("login-fb-failure", data.code)
        elseif self.login_type == LOGIN_TYPE.TWITTER then
            bee.logEvent("login-x-failure", data.code)
        elseif self.login_type == LOGIN_TYPE.iOS then
            bee.logEvent("login-apple-failure", data.code)
        elseif self.login_type == LOGIN_TYPE.STOVE then
            bee.logEvent("login-stove-failure", data.code)
        elseif self.login_type == LOGIN_TYPE.STOVE_PC then
            bee.logEvent("login-stove-failure", data.code)
        end
        return
    end
    
    PlayerModel:setUid(data.uid)
    PlayerModel:setLoginType(params.type)
    PlayerModel:setAutoLogin(true)
    PlayerModel:setRdkey(data.rdkey)
    PlayerModel:setAuthorization(data.authorization)
    PlayerModel:setBindEmail(data.bind_email)
    PlayerModel:setRegChnl(data.reg_chnl)
    PlayerModel:setIsWhite(data.update_white)
    PlayerModel:setIsEventWhite(data.event_white)
    PlayerModel:setLoginRegion(data.login_region)
    PlayerModel:setIsDeleted(data.is_del)
    PlayerModel:setIsCanPay(data.able_pay)
    PlayerModel:setIP(data.login_ip)
    PlayerModel:setIsGuest(data.is_guest)
    PlayerModel:setStoveGUID(data.stove_guid)
    PlayerModel:onSave()

    UrlManager:setHosts(data.server.server)

    if PlayerModel:isDeleted() then
        UiManager:hideLoadingMask("Login")
        UiManager:showTip({
            text = _T("LAB_SETTINGS_117"),
            style = "big",
            sureStr = _T("LAB_SETTINGS_118"),
            cancelStr = _T("LAB_SETTINGS_030"),
            onSure = function()
                Net:post("player/cancelDeleteAccount", {
                    t = 1,
                    token = SdkHelper:getToken(),
                }, function(data)
                    UiManager:showToast(_T("LAB_SETTINGS_109"))
                    PlayerModel:setIsDeleted(false)
                    self:reConnect()
                end)
            end,
            onCancel = function()
                Game:quit()
            end
        })
        return
    end

    if PlayerModel:isWhite() then
        GF.startCheckUpdate(true, function()
            self:reConnect()
        end)
        bee.emit("evt_start_white_update")
        UiManager:hideLoadingMask("Login")
    else
        self:reConnect()
    end
    
    if self.login_type == LOGIN_TYPE.GUEST then
        bee.logEvent("login-guest-success")
    elseif self.login_type == LOGIN_TYPE.EMAIL then
        bee.logEvent("login-email-success")
    elseif self.login_type == LOGIN_TYPE.FACEBOOK then
        bee.logEvent("login-fb-success")
    elseif self.login_type == LOGIN_TYPE.TWITTER then
        bee.logEvent("login-x-success")
    elseif self.login_type == LOGIN_TYPE.iOS then
        bee.logEvent("login-apple-success")
    elseif self.login_type == LOGIN_TYPE.STOVE then
        bee.logEvent("login-stove-success")
    elseif self.login_type == LOGIN_TYPE.STOVE_PC then
        bee.logEvent("login-stove-success")
    end

    if data.is_reg then
        -- SdkHelper:sendFbEvent("sign_up")
        SdkHelper:sendFbEvent("fb_mobile_complete_registration")
        SdkHelper:sentAdjustEvent("ritfm3")
        SdkHelper:sendFirebaseEvent("sign_up")
    end
    SdkHelper:sentAdjustEvent("2v0xq5")
    SdkHelper:sendFirebaseEvent("login")
end

function P:_onLoginFail()
    UiManager:hideLoadingMask("Login")
    bee.emit(EventDef.evt_login_fail)
end

function P:reConnectWithCheck(cb, tip)
    if not self._reConnectSt then
        self._reConnectSt = os.time()
    end
    if os.time() - self._reConnectSt >= 15 then
        UiManager:hideLoadingMask("Connect")
        self._stopAutoReConnect = true
        UiManager:showTip({
            text = _T("LAB_NET_ERR_TIPS1"),
            noClose = true,
            sureStr = _T("LAB_NET_LINK_AGAIN"),
            onSure = function()
                self._reConnectSt = nil
                self._stopAutoReConnect = nil
                if not Net:isConnected() then
                    self:checkLoginValid(function()
                        self:reConnectWithCheck(cb, _T("LAB_NET_LINK_ING"))
                    end)
                end
            end,
            onCancel = function()
                self._stopAutoReConnect = nil
                PlayerModel:setIsLogin(false)
                PlayerModel:setNotAutoLogin(true)
                ItemModel:clearItems()
                Net:closeSocket()
                bee.enterScene("StartScene")
            end,
        })
        return
    end
    UiManager:showLoadingMask("Connect", tip or _T("LAB_NET_ERR_TIPS"))
    Net:post("open/checkServer", {t=1, immediately = true}, function(data)
        if data and data.code == 0 then
            if not data.data then
                self:reConnect(cb)
            elseif data.data.status == 1 then   -- 设置了停服
                UiManager:hideLoadingMask("Connect")
                local ct = bee.getServerTime()
                if ct >= data.data.start_time then
                    PlayerModel:setIsLogin(false)
                    PlayerModel:setNotAutoLogin(true)
                    ItemModel:clearItems()
                    Net:closeSocket()
                    if not bee.isInStart() then
                        bee.enterScene("StartScene")
                    end
                elseif ct >= data.data.show_time then
                    GF.showServerMaintain(data.data, function()
                        self:reConnect(cb)
                    end)
                else
                    self:reConnect(cb)
                end
            else
                self:reConnect(cb)
            end
        else
            self:reConnect(cb)
        end
    end)
end

--连接网络
function P:reConnect(cb)
    if self._connectRet and Net:isConnected() then
        self._reConnectSt = nil
        self._stopAutoReConnect = nil
        if cb then
            cb(self._connectRet)
        else
            Net:sendReq("pb.UserLoginREQ", {
                uid = PlayerModel:getUid(),
                key = PlayerModel:getRdkey(),
                ver = G_UPDATE_VERSION,
                chnl = G_CHNL_ID,
            })
        end
        return
    end
    self._connectRet = false
    UiManager:showLoadingMask("Connect")
    if bee.isEditor then
        print("[LoginMode] 连接到服务器...", self:getServerUrl())
    end
    Net:connect(self:getServerUrl(), function(ret)
        UiManager:hideLoadingMask("Connect")
        self._connectRet = ret  --连接成功
        self._reConnectSt = nil
        self._stopAutoReConnect = nil
        if bee.isEditor then
            print("[LoginMode] 网络重新连接...", ret, self:getServerUrl())
        end
        if cb then
            cb(ret)
        else
            Net:sendReq("pb.UserLoginREQ", {
                uid = PlayerModel:getUid(),
                key = PlayerModel:getRdkey(),
                ver = G_UPDATE_VERSION,
                chnl = G_CHNL_ID,
            })
        end
        if ret then
            bee.logEvent("connect_server")
        end
    end)
end

function P:forgotPassword(step, verify, check, password, cb, noTipError)
    local args = {
        step = step,
        verify = verify,
        check = check,
        password = password,
        lang = LanguageManager:getLanguage(),
    }

    local _onSuccess = function (data)
        if step == RETRIEVE_STEP.MODIFY then
            PlayerModel:setLoginEmail(verify)
            PlayerModel:setLoginPw(password)
        end
        if cb then
            cb(data)
        end
    end

    Net:post("forgotPassword", self:addLoginArgs(args), _onSuccess, nil, noTipError) 
end

function P:evt_faceBookLogin(token)
    self.login_type = LOGIN_TYPE.FACEBOOK
    if not token then
        return
    end

    local args = {
        type = LOGIN_TYPE.FACEBOOK,
        token = token,
        os = bee.pfsys,
        imei = SdkHelper:getDeviceID(),
        lang = LanguageManager:getLanguage(),
    }

    local _onSuccess = function (data)
        self:_onLoginSuccess(data, args)
    end

    Net:post("login", self:addLoginArgs(args), _onSuccess, function() self:_onLoginFail() end)
end

function P:evt_appleLogin(info)
    self.login_type = LOGIN_TYPE.iOS
    if not info then
        return
    end
    local d = json.decode(info)
    print("==== gggggg evt_appleLogin", d, d.retCode)
    if not d or d.retCode ~= 0 then
        return
    end

    local args = {
        type = LOGIN_TYPE.iOS,
        token = d.identityToken,
        os = bee.pfsys,
        imei = SdkHelper:getDeviceID(),
        lang = LanguageManager:getLanguage(),
    }

    local _onSuccess = function (data)
        self:_onLoginSuccess(data, args)
        if data.code == 0 then
            PlayerModel:setLoginToken(args.token)
        end
    end

    Net:post("login", self:addLoginArgs(args), _onSuccess, function() self:_onLoginFail() end)
end

function P:evt_stoveLogin(info)
    if info then
        print("==== gggggg evt_stoveLogin", json.encode(info))
        if 0 ~= info.resultCode then
            UiManager:hideLoadingMask("Login")
            bee.emit(EventDef.evt_login_fail)
            return
        end
        UiManager:showLoadingMask("Login")
        if self._isBinding then
            self._isBinding = nil
            Net:post("player/bindStove", {
                token = info.token,
            }, function(data)
                UiManager:hideLoadingMask("Login")
                if data.code == 0 then
                    UiManager:showTip({text = _T("LAB_SETTINGS_113")})
                    PlayerModel:setStoveGUID(data.stove_guid)
                    bee.emit(EventDef.evt_refreshBindStove)
                elseif data.exist_uid and data.exist_uid > 0 then
                    UiManager:showTip({text = _F("LAB_SETTINGS_036", data.exist_uid)})
                end
            end, function()
                UiManager:hideLoadingMask("Login")
            end)
            return
        else
            self.login_type = bee.isPc and LOGIN_TYPE.STOVE_PC or LOGIN_TYPE.STOVE
            self:doLogin({
                type = self.login_type,
                token = info.token,
            })
        end
    end
end

function P:evt_steamLogin(ticket)
    if ticket and "" ~= ticket then
        print("==== gggggg evt_steamLogin", ticket)
        self.login_type = LOGIN_TYPE.STEAM
        self:doLogin({
            type = LOGIN_TYPE.STEAM,
            token = ticket,
        })
    else
        self:_onLoginFail()
    end
end

-- --------------------------------------------------

function P:loginWithGoogle()
    GoogleMgr:checkLogin(function(isLogin)
        if isLogin then
            self:reConnect(function(ret)
                if ret then
                    GoogleMgr:getPlayerId(function(playerId)
                        GoogleMgr:loginServer(function(token)
                            if token then
                                bee.emit(EventType.evt_doLogin, {
                                    authType = Config.LoginType.GOOGLE,
                                    authToken = token,
                                    gameType = G_GAME_NAME,
                                    clientId = GoogleMgr:getClientId(),
                                    playerId = playerId,
                                })
                            end
                        end)
                    end)
                end
            end)
        end
    end)
end

function P:checkReConnect()
    if (not self._connectRet or not Net:isConnected()) and PlayerModel:isLogin() then
        self._connectRet = nil
        if bee.checkCd("socket_reconnect", 9) then
            self:reConnectWithCheck()
        else
            bee.once(9, function()
                if not Net:isConnected() then
                    self:reConnectWithCheck()
                end
            end)
        end
    end
end

function P:evt_netClosed()
    if PlayerModel:isLogin() then
        self:checkReConnect()
    end
end

function P:isOnLine() 
    return Net:isConnected() and PlayerModel and PlayerModel:isLogin()
end

-- 是否在排队中
function P:isInQueue()
    return self._inQueue
end

function P:setInQueue(flag)
    self._inQueue = flag
end

function P:getServerUrl()
	return UrlManager:getServerUrl()
end

function P:startClock()
end

function P:resetHeartBeat()
    self._heartbeat = 0
end

function P:setServerTime(dt)
    if dt and dt > 0 then
        self._serverTime = dt
        self._serverTimeSt = os.time()
    else
        self._serverTime = os.time()
        self._serverTimeSt = self._serverTime
    end
    local utc_date = os.date("!*t", self._serverTime)
    self._utc_hour = utc_date.hour
end

-- 获取当前服务器的时间(s)
function P:getServerTime()
    local ct = os.time() + self._serverTime - self._serverTimeSt
    return ct
end

function P:evt_onApplicationFocus(isFocus)
    -- if isFocus then
    --     self:checkReConnect()
    -- end
end

function P:getAcountData()
    return self.saveData
end

function P:setAuthData(authType, aToken)
    self.saveData.authType = authType
    self.saveData.authToken = aToken
    self:onSave()
end

function P:setAcountBindList(data)
    self.saveData.isBindFacebook = data.isBindFacebook
    self:onSave()
end

function P:getAuthType()
    return self.saveData.authType
end

function P:isFB()
    return self.saveData.authType == Config.LoginType.FACEBOOK or self.saveData.isBindFacebook
end

function P:isAppleLogin()
    return self.saveData.authType == Config.LoginType.APPLE
end

function P:isGoogleLogin()
    return self.saveData.authType == Config.LoginType.GOOGLE
end

function P:cryptoPasswrod(pwd)
	return CS.Utils.GetMd5(CS.Utils.GetMd5(pwd))
end

function P:getCheckMd5Str(input)
	return "&verify=" .. CS.Utils.GetMd5(input .. "ba2798edafa12f3ae08822a3203158cb")
end

function P:getCheckMd5(input)
    return CS.Utils.GetMd5(input .. "ba2798edafa12f3ae08822a3203158cb")
end

function P:checkLoginCode(code, show)
	if code >= 13000 then
		local lab
		if code == 13000 then
			lab = "LAB_CHECK_EMAIL_INVALID"
		elseif code == 13001 then
			lab = "LAB_CHECK_EMAIL_SENDED"
		elseif code == 13002 then
			lab = "LAB_CHECK_EMAIL_INPUT_ERROR"
		elseif code == 13003 then
			lab = "LAB_EMAIL_TIPS_3"
		elseif code == 13004 then
			lab = "LAB_CHECK_EMAIL_BOUND"
		end
		if lab and show then
			M.showCommonDialog({content = _T(lab)})
		else
			return lab
		end
		return true
	end
	return false
end

function P:checkLoginValid(cb)
    Net:post("player/valid", {t = 1}, function(data)
        if data.code == tpl_HttpCode.HTTP_AUTHENTICATION_FAILED.code then
            if not bee.isInStart() then
                PlayerModel:setIsLogin(false)
                PlayerModel:setNotAutoLogin(true)
                Net:closeSocket()
                bee.enterScene("StartScene", {onEnter = function()
                    UiManager:showUI("LoginNoNetwordDialog", {text = _T("HTTP_AUTHENTICATION_FAILED")})
                end})
            end
        else
            if cb then cb() end
        end
    end, function()
        if cb then cb() end
    end, true)
end

--其他玩家登录相同账号
function P:evt_OtherLoginMsg()
    print("其他玩家登录相同账号")
    self._connectRet=false
    scheduler:removeTag(self.__timerId)
end

function P:setOpenTime(openDateTime, regTime)
    self:setOpenDateTime(openDateTime)
    self:setRegTime(regTime)
end

-- 设置开服时间
function P:setOpenDateTime(openDate)
    self.__openDateTime = openDate
end

-- 获取开服时间
function P:getOpenDateTime()
    return self.__openDateTime
end

--设置注册时间
function P:setRegTime(regTime)
    self.saveData.cloud.__regTime = regTime
end

function P:getRegTime()
    return self.saveData.cloud.__regTime
end

--获取开服天数
function P:getOpenDay()
    local openTime = self:getOpenDateTime()
    if openTime == 0 then
        openTime = bee.getServerTime()
    end
    return self:getDay(openTime)
end

--获取注册天数
function P:getRegDay()
    local openTime = self:getRegTime()
    if openTime == 0 then
        openTime = bee.getServerTime()
    end
    return self:getDay(openTime)
end

--获取开服周数
function P:getOpenWeek()
    local openTime = self:getOpenDateTime()
    local day = self:getDay(openTime) + 1
    return math.ceil(day / 7)
end

--获取天数
function P:getDay(timeVal)
    timeVal = timeVal + 28800
    local serverTime = bee.getServerTime() + 28800
    local preDay = timeVal / 86400
    local curDay = serverTime / 86400
    return math.floor(curDay - preDay)
end

--断线重连时的清理
function P:clear()
    self.__openDateTime = 0
end

bee.schedule(5, function()
    if LoginModel then
        if LoginModel:isOnLine() or LoginModel:isInQueue() then
            LoginModel._heartbeat = LoginModel._heartbeat + 1
            Net:sendReq("pb.HeartBeatREQ", {})
            if LoginModel._heartbeat > 1 then
	            bee.logEvent("net_heartbeat_lose", UrlManager:getServerUrl())
                Net:closeSocket()
                UrlManager:nextServerUrl()
                LoginModel:checkReConnect()
            else
                local ct = bee.getServerTime()
                local utc_date = os.date("!*t", ct)
                local utc_hour = utc_date.hour
                if utc_hour ~= LoginModel._utc_hour then
                    LoginModel._utc_hour = utc_hour
                    if utc_hour == TimeHelp.crossHourUTC then
                        bee.emit(EventDef.evt_serverTimeCrossDay)
                    end
                end
            end
            bee.logEvent("net_delay", math.floor(Net:getDelay() * 1000), UrlManager:getServerUrl())
            local dt = math.floor(Net:getHttpDelay() * 1000)
            if dt > 0 then
                bee.logEvent("http_delay", dt, UrlManager:getHttpUrl())
            end
        else
            if not LoginModel._stopAutoReConnect then
                LoginModel:checkReConnect()
            end
        end
    end
end)

return P
