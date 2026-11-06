local P = class("TournamentMTTApply", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    local Panel = self:find("Center/Panel", self.AnimRoot)

    local Information = self:find("Information", Panel)
    self.TextPlayerCount = self:find("01/TextPlayerCount", Information)
    self.TextPrize = self:find("02/TextPrize", Information)
    self.TextAvgChip = self:find("03/TextAvgChip", Information)

    local Chip = self:find('Chip', Panel)
    self.TextGold = self:find("01/chip/TextGold", Chip)
    self.icon_10100001 = self:find("01/chip/icon_10100001", Chip)
    self.TextStartChips = self:find("02/chip/TextStartChips", Chip)

    self.TextTime = self:find("TextTime", Panel)

    self.ConfirmButton = self:find("btn/ConfirmButton", Panel)
    self.CancleButton = self:find("btn/CancleButton", Panel)
    self.ClosedButton = self:find("ClosedButton", Panel)

    bee.addClick(self:find("CloseButton", Panel), function()
        self:hideUI()
    end)
    bee.addClick(self.ConfirmButton, function()
        Game:playSound("ui_button_confirm")

        if self._mttInfo.mtt_round ~= 0 or bee.getServerTime() >= (self._mttInfo.sign_end_time or 0) then
            UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO5"))
            return
        end

        if self._signItem and self._signItem.item_num > ItemModel:getItemNumById(self._signItem.item_id) then
            UiManager:showToast(_F("LAB_SHOP_COMMON_24", _T(tpl_props[self._signItem.item_id].name)))
            return
        end
        
        if not bee.checkCd("MttSignREQ_Apply", 2) then
            return
        end

        Net:sendReq("pb.LeaveRoomREQ", {
            client_str = json.encode({
                key = "mtt_sign",
                tour_id = self._mttInfo.tour_id,
                item_id = self._signItem and self._signItem.item_id or 0,
                roomid = GameModel.data:getSrcRoomId()
            })
        })
        bee.logEvent("tournament-mtt-apply-sign", self._mttInfo and self._mttInfo.tour_id)
        self:hideUI()
    end)
    bee.addClick(self.CancleButton, function()
        self:hideUI()
    end)
end

function P:onShow()
    self._mttInfo = GameModel.data and GameModel.data.room_info
    self._signItem, self._itemData = TournamentModel:getSignItem(self._mttInfo or {})

    -- 请求实时房间详情
    Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})

    -- 刷新配置数据
    self:refreshConfigUI()

    self:schedule(1, function()
        if not self:refreshDeadline() then
            UiManager:showToast(_T("LAB_TOURNAMENT_MTT_INFO5"))
            self:hideUI()
        end
    end)
    self:refreshDeadline()
end

--- 刷新配置类数据 (报名费、初始筹码、截止时间)
function P:refreshConfigUI()
    if not self._mttInfo then
        return
    end

    bee.setText(self.TextStartChips, _N(self._mttInfo.begin_chips))

    -- 报名费用
    if self._signItem then
        TournamentModel:setByinText(self.TextGold, self._signItem, true)
        bee.setIcon(self.icon_10100001, tpl_props[self._signItem.item_id].icon)
    else
        bee.setText(self.TextGold, _T("LAB_SHOP_COMMON_21"))
        self.icon_10100001:SetActive(false)
    end
end

--- 刷新截止时间
function P:refreshDeadline()
    local dt = (self._mttInfo.sign_end_time or 0) - bee.getServerTime()
    if dt <= 0 or self._mttInfo.src_room_mtt_round ~= 0 then
        dt = 0
        bee.setText(self.TextTime, _T("LAB_TOURNAMENT_MTT_INFO5"))
        return false
    else
        bee.setText(self.TextTime, _F("LAB_TOURNAMENT_MTT_INFO113", TimeHelp:getTimeStr(dt)))
    end
    return true
end

--- 刷新实时数据 (玩家数、奖圈、平均筹码) 并更新按钮状态
function P:refreshLiveUI(msg)
    bee.setText(self.TextPlayerCount, msg.left_players .. "/" .. msg.cur_sign_num)
    bee.setText(self.TextAvgChip, GameModel.data:getBetChipsStr(msg.avg_chips))

    -- 奖圈人数
    bee.setText(self.TextPrize, msg.reward_num or 0)

    -- 按钮状态
    self:refreshButtons(msg)
end

function P:refreshButtons(msg)
end

-- ============================== 事件处理 ==============================

function P:evt_MttRoomDetailRSP(msg)
    if msg.code ~= 0 then
        return
    end
    self:refreshLiveUI(msg)
end

function P:evt_MttPlayerNumChangeBRC(msg)
    Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})
end

function P:evt_ItemChangeRSP(msg)
    self:refreshConfigUI()
end

return P