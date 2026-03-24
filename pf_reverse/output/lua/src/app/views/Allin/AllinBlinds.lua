local P = class("AllinBlinds", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)

    self.StartButton = self:find("StartButton", self.Panel)
    self.NoGoldButton = self:find("NoGoldButton", self.Panel)
    self.TextTime = self:find("TextTime", self.Panel)

    local Blinds = self:find("Blinds", self.Panel)
    self.TextByin = self:find("TextByin", Blinds)
    self.TextBlind = self:find("TextBlind", Blinds)
    self.ImageArrow = self:find("ImageArrow", Blinds)

    self.Slider = self:find("Slider", self.Panel)
    self.MinusButton = self:find("MinusButton", self.Slider)
    self.PlusButton = self:find("PlusButton", self.Slider)

    local Currency = self:find("Currency", self.RightTop)
    self.TextGold = self:find("Gold/TextGold", Currency)
    self.TextTick1 = self:find("Ticket1/TextTick1", Currency)
    
    self.Currency = self:find("Currency", self.Panel)
    self.Items = {
        PropItem:create(self:find("Item1", self.Currency)),
        PropItem:create(self:find("Item2", self.Currency)),
        PropItem:create(self:find("Item3", self.Currency)),
    }
    
    self.ItemTypes = {
        {GPropId.FirePower},
        {GPropId.Exp},
        {GPropId.Bond, {tpl_constdata.Bondcap}},
    }
    for k, v in ipairs(self.ItemTypes) do
        bee.addClick(self.Items[k].node, function()
            UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(v[1], true), format = v[2], target = self.Items[k].node})
        end)
    end

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:hideUI()
    end)
    bee.addClick(self:find("SettingButton", self.RightTop), function()
        UiManager:showUI("AllinSettings")
    end)
    bee.addClick(self.StartButton, function()
        local data = self.BlindSlider:getCurData()
        local params = {
            boot = data.bb, 
            game_type = data.gameType, 
            lobby_coin = GPropId.Gold,
            byin_chips = data.byin,
        }
        Net:sendReq("pb.QuickStartREQ", params)
    end)
    bee.addClick(self.NoGoldButton, function()
        local data = self._datas[1]
        if PlayerModel:getGold() < data.byin then
            UiManager:showToast(_T("LAB_GOLD_LACK"))
        else
            UiManager:showToast(_T("LAB_SMALL_THAN_BUYIN"))
        end
    end)
    bee.addClick(self.MinusButton, function()
        self.BlindSlider:setCurStep(self.BlindSlider:getCurStep() - 1)
    end)
    bee.addClick(self.PlusButton, function()
        self.BlindSlider:setCurStep(self.BlindSlider:getCurStep() + 1)
    end)

    self.BlindSlider = UiSliderEx:create(self.Slider)
    self.BlindSlider:onValueChanged(function(val)
        bee.setText(self.TextBlind, _N(val.sb) .. "/" .. _N(val.bb))
        bee.setText(self.TextByin, _N(val.byin))
        self:refreshButton()

        local pos = self.ImageArrow.transform.position
        pos.x = self.BlindSlider.ImageHandle.transform.position.x
        self.ImageArrow.transform.position = pos
    end)
    self.BlindSlider:setStepDatas(tpl_table_poker_allin_list)
end

function P:onShow()
    bee.setTextGold(self.TextGold, _N(PlayerModel:getGold()))
    bee.setTextGold(self.TextTick1, _N(ItemModel:getItemNumById(GPropId.TicketDraw)))

    self._datas = tpl_table_poker_allin_list
    local step = 1
    for i = #self._datas, 1, -1 do
        if PlayerModel:getGold() >= self._datas[i].recommend then
            step = i
            break
        end
    end
    self.BlindSlider:setCurStep(step)

    self.Currency:SetActive(false)
    bee.setText(self.TextTime, "")
    Net:sendReq("pb.RoomWinnerRewardsInfoREQ", {
        game_type = GAME_GAME_TYPE.LOBBY_HOLDEM_ALLIN,
    })
    Net:sendReq("pb.GetAllinGameTimeREQ", {})
end

function P:refreshButton()
    self.MinusButton:SetActive(self.BlindSlider:getCurStep() > 1)
    self.PlusButton:SetActive(self.BlindSlider:getCurStep() < #tpl_table_poker_allin_list)

    local flag = PlayerModel:getGold() >= self.BlindSlider:getCurData().byin
    self.StartButton:SetActive(flag)
    self.NoGoldButton:SetActive(not flag)

    self:refreshRewardItems()
end

function P:refreshRewardItems()
    if self.reward_list then
        for _, v in ipairs(self.reward_list) do
            if v.room_lvl == self.BlindSlider:getCurStep() then
                local item = ItemModel:getItem(GPropId.FirePower, true)
                item.num = v.fire_power
                self.Items[1]:setData(item)
                
                self.Items[2].node:SetActive(v.win_exp > 0)
                if v.win_exp > 0 then
                    item = ItemModel:getItem(GPropId.Exp, true)
                    item.num = v.win_exp
                    self.Items[2]:setData(item)
                end

                self.Items[3].node:SetActive(v.bond_add > 0)
                if v.bond_add > 0 then
                    item = ItemModel:getItem(GPropId.Bond, true)
                    item.num = v.bond_add
                    self.Items[3]:setData(item)
                end
                break
            end
        end
    end
end

function P:refreshTime(msg)
    local curTime = bee.getServerTime()
    if msg.end_time <= curTime then
        bee.setText(self.TextTime, _T("LAB_ALLIN_12"))
    elseif msg.start_time > bee.getServerTime() then
        bee.setText(self.TextTime, _T("LAB_ALLIN_13") .. TimeHelp:getDateTimeStr(msg.start_time) .. " -- " .. TimeHelp:getDateTimeStr(msg.end_time))
    else
        local dt = msg.end_time - curTime
        if dt >= 86400 then
            bee.setText(self.TextTime, _T("LAB_ALLIN_07") .. _F("LAB_ALLIN_05", math.floor(dt / 86400), math.floor((dt % 86400) / 3600)))
        elseif dt >= 3600 then
            bee.setText(self.TextTime, _T("LAB_ALLIN_07") .. _F("LAB_ALLIN_04", math.floor(dt / 3600), math.floor((dt % 3600) / 60)))
        else
            bee.setText(self.TextTime, _T("LAB_ALLIN_07") .. _F("LAB_ALLIN_03", math.floor(dt / 60), dt % 60))
        end
    end
end

function P:evt_RoomWinnerRewardsInfoRSP(msg)
    self.Currency:SetActive(true)
    self.reward_list = msg.reward_list
    self:refreshRewardItems()
end

function P:evt_GetAllinGameTimeRSP(msg)
    self:refreshTime(msg)
    self:schedule(1, function()
        self:refreshTime(msg)
    end)
end

