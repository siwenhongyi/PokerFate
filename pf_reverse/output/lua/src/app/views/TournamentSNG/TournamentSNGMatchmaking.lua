local P = class("TournamentSNGMatchmaking", UiBase)


function P:onAwake()
	self._openAnim, self._closeAnim = "UI_1_" .. self.__cname .. "_into", "UI_1_" .. self.__cname .. "_back"
    self.Center = self:find("AnimRoot/Center")
    self.RightTop = self:find("AnimRoot/RightTop")
    self.LeftTop = self:find("AnimRoot/LeftTop")
    self.ColorButton = self:find("ColorButton", self.RightTop)

    self.Items = {
        self:find("Item1", self.Center),
        self:find("Item3", self.Center),
    }

    self.MyItem = self:find("Item2", self.Center)

    self.TextName = self:find("TextName", self.Center)
    self.TextTip = self:find("TextTip", self.Center)
    self.Eff_poker_Ui_Tournament_gamestart = self:find("Eff_poker_Ui_Tournament_gamestart2", self.Center)
    self.CancelButton = self:find("CancelButton", self.Center)

    bee.addClick(self.CancelButton, function()
        TournamentModel:setMatchingSngInfo(0, 0, {}, 0)

        Net:sendReq("pb.LeaveRoomREQ", {
            client_str = json.encode({
                key = "tournament",
                kind = 2,
            })
        })
        bee.logEvent("tournament-signup-cancel", 1, GameModel.data.room_info.tour_id)
    end)

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        UiManager:showTip({
            text = _T("LAB_TOURNAMENT_SNG_INFO51"),
            onSure = function()
                Net:sendReq("pb.LeaveRoomREQ", {back_wait = true})
            end
        })
    end)

    bee.addClick(self.ColorButton, function()
        UiManager:showUI("SideGameView")
    end)
end

function P:onShow()
    self.Eff_poker_Ui_Tournament_gamestart:SetActive(false)
    self.CancelButton:SetActive(true)
    self.TextTip:SetActive(true)
    if self.ColorButton then
        self.ColorButton:SetActive(SettingModel:isColorGameUnlock())
    end

    bee.setText(self.TextName, GameModel.data:getRoomName())

    local player = GameModel.data:getMyPlayerInfo()
    if player then
        self:refreshItem(self.MyItem, player, true)
    end
    self:refreshUI()
end

function P:preHide()
    P.super.preHide(self)
    self.Eff_poker_Ui_Tournament_gamestart:SetActive(true)
    self.CancelButton:SetActive(false)
    self.TextTip:SetActive(false)
    Game:playSound("sound_SNG_match")

    UiManager:hideUIForce("CommonNoticeSmall")
end

function P:refreshUI()
    local players = GameModel.data:getAllPlayers()
    local index = 1
    for _, v in ipairs(players) do
        if v.on_seat and not v:isMe() then
            self:refreshItem(self.Items[index], v, false)
            index = index + 1
        end
    end
    for i = index, 2 do
        self:refreshItem(self.Items[i], nil, false)
    end

    TournamentModel:setMatchingSngInfo(GameModel.data:getRoomId(), index, GameModel.data.room_info.room_name or GameModel.data.room_info.name, GameModel.data.room_info.tour_id)
end

function P:refreshItem(item, player, showRole)
    local Mask = self:find("Mask", item)
    local Name = self:find("Name", item)
    local Status = self:find("Status", item)
    if player then
        if showRole then
            Mask:SetActive(true)
            local skin = tpl_character_skin[player.skin_id or 0]
            if skin then
                local ImageRole = self:find("Mask/ImageRole", item)
                bee.setIcon(ImageRole, skin.image, true)
                if skin.leaderboard_offset then
                    ImageRole.transform.localPosition = bee.v3(skin.leaderboard_offset[1], skin.leaderboard_offset[2])
                    if skin.leaderboard_offset[3] then
                        ImageRole.transform.localScale = bee.v3(skin.leaderboard_offset[3], skin.leaderboard_offset[3], skin.leaderboard_offset[3])
                    end
                end
                if skin.spine_rotation then
                    ImageRole.transform.localEulerAngles = bee.v3(0, 0, skin.spine_rotation)
                else
                    ImageRole.transform.localEulerAngles = bee.v3zero
                end
            end
            if player.level > 0 then
                bee.setIcon(self:find("ImageLevel", Name), tpl_level[player.level].icon)
            end
            if Status then
                Status:SetActive(false)
            end
            Name:SetActive(true)
            bee.setTextCut(self:find("TEXT", Name), player.name, 280)
        else
            Mask:SetActive(false)
            self:find("tournament_matchmaking_wait", item):SetActive(false)
            self:find("tournament_matchmaking_player_mask", item):SetActive(true)
            self:find("tournament_matchmaking_seat", item):SetActive(true)
            if Status then
                Status:SetActive(true)
                local TEXT = self:find("TEXT", Status)
                local key = "_actTag" .. item.name
                if self[key] then
                    scheduler:removeTag(self[key])
                end
                bee.setText(TEXT, _T("LAB_TOURNAMENT_SNG_INFO24"))
            end
            Name:SetActive(false)
        end
    else
        Mask:SetActive(false)
        Name:SetActive(false)
        if Status then
            Status:SetActive(true)
            local signs = {".", "..", "...", ""}
            local TEXT = self:find("TEXT", Status)

            local key = "_actTag" .. item.name
            if self[key] then
                scheduler:removeTag(self[key])
            end
            local idx = 1
            self[key] = self:schedule(1, function()
                bee.setText(TEXT, _T("LAB_TOURNAMENT_SNG_INFO23") .. signs[idx])
                idx = idx + 1
                if idx > #signs then
                    idx = 1
                end
            end)
        end
        self:find("tournament_matchmaking_wait", item):SetActive(true)
        self:find("tournament_matchmaking_player_mask", item):SetActive(false)
        self:find("tournament_matchmaking_seat", item):SetActive(false)
    end
end

function P:evt_SngRoomStartBRC(msg)
    self:hideUI()
    UiManager:hideUIForce("SideGameView")
end

function P:evt_SitDownBRC(msg)
    if GameModel.data:isSNG() then
        self:refreshUI()
    end
end

function P:evt_StandUpBRC(msg)
    if GameModel.data:isSNG() then
        self:refreshUI()
    end
end

function P:evt_ActionBRC(msg)
    self:hideUIForce()
end

return P