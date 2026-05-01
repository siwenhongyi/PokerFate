local P = class("DevelopmentFund", UiFullView)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)

    self.Amount = self:find("Amount", self.Panel)
    self.Off = self:find("Off", self.Amount)
    self.On = self:find("On", self.Amount)

    self.development_fund_bg_uip = self:find("development_fund_bg_uip", self.Panel)
    self.development_fund_bg2_uip = self:find("development_fund_bg2_uip", self.Panel)

    self.Bubble = self:find("Bubble", self.Panel)
    self.TextAmount = self:find("Item/TextAmount", self.Bubble)
    self.TextTime = self:find("Time/TextTime", self.Panel)

    self.FundLevel = self:find("FundLevel", self.Panel)
    self.LV1 = self:find("Slider/LV1", self.FundLevel)
    self.LV2 = self:find("Slider/LV2", self.FundLevel)
    self.LV3 = self:find("Slider/LV3", self.FundLevel)
    self.TextReset = self:find("Slider/TextReset", self.FundLevel)
    self.TextResult = self:find("Slider/TextResult", self.FundLevel)
    self.Progress = self:find("Progress", self.FundLevel)

    self.Fgs = {}
    for i = 1, 50 do
        self.Fgs[i] = self:find("fg" .. i, self.Progress)
    end

    bee.addClick2(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick2(self:find("Title/InfoButton", self.Panel), function()
        Game:playSound("ui_button_confirm")
        table.sort(self._data.levels, function(a, b)
            return a.level < b.level
        end)
        local levels = self._data.levels
        UiManager:showUI("CommonRules", {text = _F("REBATE_RULES_1", 
            string.format("%.1f", levels[1].rewards_lower_ratio / 100), 
            string.format("%.1f", levels[1].rewards_upper_ratio / 100), 
            string.format("%.1f", levels[2].rewards_lower_ratio / 100), 
            string.format("%.1f", levels[2].rewards_upper_ratio / 100), 
            string.format("%.1f", levels[3].rewards_lower_ratio / 100), 
            string.format("%.1f", levels[3].rewards_upper_ratio / 100)
        )})
    end)

    bee.addClick2(self:find("MatchButton", self.Panel), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("OmahaBlinds", {gameType = GAME_GAME_TYPE.LOBBY_HOLDEM_GAME})
    end)

    bee.setText(self:find("TextLevel", self.LV1), _F("LAB_PLAY_REBATE_3", 1))
    bee.setText(self:find("TextLevel", self.LV2), _F("LAB_PLAY_REBATE_3", 2))
    bee.setText(self:find("TextLevel", self.LV3), _F("LAB_PLAY_REBATE_3", 3))

    if LAN:getLanguage() ~= "en" then
        local development_fund_title_en = self:find("Title/development_fund_title_en", self.Panel)
        local pos = development_fund_title_en.transform.localPosition
        pos.y = pos.y - 40
        development_fund_title_en.transform.localPosition = pos
    else
        self:find("Title/InfoButton", self.Panel).transform.localPosition = bee.v3(129, 43)
    end
end

function P:onShow()
    local pencent = tpl_play_rebate[2].to_ser / tpl_play_rebate[3].to_ser
    local index = math.floor(pencent * 100 / 2) + 1
    if self.Fgs[index] then
        local development_fund_slider_powder_fg = self:find("Slider/development_fund_slider_powder_fg", self.FundLevel)
        local pos = development_fund_slider_powder_fg.transform.position
        pos.x = self.Fgs[index].transform.position.x
        development_fund_slider_powder_fg.transform.position = pos
    end

    if not ClientDataModel:getData("play_DevelopmentFund_story") then
        ClientDataModel:setData("play_DevelopmentFund_story", 1)
        UiManager:showUI("Story", {name = tpl_constdata.Play_Rebate_Story, hideCb = function()
            self._isInStory = false
            self:refreshUI()
        end})

        self._isInStory = true
    end

    self._data = {
        status = 0,
        expires_in =  0,
        expires_st = os.time(),
        reward = 0,
        total_flow =  0,
        user_flow =  0,
        rewards_lower_ratio = 0,
        rewards_upper_ratio = 0,
        participate_conditions = tpl_play_rebate_info[1].participate_conditions,
        levels = {
            {
                level = 1,
                rewards_lower_ratio = 80,
                rewards_upper_ratio = 800
            },
            {
                level = 2,
                rewards_lower_ratio = 100,
                rewards_upper_ratio = 1000
            },
            {
                level = 3,
                rewards_lower_ratio = 120,
                rewards_upper_ratio = 1200
            }

        },
    }

    self:refreshUI()
    self:reqData()

    self:schedule(1, function()
        self:refreshTime()
    end)
end

function P:reqData(cb)
    if self._waitTag then
        scheduler:removeTag(self._waitTag)
    end
    Net:post("/activity/rebate", {t = 1, immediately = true}, function(data)
        if data.code == 0 then
            ClientDataModel._fundStatus = data.status
            ClientDataModel:refreshReddot()
        end
        if not bee.isNull(self.node) and data.code == 0 then
            self._data = data
            self._data.expires_st = os.time()
            self._reqData = false
            if cb then
                cb()
            else
                self:refreshUI()
            end
        end
    end)
end

function P:refreshUI()
    self:refreshTime()
    self:refreshProgress()
end

function P:refreshTime()
    if self._data.expires_in > 0 then
        local dt = self._data.expires_in - (os.time() - self._data.expires_st)
        if dt <= 0 then
            dt = 0
            if not self._reqData then
                self._reqData = true
                self:reqData()
            end
        end
        
        bee.setText(self.TextTime, _F("LAB_PLAY_REBATE_5", TimeHelp:getTimeLeftStr(dt, true)))
    else
        bee.setText(self.TextTime, "")
    end
end

function P:refreshProgress()
    local isLock = self._data.user_flow < self._data.participate_conditions
    local imgs = {"Development[development_fund_slider_blue_fg]", "Development[development_fund_slider_powder_fg]", "Development[development_fund_slider_yellow_fg]"}
    local amount = self._data.total_flow
    local pencent = amount / tpl_play_rebate[3].to_ser
    if pencent > 1 then pencent = 1 end
    local index = math.floor(pencent * 100 / 2)
    if index < pencent * 100 / 2 then index = index + 1 end

    local lvl, d = 0, tpl_play_rebate_list[1]
    for k = #tpl_play_rebate_list, 1, -1 do
        local v = tpl_play_rebate_list[k]
        if amount >= v.to_ser then
            lvl = v.level
            d = v
            break
        end
    end

    local img = imgs[lvl] or imgs[1]
    for k, v in ipairs(self.Fgs) do
        v:SetActive(k <= index)
        if k <= index then
            bee.setIcon(v, img)
        end
    end

    if not isLock and self._data.start_time and LocalStore:getIntegerForKey("development_fund_id") ~= self._data.start_time then
        if not self._isInStory then
            LocalStore:setIntegerForKey("development_fund_id", self._data.start_time)
            self:refreshLockInfo(true)
            self:find("Eff_poker_Ui_Development_js01", self.Amount):SetActive(false)
            self:find("Eff_poker_Ui_Development_js01", self.Amount):SetActive(true)
            self:once(0.5, function()
                self:refreshLockInfo(isLock)
            end)
        else
            self:refreshLockInfo(not isLock)
        end
    else
        self:refreshLockInfo(isLock)
    end

    self.development_fund_bg_uip:SetActive(lvl < 3)
    self.development_fund_bg2_uip:SetActive(lvl >= 3)

    self.LV1:SetActive(lvl == 1 and self._data.status == 0)
    self.LV2:SetActive(lvl == 2 and self._data.status == 0)
    self.LV3:SetActive(lvl == 3 and self._data.status == 0)
    self.TextReset:SetActive(false)
    self.TextResult:SetActive(self._data.status == 1 or self._data.status == 2)
    if self._data.status == 1 then
        if self._isInStory then
            return
        end
        local reward = self._data.reward
        self:once(1, function()
            if reward and reward <= 0 then
                return
            end
            UiManager:showUI("DevelopmentFundReward", {reward = reward, hideCb = function()
                self.TextReset:SetActive(true)
                self.TextResult:SetActive(false)
                self:once(1, function()
                    self:reqData(function()
                        self:find("Eff_poker_Ui_Development_js02", self.Amount):SetActive(false)
                        self:find("Eff_poker_Ui_Development_sx", self.FundLevel):SetActive(false)
                        self:find("Eff_poker_Ui_Development_js02", self.Amount):SetActive(true)
                        self:find("Eff_poker_Ui_Development_sx", self.FundLevel):SetActive(true)
                        self:once(0.5, function()
                            self:refreshUI()
                        end)
                    end)
                end)
                self:showTextSignAnim(self.TextReset, _T("LAB_PLAY_REBATE_12"))
            end})
        end)

        -- self:showTextSignAnim(self.TextResult, _T("LAB_PLAY_REBATE_13"))
    elseif self._data.status == 2 then
        self:showTextSignAnim(self.TextResult, _T("LAB_PLAY_REBATE_13"))
        self:waitReward()
    end
end

function P:refreshLockInfo(isLock)
    self.Off:SetActive(isLock)
    self.On:SetActive(not isLock)
    self.Bubble:SetActive(not isLock)
    if isLock then
        bee.setText(self:find("TextNeedCount", self.Off), "" .. _N(self._data.user_flow) .. "/" .. _N(self._data.participate_conditions))
    else
        bee.setText(self.TextAmount, _N(self._data.user_flow))
        bee.setText(self:find("Item/TextNum1", self.On), _N(math.floor(self._data.user_flow * self._data.rewards_lower_ratio / 10000)))
        bee.setText(self:find("Item/TextNum2", self.On), _N(math.floor(self._data.user_flow * self._data.rewards_upper_ratio / 10000)))
    end
end

function P:waitReward()
    if self._waitTag then
        scheduler:removeTag(self._waitTag)
    end
    self._waitTag = self:once(30, function()
        self._waitTag = nil
        self:reqData(function()
            if self._data.status == 2 then
                self:waitReward()
            else
                self:refreshUI()
            end
        end)
    end)
end

function P:showTextSignAnim(TEXT, text)
    local key = "showActTag"
    if self[key] then
        scheduler:removeTag(self[key])
    end
    if TEXT then
        local signs = {".", "..", "...", ""}
        local idx = 1
        self[key] = self:schedule(1, function()
            bee.setText(TEXT, text .. signs[idx])
            idx = idx + 1
            if idx > #signs then
                idx = 1
            end
        end)
    end
end

function P:evt_developmentFund_refresh()
    self:reqData()
end

return P