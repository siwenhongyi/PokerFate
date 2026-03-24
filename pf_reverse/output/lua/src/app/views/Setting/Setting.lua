local P = class("Setting", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    
    self.TextVer = self:find("Bg/TextVer", self.Panel)
    self.TextFullVer = self:find("Bg/TextFullVer", self.Panel)

    self.TabViews = {
        self:find("TabGeneral", self.Panel),
        self:find("TabAudioList", self.Panel),
        self:find("TabAccount", self.Panel),
        self:find("TabIngame", self.Panel),
    }
    self.ViewSize = self.TabViews[1].transform.sizeDelta
    local TAB = self:find("TAB", self.Panel)
    self.Tabs = {
        self:find("Tab1Toggle", TAB),
        self:find("Tab2Toggle", TAB),
        self:find("Tab3Toggle", TAB),
        self:find("Tab4Toggle", TAB),
    }
    for k, v in ipairs(self.Tabs) do
        bee.addValueChanged(v, function(isOn)
            if isOn then
                Game:playSound("ui_tab_switch_1")
                self:doShowView(k)
            end
        end)
    end

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)

    self.ButtonsExit = self:find("ButtonsExit", self.Panel)
    bee.addClick(self:find("FeedbackButton", self.ButtonsExit), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SettingFeedback")
        bee.logEvent("settings-feedback")
    end)
    bee.addClick(self:find("ProtocolButton", self.ButtonsExit), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SettingProtocol")
        bee.logEvent("settings-tc")
    end)
    bee.addClick(self:find("GiftCodeButton", self.ButtonsExit), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SettingRedeemCodeView")
        bee.logEvent("settings-giftcode")
    end)
    bee.addClick(self:find("ExitButton", self.ButtonsExit), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("settings-exitgame")
        UiManager:showTip({
            text = _T("LAB_SETTINGS_108"),
            onSure = function()
                Game:quit()
            end
        })
    end)
end

function P:onShow()
    if bee.isInGame() then
        self.Tabs[3]:SetActive(false)
        self.Tabs[4].transform.localPosition = bee.v3(0, 108)
        self.Tabs[1].transform.localPosition = bee.v3(0, 0)
        self.Tabs[2].transform.localPosition = bee.v3(0, -108)
        self:doShowView(4)

        for _, v in ipairs(self.TabViews) do
            v.transform.sizeDelta = bee.v2(self.ViewSize.x, 799)
        end
        self.ButtonsExit:SetActive(false)
        local bg = self:find("Bg/common_panel_black_frame_01", self.Panel)
        local s = bg.transform.sizeDelta
        bg.transform.sizeDelta = bee.v2(s.x, 799)
    else
        self.Tabs[4]:SetActive(false)
        self:doShowView(1)
    end

    bee.setText(self.TextVer, _F("LAB_SETTINGS_018", G_UPDATE_VERSION))
    bee.setText(self.TextFullVer, _F("LAB_SETTINGS_122", G_APP_VERSION))
end

function P:onDestroy()
    P.super.onDestroy(self)
    SettingModel:onSave()
end

function P:doShowView(index)
    for i, view in ipairs(self.TabViews) do
        view:SetActive(i == index)
        if not self["_initview" .. index] then
            if 1 == index then
                self:onShowTabGeneral()
            elseif 2 == index then
                self:onShowTabAudioList()
            elseif 3 == index then
                self:onShowTabAccount()
            else
                self:onShowTabIngame()
            end
            self["_initview" .. index] = true
        end
        if self._is_lan_mod and i == index then
            LanguageManager:refreshLan(view)
        end
    end
end

function P:onShowTabGeneral()
    self:initTabGeneral()
    self:refreshFilter()
    bee.setCheck(self.FullToggle, false, bee.isFullScreen())
    for k, v in ipairs(Config.Languages) do
        if v == LanguageManager:getLanguage() then
            bee.setCheck(self.ToggleLans[k])
            break
        end
    end
    for k, v in ipairs(Config.FrameRates) do
        if v == bee.getFrameRate() then
            bee.setCheck(self.ToggleRates[k])
            break
        end
    end
    bee.setCheck(self.ToggleQualitys[bee.getGraphicQuality()], false)
end

function P:onShowTabAudioList()
    self:initTabAudioList()
end

function P:onShowTabAccount()
    self:initTabAccount()

    bee.setText(self.TextAccount, _F("LAB_SETTINGS_032", PlayerModel:getUid()))
    bee.setText(self.TextDelete, _T("LAB_SETTINGS_040"))
    self:evt_refreshBindEmail()
end

