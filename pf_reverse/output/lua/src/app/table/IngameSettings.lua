local P = class("IngameSettings", UiDialog)

function P:onAwake()
    local Panel = self:find("AnimRoot/Center/Panel")
    local Content = self:find("SettingList/Viewport/Content", Panel)
    if bee.isNull(Content) then
        Content = Panel
    end

    local Panel1 = self:find("Panel1", Content)
    local Panel2 = self:find("Panel2", Content)
    self.Panel3 = self:find("Panel3", Content)

    self.ButtonPreAction = self:find("ButtonPreAction", Panel1)
    self.SETTINGAutoByin = self:find("SETTINGAutoByin", Panel1)
    self.ButtonAutoByin = self:find("ButtonAutoByin", Panel1)
    self.ButtonShowBB = self:find("ButtonShowBB", Panel1)
    self.ButtonShowCard = self:find("ButtonShowCard", Panel1)
    self.ButtonCustomize = self:find("ButtonCustomize", Panel1)
    self.ButtonPrecise = self:find("ButtonPrecise", Panel1)

    self.ButtonMusic = self:find("ButtonMusic", Panel2)
    self.ButtonSound = self:find("ButtonSound", Panel2)
    self.ButtonVoice = self:find("ButtonVoice", Panel2)
    self.ButtonVibrite = self:find("ButtonVibrite", Panel2)
    self.ButtonSaveGame = self:find("ButtonSaveGame", Panel2)
    self.ButtonHideChat = self:find("ButtonHideChat", Panel2)

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
                    SettingModel:setRaiseKind(k)
                    self._curRaiseKind = k
                    self:refreshBetRaise()
                    self:refreshRaiseValue(true)
                end
            end)
        end
    end

    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("InfoButton1", Panel1), function()
        UiManager:showUI("CommonTextTipUD", {text = _T("LAB_GAME_042"), target = self:find("InfoButton1", Panel1), parent = self.node})
    end)
    bee.addClick(self:find("InfoButton2", Panel1), function()
        UiManager:showUI("CommonTextTipBigRL", {text = _T("LAB_GAME_037"), target = self:find("InfoButton2", Panel1), parent = self.node})
    end)
    bee.addClick(self:find("InfoButton3", Panel1), function()
        UiManager:showUI("CommonTextTipUD", {text = _T("LAB_GAME_041"), target = self:find("InfoButton3", Panel1), parent = self.node})
    end)

    if self.SliderBet then
        self.BetSlider = UiSliderEx:create(self.SliderBet)
        self.BetSlider:onValueChanged(function(val, step)
            if self._curBetIndex then
                if self._isOmaha then
                    SettingModel:setBetOmahaValue(self._curBetIndex, step)
                else
                    SettingModel:setBetPkValue(self._curBetIndex, step)
                end
                self._isSetBets = true
                self:refreshBetValue()
            end
        end)

        self.RaiseSlider = UiSliderEx:create(self.SliderRaise)
        self.RaiseSlider:onValueChanged(function(val, step)
            if self._curRaiseIndex then
                if self._isOmaha then
                    SettingModel:setRaiseOmahaValue(self._curRaiseIndex, step, self._curRaiseKind)
                else
                    SettingModel:setRaisePkValue(self._curRaiseIndex, step, self._curRaiseKind)
                end
                self._isSetRaises = true
                self:refreshRaiseValue()
            end
        end)
    end
end

