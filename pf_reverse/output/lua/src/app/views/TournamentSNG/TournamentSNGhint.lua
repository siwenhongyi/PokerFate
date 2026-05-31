local P = class("TournamentSNGhint", UiBase)

function P:onAwake()
    self.inPop = true
    self.LeftBottom = self:find("AnimRoot/LeftBottom")

    self.Notice2 = self:find("Notice2", self.LeftBottom)
    self.NoticeLobby = self:find("NoticeLobby", self.LeftBottom)
    self.NoticeIngame = self:find("NoticeIngame", self.LeftBottom)

    bee.addClick(self:find("NoButton", self.Notice2), function()
        TournamentModel.sng_matching_num = 0
        self:hideUI()
    end)
    bee.addClick(self:find("YesButton", self.Notice2), function()
        TournamentModel.sng_matching_num = 0
        self:onEnterSNG()
    end)
    bee.addClick(self:find("BackButton", self.NoticeLobby), function()
        self:onEnterSNG(true)
    end)

    self._size = self.NoticeLobby.transform.sizeDelta
end

function P:onEnterSNG(isBack)
    if GameModel.data and not GameModel.data:isRecord() then
        if GameModel.data:isPlaying() and GameModel.data:isMePlaying() and not GameModel.data:isMeFold() then
            UiManager:showTip({
                text = _T("LAB_SURE_EXIT"),
                onSure = function()
                    Net:sendReq("pb.LeaveRoomREQ", {
                        client_str = json.encode({
                            key = "enterroom",
                            roomid = TournamentModel.sng_matching_roomid,
                            loading = true,
                        })
                    })
                    self:hideUI()
                    if isBack then
                        bee.logEvent("tournament-sng-back", 2, TournamentModel.sng_matching_tour_id)
                    else
                        bee.logEvent("tournament-sng-open", 2, TournamentModel.sng_matching_tour_id)
                    end
                end
            })
        else
            Net:sendReq("pb.LeaveRoomREQ", {
                client_str = json.encode({
                    key = "enterroom",
                    roomid = TournamentModel.sng_matching_roomid,
                    loading = true,
                })
            })
            self:hideUI()
            if isBack then
                bee.logEvent("tournament-sng-back", 2, TournamentModel.sng_matching_tour_id)
            else
                bee.logEvent("tournament-sng-open", 2, TournamentModel.sng_matching_tour_id)
            end
        end
    else
        Net:sendReq("pb.EnterRoomREQ", {
            roomid = TournamentModel.sng_matching_roomid,
            uid = PlayerModel:getUid(),
        })
        self:hideUI()
        if isBack then
            bee.logEvent("tournament-sng-back", 1, TournamentModel.sng_matching_tour_id)
        else
            bee.logEvent("tournament-sng-open", 1, TournamentModel.sng_matching_tour_id)
        end
    end
end

function P:onShow()
    if bee.isInGame() then
        self.NoticeLobby.transform.localPosition = self.NoticeIngame.transform.localPosition
    end
    self:refreshUI()
end

function P:refreshUI()
    if TournamentModel.sng_matching_num < 3 then
        bee.setText(self:find("TextTip", self.NoticeLobby), _F("LAB_TOURNAMENT_SNG_INFO46", TournamentModel.sng_matching_num, 3))
        self.NoticeLobby:SetActive(true)
        self.Notice2:SetActive(false)
    else
        if bee.isInGame() then
            bee.setText(self:find("TextTip", self.Notice2), _F("LAB_TOURNAMENT_SNG_INFO49", TournamentModel:getMatchingSngName()))
        else
            bee.setText(self:find("TextTip", self.Notice2), _F("LAB_TOURNAMENT_SNG_INFO53", TournamentModel:getMatchingSngName()))
        end
        
        self.NoticeLobby:SetActive(false)
        self.Notice2:SetActive(true)
    end
end

function P:onDrag(e)
    if self.NoticeLobby.activeSelf then
        local pos = e.delta
        local p1 = self.NoticeLobby.transform.localPosition
        p1.x = p1.x + pos.x
        p1.y = p1.y + pos.y
        self.NoticeLobby.transform.localPosition = p1
    end
end

function P:onPointerUp()
    local pos1 = self.NoticeLobby.transform.localPosition
    local pos2 = self.LeftBottom.transform.localPosition
    local pos = bee.v3(pos1.x + pos2.x, pos1.y + pos2.y)
    local flag, curPos = false, self.NoticeLobby.transform.localPosition
    if pos.x - self._size.x / 2 < -SCREEN_WIDTH_SAFE / 2 then
        curPos.x = curPos.x + (-SCREEN_WIDTH_SAFE / 2 - (pos.x - self._size.x / 2))
        flag = true
    elseif pos.x + self._size.x / 2 > SCREEN_WIDTH_SAFE / 2 then
        curPos.x = curPos.x - (pos.x + self._size.x / 2 - SCREEN_WIDTH_SAFE / 2)
        flag = true
    end
    if pos.y - self._size.y / 2 < -SCREEN_HEIGHT_SAFE / 2 then
        curPos.y = curPos.y + (-SCREEN_HEIGHT_SAFE / 2 - (pos.y - self._size.y / 2))
        flag = true
    elseif pos.y + self._size.y / 2 > SCREEN_HEIGHT_SAFE / 2 then
        curPos.y = curPos.y - (pos.y + self._size.y / 2 - SCREEN_HEIGHT_SAFE / 2)
        flag = true
    end
    if flag then
        self.NoticeLobby.transform.localPosition = curPos
    end
end

function P:evt_SngWaitingOtherEnterBRC(msg)
    self:refreshUI()
end

function P:evt_SngMatchPlayerNumRSP(msg)
    self:refreshUI()
end

function P:evt_lan_mod()
    self:refreshUI()
end

function P:evt_guide_ui_show()
    self.transform.localScale = bee.v3()
end

function P:evt_guide_ui_hide()
    self.transform.localScale = bee.v3(1, 1, 1)
end

function P:evt_loading_show()
    self.transform.localScale = bee.v3()
end

function P:evt_loading_hide()
    self.transform.localScale = bee.v3(1, 1, 1)
end


return P