function P:onShowTabIngame()
    self:initTabIngame()

    self._gameType = GAME_GAME_TYPE.LOBBY_HOLDEM_GAME
    self._isOmaha = false
    if GameModel.data then
        self._isOmaha = GameModel.data:isOmaha()
        self._gameType = GameModel.data:getGameType()
        
        if GameModel.data:isTournament() then
            self.ButtonAutoByin.transform.parent.gameObject:SetActive(false)
            self.ButtonAutoSwitch.transform.parent.gameObject:SetActive(false)
        elseif GameModel.data:isFriendsRoom() then
            self.ButtonAutoSwitch.transform.parent.gameObject:SetActive(false)
        end
    end
    
    bee.setCheck(self.ButtonPreAction, false, SettingModel:isPreAction())
    bee.setCheck(self.ButtonCardValue, false, SettingModel:isCardValue())
    bee.setCheck(self.ButtonAutoByin, false, SettingModel:isAutoByin())
    bee.setCheck(self.ButtonShowCard, false, SettingModel:isShowCard())
    bee.setCheck(self.ButtonShowBB, false, SettingModel:isShowBB())
    bee.setCheck(self.ButtonCustomize, false, SettingModel:isBetCustomize(self._gameType) == true)
    bee.setCheck(self.ButtonPrecise, false, SettingModel:isBetPrecise())
    bee.setCheck(self.ButtonAutoSwitch, false, SettingModel:isAutoSwitch())
    bee.setCheck(self.ButtonHideInvite, false, SettingModel:isHideInvite())
    bee.setCheck(self.ButtonHideChat, false, SettingModel:isHideChat())

    if self.Panel3 then
        self.Panel3:SetActive(SettingModel:isBetCustomize(self._gameType))
    end


    local flag = false
    for k, v in ipairs(self.IngameButtons) do
        if v.transform.parent.gameObject.activeSelf then
            self:find("common_panel_black_grid_04", v.transform.parent.gameObject):SetActive(flag)
            flag = not flag
        end
    end

    if self.BetSlider then
        self._curBetIndex = 1
        self._curRaiseIndex = 1
        self._curRaiseKind = SettingModel:getRaiseKind(true, self._gameType)
        if self.RaiseKinds then
            bee.setCheck(self.RaiseKinds[self._curRaiseKind])
        end

        self:refreshBetRaise()
    end
end

function P:initTabGeneral()
    if self._initview1 then return end

    self.FilterMask = self:find("Center/FilterMask", self.AnimRoot)
    self.FilterView = self:find("FilterView", self.FilterMask)
    self.FilterItem = self:find("FilterItem", self.FilterMask)
    self.FilterMask:SetActive(false)
    self.FilterItem:SetActive(false)

    local Content = self:find("Viewport/Content", self.TabViews[1])
    local GeneralItem1 = self:find("GeneralItem01", Content)
    self.ToggleLans = {
        self:find("Check1Toggle", GeneralItem1),
        self:find("Check2Toggle", GeneralItem1),
        self:find("Check3Toggle", GeneralItem1),
        self:find("Check4Toggle", GeneralItem1),
    }
    for k, v in ipairs(self.ToggleLans) do
        bee.addValueChanged(v, function(isOn)
            if isOn then
                Game:playSound("ui_button_disabled")
                LanguageManager:setLanguage(Config.Languages[k])
                
                bee.logEvent("settings-language", k)
            end
        end)
    end

    local GeneralItem2 = self:find("GeneralItem02", Content)
    self.ToggleQualitys = {
        self:find("Check1Toggle", GeneralItem2),
        self:find("Check2Toggle", GeneralItem2),
        self:find("Check3Toggle", GeneralItem2),
    }
    for k, v in ipairs(self.ToggleQualitys) do
        bee.addValueChanged(v, function(isOn)
            if isOn then
                Game:playSound("ui_button_disabled")
                bee.setGraphicQuality(k)
                bee.logEvent("settings-graphics", k)
            end
        end)
    end

    local GeneralItem3 = self:find("GeneralItem03", Content)
    self.ToggleRates = {
        self:find("Check1Toggle", GeneralItem3),
        self:find("Check2Toggle", GeneralItem3),
    }
    for k, v in ipairs(self.ToggleRates) do
        bee.addValueChanged(v, function(isOn)
            if isOn then
                Game:playSound("ui_button_disabled")
                bee.setFrameRate(Config.FrameRates[k])
                bee.refreshFrameRate()
                bee.logEvent("settings-frame", k)
            end
        end)
    end

    self.GeneralItem4 = self:find("GeneralItem04", Content)
    self.Filter = self:find("Filter", self.GeneralItem4)
    self.TextResolution = self:find("TextResolution", self.Filter)
    self.GeneralItem4:SetActive(bee.isPc)
    self.FilterArrow = self:find("FilterArrow", self.Filter)
    self.FullToggle = self:find("CheckToggle", self.GeneralItem4)

    bee.addValueChanged(self.FullToggle, function(isOn)
        Game:playSound("ui_button_disabled")
        bee.setFullScreen(isOn)
        bee.refreshScreen()
        bee.logEvent("settings-fullscreen", isOn and 1 or 2)
    end)

    bee.addClick(self.Filter, function()
        Game:playSound("ui_button_confirm")
        self:doShowResolution()
    end)

    bee.addClick2(self.FilterMask, function()
        self.FilterMask:SetActive(false)
        self:refreshFilter()
    end)

    self.FilterList = UiListEx:create(self.FilterView)
    self.FilterList:setWidth(70)
    self.FilterList:setTopBottom(4, 4)
    self.FilterList:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.FilterItem)
    end)
    self.FilterList:setRefreshFunc(function(data, item)
        bee.setText(self:find("On/TextValue", item), string.format("%dx%d", data[1], data[2]))
        bee.setText(self:find("Off/TextValue", item), string.format("%dx%d", data[1], data[2]))
        local cur = Config.Resolutions[bee.getResolution()]
        self:find("On", item):SetActive(cur == data)
        self:find("Off", item):SetActive(cur ~= data)

        bee.addClick(item, function()
            Game:playSound("ui_button_confirm")
            bee.setResolution(data.index)
            self.FilterMask:SetActive(false)
            self:refreshFilter()
            bee.refreshScreen()
            bee.logEvent("settings-resolution", data.index)
        end, true)
    end)

    self.GeneralItem5 = self:find("GeneralItem05", Content)
    self.VibrateSwitch1 = self:find("panel1/Switch", self.GeneralItem5)
    self.VibrateSwitch2 = self:find("panel2/Switch", self.GeneralItem5)
    self.VibrateSwitch3 = self:find("panel3/Switch", self.GeneralItem5)

    self:bindVibrateSwitch("vibrateUI", self.VibrateSwitch1, function(isOn)
        bee.logEvent("settings-vibrate-ui", isOn and 1 or 2)
    end)
    self:bindVibrateSwitch("vibrateInGame", self.VibrateSwitch2, function(isOn)
        bee.logEvent("settings-vibrate-ingame", isOn and 1 or 2)
    end)
    self:bindVibrateSwitch("vibrateOutGame", self.VibrateSwitch3, function(isOn)
        bee.logEvent("settings-vibrate-outgame", isOn and 1 or 2)
    end)
