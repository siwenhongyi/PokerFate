local P = class("TournamentMTTUILayer", require("app.table.PK.PKUILayer"))

function P:onAwake()
    P.super.onAwake(self)

    self.Top = self:find("Top", self.LeftTop)
    self.BlindsInfo2 = self:find("BlindsInfo2", self.Top)
    self.BlindsInfo3 = self:find("BlindsInfo3", self.Top)
    self.Observe = self:find("Observe", self.Top)
    self.ButtonSign = self:find("ButtonSign", self.RightTop)
    self.RebuyButton = self:find("RebuyButton", self.RightTop)

    self.TextTime = self:find("TextTime", self.BlindsInfo2)
    self.TextBlind = self:find("TextBlind", self.BlindsInfo3)
    self.TextTitle = self:find("TextTitle", self.BlindsInfo3)
    self.TextBlindNext = self:find("TextBlindNext", self.BlindsInfo2)

    bee.addClick(self:find("StatsButton", self.RightTop), function()
        UiManager:showUI("TournamentIngameMTTRightList")
        Game:playSound("ui_button_confirm")
        bee.logEvent("tournament-mtt-detail", GameModel.data.room_info.tour_id)
    end)

    bee.addClick(self.ButtonSign, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("tournament-mtt-observer-sign", GameModel.data.room_info.tour_id)
        UiManager:showUI("TournamentMTTApply")
    end)

    bee.addClick(self.RebuyButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("tournament-mtt-rebuy", GameModel.data.room_info.tour_id)
        UiManager:showUI("TournamentMTTRebuy")
    end)
end

function P:onShow()
    P.super.onShow(self)

    self:evt_TourRoomRankRefreshBRC()

    bee.setText(self.TextTitle, GameModel.data:getRoomName())

    self:refreshButtonSign()
    if self.ButtonSign.activeSelf or self.RebuyButton.activeSelf then
        self:schedule(1, function()
            self:refreshButtonSign()
        end)
    end
end

function P:getBlindText(sb, bb, ante)
    if ante and ante > 0 then
        return _F("<color=#FFBE18>{p1} ({p2})</color>", _N(sb) .. "/" .. _N(bb), _N(ante))
    else
        return _F("<color=#FFBE18>{p1}</color>", _N(sb) .. "/" .. _N(bb))
    end
end

function P:refreshButtonSign()
    self.ButtonSign:SetActive(GameModel.data:isInObserve() and not GameModel.data:isInOpenObserve() and 1 == GameModel.data.room_status.mtt_sign_status)
    self.RebuyButton:SetActive(GameModel.data:isInObserve() and not GameModel.data:isInOpenObserve() and 2 == GameModel.data.room_status.mtt_sign_status)

    if self.ButtonSign.activeSelf or self.RebuyButton.activeSelf then
        local dt = (GameModel.data.room_info.sign_end_time or 0) - bee.getServerTime()
        if dt <= 0 or GameModel.data.room_info.src_room_mtt_round ~= 0 then
            self.ButtonSign:SetActive(false)
            self.RebuyButton:SetActive(false)
        end
    end
end

function P:evt_GetRoomDataRSP(msg)
    self:evt_TourRoomRankRefreshBRC()
end

function P:evt_TourRoomRankRefreshBRC()
    if GameModel.data.rank_list then
        for _, v in ipairs(GameModel.data.rank_list) do
            if v.brief.uid == PlayerModel:getUid() then
                bee.setText(self.TextRank, v.rank)
                return
            end
        end
    end
end

function P:evt_refreshBlind()
	local sb = GameModel.data:getSmallBlind()
	local bb = GameModel.data:getBigBlind()
    local ante = GameModel.data:getAnte()
	bee.setText(self.TextBlind, _T("LAB_FRIROOM_031") .. self:getBlindText(sb, bb, ante))

    self:evt_refreshNextBlind()
end

function P:evt_refreshNextBlind()
    local nextBlindInfo = GameModel.data:getNextBlindInfo()
    if not nextBlindInfo then
        bee.setText(self.TextBlindNext, _T("LAB_TOURNAMENT_SNG_INFO29"))
        self.BlindsInfo2:SetActive(false)
    else
	    bee.setText(self.TextBlindNext, _T("LAB_TOURNAMENT_SNG_INFO28") .. self:getBlindText(nextBlindInfo.small_blind, nextBlindInfo.big_blind, nextBlindInfo.ante))
        local dt = GameModel.data:getBlindUpTime()
        bee.setText(self.TextTime, TimeHelp:getTimeStrHMS(dt))
        self:once(1, function()
            self:evt_refreshNextBlind()
        end)
    end
end

function P:evt_SngSpinBRC()
end

function P:evt_BlindStatusBRC()
    self:evt_refreshBlind()
end

function P:evt_lan_mod()
    self:evt_refreshBlind()
    bee.setText(self.TextTitle, GameModel.data:getRoomName())
end

-- function P:evt_uiBlur(flag, name)
--     if name == "BackpackPreview" then
--         self:onUiBlur(flag, name)
--     end
-- end

return P