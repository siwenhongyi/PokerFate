local P = class("TournamentMTTRebuy", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    local Panel = self:find("Center/Panel", self.AnimRoot)
    self.Main = self:find("Main", Panel)
    self.Normal = self:find("Normal", self.Main)
    self.Multiples = self:find("Multiples", self.Main)

    self.TextTime = self:find("TextTime", Panel)
    self.TextCount = self:find("TextCount", Panel)

    self.ConfirmButton = self:find("btn/ConfirmButton", Panel)
    self.CancleButton = self:find("btn/CancleButton", Panel)

    -- 倍数选择 (1x/2x/3x)
    self.MultiplierGroup = self:find("MultiplierGroup", Panel)
    self.Tabs = {
        self:find("Chip/MultiplesRebuy/1x", self.Multiples),
        self:find("Chip/MultiplesRebuy/2x", self.Multiples),
        self:find("Chip/MultiplesRebuy/3x", self.Multiples),
    }
    for k, v in ipairs(self.Tabs) do
        bee.onCheck(v, function()
            if not self._detailMsg then
                self:once(-1, function()
                    bee.setCheck(self.Tabs[self._multiplier], true, true)
                end)
                return
            end
            local num = self.reby_multiple[k]
            if -1 ~= self._detailMsg.left_reby_times and self._detailMsg.left_reby_times < num then
                UiManager:showToast(_F("LAB_TOURNAMENT_MTT_INFO124", self._detailMsg.left_reby_times, self._mttInfo.reby_time_limit))
                self:once(-1, function()
                    bee.setCheck(self.Tabs[self._multiplier], true, true)
                end)
                return
            end
            self._multiplier = k
            self:refreshConfigUI()
        end)
    end

    bee.addClick(self:find("CloseButton", Panel), function()
        self:onBtClose()
    end)
    bee.addClick(self.ConfirmButton, function()
        self:onClickConfirm()
    end)
    bee.addClick(self.CancleButton, function()
        self:onBtClose()
    end)
    
    self._multiplier = 1
end

function P:onShow()
    self._mttInfo = GameModel.data and GameModel.data.room_info
    self._signItem, self._itemData = TournamentModel:getSignItem(self._mttInfo or {})

    self.reby_multiple = self._mttInfo and self._mttInfo.reby_multiple or {1, 3}
    table.sort(self.reby_multiple)
    for k, v in ipairs(self.reby_multiple) do
        bee.setText(self:find("Text", self.Tabs[k]), "" .. v .. "x")
        self.Tabs[k]:SetActive(true)
    end
    for i = #self.reby_multiple + 1, #self.Tabs do
        self.Tabs[i]:SetActive(false)
    end

    Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})

    self:refreshConfigUI()

    -- 定时检查截止时间
    local i = 0
    self:schedule(1, function()
        self:refreshDeadline()
        i = i + 1
        if i % 3 == 0 then
            Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})
        end
    end)
    self:refreshDeadline()

    if self._signItem and self._signItem.item_id == GPropId.Gold and self._signItem.item_num > PlayerModel:getGold() then
        QuickByModel:checkInsideGame(GameModel.data:getGameType(), self._mttInfo.reby_gift_pack)
    end
end

function P:isMultipliper()
    return self._mttInfo.reby_multiple_switch == 1
end

function P:refreshConfigUI()
    if not self._mttInfo then
        return
    end

    local Panel = self:isMultipliper() and self.Multiples or self.Normal

    -- 获得筹码
    if self._mttInfo.begin_chips and self._mttInfo.begin_chips > 0 then
        bee.setText(self:find("Chip/EntryChips/chip/TEXT", Panel), _N(self._mttInfo.reby_chip_multiplier * self._mttInfo.begin_chips * self.reby_multiple[self._multiplier] / 100))
    end

    -- 重购费用
    if self._signItem then
        TournamentModel:setByinText(self:find("Chip/RebuyCosts/chip/TEXT", Panel), {
            item_id = self._signItem.item_id,
            item_num = self._signItem.item_num * self.reby_multiple[self._multiplier],
        }, true)
        bee.setIcon(self:find("Chip/RebuyCosts/chip/icon_10100001", Panel), tpl_props[self._signItem.item_id].icon)
    else
        bee.setText(self:find("Chip/RebuyCosts/chip/TEXT", Panel), _T("LAB_SHOP_COMMON_21"))
        self:find("Chip/RebuyCosts/chip/icon_10100001", Panel):SetActive(false)
    end