end

function P:bindVibrateSwitch(name, switch, onChange)
    bee.setCheck(switch, nil, SettingModel.saveData[name])
    bee.addValueChanged(switch, function(isOn)
        SettingModel.saveData[name] = isOn
        if onChange then
            onChange(isOn)
        end
        Game:playSound("ui_button_disabled")
    end)
end

function P:initTabAudioList()
    if self._initview2 then return end

    self.AudioContent = self:find("Viewport/Content", self.TabViews[2])
    local AudioItem1 = self:find("AudioItem1", self.AudioContent)
    local AudioItem2 = self:find("AudioItem2", self.AudioContent)
    local AudioItem3 = self:find("AudioItem3", self.AudioContent)
    local AudioItem4 = self:find("AudioItem4", self.AudioContent)

    self.GlobalSwitch = self:find("Switch", AudioItem1)
    self.GlobalAudioSlider = self:find("AudioSlider", AudioItem1)

    self:bindAudioSwitch("globalVolume", self:find("AudioSlider", AudioItem1), self:find("Switch", AudioItem1), function(isOn, val)
        self:refreshLobbyBGM()
        self:refreshIngameBGM()
        if not val then
            bee.logEvent("settings-mastervolume", isOn and 1 or 2)
        end
    end)

    self:bindAudioSwitch("lobbyBGM", self:find("AudioSlider1", AudioItem2), self:find("Switch1", AudioItem2), function(isOn, val)
        self:refreshLobbyBGM()
        if not val then
            bee.logEvent("settings-lobbybgm", isOn and 1 or 2)
        end
    end)
    self:bindAudioSwitch("ingameBGM", self:find("AudioSlider2", AudioItem2), self:find("Switch2", AudioItem2), function(isOn, val)
        self:refreshIngameBGM()
        if not val then
            bee.logEvent("settings-tablebgm", isOn and 1 or 2)
        end
    end)
    self:bindAudioSwitch("soundVolume", self:find("AudioSlider3", AudioItem2), self:find("Switch3", AudioItem2), function(isOn, val)
        if not val then
            bee.logEvent("settings-soundeffect", isOn and 1 or 2)
        end
    end)

    self:bindAudioSwitch("roleInVolume", self:find("AudioSlider1", AudioItem3), self:find("Switch1", AudioItem3), function(isOn, val)
        if not val then
            bee.logEvent("settings-attable", isOn and 1 or 2)
        end
    end)
    self:bindAudioSwitch("roleOutVolume", self:find("AudioSlider2", AudioItem3), self:find("Switch2", AudioItem3), function(isOn, val)
        if not val then
            bee.logEvent("settings-offtable", isOn and 1 or 2)
        end
    end)

    self.AudioItem1 = self:find("Item01", AudioItem4)
    self.AvatarList = self:find("AvatarList", AudioItem4)
    for _, v in ipairs(tpl_character_list) do
        if not v.display_time or v.display_time <= bee.getServerTime() or PlayerModel:isEventWhite() then
            local item = CU.GameObject.Instantiate(self.AudioItem1, self.AvatarList.transform, false)
            local flag = SettingModel:isRoleVolumeOn(v.id)
            self:find("On", item):SetActive(flag)
            self:find("Off", item):SetActive(not flag)
            CharacterModel:setSkinAvater(self:find("Mask/ImageIcon", item), CharacterModel:getRoleSkinData(v.id).id)
            bee.addClick(item, function()
                Game:playSound("ui_button_confirm")
                flag = not flag
                SettingModel:setRoleVolumeOn(v.id, flag)
                self:find("On", item):SetActive(flag)
                self:find("Off", item):SetActive(not flag)
                bee.logEvent("settings-customchar", v.id, flag and 1 or 2)
            end)
        end
    end
    self.AudioItem1:SetActive(false)

    bee.addClick(self:find("CONTENT1/Info1Button", AudioItem3), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonTextTipRL", {text = _T("LAB_SETTINGS_061"), target = self:find("CONTENT1/Info1Button", AudioItem3)})
    end)
    bee.addClick(self:find("CONTENT2/Info2Button", AudioItem3), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("CommonTextTipRL", {text = _T("LAB_SETTINGS_062"), target = self:find("CONTENT2/Info2Button", AudioItem3)})
    end)
