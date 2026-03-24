local P = class("LoginLayer", require("app.views.Login.LoginBase"))

function P:onAwake()
    self.Panel = self:find("AnimRoot/Panel")
    self.Center = self:find("AnimRoot/Center")
    self.BgMain = self:find("BgMain", self.Center)
    self.BgLogin = self:find("BgLogin", self.Center)
    self.BgStove = self:find("BgStove", self.Center)

    self.InputFieldName = self:find("InputFieldName", self.BgLogin)
    self.InputFieldPwd = self:find("InputFieldPwd", self.BgLogin)
    self.TipsText = self:find("TipsText", self.BgLogin)

    self.LoginButtons = {
        [LOGIN_TYPE.iOS] = self:find("ButtonApple", self.BgMain),
        [LOGIN_TYPE.FACEBOOK] = self:find("ButtonFacebook", self.BgMain),
        [LOGIN_TYPE.TWITTER] = self:find("ButtonX", self.BgMain),
        [LOGIN_TYPE.EMAIL] = self:find("ButtonEmail", self.BgMain),
        [LOGIN_TYPE.GUEST] = self:find("ButtonGuest", self.BgMain),
        [LOGIN_TYPE.STOVE] = self:find("ButtonStove", self.BgMain),
        [LOGIN_TYPE.STEAM] = self:find("ButtonSteam", self.BgMain),
    }
    self.ButtonStoveMobile = self:find("ButtonStove", self.BgStove)

    self.LoginBtPoses = {}
    for k, v in pairs(self.LoginButtons) do
        -- self.LoginBtPoses[k] = v.transform.localPosition
        table.insert(self.LoginBtPoses, v.transform.localPosition)
    end
    table.sort(self.LoginBtPoses, function(a, b)
        if a.y == b.y then
            return a.x < b.x
        end
        return a.y > b.y
    end)

    bee.addClick(self.LoginButtons[LOGIN_TYPE.iOS], function()
        self:onBtApple()
        bee.logEvent("login-apple-click")
    end)
    bee.addClick(self.LoginButtons[LOGIN_TYPE.FACEBOOK], function()
        self:onBtFacebook()
        bee.logEvent("login-fb-click")
    end)
    bee.addClick(self.LoginButtons[LOGIN_TYPE.TWITTER], function()
        self:onBtX()
        bee.logEvent("login-x-click")
    end)
    bee.addClick(self.LoginButtons[LOGIN_TYPE.EMAIL], function()
        self:onBtEmail()
        bee.logEvent("login-email-click")
    end)
    bee.addClick(self.LoginButtons[LOGIN_TYPE.GUEST], function()
        self:onBtGuest()
        bee.logEvent("login-guest-click")
    end)
    bee.addClick(self.LoginButtons[LOGIN_TYPE.STOVE], function()
        self:onBtStove()
        bee.logEvent("login-stove-click")
    end)
    bee.addClick(self.ButtonStoveMobile, function()
        self:onBtStove()
        bee.logEvent("login-stove-click")
    end)
    bee.addClick(self.LoginButtons[LOGIN_TYPE.STEAM], function()
        self:onBtSteam()
        bee.logEvent("login-steam-click")
    end)


    bee.addClick(self:find("ButtonRegister", self.BgMain), function()
        self:onBtRegister()
        bee.logEvent("login-email-login")
    end)
    bee.addClick(self:find("ButtonForgot", self.BgMain), function()
        self:onBtForgot()
        bee.logEvent("login-email-forget-password")
    end)
    bee.addClick(self:find("ButtonLogin", self.BgLogin), function()
        self:onBtLogin()
    end)
    bee.addClick(self:find("ButtonRegister", self.BgLogin), function()
        self:onBtRegister()
        bee.logEvent("login-email-login")
    end)
    bee.addClick(self:find("ButtonForgot", self.BgLogin), function()
        self:onBtForgot()
        bee.logEvent("login-email-forget-password")
    end)
    bee.addClick(self:find("ButtonClose", self.BgLogin), function()
        self.BgMain:SetActive(true)
        self.BgLogin:SetActive(false)
        LAN:refreshLan(self.BgMain)
    end)

     Game:playMusic("10001", SettingModel:getLobbyBGMVolume())
end

function P:evt_hideRegister()
    self.Center:SetActive(false)
end

function P:evt_showRegister(params)
    self.Center:SetActive(true)
    if params and params.showLogin then
        self:setEmailLoginShow()
    end
end

function P:onStart()
    self:setLoginCont()

    -- if PlayerModel:getNotAutoLogin() then
    --     self:setLoginCont()
    -- else
    --     self.Center:SetActive(false)
    --     self:autoLogin()
    -- end
end

function P:setLoginCont()
    self.Center:SetActive(true)
    for k, v in pairs(self.LoginButtons) do
        self:find("ImageTip", v):SetActive(PlayerModel:getLoginType() == k)
    end
end