end

function P:refreshDeadline()
    if not self._mttInfo or GameModel.data:isInObserve() then
        if GameModel.data.room_status.is_addoning then
            local dt = GameModel.data:getAddOnBuyinRemainTime()
            if dt <= 0 then
                dt = 0
            end

            bee.setText(self.TextTime, _F("LAB_TOURNAMENT_MTT_INFO94", TimeHelp:getTimeStrHMS(dt)))
            if dt <= 0 then
                self:hideUIForce()
            end
        else
            bee.setText(self.TextTime, "")
        end
        return
    end

    local dt = GameModel.data:getRebuyRemainTime(GameModel.data:getMyPosition())
    if dt <= 0 then
        dt = 0
    end
    bee.setText(self.TextTime, _F("LAB_TIME_DES", _F(math.floor(dt))))
end

function P:refreshLiveUI(msg)
    self.Multiples:SetActive(false)
    self.Normal:SetActive(false)
    local Panel = self:isMultipliper() and self.Multiples or self.Normal

    Panel:SetActive(true)
    bee.setText(self:find("Information/Players/TEXT", Panel), msg.left_players .. "/" .. msg.cur_sign_num)
    bee.setText(self:find("Information/AverageChips/TEXT", Panel), GameModel.data:getBetChipsStr(msg.avg_chips))
    bee.setText(self:find("Information/ITM/TEXT", Panel), msg.reward_num or 0)

    if self._detailMsg.left_reby_times == -1 then
        bee.setText(self.TextCount, _T("LAB_TOURNAMENT_MTT_INFO126") .. _T("LAB_TOURNAMENT_MTT_INFO128"))
    else
        bee.setText(self.TextCount, _T("LAB_TOURNAMENT_MTT_INFO126") .. self._detailMsg.left_reby_times .. "/" .. self._mttInfo.reby_time_limit)
    end
end

function P:onBtClose()
    if GameModel.data and not GameModel.data:isInObserve() then
        Net:sendReq("pb.RebyREQ", {
            is_reby = false,
        })
    end
    P.super.onBtClose(self)
end

function P:onClickConfirm()
    Game:playSound("ui_button_confirm")

    if self._mttInfo.mtt_round ~= 0 or bee.getServerTime() >= (self._mttInfo.sign_end_time or 0) then
        UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO5"))
        return
    end

    local num = self.reby_multiple[self._multiplier]
    if self._signItem and self._signItem.item_num * num > ItemModel:getItemNumById(self._signItem.item_id) then
        QuickByModel:checkShowView(GameModel.data:getGameType())
        UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[self._signItem.item_id].name)))
        return
    end

    if not bee.checkCd("MttRebuyREQ", 2) then
        return
    end

    if GameModel.data:isInObserve() then
        Net:sendReq("pb.LeaveRoomREQ", {
            client_str = json.encode({
                key = "mtt_sign",
                tour_id = self._mttInfo.tour_id,
                item_id = self._signItem and self._signItem.item_id or 0,
                roomid = GameModel.data:getSrcRoomId(),
                multiple = num,
            })
        })
    else
        Net:sendReq("pb.RebyREQ", {
            is_reby = true,
            chips = num * self._mttInfo.reby_chip_multiplier * self._mttInfo.begin_chips / 100,
        })
    end
    bee.logEvent("tournament-mtt-rebuy", self._mttInfo and self._mttInfo.tour_id, num)
end

-- ============================== 事件处理 ==============================

function P:evt_MttRoomDetailRSP(msg)
    if msg.code ~= 0 then
        return
    end
    self._detailMsg = msg
    self:refreshLiveUI(msg)
end

function P:evt_MttPlayerNumChangeBRC(msg)
    Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})
end

function P:evt_refreshTopInfo()
    self:refreshConfigUI()
end

function P:evt_ItemChangeRSP(msg)
    self:refreshConfigUI()
end

function P:evt_RebyBRC(msg)
    if msg.seatid + 1 == GameModel.data:getMyPosition() then
        self:hideUI()
    end
end

return P