end

function P:bindAudioSwitch(name, slider, switch, onChange)
    bee.setCheck(switch, nil, SettingModel.saveData[name .. "On"])
    bee.addValueChanged(switch, function(isOn)
        SettingModel.saveData[name .. "On"] = isOn
        self:refreshAutioSwitch(name, slider, switch)
        if onChange then
            onChange(isOn)
        end
        Game:playSound("ui_button_disabled")
    end)
    bee.addValueChanged(slider, function(val)
        SettingModel.saveData[name] = val
        if val <= 0 then
            self:find("common_icon_audio_on", slider):SetActive(false)
            self:find("common_icon_audio_off", slider):SetActive(true)
        else
            self:find("common_icon_audio_on", slider):SetActive(true)
            self:find("common_icon_audio_off", slider):SetActive(false)
        end

        if onChange then
            onChange(nil, val)
        end
    end, "Slider")
    self:refreshAutioSwitch(name, slider, switch)
    bee.setSliderValue(slider, SettingModel.saveData[name], true)
end

function P:refreshAutioSwitch(name, slider, switch)
    if SettingModel.saveData[name .. "On"] then
        if SettingModel.saveData[name] > 0 then
            self:find("common_icon_audio_on", slider):SetActive(true)
            self:find("common_icon_audio_off", slider):SetActive(false)
        else
            self:find("common_icon_audio_on", slider):SetActive(false)
            self:find("common_icon_audio_off", slider):SetActive(true)
        end

        self:find("Fill/On", slider):SetActive(true)
        self:find("Fill/Off", slider):SetActive(false)

        slider:GetComponent("Slider").enabled = true
    else
        self:find("common_icon_audio_on", slider):SetActive(false)
        self:find("common_icon_audio_off", slider):SetActive(true)

        self:find("Fill/On", slider):SetActive(true)
        self:find("Fill/Off", slider):SetActive(true)

        slider:GetComponent("Slider").enabled = false
    end
end

function P:refreshLobbyBGM()
    if bee.isInHome() then
        local v = SettingModel:getLobbyBGMVolume()
        if v > 0 then
            if CS.SoundManager.Instance:IsMusicPlaying() then
                CS.SoundManager.Instance:ChangeMusicVolume(v)
            else
                Game:playLobbyBGM()
            end
        else
            Game:stopMusic()
        end
    end
end

function P:refreshIngameBGM()
    if bee.isInGame() then
        local v = SettingModel:getIngameBGMVolume()
        if v > 0 then
            if CS.SoundManager.Instance:IsMusicPlaying() then
                CS.SoundManager.Instance:ChangeMusicVolume(v)
            else
                Game:playIngameBGM()
            end
        else
            Game:stopMusic()
        end
    end
end

