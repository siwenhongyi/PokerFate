local P = class("PKFriendsRoomLayer", require("app.table.PK.PKUILayer"))

function P:onAwake()
    P.super.onAwake(self)

    self.BlindsInfo = self:find("Top/BlindsInfo", self.LeftTop)
    self.BlindsInfo2 = self:find("Top/BlindsInfo2", self.LeftTop)

    self.RoomNumber = self:find("RoomNumber", self.RightTop)
    self.ingame_friend_game_number_bg = self:find("ingame_friend_game_number_bg", self.RoomNumber)
    self.TextNumber = self:find("TextNumber", self.ingame_friend_game_number_bg)
    self.Observe = self:find("Top/Observe", self.LeftTop)
    
    self.TextRoomType = self:find("TextRoomType", self.BlindsInfo)
    self.TextBlind = self:find("TextBlind", self.BlindsInfo)
    self.TextTime = self:find("TextTime", self.BlindsInfo2)
    self.TextBlindNext = self:find("TextBlindNext", self.BlindsInfo2)

    self.StatsButton = self:find("StatsButton", self.RightTop)
    self.ScoreButton = self:find("ScoreButton", self.RightTop)
    
    bee.addClick(self:find("CopyButton", self.ingame_friend_game_number_bg), function()
        CS.SdkHelper.copyText("" .. GameModel.data:getRoomId())
        UiManager:showToast(_T("LAB_COPY_SUC"))
    end)
    bee.addClick(self:find("InviteButton", self.RightTop), function()
        UiManager:showUI("IngameInvite")
    end)
    bee.addClick(self:find("StatsButton", self.RightTop), function()
        UiManager:showUI("TournamentSNGingame")
        Game:playSound("ui_button_confirm")

        bee.logEvent("tournament-sng-detail", 0)
    end)
    bee.addClick(self.ScoreButton, function()
        UiManager:showUI("FriendsRoomScoreBoard")
        Game:playSound("ui_button_confirm")
    end)
end

function P:onShow()
    P.super.onShow(self)

    self:refreshFriendRoomInfo()
    
    if GameModel.data and GameModel.data:isInObserve() then
        self.ChatButton:SetActive(false)
        self:find("InviteButton", self.RightTop):SetActive(false)
        if GameModel.data.friend_room_info.is_private then
            self.RoomNumber:SetActive(false)
        end
    else
        self.ChatButton:SetActive(not GameModel.data.friend_room_info.is_forbid_chat)
        self:refreshOwnerButton()
    end

    if GameModel.data then
        local isSNG = GameModel.data:isFriendSNG()
        self.StatsButton:SetActive(isSNG)
        self.BlindsInfo2:SetActive(isSNG)
        self.ScoreButton:SetActive(not isSNG and not GameModel.data:isInObserve())

        local friend_room_outlook_bg_03 = self:find("friend_room_outlook_bg_03", self.RoomNumber)
        friend_room_outlook_bg_03:SetActive(GameModel.data:isOpenObserve())
        if friend_room_outlook_bg_03.activeSelf then
            local pos = friend_room_outlook_bg_03.transform.localPosition
            pos.y = pos.y + 28
            friend_room_outlook_bg_03.transform.localPosition = pos

            pos = self.ingame_friend_game_number_bg.transform.localPosition
            pos.y = pos.y + 28
            self.ingame_friend_game_number_bg.transform.localPosition = pos
        end
    end
end

function P:refreshOwnerButton()
    if GameModel.data.friend_room_info.is_private and PlayerModel:getUid() ~= GameModel.data.friend_room_info.owner_uid then
        self:find("InviteButton", self.RightTop):SetActive(false)
        self.RoomNumber:SetActive(false)
    else
        self:find("InviteButton", self.RightTop):SetActive(true)
        self.RoomNumber:SetActive(true)
    end
end

function P:refreshFriendRoomInfo()
    bee.setText(self.TextNumber, _F("LAB_FRIROOM_040", GameModel.data:getSrcRoomId()))
    -- bee.setText(self.TextRoomType, GameModel.data.friend_room_info.is_private and _T("LAB_FRIROOM_005") or _T("LAB_FRIROOM_006"))
    bee.setText(self.TextRoomType, GF.getGameTypeName(GameModel.data:getGameType(), true))
end

function P:getBlindText(sb, bb, ante)
    if ante and ante > 0 then
        return _F("<color=#FFBE18>{p1} ({p2})</color>", _N(sb) .. "/" .. _N(bb), _N(ante))
    else
        return _F("<color=#FFBE18>{p1}</color>", _N(sb) .. "/" .. _N(bb))
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
    if not GameModel.data:isFriendSNG() then
        return
    end
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

function P:evt_FriendRoomOwnerChangeBRC(msg)
    local uid, seatid = nil, nil
    if GameModel.data then
        local info, i = GameModel.data:getPlayerByUid(msg.uid)
        if info then
            uid, seatid = info.uid, i
        end
    end
    UiManager:showToast(_F("LAB_FRIROOM_045", GF.getOtherName(msg.owner.name, seatid, uid)))
    self:refreshOwnerButton()
end

function P:evt_BlindStatusBRC()
    self:evt_refreshBlind()
end

function P:evt_lan_mod()
    P.super.evt_lan_mod(self)
    self:refreshFriendRoomInfo()
end

return P