function P:onShow()
    if G_CHNL_ID == 5 or G_CHNL_ID == 6 or G_CHNL_ID == 8 then
        self.BgStove:SetActive(true)
        self.Panel:SetActive(false)
        self.BgMain:SetActive(false)
        self.BgLogin:SetActive(false)
    else
        self.BgStove:SetActive(false)
        self.Panel:SetActive(true)
        self.BgMain:SetActive(true)
        self.BgLogin:SetActive(false)
    end
    
    local btns
    if bee.isIos then
        -- btns = {LOGIN_TYPE.iOS, LOGIN_TYPE.EMAIL, LOGIN_TYPE.FACEBOOK, LOGIN_TYPE.GUEST}
        btns = {LOGIN_TYPE.STOVE}
    elseif bee.isAndroid then
        if G_CHNL_ID == 5 then
            btns = {LOGIN_TYPE.STOVE}
        else
            btns = {LOGIN_TYPE.EMAIL, LOGIN_TYPE.GUEST}
        end
    else
        btns = {LOGIN_TYPE.EMAIL, LOGIN_TYPE.GUEST}
        if G_CHNL_ID == 4 then
            table.insert(btns, 1, LOGIN_TYPE.STEAM)
        elseif G_CHNL_ID == 8 then
            table.insert(btns, 1, LOGIN_TYPE.STOVE)
        end
    end
    for _, v in pairs(self.LoginButtons) do
        v:SetActive(false)
    end
    for k, v in ipairs(btns) do
        local btn = self.LoginButtons[v]
        btn:SetActive(true)
        if #btns > 2 then
            btn.transform.localPosition = self.LoginBtPoses[k]
        else
            btn.transform.localPosition = self.LoginBtPoses[k + 2]
        end
    end
end

function P:setEmailLoginShow()
    bee.setText(self.InputFieldName, PlayerModel:getLoginEmail(), "InputField")
    bee.setText(self.InputFieldPwd, "", "InputField")

    self:initInputSeek(self.InputFieldName, true)
    self:initInputSeek(self.InputFieldPwd, false)
end

function P:onBtEmail()
    self.BgMain:SetActive(false)
    self.BgLogin:SetActive(true)
    self:setEmailLoginShow()
    LAN:refreshLan(self.BgLogin)
end

-- 游客登录
function P:onBtGuest()
    local params = {}
    params.text = _T("LAB_GUEST_LOGIN_TIPS")
    params.noClose = true
    params.onSure = function()
        PlayerModel:setTestDeviceID()
        UiManager:showLoadingMask("Login")
        LoginModel:guestLogin()
    end
    UiManager:showTip(params)
end

function P:onBtFacebook()
    CS.SdkHelper.FBLogin()
end

function P:onBtApple()
    CS.SdkHelper.LoginApple()
end

function P:onBtX()
    LoginModel:XLogin()
end

function P:onBtStove()
    if not bee.checkCd("stove_login_click", 2) then
        return
    end
    -- LoginModel:stoveLogin()
    if bee.isAndroid or bee.isIos then
        LoginModel:loginStove()
        bee.emit("evt_start_stove_login")
    else
        UiManager:showLoadingMask("Login")
        LoginModel._isBinding = nil
        CS.ThirdManager.Instance:login()
    end
end

function P:onBtSteam()
    UiManager:showLoadingMask("Login")
    CS.ThirdManager.Instance:login()
end

function P:onBtRegister()
    UiManager:showUI("LoginRegisterDialog")
end

function P:onBtForgot()
    UiManager:showUI("LoginForgotDialog")
end

-- 邮箱登录
function P:onBtLogin()
    local email = bee.getText(self.InputFieldName, "InputField")
    local pwd = bee.getText(self.InputFieldPwd, "InputField")

    if "" == email then
        bee.setText(self.TipsText, _T("LAB_E_MAIL_TIP"))
        return
    end
    if not GF.isValidEmail(email) then
        bee.setText(self.TipsText, _T("LAB_EMAIL_WRONG"))
        return
    end
    if "" == pwd then
        bee.setText(self.TipsText, _T("LAB_E_PWD"))
        return
    end
    bee.setText(self.TipsText, _T(""))

    LoginModel:emailLogin(email, pwd, function(data)
        if data and data.code < 0 then
            local e = tpl_errorCode[data.code]
            if e then
                bee.setText(self.TipsText, _T(e.id))
            end
        end
    end, true)
end

function P:autoLogin()
    local loginType = PlayerModel:getLoginType()
    if not loginType or not PlayerModel:isAutoLogin() then
        self:setLoginCont()
        return false
    end

    if loginType == LOGIN_TYPE.GUEST then
        if PlayerModel:getTestDeviceID() then
            LoginModel:guestLoginTest(PlayerModel:getTestDeviceID())
        else
            LoginModel:guestLogin()
        end
    elseif loginType == LOGIN_TYPE.EMAIL then
        local email = PlayerModel:getLoginEmail()
        local pw = PlayerModel:getLoginPw()
        if not email or not pw then
            self:setLoginCont()
            return false
        end
        LoginModel:emailLogin(email, pw, function(data)
            if data and data.code < 0 then
                local e = tpl_errorCode[data.code]
                if e then
                    bee.setText(self.TipsText, _T(e.id))
                end
            end
        end, true)
    elseif loginType == LOGIN_TYPE.FACEBOOK then
        self:onBtFacebook()
    elseif loginType == LOGIN_TYPE.TWITTER then
        self:onBtX()
    elseif loginType == LOGIN_TYPE.iOS then
        -- self:onBtApple()
        local token = PlayerModel:getLoginToken()
        if token and "" ~= token then
            LoginModel:evt_appleLogin(json.encode({retCode = 0, identityToken = token}))
        else
            return false
        end
    elseif loginType == LOGIN_TYPE.STOVE then
        -- LoginModel:initStove()
        CS.ThirdManager.Instance:loginWithCache()
    elseif loginType == LOGIN_TYPE.STOVE_PC then
        self:onBtStove()
    elseif loginType == LOGIN_TYPE.STEAM then
        self:onBtSteam()
    else
        self:setLoginCont()
    end
    return true
end

function P:evt_faceBookLogin(token)
    if not token or "" == token then
        self:setLoginCont()
    end
end

function P:evt_login_fail()
    self:setLoginCont()
end