function P:initTabAccount()
    if self._initview3 then return end

    local AccountItem1 = self:find("Viewport/Content/AccountItem1", self.TabViews[3])
    local AccountItem2 = self:find("Viewport/Content/AccountItem2", self.TabViews[3])
    local AccountItem3 = self:find("Viewport/Content/AccountItem3", self.TabViews[3])
    self.AccountItemStove = self:find("Viewport/Content/AccountItemStove", self.TabViews[3])
    self.AccountItemStove:SetActive(PlayerModel:isStoveAccount() and PlayerModel:getStoveGUID() <= 0)

    self.AccountItemBindUID = self:find("Viewport/Content/AccountItemBindUID", self.TabViews[3])
    self.AccountItemGenUID = self:find("Viewport/Content/AccountItemGenUID", self.TabViews[3])
    local chnl_id = PlayerModel:getRegChnl()
    if (chnl_id == 2 or chnl_id == 3 or chnl_id == 4 or chnl_id == 9 or chnl_id == 10) and 
        (G_CHNL_ID == 2 or G_CHNL_ID == 3 or G_CHNL_ID == 4 or G_CHNL_ID == 9 or G_CHNL_ID == 10) then
        self.AccountItemGenUID:SetActive(true)
        self.AccountItemBindUID:SetActive(false)

        bee.addClick(self:find("GenUIDButton", self.AccountItemGenUID), function()
            Game:playSound("ui_button_confirm")
            if "" == PlayerModel:getBindEmail() then
                UiManager:showTip({
                    text = _T("LAB_LOGIN_BIND_11"),
                    onSure = function()
                        UiManager:showUI("SettingBindEmail")
                        bee.logEvent("settings-linkmail")
                    end
                })
                return
            end
            bee.logEvent("login-account-transfer code-generate")
            UiManager:showUI("SettingTransferID", {kind = 1})
        end)
    elseif (chnl_id == 5 or chnl_id == 6) and (G_CHNL_ID == 5 or G_CHNL_ID == 6) then
        self.AccountItemGenUID:SetActive(false)
        if PlayerModel:isGuest() or PlayerModel:getBindEmail() ~= "" then
            self.AccountItemBindUID:SetActive(false)
        else
            self.AccountItemBindUID:SetActive(true)
        end

        bee.addClick(self:find("BindUIDButton", self.AccountItemBindUID), function()
            Game:playSound("ui_button_confirm")
            if PlayerModel:isGuest() then
                UiManager:showToast(_T("LAB_LOGIN_BIND_20"))
                return
            end
                
            if PlayerModel:getBindEmail() and "" ~= PlayerModel:getBindEmail() then
                UiManager:showToast(_T("LAB_LOGIN_BIND_21"))
                return
            end
            bee.logEvent("login-account-transfer code-blind")
            UiManager:showTip({
                text = _T("LAB_LOGIN_BIND_14"),
                sureStr = _T("LAB_LOGIN_BIND_16"),
                cancelStr = _T("LAB_LOGIN_BIND_15"),
                onSure = function()
                    UiManager:showUI("SettingTransferID", {kind = 2})
                end
            })
        end)
    else
        self.AccountItemGenUID:SetActive(false)
        self.AccountItemBindUID:SetActive(false)
    end

    bee.addClick(self:find("ViewButton", AccountItem1), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SettingAccountDetail")
        bee.logEvent("settings-accountdetails")
    end)
    bee.addClick(self:find("OutButton", AccountItem1), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("settings-logout")
        
        UiManager:showTip({
            text = _T("LAB_SETTINGS_107"),
            onSure = function()
                PlayerModel:setNotAutoLogin(true)
                PlayerModel:setIsLogin(false)
                PlayerModel:setAutoLogin(false)
                Net:sendReq("pb.UserLogoutREQ", {})
            end
        })
    end)

    self.TextAccount = self:find("TextAccount", AccountItem1)
    self.TextEmail = self:find("TextEmail", AccountItem2)
    self.LinkButton = self:find("LinkButton", AccountItem2)
    bee.addClick(self.LinkButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SettingBindEmail")
        bee.logEvent("settings-linkmail")
    end)
    bee.addClick(self:find("StoveButton", self.AccountItemStove), function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("settings-linkstove")
        LoginModel:bindStove()
    end)

    self.TextDelete = self:find("TextDelete", AccountItem3)
    self.DeleteButton = self:find("DeleteButton", AccountItem3)
    self.CancelButton = self:find("CancelButton", AccountItem3)
    bee.addClick(self.DeleteButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("SettingAccountRemove")
        bee.logEvent("settings-deleteaccount")
    end)
    bee.addClick(self.CancelButton, function()
        Game:playSound("ui_button_confirm")
        Net:post("player/cancelDeleteAccount", {
            t = 1,
            token = SdkHelper:getToken(),
        }, function(data)
            UiManager:showToast(_T("LAB_SETTINGS_109"))
            PlayerModel:setIsDeleted(false)
            self.DeleteButton:SetActive(not PlayerModel:isDeleted())
            self.CancelButton:SetActive(PlayerModel:isDeleted())
        end)
        bee.logEvent("settings-canceldeleteaccount")
    end)
    self.DeleteButton:SetActive(not PlayerModel:isDeleted())
    self.CancelButton:SetActive(PlayerModel:isDeleted())
end

