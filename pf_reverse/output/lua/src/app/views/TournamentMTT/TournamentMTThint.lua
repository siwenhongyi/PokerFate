local P = class("TournamentMTThint", UiBase)

function P:onAwake()
    self.inPop = true
    self.LeftBottom = self:find("AnimRoot/LeftBottom")

    self.Notice = self:find("Notice", self.LeftBottom)

    bee.addClick(self:find("NoButton", self.Notice), function()
        TournamentModel.sng_matching_num = 0
        self:hideUI()
    end)
    bee.addClick(self:find("YesButton", self.Notice), function()
        TournamentModel.sng_matching_num = 0
        self:onEnterMTT()
    end)
end

function P:onEnterMTT()
    if GameModel.data and not GameModel.data:isRecord() then
        if GameModel.data:isPlaying() and GameModel.data:isMePlaying() and not GameModel.data:isMeFold() then
            UiManager:showTip({
                text = _T("LAB_SURE_EXIT"),
                onSure = function()
                    Net:sendReq("pb.LeaveRoomREQ", {
                        client_str = json.encode({
                            key = "enterroom",
                            roomid = self._params.roomid,
                            loading = true,
                        })
                    })
                    self:hideUI()
                end
            })
        else
            Net:sendReq("pb.LeaveRoomREQ", {
                client_str = json.encode({
                    key = "enterroom",
                    roomid = self._params.roomid,
                    loading = true,
                })
            })
            self:hideUI()
        end
    else
        Net:sendReq("pb.EnterRoomREQ", {
            roomid = self._params.roomid,
            uid = PlayerModel:getUid(),
        })
        self:hideUI()
    end
end

function P:onShow()
    self:refreshUI()
end

function P:refreshUI()
    local name = ""
    for _, v in ipairs(self._params.tour_name) do
        if v.lang == LAN:getLanguage() then
            name = v.text
            break
        end
    end
    
    if bee.isInGame() then
        bee.setText(self:find("TextTip", self.Notice), _F("LAB_TOURNAMENT_SNG_INFO49", name))
    else
        bee.setText(self:find("TextTip", self.Notice), _F("LAB_TOURNAMENT_SNG_INFO53", name))
    end
end


return P