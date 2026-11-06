local P = class("LoginStartLayer", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)

    local Loading = self:find("Loading", self.Bottom)
    self.LoadingBar = self:find("LoadingBar", Loading)
    self.LoadingEft = self:find("LoadingEft", Loading)
    self.TextDowning = self:find("TextDowning", Loading)
    self.TextPrecent = self:find("TextPrecent", Loading)

    self.LoadingEftPos = self.LoadingEft.transform.localPosition

    self.TouchStart = self:find("TouchStart", self.AnimRoot)

    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.ButtonLogo = self:find("LogoIcon", self.LeftTop)
    self._logo_clickable = false

    self.RightTop = self:find("RightTop", self.AnimRoot)
    local Layer = self:find("Layer", self.RightTop)
    self.ButtonLanguage = self:find("ButtonLanguage", Layer)
    self.ButtonAccount = self:find("ButtonAccount", Layer)
    self.ButtonNetwork = self:find("ButtonNetwork", Layer)
    self.ButtonMusic = self:find("ButtonMusic", Layer)
    self.ButtonRepair = self:find("ButtonRepair", Layer)

    bee.addClick(self.TouchStart, function()
        Game:playSound("ui_button_confirm")
        if PlayerModel:isLogin() then
            if AppLoadRes:isInCheckUpdate() then
                return
            end
            if PlayerModel:getLoginType() == LOGIN_TYPE.GUEST then
                local params = {}
                params.text = _T("LAB_GUEST_LOGIN_TIPS")
                params.noClose = true
                params.onSure = function()
                    bee.enterScene("MainScene", {from = "StartScene"})
                end
                UiManager:showTip(params)
            else
                bee.enterScene("MainScene", {from = "StartScene"})
            end
        else
            self:showLoginLayer()
            self.TouchStart:SetActive(false)
        end
    end)


    bee.addClick(self:find("LogoIcon2", self.LeftTop), function ()
        self:onBtLogo()
    end)
    bee.addClick(self.ButtonLogo, function ()
        self:onBtLogo()
    end)

    bee.addClick(self.ButtonLanguage, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("LoginSetLanguage")
        bee.logEvent("login-language")
    end)

    bee.addClick(self.ButtonAccount, function()
        Game:playSound("ui_button_confirm")
        UiManager:showLoadingMask("Logout")
        PlayerModel:setNotAutoLogin(false)
        PlayerModel:setIsLogin(false)
        PlayerModel:setAutoLogin(false)
        Net:sendReq("pb.UserLogoutREQ", {})
        
        bee.logEvent("login-account")
    end)

    bee.addClick(self.ButtonNetwork, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("login-route-access")

        UiManager:showUI("Loginline")
    end)

    bee.addClick(self.ButtonMusic, function()
        Game:playSound("ui_button_confirm")

        SettingModel.saveData.lobbyBGMOn = not self:isBGMisOn()
        if SettingModel.saveData.lobbyBGMOn then
            SettingModel.saveData.globalVolumeOn = true
            if SettingModel.saveData.globalVolume <= 0 then
                SettingModel.saveData.globalVolume = 0.5
            end
            if SettingModel.saveData.lobbyBGM <= 0 then
                SettingModel.saveData.lobbyBGM = 0.5
            end
        end
        SettingModel:onSave()
        bee.logEvent("login-music-switch", SettingModel.saveData.lobbyBGMOn and 1 or 0)
        
        self:find("ON", self.ButtonMusic):SetActive(SettingModel.saveData.lobbyBGMOn)
        self:find("OFF", self.ButtonMusic):SetActive(not SettingModel.saveData.lobbyBGMOn)

        if SettingModel.saveData.lobbyBGMOn then
            self:playStartBGM()
	        LAN:refreshLan(self:find("ON", self.ButtonMusic))
        else
            Game:stopMusic()
	        LAN:refreshLan(self:find("OFF", self.ButtonMusic))
        end
    end)

    bee.addClick(self.ButtonRepair, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("login-repair-access")

        UiManager:showUI("Loginrepair")
    end)

    self.ButtonAccount:SetActive(false)

    self:evt_refreshLimitView()
end

function P:onShow()
    self.TouchStart:SetActive(false)
	self.LoginLayer = UiManager:showUI("LoginLayer")
    self:hideLoginLayer()

    if G_DOWNLOAD_REMOTE then
        G_DOWNLOAD_REMOTE = false
        PlayerModel:setIsLogin(false)
        PlayerModel:setNotAutoLogin(true)
        ItemModel:clearItems()
        Net:closeSocket()
        -- self.ButtonRepair:SetActive(false)
        AppLoadRes:startDownload()
    elseif not G_CHECK_DL_RES then
        G_CHECK_DL_RES = true
        -- self.ButtonRepair:SetActive(false)
        self:checkDownload()
    else
        self:onDownloadComplete()
    end
    bee.logEvent("login-ui-access")

    local isOn = self:isBGMisOn()
    self:find("ON", self.ButtonMusic):SetActive(isOn)
    self:find("OFF", self.ButtonMusic):SetActive(not isOn)
    
    self:playStartBGM()