function P:onStart()
    bee.addClick(self.ButtonPreAction, function()
        local flag = not SettingModel:isPreAction()
        SettingModel:setPreAction(flag)
        self:setButtonFlag(self.ButtonPreAction, flag)
        bee.logEvent("ingame-menu-setting-pre", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonAutoByin, function()
        local flag = not SettingModel:isAutoByin()
        SettingModel:setAutoByin(flag)
        self:setButtonFlag(self.ButtonAutoByin, flag)
        Net:sendReq("pb.SetTableFlagREQ", {is_auto_byin = SettingModel:isAutoByin() and 2 or 1})
        bee.logEvent("ingame-menu-setting-autobyin", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonShowCard, function()
        local flag = not SettingModel:isShowCard()
        SettingModel:setShowCard(flag)
        self:setButtonFlag(self.ButtonShowCard, flag)
        bee.logEvent("ingame-menu-setting-show-card", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonShowBB, function()
        local flag = not SettingModel:isShowBB()
        SettingModel:setShowBB(flag)
        self:setButtonFlag(self.ButtonShowBB, flag)
        bee.logEvent("ingame-menu-setting-bb", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonCustomize, function()
        local flag = not SettingModel:isBetCustomize()
        SettingModel:setBetCustomize(flag)
        self:setButtonFlag(self.ButtonCustomize, flag)
        bee.logEvent("ingame-menu-setting-customize-bet", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
        if self.Panel3 then
            self.Panel3:SetActive(SettingModel:isBetCustomize())
        end
    end, true)
    bee.addClick(self.ButtonPrecise, function()
        local flag = not SettingModel:isBetPrecise()
        SettingModel:setBetPrecise(flag)
        self:setButtonFlag(self.ButtonPrecise, flag)
        bee.logEvent("ingame-menu-setting-precise-betting", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)

    bee.addClick(self.ButtonMusic, function()
        local flag = not SettingModel.saveData.ingameBGMOn
        SettingModel.saveData.ingameBGMOn = flag
        SettingModel:onSave()
        self:setButtonFlag(self.ButtonMusic, flag)

        if bee.isInGame() then
            if flag then
                Game:playIngameBGM()
            else
                Game:stopMusic()
            end
        end
        bee.logEvent("ingame-menu-setting-music", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonSound, function()
        local flag = not SettingModel.saveData.soundVolumeOn
        SettingModel.saveData.soundVolumeOn = flag
        SettingModel:onSave()
        self:setButtonFlag(self.ButtonSound, flag)
        bee.logEvent("ingame-menu-setting-sound-effects", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonVoice, function()
        local flag = not SettingModel.saveData.roleInVolumeOn
        SettingModel.saveData.roleInVolumeOn = flag
        SettingModel:onSave()
        self:setButtonFlag(self.ButtonVoice, flag)
        bee.logEvent("ingame-menu-setting-char-voice", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonVibrite, function()
        -- local flag = not VibrateManager:isOn()
        -- VibrateManager:setIsOn(flag)
        local flag = not SettingModel:isCanVibrate(VibrateKind.InGame)
        SettingModel:setIsCanVibrate(VibrateKind.InGame, flag)
        self:setButtonFlag(self.ButtonVibrite, flag)
        bee.logEvent("ingame-menu-setting-vibration", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonSaveGame, function()
        local flag = not SettingModel:isHideInvite()
        SettingModel:setHideInvite(flag)
        self:setButtonFlag(self.ButtonSaveGame, flag)
        bee.logEvent("ingame-menu-setting-invite", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
    bee.addClick(self.ButtonHideChat, function()
        local flag = not SettingModel:isHideChat()
        SettingModel:setHideChat(flag)
        self:setButtonFlag(self.ButtonHideChat, flag)
        bee.logEvent("ingame-menu-setting-emoji", GameModel.data:getGameType(), GameModel.data:getRoomId(), flag and 1 or 0)
        Game:playSound("ui_button_disabled")
    end, true)
end

function P:onShow()
    self:setButtonFlag(self.ButtonPreAction, SettingModel:isPreAction())
    self:setButtonFlag(self.ButtonAutoByin, SettingModel:isAutoByin())
    self:setButtonFlag(self.ButtonShowCard, SettingModel:isShowCard())
    self:setButtonFlag(self.ButtonShowBB, SettingModel:isShowBB())
    self:setButtonFlag(self.ButtonCustomize, SettingModel:isBetCustomize())
    self:setButtonFlag(self.ButtonPrecise, SettingModel:isBetPrecise())
    self:setButtonFlag(self.ButtonMusic, SettingModel.saveData.ingameBGMOn)
    self:setButtonFlag(self.ButtonSound, SettingModel.saveData.soundVolumeOn)
    self:setButtonFlag(self.ButtonVoice, SettingModel.saveData.roleInVolumeOn)
    self:setButtonFlag(self.ButtonVibrite, SettingModel:isCanVibrate(VibrateKind.InGame))
    self:setButtonFlag(self.ButtonSaveGame, SettingModel:isHideInvite())
    self:setButtonFlag(self.ButtonHideChat, SettingModel:isHideChat())

    if self.Panel3 then
        self.Panel3:SetActive(SettingModel:isBetCustomize())
    end

    self._isOmaha = false
    if GameModel.data then
        self._isOmaha = GameModel.data:isOmaha()
        
        if GameModel.data:isTournament() and self.SETTINGAutoByin then
            self.SETTINGAutoByin:SetActive(false)
            self.ButtonAutoByin:SetActive(false)
        end
    end

    if self.BetSlider then
        self._curBetIndex = 1
        self._curRaiseIndex = 1
        self._curRaiseKind = SettingModel:getRaiseKind(true)
        if self.RaiseKinds then
            bee.setCheck(self.RaiseKinds[self._curRaiseKind])
        end

        self:refreshBetRaise()
    end
end

function P:onHide()
    P.super.onHide(self)
    if self._isSetBets then
        local bets = SettingModel:getBetPkValues(self._isOmaha)
        local s, val = {}, nil
        for k, v in ipairs(bets) do
            s[#s + 1] = k
            val = self._bet_steps[v]
            s[#s + 1] = string.format("%.2f", val[1] / (val[2] or 1))
        end
        bee.logEvent("ingame-menu-setting-custom-betting", GameModel.data:getGameType(), GameModel.data:getRoomId(), 1, table.concat(s, ","))
    end
    if self._isSetRaises then
        local bets = SettingModel:getRaisePkValues(self._isOmaha, nil, self._curRaiseKind)
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
    local bets, raises = SettingModel:getBetPkValues(self._isOmaha), SettingModel:getRaisePkValues(self._isOmaha, nil, self._curRaiseKind)
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
    local bets = self._isOmaha and SettingModel:getBetOmahaValues() or SettingModel:getBetPkValues()
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
    local bets = SettingModel:getRaisePkValues(self._isOmaha, nil, self._curRaiseKind)
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
    local bets = self._isOmaha and SettingModel:getBetOmahaValues() or SettingModel:getBetPkValues()
    if isSetSlider then
        self:_refreshBetSlider()
    end
    local betValue = bets[self._curBetIndex] or 1
    local valStr = GF.getBetNameStr(self._bet_steps[betValue])
    bee.setText(self:find("On/Text", self.Bets[self._curBetIndex]), valStr)
    bee.setText(self:find("Off/Text", self.Bets[self._curBetIndex]), valStr)
end

function P:refreshRaiseValue(isSetSlider)
    local bets = SettingModel:getRaisePkValues(self._isOmaha, nil, self._curRaiseKind)
    
    if isSetSlider then
        self:_refreshRaiseSlider()
    end
    local betValue = bets[self._curRaiseIndex] or 1
    local valStr = GF.getRaiseNameStr(self._raise_steps[betValue])
    bee.setText(self:find("On/Text", self.Raises[self._curRaiseIndex]), valStr)
    bee.setText(self:find("Off/Text", self.Raises[self._curRaiseIndex]), valStr)
end

function P:setButtonFlag(button, isOn)
    if button then
        self:find("common_switch_off_01", button):SetActive(not isOn)
        self:find("common_switch_on_01", button):SetActive(isOn)
    end
end

function P:evt_hideUiWhenAction(isVisible)
    self:onUiBlur(not isVisible, "evt_hideUiWhenAction", true)
end

return P