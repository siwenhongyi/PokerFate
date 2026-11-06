local P = class("TournamentMTTShowdown02", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.RightBottom = self:find("RightBottom", self.AnimRoot)
    self.Top = self:find("Top", self.AnimRoot)
    self.Bottom = self:find("Bottom", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)

    self.CharacterImage = self:find("CharacterImage", self.Center)
    self.Player = self:find("Player", self.Bottom)
    self.ImageTitle = self:find("ImageTitle", self.Player)
    self.TextName = self:find("TextName", self.Player)
    self.TextLevel = self:find("Rank/TextLevel", self.Player)

    self.ShareButton = self:find("ShareCont/ShareButton", self.LeftTop)
    self.Sharetips = self:find("ShareCont/Sharetips", self.LeftTop)

    self.TextTitle = self:find("TextTitle", self.Top)

    self.ObserveButton = self:find("ObserveButton", self.Bottom)
    self.CloseButton = self:find("CloseButton", self.RightTop)

    self.Trophy = self:find("Trophy", self.Center)

    bee.addClick(self.CloseButton, function()
		Game:playSound("ui_button_confirm")
        self:onBtClose()
    end)
    bee.addClick(self.ObserveButton, function()
        Game:playSound("ui_button_confirm")
        bee.logEvent("tournament-view", 2, GameModel.data.room_info.tour_id)
		Net:sendReq("pb.EnterRoomREQ", {roomid = GameModel.data:getRoomId(), is_observer = true, uid_being_observed = PlayerModel:getUid()})
    end)
    bee.addClick(self.ShareButton, function()
        Game:playSound("ui_button_confirm")
        self.CloseButton:SetActive(false)
        self.NextButton:SetActive(false)
        self.BuyIn:SetActive(false)
        self.ShareButton:SetActive(false)
        self.Sharetips:SetActive(false)
        UiManager:showUI("ShareMain", {id = 6})
        self:once(1, function()
            self.CloseButton:SetActive(true)
            self.NextButton:SetActive(true)
            self.BuyIn:SetActive(true)
            self.ShareButton:SetActive(true)
        end)
    end)
    GameModel:setStopLeaveRoom(true)
end

function P:onShow()
    GameModel:setStopLeaveRoom(true)
    Game:stopRoleSound()
    bee.emit("evt_gameBlur", true, self.__cname)

    self._data = self._params and self._params.data
    if not self._data then
        self._data = {
            rank = 1, 
            champion_points = 10, 
            sign_item_list = {{item_num = 30000, item_id = 10100001}}, 
            reward = {{item_id = 20410201, item_num = 1000}, {item_id = 10100001, item_num = 1000}, {item_id = 10100001, item_num = 1000}, {item_id = 70110301, item_num = 1000}}, 
            bond_inc = 10, 
            exp_inc = 10, 
            tour_name = {}, 
            tour_id=16,
            skin_id = 0,
            is_enter_win_round = true,
            winner_brief = {name = "11", uid = 11, level = 1},
            act_reward_list = {{item_id=20410201, item_num = 1000}},
        }
    end
    self.ObserveButton:SetActive(self._data.rank > 2)

    if 0 == self._data.rank then
        bee.setTextCut(self.TextName, GF.getOtherName(self._data.winner_brief.name, self._data.winner_seat_index), 460)
        bee.setText(self.TextLevel, self._data.winner_brief.level)
        if self._data.winner_brief.level > 0 then
            bee.setIcon(self:find("Rank/icon_rank_01", self.Player), tpl_level[self._data.winner_brief.level].icon)
        end
        GF.setTitleImage(self.ImageTitle, self._data.winner_brief.title, true, true)
        
        local ingame_history_player_01 = self:find("ingame_history_player_01", self.Player)
        if self._data.winner_brief.user_type == USER_TYPE.Developer then
            bee.setIcon(ingame_history_player_01, "InGame[ingame_history_player_04]")
        elseif self._data.winner_brief.user_type == USER_TYPE.Streamer then
            bee.setIcon(ingame_history_player_01, "InGame[ingame_history_player_03]")
        else
            bee.setIcon(ingame_history_player_01, "InGame[ingame_history_player_02]")
        end
    else
        bee.setTextCut(self.TextName, PlayerModel:getNameIngame(), 460)
        bee.setText(self.TextLevel, PlayerModel:getCurLevel())
        if PlayerModel:getCurLevel() > 0 then
            bee.setIcon(self:find("Rank/icon_rank_01", self.Player), tpl_level[PlayerModel:getCurLevel()].icon)
        end
        GF.setTitleImage(self.ImageTitle, PlayerModel:getTitle2(), true, true)
    end

    local skin = tpl_character_skin[self._data.skin_id or 0]

    for _, v in ipairs(self._data.tour_name) do
        if v.lang == LAN:getLanguage() then
            bee.setText(self.TextTitle, v.text)
            break
        end
    end

    self:find("01", self.Trophy):SetActive(1 == self._data.rank or 0 == self._data.rank)
    self:find("02", self.Trophy):SetActive(2 == self._data.rank)
    self:find("03", self.Trophy):SetActive(3 == self._data.rank)

    bee.invoke(self.CharacterImage, "setSkin", skin or CharacterModel:getUsingRole():getSkinData(), false, true)
    bee.invoke(self.CharacterImage, "setSkinRotate")
    Game:playSound("sound_SNG_win")
    self.ShareButton:SetActive(true)
    self.Sharetips:SetActive(not bee.isPc and not ShareModel:getPageIsShared(6))

    local Rewards01 = self:find("Rewards01", self.Bottom)
    local Rewards02 = self:find("Rewards02", self.Bottom)
    local BgView = self:find("BgView", Rewards02)
    local Item3 = self:find("Item3", Rewards02)
    Item3:SetActive(false)

    local BgItems = self:find("BgItems", Rewards01)
    local ViewItems = self:find("ViewItems/Viewport/Content", Rewards01)
    local Item1 = self:find("Item1", Rewards01)
    Item1:SetActive(false)

    local flag01, flag = false, false
    local rewards = self._data.reward
    if self._data.champion_points > 0 then
        table.insert(rewards, {item_id = GPropId.ChampionPoints, item_num = self._data.champion_points})
    end
    if #rewards > 3 then
        BgItems = ViewItems
    end
    flag01 = #rewards > 0
    GF.addItemsToParent(BgItems, Item1, rewards, BgItems == ViewItems and {} or nil)

    if self._data.bond_inc > 0 then
        flag = true
        local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
        item:SetActive(true)
        PropItem:create(item, {id = GPropId.BondSNG, num = self._data.bond_inc, format = {VipModel:getFriendshipTournament()}}): bindTips()
    end
    if self._data.exp_inc > 0 then
        flag = true
        local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
        item:SetActive(true)
        PropItem:create(item, {id = GPropId.ExpSNG, num = self._data.exp_inc, format = {VipModel:getExpTournament()}}): bindTips()
    end
    if self._data.act_reward_list then
        for _, v in ipairs(self._data.act_reward_list) do
            flag = true
            local item = CU.GameObject.Instantiate(Item3, BgView.transform, false)
            item:SetActive(true)
            PropItem:create(item, v): bindTips()
        end
    end
    Rewards01:SetActive(flag01)
    Rewards02:SetActive(flag)
    if not flag then
        Rewards01.transform.localPosition = bee.v3(0, 100, 0)
    elseif not flag01 then
        Rewards02.transform.localPosition = bee.v3(0, 100, 0)
    end

    Game:stopMusic()
end

function P:onHide()
    GameModel:setStopLeaveRoom(nil)
    bee.emit("evt_gameBlur", false, self.__cname)
    P.super.onHide(self)
end

function P:onBtClose()
    bee.enterScene("MainScene", { info = {
        key = "tournament",
        kind = 3,
    }})
end

return P