end

function P:isBGMisOn()
    return SettingModel.saveData.lobbyBGMOn and SettingModel.saveData.lobbyBGM > 0 and SettingModel.saveData.globalVolumeOn and SettingModel.saveData.globalVolume > 0
end

function P:playStartBGM()
    if SettingModel.saveData.lobbyBGMOn and SettingModel:getLobbyBGMVolume() > 0 then
        Game:playMusic("10001", SettingModel:getLobbyBGMVolume())
    end
end

function P:checkServer()
    self:setDownloadText("LAB_UPDATE_TIPS_6")
    bee.setText(self.TextPrecent, "")
    Net:post("open/checkServer", {t=1, immediately = true}, function(data)
        if bee.isNull(self.node) then
            return
        end
        if data and data.code == 0 then
            if not data.data then
                self:tryAutoLogin()
            elseif data.data.status == 1 then   -- 设置了停服
                GF.showServerMaintain(data.data, function() self:tryAutoLogin() end, function() self:showLoginLayer() end)
            else
                self:tryAutoLogin()
            end
        else
            self:showLoginLayer()
            PlayerModel:setNotAutoLogin(true)
        end
    end, function()
        self._checkFailCount = (self._checkFailCount or 0) + 1
        if self._checkFailCount >= 3 then
            self._checkFailCount = nil
            UiManager:showTip({
                text = _T("LAB_NET_ERR_TIPS1"),
                noClose = true,
                sureStr = _T("LAB_NET_LINK_AGAIN"),
                -- cancelStr = _T("LAB_SETTINGS_030"),
                onSure = function()
                    if UrlManager:getSelectKey() == UrlManager:getHttpUrl() then
                        UrlManager:nextHttpUrl()
                    end
                    UrlManager:setSelectKey(nil)
                    self:checkServer()
                end,
                onCancel = function()
                    -- Game:quit()
                    self:showLoginLayer()
                end,
            })
        else
            self:once(5, function()
                self:checkServer()
            end)
        end
    end)
end

function P:setDownloadText(text)
    self._downloadText = text
    bee.setText(self.TextDowning, _T(text))
end

function P:tryAutoLogin()
    self.Bottom:SetActive(false)

    if not PlayerModel:getNotAutoLogin() then
        self._isInAutoLogin = self.LoginLayer:autoLogin()
    end
    if not self._isInAutoLogin then
        self:showLoginLayer()
    else
        self:once(10, function()
            if not self._isInWhiteUpdate and not self.Bottom.activeSelf and not self.TouchStart.activeSelf then
                self:showLoginLayer()
            end
        end)
    end
end

function P:checkDownload()
    self:setDownloadText("LAB_UPDATE_TIPS_5")
    bee.setText(self.TextPrecent, "")

    GF.startCheckUpdate(false, function()
        self:onUpdateFinish()
    end)
end

function P:getMB(size)
	return tostring(math.floor(size / (1024 * 1024) * 100) / 100) .. " MB"
end

function P:onDownloadComplete()
    -- self:tryAutoLogin()
    self.ButtonRepair:SetActive(true)
    self:checkServer()
end

function P:showLoginLayer()
    self.Bottom:SetActive(false)
    self.LoginLayer.transform.localPosition = bee.v3zero
    self.LoginLayer.transform.localScale = bee.v3one
    self.ButtonAccount:SetActive(false)
    self._logo_clickable = true
end

function P:hideLoginLayer()
    if self.LoginLayer then
        self.LoginLayer.transform.localPosition = bee.v3(0, -9999)
        self.LoginLayer.transform.localScale = bee.v3zero
    end
end

function P:onBtLogo()
    if not (G_CHNL_ID == 5 or G_CHNL_ID == 6) then
        return
    end
    if self._isLinked then
        return
    end
    if not self._logo_clickable then
        return
    end

    Game:playSound("ui_button_confirm")
    self:showLoginLayer()
    self.LoginLayer:showEmailLogin()
    bee.logEvent("login-logo")
end

function P:evt_onApplicationPause(paused)
    if not paused then
        self:once(1, function()
            if LoginModel.login_type == LOGIN_TYPE.FACEBOOK and not PlayerModel:getXToken() then
                self:evt_login_fail()
            end
        end)
    end
