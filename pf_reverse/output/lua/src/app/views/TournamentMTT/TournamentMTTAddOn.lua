local P = class("TournamentMTTAddOn", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    local Tips1 = self:find("Center/Tips1", self.AnimRoot)

    self.TextTime = self:find("TextTime", Tips1)
    self.TextPlayers = self:find("Information/Players/Text", Tips1)
    self.TextAddonCnt = self:find("Information/AddOnTimes/Text", Tips1)
    self.TextAvgChips = self:find("Information/AverageChips/Text", Tips1)

    self.TextAdded = self:find("TextAdded", Tips1)
    self.AddOnButton = self:find("AddOnButton", Tips1)
    self.CloseButton = self:find("CloseButton", Tips1)

    bee.addClick(self.CloseButton, function()
        self:hideUI()
    end)

    bee.addClick(self.AddOnButton, function()
        Game:playSound("ui_button_confirm")
        if GameModel.data:isInObserve() then
            if 1 == GameModel.data.room_status.mtt_sign_status then
                Net:sendReq("pb.LeaveRoomREQ", {
                    client_str = json.encode({
                        key = "mtt_sign",
                        tour_id = self._mttInfo.tour_id,
                        item_id = self._signItem and self._signItem.item_id or 0,
                        roomid = GameModel.data:getSrcRoomId(),
                        multiple = 1,
                    })
                })
            else
                UiManager:showUI("TournamentMTTRebuy")
            end
        else
            UiManager:showUI("TournamentMTTAddOnBuyin")
            bee.logEvent("tournament-mtt-addon", self._mttInfo and self._mttInfo.tour_id)
        end
    end)
end

function P:onShow()
    self._mttInfo = GameModel.data and GameModel.data.room_info
    self._signItem, self._itemData = TournamentModel:getSignItem(self._mttInfo or {})

    Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})

    self:refreshButton()
    self:refreshTipUI()

    -- 定时刷新
    local i = 0
    self:schedule(1, function()
        self:refreshDeadline()
        i = i + 1
        if i % 3 == 0 then
            if bee.checkCd("pb.MttRoomDetailREQ", 3) then
                Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})
            end
        end
    end)
    self:refreshDeadline()

    UiManager:hideUIForce("TournamentMTTAddOnTip")
end

function P:refreshTipUI()
    if not self._mttInfo then
        return
    end

    local msg = self._detailMsg
    if not msg then
        return
    end

    -- 玩家数量
    bee.setText(self.TextPlayers, msg.left_players .. "/" .. msg.cur_sign_num)
    -- 赠购人数
    bee.setText(self.TextAddonCnt, msg.addon_cnt > 0 and msg.addon_cnt or 0)
    -- 平均筹码
    bee.setText(self.TextAvgChips, msg.avg_chips > 0 and GameModel.data:getBetChipsStr(msg.avg_chips) or "-")

    self:refreshDeadline()
end

function P:refreshButton()
    self.TextAdded:SetActive(false)
    if GameModel.data then
        if GameModel.data and GameModel.data:isInObserve() then
            if GameModel.data:isInOpenObserve() then
                self.AddOnButton:SetActive(false)
            elseif 1 == GameModel.data.room_status.mtt_sign_status then
                bee.setText(self:find("TEXT", self.AddOnButton), _T("LAB_TOURNAMENT_MTT_INFO42"))
            elseif 2 == GameModel.data.room_status.mtt_sign_status then
                bee.setText(self:find("TEXT", self.AddOnButton), _T("LAB_TOURNAMENT_MTT_INFO69"))
            else
                self.AddOnButton:SetActive(false)
            end
            if self._mttInfo.mtt_round ~= 0 then
                self.AddOnButton:SetActive(false)
            end
        else
            self.AddOnButton:SetActive(GameModel.data.room_status.left_addon_times > 0)
            self.TextAdded:SetActive(GameModel.data.room_status.left_addon_times <= 0)
        end
    end
end

function P:refreshDeadline()
    if not self._mttInfo or not GameModel.data.getAddOnBuyinRemainTime then
        bee.setText(self.TextTime, "")
        return
    end

    local dt = GameModel.data:getAddOnBuyinRemainTime()
    if dt <= 0 then
        dt = 0
    end
    bee.setText(self.TextTime, _F("LAB_TOURNAMENT_MTT_INFO96", "<color=#4aad19>" .. TimeHelp:getTimeStrHMS(dt) .. "</color>"))

    if dt <= 0 then
        self:hideUIForce()
    end
end

function P:onBtClose()
end

-- ============================== 事件处理 ==============================

function P:evt_MttRoomDetailRSP(msg)
    if msg.code ~= 0 then
        return
    end
    self._detailMsg = msg
    self:refreshTipUI()
end

function P:evt_MttPlayerNumChangeBRC(msg)
    Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})
end

function P:evt_AddonBRC(msg)
    if msg.seatid + 1 == GameModel.data:getMyPosition() then
        if not GameModel.data:isInObserve() then
            self:refreshButton()
        end
        Net:sendReq("pb.MttRoomDetailREQ", {is_req_src_room = true})
    end
end

function P:evt_MttBubbleRoundBRC(msg)
    if GameModel.data:isInObserve() then
        self.AddOnButton:SetActive(false)
    end
end

function P:evt_UserMttOverRSP()
    self:hideUIForce()
end

function P:evt_refreshShowBB()
    self:refreshTipUI()
end

return P