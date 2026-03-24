local P = class("LobbyByinDialog", UiDialog)

function P:onAwake()
    self.Panel = self:find("AnimRoot/Center/Panel")

    self.TextTitle = self:find("TextTitle", self.Panel)
    local Buyin = self:find("Buyin", self.Panel)
    self.TextBuyin = self:find("TextBuyin", Buyin)
    self.TextMin = self:find("TextMin", Buyin)
    self.TextMax = self:find("TextMax", Buyin)
    self.ImageArrow = self:find("ingame_blinds_fg_arrow", Buyin)
    self.TextGold = self:find("Chip/TextGold", self.Panel)

    self.Slider = self:find("Slider", self.Panel)
    self.StartButton = self:find("StartButton", self.Panel)
    self.ButtonNoGold = self:find("ButtonNoGold", self.Panel)
    self.PlusButton = self:find("PlusButton", self.Panel)
    self.MinusButton = self:find("MinusButton", self.Panel)
    self.InfoButton = self:find("InfoButton", self.Panel)
    self.CheckToggle = self:find("CheckToggle", self.Panel)

    self.SliderHandle = self:find("Handle Slide Area/Handle", self.Slider)

    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:onBtClose()
    end)
    bee.addClick(self.InfoButton, function()
        UiManager:showUI("CommonTextTipUD", {text = _T("LAB_GAME_020"), target = self.InfoButton})
    end)
    bee.addClick(self.StartButton, function()
        if self._params.isReby then
            Net:sendReq("pb.RebyREQ", {
                is_reby = true,
                chips = tpl_constdata.PokerBuyinStep[self._curStep] * self._params.data.bb,
            })
        elseif self._params.isSetReby then
            Net:sendReq("pb.SetRebyREQ", {
                reby_chips = tpl_constdata.PokerBuyinStep[self._curStep] * self._params.data.bb,
            })
        else
            if GuideManager:isInGuide() then
                Net:setRecver(require("app.server.GameServer"):create())
            end
            local params = {
                boot = self._params.data.bb, 
                game_type = self._params.data.gameType, 
                lobby_coin = GPropId.Gold,
                byin_chips = tpl_constdata.PokerBuyinStep[self._curStep] * self._params.data.bb,
                wait_blind = not bee.isCheck(self.CheckToggle),
                ip = PlayerModel:getIP(),
            }
            Net:sendReq("pb.QuickStartREQ", params)
            LocalStore:setBoolForKey("poker_pay_bb_byin", bee.isCheck(self.CheckToggle))
            LocalStore:setIntegerForKey(self:getLobbyByinStepKey(), self._curStep)
        end
        self:hideUI()
    end)
    bee.addClick(self.ButtonNoGold, function()
        -- if PlayerModel:getGold() < self._params.data.min_byin then
        --     UiManager:showToast(_T("LAB_SMALL_THAN_BUYIN"))
        -- else
        --     UiManager:showToast(_T("LAB_GOLD_LACK"))
        -- end
        UiManager:showToast(_T("LAB_GOLD_LACK"))
    end)
    bee.addClick(self.PlusButton, function()
        if self._curStep < #tpl_constdata.PokerBuyinStep then
            self:setCurStep(self._curStep + 1)
            self:refreshSlide()
        end
        bee.logEvent("ingame-table-addchips", self._params.data.gameType)
    end)
    bee.addClick(self.MinusButton, function()
        if self._curStep > 1 then
            self:setCurStep(self._curStep - 1)
            self:refreshSlide()
        end
    end)

    self._stepNum = #tpl_constdata.PokerBuyinStep
    self._step = 1 / (self._stepNum * 2 - 2)
    self._curStep = 1
    
    bee.addValueChanged(self.Slider, function(value)
        local step = math.floor(value / self._step)
        self:setCurStep(math.floor((step + 1) / 2) + 1)
        
        local p1 = self.ImageArrow.transform.position
        p1.x = self.SliderHandle.transform.position.x
        self.ImageArrow.transform.position = p1
    end,"Slider")
end

function P:onShow()
    local step = 1
    for k, v in ipairs(tpl_constdata.PokerBuyinStep) do
        if v == 50 then
            if PlayerModel:getGold() >= v * self._params.data.bb then
                step = k
            end
            break
        end
    end

    bee.setText(self.TextMin, _N(self._params.data.min_byin))
    bee.setText(self.TextMax, _N(self._params.data.max_byin))
    bee.setTextGold(self.TextGold, _N(PlayerModel:getGold()))

    if self._params and (self._params.isReby or self._params.isSetReby) then
        self.InfoButton:SetActive(false)
        self.CheckToggle:SetActive(false)

        if self._params.isSetReby then
            bee.setText(self.TextTitle, _T("LAB_GAME_026"))
            bee.setText(self:find("Text", self.StartButton), _T("LAB_GAME_027"))
            bee.setText(self:find("Text", self.ButtonNoGold), _T("LAB_GAME_027"))

            for k, v in ipairs(tpl_constdata.PokerBuyinStep) do
                if v == GameModel.data:getDelayRebyChips() then
                    step = k
                    break
                end
            end
        end
    else
        bee.setCheck(self.CheckToggle, nil, LocalStore:getBoolForKey("poker_pay_bb_byin", true))

        local key = self:getLobbyByinStepKey()
        local lastStep = LocalStore:getIntegerForKey(key, 0)
        if lastStep >= 1 then
            for k, v in ipairs(tpl_constdata.PokerBuyinStep) do
                if k == lastStep then
                    if PlayerModel:getGold() >= v * self._params.data.bb then
                        step = k
                    end
                    break
                end
            end
        end
    end

    self:setCurStep(step)
    self:refreshSlide()
end

function P:getLobbyByinStepKey()
    return "lobby_byin_step_" .. self._params.data.gameType .. "_" .. self._params.data.bb .. "_" .. PlayerModel:getUid()
end

function P:refreshSlide()
    bee.setSliderValue(self.Slider, (self._curStep - 1) / (self._stepNum - 1), true)
end

function P:setCurStep(step)
    self._curStep = step
    local gold = tpl_constdata.PokerBuyinStep[self._curStep] * self._params.data.bb
    bee.setText(self.TextBuyin, _N(gold))

    self.StartButton:SetActive(PlayerModel:getGold() >= gold)
    self.ButtonNoGold:SetActive(PlayerModel:getGold() < gold)
    self.PlusButton:SetActive(self._curStep ~= #tpl_constdata.PokerBuyinStep)
    self.MinusButton:SetActive(self._curStep ~= 1)
end

function P:onBtClose()
    if self._params.isReby then
        Net:sendReq("pb.LeaveRoomREQ", {})
    elseif self._params.isSetReby then
    else
        UiManager:showUI("OmahaBlinds", {data = self._params.data, gameType = self._params.data.gameType})
    end
    self:hideUI()
end

function P:evt_DealerInfoRSP()
    if self._params and self._params.isSetReby then
        self:hideUI()
    end
end

function P:evt_TableGameOverRSP()
    if self._params and self._params.isSetReby then
        self:hideUI()
    end
end