end

function P:evt_remote_res_start()
    self.ButtonRepair:SetActive(false)
    UiManager:hideUI("Loginrepair")
    UiManager:hideUI("CommonNoticeSmall")
end

function P:evt_remote_res_progress(val)
    self.Bottom:SetActive(true)
    self:hideLoginLayer()
    self.TouchStart:SetActive(false)
    self.ButtonAccount:SetActive(false)
    
    self._downloadText = nil
    bee.setText(self.TextPrecent, tostring(math.ceil(val * 100)) .. "%")
    bee.setText(self.TextDowning, _F("LAB_DOWNLOADING", self:getMB(val * AppLoadRes.downSize), self:getMB(AppLoadRes.downSize)))
    bee.setFillAmount(self.LoadingBar, val)
    local pos = bee.v3(self.LoadingEftPos.x * 2 * val - self.LoadingEftPos.x, self.LoadingEftPos.y)
    self.LoadingEft.transform.localPosition = pos
end

function P:onUpdateFinish()
    if AppLoadRes.downSize > 0 then
        self._downloadText = nil
        bee.setText(self.TextPrecent, "100%")
        bee.setText(self.TextDowning, _F("LAB_DOWNLOADING", self:getMB(AppLoadRes.downSize), self:getMB(AppLoadRes.downSize)))
    end
    bee.setFillAmount(self.LoadingBar, 1)
    self.LoadingEft.transform.localPosition = self.LoadingEftPos
    self:onDownloadComplete()
end

function P:evt_login_fail()
    self:showLoginLayer()
    self._isLinked = false
    self._isInAutoLogin = nil
    self._isInWhiteUpdate = nil
end

function P:evt_faceBookLogin(token)
    self:evt_login_fail()
end

function P:evt_UserLoginRSP(msg)
    self._isInWhiteUpdate = nil
    if 0 == msg.code then
    else
        UiManager:hideLoadingMask("Login")
        self:showLoginLayer()
    end
end

function P:evt_SelfUserInfoRSP(msg)
    UiManager:hideLoadingMask("Login")
    if not self._isInAutoLogin and GameModel.roomid == 0 then
        bee.enterScene("MainScene", {from = "StartScene"})
    else
        self:hideLoginLayer()
        self.TouchStart:SetActive(true)
        self.ButtonAccount:SetActive(G_CHNL_ID ~= 8)
    end
    self._isLinked = true
    self._isInAutoLogin = nil
    self._isInWhiteUpdate = nil
end

function P:evt_UserLogoutRSP()
    UiManager:hideLoadingMask("Logout")
    self:showLoginLayer()
    self.TouchStart:SetActive(false)
    self._isLinked = false
    if G_CHNL_ID == 5 or G_CHNL_ID == 6 then
        CS.ThirdManager.Instance:login()
    end
end

function P:evt_netClosed()
    UiManager:hideLoadingMask("Login")
    self:showLoginLayer()

    LoginModel:checkReConnect()
end

function P:evt_start_stove_login()
    self.RightTop:SetActive(false)
end

function P:evt_stoveLogin()
    self.RightTop:SetActive(true)
end

function P:evt_lan_mod()
    if self._downloadText then
        bee.setText(self.TextDowning, _T(self._downloadText))
    end
end

function P:evt_start_white_update()
    self:hideLoginLayer()
    self.ButtonAccount:SetActive(false)
    self._isInWhiteUpdate = true
end

function P:evt_try_resume_bgm()
    self:playStartBGM()

    self:find("ON", self.ButtonMusic):SetActive(SettingModel.saveData.lobbyBGMOn)
    self:find("OFF", self.ButtonMusic):SetActive(not SettingModel.saveData.lobbyBGMOn)
end

function P:evt_refreshLimitView()
    local oldName = self.LoginSpineKV
    local isUseKv2 = tpl_constdata.KV2_Endtime > bee.getServerTime()
    self.LoginSpineKV = bee.getLimitViewRes(isUseKv2 and "LoginSpineKV2" or "LoginSpineKV", true)
    self:find("LogoIcon", self.LeftTop):SetActive(not isUseKv2)
    self:find("LogoIcon2", self.LeftTop):SetActive(isUseKv2)
    if oldName ~= self.LoginSpineKV then
        local obj = ResManager:InstantiateObject(self.LoginSpineKV)
        if obj then
            if not bee.isNull(self.LoginSpineKVObj) then
                CU.GameObject.Destroy(self.LoginSpineKVObj)
                self.LoginSpineKVObj = nil
            end
            obj.transform:SetParent(self.Center.transform, false)
            self.LoginSpineKVObj = obj
        end
    end
end

return P