function P:initTabIngame()
    if self._initview4 then return end

    local Content = self:find("Viewport/Content", self.TabViews[4])
    self.Panel3 = self:find("Panel3", Content)

    self.ButtonPreAction = self:find("ButtonPreAction/Switch", Content)
    self.ButtonCardValue = self:find("ButtonCardValue/Switch", Content)
    self.ButtonShowBB = self:find("ButtonShowBB/Switch", Content)
    self.ButtonAutoByin = self:find("ButtonAutoByin/Switch", Content)
    self.ButtonShowCard = self:find("ButtonShowCard/Switch", Content)
    self.ButtonCustomize = self:find("ButtonCustomize/Switch", Content)
    self.ButtonAutoSwitch = self:find("ButtonAutoSwitch/Switch", Content)
    self.ButtonPrecise = self:find("ButtonPrecise/Switch", Content)
    self.ButtonHideInvite = self:find("ButtonHideInvite/Switch", Content)
    self.ButtonHideChat = self:find("ButtonHideChat/Switch", Content)

    self.IngameButtons = {
        self.ButtonPreAction,
        self.ButtonCardValue,
        self.ButtonShowBB,
        self.ButtonAutoByin,
        self.ButtonShowCard,
        self.ButtonCustomize,
        self.ButtonAutoSwitch,
        self.ButtonPrecise,
        self.ButtonHideInvite,
        self.ButtonHideChat,
    }

    if self.Panel3 then
        self.ImageBetSetting = self:find("ImageBetSetting", self.Panel3)
        self.SliderBet = self:find("SliderBet", self.ImageBetSetting)
        self.SliderRaise = self:find("SliderRaise", self.ImageBetSetting)
        local Bets = self:find("Bets", self.ImageBetSetting)
        local Raises = self:find("Raises", self.ImageBetSetting)
        local RaiseType = self:find("RaiseType", self.ImageBetSetting)

        self.Bets = {
            self:find("Pot1Button", Bets),
            self:find("Pot2Button", Bets),
            self:find("Pot3Button", Bets),
            self:find("Pot4Button", Bets),
        }

        self.Raises = {
            self:find("Raise1Button", Raises),
            self:find("Raise2Button", Raises),
            self:find("Raise3Button", Raises),
            self:find("Raise4Button", Raises),
        }

        self.RaiseKinds = {
            self:find("RaisePotButton", RaiseType),
            self:find("RaiseXButton", RaiseType),
        }

        for k, v in ipairs(self.Bets) do
            bee.addValueChanged(v, function(isOn)
                if isOn then
                    self._curBetIndex = k
                    self:refreshBetValue(true)
                    if k == 4 and self._isOmaha then
                        UiManager:showToast(_T("LAB_GAME_036"))
                    end
                end
            end)
        end

        for k, v in ipairs(self.Raises) do
            bee.addValueChanged(v, function(isOn)
                if isOn then
                    self._curRaiseIndex = k
                    self:refreshRaiseValue(true)
                    if k == 4 and self._curRaiseKind == 1 and self._isOmaha then
                        UiManager:showToast(_T("LAB_GAME_036"))
                    end
                end
            end)
        end

        for k, v in ipairs(self.RaiseKinds) do
            bee.addValueChanged(v, function(isOn)
                if isOn then
                    SettingModel:setRaiseKind(k, self._gameType)
                    self._curRaiseKind = k
                    self:refreshBetRaise()
                    self:refreshRaiseValue(true)
                end
            end)
        end
    end

    bee.addClick(self:find("ButtonShowCard/InfoButton", Content), function()
        UiManager:showUI("CommonTextTipRL", {text = _T("LAB_GAME_042"), target = self:find("ButtonShowCard/InfoButton", Content), parent = self.node})
    end)
    bee.addClick(self:find("ButtonCustomize/InfoButton", Content), function()
        UiManager:showUI("CommonTextTipBigRL", {text = _T("LAB_GAME_037"), target = self:find("ButtonCustomize/InfoButton", Content), parent = self.node})
    end)
    bee.addClick(self:find("ButtonPrecise/InfoButton", Content), function()
        UiManager:showUI("CommonTextTipRL", {text = _T("LAB_GAME_041"), target = self:find("ButtonPrecise/InfoButton", Content), parent = self.node})
    end)
    bee.addClick(self:find("ButtonAutoSwitch/InfoButton", Content), function()
        UiManager:showUI("CommonTextTipRL", {text = _T("LAB_GAME_048"), target = self:find("ButtonAutoSwitch/InfoButton", Content), parent = self.node})
    end)
    bee.addClick(self:find("ButtonAutoByin/InfoButton", Content), function()
        UiManager:showUI("CommonTextTipRL", {text = _T("LAB_GAME_049"), target = self:find("ButtonAutoByin/InfoButton", Content), parent = self.node})
    end)

    if self.SliderBet then
        self.BetSlider = UiSliderEx:create(self.SliderBet)
        self.BetSlider:onValueChanged(function(val, step)
            if self._curBetIndex then
                SettingModel:setBetPkValue(self._curBetIndex, step, self._gameType)
                self._isSetBets = true
                self:refreshBetValue()
            end
        end)

        self.RaiseSlider = UiSliderEx:create(self.SliderRaise)
        self.RaiseSlider:onValueChanged(function(val, step)
            if self._curRaiseIndex then
                SettingModel:setRaisePkValue(self._curRaiseIndex, step, self._curRaiseKind, self._gameType)
                self._isSetRaises = true
                self:refreshRaiseValue()
            end
        end)
    end

    bee.onCheck(self.ButtonPreAction, function()
        local flag = not SettingModel:isPreAction()
        SettingModel:setPreAction(flag)
        -- self:setButtonFlag(self.ButtonPreAction, flag)
        bee.logEvent("ingame-menu-setting-pre", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.onCheck(self.ButtonCardValue, function()
        local flag = not SettingModel:isCardValue()
        SettingModel:setCardValue(flag)
        -- self:setButtonFlag(self.ButtonCardValue, flag)
        bee.logEvent("ingame-menu-setting-card-value", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.onCheck(self.ButtonAutoByin, function()
        local flag = not SettingModel:isAutoByin()
        SettingModel:setAutoByin(flag)
        -- self:setButtonFlag(self.ButtonAutoByin, flag)
        Net:sendReq("pb.SetTableFlagREQ", {is_auto_byin = SettingModel:isAutoByin() and 2 or 1})
        bee.logEvent("ingame-menu-setting-autobyin", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.onCheck(self.ButtonShowCard, function()
        local flag = not SettingModel:isShowCard()
        SettingModel:setShowCard(flag)
        -- self:setButtonFlag(self.ButtonShowCard, flag)
        bee.logEvent("ingame-menu-setting-show-card", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.onCheck(self.ButtonShowBB, function()
        local flag = not SettingModel:isShowBB()
        SettingModel:setShowBB(flag)
        -- self:setButtonFlag(self.ButtonShowBB, flag)
        bee.logEvent("ingame-menu-setting-bb", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.onCheck(self.ButtonCustomize, function()
        local flag = not SettingModel:isBetCustomize(self._gameType)
        SettingModel:setBetCustomize(flag, self._gameType)
        -- self:setButtonFlag(self.ButtonCustomize, flag)
        bee.logEvent("ingame-menu-setting-customize-bet", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
        if self.Panel3 then
            self.Panel3:SetActive(SettingModel:isBetCustomize(self._gameType))
        end
    end, true)
    bee.onCheck(self.ButtonAutoSwitch, function()
        local flag = not SettingModel:isAutoSwitch()
        SettingModel:setAutoSwitch(flag)
        -- self:setButtonFlag(self.ButtonAutoSwitch, flag)
        bee.logEvent("ingame-menu-setting-auto-switch", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.onCheck(self.ButtonPrecise, function()
        local flag = not SettingModel:isBetPrecise()
        SettingModel:setBetPrecise(flag)
        -- self:setButtonFlag(self.ButtonPrecise, flag)
        bee.logEvent("ingame-menu-setting-precise-betting", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)

    bee.onCheck(self.ButtonHideInvite, function()
        local flag = not SettingModel:isHideInvite()
        SettingModel:setHideInvite(flag)
        -- self:setButtonFlag(self.ButtonHideInvite, flag)
        bee.logEvent("ingame-menu-setting-invite", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.onCheck(self.ButtonHideChat, function()
        local flag = not SettingModel:isHideChat()
        SettingModel:setHideChat(flag)
        -- self:setButtonFlag(self.ButtonHideChat, flag)
        bee.logEvent("ingame-menu-setting-emoji", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
end

function P:doShowResolution()
    self.FilterMask:SetActive(true)
    self:refreshFilter()

    self._Resolutions = {}
    for k, v in ipairs(Config.Resolutions) do
        v.index = k
        table.insert(self._Resolutions, v)
    end
    table.sort(self._Resolutions, function(a, b)
        if a[1] == b[1] then
            return a[2] > b[2]
        else
            return a[1] > b[1]
        end
    end)
    self.FilterList:setDatas(self._Resolutions)
    self.FilterList:moveToYItem(bee.getResolution())
    self.FilterView.transform.position = self.Filter.transform.position
    local pos = self.FilterView.transform.localPosition
    pos.y = pos.y + (self.FilterView.transform.sizeDelta.y / 2) + 29
    self.FilterView.transform.localPosition = pos
end

function P:refreshFilter()
    local data = Config.Resolutions[bee.getResolution()]
    -- bee.setText(self.TextResolution, string.format("%dx%d", data[1], data[2]))
    bee.setText(self.TextResolution, string.format("%dx%d", CU.Screen.width, CU.Screen.height))
    self.FilterArrow.transform.localScale = self.FilterMask.activeSelf and bee.v3(1, -1, 1) or bee.v3one
end

function P:onHide()
    P.super.onHide(self)
    if self._isSetBets then
        local bets = SettingModel:getBetPkValues(self._gameType)
        local s, val = {}, nil
        for k, v in ipairs(bets) do
            s[#s + 1] = k
            val = self._bet_steps[v]
            s[#s + 1] = string.format("%.2f", val[1] / (val[2] or 1))
        end
        bee.logEvent("ingame-menu-setting-custom-betting", GameModel.data:getGameType(), GameModel.data:getRoomId(), 1, table.concat(s, ","))
    end
    if self._isSetRaises then
        local bets = SettingModel:getRaisePkValues(self._gameType, nil, self._curRaiseKind)
        local s, val = {}, nil
        for k, v in ipairs(bets) do
            s[#s + 1] = k
            val = self._raise_steps[v]
            if type(val) == "table" then
                s[#s + 1] = string.format("%.2f", val[1] / (val[2] or 1))
            else
                s[#s + 1] = tostring(val)
            end
        end
        bee.logEvent("ingame-menu-setting-custom-betting", GameModel.data:getGameType(), GameModel.data:getRoomId(), 2, table.concat(s, ","))
    end
end

function P:refreshBetRaise()
    local bets, raises = SettingModel:getBetPkValues(self._gameType), SettingModel:getRaisePkValues(self._gameType, nil, self._curRaiseKind)
    self._bet_steps, self._raise_steps = SettingModel:getBetStep(self._isOmaha), SettingModel:getRaiseStep(self._isOmaha, self._curRaiseKind)

    self.BetSlider:setStepDatas(self._bet_steps)
    self.RaiseSlider:setStepDatas(self._raise_steps)
    self.BetSlider:setCurStep(bets[self._curBetIndex])
    self.RaiseSlider:setCurStep(raises[self._curRaiseIndex])
    for k, v in ipairs(self.Bets) do
        local betValue = bets[k] or 1
        local valStr = GF.getBetNameStr(self._bet_steps[betValue])
        bee.setText(self:find("On/Text", v), valStr)
        bee.setText(self:find("Off/Text", v), valStr)
    end
    for k, v in ipairs(self.Raises) do
        local raiseValue = raises[k] or 1
        local valStr = GF.getRaiseNameStr(self._raise_steps[raiseValue], self._curRaiseKind)
        bee.setText(self:find("On/Text", v), valStr)
        bee.setText(self:find("Off/Text", v), valStr)
    end
    self:_refreshBetSlider()
    self:_refreshRaiseSlider()
end

function P:_refreshBetSlider()
    local bets = SettingModel:getBetPkValues(self._gameType)
    local minStep, maxStep = nil, nil
    self.BetSlider:setStepRange(minStep, maxStep)
    self.BetSlider:setCurStep(bets[self._curBetIndex], true)
    if self._curBetIndex > 1 then
        minStep = bets[self._curBetIndex - 1] + 1
    end
    if self._curBetIndex < #bets then
        maxStep = bets[self._curBetIndex + 1] - 1
    end
    self.BetSlider:setStepRange(minStep, maxStep)

    if self._curBetIndex == 4 then
        self.BetSlider:setEnable(not self._isOmaha)
    else
        self.BetSlider:setEnable(true)
    end
end

function P:_refreshRaiseSlider()
    local bets = SettingModel:getRaisePkValues(self._gameType, nil, self._curRaiseKind)
    local minStep, maxStep = nil, nil
    self.RaiseSlider:setStepRange(minStep, maxStep)
    self.RaiseSlider:setCurStep(bets[self._curRaiseIndex], true)
    if self._curRaiseIndex > 1 then
        minStep = bets[self._curRaiseIndex - 1] + 1
    end
    if self._curRaiseIndex < #bets then
        maxStep = bets[self._curRaiseIndex + 1] - 1
    end
    self.RaiseSlider:setStepRange(minStep, maxStep)

    if self._curRaiseIndex == 4 and self._curRaiseKind == 1 then
        self.RaiseSlider:setEnable(not self._isOmaha)
    else
        self.RaiseSlider:setEnable(true)
    end
end

function P:refreshBetValue(isSetSlider)
    local bets = SettingModel:getBetPkValues(self._gameType)
    if isSetSlider then
        self:_refreshBetSlider()
    end
    local betValue = bets[self._curBetIndex] or 1
    local valStr = GF.getBetNameStr(self._bet_steps[betValue])
    bee.setText(self:find("On/Text", self.Bets[self._curBetIndex]), valStr)
    bee.setText(self:find("Off/Text", self.Bets[self._curBetIndex]), valStr)
end

function P:refreshRaiseValue(isSetSlider)
    local bets = SettingModel:getRaisePkValues(self._gameType, nil, self._curRaiseKind)
    
    if isSetSlider then
        self:_refreshRaiseSlider()
    end
    local betValue = bets[self._curRaiseIndex] or 1
    local valStr = GF.getRaiseNameStr(self._raise_steps[betValue])
    bee.setText(self:find("On/Text", self.Raises[self._curRaiseIndex]), valStr)
    bee.setText(self:find("Off/Text", self.Raises[self._curRaiseIndex]), valStr)
end

function P:evt_refreshBindEmail()
    if not self.LinkButton then return end

    local email = PlayerModel:getBindEmail()
    if not email or "" == email then
        bee.setText(self.TextEmail, _T("LAB_SETTINGS_037"))
        self.LinkButton:SetActive(true)
    else
        bee.setText(self.TextEmail, _F("LAB_SETTINGS_036", GF.getSecretEmail(email)))
        self.LinkButton:SetActive(false)
    end
end

function P:evt_refreshBindStove()
    self.AccountItemStove:SetActive(PlayerModel:isStoveAccount() and PlayerModel:getStoveGUID() <= 0)
end

function P:evt_lan_mod()
    self:evt_refreshBindEmail()
    bee.setText(self.TextVer, _F("LAB_SETTINGS_018", G_UPDATE_VERSION))
    bee.setText(self.TextFullVer, _F("LAB_SETTINGS_122", G_APP_VERSION))
    if self.TextAccount then
        bee.setText(self.TextAccount, _F("LAB_SETTINGS_032", PlayerModel:getUid()))
    end
    if self.TextDelete then
        bee.setText(self.TextDelete, _T("LAB_SETTINGS_040"))
    end
    self._is_lan_mod = true

    local TAB = self:find("TAB", self.Panel)
    local tabs = {self:find("Tab1Toggle", TAB), self:find("Tab2Toggle", TAB), self:find("Tab3Toggle", TAB), self:find("Tab4Toggle", TAB)}
    local texts = {_T("LAB_SETTINGS_002"), _T("LAB_SETTINGS_003"), _T("LAB_SETTINGS_004"), _T("LAB_TABLE_SETTING")}
    for k, v in ipairs(tabs) do
        bee.setText(self:find("common_panel_black_tab_01_off/TEXT", v), texts[k])
        bee.setText(self:find("common_panel_black_tab_01_on/TEXT", v), texts[k])
    end
end

function P:evt_deleteAccount()
    if self.DeleteButton then
        self.DeleteButton:SetActive(not PlayerModel:isDeleted())
        self.CancelButton:SetActive(PlayerModel:isDeleted())
    end
end

function P:evt_onScreenChanged()
    self:refreshFilter()
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

